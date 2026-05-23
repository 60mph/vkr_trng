#!/usr/bin/env python3
"""
Альтернативные постобработки + NIST STS.

**Режим 1 — сырой ADC (`uint16le`):** см. `analysis/postprocess_raw_variants.py`.

  - `postproc_<variant>.bin`, каталог отчётов `postprocessing_nist/`,
  - сводка `postprocessing_nist_comparison.md`.

**Режим 2 — поверх выхода Von Neumann (`--after-von-neumann`):**
  вход `data/processed/<source>/run_001_lsb<bits>_vn.bin`, см.
  `analysis/postprocess_stream_variants.py`.

  - `postproc_<variant>_vn2.bin`, `postprocessing_nist_after_vn/`,
  - сводка `postprocessing_nist_comparison_after_vn.md`.

Из-за второго слоя некоторые варианты **сильно короче** входа (особенно
`decim_xor8win`); при нехватке байтов для STS скрипт сообщит ошибку —
нужно **больше сырья** или тот же `pipeline` с увеличенным захватом.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PP_RAW = REPO / "analysis" / "postprocess_raw_variants.py"
PP_STREAM = REPO / "analysis" / "postprocess_stream_variants.py"
DEFAULT_STS = REPO / "nist_sts" / "sts-2.1.2"

VARIANT_ORDER = [
    "xor_delay8",
    "xor_lsb012",
    "decim_xor8win",
    "fold_lsb_byte",
    "sha256_2048",
]

SUMMARY_LINE_RE = re.compile(
    r"\*\*Сводка по типам тестов:\*\* PASS=(\d+),\s*FAIL=(\d+),\s*N/A=(\d+)",
)


def sts_min_bytes(streams: int, n_bits: int) -> int:
    return (streams * n_bits + 7) // 8


def parse_results_summary(results_md: Path) -> tuple[int | None, int | None, int | None]:
    if not results_md.is_file():
        return None, None, None
    m = SUMMARY_LINE_RE.search(results_md.read_text(encoding="utf-8"))
    if not m:
        return None, None, None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def sh(cmd: list[str]) -> None:
    print("→", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)


def load_variant_descriptions(use_stream_pp: bool) -> dict[str, str]:
    path = PP_STREAM if use_stream_pp else PP_RAW
    spec = importlib.util.spec_from_file_location("_ppmods", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    v = getattr(mod, "VARIANTS", {})
    return {str(k): str(v[k][0]) for k in v}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, help="каталог в data/raw|processed|reports")
    ap.add_argument(
        "--raw",
        default=None,
        help="сырой uint16 .bin (только без --after-von-neumann; по умолчанию raw/<source>/run_001.bin)",
    )
    ap.add_argument(
        "--after-von-neumann",
        action="store_true",
        help="вход из processed/<source>/run_001_lsb<bits>_vn.bin (постобработка после VN)",
    )
    ap.add_argument("--bits", type=int, default=1, help="суффикс lsb имени vn-файла")
    ap.add_argument(
        "--vn-in",
        default=None,
        help="явный путь к vn-бинарнику (иначе computed из --source и --bits)",
    )
    ap.add_argument("--streams", type=int, default=10)
    ap.add_argument("--nist-n-bits", type=int, default=1_000_000)
    ap.add_argument("--sts", default=None, help=f"каталог sts (по умолчанию {DEFAULT_STS})")
    ap.add_argument(
        "--variants",
        default=",".join(VARIANT_ORDER),
        help=f"id через запятую: {VARIANT_ORDER}",
    )
    ap.add_argument("--inject-link-report", type=Path, default=None)
    ap.add_argument("--skip-nist", action="store_true")
    args = ap.parse_args()

    proc_dir = REPO / "data" / "processed" / args.source
    rep_dir = REPO / "data" / "reports" / args.source
    after_vn = args.after_von_neumann
    nist_sub = "postprocessing_nist_after_vn" if after_vn else "postprocessing_nist"
    cmp_name = (
        "postprocessing_nist_comparison_after_vn.md"
        if after_vn
        else "postprocessing_nist_comparison.md"
    )

    vn_path = (
        Path(args.vn_in).expanduser().resolve()
        if args.vn_in
        else proc_dir / f"run_001_lsb{args.bits}_vn.bin"
    )
    raw_bin = Path(args.raw) if args.raw else REPO / "data" / "raw" / args.source / "run_001.bin"

    nist_parent = rep_dir / nist_sub
    sts_dir = Path(args.sts) if args.sts else DEFAULT_STS
    assess_bin = sts_dir / "assess"
    need_b = sts_min_bytes(args.streams, args.nist_n_bits)

    if assess_bin.is_file() is False:
        print(f"[!] не найден {assess_bin} — соберите NIST STS или --sts …", file=sys.stderr)
        return 1

    if after_vn:
        if not vn_path.is_file():
            print(
                f"[!] нет файла после Von Neumann: {vn_path}\n"
                f"    сначала: python3 scripts/pipeline.py --source {args.source} ...",
                file=sys.stderr,
            )
            return 1
        descriptions = load_variant_descriptions(use_stream_pp=True)
        pp_input_note = vn_path
    else:
        if not raw_bin.is_file():
            print(f"[!] нет сыгога {raw_bin}", file=sys.stderr)
            return 1
        descriptions = load_variant_descriptions(use_stream_pp=False)
        pp_input_note = raw_bin

    want = [v.strip() for v in args.variants.split(",") if v.strip()]
    for v in want:
        if v not in descriptions:
            print("[!] неизвестный variant; см. VARIANTS модуля postprocess", file=sys.stderr)
            return 1

    proc_dir.mkdir(parents=True, exist_ok=True)
    rep_dir.mkdir(parents=True, exist_ok=True)
    nist_parent.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, object]] = []

    for vid in want:
        out_name = f"postproc_{vid}_vn2.bin" if after_vn else f"postproc_{vid}.bin"
        out_bin = proc_dir / out_name

        pp_cmd = (
            [
                sys.executable,
                str(PP_STREAM),
                "--in",
                str(vn_path),
                "--out",
                str(out_bin),
                "--variant",
                vid,
            ]
            if after_vn
            else [
                sys.executable,
                str(PP_RAW),
                "--in",
                str(raw_bin),
                "--out",
                str(out_bin),
                "--variant",
                vid,
            ]
        )
        sh(pp_cmd)

        blob = out_bin.read_bytes()
        sz = len(blob)
        if sz < need_b:
            hint = (
                "\n[!] Для режима после VN чаще не хватает длины (особенно decim_xor8win). "
                "Повторите захват: pipeline с --nist-dual --auto-bytes-for-nist или больший --bytes; "
                "или исключите вариант через --variants."
            )
            if after_vn and vid == "decim_xor8win":
                hint += "\n[!] Приблизительно нужен объём vn-файла порядка 8× длины, требуемой для STS."
            print(
                f"[!] {vid}: выход {sz} B < нужных для STS {need_b} B."
                + (hint if after_vn else " Нужен более длинный raw."),
                file=sys.stderr,
            )
            return 1

        cut = blob[:need_b]
        out_bin.write_bytes(cut)

        sts_out = nist_parent / vid
        if not args.skip_nist:
            try:
                sh(
                    [
                        "bash",
                        str(REPO / "nist_sts" / "run_sts.sh"),
                        "--sts",
                        str(sts_dir),
                        "--in",
                        str(out_bin),
                        "--out",
                        str(sts_out),
                        "--streams",
                        str(args.streams),
                        "--n-bits",
                        str(args.nist_n_bits),
                    ]
                )
            except subprocess.CalledProcessError:
                print(f"[!] NIST: ошибка для {vid}; см. {sts_out}", file=sys.stderr)
                return 1

        rmd = sts_out / "results.md"
        pa, fb, na = parse_results_summary(rmd)
        summaries.append({
            "id": vid,
            "bytes": len(cut),
            "PASS": pa if pa is not None else "—",
            "FAIL": fb if fb is not None else "—",
            "N/A": na if na is not None else "—",
        })

    cmp_path = rep_dir / cmp_name
    try:
        inp_rel = Path(pp_input_note).resolve().relative_to(REPO.resolve())
    except ValueError:
        inp_rel = Path(pp_input_note)

    if after_vn:
        hdr = "# Постобработки **после Von Neumann** + NIST STS 2.1.2"
        meth = "`analysis/postprocess_stream_variants.py` (поверх `von_neumann.py`)."
        src_line = f"**Вход (после VN):** `{inp_rel}`"
    else:
        hdr = "# Сравнение постобработок сырых uint16 + NIST STS 2.1.2"
        meth = "`analysis/postprocess_raw_variants.py`."
        src_line = f"**Исходный raw:** `{inp_rel}`"

    lines: list[str] = [
        hdr,
        "",
        f"Модули задания способов: {meth}",
        "**Обрезка** до точного объёма, требуемого STS: "
        f"`streams={args.streams}`, `nist_n_bits={args.nist_n_bits}` ⇒ **{need_b}** B.",
        "",
        src_line,
        "",
        "## Краткая сводка (PASS/FAIL/N/A по типам)",
        "",
        "| # | метод | описание | байт | PASS | FAIL | N/A |",
        "|---|--------|---------|-----|------|------|-----|",
    ]

    for i, row in enumerate(summaries, 1):
        vid = str(row["id"])
        desc = descriptions.get(vid, "—").replace("|", "\\|")[:140]
        lines.append(
            f"| {i} | `{vid}` | {desc} | {row['bytes']} | {row['PASS']} | {row['FAIL']} | {row['N/A']} |",
        )

    lines += ["", "---", ""]

    for row in summaries:
        vid = str(row["id"])
        rfp = nist_parent / vid / "results.md"
        lines.append(f"## `{vid}`\n")
        if rfp.is_file():
            lines.append(rfp.read_text(encoding="utf-8").rstrip())
        else:
            lines.append("_нет STS (--skip-nist)._")
        lines.append("")
        lines.append("---")
        lines.append("")

    cmp_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"[*] сводный отчёт → {cmp_path}", file=sys.stderr)

    inject = args.inject_link_report
    if inject:
        marker_vn = "## Постобработки после Von Neumann + NIST"
        marker_rw = "## Альтернативные постобработки + NIST"
        blk = (
            f"\n{marker_vn if after_vn else marker_rw}\n\n"
            f"[{cmp_path.name}]({cmp_path.name})\n"
        )
        rep_p = inject.expanduser().resolve()
        t = rep_p.read_text(encoding="utf-8")
        needle = marker_vn if after_vn else marker_rw
        if needle in t:
            print(f"[*] уже есть блок в {rep_p}", file=sys.stderr)
        else:
            rep_p.write_text(t.rstrip() + "\n" + blk, encoding="utf-8")
            print(f"[*] дописано в {rep_p}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
