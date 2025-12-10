# SentinelHub 회로도 상세 설계

**Rev 1.1** - MCU: STM32F405RG (무선 기능 없음, EMC 인증 간소화)

## 1. 전원부 설계

### 1.1 PoE 입력부 (AG9905M)

```
PoE 48V Input (IEEE 802.3af)
          │
          ▼
    ┌─────────────────────────────────────┐
    │           AG9905M                    │
    │                                      │
    │  VIN+ ────────────────── PoE+ (48V) │
    │  VIN- ────────────────── PoE- (GND) │
    │                                      │
    │  VOUT+ ─────────────────── +5V      │
    │  VOUT- ─────────────────── GND      │
    │                                      │
    │  Specs:                              │
    │  - Input: 36-57V DC                  │
    │  - Output: 5V / 2A (10W max)         │
    │  - Efficiency: >85%                  │
    └─────────────────────────────────────┘
```

**부품**:
| Ref | Part | Value | Description |
|-----|------|-------|-------------|
| U1 | AG9905M | - | PoE PD Module |
| C1 | Capacitor | 100uF/10V | 입력 필터 (전해) |
| C3 | Capacitor | 100nF | 입력 필터 (세라믹) |

### 1.2 3.3V LDO (AMS1117-3.3)

```
      5V Input
          │
          ├───┬───────────────────────────┐
          │   │                           │
         ┌┴┐ ═══ C4                       │
     R7  │ │ 10uF                         │
    10k  └┬┘                              │
          │                               │
          ▼                               │
    ┌─────────────────────┐               │
    │    AMS1117-3.3      │               │
    │                     │               │
    │  VIN ◄──────────────┴               │
    │                     │               │
    │  GND ◄──────────────┼───── GND      │
    │                     │               │
    │  VOUT ►─────────────┼───── 3.3V     │
    │                     │     │         │
    └─────────────────────┘     │         │
                               ═══ C5     │
                               22uF       │
                                │         │
                               ═══ GND    │
```

### 1.3 전원 분배

```
전력 버짓:
┌──────────────────┬─────────┬─────────┬─────────┐
│ Component        │ Voltage │ Current │ Power   │
├──────────────────┼─────────┼─────────┼─────────┤
│ MLX90640 x 4     │ 3.3V    │ 80mA    │ 264mW   │
│ STM32F405RG      │ 3.3V    │ 100mA   │ 330mW   │
│ W5500            │ 3.3V    │ 150mA   │ 495mW   │
│ TCA9548A         │ 3.3V    │ 10mA    │ 33mW    │
│ LEDs + Others    │ 3.3V    │ 50mA    │ 165mW   │
├──────────────────┼─────────┼─────────┼─────────┤
│ Total            │ -       │ ~390mA  │ ~1.3W   │
└──────────────────┴─────────┴─────────┴─────────┘

PoE 802.3af 지원: 12.95W → 충분한 마진
```

---

## 2. STM32F405RG MCU 회로

### 2.1 MCU 사양

| 항목 | 값 |
|------|-----|
| Core | ARM Cortex-M4F |
| Clock | 168MHz |
| Flash | 1MB |
| RAM | 192KB |
| Package | LQFP-64 |
| 무선 | **없음** (EMC 인증 간소화) |

### 2.2 핀 배치

```
                      STM32F405RGT6 (LQFP-64)
                    ┌───────────────────────┐
            VBAT ──┤1                    64├── VDD
            PC13 ──┤2                    63├── VSS
            PC14 ──┤3                    62├── VDD
            PC15 ──┤4                    61├── PD2
       HSE_IN/PH0──┤5                    60├── PC12
      HSE_OUT/PH1──┤6                    59├── PC11
           NRST ──┤7                    58├── PC10
            PC0 ──┤8  (LED_STATUS)      57├── PA15
            PC1 ──┤9  (LED_ALARM)       56├── PA14 (SWCLK)
            PC2 ──┤10                   55├── PA13 (SWDIO)
            PC3 ──┤11                   54├── PA12
           VSSA ──┤12                   53├── PA11
           VDDA ──┤13                   52├── PA10
            PA0 ──┤14                   51├── PA9
            PA1 ──┤15                   50├── PA8
            PA2 ──┤16                   49├── PC9
            PA3 ──┤17                   48├── PC8
            VSS ──┤18                   47├── PC7
            VDD ──┤19                   46├── PC6
            PA4 ──┤20 (W5500_CS)        45├── PB15
            PA5 ──┤21 (SPI1_SCK)        44├── PB14
            PA6 ──┤22 (SPI1_MISO)       43├── PB13
            PA7 ──┤23 (SPI1_MOSI)       42├── PB12
            PC4 ──┤24 (W5500_INT)       41├── VDD
            PC5 ──┤25 (W5500_RST)       40├── VSS
            PB0 ──┤26                   39├── PB11
            PB1 ──┤27                   38├── PB10
            PB2 ──┤28 (BOOT1)           37├── VCAP1
           PB10 ──┤29                   36├── VCAP2
           PB11 ──┤30                   35├── PB9
           VCAP1──┤31                   34├── PB8
            VSS ──┤32                   33├── BOOT0
                    └───────────────────────┘

주요 핀 기능:
├── I2C1: PB6 (SCL), PB7 (SDA) → TCA9548A
├── SPI1: PA5 (SCK), PA6 (MISO), PA7 (MOSI) → W5500
├── GPIO: PA4 (CS), PC4 (INT), PC5 (RST) → W5500 제어
├── GPIO: PC0 (LED_STATUS), PC1 (LED_ALARM)
├── SWD: PA13 (SWDIO), PA14 (SWCLK) → 디버그
└── HSE: PH0 (IN), PH1 (OUT) → 8MHz 크리스탈
```

