#!/usr/bin/env python3
"""
autocorrelation.py — автокорреляция битового или отсчётного потока.

Для ГИСП — критически важная метрика (формула из главы 1 дипломной работы):
    Corr(X_t, X_{t+τ}) = E[(X_t - μ)(X_{t+τ} - μ)] / σ².

Для случайной последовательности |Corr(τ)| ≈ 1/√N для τ > 0.
Если на каком-то лаге автокорреляция систематически выше — есть периодичность.

Режимы:
    --kind samples : строит автокорреляцию uint16-выборок (для лучшей видимости
                     периодик: 50 Гц помехи, артефакты ADC)
    --kind bits    : строит автокорреляцию ВЫХОДНЫХ БИТ (после extract_bits.py)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def autocorr_fft(x: np.ndarray, max_lag: int) -> np.ndarray:
    """Эффективная (FFT) автокорреляция нормированного сигнала."""
    x = x.astype(np.float64)
    x -= x.mean()
    n = x.size
    # Длина FFT — ближайшая степень двойки выше 2n.
    fft_n = 1 << (int(np.ceil(np.log2(2 * n))) )
    F = np.fft.rfft(x, n=fft_n)
    acf = np.fft.irfft(F * F.conj(), n=fft_n).real[:max_lag + 1]
    acf /= acf[0]
    return acf


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in",   dest="inp", required=True)
    ap.add_argument("--kind", choices=["samples", "bits"], required=True)
    ap.add_argument("--max-lag", type=int, default=4096)
    ap.add_argument("--out", required=True, help=".png")
    ap.add_argument("--json", default=None)
    ap.add_argument("--max-points", type=int, default=2_000_000,
                    help="ограничение объёма для скорости (хвост отбрасываем)")
    ap.add_argument("--title", default=None, help="заголовок рисунка (без имён файлов)")
    args = ap.parse_args()

    src = Path(args.inp)
    if args.kind == "samples":
        x = np.fromfile(src, dtype="<u2").astype(np.float64)
    else:
        bytes_ = np.fromfile(src, dtype=np.uint8)
        x = np.unpackbits(bytes_, bitorder="big").astype(np.float64)

    if x.size > args.max_points:
        x = x[: args.max_points]

    max_lag = min(args.max_lag, x.size - 1)
    acf = autocorr_fft(x, max_lag)

    # Двусторонний 95% доверительный интервал — ±1.96/√N
    ci = 1.96 / np.sqrt(x.size)
    n_outside = int(np.sum(np.abs(acf[1:]) > ci))
    pct_outside = n_outside / max_lag

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "axes.titlepad": 8,
        }
    )

    base_title = (
        "Автокорреляция отсчётов АЦП"
        if args.kind == "samples"
        else "Автокорреляция битового потока"
    )
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(acf, lw=0.8, color="#1f4f8c")
    ax.axhline(+ci, color="crimson", lw=0.7, ls="--", alpha=0.85)
    ax.axhline(-ci, color="crimson", lw=0.7, ls="--", alpha=0.85)
    ax.set_xlabel(r"Лаг $\tau$")
    ax.set_ylabel(r"Нормированная АКФ $\rho(\tau)$")
    ax.set_title(args.title or base_title)
    ax.grid(True, ls=":", lw=0.5, alpha=0.5)
    ax.text(0.98, 0.95,
            f"$\\tau_\\mathrm{{max}}={max_lag}$\n"
            f"Вне 95% ДИ: {n_outside}/{max_lag} ({pct_outside*100:.1f}%)",
            ha="right", va="top", transform=ax.transAxes,
            bbox=dict(facecolor="white", alpha=0.8))
    out_png = Path(args.out); out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(); fig.savefig(out_png, dpi=130)

    stats = {
        "n":          int(x.size),
        "max_lag":    int(max_lag),
        "ci_95":      float(ci),
        "lags_outside_ci_count": n_outside,
        "lags_outside_ci_pct":   float(pct_outside),
        "max_abs_acf_lag1":      float(np.abs(acf[1])),
        "png":        str(out_png),
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    if args.json:
        Path(args.json).write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
