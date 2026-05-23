# Arduino Nano — быстрая памятка: прошивки и утилиты

Одна строка сборки перед любыми скетчами (создаёт ссылки на `common/*.h`):

```bash
cd /path/to/trng/firmware && ./sync_common.sh
```

Общие переменные в shell (подставь свой путь к каталогу `trng/` и порт):

```bash
export TRNG="/path/to/trng"          # абсолютный путь к каталогу trng/
export PORT="/dev/ttyUSB0"
export CLI="$TRNG/tools/arduino-cli"
export FQBN="arduino:avr:nano"
# Если Nano со «старым» загрузчиком:
# export FQBN="arduino:avr:nano:cpu=atmega328old"
```

Шаблон компиляции и загрузки (путь `SKETCH_DIR` — папка вида `$TRNG/firmware/NN_name/` с `.ino` внутри):

```bash
"$CLI" compile --fqbn "$FQBN" "$SKETCH_DIR" &&
"$CLI" upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"
```

Перед прошивкой закрой всё, что держит `PORT` (Serial Monitor, `picocom`, осциллограф, `pipeline.py`).

---

## Тесты на A0 (числа в Serial)

| Скетч | Назначение | UART | Просмотр |
|--------|------------|------|----------|
| **`09_numeric_test`** | Максимально быстрый free-running ADC и вывод **каждой** выборки в виде `ADC<TAB>Вольт` (или одно число в режиме плоттера). Универсально для любой схемы на A0. | **1 Mbd** | `picocom -b 1000000 "$PORT"` |
| **`10_numeric_avg_test`** | Тот же АЦП, но **редкий** отчёт раз в 100 ms: число выборок `n`, min…max ADC и в вольтах, среднее ADC и вольт. | **1 Mbd** | `picocom -b 1000000 "$PORT"` |

Команды:

```bash
export SKETCH_DIR="$TRNG/firmware/09_numeric_test"
"$CLI" compile --fqbn "$FQBN" "$SKETCH_DIR" && "$CLI" upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"
```

```bash
export SKETCH_DIR="$TRNG/firmware/10_numeric_avg_test"
"$CLI" compile --fqbn "$FQBN" "$SKETCH_DIR" && "$CLI" upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"
```

Дополнительно в репозитории остаются **`01_thermal_test`** (медленнее АЦП, 115200 в прошивке) и **`02_zener_test`** (аналогично **`09_numeric_test`**, но с подписью зенера) — для совместимости со старыми заметками.

---

## Осциллограф на ПК (`capture/serial_scope.py`)

Нужен поток **после `BEGIN`**: **uint16 little-endian**, **1 Mbd** — то есть **боевая** прошивка того источника, который реально собран на макетке.

1. Прошить соответствующий скетч из таблицы «Боевые прошивки» ниже.
2. Запустить (из каталога `trng/`):

```bash
cd "$TRNG"
python3 capture/serial_scope.py --port "$PORT" --baud 1000000 --format binary
```

Если маркер `BEGIN` не находится сразу после открытия порта:

```bash
python3 capture/serial_scope.py --port "$PORT" --baud 1000000 --format binary --reset-board
```

Режим `--format text` — только если на плате текстовые строки (**`09_numeric_test`** / **`10_numeric_avg_test`**); для боевых источников используй **`binary`**.

---

## Боевые прошивки (захват `pipeline.py` / `capture_serial.py`)

После загрузки: баннер с `# TRNG_SOURCE=…`, затем **`BEGIN\n`**, далее непрерывный **uint16 LE**, **1 Mbd**.

| Источник | Папка скетча | `TRNG_SOURCE` в баннере |
|----------|----------------|--------------------------|
| 1 Тепловой шум | `firmware/01_thermal/` | `01_thermal` |
| 2 Зенер | `firmware/02_zener/` | `02_zener` |
| 3 BJT лавина | `firmware/03_bjt_avalanche/` | `03_bjt_avalanche` |
| 4 Микрофон | `firmware/04_microphone/` | `04_microphone` |
| 5 MPU-6050 | `firmware/05_mpu6050/` | `05_mpu6050` |
| 6 Floating ADC | `firmware/06_floating_adc/` | `06_floating_adc` |
| 7 Clock jitter | `firmware/07_clock_jitter/` | `07_clock_jitter` |
| 8 Гибрид | `firmware/08_hybrid/` | `08_hybrid` |

Пример (тепло):

```bash
export SKETCH_DIR="$TRNG/firmware/01_thermal"
"$CLI" compile --fqbn "$FQBN" "$SKETCH_DIR" && "$CLI" upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"
```

Пример (BJT под осциллограф / пайплайн):

