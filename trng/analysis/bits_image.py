#!/usr/bin/env python3
"""
bits_image.py — визуализация упакованного битового потока как изображения n×m.

Вход: бинарный файл байтов (биты упакованы MSB-first, как в extract_bits /
von_neumann).

Каждый пиксель — один бит: 0 → чёрный, 1 → белый (классическая «карта»
случайности; крупные однородные области и полосы сразу видны глазом).

Пример:
    python bits_image.py --in ../data/processed/02_zener/run_001_lsb1_vn.bin \\
        --out ../data/reports/02_zener/bits_image.png \\
        --width 512 --height 512

Если задать --height 0, высота вычисляется как floor(n_bits / width) (все
доступные биты, без дополнения нулями).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--in", dest="inp", required=True, help="файл с упакованными битами")
    ap.add_argument("--out", required=True, help="выходной .png")
    ap.add_argument("--width", "-W", type=int, required=True, help="число пикселей по горизонтали")
    ap.add_argument(
        "--height",
        "-H",
        type=int,
        default=0,
        help="число строк; 0 = автоматически из размера файла и width",
    )
    ap.add_argument(
        "--pad",
        choices=["none", "zero"],
        default="zero",
        help="если битов меньше width*height: none — обрезать область; "
        "zero — дописать нулевые биты до полного прямоугольника",
    )
    args = ap.parse_args()

    if args.width < 1:
        print("--width должен быть ≥ 1", file=sys.stderr)
        return 2

    raw = np.fromfile(Path(args.inp), dtype=np.uint8)
    bits = np.unpackbits(raw, bitorder="big")
    n_bits = int(bits.size)

    if args.height == 0:
        h = n_bits // args.width
        if h < 1:
            print(
                f"[!] Слишком мало битов ({n_bits}) для width={args.width}",
                file=sys.stderr,
            )
            return 1
        w = args.width
        need = w * h
    else:
        w, h = args.width, args.height
        need = w * h
        if n_bits < need:
            if args.pad == "none":
                h = n_bits // w
                if h < 1:
                    print(
                        f"[!] Недостаточно битов ({n_bits}) для width={w}",
                        file=sys.stderr,
                    )
                    return 1
                need = w * h
                print(
                    f"[*] Битов {n_bits} < {w}×{args.height}; "
                    f"сохраняю изображение {w}×{h}",
                    file=sys.stderr,
                )
            else:
                pad = need - n_bits
                bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])
                print(
                    f"[*] Дописано {pad} нулевых битов до {w}×{h}",
                    file=sys.stderr,
                )

    flat = bits[:need].astype(np.float32)
    img = flat.reshape(h, w)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(max(w / 100, 1), max(h / 100, 1)), dpi=100)
    ax.imshow(img, cmap="gray", vmin=0.0, vmax=1.0, interpolation="nearest")
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    fig.savefig(out, dpi=100, bbox_inches="tight", pad_inches=0)
    plt.close(fig)

    print(
        f"[*] bits_image: {w}×{h} px, {need} бит из файла "
        f"({raw.size} B упакованных) → {out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
