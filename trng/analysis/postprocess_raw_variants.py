#!/usr/bin/env python3
"""
Пять вариантов постобработки сырья uint16le (Arduino TRNG):

1. xor_delay8    — последовательные LSB-биты: out[i] = bit[i]⊕bit[i−8].
2. xor_lsb012    — на каждый отсчёт: бит = b0⊕б1⊕б2 ADC.
3. decim_xor8win — блок 8 отсчётов, выход XOR восьми LSB.
4. fold_lsb_byte — LSB упаковать в байты, затем байтово x^=x>>4;>>2;>>1.
5. sha256_2048   — SHA-256 блоков по 2048 байт сырого .bin (как на диске).

Выход каждого варианта — байтовый файл для NIST STS.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Callable

import numpy as np

VariantFn = Callable[[np.ndarray], np.ndarray]


def _pack_bits_msb(bits: np.ndarray) -> np.ndarray:
    bits = bits.astype(np.uint8).ravel()
    if bits.size < 8:
        return np.array([], dtype=np.uint8)
    n = (bits.size // 8) * 8
    return np.packbits(bits[:n], bitorder="big").astype(np.uint8)


def variant_xor_delay(samples: np.ndarray, delay: int = 8) -> np.ndarray:
    b = (samples & 1).astype(np.uint8).ravel()
    if b.size <= delay:
        return np.array([], dtype=np.uint8)
    ob = np.bitwise_xor(b[delay:], b[:-delay])
    return _pack_bits_msb(ob)


def variant_xor_lsb012(samples: np.ndarray) -> np.ndarray:
    s = samples.astype(np.uint32)
    bits = (((s & 1) ^ ((s >> 1) & 1) ^ ((s >> 2) & 1)) & 1).astype(np.uint8)
    return _pack_bits_msb(bits)


def variant_decim_xor8win(samples: np.ndarray) -> np.ndarray:
    ngrp = samples.size // 8
    if ngrp < 1:
        return np.array([], dtype=np.uint8)
    m = (samples[: ngrp * 8].astype(np.uint32).reshape(-1, 8) & 1).astype(np.uint8)
    bits = np.bitwise_xor.reduce(m, axis=1)
    return _pack_bits_msb(bits)


def variant_fold_on_bytes(buf: np.ndarray) -> np.ndarray:
    if buf.size == 0:
        return buf
    x = buf.astype(np.uint16).copy()
    x ^= np.right_shift(x, 4)
    x ^= np.right_shift(x, 2)
    x ^= np.right_shift(x, 1)
    return (x & 0xFF).astype(np.uint8)


VARIANTS: dict[str, tuple[str, VariantFn | None]] = {
    "xor_delay8": (
        "LSB: выходные биты out[i]=bit[i]⊕bit[i−8]",
        variant_xor_delay,
    ),
    "xor_lsb012": (
        "на отсчёт ADC: b0⊕б1⊕б2 → один выходной бит",
        variant_xor_lsb012,
    ),
    "decim_xor8win": (
        "1 бит на 8 отсчётов: XOR восьми LSB подряд",
        variant_decim_xor8win,
    ),
    "fold_lsb_byte": (
        "LSB в байты, затем XOR-shift отбеливание каждого байта",
        lambda s: variant_fold_on_bytes(_pack_bits_msb((s & 1).astype(np.uint8))),
    ),
    "sha256_2048": ("SHA-256 блоков сырых данных по 2048 B (отбеливание хэшем)", None),
}


def variant_sha256_2048_raw_file(raw_bytes: bytes, block_size: int = 2048) -> np.ndarray:
    if len(raw_bytes) < block_size:
        return np.array([], dtype=np.uint8)
    out = bytearray()
    lo = len(raw_bytes) - (len(raw_bytes) % block_size)
    if lo < block_size:
        return np.array([], dtype=np.uint8)
    for off in range(0, lo, block_size):
        out.extend(hashlib.sha256(memoryview(raw_bytes)[off : off + block_size]).digest())
    return np.frombuffer(bytes(out), dtype=np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", required=True, type=str)
    ap.add_argument("--out", required=True, type=str)
    ap.add_argument("--variant", required=True, choices=sorted(VARIANTS.keys()))
    args = ap.parse_args()

    inp = Path(args.inp)
    samples = np.fromfile(inp, dtype="<u2")
    if samples.size == 0:
        print("[!] пустой вход", file=sys.stderr)
        return 1

    if args.variant == "sha256_2048":
        out = variant_sha256_2048_raw_file(inp.read_bytes(), 2048)
        print("[*] sha256_2048: блоки сырых байт по 2048 B", file=sys.stderr)
    else:
        _, fn = VARIANTS[args.variant]
        assert fn is not None
        out = fn(samples)
        print(f"[*] {args.variant}: {VARIANTS[args.variant][0]}", file=sys.stderr)

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    out.tofile(outp)
    print(f"[*] записано {out.size} байт → {outp}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
