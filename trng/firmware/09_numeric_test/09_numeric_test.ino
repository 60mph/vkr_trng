/*
 * Универсальный тест A0: максимально быстрый свободный АЦП → числа в UART.
 * Подходит для любой схемы на A0 (тепло, зенер, BJT, микрофон и т.д.).
 *
 * Вывод: «ADC<TAB>Вольт» (3 знака) на строку, 1 000 000 бод.
 * SERIAL_PLOTTER = true → одно число 0…1023 (Arduino Serial Plotter).
 *
 * Prescaler как в боевых источниках u16le (~77 kS/s); UART физически не выдаёт
 * столько ASCII-строк в секунду — на ПК строки реже, чем выборки АЦП.
 *
 * Перед сборкой: из каталога firmware выполните ./sync_common.sh
 */

#include "adc_fast.h"

constexpr uint8_t  ADC_CHANNEL       = 0;
constexpr uint8_t  ADC_PRESCALE    = 4;
constexpr uint32_t SAMPLE_RATE_HZ  = 16000000UL / 16UL / 13UL;
constexpr uint32_t SERIAL_BAUD     = 1000000UL;

constexpr bool SERIAL_PLOTTER = false;

void setup() {
    Serial.begin(SERIAL_BAUD);
    while (!Serial) { delay(10); }
    adc_fast_init(ADC_CHANNEL, ADC_PRESCALE, ADC_REF_AVCC);

    if (!SERIAL_PLOTTER) {
        Serial.print(F("09_numeric_test  A0  ~"));
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
