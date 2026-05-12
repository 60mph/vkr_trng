#!/usr/bin/env python3
"""
von_neumann.py — дебиасинг Von Neumann.

Берём поток битов парами:
    (0,0), (1,1) → отбрасываем
    (0,1)        → 0
    (1,0)        → 1

Пара независимых, но смещённых битов даёт идеально симметричный (но
непредсказуемо разрежённый) выход. Метод упоминается в разделе 2.4 дипломной работы
("Специальные простые корректоры").

На вход — байтовый файл (биты упакованы MSB-first), на выход — то же самое.

Эффективность: при p(1)=p, KPD ≈ p(1-p) ⋅ 1 бит/2 входных битов = p(1-p)/2.
Для слабо смещённого источника (p ≈ 0.5) выход ≈ 25% от входа.

Пример:
    python von_neumann.py \\
        --in  ../data/processed/02_zener/run_001_lsb1.bin \\
        --out ../data/processed/02_zener/run_001_lsb1_vn.bin
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


def von_neumann(packed_bytes: np.ndarray) -> np.ndarray:
    bits = np.unpackbits(packed_bytes, bitorder="big")
    if bits.size % 2:
        bits = bits[:-1]
    pairs = bits.reshape(-1, 2)
    keep_mask = pairs[:, 0] != pairs[:, 1]
    out_bits = pairs[keep_mask, 0]
    n_full = (out_bits.size // 8) * 8
    return np.packbits(out_bits[:n_full], bitorder="big")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in",  dest="inp", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    src = Path(args.inp); dst = Path(args.out)
    dst.parent.mkdir(parents=True, exist_ok=True)
    raw = np.fromfile(src, dtype=np.uint8)
    print(f"[*] Von Neumann: вход {raw.size} байт", file=sys.stderr)
    out = von_neumann(raw)
    out.tofile(dst)
    ratio = out.size / raw.size if raw.size else 0
    print(f"[*] Выход {out.size} байт ({ratio*100:.1f}% от входа) → {dst}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
