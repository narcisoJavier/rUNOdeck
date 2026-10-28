#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Keypad.h>
#include <string.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

const byte ROWS = 4;
const byte COLS = 4;

// Hardware-compensated keymap for upside-down PCB mounting and D2-D9 pin order
// so physical buttons top-to-bottom, left-to-right read as:
// [1, 2, 3, A] / [4, 5, 6, B] / [7, 8, 9, C] / [*, 0, #, D]
char keys[ROWS][COLS] = {
  {'A', '3', '2', '1'},
  {'B', '6', '5', '4'},
  {'D', '#', '0', '*'},
  {'C', '9', '8', '7'}
};

byte rowPins[ROWS] = {2, 3, 4, 5};
byte colPins[COLS] = {6, 7, 8, 9};

Keypad keypad = Keypad(
  makeKeymap(keys),
  rowPins,
  colPins,
  ROWS,
  COLS
);

const int JOY_X  = A0;
const int JOY_Y  = A1;
const int JOY_SW = A2;
const int SW_PINS[6] = {A2, A3, 10, 11, 12, 13};
bool swBaselinePullup[6] = {HIGH, HIGH, HIGH, HIGH, HIGH, HIGH};
int swBaselineFloat[2] = {0, 0};

int centerX = 512;
int centerY = 512;
float smoothX = 512.0f;
float smoothY = 512.0f;

const int DEADZONE_TELEM = 40;
const int DEADZONE_MOUSE = 48;
const int THRESH_DELTA   = 210;

enum AppMode { MODE_MEDIA, MODE_MOUSE, MODE_SCROLL };
AppMode currentMode = MODE_MEDIA;

bool selectingMode = false;
unsigned long selectModeTimer = 0;

bool ledEnabled = true;
bool isIdle = false;
bool showingToast = false;
unsigned long lastActivityTime = 0;
unsigned long toastEndTime = 0;
unsigned long lastAnimFrameTime = 0;
uint8_t animStep = 0;

bool lastBtnState = HIGH;
unsigned long lastBtnDebounce = 0;
unsigned long lastUpdateTimer = 0;
unsigned long lastTelemTimer = 0;
unsigned long lastVolTime = 0;
unsigned long lastTabTime = 0;
int lastSentNormX = 0;
int lastSentNormY = 0;

// Custom CGRAM characters (0..5: wave bars, 6..7: rUNOdeck infinity glyph)
byte bar0[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F};
byte bar1[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F};
byte bar2[8] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F};
byte bar3[8] = {0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F};
byte bar4[8] = {0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F};
byte bar5[8] = {0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F};
byte infLeft[8]  = {0x00, 0x0E, 0x11, 0x17, 0x11, 0x0E, 0x00, 0x00};
byte infRight[8] = {0x00, 0x0E, 0x15, 0x1F, 0x15, 0x0E, 0x00, 0x00};

const uint8_t WAVE_LUT[16] = {0, 1, 2, 4, 5, 4, 2, 1, 0, 1, 3, 5, 3, 1, 0, 0};

void printPadded16(uint8_t row, const char* text) {
  if (!ledEnabled) return;
  lcd.setCursor(0, row);
  uint8_t i = 0;
  while (text[i] != '\0' && i < 16) {
    lcd.write(text[i]);
    i++;
  }
  while (i < 16) {
    lcd.write(' ');
    i++;
  }
}

void drawBrandRow(const char* rightLabel) {
  if (!ledEnabled) return;
  lcd.setCursor(0, 0);
  lcd.write(byte(6));
  lcd.write(byte(7));
  lcd.print(" rUNO ");
  uint8_t used = 8;
  uint8_t i = 0;
  while (rightLabel[i] != '\0' && used < 16) {
    lcd.write(rightLabel[i]);
    i++;
    used++;
  }
  while (used < 16) {
    lcd.write(' ');
    used++;
  }
}

