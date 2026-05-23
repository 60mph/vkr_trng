#!/usr/bin/env python3
"""
pipeline.py — end-to-end конвейер для одного источника.

  capture → … → report.py (гистограмма, PSD, **осциллограммы начала записи** 1 s / ½ / ¼ / ⅛, …)

Пример:
    python scripts/pipeline.py --source 02_zener \\
                               --port /dev/ttyUSB0 \\
                               --bytes 10485760 \\
                               --nist

Два прогона NIST (LSB и Von Neumann) + автоподбор объёма raw:
    python scripts/pipeline.py --source 04_microphone \\
                               --port /dev/ttyUSB0 \\
                               --nist-dual --auto-bytes-for-nist

    NIST: `--nist` (папка `nist/`), `--nist-dual` (`nist_lsb/`, `nist_vn/`), `--auto-bytes-for-nist`.
    Нужен собранный `nist_sts/sts-2.1.2/assess` или явный `--sts`.

Если после пайплайна планируется **ещё один** этап (например
`scripts/postprocessing_nist_scan.py --after-von-neumann`), второй поток сильнее
«сжимается». Тогда имеет смысл задать `--nist-raw-margin` > 1 (или просто указать
больший явный `--bytes`, он не будет уменьшен автоматикой ниже нужного STS).

Если опустить `--port`, шаг capture пропускается, а используется уже существующий
data/raw/<source>/run_001.bin.
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable


def _packed_bits_bytes(streams: int, n_bits: int) -> int:
    return (streams * n_bits + 7) // 8


def min_raw_bytes_for_nist_lsb(streams: int, n_bits: int, lsb_per_sample: int = 1) -> int:
    """Минимум байт uint16le в raw, чтобы extract_bits дал достаточно упакованных бит для NIST."""
    need = _packed_bits_bytes(streams, n_bits)
    samples = 0
    if not (1 <= lsb_per_sample <= 8):
        raise ValueError("lsb_per_sample must be 1..8")
    while (samples * lsb_per_sample) // 8 < need:
        samples += 1
    return 2 * samples


def min_raw_bytes_for_nist_after_vn(streams: int, n_bits: int, lsb_per_sample: int = 1) -> int:
    """Минимум raw, чтобы после extract_bits и Von Neumann хватило байт на NIST.

    Теоретически KPD VN ~25% от входных бит; на сильно смещённом АЦП выход может
    быть намного меньше — закладываем коэффициент ×8.5 к требуемому объёму
    упакованного LSB (если не хватает, увеличьте --bytes вручную).
    """
    need = _packed_bits_bytes(streams, n_bits)
    lsb_need = int(math.ceil(need * 8.5))
    samples = 0
    while (samples * lsb_per_sample) // 8 < lsb_need:
        samples += 1
    return 2 * samples


def min_raw_bytes_for_nist_dual(streams: int, n_bits: int, lsb_per_sample: int = 1) -> int:
    return max(
        min_raw_bytes_for_nist_lsb(streams, n_bits, lsb_per_sample),
        min_raw_bytes_for_nist_after_vn(streams, n_bits, lsb_per_sample),
    )


def sh(cmd: list[str], **kw) -> int:
    print("→", " ".join(map(str, cmd)))
    return subprocess.run(cmd, check=True, **kw).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="например 02_zener")
    ap.add_argument("--port",   default=None,   help="serial-порт; если пропущен — используем готовый файл")
    ap.add_argument("--baud",   type=int, default=1_000_000)
    ap.add_argument("--bytes",  type=int, default=10 * 1024 * 1024)
    ap.add_argument("--bits",   type=int, default=1, help="LSB на отсчёт (1..16, для clock_jitter — до 16)")
    ap.add_argument("--no-vn",  action="store_true", help="не применять Von Neumann")
    ap.add_argument("--nist",   action="store_true", help="прогнать NIST STS (нужен собранный nist_sts/sts-2.1.2/assess)")
    ap.add_argument(
        "--nist-dual",
        action="store_true",
        help="два прогона STS: по LSB (extract_bits) и по выходу Von Neumann; нужен больший --bytes (см. --auto-bytes-for-nist)",
    )
    ap.add_argument(
        "--auto-bytes-for-nist",
        action="store_true",
        help="если задан --nist-dual (или одиночный --nist), поднять --bytes до минимума для выбранного режима",
    )
    ap.add_argument(
        "--nist-raw-margin",
        type=float,
        default=1.0,
        help=(
            "множитель к автоматически вычисленному минимуму raw (--auto-bytes-for-nist): "
            "запас длины сыгога для второй постобработки после VN, хвост отчётов и т.д. "
            "Например 8–16 при сильном последующем decimation XOR."
        ),
    )
    ap.add_argument("--sts",    default=None, help="каталог NIST sts-2.1.2 (перекрывает путь при --nist)")
    ap.add_argument("--streams",type=int, default=10)
    ap.add_argument("--nist-bits", choices=["auto", "final", "lsb"], default="auto",
                    help="auto: если после VN мало данных для STS — брать LSB; final/lsb — явно")
    ap.add_argument("--nist-n-bits", type=int, default=1_000_000, help="длина одного битового потока для assess (как в NIST, по умолчанию 1M)")
    ap.add_argument(
        "--nist-vn-streams",
        type=int,
        default=None,
        help="для --nist-dual: число потоков STS по VN (по умолчанию = --streams; меньше = укороченный прогон)",
    )
    ap.add_argument(
        "--nist-vn-n-bits",
        type=int,
        default=None,
        help="для --nist-dual: бит на поток STS по VN (по умолчанию = --nist-n-bits)",
    )
    ap.add_argument(
        "--bits-img-width",
        type=int,
        default=512,
        help="ширина PNG-визуализации битового потока (пиксели); 0 — не строить",
    )
    ap.add_argument(
        "--bits-img-height",
        type=int,
        default=0,
        help="высота PNG; 0 = floor(n_bits/width), без искусственного паддинга",
    )
    ap.add_argument(
        "--bits-img-pad",
        choices=["none", "zero"],
        default="none",
        help="если задана фиксированная height и битов меньше width×height: none — уменьшить высоту; zero — доп. нули",
    )
    ap.add_argument("--no-bits-image", action="store_true", help="не строить bits_image.png")
    args = ap.parse_args()

    want_nist = args.nist or args.nist_dual
    vn_streams = args.nist_vn_streams if args.nist_vn_streams is not None else args.streams
    vn_n_bits = args.nist_vn_n_bits if args.nist_vn_n_bits is not None else args.nist_n_bits
    if args.auto_bytes_for_nist and want_nist:
        if args.nist_dual:
            need_raw = max(
                min_raw_bytes_for_nist_lsb(args.streams, args.nist_n_bits, args.bits),
                min_raw_bytes_for_nist_after_vn(vn_streams, vn_n_bits, args.bits),
            )
        else:
            need_raw = min_raw_bytes_for_nist_lsb(
                args.streams, args.nist_n_bits, args.bits
            )
        if args.nist_raw_margin < 1.0:
            print("[!] --nist-raw-margin < 1 отсечено до 1.0", file=sys.stderr)
            args.nist_raw_margin = 1.0
        need_raw = int(math.ceil(need_raw * args.nist_raw_margin))
        if args.bytes < need_raw:
            print(
                f"[*] --auto-bytes-for-nist: {args.bytes} → {need_raw} байт raw "
                f"(uint16le, margin={args.nist_raw_margin:g}×)",
                file=sys.stderr,
            )
            args.bytes = need_raw

    sts_dir: str | None = args.sts
    if sts_dir is None and want_nist:
        default_sts = REPO / "nist_sts" / "sts-2.1.2"
        if (default_sts / "assess").is_file():
            sts_dir = str(default_sts)
        else:
            print(
                f"[!] --nist: не найден {default_sts / 'assess'}; соберите STS (nist_sts/sts-2.1.2, make).",
                file=sys.stderr,
            )
            return 1

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
    nist_for_report: Path | None = None
    nist_section_args: list[list[str]] = []
    if sts_dir:
        need_b = (args.streams * args.nist_n_bits + 7) // 8
        need_b_vn = (vn_streams * vn_n_bits + 7) // 8

        def _run_sts(
            inp: Path,
            out_sub: str,
            streams: int | None = None,
            n_bits: int | None = None,
        ) -> None:
            d = rep_dir / out_sub
            d.mkdir(parents=True, exist_ok=True)
            st = args.streams if streams is None else streams
            nb = args.nist_n_bits if n_bits is None else n_bits
            sh(
                [
                    "bash",
                    str(REPO / "nist_sts" / "run_sts.sh"),
                    "--sts",
                    sts_dir,
                    "--in",
                    str(inp),
                    "--out",
                    str(d),
                    "--streams",
                    str(st),
                    "--n-bits",
                    str(nb),
                ]
            )

        if args.nist_dual:
            if args.no_vn:
                print("[!] --nist-dual требует Von Neumann (уберите --no-vn)", file=sys.stderr)
                return 1
            lsb_ok = bits_lsb.stat().st_size >= need_b
            vn_ok = bits_final.stat().st_size >= need_b_vn
            if not lsb_ok or not vn_ok:
                mn_lsb = min_raw_bytes_for_nist_lsb(
                    args.streams, args.nist_n_bits, args.bits
                )
                mn_vn = min_raw_bytes_for_nist_after_vn(
                    vn_streams, vn_n_bits, args.bits
                )
                print(
                    f"[!] Для двух прогонов NIST нужно ≥ {need_b} B (LSB) и "
                    f"≥ {need_b_vn} B (VN). "
                    f"Сейчас: LSB={bits_lsb.stat().st_size} B, VN={bits_final.stat().st_size} B. "
                    f"Минимум raw (uint16le) ≈ LSB:{mn_lsb} B, VN:{mn_vn} B — "
                    f"задайте --bytes или --auto-bytes-for-nist.",
                    file=sys.stderr,
                )
                return 1
            _run_sts(bits_lsb, "nist_lsb")
            _run_sts(bits_final, "nist_vn", streams=vn_streams, n_bits=vn_n_bits)
            nist_for_report = rep_dir / "nist_vn" / "results.csv"
            vn_label = "После Von Neumann"
            if vn_streams != args.streams or vn_n_bits != args.nist_n_bits:
                vn_label += (
                    f" (укороченный STS: {vn_streams}×{vn_n_bits} bit)"
                )
            nist_section_args = [
                ["--nist-section", "LSB (extract_bits, без Von Neumann)", str(rep_dir / "nist_lsb" / "results.md")],
                ["--nist-section", vn_label, str(rep_dir / "nist_vn" / "results.md")],
            ]
        elif want_nist:
            nist_input = bits_final
            if args.nist_bits == "lsb":
                nist_input = bits_lsb
            elif args.nist_bits == "final":
                nist_input = bits_final
            else:
                if bits_final.stat().st_size < need_b and bits_lsb.stat().st_size >= need_b:
                    print(
                        f"[*] NIST: после Von Neumann {bits_final.stat().st_size} B < {need_b} B; "
                        "прогон STS по LSB (выход extract_bits).",
                        file=sys.stderr,
                    )
                    nist_input = bits_lsb
                elif bits_final.stat().st_size < need_b:
                    print(
                        f"[!] Ни VN ({bits_final.stat().st_size} B), ни LSB ({bits_lsb.stat().st_size} B) "
                        f"не достигают {need_b} B для STS — увеличьте --bytes.",
                        file=sys.stderr,
                    )
            if nist_input.stat().st_size >= need_b:
                _run_sts(nist_input, "nist")
                nist_for_report = rep_dir / "nist" / "results.csv"

    # 6) сводный отчёт
    cmd = [
        PY,
        str(REPO / "analysis" / "report.py"),
        "--raw",
        str(raw_bin),
        "--bits",
        str(bits_final),
        "--out-dir",
        str(rep_dir),
        "--source",
        src,
    ]
    for pair in nist_section_args:
        cmd += pair
    if not nist_section_args and nist_for_report and nist_for_report.exists():
        cmd += ["--nist-csv", str(nist_for_report)]
    sh(cmd)

    print(f"\n[*] Все артефакты — в {rep_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
