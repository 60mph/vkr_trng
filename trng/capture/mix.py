#!/usr/bin/env python3
"""
mix.py — смешивание потоков энтропии.

Поддерживаемые режимы:
    --mode xor      : побайтовое XOR двух или более файлов
    --mode sha256   : SHA-256 поверх конкатенации (выход = ceil(N/64) хешей)
    --mode blake2b  : BLAKE2b-512 поверх конкатенации

XOR соответствует разделу 2.4 дипломной работы ("XOR-корректоры"); SHA/BLAKE2 —
криптографически стойкое сжатие энтропии (extractor) для главы "Постобработка".

Пример: гибридный поток из 02_zener + 04_microphone + 05_mpu6050:
    python mix.py --mode xor \\
        --in ../data/processed/02_zener/raw.bin \\
        --in ../data/processed/04_microphone/raw.bin \\
        --in ../data/processed/05_mpu6050/raw.bin \\
        --out ../data/processed/08_hybrid/xor_mix.bin
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from functools import reduce
from operator import xor as op_xor

import numpy as np


def _read(path: Path) -> np.ndarray:
    return np.fromfile(path, dtype=np.uint8)


def mode_xor(files: list[Path]) -> np.ndarray:
    arrs = [_read(p) for p in files]
    n = min(a.size for a in arrs)
    arrs = [a[:n] for a in arrs]
    return reduce(op_xor, arrs)


def mode_hash(files: list[Path], algo: str, chunk: int = 1 << 20) -> bytes:
    out = bytearray()
    for p in files:
        h = hashlib.new(algo)
        with p.open("rb") as f:
            while True:
                buf = f.read(chunk)
                if not buf: break
                h.update(buf)
        out += h.digest()
    return bytes(out)


def mode_hash_streamed(files: list[Path], algo: str, chunk: int = 64 * 1024) -> bytes:
    """Вариант: хешируем последовательные блоки конкатенации, выдаём хеш каждого блока.

    Так получается удлинённый поток с хорошими статистическими свойствами,
    подходящий для NIST STS (несколько мегабайт)."""
    files_data = [open(p, "rb") for p in files]
    out = bytearray()
    try:
        while True:
            block = bytearray()
            for fd in files_data:
                b = fd.read(chunk)
                block.extend(b)
            if not block:
                break
            h = hashlib.new(algo)
            h.update(block)
            out.extend(h.digest())
    finally:
        for fd in files_data: fd.close()
    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["xor", "sha256", "blake2b"], required=True)
    ap.add_argument("--in",   dest="inp", action="append", required=True,
                    help="путь к входному файлу (можно повторять)")
    ap.add_argument("--out",  required=True)
    args = ap.parse_args()

    files = [Path(p) for p in args.inp]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.mode == "xor":
        if len(files) < 2:
            print("Для xor нужно ≥2 файлов", file=sys.stderr); return 2
        data = mode_xor(files)
        data.tofile(out)
    elif args.mode in ("sha256", "blake2b"):
        data_b = mode_hash_streamed(files, args.mode)
        out.write_bytes(data_b)
    print(f"[*] Записано {out.stat().st_size} байт в {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
