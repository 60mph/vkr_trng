#!/usr/bin/env bash
# Создаёт в каждой папке sketch'а символические ссылки на общие заголовки
# common/trng_protocol.h и common/adc_fast.h.
#
# Arduino IDE и arduino-cli ищут .h только в самой папке скетча, поэтому
# мы линкуем их туда.

set -e
cd "$(dirname "$0")"

for sketch_dir in 0[1-9]_*/; do
    [[ -d "$sketch_dir" ]] || continue
    for header in trng_protocol.h adc_fast.h; do
        link="$sketch_dir$header"
        target="../common/$header"
        if [[ -L "$link" ]]; then
            rm -f "$link"
        fi
        ln -s "$target" "$link"
        echo "ln -s $target $link"
    done
done

echo "Готово. Теперь каждая папка скетча содержит ссылки на common/*."
