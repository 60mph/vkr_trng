/*
 * Тест A0 с редким текстовым выводом: за окно PRINT_INTERVAL_MS собирает все
 * доступные выборки free-running ADC, печатает их число n, min…max, среднее
 * (коды ADC и вольты). Удобно настраивать пробой, связь, смещение.
 *
 * Serial: 1 000 000 бод. Prescaler совпадает с боевым потоком ~77 kS/s.
 *
 * Перед сборкой: из каталога firmware выполните ./sync_common.sh
 */

#include "adc_fast.h"

constexpr uint8_t  ADC_CHANNEL         = 0;
constexpr uint8_t  ADC_PRESCALE      = 4;
constexpr uint32_t SAMPLE_RATE_HZ    = 16000000UL / 16UL / 13UL;
constexpr uint32_t SERIAL_BAUD       = 1000000UL;
constexpr uint32_t PRINT_INTERVAL_MS = 100;

void setup() {
    Serial.begin(SERIAL_BAUD);
    while (!Serial) { delay(10); }
    adc_fast_init(ADC_CHANNEL, ADC_PRESCALE, ADC_REF_AVCC);

    Serial.print(F("10_numeric_avg_test  A0  ~"));
    Serial.print(SAMPLE_RATE_HZ);
    Serial.print(F(" ADC/s  every "));
    Serial.print(PRINT_INTERVAL_MS);
    Serial.print(F(" ms  "));
    Serial.print(SERIAL_BAUD);
    Serial.println(F(" baud"));
}

void loop() {
    const uint32_t t0 = millis();
    uint64_t sum      = 0;
    uint32_t n        = 0;
    uint16_t vmin     = 1023;
    uint16_t vmax     = 0;

    while ((uint32_t)(millis() - t0) < PRINT_INTERVAL_MS) {
        const uint16_t s = adc_fast_read();
        sum += s;
        if (s < vmin) {
            vmin = s;
        }
        if (s > vmax) {
            vmax = s;
        }
        ++n;
    }

    const float lsb = 5.0f / 1024.0f;

    Serial.print(F("n="));
    Serial.print(n);
    Serial.print(F("  "));
    Serial.print(vmin);
    Serial.print(F("…"));
    Serial.print(vmax);
    Serial.print(F("  ("));
    Serial.print(vmin * lsb, 3);
    Serial.print(F("…"));
    Serial.print(vmax * lsb, 3);
    Serial.print(F(" V)  avg "));
    Serial.print((float)sum / (float)n, 1);
    Serial.print(F("  "));
    Serial.print(((float)sum / (float)n) * lsb, 3);
    Serial.println(F(" V"));
}
