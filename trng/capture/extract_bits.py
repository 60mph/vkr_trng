#!/usr/bin/env python3
"""
extract_bits.py — преобразование сырых ADC-отсчётов в поток случайных бит.

Стратегия: брать N младших бит каждого uint16-отсчёта и упаковывать их в
байты (MSB-first). Это самый простой и распространённый "raw bit extractor"
для физических ГИСП.

Расширения:
    --whiten xor — XOR-отбеливание соседних блоков
    --skip       — отбросить первые N байт (transient после reset)
    --bits 1..8  — число LSB на отсчёт (по умолчанию 1)

Пример:
    python extract_bits.py \\
        --in  ../data/raw/02_zener/run_001.bin \\
        --out ../data/processed/02_zener/run_001_lsb1.bin \\
        --bits 1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


def extract_lsb_bits(samples: np.ndarray, n_bits: int) -> np.ndarray:
    """Возвращает байтовый массив, упакованный из младших n_bits каждого отсчёта.
    Биты упаковываются MSB-first, как в np.packbits."""
    mask = (1 << n_bits) - 1
    lsb = (samples & mask).astype(np.uint8)
    if n_bits == 1:
        bits = lsb.astype(np.uint8)
    else:
        bits = np.unpackbits(lsb.reshape(-1, 1), axis=1, count=n_bits, bitorder="big").reshape(-1)
    # Дополним до целого числа байт нулями (отрезаем хвост, чтобы не вносить смещение).
    n_full = (bits.size // 8) * 8
    return np.packbits(bits[:n_full], bitorder="big")


def whiten_xor(buf: np.ndarray, block: int = 64) -> np.ndarray:
    """XOR соседних блоков: out[i] = in[2i] ^ in[2i+1]. Снижает смещение, теряет 50% объёма."""
    n_pairs = buf.size // (2 * block)
    a = buf[: n_pairs * 2 * block].reshape(n_pairs, 2, block)
    return (a[:, 0] ^ a[:, 1]).reshape(-1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in",   dest="inp", required=True, help="путь к raw .bin (uint16le)")
    ap.add_argument("--out",  required=True)
    ap.add_argument("--bits", type=int, default=1, help="сколько младших бит брать (1..8)")
    ap.add_argument("--skip", type=int, default=0, help="пропустить N начальных uint16 отсчётов")
    ap.add_argument("--whiten", choices=["none", "xor"], default="none")
    args = ap.parse_args()

    if not (1 <= args.bits <= 8):
        print("--bits должен быть от 1 до 8", file=sys.stderr); return 2

    src = Path(args.inp)
    dst = Path(args.out)
    dst.parent.mkdir(parents=True, exist_ok=True)

    samples = np.fromfile(src, dtype="<u2")
    if args.skip:
        samples = samples[args.skip:]
    print(f"[*] Прочитано {samples.size} отсчётов, извлекаем {args.bits} LSB...",
          file=sys.stderr)

    out = extract_lsb_bits(samples, args.bits)
    if args.whiten == "xor":
        out = whiten_xor(out)

    out.tofile(dst)
    print(f"[*] Записано {out.size} байт в {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
