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


# Формат NIST STS 2.1.2 (finalAnalysisReport.txt):
#     C1  C2  ... C10  P-VALUE [*]   PROPORTION [*]   STATISTICAL TEST
# Примеры реальных строк:
#     "10   0   0   0   0   0   0   0   0   0  0.000000 *    0/10   *  Frequency"
#     " 3   1   0   1   2   0   1   1   1   1  0.911413     10/10      Frequency"
#     " 0   0   0   0   0   0   0   0   0   0     ----     ------     RandomExcursions"
# Звёздочка после p-value/proportion — флаг «FAIL» от NIST, мы парсим её отдельно.
LINE_RE = re.compile(
    r"^\s*"
    r"(?P<bins>(?:\s*[\d\*]+){10})\s+"
    r"(?P<pvalue>[\d\.]+|----|\*+)\s*"
    r"(?P<pflag>\*?)\s+"
    r"(?P<prop>\d+/\d+|-+|\*+)\s*"
    r"(?P<propflag>\*?)\s+"
    r"(?P<name>.+?)\s*$"
)


def proportion_pass(passed: int, total: int) -> tuple[bool, float, float]:
    p_hat = 0.99
    if total == 0: return False, 0.0, 0.0
    p = passed / total
    half = 3.0 * math.sqrt(p_hat * (1 - p_hat) / total)
    lo, hi = p_hat - half, p_hat + half
    return (lo <= p <= hi), lo, hi


GENERATOR_RE = re.compile(r"generator is\s*<([^>]+)>")


def parse_input_file(path: Path) -> str | None:
    for line in path.read_text(errors="replace").splitlines()[:20]:
        m = GENERATOR_RE.search(line)
        if m:
            return m.group(1).strip()
    return None


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
        if pv_raw.startswith("-") or pv_raw.startswith("*"):
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
        if total == 0 and pv is None:
            verdict = "N/A"
        else:
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


def aggregate(rows: list[dict]) -> list[dict]:
    """Сворачивает повторяющиеся имена тестов (NonOverlappingTemplate × N шаблонов,
    CumulativeSums × 2 направления, Serial × 2 …) в одну строку:
      - sub_runs            — сколько прогонов под этим именем,
      - passed_total/total  — суммарно пройденных/проверенных битовых последовательностей,
      - p_value_min/max     — минимальное/максимальное p-value среди подтестов,
      - fail_sub            — сколько подтестов вердикт != PASS.
    Сохраняет порядок появления имён в исходном отчёте."""
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for r in rows:
        name = r["test"]
        if name not in grouped:
            grouped[name] = []
            order.append(name)
        grouped[name].append(r)

    out: list[dict] = []
    for name in order:
        items = grouped[name]
        pvs = [it["p_value"] for it in items if isinstance(it["p_value"], float)]
        total = sum(it["total"] for it in items)
        passed = sum(it["passed"] for it in items)
        verdicts = [it["verdict"] for it in items]
        fail_sub = sum(1 for v in verdicts if v == "FAIL")
        na_sub = sum(1 for v in verdicts if v == "N/A")
        if na_sub == len(items):
            verdict = "N/A"
        elif fail_sub == 0:
            verdict = "PASS"
        else:
            verdict = "FAIL"
        out.append({
            "test": name,
            "sub_runs": len(items),
            "p_min": min(pvs) if pvs else None,
            "p_max": max(pvs) if pvs else None,
            "passed": passed,
            "total": total,
            "fail_sub": fail_sub,
            "na_sub": na_sub,
            "verdict": verdict,
        })
    return out


def write_md(rows: list[dict], path: Path, input_file: str | None = None) -> None:
    if not rows:
        path.write_text("(NIST STS не вернул ни одной валидной строки)\n"); return

    agg = aggregate(rows)
    n_pass = sum(1 for r in agg if r["verdict"] == "PASS")
    n_fail = sum(1 for r in agg if r["verdict"] == "FAIL")
    n_na = sum(1 for r in agg if r["verdict"] == "N/A")
    lines: list[str] = []
    if input_file:
        lines.append(f"**Входной файл NIST:** `{input_file}`.")
        lines.append("")
    lines += [
        f"**Сводка по типам тестов:** PASS={n_pass}, FAIL={n_fail}, N/A={n_na} "
        f"(из {len(agg)} групп; всего подтестов = {sum(r['sub_runs'] for r in agg)}).",
        "",
        "| Тест | подтестов | p-value min / max | пройдено / всего | вердикт |",
        "|------|----------:|------------------:|-----------------:|---------|",
    ]
    for r in agg:
        if r["p_min"] is None:
            pv = "—"
        elif r["sub_runs"] == 1:
            pv = f"{r['p_min']:.4f}"
        else:
            pv = f"{r['p_min']:.4f} / {r['p_max']:.4f}"
        prop = f"{r['passed']}/{r['total']}" if r["total"] else "—"
        verdict_md = {
            "PASS": "**PASS**",
            "FAIL": "**FAIL**",
            "N/A":  "N/A",
        }[r["verdict"]]
        lines.append(f"| {r['test']} | {r['sub_runs']} | {pv} | {prop} | {verdict_md} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in",  dest="inp", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--md",  required=True)
    args = ap.parse_args()

    rows = parse(Path(args.inp))
    input_file = parse_input_file(Path(args.inp))
    Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
    write_csv(rows, Path(args.csv))
    write_md(rows, Path(args.md), input_file=input_file)
    npass = sum(1 for r in rows if r["verdict"] == "PASS")
    nfail = sum(1 for r in rows if r["verdict"] == "FAIL")
    nna   = sum(1 for r in rows if r["verdict"] == "N/A")
    print(f"[*] {len(rows)} подтестов: PASS={npass}, FAIL={nfail}, N/A={nna}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
