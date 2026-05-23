#!/usr/bin/env python3
"""
Симуляция типичной (и небезопасной) схемы Arduino:

    randomSeed(analogRead(A0));
    ...
    x = random(256);   // или random() в loop

Реализует LCG из Arduino AVR core (WMath.cpp):
    next = next * 1103515245 + 12345
    random() = (next / 65536) % 32768
    random(howbig) = random() % howbig

Режимы:
  setup_once  — один randomSeed(analogRead) по первому отсчёту сырья, далее
                только вызовы random(256) (классика «засеяли в setup — крутим PRNG»).
  each_sample — на каждый отсчёт ADC: randomSeed(sample); random(256) (ещё хуже,
                но встречается в примерах из форумов).

Вход: uint16le raw (значение как analogRead: младшие 10 бит).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


class ArduinoRandom:
    """Совместимо с Arduino AVR random() / randomSeed()."""

    __slots__ = ("_next",)

    def __init__(self) -> None:
        self._next = 1

    def seed(self, seed: int) -> None:
        if seed != 0:
            self._next = int(seed) & 0xFFFFFFFF

    def random(self) -> int:
        self._next = (self._next * 1103515245 + 12345) & 0xFFFFFFFF
        return (self._next // 65536) % 32768

    def random_range(self, howbig: int) -> int:
        if howbig == 0:
            return 0
        return self.random() % howbig


def stream_setup_once(seed_sample: int, nbytes: int) -> np.ndarray:
    rng = ArduinoRandom()
    rng.seed(int(seed_sample) & 0x3FF)
    out = np.empty(nbytes, dtype=np.uint8)
    for i in range(nbytes):
        out[i] = rng.random_range(256)
    return out


def stream_each_sample(samples: np.ndarray, nbytes: int) -> np.ndarray:
    rng = ArduinoRandom()
    n = min(samples.size, nbytes)
    out = np.empty(n, dtype=np.uint8)
    for i in range(n):
        rng.seed(int(samples[i]) & 0x3FF)
        out[i] = rng.random_range(256)
    if n < nbytes:
        # дополнить PRNG после последнего re-seed
        rng.seed(int(samples[-1]) & 0x3FF)
        tail = np.empty(nbytes - n, dtype=np.uint8)
        for j in range(tail.size):
            tail[j] = rng.random_range(256)
        out = np.concatenate([out, tail])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", required=True, help="сырой uint16le .bin")
    ap.add_argument("--out", required=True, help="выходной байтовый поток")
    ap.add_argument(
        "--mode",
        choices=["setup_once", "each_sample"],
        default="setup_once",
        help="setup_once: seed из первого отсчёта; each_sample: re-seed на каждый ADC",
    )
    ap.add_argument(
        "--bytes",
        type=int,
        default=1_250_000,
        help="сколько байт сгенерировать (по умолчанию 10×1Mbit для STS)",
    )
    args = ap.parse_args()

    if args.bytes < 1:
        print("--bytes >= 1", file=sys.stderr)
        return 2

    raw = np.fromfile(Path(args.inp), dtype="<u2")
    if raw.size == 0:
        print("[!] пустой вход", file=sys.stderr)
        return 1

    if args.mode == "setup_once":
        blob = stream_setup_once(int(raw[0]), args.bytes)
        seed_note = int(raw[0]) & 0x3FF
        print(
            f"[*] randomSeed(analogRead(A0)) ← {seed_note} (первый отсчёт); "
            f"далее {args.bytes}× random(256)",
            file=sys.stderr,
        )
    else:
        blob = stream_each_sample(raw, args.bytes)
        print(
            f"[*] на каждый из min({raw.size}, {args.bytes}) отсчётов: "
            f"randomSeed(ADC); random(256)",
            file=sys.stderr,
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    blob.tofile(out)
    print(f"[*] записано {blob.size} B → {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