### 2.3 리셋 회로

```
         3.3V
          │
         ┌┴┐
     R8  │ │ 10k
         └┬┘
          │
          ├──────────┬─────────────► NRST (Pin 7)
          │          │
         ┌┴┐        ═══ C16
    SW1  │ │        100nF
  RESET  └┬┘         │
          │          │
         ═══        ═══
         GND        GND

- R8: 10k 풀업
- C16: 100nF 노이즈 필터
- SW1: 택트 스위치
```

### 2.4 HSE 크리스탈 회로 (8MHz)

```
                         STM32F405
                    ┌─────────────────┐
                    │                 │
        ┌───────────┤ PH0 (HSE_IN)    │
        │           │                 │
       ┌┴┐          │                 │
  C14  │ │ 20pF     │                 │
       └┬┘          │                 │
        │   ┌───┐   │                 │
        ├───┤ Y2├───┤ PH1 (HSE_OUT)   │
        │   └───┘   │                 │
       ┌┴┐  8MHz    │                 │
  C15  │ │ 20pF     │                 │
       └┬┘          │                 │
        │           │                 │
       ═══         └─────────────────┘
       GND

부품:
- Y2: 8MHz Crystal (HC49 또는 3215 SMD)
- C14, C15: 20pF (0603)
- 로드 커패시터 계산: CL = (C14 × C15)/(C14 + C15) + Cstray
```

### 2.5 BOOT0 회로

```
         GND
          │
         ┌┴┐
    R12  │ │ 10k
         └┬┘
          │
          └──────────────────► BOOT0 (Pin 33)

BOOT 모드:
- BOOT0 = 0 (GND): Flash 부팅 (정상 동작)
- BOOT0 = 1 (3V3): System Memory 부팅 (DFU 모드)

Note: BOOT1 (PB2)는 내부 풀다운, 별도 회로 불필요
```

### 2.6 SWD 디버그 인터페이스

```
              J9 (SWD Debug Header)
            ┌─────────────────────┐
          1 │ SWDIO ──────────────┼── PA13
          2 │ SWCLK ──────────────┼── PA14
          3 │ GND ────────────────┼── GND
          4 │ 3V3 ────────────────┼── VCC_3V3
            └─────────────────────┘

커넥터: 2.54mm 4핀 헤더 또는 Tag-Connect TC2030

지원 디버거:
- ST-Link V2/V3
- J-Link
- CMSIS-DAP
```

### 2.7 전원 바이패스 커패시터

```
STM32F405 전원 핀 바이패스:

VDD 핀 (Pin 19, 41, 64):
각 핀마다 100nF 세라믹 커패시터

  VDD ──┬── C6 (100nF) ──┬── GND
        ├── C7 (100nF) ──┤
        ├── C8 (100nF) ──┤
        └── C9 (4.7uF) ──┘

VDDA (Pin 13):
  VDDA ──┬── 10nF ──┬── GND
         └── 1uF ───┘

VCAP 핀 (내부 1.2V 레귤레이터):
  VCAP1 (Pin 31) ── C17 (2.2uF) ── GND
  VCAP2 (Pin 36) ── C18 (2.2uF) ── GND

Note: VCAP 커패시터는 반드시 2.2uF 세라믹 사용
```

---

## 3. I2C 멀티플렉서 (TCA9548A)

### 3.1 핀 연결

