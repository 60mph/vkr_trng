#!/usr/bin/env python3
"""
Строит PNG-осциллограммы сырага uint16le: первые T секунд сигнала (начало записи).

T ∈ { 1, 1/2, 1/4, 1/8 } с частотой дискретизации из .meta (device.SAMPLE_RATE_HZ),
рядом с .bin — как в spectral.py. Fallback: --fs или 76923 Гц.

Если файла короче, чем нужно для интервала, на графике — все доступные отсчёты.
При большом числе точек выполняется визуальное уплотнение (не более --max-draw)
точек по индексу, подписано в заголовке.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def fs_from_bin_meta(bin_path: Path, fallback_hz: float) -> float:
    meta_path = bin_path.with_suffix(".meta")
    if meta_path.is_file():
        try:
            m = json.loads(meta_path.read_text())
            return float(m["device"]["SAMPLE_RATE_HZ"])
        except (KeyError, ValueError, TypeError):
            pass
    return fallback_hz


def downsample_evenly(y: np.ndarray, t: np.ndarray, max_draw: int) -> tuple[np.ndarray, np.ndarray]:
    n = y.size
    if n <= max_draw:
        return y, t
    idx = np.linspace(0, n - 1, max_draw, dtype=np.int64)
    return y[idx], t[idx]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", required=True, type=Path, help="raw uint16le .bin")
    ap.add_argument("--out-dir", required=True, type=Path, help="каталог для PNG")
    ap.add_argument(
        "--fs",
        type=float,
        default=None,
        help="частота дискретизации, Гц (если нет SAMPLE_RATE_HZ в .meta)",
    )
    ap.add_argument(
        "--fallback-fs",
        type=float,
        default=76923.0,
        help="Гц если нет ни .meta, ни --fs",
    )
    ap.add_argument("--max-draw", type=int, default=50_000, help="макс. точек на кривой")
    ap.add_argument("--dpi", type=int, default=120)
    args = ap.parse_args()

    src: Path = args.inp
    if not src.is_file():
        print(f"[!] нет файла {src}", file=sys.stderr)
        return 1

    fs = args.fs
    if fs is None:
        fs = fs_from_bin_meta(src, args.fallback_fs)

    x_all = np.fromfile(src, dtype="<u2").astype(np.float64)
    if x_all.size < 2:
        print(f"[!] слишком мало отсчётов в {src}", file=sys.stderr)
        return 1

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # (доля секунды, имя файла, подпись)
    windows: list[tuple[float, str, str]] = [
        (1.0, "scope_time_1s000.png", "первая 1 с"),
        (0.5, "scope_time_500ms.png", "первая 1/2 с"),
        (0.25, "scope_time_250ms.png", "первая 1/4 с"),
        (0.125, "scope_time_125ms.png", "первая 1/8 с"),
    ]

    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
        }
    )

    for frac_sec, fname, title_ru in windows:
        n_want = int(fs * frac_sec)
        if n_want < 2:
            n_want = 2
        n_use = min(n_want, x_all.size)
        y = x_all[:n_use]
        t_ms = (np.arange(n_use, dtype=np.float64) / fs) * 1000.0

        y_d, t_d = downsample_evenly(y, t_ms, args.max_draw)
        condensed = y_d.size < y.size

        fig_w = min(14.0, 8.0 + 6.0 * (frac_sec / 1.0))
        fig, ax = plt.subplots(figsize=(fig_w, 3.8))
        ax.plot(t_d, y_d, color="#1f77b4", lw=0.35)
        ax.set_xlabel("Время от начала записи, мс")
        ax.set_ylabel("ADC, отсчёты")
        ax.set_title(
            f"Осциллограмма ({title_ru}), fs≈{fs:.0f} Гц · N={n_use}"
            + (" · на графике уплотнено" if condensed else "")
        )
        ax.set_xlim(0, float(t_ms[-1]) if n_use > 1 else 1)
        ax.grid(True, ls=":", alpha=0.45)
        if n_use < n_want:
            ax.text(
                0.98,
                0.98,
                f"запись короче: {n_use} < {n_want} отсч.",
                ha="right",
                va="top",
                fontsize=8,
                transform=ax.transAxes,
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.65),
            )
        fig.tight_layout()
        outp = out_dir / fname
        fig.savefig(outp, dpi=args.dpi)
        plt.close(fig)
        print(f"[*] {outp}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
