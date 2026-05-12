/*
 * Источник №5 — MEMS-шум MPU-6050 (акселерометр + гироскоп)
 * ==========================================================
 *
 * Схема: GY-521 модуль на I²C, адрес 0x68 (AD0=GND).
 * VCC — 5V, GND — GND, SDA — A4, SCL — A5.
 *
 * Каждый цикл считываем 14 байт начиная с регистра 0x3B:
 *   ACCEL_X(2), ACCEL_Y(2), ACCEL_Z(2), TEMP(2), GYRO_X(2), GYRO_Y(2), GYRO_Z(2)
 *
 * Из шести измерений (без TEMP) выкидываем по одному младшему биту = 6 бит
 * энтропии за цикл. Упаковываем в uint16_t (старшие 10 бит — нули) и шлём.
 *
 * Скорость I²C — 400 кГц (Fast Mode); реальная скорость ~ 700 циклов/сек,
 * т.е. ~4200 бит/сек "сырой" энтропии. Этого достаточно для NIST после
 * нескольких часов накопления (~1.5 МБ за 1 час, NIST STS требует от 1 МБ).
 *
 * Соответствует разделу 2.3 дипломной работы ("MEMS-ГИСП").
 *
 * Подробная схема — ../../hardware/05_mpu6050.md
 */

#include "trng_protocol.h"
#include <Wire.h>

constexpr uint8_t MPU_ADDR     = 0x68;
constexpr uint8_t REG_PWR_MGMT = 0x6B;
constexpr uint8_t REG_ACCEL_X  = 0x3B;
constexpr uint8_t REG_GYRO_CFG = 0x1B;
constexpr uint8_t REG_ACC_CFG  = 0x1C;
constexpr uint8_t REG_CONFIG   = 0x1A;
constexpr uint8_t REG_SMPLRT   = 0x19;

static void mpu_write(uint8_t reg, uint8_t val) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(reg);
    Wire.write(val);
    Wire.endTransmission();
}

void setup() {
    Serial.begin(TRNG_BAUD);
    while (!Serial) {}
    Wire.begin();
    Wire.setClock(400000);

    // Просыпаем чип, отключаем temperature sensor для уменьшения коррелированных
    // помех и фиксируем тактирование от внутреннего гироскопа X (PWR_MGMT_1 = 0x01).
    mpu_write(REG_PWR_MGMT, 0x01);
    delay(50);

    // Максимальная пропускная способность: DLPF=0, SMPLRT_DIV=0 → 8 кГц.
    mpu_write(REG_CONFIG,  0x00);
    mpu_write(REG_SMPLRT,  0x00);
    // Самые широкие диапазоны → максимальный шум по абсолютной величине.
    mpu_write(REG_GYRO_CFG, 0x18);  // ±2000 °/с
    mpu_write(REG_ACC_CFG,  0x18);  // ±16 g

    trng_print_banner("05_mpu6050", 6, 700,  "I2C-MPU6050",
                      "6 LSBs from ACCEL/GYRO XYZ packed into u16; ~4200 raw bits/sec");
}

// Читает 14 байт сырых данных и возвращает 6 младших бит (по одному с каждого
// AX/AY/AZ/GX/GY/GZ) упакованных в младшие 6 бит u16.
static uint16_t mpu_read_lsb_word() {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(REG_ACCEL_X);
    Wire.endTransmission(false);
    Wire.requestFrom((int)MPU_ADDR, 14);

    int16_t ax = (Wire.read() << 8) | Wire.read();
    int16_t ay = (Wire.read() << 8) | Wire.read();
    int16_t az = (Wire.read() << 8) | Wire.read();
    (void)Wire.read(); (void)Wire.read();              // skip TEMP
    int16_t gx = (Wire.read() << 8) | Wire.read();
    int16_t gy = (Wire.read() << 8) | Wire.read();
    int16_t gz = (Wire.read() << 8) | Wire.read();

    uint16_t bits = 0;
    bits |= ((uint16_t)ax & 1) << 0;
    bits |= ((uint16_t)ay & 1) << 1;
    bits |= ((uint16_t)az & 1) << 2;
    bits |= ((uint16_t)gx & 1) << 3;
    bits |= ((uint16_t)gy & 1) << 4;
    bits |= ((uint16_t)gz & 1) << 5;
    return bits;
}

void loop() {
    trng_send_u16(mpu_read_lsb_word());
}