void refreshModeScreen() {
  if (!ledEnabled) return;
  showingToast = false;
  isIdle = false;
  switch (currentMode) {
    case MODE_MEDIA:
      drawBrandRow("  [MEDIA]");
      printPadded16(1, "Stick:Shortcuts ");
      break;
    case MODE_MOUSE:
      drawBrandRow("  [MOUSE]");
      printPadded16(1, "Stick:MoveCursr ");
      break;
    case MODE_SCROLL:
      drawBrandRow(" [SCROLL]");
      printPadded16(1, "Stick:SmoothScr ");
      break;
  }
}

void showToast(const char* title, const char* subtitle, unsigned long durationMs = 1300) {
  lastActivityTime = millis();
  isIdle = false;
  showingToast = true;
  toastEndTime = millis() + durationMs;
  if (!ledEnabled) return;
  drawBrandRow(title);
  printPadded16(1, subtitle);
}

void setLedState(bool enabled) {
  ledEnabled = enabled;
  if (ledEnabled) {
    lcd.display();
    lcd.backlight();
    Serial.println("LED: ON");
    showToast("   [LEDS]", "Backlight: ON", 1000);
  } else {
    lcd.clear();
    lcd.noBacklight();
    Serial.println("LED: OFF");
  }
}

void calibrateStickCenter(bool announce) {
  long sumX = 0;
  long sumY = 0;
  for (int i = 0; i < 16; i++) {
    sumX += (1023 - analogRead(JOY_X));
    sumY += (1023 - analogRead(JOY_Y));
    delay(2);
  }
  centerX = (int)(sumX / 16);
  centerY = (int)(sumY / 16);
  smoothX = (float)centerX;
  smoothY = (float)centerY;

  if (announce) {
    Serial.print("CALIBRATED: ");
    Serial.print(centerX);
    Serial.print(",");
    Serial.println(centerY);
    showToast("  [CALIB]", "Center Locked", 1100);
  }
}

void renderIdleFrame() {
  if (!ledEnabled) return;

  lcd.setCursor(0, 0);
  uint8_t leftWave = WAVE_LUT[(animStep) & 0x0F];
  uint8_t rightWave = WAVE_LUT[(animStep + 8) & 0x0F];

  lcd.write(byte(leftWave));
  lcd.write(' ');
  lcd.write(byte(6));
  lcd.write(byte(7));
  lcd.print(" rUNOdeck ");
  lcd.write(' ');
  lcd.write(byte(rightWave));

  lcd.setCursor(0, 1);
  for (uint8_t col = 0; col < 16; col++) {
    uint8_t idx = (col + animStep) & 0x0F;
    lcd.write(byte(WAVE_LUT[idx]));
  }
  animStep++;
}

void setMode(AppMode newMode) {
  currentMode = newMode;
  selectingMode = false;
  lastActivityTime = millis();
  refreshModeScreen();
  if (currentMode == MODE_MEDIA) Serial.println("MODE: MEDIA");
  else if (currentMode == MODE_MOUSE) Serial.println("MODE: MOUSE");
  else if (currentMode == MODE_SCROLL) Serial.println("MODE: SCROLL");
}

void cycleStickMode() {
  if (currentMode == MODE_MEDIA) setMode(MODE_MOUSE);
  else if (currentMode == MODE_MOUSE) setMode(MODE_SCROLL);
  else setMode(MODE_MEDIA);
}

