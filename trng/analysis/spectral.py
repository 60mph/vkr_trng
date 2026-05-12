#!/usr/bin/env python3
"""
spectral.py — спектральная плотность мощности (PSD).

Использует метод Уэлча (scipy.signal.welch). Для физических ГИСП спектр
ОБЯЗАТЕЛЕН — он показывает "цвет" шума:

    - белый шум (тепловой, дробовой) — плоский PSD;
    - 1/f-шум (мерцающий, MOSFET)    — наклон -10 дБ/декаду;
    - наводка 50/100 Гц              — острый пик.

См. главу 1 (определение спектральной плотности) и главу 2.1 (1/f-шум) дипломной работы.

Вход — сырые ADC-отсчёты (uint16le). Частота дискретизации берётся из метаданных
(.meta файла), либо передаётся через --fs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import welch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def get_fs_from_meta(bin_path: Path, fallback_hz: float | None) -> float:
    meta_path = bin_path.with_suffix(".meta")
    if meta_path.exists():
        m = json.loads(meta_path.read_text())
        try:
            return float(m["device"]["SAMPLE_RATE_HZ"])
        except (KeyError, ValueError):
            pass
    if fallback_hz is None:
        raise SystemExit(f"Не нашёл SAMPLE_RATE_HZ в {meta_path}; укажите --fs.")
    return fallback_hz


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in",   dest="inp", required=True, help=".bin uint16le")
    ap.add_argument("--fs",   type=float, default=None, help="частота дискретизации (Гц)")
    ap.add_argument("--nperseg", type=int, default=8192)
    ap.add_argument("--out",  required=True, help=".png")
    ap.add_argument("--json", default=None)
    ap.add_argument("--max-samples", type=int, default=2_000_000)
    ap.add_argument("--title", default=None, help="заголовок рисунка (без имён файлов)")
    args = ap.parse_args()

    src = Path(args.inp)
    fs = get_fs_from_meta(src, args.fs)

    x = np.fromfile(src, dtype="<u2").astype(np.float64)
    if x.size > args.max_samples:
        x = x[: args.max_samples]

    f, pxx = welch(x - x.mean(), fs=fs, nperseg=min(args.nperseg, x.size))

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "axes.titlepad": 8,
        }
    )

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.loglog(f[1:], pxx[1:])
    ax.set_xlabel("Частота $f$, Гц")
    ax.set_ylabel(r"СПМ $S_{xx}(f)$, отсч.²/Гц")
    ax.set_title(args.title or "Спектральная плотность мощности (метод Уэлча)")
    ax.grid(True, which="both", ls=":", lw=0.5, alpha=0.65)

    # Поиск самого яркого пика — обычно 50/100 Гц помеха.
    peak_idx = int(np.argmax(pxx[1:]) + 1)
    ax.axvline(f[peak_idx], color="r", lw=0.6, ls="--")
    ax.text(0.02, 0.95,
            f"Пик: {f[peak_idx]:.1f} Гц\nМедиана СПМ: {np.median(pxx[1:]):.2e}",
            ha="left", va="top", transform=ax.transAxes,
            bbox=dict(facecolor="white", alpha=0.8))
    out_png = Path(args.out); out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(); fig.savefig(out_png, dpi=130)

    stats = {
        "fs_hz":      fs,
        "n_samples":  int(x.size),
        "nperseg":    int(args.nperseg),
        "peak_hz":    float(f[peak_idx]),
        "peak_pxx":   float(pxx[peak_idx]),
        "median_pxx": float(np.median(pxx[1:])),
        "png":        str(out_png),
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    if args.json:
        Path(args.json).write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
