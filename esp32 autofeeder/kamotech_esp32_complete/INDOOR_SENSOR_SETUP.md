# Indoor light and MQ-135 setup

The complete GoHMoTech controller now reads both new sensors and posts them to the existing Django sensor API every 30 seconds.

## Wiring

| Sensor | Sensor pin | ESP32 pin |
|---|---|---|
| Analog light/LDR module | AO | GPIO 34 |
| MQ-135 module | AO | GPIO 35 through a voltage divider when AO can exceed 3.3 V |
| Both modules | GND | ESP32 GND |

GPIO 34 and 35 are ADC1 input-only pins, so they remain usable while Wi-Fi is active.

**Electrical warning:** many MQ-135 boards are powered from 5 V and their analog output may approach 5 V. The ESP32 ADC input must never receive more than 3.3 V. Use a suitable voltage divider and verify the maximum with a multimeter before connecting AO to GPIO 35. Keep all grounds common.

## Light calibration

1. Open the Serial Monitor and record `lightRaw` in the darkest expected goat-house condition.
2. Record it again in the brightest expected condition.
3. Replace `LIGHT_DARK_ADC` and `LIGHT_BRIGHT_ADC` in `kamotech_esp32_complete.ino`.
4. If your module's values move in the opposite direction, swap the two calibration values.

## MQ-135 calibration

The firmware safely uploads raw ADC and input voltage immediately. It deliberately leaves PPM disabled until the sensor is calibrated.

1. Follow the sensor/module datasheet for initial burn-in and warm-up.
2. Determine the module's R0 calibration value in clean reference air.
3. Replace `MQ135_R0_KOHMS` (currently `0.0`) with the measured value.
4. Re-upload the sketch. The API will then mark the calculated value as a calibrated estimate.

MQ-135 responds to multiple gases. Its calculated PPM is an estimate and must not be presented as a certified CO2, ammonia, or safety measurement.

## Django

Run:

```powershell
venv\Scripts\python.exe manage.py migrate
```

The values then appear in Monitoring, the owner dashboard, Django admin sensor readings, and Analytics > Environmental Report.
