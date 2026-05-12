/*
 * Источник №3 — Лавинный пробой BE-перехода BJT (классическая схема ГИСП)
 * =======================================================================
 *
 * Схема (рекомендуется 2N3904 или 2N2222):
 *   Коллектор не подключаем (NC).
 *   База — на GND через 1 МОм + AC-связь 10 мкФ → вход TL072(A).
 *   Эмиттер — к +9 В через резистор 470 кОм.
 *   При U_BE_reverse ≥ 7 В переход идёт в лавинный пробой, ток ~1–10 мкА
 *   с очень шумной флуктуацией. Сигнал — широкополосный белый шум (см. 2.1
 *   дипломной работы "Дробовой шум" + "Лавинный шум").
 *
 * Подробная схема — ../../hardware/03_bjt_avalanche.md
 */

#include "trng_protocol.h"
#include "adc_fast.h"

constexpr uint8_t  ADC_CHANNEL  = 0;
constexpr uint8_t  ADC_PRESCALE = 4;
constexpr uint32_t SAMPLE_RATE_HZ = 76923UL;

void setup() {
    Serial.begin(TRNG_BAUD);
    while (!Serial) {}
    trng_print_banner("03_bjt_avalanche", 10, SAMPLE_RATE_HZ, "AVCC",
                      "2N3904 BE reverse breakdown @ ~9V, TL072 x2 amplification");
    adc_fast_init(ADC_CHANNEL, ADC_PRESCALE, ADC_REF_AVCC);
}

void loop() {
    uint16_t s = adc_fast_read();
    trng_send_u16(s);
}