void checkSerialCommands() {
  while (Serial.available() > 0) {
    char buf[48];
    size_t len = Serial.readBytesUntil('\n', buf, sizeof(buf) - 1);
    buf[len] = '\0';
    while (len > 0 && (buf[len - 1] == '\r' || buf[len - 1] == ' ')) {
      buf[--len] = '\0';
    }
    if (len == 0) continue;

    if (strncmp(buf, "LCD: ", 5) == 0) {
      char* payload = buf + 5;
      char* sep = strchr(payload, '|');
      if (sep != NULL) {
        *sep = '\0';
        const char* tag = payload;
        const char* line2 = sep + 1;
        showToast(tag, line2, 1500);
      } else {
        showToast("   [OPEN]", payload, 1500);
      }
    } else if (strcmp(buf, "CMD: TOGGLE_LED") == 0) {
      setLedState(!ledEnabled);
    } else if (strcmp(buf, "CMD: LED_OFF") == 0) {
      setLedState(false);
    } else if (strcmp(buf, "CMD: LED_ON") == 0) {
      setLedState(true);
    } else if (strcmp(buf, "CMD: CALIBRATE") == 0) {
      calibrateStickCenter(true);
    } else if (strcmp(buf, "CMD: MODE_MEDIA") == 0) {
      setMode(MODE_MEDIA);
    } else if (strcmp(buf, "CMD: MODE_MOUSE") == 0) {
      setMode(MODE_MOUSE);
    } else if (strcmp(buf, "CMD: MODE_SCROLL") == 0) {
      setMode(MODE_SCROLL);
    } else if (strcmp(buf, "CMD: DIAG") == 0) {
      Serial.print("DIAG:");
      for (int i = 0; i < 2; i++) {
        int p = SW_PINS[i];
        pinMode(p, INPUT_PULLUP);
        delayMicroseconds(30);
        int pu = analogRead(p);
        pinMode(p, OUTPUT);
        digitalWrite(p, LOW);
        analogRead(p);
        pinMode(p, INPUT);
        delayMicroseconds(25);
        int pd = analogRead(p);
        pinMode(p, INPUT_PULLUP);
        Serial.print(" A"); Serial.print(i + 2);
        Serial.print("="); Serial.print(pu);
        Serial.print("/"); Serial.print(pd);
      }
      for (int i = 2; i < 6; i++) {
        int p = SW_PINS[i];
        pinMode(p, INPUT_PULLUP);
        delayMicroseconds(20);
        int pu = digitalRead(p);
        pinMode(p, OUTPUT);
        digitalWrite(p, LOW);
        delayMicroseconds(3);
        pinMode(p, INPUT);
        delayMicroseconds(8);
        int pd = digitalRead(p);
        pinMode(p, INPUT_PULLUP);
        Serial.print(" D"); Serial.print(p);
        Serial.print("="); Serial.print(pu);
        Serial.print("/"); Serial.print(pd);
      }
      Serial.println();
    }
  }
}

int swBasePuAnalog[2] = {1023, 1023};
int swBasePdAnalog[2] = {0, 0};
bool swBaselinePd[6] = {LOW, LOW, LOW, LOW, LOW, LOW};

bool probeAnalogSwitchPin(int pin, int idx) {
  pinMode(pin, INPUT_PULLUP);
  delayMicroseconds(30);
  int pu = analogRead(pin);

  pinMode(pin, OUTPUT);
  digitalWrite(pin, LOW);
  analogRead(pin);
  pinMode(pin, INPUT);
  delayMicroseconds(25);
  int pd = analogRead(pin);

  pinMode(pin, INPUT_PULLUP);
  return (abs(pu - swBasePuAnalog[idx]) > 140) || (abs(pd - swBasePdAnalog[idx]) > 180);
}

bool probePinPressed(int pin, bool basePu, bool basePd) {
  pinMode(pin, INPUT_PULLUP);
  delayMicroseconds(20);
  bool pu = digitalRead(pin);

  pinMode(pin, OUTPUT);
  digitalWrite(pin, LOW);
  delayMicroseconds(3);
  pinMode(pin, INPUT);
  delayMicroseconds(8);
  bool pd = digitalRead(pin);

  pinMode(pin, INPUT_PULLUP);
  return (pu != basePu) || (pd != basePd);
}

