#!/usr/bin/env python3
"""
entropy.py — оценки энтропии битового потока.

Считает:
    - Шенноновскую энтропию H(X)         (на 1 бит / на 1 байт)
    - Min-entropy H_∞(X) = -log2(max p_i)
    - Most-Common-Value estimator из NIST SP 800-90B §6.3.1
      (консервативная оценка min-entropy с поправкой на конечную выборку)

Min-entropy — ключевая метрика для криптографических TRNG, потому что именно
её "съедают" extractor'ы (см. SP 800-90B / SP 800-90C).

Вход — байты (data/processed/*.bin) либо биты (--unpack).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


def shannon_entropy(counts: np.ndarray) -> float:
    n = counts.sum()
    if n == 0: return 0.0
    p = counts.astype(np.float64) / n
    p = p[p > 0]
    return float(-np.sum(p * np.log2(p)))


def min_entropy(counts: np.ndarray) -> float:
    n = counts.sum()
    if n == 0: return 0.0
    pmax = counts.max() / n
    return float(-np.log2(pmax)) if pmax > 0 else float("inf")


def mcv_estimator(counts: np.ndarray, alpha: float = 0.005) -> float:
    """Most-Common-Value estimator из NIST SP 800-90B §6.3.1.

    Возвращает консервативную оценку min-entropy на 1 символ:
        p_u = min(1, p_hat + Z_{1-α} √(p_hat(1-p_hat)/(N-1)))
        H_min ≈ -log2(p_u)
    где p_hat — относительная частота самого частого символа,
    α=0.005 → Z=2.576 (двусторонний 99%-й интервал)."""
    from scipy.stats import norm
    n = int(counts.sum())
    if n < 2: return 0.0
    p_hat = counts.max() / n
    z = float(norm.ppf(1 - alpha))
    p_u = min(1.0, p_hat + z * float(np.sqrt(p_hat * (1 - p_hat) / (n - 1))))
    return float(-np.log2(p_u)) if p_u > 0 else float("inf")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--unit", choices=["bits", "bytes"], default="bytes",
                    help="оценивать энтропию по битам (2 символа) или по байтам (256 символов)")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    raw = np.fromfile(Path(args.inp), dtype=np.uint8)
    if args.unit == "bits":
        bits = np.unpackbits(raw, bitorder="big")
        counts = np.bincount(bits, minlength=2)
        n_symbols = 2
    else:
        counts = np.bincount(raw, minlength=256)
        n_symbols = 256

    h_shannon = shannon_entropy(counts)
    h_min     = min_entropy(counts)
    h_mcv     = mcv_estimator(counts)

    stats = {
        "input":               args.inp,
        "unit":                args.unit,
        "n":                   int(counts.sum()),
        "alphabet":            n_symbols,
        "shannon_per_symbol":  h_shannon,
        "min_entropy_per_symbol": h_min,
        "mcv_min_entropy_per_symbol": h_mcv,
        "max_count_fraction":  float(counts.max() / counts.sum() if counts.sum() else 0),
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    if args.json:
        Path(args.json).write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