```bash
export SKETCH_DIR="$TRNG/firmware/03_bjt_avalanche"
"$CLI" compile --fqbn "$FQBN" "$SKETCH_DIR" && "$CLI" upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"
```

---

## Пайплайн одной строкой (`--source` совпадает с именем источника в данных)

Подставь реальный источник, например `02_zener` или `03_bjt_avalanche`:

```bash
cd "$TRNG"
python3 scripts/pipeline.py --source 03_bjt_avalanche \
  --port "$PORT" --baud 1000000 --bits 1 --nist-dual --auto-bytes-for-nist
```

Без захвата (если есть `data/raw/<source>/run_001.bin`): опусти `--port`.

Обычный прогон `pipeline.py` сам строит осциллограммы начала записи и встраивает их в `data/reports/<source>/report.md` (PNG: 1 с, ½ с, ¼ с, ⅛ с).

Перегенерировать **только** эти PNG из уже сохранённого raw (без полного пайплайна):

```bash
cd "$TRNG"
python3 analysis/raw_waveform_snapshots.py \
  --in data/raw/SOURCE/run_001.bin \
  --out-dir data/reports/SOURCE/
```

Пример для BJT (`SOURCE=03_bjt_avalanche`):

```bash
cd "$TRNG"
python3 analysis/raw_waveform_snapshots.py \
  --in data/raw/03_bjt_avalanche/run_001.bin \
  --out-dir data/reports/03_bjt_avalanche/
```

---

## Постобработка после Von Neumann + NIST (`scripts/postprocessing_nist_scan.py`)

Вход после VN: `data/processed/<SOURCE>/run_001_lsb<bits>_vn.bin`. Реализация второго слоя: `analysis/postprocess_stream_variants.py`. Выход: `postproc_<variant>_vn2.bin`, отчёты STS в `data/reports/<SOURCE>/postprocessing_nist_after_vn/<variant>/`, сводка `postprocessing_nist_comparison_after_vn.md`.

**Отдельно `decim_xor8win`** (выход может стать намного короче входа; при ошибке по длине для STS нужен более длинный vn-файл):

```bash
cd "$TRNG"
python3 scripts/postprocessing_nist_scan.py \
  --source SOURCE \
  --after-von-neumann \
  --bits 1 \
  --variants decim_xor8win
```

**Отдельно `fold_lsb_byte`**:

```bash
cd "$TRNG"
python3 scripts/postprocessing_nist_scan.py \
  --source SOURCE \
  --after-von-neumann \
  --bits 1 \
  --variants fold_lsb_byte
```

**Все варианты за один запуск** (порядок по умолчанию): `xor_delay8`, `xor_lsb012`, `decim_xor8win`, `fold_lsb_byte`, `sha256_2048` — опусти `--variants`:

```bash
python3 scripts/postprocessing_nist_scan.py --source SOURCE --after-von-neumann --bits 1
```

Постобработка **поверх сырая** (`uint16`): без `--after-von-neumann`, вход по умолчанию `data/raw/<SOURCE>/run_001.bin`, выходы `postproc_<variant>.bin`, каталог `postprocessing_nist/`, сводка `postprocessing_nist_comparison.md`.

### Флаги `postprocessing_nist_scan.py`

| Флаг | Смысл |
|------|--------|
| `--source SOURCE` *(обяз.)* | Имя каталога под `data/raw`, `data/processed`, `data/reports` — одинаковое для набора эксперимента. |
| `--after-von-neumann` | Второй слой поверх vn: `processed/<SOURCE>/run_001_lsb<bits>_vn.bin` (или файл из `--vn-in`). |
| `--bits N` | Суффикс в имени vn: `run_001_lsbN_vn.bin` (по умолчанию `1`). |
| `--vn-in PATH` | Явный путь к vn-файлу вместо вычисления из `--source` и `--bits`. |
| `--raw PATH` | Только **без** `--after-von-neumann`: другой сырое `run_001.bin`. |
| `--variants a,b,...` | Список методов через запятую (по умолчанию — все перечисленные выше). |
| `--streams K` | Число битовых потоков для STS (по умолчанию `10`). |
| `--nist-n-bits M` | Бит на поток (по умолчанию `1000000`). |
| `--sts DIR` | Каталог сборки NIST STS 2.1.2; по умолчанию `nist_sts/sts-2.1.2`. |
| `--skip-nist` | Только сгенерировать `postproc_*.bin`, без запуска STS. |
| `--inject-link-report PATH` | Дописать в указанный `report.md` ссылку на сводку сравнения (если блока ещё нет). |

---

## Диагностика «порт занят»

```bash
lsof "$PORT"
```

Завершить процесс или закрыть терминал с `picocom` (выход: `Ctrl+A`, затем `Ctrl+X`).
