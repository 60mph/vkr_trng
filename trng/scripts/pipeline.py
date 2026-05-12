#!/usr/bin/env python3
"""
pipeline.py — end-to-end конвейер для одного источника.

  capture → extract_bits → von_neumann → bits_image.png (n×m пикселей)
         → NIST STS → report.py (гистограмма, PSD, автокорреляция, …)

Пример:
    python scripts/pipeline.py --source 02_zener \\
                               --port /dev/ttyUSB0 \\
                               --bytes 10485760 \\
                               --sts ./nist_sts/sts-2.1.2

Если опустить --port, шаг capture пропускается, а используется уже существующий
data/raw/<source>/run_001.bin.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable


def sh(cmd: list[str], **kw) -> int:
    print("→", " ".join(map(str, cmd)))
    return subprocess.run(cmd, check=True, **kw).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="например 02_zener")
    ap.add_argument("--port",   default=None,   help="serial-порт; если пропущен — используем готовый файл")
    ap.add_argument("--baud",   type=int, default=1_000_000)
    ap.add_argument("--bytes",  type=int, default=10 * 1024 * 1024)
    ap.add_argument("--bits",   type=int, default=1, help="LSB на отсчёт")
    ap.add_argument("--no-vn",  action="store_true", help="не применять Von Neumann")
    ap.add_argument("--sts",    default=None, help="путь к sts-2.1.2/, если хотим NIST")
    ap.add_argument("--streams",type=int, default=10)
    ap.add_argument(
        "--bits-img-width",
        type=int,
        default=512,
        help="ширина PNG-визуализации битового потока (пиксели); 0 — не строить",
    )
    ap.add_argument(
        "--bits-img-height",
        type=int,
        default=512,
        help="высота PNG; 0 = floor(n_bits/width), все доступные биты по строкам",
    )
    ap.add_argument(
        "--bits-img-pad",
        choices=["none", "zero"],
        default="zero",
        help="если битов меньше width×height: none — уменьшить высоту; zero — доп. нули",
    )
    ap.add_argument("--no-bits-image", action="store_true", help="не строить bits_image.png")
    args = ap.parse_args()

    src = args.source
    raw_dir = REPO / "data" / "raw" / src
    proc_dir = REPO / "data" / "processed" / src
    rep_dir  = REPO / "data" / "reports" / src
    raw_dir.mkdir(parents=True, exist_ok=True)
    proc_dir.mkdir(parents=True, exist_ok=True)
    rep_dir.mkdir(parents=True, exist_ok=True)

    raw_base = raw_dir / "run_001"
    raw_bin  = raw_base.with_suffix(".bin")

    # 1) capture
    if args.port:
        sh([PY, str(REPO / "capture" / "capture_serial.py"),
            "--port", args.port, "--baud", str(args.baud),
            "--bytes", str(args.bytes), "--out", str(raw_base)])
    elif not raw_bin.exists():
        print(f"[!] {raw_bin} не существует и --port не задан", file=sys.stderr)
        return 1

    # 2) extract bits (LSB)
    bits_lsb = proc_dir / f"run_001_lsb{args.bits}.bin"
    sh([PY, str(REPO / "capture" / "extract_bits.py"),
        "--in", str(raw_bin), "--out", str(bits_lsb), "--bits", str(args.bits)])

    # 3) Von Neumann debiasing (опц.)
    bits_final = bits_lsb
    if not args.no_vn:
        bits_vn = proc_dir / f"run_001_lsb{args.bits}_vn.bin"
        sh([PY, str(REPO / "capture" / "von_neumann.py"),
            "--in", str(bits_lsb), "--out", str(bits_vn)])
        bits_final = bits_vn

    # 4) Визуализация битов как изображения n×m (ч/б, 1 бит на пиксель)
    if not args.no_bits_image and args.bits_img_width > 0:
        bits_png = rep_dir / "bits_image.png"
        cmd_img = [
            PY,
            str(REPO / "analysis" / "bits_image.py"),
            "--in",
            str(bits_final),
            "--out",
            str(bits_png),
            "--width",
            str(args.bits_img_width),
            "--height",
            str(args.bits_img_height),
            "--pad",
            args.bits_img_pad,
        ]
        sh(cmd_img)

    # 5) NIST STS (опц.)
    nist_csv = None
    if args.sts:
        nist_dir = rep_dir / "nist"
        nist_dir.mkdir(parents=True, exist_ok=True)
        sh(["bash", str(REPO / "nist_sts" / "run_sts.sh"),
            "--sts", args.sts, "--in", str(bits_final),
            "--out", str(nist_dir), "--streams", str(args.streams)])
        nist_csv = nist_dir / "results.csv"

    # 6) сводный отчёт
    cmd = [PY, str(REPO / "analysis" / "report.py"),
           "--raw", str(raw_bin),
           "--bits", str(bits_final),
           "--out-dir", str(rep_dir),
           "--source", src]
    if nist_csv and nist_csv.exists():
        cmd += ["--nist-csv", str(nist_csv)]
    sh(cmd)

    print(f"\n[*] Все артефакты — в {rep_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