```
                         TCA9548A
                    ┌─────────────────┐
              A0 ──┤1              24├── VCC (3.3V)
              A1 ──┤2              23├── SDA (Main)
              A2 ──┤3              22├── SCL (Main)
            /RST ──┤4              21├── SD0 → CAM1_SDA
             GND ──┤5              20├── SC0 → CAM1_SCL
             SD1 ──┤6              19├── SD7
             SC1 ──┤7              18├── SC7
             SD2 ──┤8              17├── SD6
             SC2 ──┤9              16├── SC6
             SD3 ──┤10             15├── SD5
             SC3 ──┤11             14├── SC5
             GND ──┤12             13├── SD4/SC4
                    └─────────────────┘

I2C Address: 0x70 (A0=A1=A2=GND)
```

### 3.2 I2C 버스 연결

```
Main I2C Bus (STM32 → TCA9548A):

STM32F405                       TCA9548A
PB7 (I2C1_SDA) ──────┬────────── SDA (Pin 23)
                     │
                    ┌┴┐ R1
                    │ │ 4.7k
                    └┬┘
                     │
                    3.3V

PB6 (I2C1_SCL) ──────┬────────── SCL (Pin 22)
                     │
                    ┌┴┐ R2
                    │ │ 4.7k
                    └┬┘
                     │
                    3.3V

I2C 속도: 400kHz (Fast Mode)
```

---

## 4. MLX90640 카메라 커넥터

### 4.1 커넥터 핀아웃

```
각 카메라 커넥터 (J3, J4, J5, J6):

    ┌─────┐
  1 │ VCC │ ─── 3.3V
  2 │ GND │ ─── GND
  3 │ SDA │ ─── TCA9548A SDx
  4 │ SCL │ ─── TCA9548A SCx
    └─────┘

커넥터 타입: JST-SH 4핀 (1.0mm pitch)
```

### 4.2 채널 할당

| 커넥터 | TCA9548A 채널 | 위치 |
|--------|---------------|------|
| J3 (CAM1) | Ch0 | 좌상단 모서리 |
| J4 (CAM2) | Ch1 | 우상단 모서리 |
| J5 (CAM3) | Ch2 | 좌하단 모서리 |
| J6 (CAM4) | Ch3 | 우하단 모서리 |

---

## 5. W5500 Ethernet 회로

### 5.1 핀 연결 (SPI1)

```
STM32F405                        W5500
PA5 (SPI1_SCK)  ──────────────── SCLK
PA6 (SPI1_MISO) ──────────────── MISO
PA7 (SPI1_MOSI) ──────────────── MOSI
PA4 (GPIO)      ──────────────── SCSn
PC4 (GPIO)      ──────────────── INTn
PC5 (GPIO)      ──────────────── RSTn
```

### 5.2 크리스탈 회로 (25MHz)

```
              W5500
         ┌────────────┐
         │            │
XTLP ◄───┤            │
         │    25MHz   │
         │    ┌───┐   │
XTLN ◄───┤────┤ Y1├───┤
         │    └─┬─┘   │
         └──────┼─────┘
                │
            ┌───┴───┐
            │       │
           ═══     ═══
        C10 18pF C11 18pF
            │       │
            └───┬───┘
                │
               ═══ GND
```

### 5.3 전원 바이패스

```
W5500 전원 핀별 바이패스:

AVDD (1.8V Internal LDO 출력):
  AVDD ──┬── 10uF (C12) ──┬── GND
         └── 100nF (C13) ─┘

VCC (3.3V):
  VCC ──┬── 10uF (C4) ──┬── GND
        └── 100nF (C5) ─┘
```

---

## 6. Status LED 회로

```
3.3V ───────────────────┐
                        │
GPIO (Active Low)       │
       │                │
       └─── R ───── LED ┘

LED 사양:
┌────────┬────────┬────────┬─────────┬─────────────┐
│ LED    │ Color  │ GPIO   │ R Value │ Purpose     │
├────────┼────────┼────────┼─────────┼─────────────┤
│ D1     │ Green  │ -      │ 1k      │ Power ON    │
│ D2     │ Blue   │ PC0    │ 1k      │ Status      │
│ D3     │ Red    │ PC1    │ 1k      │ Alarm       │
│ D4     │ Yellow │ W5500  │ 1k      │ ETH Link    │
└────────┴────────┴────────┴─────────┴─────────────┘

D1 (Power LED)는 3.3V 레일에 직접 연결 (상시 ON)
```

---

## 7. BOM (Bill of Materials)

### 7.1 주요 IC

