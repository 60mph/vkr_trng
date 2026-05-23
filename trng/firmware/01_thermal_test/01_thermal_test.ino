/*
 * Тест А0 для схемы теплового шума (см. hardware/01_thermal.md).
 *
 * Каждая готовая выборка АЦП сразу уходит в Serial: моментальное значение
 * (нет усреднения по окну).
 *
 * Serial Monitor: строки «ADC<TAB>Вольт» (3 знака после запятой).
 * SERIAL_PLOTTER = true → одно число 0…1023 на строку (Инструменты → Плоттер).
 *
 * Скорость АЦП ~38 kS/s, UART при 115200 не потянет все строки — частота на ПК
 * будет ниже (ограничение TX). Для быстрее: поднимите SERIAL_BAUD (порт/монитор
 * той же скорости).
 *
 * Перед сборкой: из каталога firmware выполните ./sync_common.sh
 */

#include "adc_fast.h"

constexpr uint8_t  ADC_CHANNEL  = 0;
constexpr uint8_t  ADC_PRESCALE    = 5;   // делитель 32 → ~38 kS/s, 10 бит
constexpr uint32_t SAMPLE_RATE_HZ = 16000000UL / 32UL / 13UL;
constexpr uint32_t SERIAL_BAUD     = 115200UL;

constexpr bool SERIAL_PLOTTER = false;

void setup() {
    Serial.begin(SERIAL_BAUD);
    while (!Serial) { delay(10); }
    adc_fast_init(ADC_CHANNEL, ADC_PRESCALE, ADC_REF_AVCC);

    if (!SERIAL_PLOTTER) {
        Serial.print(F("01_thermal_test  A0  ~"));
        Serial.print(SAMPLE_RATE_HZ);
        Serial.print(F(" ADC/s  "));
        Serial.print(SERIAL_BAUD);
        Serial.println(F(" baud  cols: ADC \\t Volt"));
    }
}

void loop() {
    const uint16_t s = adc_fast_read();
    const float v    = s * (5.0f / 1024.0f);

    if (SERIAL_PLOTTER) {
        Serial.println(s);
        return;
    }

    Serial.print(s);
    Serial.write('\t');
    Serial.println(v, 3);
}
