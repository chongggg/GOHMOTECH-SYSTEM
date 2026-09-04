#include <HX711_ADC.h>

#define DOUT 19
#define CLK 18

HX711_ADC loadcell(DOUT, CLK);

unsigned long timer = 0;

void setup() {
  Serial.begin(115200);

  loadcell.begin();

  // IMPORTANT:
  // Nobody and nothing extra should be on the platform during startup.
  loadcell.start(3000, true);

  if (loadcell.getTareTimeoutFlag() ||
      loadcell.getSignalTimeoutFlag()) {
    Serial.println("HX711 ERROR");
    while (1);
  }

  loadcell.setCalFactor(760.0);

  Serial.println("Scale ready");
}

void loop() {
  loadcell.update();

  if (millis() - timer >= 500) {
    timer = millis();

    float weight = loadcell.getData();

    if (weight > -0.1 && weight < 0.1) {
      weight = 0;
    }

    Serial.print("Weight: ");
    Serial.print(weight, 2);
    Serial.println(" kg");
  }
}