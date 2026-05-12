#!/usr/bin/env python3
"""
capture_serial.py — захват потока ГИСП-выборок с Arduino в бинарный файл.

Формат соответствует firmware/common/trng_protocol.h:

    1) Прошивка после reset шлёт ASCII-метаданные, заканчивающиеся "BEGIN\n".
    2) Дальше — непрерывный поток uint16 little-endian отсчётов.

Скрипт пишет:
    <out>.bin   — бинарные uint16le отсчёты
    <out>.meta  — JSON: метаданные банера + параметры захвата + checksum

Пример:
    python capture_serial.py \\
        --port /dev/ttyUSB0 --baud 1000000 \\
        --bytes 10485760 \\
        --out ../data/raw/02_zener/run_001
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import sys
import time
from pathlib import Path

import serial  # pyserial
from tqdm import tqdm


def wait_for_begin(
    ser: serial.Serial,
    deadline_sec: float = 25.0,
) -> tuple[dict, bytes]:
    """Ждёт маркер BEGIN\\n в потоке (байты), парсит ASCII-метаданные перед ним.

    Возвращает (meta, tail): tail — уже прочитанные бинарные байты после BEGIN\\n
    (их нужно первыми записать в .bin). Надёжнее readline() при «срыве» синхронизации
    или если в шине уже идёт бинарный поток без переводов строк.
    """
    meta: dict = {}
    buf = bytearray()
    # AVR: Serial.println даёт \r\n; на некоторых платах может быть только \n.
    markers = (b"BEGIN\r\n", b"BEGIN\n")
    t0 = time.time()

    def _find_marker(b: bytes) -> tuple[int, int] | None:
        for m in markers:
            i = b.find(m)
            if i >= 0:
                return i, i + len(m)
        return None

    while time.time() - t0 < deadline_sec:
        hit = _find_marker(buf)
        if hit is not None:
            idx, end_idx = hit
            break
        chunk = ser.read(2048)
        if chunk:
            buf.extend(chunk)
        else:
            time.sleep(0.01)
    else:
        raise RuntimeError(
            "Не дождались маркера BEGIN (\\n или \\r\\n) от прошивки за "
            f"{deadline_sec} с. Проверьте порт, скорость 1 Mbd, нажмите RESET на Arduino."
        )

    ascii_part = buf[:idx].decode("utf-8", errors="replace")
    tail = bytes(buf[end_idx:])

    for line in ascii_part.splitlines():
        line = line.strip()
        if line == "BEGIN" or not line:
            continue
        if line.startswith("# ") and "=" in line:
            k, _, v = line[2:].partition("=")
            meta[k.strip()] = v.strip()

    return meta, tail


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True, help="например /dev/ttyUSB0 или COM3")
    ap.add_argument("--baud", type=int, default=1_000_000)
    ap.add_argument("--bytes", type=int, default=10 * 1024 * 1024,
                    help="сколько БАЙТ (uint16=2 байта) сохранить (по умолчанию 10 МБ)")
    ap.add_argument("--out", required=True, help="базовое имя файла без расширения")
    ap.add_argument("--read-timeout", type=float, default=2.0)
    ap.add_argument(
        "--banner-deadline",
        type=float,
        default=25.0,
        help="секунд на поиск BEGIN в потоке (по умолчанию 25)",
    )
    args = ap.parse_args()

    out_base = Path(args.out).expanduser().resolve()
    out_base.parent.mkdir(parents=True, exist_ok=True)
    bin_path  = out_base.with_suffix(".bin")
    meta_path = out_base.with_suffix(".meta")

    ser = serial.Serial(args.port, args.baud, timeout=args.read_timeout)
    # Короткие паузы: после сброса прошивка сразу шлёт баннер, затем сплошной
    # бинарный поток. Долгий sleep переполняет драйверный буфер USB — BEGIN теряется.
    time.sleep(0.3)
    ser.reset_input_buffer()
    ser.setDTR(False)
    time.sleep(0.05)
    ser.setDTR(True)
    time.sleep(0.4)

    print(f"[*] Поиск BEGIN на {args.port} @ {args.baud} ...", file=sys.stderr)
    meta, preamble_bin = wait_for_begin(ser, deadline_sec=args.banner_deadline)
    print(f"[*] Источник: {meta.get('TRNG_SOURCE')!r}, "
          f"sample_bits={meta.get('SAMPLE_BITS')}, "
          f"sample_rate_hz={meta.get('SAMPLE_RATE_HZ')}",
          file=sys.stderr)

    sample_rate = int(meta.get("SAMPLE_RATE_HZ", "0") or "0")
    eta_str = ""
    if sample_rate > 0:
        eta_sec = args.bytes / 2 / sample_rate
        eta_str = f", ожид. время ~{eta_sec:.1f} с"
    print(f"[*] Запись {args.bytes} байт в {bin_path}{eta_str}", file=sys.stderr)

    # Корректное завершение по Ctrl-C — закрываем файл нормально.
    interrupted = {"v": False}
    def _sigint(_sig, _frm): interrupted["v"] = True
    signal.signal(signal.SIGINT, _sigint)

    written = 0
    # Крупные read() снижают накладные расходы; упор — в fs на плате, не в baud.
    chunk_target = 65536
    started_at = time.time()
    with bin_path.open("wb") as f, tqdm(total=args.bytes, unit="B", unit_scale=True) as bar:
        # Байты, уже прочитанные после маркера BEGIN (начало бинарного потока)
        if preamble_bin:
            n = min(len(preamble_bin), args.bytes)
            f.write(preamble_bin[:n])
            written += n
            bar.update(n)

        while written < args.bytes and not interrupted["v"]:
            need = min(chunk_target, args.bytes - written)
            data = ser.read(need)
            if not data:
                continue
            f.write(data)
            written += len(data)
            bar.update(len(data))

    elapsed = time.time() - started_at
    ser.close()

    full_meta = {
        "device": dict(meta),
        "capture": {
            "port":            args.port,
            "baud":            args.baud,
            "requested_bytes": args.bytes,
            "written_bytes":   written,
            "elapsed_sec":     elapsed,
            "started_at":      dt.datetime.now(dt.timezone.utc).isoformat(),
            "interrupted":     interrupted["v"],
        },
    }
    meta_path.write_text(json.dumps(full_meta, indent=2, ensure_ascii=False))
    print(f"[*] Записано {written} байт за {elapsed:.1f} с "
          f"({written / max(elapsed, 1e-6) / 1024:.1f} КиБ/с). Метаданные → {meta_path}",
          file=sys.stderr)
    if sample_rate > 0 and elapsed > 0.5:
        theory_max = 2.0 * sample_rate
        actual = written / elapsed
        if actual < 0.85 * theory_max:
            print(
                f"[*] Подсказка: при fs≈{sample_rate} Гц теор. потолок ~{theory_max/1024:.1f} КиБ/с; "
                f"линия {args.baud} бод обычно не лимитирует — ускорять нужно прошивку (частоту АЦП и т.п.).",
                file=sys.stderr,
            )
    return 0 if not interrupted["v"] else 130


if __name__ == "__main__":
    sys.exit(main())
