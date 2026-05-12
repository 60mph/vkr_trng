#!/usr/bin/env python3
"""
histogram.py — гистограмма + хи²-тест на равномерность.

Режимы входа:
    --kind samples : вход — uint16le ADC отсчёты (.bin из data/raw/)
    --kind bytes   : вход — байты (.bin из data/processed/)

Выход:
    .png          с гистограммой
    stdout / json: число bin'ов, χ², p-value, флаг прохождения
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import chisquare
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def chi2_uniform(counts: np.ndarray) -> tuple[float, float]:
    expected = np.full_like(counts, fill_value=counts.sum() / counts.size, dtype=float)
    res = chisquare(counts, f_exp=expected)
    return float(res.statistic), float(res.pvalue)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in",   dest="inp", required=True)
    ap.add_argument("--kind", choices=["samples", "bytes"], required=True)
    ap.add_argument("--bins", type=int, default=None,
                    help="число корзин (по умолчанию: max+1)")
    ap.add_argument("--out",  required=True, help="путь к .png")
    ap.add_argument("--json", default=None, help="опц. путь к json со статистикой")
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    src = Path(args.inp)
    if args.kind == "samples":
        data = np.fromfile(src, dtype="<u2")
    else:
        data = np.fromfile(src, dtype=np.uint8)

    if args.bins is None:
        args.bins = int(data.max()) + 1

    counts, edges = np.histogram(data, bins=args.bins, range=(0, args.bins))
    chi2, pval = chi2_uniform(counts)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(edges[:-1], counts, width=1.0)
    title = args.title or f"{src.name} — гистограмма"
    ax.set_title(title)
    ax.set_xlabel("значение")
    ax.set_ylabel("частота")
    ax.text(0.98, 0.95, f"χ² = {chi2:.1f}\np = {pval:.3e}",
            ha="right", va="top", transform=ax.transAxes,
            bbox=dict(facecolor="white", alpha=0.8))

    out_png = Path(args.out)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)

    stats = {
        "n_samples": int(data.size),
        "min": int(data.min()), "max": int(data.max()),
        "mean": float(data.mean()), "std": float(data.std()),
        "bins": args.bins,
        "chi2": chi2, "p_value": pval,
        "uniform_pass_at_alpha_0_01": bool(pval >= 0.01),
        "histogram_png": str(out_png),
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    if args.json:
        Path(args.json).write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
