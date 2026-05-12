#!/usr/bin/env python3
"""
report.py — сводный отчёт по одному источнику энтропии.

Принимает:
    --raw     ../data/raw/02_zener/run_001.bin              (uint16le)
    --bits    ../data/processed/02_zener/run_001_lsb1.bin    (упакованные биты)
    --nist-csv ../data/reports/02_zener/nist.csv            (опц.)
    --out-dir ../data/reports/02_zener/                     (куда писать report.md и графики)

Запускает histogram / autocorrelation / spectral / entropy и собирает
один markdown-отчёт report.md, готовый к импорту в дипломную работу (parts/05-chapter2.tex
через pandoc).

Также есть режим --compare: принимает несколько --raw/--bits пар (или путей к
готовым отчётам) и собирает сравнительную таблицу для главы 3.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


def run(cmd: list[str]) -> dict:
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(f"[!] cmd failed: {' '.join(cmd)}\n{res.stderr}", file=sys.stderr)
        return {}
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return {"_stdout": res.stdout}


def make_single_report(raw: Path | None, bits: Path | None,
                       nist_csv: Path | None, out_dir: Path,
                       source_name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    parts.append(f"# Отчёт по источнику {source_name}\n")

    # 1) Сырая часть
    raw_stats = {}
    if raw and raw.exists():
        hist_png  = out_dir / "histogram_raw.png"
        hist_json = out_dir / "histogram_raw.json"
        run([sys.executable, str(THIS_DIR / "histogram.py"),
             "--in", str(raw), "--kind", "samples", "--out", str(hist_png),
             "--json", str(hist_json), "--title", f"{source_name} — гистограмма ADC отсчётов"])
        raw_stats["hist"] = json.loads(hist_json.read_text()) if hist_json.exists() else {}

        psd_png  = out_dir / "psd_raw.png"
        psd_json = out_dir / "psd_raw.json"
        run([sys.executable, str(THIS_DIR / "spectral.py"),
             "--in", str(raw), "--out", str(psd_png), "--json", str(psd_json)])
        raw_stats["psd"] = json.loads(psd_json.read_text()) if psd_json.exists() else {}

        ac_png  = out_dir / "autocorr_raw.png"
        ac_json = out_dir / "autocorr_raw.json"
        run([sys.executable, str(THIS_DIR / "autocorrelation.py"),
             "--in", str(raw), "--kind", "samples", "--out", str(ac_png),
             "--json", str(ac_json)])
        raw_stats["acf"] = json.loads(ac_json.read_text()) if ac_json.exists() else {}

        parts.append("## Сырой ADC-сигнал\n")
        parts.append(f"![Гистограмма отсчётов]({hist_png.name})\n")
        parts.append(f"![Автокорреляция отсчётов]({ac_png.name})\n")
        parts.append(f"![PSD]({psd_png.name})\n")
        if raw_stats.get("hist"):
            h = raw_stats["hist"]
            parts.append("**Сырая статистика:** "
                         f"N={h.get('n_samples')}, mean={h.get('mean'):.2f}, "
                         f"std={h.get('std'):.2f}, χ²={h.get('chi2'):.1f}, "
                         f"p={h.get('p_value'):.2e}\n")
        if raw_stats.get("psd"):
            p = raw_stats["psd"]
            parts.append(f"**Спектр:** fs={p.get('fs_hz')} Гц, "
                         f"пик на {p.get('peak_hz')} Гц, "
                         f"медианная PSD = {p.get('median_pxx'):.2e}\n")

    # 2) Биты после извлечения
    bit_stats = {}
    if bits and bits.exists():
        ent_json = out_dir / "entropy_bits.json"
        run([sys.executable, str(THIS_DIR / "entropy.py"),
             "--in", str(bits), "--unit", "bits", "--json", str(ent_json)])
        bit_stats["entropy_bits"] = json.loads(ent_json.read_text()) if ent_json.exists() else {}
        ent_b_json = out_dir / "entropy_bytes.json"
        run([sys.executable, str(THIS_DIR / "entropy.py"),
             "--in", str(bits), "--unit", "bytes", "--json", str(ent_b_json)])
        bit_stats["entropy_bytes"] = json.loads(ent_b_json.read_text()) if ent_b_json.exists() else {}

        ac_b_png  = out_dir / "autocorr_bits.png"
        ac_b_json = out_dir / "autocorr_bits.json"
        run([sys.executable, str(THIS_DIR / "autocorrelation.py"),
             "--in", str(bits), "--kind", "bits", "--out", str(ac_b_png),
             "--json", str(ac_b_json), "--max-lag", "1024"])
        bit_stats["acf"] = json.loads(ac_b_json.read_text()) if ac_b_json.exists() else {}

        parts.append("## Извлечённые биты\n")
        parts.append(f"![Автокорреляция бит]({ac_b_png.name})\n")
        if bit_stats.get("entropy_bits"):
            e = bit_stats["entropy_bits"]
            parts.append(f"**На бит:** Шеннон={e.get('shannon_per_symbol'):.4f}, "
                         f"min-H={e.get('min_entropy_per_symbol'):.4f}, "
                         f"MCV-min-H (NIST SP 800-90B §6.3.1)={e.get('mcv_min_entropy_per_symbol'):.4f}\n")
        if bit_stats.get("entropy_bytes"):
            e = bit_stats["entropy_bytes"]
            parts.append(f"**На байт:** Шеннон={e.get('shannon_per_symbol'):.4f}/8, "
                         f"min-H={e.get('min_entropy_per_symbol'):.4f}/8, "
                         f"MCV-min-H={e.get('mcv_min_entropy_per_symbol'):.4f}/8\n")

    # 3) NIST STS
    if nist_csv and nist_csv.exists():
        parts.append("## NIST STS\n")
        with nist_csv.open() as f:
            rdr = csv.reader(f)
            header = next(rdr, None)
            rows = list(rdr)
        if header:
            parts.append("| " + " | ".join(header) + " |")
            parts.append("|" + "|".join(["---"] * len(header)) + "|")
            for row in rows:
                parts.append("| " + " | ".join(row) + " |")
        parts.append("")

    report_md = out_dir / "report.md"
    report_md.write_text("\n".join(parts), encoding="utf-8")

    # JSON-сводка для compare
    summary = {
        "source": source_name,
        "raw":    raw_stats,
        "bits":   bit_stats,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return report_md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw",  type=Path, default=None)
    ap.add_argument("--bits", type=Path, default=None)
    ap.add_argument("--nist-csv", type=Path, default=None)
    ap.add_argument("--out-dir",  type=Path, required=True)
    ap.add_argument("--source",   type=str, required=True,
                    help="имя источника, например 02_zener")
    args = ap.parse_args()

    rep = make_single_report(args.raw, args.bits, args.nist_csv, args.out_dir, args.source)
    print(f"[*] Готов отчёт: {rep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