bool readStickButtonPressed() {
  for (int i = 0; i < 2; i++) {
    if (probeAnalogSwitchPin(SW_PINS[i], i)) {
      return true;
    }
  }
  for (int i = 2; i < 6; i++) {
    if (probePinPressed(SW_PINS[i], swBaselinePullup[i], swBaselinePd[i])) {
      return true;
    }
  }
  return false;
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(8);
  for (int i = 0; i < 2; i++) {
    int p = SW_PINS[i];
    pinMode(p, INPUT_PULLUP);
    delayMicroseconds(50);
    swBasePuAnalog[i] = analogRead(p);

    pinMode(p, OUTPUT);
    digitalWrite(p, LOW);
    analogRead(p);
    pinMode(p, INPUT);
    delayMicroseconds(25);
    swBasePdAnalog[i] = analogRead(p);

    pinMode(p, INPUT_PULLUP);
  }
  for (int i = 2; i < 6; i++) {
    int p = SW_PINS[i];
    pinMode(p, INPUT_PULLUP);
    delayMicroseconds(50);
    swBaselinePullup[i] = digitalRead(p);

    pinMode(p, OUTPUT);
    digitalWrite(p, LOW);
    delayMicroseconds(3);
    pinMode(p, INPUT);
    delayMicroseconds(8);
    swBaselinePd[i] = digitalRead(p);

    pinMode(p, INPUT_PULLUP);
  }

  lcd.init();
  lcd.backlight();
  lcd.createChar(0, bar0);
  lcd.createChar(1, bar1);
  lcd.createChar(2, bar2);
  lcd.createChar(3, bar3);
  lcd.createChar(4, bar4);
  lcd.createChar(5, bar5);
  lcd.createChar(6, infLeft);
  lcd.createChar(7, infRight);

  calibrateStickCenter(false);

  Serial.println("READY");
  drawBrandRow("   v2.4");
  printPadded16(1, "System Ready");
  delay(800);

  lastActivityTime = millis();
  setMode(MODE_MEDIA);
}

