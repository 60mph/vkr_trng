#!/usr/bin/env python3
"""
Осциллограф по данным с Arduino: чтение порта на полной скорости, кольцевой буфер,
отрисовка «хвоста» без прореживания выборок на стороне МК.

  • binary — прошивки с trng_protocol (после BEGIN идёт uint16le), напр. 02_zener.ino.
  • text   — строки вида «ADC\\tВольт» или одно число на строку (02_zener_test).

Поток чтения UART не искусственно замедляется: при наличии данных читаются крупные
порции. Задержка и «просадка» возможны только из‑за отрисовки и размера буфера ОС.
Ось Y по умолчанию 0…1023 (полный АЦП); автоподгонка по амплитуде отключена —
масштаб и сдвиг по Y — стандартными инструментами окна matplotlib.

Пример:
    cd trng
    python3 capture/serial_scope.py --port /dev/ttyUSB0 --baud 1000000 --format binary
    python3 capture/serial_scope.py --port /dev/ttyUSB0 --baud 1000000 --format text
"""

from __future__ import annotations

import argparse
import re
import sys
import threading
import time
from collections import deque
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import serial
from matplotlib.animation import FuncAnimation

_CAPTURE_DIR = Path(__file__).resolve().parent
if str(_CAPTURE_DIR) not in sys.path:
    sys.path.insert(0, str(_CAPTURE_DIR))

from capture_serial import wait_for_begin  # noqa: E402

_FIRST_COL_TEXT = re.compile(r"^(\d+)\s")


def _feed_u16le_into_deque(raw: bytes, pending: bytearray, out: deque, lock: threading.Lock) -> None:
    pending.extend(raw)
    n_pair = len(pending) // 2
    if n_pair == 0:
        return
    take = n_pair * 2
    chunk = pending[:take]
    del pending[:take]
    arr = np.frombuffer(bytes(chunk), dtype="<u2")
    with lock:
        out.extend(int(x) for x in arr.flat)


def _reader_binary(
    port: str,
    baud: int,
    buf: deque,
    lock: threading.Lock,
    stop: threading.Event,
    banner_deadline: float,
    reset_board: bool,
    meta_box: dict,
) -> None:
    pending = bytearray()
    ser = serial.Serial(port, baud, timeout=0.02)
    try:
        if reset_board:
            time.sleep(0.15)
            ser.reset_input_buffer()
            ser.dtr = False
            time.sleep(0.05)
            ser.dtr = True
            time.sleep(0.35)
        meta, tail = wait_for_begin(ser, deadline_sec=banner_deadline)
        meta_box.clear()
        meta_box.update(meta)
        if tail:
            _feed_u16le_into_deque(tail, pending, buf, lock)
        while not stop.is_set():
            chunk = ser.read(65_536)
            if chunk:
                _feed_u16le_into_deque(chunk, pending, buf, lock)
    finally:
        ser.close()


def _parse_text_line(line: str) -> int | None:
    line = line.strip()
    if not line:
        return None
    if "\t" in line:
        left = line.split("\t", 1)[0].strip()
        if left.isdigit():
            return int(left)
    m = _FIRST_COL_TEXT.match(line)
    if m:
        return int(m.group(1))
    return None


def _reader_text(
    port: str,
    baud: int,
    buf: deque,
    lock: threading.Lock,
    stop: threading.Event,
    reset_board: bool,
) -> None:
    ser = serial.Serial(port, baud, timeout=0.02)
    decode_buf = ""
    try:
        if reset_board:
            time.sleep(0.15)
            ser.reset_input_buffer()
            ser.dtr = False
            time.sleep(0.05)
            ser.dtr = True
            time.sleep(0.35)
        while not stop.is_set():
            chunk = ser.read(16_384)
            if not chunk:
                continue
            decode_buf += chunk.decode("utf-8", errors="surrogateescape")
            while "\n" in decode_buf:
                line, decode_buf = decode_buf.split("\n", 1)
                line = line.rstrip("\r")
                v = _parse_text_line(line)
                if v is not None:
                    with lock:
                        buf.append(v)
    finally:
        ser.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=1_000_000)
    ap.add_argument("--format", choices=("binary", "text"), default="binary")
    ap.add_argument(
        "--window",
        type=int,
        default=4_096,
        help="сколько последних отсчётов на экране (по умолчанию 4096)",
    )
    ap.add_argument(
        "--buffer",
        type=int,
        default=500_000,
        help="ёмкость кольцевого буфера на ПК (старые точки отбрасываются)",
    )
    ap.add_argument("--interval-ms", type=int, default=50, help="период обновления графика")
    ap.add_argument(
        "--banner-deadline",
        type=float,
        default=25.0,
        help="только binary: секунд на поиск BEGIN",
    )
    ap.add_argument(
        "--reset-board",
        action="store_true",
        help="коротко дёрнуть DTR (как в capture_serial) перед binary-разбором",
    )
    args = ap.parse_args()

    if args.window < 16:
        print("window must be >= 16", file=sys.stderr)
        return 1

    buf: deque[int] = deque(maxlen=args.buffer)
    lock = threading.Lock()
    stop = threading.Event()
    meta_box: dict = {}

    if args.format == "binary":
        th = threading.Thread(
            target=_reader_binary,
            args=(
                args.port,
                args.baud,
                buf,
                lock,
                stop,
                args.banner_deadline,
                args.reset_board,
                meta_box,
            ),
            daemon=True,
        )
    else:
        th = threading.Thread(
            target=_reader_text,
            args=(args.port, args.baud, buf, lock, stop, args.reset_board),
            daemon=True,
        )

    th.start()

    fig, ax = plt.subplots(figsize=(11, 5))
    fig.canvas.manager.set_window_title(f"serial_scope {args.port} @ {args.baud} ({args.format})")
    (line,) = ax.plot(np.arange(args.window), np.zeros(args.window), color="cyan", lw=0.7)
    ax.set_xlim(0, args.window - 1)
    ax.set_ylim(0, 1023)
    ax.set_xlabel("Отсчёт (последние N)")
    ax.set_ylabel("ADC (10 бит)")
    ax.grid(True, alpha=0.3)
    title = ax.set_title("Ожидание данных…")

    def on_close(_evt) -> None:
        stop.set()

    fig.canvas.mpl_connect("close_event", on_close)

    def update_frame(_i: int):
        with lock:
            snap = np.asarray(buf, dtype=np.float64)
        n = len(snap)
        rate_note = ""
        if meta_box.get("SAMPLE_RATE_HZ"):
            rate_note = f"  (источник ~{meta_box['SAMPLE_RATE_HZ']} Hz)"
        title.set_text(
            f"Буфер: {n} отсчётов  |  на экране: {min(args.window, n)}  |  {args.format}{rate_note}"
        )
        if n < 2:
            return line, title
        tail = snap[-args.window :]
        x = np.arange(len(tail))
        line.set_data(x, tail)
        ax.set_xlim(0, max(len(tail) - 1, 1))
        return line, title

    ani = FuncAnimation(
        fig,
        update_frame,
        interval=args.interval_ms,
        blit=False,
        cache_frame_data=False,
    )

    try:
        plt.show()
    finally:
        stop.set()
        th.join(timeout=2.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
