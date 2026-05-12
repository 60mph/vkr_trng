#ifndef ADC_FAST_H
#define ADC_FAST_H

/*
 * Быстрый ADC для ATmega328P (Arduino Nano)
 * =========================================
 *
 * Стандартный analogRead() = ~9600 выборок/с. Для энтропийных задач этого
 * мало. Здесь — несколько режимов:
 *
 *   adc_fast_init(channel, prescaler):
 *      запускает free-running режим. Скорость: 16 МГц / prescaler / 13.
 *      prescaler=16 → 76923 выб/с (но точность ~9 бит из 10);
 *      prescaler=32 → 38461 выб/с (полные 10 бит точности);
 *      prescaler=64 → 19230 выб/с (рекомендованный datasheet'ом для 10 бит).
 *
 *   adc_fast_read():
 *      ждёт следующего ADIF, читает ADCL/ADCH, очищает флаг и возвращает 10-бит.
 *
 * Источник опорного напряжения:
 *   - AVCC (5 В) — для шумных сигналов (KY-037, выход TL072)
 *   - INTERNAL (1.1 В) — для очень слабых сигналов (тепловой шум)
 */

#include <Arduino.h>

enum AdcRef : uint8_t {
    ADC_REF_AREF     = 0,  // внешний AREF
    ADC_REF_AVCC     = 1,  // 5 В (типичное)
    ADC_REF_INTERNAL = 3,  // 1.1 В
};

inline void adc_fast_init(uint8_t channel, uint8_t prescaler_bits, AdcRef ref = ADC_REF_AVCC) {
    // ADMUX: REFS1:0 = ref, ADLAR=0 (правое выравнивание), MUX3:0 = channel
    ADMUX = ((uint8_t)ref << 6) | (channel & 0x07);

    // ADCSRA: ADEN=1, ADSC=1 (start), ADATE=1 (auto trigger), ADIE=0,
    // ADPS2:0 = prescaler_bits (000=2,001=2,010=4,011=8,100=16,101=32,110=64,111=128)
    ADCSRA = (1 << ADEN) | (1 << ADSC) | (1 << ADATE) | (prescaler_bits & 0x07);

    // ADCSRB = 0 → free running
    ADCSRB = 0;

    // Отключаем цифровой буфер на выбранном канале — экономит ток и шумит меньше
    if (channel < 8) DIDR0 |= (1 << channel);
}

// Читает следующую готовую выборку. Блокирующий, но free-running готов 1 выборку
// каждые 13/F_ADC секунд, так что задержка предсказуема.
inline uint16_t adc_fast_read() {
    while (!(ADCSRA & (1 << ADIF))) { /* spin */ }
    uint8_t low  = ADCL;
    uint8_t high = ADCH;
    ADCSRA |= (1 << ADIF);  // очищаем флаг записью 1
    return ((uint16_t)high << 8) | low;
}

// Выбор канала на лету (пока ADC уже инициализирован).
inline void adc_fast_set_channel(uint8_t channel) {
    ADMUX = (ADMUX & 0xF0) | (channel & 0x07);
}

#endif // ADC_FAST_H