void loop() {
  checkSerialCommands();

  char key = keypad.getKey();

  if (key) {
    lastActivityTime = millis();
    isIdle = false;

    if (key == '*') {
      selectingMode = true;
      selectModeTimer = millis();
      if (ledEnabled) {
        drawBrandRow(" [CHORD]");
        printPadded16(1, "Press Key 0-9A-D");
      }
    } 
    else if (selectingMode) {
      selectingMode = false;
      if (key == '0') {
        setLedState(!ledEnabled);
      } else {
        Serial.print("COMBO: ");
        Serial.println(key);
        char fallback[17];
        snprintf(fallback, sizeof(fallback), "Chord [ * + %c ]", key);
        showToast("  [CHORD]", fallback, 1300);
      }
    } 
    else {
      Serial.print("KEY: ");
      Serial.println(key);

      char msg[17];
      snprintf(msg, sizeof(msg), "Key [ %c ] Active", key);
      showToast("  [MACRO]", msg, 1100);
    }
  }

  if (selectingMode && (millis() - selectModeTimer > 3500)) {
    selectingMode = false;
    refreshModeScreen();
  }

  if (showingToast && !selectingMode && (millis() - toastEndTime < 0x80000000UL)) {
    refreshModeScreen();
  }

  // Read and low-pass filter analog stick to remove potentiometer jitter
  int rawX = 1023 - analogRead(JOY_X);
  int rawY = 1023 - analogRead(JOY_Y);
  smoothX = (smoothX * 0.72f) + ((float)rawX * 0.28f);
  smoothY = (smoothY * 0.72f) + ((float)rawY * 0.28f);

  int diffX = (int)smoothX - centerX;
  int diffY = (int)smoothY - centerY;

  // Stream live normalized telemetry (-100..+100) in all modes when deflection changes
  if (millis() - lastTelemTimer >= 45) {
    lastTelemTimer = millis();
    int normX = 0;
    int normY = 0;
    if (abs(diffX) > DEADZONE_TELEM) {
      normX = constrain((-diffX * 100) / 450, -100, 100);
    }
    if (abs(diffY) > DEADZONE_TELEM) {
      normY = constrain((-diffY * 100) / 450, -100, 100);
    }
    if (normX != lastSentNormX || normY != lastSentNormY) {
      lastSentNormX = normX;
      lastSentNormY = normY;
      Serial.print("TELEM: ");
      Serial.print(normX);
      Serial.print(",");
      Serial.println(normY);
    }
  }

  bool joyActive = (abs(diffX) > THRESH_DELTA || abs(diffY) > THRESH_DELTA);
  if (joyActive) {
    lastActivityTime = millis();
    if (isIdle) {
      refreshModeScreen();
    }
  }

  if (currentMode == MODE_MEDIA) {
    if (diffY > THRESH_DELTA) {
      int mag = constrain(diffY, THRESH_DELTA, 512);
      unsigned long interval = map(mag, THRESH_DELTA, 512, 140, 45);
      if (millis() - lastVolTime >= interval) {
        lastVolTime = millis();
        Serial.println("JOY: UP");
      }
    } 
    else if (diffY < -THRESH_DELTA) {
      int mag = constrain(-diffY, THRESH_DELTA, 512);
      unsigned long interval = map(mag, THRESH_DELTA, 512, 140, 45);
      if (millis() - lastVolTime >= interval) {
        lastVolTime = millis();
        Serial.println("JOY: DOWN");
      }
    } 
    else {
      lastVolTime = 0;
    }

    if (diffX > THRESH_DELTA) {
      if (millis() - lastTabTime >= 280) {
        lastTabTime = millis();
        Serial.println("JOY: TAB_LEFT");
      }
    } 
    else if (diffX < -THRESH_DELTA) {
      if (millis() - lastTabTime >= 280) {
        lastTabTime = millis();
        Serial.println("JOY: TAB_RIGHT");
      }
    } 
    else {
      lastTabTime = 0;
    }
  }
  else if (currentMode == MODE_MOUSE) {
    // 62Hz high-resolution normalized deflection vector (-100..+100)
    if (millis() - lastUpdateTimer >= 16) {
      lastUpdateTimer = millis();

      int mx = 0;
      int my = 0;

      if (abs(diffX) > DEADZONE_MOUSE) {
        int effX = (diffX > 0) ? (diffX - DEADZONE_MOUSE) : (diffX + DEADZONE_MOUSE);
        mx = constrain((-effX * 100) / 410, -100, 100);
      }
      if (abs(diffY) > DEADZONE_MOUSE) {
        int effY = (diffY > 0) ? (diffY - DEADZONE_MOUSE) : (diffY + DEADZONE_MOUSE);
        my = constrain((-effY * 100) / 410, -100, 100);
      }

      if (mx != 0 || my != 0) {
        lastActivityTime = millis();
        if (isIdle) refreshModeScreen();
        Serial.print("MOUSE: VEC ");
        Serial.print(mx);
        Serial.print(",");
        Serial.println(my);
      }
    }
  }
  else if (currentMode == MODE_SCROLL) {
    if (millis() - lastUpdateTimer >= 25) {
      lastUpdateTimer = millis();

      int sy = 0;
      if (abs(diffY) > DEADZONE_MOUSE) {
        int effY = (diffY > 0) ? (diffY - DEADZONE_MOUSE) : (diffY + DEADZONE_MOUSE);
        sy = constrain((effY * 100) / 410, -100, 100);
      }

      if (sy != 0) {
        lastActivityTime = millis();
        if (isIdle) refreshModeScreen();
        Serial.print("SCROLL: ");
        Serial.println(sy);
      }
    }
  }

  // Pressing the joystick button (JOY_SW) cycles the stick mode: MEDIA -> MOUSE -> SCROLL
  bool currentBtnState = readStickButtonPressed() ? LOW : HIGH;
  if (currentBtnState == LOW && lastBtnState == HIGH && (millis() - lastBtnDebounce > 220)) {
    lastBtnDebounce = millis();
    cycleStickMode();
  }
  lastBtnState = currentBtnState;

  // Enter and animate non-blocking idle screen after 5 seconds of inactivity
  if (!selectingMode && !showingToast && (millis() - lastActivityTime >= 5000)) {
    isIdle = true;
    if (millis() - lastAnimFrameTime >= 180) {
      lastAnimFrameTime = millis();
      renderIdleFrame();
    }
  }
}
