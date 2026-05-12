#!/usr/bin/env bash
# Прогоняет NIST STS 2.1.2 на бинарном файле и собирает результаты.
#
# Использование:
#   bash run_sts.sh \
#       --sts ./sts-2.1.2 \
#       --in  ../data/processed/02_zener/run_001_lsb1.bin \
#       --out ../data/reports/02_zener/nist \
#       --streams 10
#
# Что делает:
#   1) копирует входной файл в формат, который понимает assess (бинарный);
#   2) запускает assess в неинтерактивном режиме с заранее подготовленным
#      ответом на меню (см. heredoc ниже);
#   3) парсит finalAnalysisReport.txt в CSV/Markdown через parse_results.py.
set -euo pipefail

STS_DIR=""
IN=""
OUT=""
STREAMS=10
N_BITS=1000000

while [[ $# -gt 0 ]]; do
    case "$1" in
        --sts)     STS_DIR="$2"; shift 2;;
        --in)      IN="$2"; shift 2;;
        --out)     OUT="$2"; shift 2;;
        --streams) STREAMS="$2"; shift 2;;
        --n-bits)  N_BITS="$2"; shift 2;;
        *) echo "Unknown arg: $1" >&2; exit 2;;
    esac
done

[[ -z "$STS_DIR" || -z "$IN" || -z "$OUT" ]] && {
    echo "Usage: run_sts.sh --sts <path> --in <bin> --out <dir> [--streams 10] [--n-bits 1000000]" >&2
    exit 2
}

[[ -x "$STS_DIR/assess" ]] || { echo "[!] $STS_DIR/assess not found; build NIST STS first" >&2; exit 1; }

mkdir -p "$OUT"
ABS_OUT=$(readlink -f "$OUT")
ABS_IN=$(readlink -f "$IN")

# assess создаёт experiments/ в TEKUSCHEM каталоге → запускаем из STS_DIR
pushd "$STS_DIR" >/dev/null

# Нужно стереть прежние experiments чтобы корректно прогнать заново.
rm -rf experiments
mkdir -p experiments

# Меню assess (см. sts-2.1.2/README):
#   0 — Input File
#   <path>
#   1 — All tests
#   0 — Default parameters (m, n, blocks…)
#   1 — Apply all
#   1 — Binary input file
# и наконец число BITSTREAMS = $STREAMS, длина = $N_BITS.
./assess $N_BITS <<EOF
0
$ABS_IN
1
0
$STREAMS
1
EOF

# финальный отчёт
REPORT=experiments/AlgorithmTesting/finalAnalysisReport.txt
[[ -f "$REPORT" ]] || { echo "[!] No $REPORT" >&2; exit 1; }
cp "$REPORT" "$ABS_OUT/finalAnalysisReport.txt"
popd >/dev/null

# парсинг
python3 "$(dirname "$0")/parse_results.py" \
    --in  "$ABS_OUT/finalAnalysisReport.txt" \
    --csv "$ABS_OUT/results.csv" \
    --md  "$ABS_OUT/results.md"

echo "[*] Готово. Смотрите $ABS_OUT/results.md и $ABS_OUT/results.csv"
