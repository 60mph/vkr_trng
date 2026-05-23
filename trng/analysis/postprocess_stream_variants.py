#!/usr/bin/env python3
"""
Постобработка **уже упакованного битового потока** (байты после `extract_bits`,
в т.ч. выход von_neumann.py), MSB-first.

Те же пять имён режимов, что и для сырья в `postprocess_raw_variants.py`, но смысл:

  xor_delay8      — побитово: out[i] = bit[i] ⊕ bit[i−8] (уже на потоке после VN).
  xor_lsb012      — аналог: три подряд бита out[i]=b[i]⊕b[i+1]⊕b[i+2].
  decim_xor8win   — XOR восьми **последовательных бит** → один выходной бит.
  fold_lsb_byte   — побайтово x^=x>>4; x>>2; x>>1 на байтах упакованного файла.
  sha256_2048     — SHA-256 блоков по 2048 байт этого файла (как на диске).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np

VARIANTS: dict[str, tuple[str, None]] = {
    "xor_delay8": ("После VN (биты): out[i]=bit[i]⊕bit[i−8]", None),
    "xor_lsb012": ("После VN: out[i]=b[i]⊕b[i+1]⊕b[i+2] (скользящий XOR тройки бит)", None),
    "decim_xor8win": ("После VN: один бит = XOR из 8 подряд входных бит", None),
    "fold_lsb_byte": ("После VN: побайтовое XOR-shift отбеливание", None),
    "sha256_2048": ("После VN: SHA-256 блоков по 2048 B файла", None),
}


def _pack_bits_msb(bits: np.ndarray) -> np.ndarray:
    b = bits.astype(np.uint8).ravel()
    if b.size < 8:
        return np.array([], dtype=np.uint8)
    n = (b.size // 8) * 8
    return np.packbits(b[:n], bitorder="big").astype(np.uint8)


def variant_xor_delay_bits(bits: np.ndarray, delay: int = 8) -> np.ndarray:
    b = bits.astype(np.uint8).ravel()
    if b.size <= delay:
        return np.array([], dtype=np.uint8)
    ob = np.bitwise_xor(b[delay:], b[:-delay])
    return _pack_bits_msb(ob)


def variant_xor3_sliding(bits: np.ndarray) -> np.ndarray:
    b = bits.astype(np.uint8).ravel()
    if b.size < 3:
        return np.array([], dtype=np.uint8)
    ob = np.bitwise_xor(np.bitwise_xor(b[:-2], b[1:-1]), b[2:])
    return _pack_bits_msb(ob)


def variant_xor_window8(bits: np.ndarray) -> np.ndarray:
    b = bits.astype(np.uint8).ravel()
    n = (b.size // 8) * 8
    if n < 8:
        return np.array([], dtype=np.uint8)
    blk = b[:n].reshape(-1, 8)
    ob = np.bitwise_xor.reduce(blk.astype(np.uint8), axis=1)
    return _pack_bits_msb(ob)


def variant_fold_bytes(buf: np.ndarray) -> np.ndarray:
    if buf.size == 0:
        return buf.astype(np.uint8)
    x = buf.astype(np.uint16).copy()
    x ^= np.right_shift(x, 4)
    x ^= np.right_shift(x, 2)
    x ^= np.right_shift(x, 1)
    return (x & 0xFF).astype(np.uint8)


def variant_sha256_2048_file(raw_bytes: bytes, block_size: int = 2048) -> np.ndarray:
    if len(raw_bytes) < block_size:
        return np.array([], dtype=np.uint8)
    lo = len(raw_bytes) - (len(raw_bytes) % block_size)
    if lo < block_size:
        return np.array([], dtype=np.uint8)
    out = bytearray()
    for off in range(0, lo, block_size):
        out.extend(hashlib.sha256(memoryview(raw_bytes)[off : off + block_size]).digest())
    return np.frombuffer(bytes(out), dtype=np.uint8)


def process_packed_bytes(buf: np.ndarray, variant: str) -> np.ndarray:
    if variant == "sha256_2048":
        return variant_sha256_2048_file(buf.astype(np.uint8).tobytes(), 2048)

    bits = np.unpackbits(buf.astype(np.uint8).ravel(), bitorder="big")
    if variant == "xor_delay8":
        return variant_xor_delay_bits(bits, 8)
    if variant == "xor_lsb012":
        return variant_xor3_sliding(bits)
    if variant == "decim_xor8win":
        return variant_xor_window8(bits)
    if variant == "fold_lsb_byte":
        return variant_fold_bytes(buf.astype(np.uint8))
    raise ValueError(f"unknown variant {variant}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--variant", choices=sorted(VARIANTS), required=True)
    args = ap.parse_args()

    inp = Path(args.inp)
    packed = np.fromfile(inp, dtype=np.uint8)
    out = process_packed_bytes(packed, args.variant)

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    out.tofile(outp)
    print(f"[*] {VARIANTS[args.variant][0]}", file=sys.stderr)
    print(f"[*] записано {out.size} байт → {outp}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
