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

if [[ "$STREAMS" -lt 2 ]]; then
    echo "[*] Подсказка: при числе потоков < 2 в finalAnalysisReport часто стоит P-VALUE ---- (нет оценки однородности); для диплома обычно берут ≥10 потоков." >&2
fi

mkdir -p "$OUT"
ABS_OUT=$(readlink -f "$OUT")
ABS_IN=$(readlink -f "$IN")

need_bytes=$(( (STREAMS * N_BITS + 7) / 8 ))
insize=$(stat -c%s "$IN")
if [[ "$insize" -lt "$need_bytes" ]]; then
    echo "[!] Входной файл ${insize} B меньше требуемых ${need_bytes} B ($STREAMS потоков по $N_BITS бит). Увеличьте захват, отключите Von Neumann для STS или уменьшите --streams / --n_bits." >&2
    exit 1
fi

# assess создаёт experiments/ в текущем каталоге → запускаем из STS_DIR
pushd "$STS_DIR" >/dev/null

# Нужно стереть прежние experiments чтобы корректно прогнать заново.
rm -rf experiments
# assess открывает experiments/AlgorithmTesting/freq.txt и
# experiments/<Generator>/<TestName>/stats.txt без mkdir — каталоги должны существовать.
GEN_DIR=AlgorithmTesting
TESTS=(
    Frequency BlockFrequency CumulativeSums Runs LongestRun Rank FFT
    NonOverlappingTemplate OverlappingTemplate Universal ApproximateEntropy
    RandomExcursions RandomExcursionsVariant Serial LinearComplexity
)
mkdir -p "experiments/$GEN_DIR"
for t in "${TESTS[@]}"; do
    mkdir -p "experiments/$GEN_DIR/$t"
done

# Меню assess (см. sts-2.1.2/README):
#   0 — Input File
#   <path>
#   1 — All tests
#   0 — Default parameters (без смены M/m в подменю)
#   <STREAMS> — число битовых последовательностей
#   1 — Binary input file
# и наконец число BITSTREAMS = $STREAMS, длина = $N_BITS.
# assess часто завершается с кодом 1 даже при успешном прогоне — проверяем отчёт.
set +e
./assess $N_BITS <<EOF
0
$ABS_IN
1
0
$STREAMS
1
EOF
assess_rc=$?
set -euo pipefail

# финальный отчёт
REPORT=experiments/AlgorithmTesting/finalAnalysisReport.txt
[[ -f "$REPORT" ]] || {
    echo "[!] Нет $REPORT (код assess=$assess_rc)" >&2
    exit 1
}
cp "$REPORT" "$ABS_OUT/finalAnalysisReport.txt"
popd >/dev/null

# парсинг
python3 "$(dirname "$0")/parse_results.py" \
    --in  "$ABS_OUT/finalAnalysisReport.txt" \
    --csv "$ABS_OUT/results.csv" \
    --md  "$ABS_OUT/results.md"

echo "[*] Готово. Смотрите $ABS_OUT/results.md и $ABS_OUT/results.csv"
