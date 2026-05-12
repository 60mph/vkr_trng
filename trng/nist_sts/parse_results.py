#!/usr/bin/env python3
"""
parse_results.py — преобразует finalAnalysisReport.txt → CSV + Markdown.

NIST STS 2.1.2 пишет отчёт в виде таблицы:

  ------------------------------------------------------------------------------
  C1  C2  C3  ... C10  P-VALUE   PROPORTION   STATISTICAL TEST
  ------------------------------------------------------------------------------
   3   1   0   ... 1   0.911413    10/10      Frequency
  ...

Для каждого теста есть P-VALUE (uniformity over blocks) и PROPORTION
(сколько блоков прошло). Скрипт собирает всё в:
    - results.csv  — машинно-читаемый
    - results.md   — таблица для отчёта в дипломной работе

Решение PASS/FAIL:
    - p_value >= 1e-4
    - proportion в интервале p̂ ± 3√(p̂(1-p̂)/m), p̂=0.99, m=streams.
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from pathlib import Path


# Каждая строка теста заканчивается именем теста (буквы/пробелы/символы).
LINE_RE = re.compile(
    r"^\s*"
    r"(?P<bins>(?:\s*[\d\*]+){10})\s+"          # 10 столбцов C1..C10 (могут быть * * *)
    r"(?P<pvalue>[\d\.\*]+)\s+"
    r"(?P<prop>(?:\d+/\d+|--|\*+))\s+"
    r"(?P<name>.+?)\s*$"
)


def proportion_pass(passed: int, total: int) -> tuple[bool, float, float]:
    p_hat = 0.99
    if total == 0: return False, 0.0, 0.0
    p = passed / total
    half = 3.0 * math.sqrt(p_hat * (1 - p_hat) / total)
    lo, hi = p_hat - half, p_hat + half
    return (lo <= p <= hi), lo, hi


def parse(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(errors="replace").splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        name = m["name"].strip()
        # Пропускаем строки-разделители и заголовок
        if name.lower() in ("statistical test", "statistical tests"):
            continue
        if "C1" in line and "C10" in line:
            continue

        pv_raw = m["pvalue"]
        pv: float | None
        if pv_raw == "*" * len(pv_raw) or pv_raw.startswith("*"):
            pv = None
        else:
            try:
                pv = float(pv_raw)
            except ValueError:
                pv = None

        prop_raw = m["prop"]
        if "/" in prop_raw:
            passed_s, total_s = prop_raw.split("/")
            passed, total = int(passed_s), int(total_s)
        else:
            passed = total = 0

        prop_ok, lo, hi = proportion_pass(passed, total) if total else (False, 0, 0)
        pv_ok = pv is not None and pv >= 1e-4
        verdict = "PASS" if (pv_ok and prop_ok) else "FAIL"

        rows.append({
            "test":        name,
            "p_value":     pv if pv is not None else "",
            "proportion":  prop_raw,
            "passed":      passed,
            "total":       total,
            "prop_lo":     round(lo, 4),
            "prop_hi":     round(hi, 4),
            "verdict":     verdict,
        })
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text(""); return
    keys = ["test", "p_value", "proportion", "passed", "total", "prop_lo", "prop_hi", "verdict"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows: w.writerow(r)


def write_md(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("(NIST STS не вернул ни одной валидной строки)\n"); return
    lines = [
        "| Тест | p-value | пройдено / всего | допустимый интервал | вердикт |",
        "|------|--------:|------------------|--------------------:|---------|",
    ]
    for r in rows:
        pv = f"{r['p_value']:.4f}" if isinstance(r["p_value"], float) else "—"
        prop = f"{r['passed']}/{r['total']}" if r["total"] else r["proportion"]
        ci = f"{r['prop_lo']:.3f}…{r['prop_hi']:.3f}" if r["total"] else "—"
        verdict_md = "**PASS**" if r["verdict"] == "PASS" else "**FAIL**"
        lines.append(f"| {r['test']} | {pv} | {prop} | {ci} | {verdict_md} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in",  dest="inp", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--md",  required=True)
    args = ap.parse_args()

    rows = parse(Path(args.inp))
    Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
    write_csv(rows, Path(args.csv))
    write_md(rows, Path(args.md))
    npass = sum(1 for r in rows if r["verdict"] == "PASS")
    print(f"[*] {len(rows)} тестов, PASS={npass}, FAIL={len(rows)-npass}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