| Ref | Part Number | Description | Qty | Package |
|-----|-------------|-------------|-----|---------|
| U1 | AG9905M | PoE PD Module 48V→5V | 1 | Module |
| U2 | AMS1117-3.3 | 3.3V LDO | 1 | SOT-223 |
| U3 | **STM32F405RGT6** | ARM Cortex-M4F MCU | 1 | **LQFP-64** |
| U4 | TCA9548A | I2C Multiplexer | 1 | TSSOP-24 |
| U5 | W5500 | Ethernet Controller | 1 | LQFP-48 |

### 7.2 커넥터

| Ref | Part Number | Description | Qty |
|-----|-------------|-------------|-----|
| J1 | RJ45-PoE | RJ45 with PoE | 1 |
| J3-J6 | JST-SH-4 | Camera Connector | 4 |
| J7 | RJ45-MagJack | Ethernet Jack | 1 |
| **J9** | **Header 1x4** | **SWD Debug** | **1** |

### 7.3 크리스탈

| Ref | Value | Description | Qty |
|-----|-------|-------------|-----|
| Y1 | 25MHz | W5500 Crystal | 1 |
| **Y2** | **8MHz** | **STM32 HSE Crystal** | **1** |

### 7.4 수동 부품

| Ref | Value | Description | Qty | Package |
|-----|-------|-------------|-----|---------|
| R1, R2 | 4.7k | I2C Pull-up | 2 | 0603 |
| R3-R6 | 1k | LED 저항 | 4 | 0603 |
| R8 | 10k | NRST Pull-up | 1 | 0603 |
| **R12** | **10k** | **BOOT0 Pull-down** | **1** | **0603** |
| C1 | 100uF/10V | PoE 필터 | 1 | Electrolytic |
| C2, C4, C5 | 22uF | 전원 필터 | 3 | 0805 |
| C6-C8, C13 | 100nF | 바이패스 | 4 | 0603 |
| C9 | 4.7uF | MCU 전원 | 1 | 0805 |
| C10, C11 | 18pF | W5500 Crystal | 2 | 0603 |
| **C14, C15** | **20pF** | **HSE Crystal** | **2** | **0603** |
| C16 | 100nF | NRST 필터 | 1 | 0603 |
| **C17, C18** | **2.2uF** | **VCAP** | **2** | **0603** |

### 7.5 기타

| Ref | Description | Qty |
|-----|-------------|-----|
| SW1 | Reset Tactile Switch | 1 |
| D1-D4 | LED (0805) | 4 |

---

## 8. ESP32 대비 변경 사항

| 항목 | ESP32-S3 (이전) | STM32F405RG (현재) |
|------|----------------|-------------------|
| 무선 | WiFi + BLE | **없음** |
| EMC 인증 | 필요 (RF) | **간소화** |
| 프로그래밍 | USB-C | **SWD** |
| 외부 크리스탈 | 불필요 | **8MHz 필요** |
| 패키지 | Module | **LQFP-64** |
| 전류 소모 | ~200mA | **~100mA** |

### 제거된 부품
- USB-C 커넥터 (J2)
- USB CC 저항 (5.1k x 2)
- BOOT 스위치 (SW2)

### 추가된 부품
- 8MHz 크리스탈 (Y2)
- HSE 로드 커패시터 (C14, C15)
- VCAP 커패시터 (C17, C18)
- BOOT0 풀다운 저항 (R12)
- SWD 헤더 (J9)

---

## 9. 설계 체크리스트

- [x] PoE 입력부 설계
- [x] 5V→3.3V LDO 설계
- [x] **STM32F405RG 핀 배치**
- [x] Reset 회로
- [x] **8MHz HSE 크리스탈 회로**
- [x] **BOOT0 회로**
- [x] **SWD 디버그 헤더**
- [x] **VCAP 커패시터**
- [x] TCA9548A I2C 멀티플렉서
- [x] I2C Pull-up 저항
- [x] MLX90640 커넥터 (x4)
- [x] W5500 SPI 연결
- [x] W5500 크리스탈 회로
- [x] RJ45 Magnetics
- [x] Status LED
- [x] 바이패스 커패시터
- [x] BOM 작성

---

## 10. 예상 비용

| 부품 | 단가 | 수량 | 금액 |
|------|------|------|------|
| MLX90640 광각 | $40 | 4 | $160 |
| **STM32F405RGT6** | **$6** | 1 | **$6** |
| W5500 | $3 | 1 | $3 |
| TCA9548A | $3 | 1 | $3 |
| PoE 모듈 | $10 | 1 | $10 |
| PCB + 부품 | $20 | 1 | $20 |
| **합계** | | | **~$202/모듈** |

(ESP32-S3 대비 $4 절감, EMC 인증 비용 대폭 절감)
