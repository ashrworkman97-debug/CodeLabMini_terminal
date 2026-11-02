/*
  CLM-1 Code Lab Mini firmware v1.3.0
  Target: ATmega328P-compatible Code Lab Mini
  Serial protocol: 9600 baud, newline-terminated ASCII
  Supports the serial command protocol used by the CLM-1 host application.

  Board mapping used by this build:
    D2       speaker
    D3       vibration motor (PWM)
    D4-D7    four arcade buttons (active LOW)
    D8       red jumbo LED
    D10      green jumbo LED
    D12      blue jumbo LED
    A0       turn knob

  This firmware uses ordinary Arduino AVR functions; no LetsStartCoding.h.
*/
#include <Arduino.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

const uint8_t SPEAKER_PIN = 2;
const uint8_t MOTOR_PIN = 3;
const uint8_t BUTTON_PINS[4] = {4, 5, 6, 7};
const uint8_t LED_PINS[3] = {8, 10, 12}; // 1=red, 2=green, 3=blue
const uint8_t KNOB_PIN = A0;
const unsigned long REPORT_INTERVAL_MS = 120;

char commandBuffer[96];
uint8_t commandLength = 0;
bool streamEnabled = true;
bool toneActive = false;
bool toneHasDeadline = false;
unsigned long toneStopAt = 0;
bool motorActive = false;
bool motorHasDeadline = false;
unsigned long motorStopAt = 0;
uint8_t motorLevel = 0;
unsigned long lastReport = 0;
uint8_t knobMode = 0; // 0=off, 1=tone, 2=motor, 3=color
int lastKnobBucket = -999;

void setLed(uint8_t index, bool on) {
  if (index < 3) digitalWrite(LED_PINS[index], on ? HIGH : LOW);
}

void setMask(uint8_t mask) {
  for (uint8_t i = 0; i < 3; ++i) setLed(i, (mask & (1 << i)) != 0);
}

void setMotor(uint8_t level, unsigned long durationMs) {
  motorLevel = level;
  analogWrite(MOTOR_PIN, level);
  motorActive = level > 0;
  motorHasDeadline = motorActive && durationMs > 0;
  if (motorHasDeadline) motorStopAt = millis() + durationMs;
}

void stopMotorNow() {
  analogWrite(MOTOR_PIN, 0);
  motorLevel = 0;
  motorActive = false;
  motorHasDeadline = false;
}

void stopToneNow() {
  noTone(SPEAKER_PIN);
  toneActive = false;
  toneHasDeadline = false;
}

void beepBlocking(unsigned int hz, unsigned int ms) {
  tone(SPEAKER_PIN, hz);
  delay(ms);
  noTone(SPEAKER_PIN);
}

void setColorName(const char *name) {
  if (strcmp(name, "OFF") == 0 || strcmp(name, "BLACK") == 0) setMask(0);
  else if (strcmp(name, "RED") == 0) setMask(1);
  else if (strcmp(name, "GREEN") == 0) setMask(2);
  else if (strcmp(name, "BLUE") == 0) setMask(4);
  else if (strcmp(name, "YELLOW") == 0) setMask(3);
  else if (strcmp(name, "CYAN") == 0) setMask(6);
  else if (strcmp(name, "MAGENTA") == 0) setMask(5);
  else if (strcmp(name, "WHITE") == 0 || strcmp(name, "ALL") == 0) setMask(7);
  else if (strcmp(name, "ORANGE") == 0) setMask(1); // discrete LEDs: nearest available color
  else { Serial.println(F("ERR COLOR: OFF RED GREEN BLUE YELLOW CYAN MAGENTA WHITE")); return; }
  Serial.print(F("OK COLOR "));
  Serial.println(name);
}

void sendState() {
  Serial.print(F("STATE"));
  for (uint8_t i = 0; i < 4; ++i) {
    Serial.print(' ');
    Serial.print(digitalRead(BUTTON_PINS[i]) == LOW ? 1 : 0);
  }
  Serial.print(' ');
  Serial.println(analogRead(KNOB_PIN));
}

void blinkLed(uint8_t ledIndex, uint8_t count, uint16_t ms) {
  if (ledIndex > 2 || count < 1 || count > 30 || ms < 30 || ms > 2000) {
    Serial.println(F("ERR BLINK RANGE")); return;
  }
  for (uint8_t i = 0; i < count; ++i) {
    setLed(ledIndex, true); delay(ms);
    setLed(ledIndex, false); delay(ms);
  }
  Serial.println(F("OK BLINK"));
}

void doChase(uint8_t cycles, uint16_t ms, bool bounce) {
  if (cycles < 1 || cycles > 20 || ms < 30 || ms > 1000) {
    Serial.println(F("ERR EFFECT RANGE")); return;
  }
  for (uint8_t c = 0; c < cycles; ++c) {
    for (uint8_t i = 0; i < 3; ++i) { setMask(1 << i); delay(ms); }
    if (bounce) for (int8_t i = 1; i >= 0; --i) { setMask(1 << i); delay(ms); }
  }
  setMask(0);
  Serial.println(F("OK WAVE"));
}

void doRainbow(uint8_t cycles, uint16_t ms) {
  const uint8_t colors[7] = {1, 3, 2, 6, 4, 5, 7}; // red, yellow, green, cyan, blue, magenta, white
  if (cycles < 1 || cycles > 20 || ms < 30 || ms > 1500) {
    Serial.println(F("ERR EFFECT RANGE")); return;
  }
  for (uint8_t c = 0; c < cycles; ++c) {
    for (uint8_t i = 0; i < 7; ++i) { setMask(colors[i]); delay(ms); }
  }
  setMask(0);
  Serial.println(F("OK RAINBOW"));
}

void doSiren(uint8_t cycles, bool alarmOnly) {
  if (cycles < 1 || cycles > 20) { Serial.println(F("ERR CYCLES 1-20")); return; }
  for (uint8_t i = 0; i < cycles; ++i) {
    setMask(1); beepBlocking(alarmOnly ? 950 : 520, alarmOnly ? 110 : 180);
    setMask(4); beepBlocking(alarmOnly ? 950 : 980, alarmOnly ? 110 : 180);
  }
  setMask(0);
  Serial.println(alarmOnly ? F("OK ALARM") : F("OK SIREN"));
}

void doLaser() {
  setMask(4);
  for (int hz = 1800; hz >= 260; hz -= 110) beepBlocking((unsigned int)hz, 28);
  setMask(0);
  Serial.println(F("OK LASER"));
}

void doPowerup() {
  const uint8_t masks[3] = {1, 2, 4};
  for (uint8_t i = 0; i < 12; ++i) {
    setMask(masks[i % 3]);
    beepBlocking(260 + i * 115, 65);
  }
  setMask(7); beepBlocking(1500, 170); setMask(0);
  Serial.println(F("OK POWERUP"));
}

void doExplosion() {
  setMask(7);
  setMotor(220, 240);
  for (int hz = 1000; hz >= 90; hz -= 65) beepBlocking((unsigned int)hz, 18);
  setMask(0); stopMotorNow();
  Serial.println(F("OK EXPLOSION"));
}

void doHeartbeat(uint8_t cycles) {
  if (cycles < 1 || cycles > 20) { Serial.println(F("ERR CYCLES 1-20")); return; }
  for (uint8_t i = 0; i < cycles; ++i) {
    setMask(1); setMotor(150, 75); delay(90); setMask(0); stopMotorNow(); delay(90);
    setMask(1); setMotor(190, 75); delay(90); setMask(0); stopMotorNow(); delay(420);
  }
  Serial.println(F("OK HEARTBEAT"));
}

void doParty(uint8_t seconds) {
  if (seconds < 1 || seconds > 10) { Serial.println(F("ERR PARTY RANGE 1-10 SECONDS")); return; }
  unsigned long endAt = millis() + (unsigned long)seconds * 1000UL;
  while ((long)(millis() - endAt) < 0) {
    uint8_t mask = (uint8_t)random(1, 8);
    setMask(mask);
    beepBlocking((unsigned int)random(180, 1600), (unsigned int)random(35, 100));
    analogWrite(MOTOR_PIN, (uint8_t)random(80, 220));
    delay(45);
    analogWrite(MOTOR_PIN, 0);
    delay((unsigned int)random(25, 100));
  }
  setMask(0); stopMotorNow(); stopToneNow();
  Serial.println(F("OK PARTY"));
}

void doMelody() {
  // Original short chiptune phrase; not a recording or transcription of an existing song.
  const unsigned int notes[] = {523, 659, 784, 1047, 784, 659, 587, 698, 880, 1175};
  setMask(2);
  for (uint8_t i = 0; i < sizeof(notes) / sizeof(notes[0]); ++i) {
    tone(SPEAKER_PIN, notes[i]); delay(115); noTone(SPEAKER_PIN); delay(35);
    setMask(1 << (i % 3));
  }
  setMask(0);
  Serial.println(F("OK MELODY"));
}

void doCountdown(uint8_t count) {
  if (count < 1 || count > 10) { Serial.println(F("ERR COUNTDOWN RANGE 1-10")); return; }
  for (int i = count; i > 0; --i) {
    setMask(1);
    beepBlocking(i == 1 ? 1100 : 650, 130);
    setMask(0); delay(650);
  }
  setMask(7); beepBlocking(1400, 350); setMask(0);
  Serial.println(F("OK GO"));
}

void doMetronome(uint16_t bpm, uint8_t beats) {
  if (bpm < 20 || bpm > 240 || beats < 1 || beats > 64) {
    Serial.println(F("ERR METRO: BPM 20-240, BEATS 1-64")); return;
  }
  unsigned int interval = 60000UL / bpm;
  for (uint8_t i = 0; i < beats; ++i) {
    setMask((i % 4 == 0) ? 1 : 2);
    beepBlocking((i % 4 == 0) ? 1000 : 650, 55);
    setMask(0);
    if (interval > 55) delay(interval - 55);
  }
  Serial.println(F("OK METRO"));
}

void doLedTest() {
  for (uint8_t i = 0; i < 3; ++i) {
    setMask((uint8_t)(1 << i));
    beepBlocking(520 + i * 180, 110);
    delay(150);
  }
  setMask(0);
  Serial.println(F("OK LEDTEST"));
}

void doGlitch() {
  for (uint8_t i = 0; i < 18; ++i) {
    setMask((uint8_t)random(0, 8));
    tone(SPEAKER_PIN, (unsigned int)random(100, 2400));
    delay((unsigned int)random(25, 85));
    noTone(SPEAKER_PIN);
  }
  setMask(0);
  Serial.println(F("OK GLITCH"));
}

void doBeacon(uint8_t cycles) {
  if (cycles < 1 || cycles > 20) { Serial.println(F("ERR CYCLES 1-20")); return; }
  for (uint8_t i = 0; i < cycles; ++i) {
    for (uint8_t flash = 0; flash < 3; ++flash) {
      setMask(4); beepBlocking(1000, 75); setMask(0); delay(100);
    }
    delay(350);
  }
  Serial.println(F("OK BEACON"));
}

void doPortal() {
  for (uint8_t round = 0; round < 3; ++round) {
    for (uint8_t led = 0; led < 3; ++led) {
      setMask((uint8_t)(1 << led));
      beepBlocking(260 + round * 220 + led * 160, 95);
    }
  }
  setMask(7); beepBlocking(1500, 180); setMask(0);
  Serial.println(F("OK PORTAL"));
}

void doFireworks(uint8_t count) {
  if (count < 1 || count > 10) { Serial.println(F("ERR FIREWORKS 1-10")); return; }
  for (uint8_t i = 0; i < count; ++i) {
    setMask((uint8_t)(1 << (i % 3)));
    for (int hz = 300; hz <= 1200; hz += 150) { tone(SPEAKER_PIN, (unsigned int)hz); delay(25); }
    noTone(SPEAKER_PIN);
    setMask(7); setMotor(210, 100); delay(120); setMask(0); stopMotorNow();
    delay(220);
  }
  Serial.println(F("OK FIREWORKS"));
}

void doHyperspace() {
  const uint8_t colors[3] = {1, 2, 4};
  for (uint8_t i = 0; i < 10; ++i) {
    setMask(colors[i % 3]);
    beepBlocking(180 + i * 185, 75);
  }
  setMask(7); beepBlocking(2100, 250); setMask(0);
  Serial.println(F("OK HYPERSPACE"));
}

void doDice() {
  long value = random(1, 7);
  setMask((uint8_t)value & 7);
  for (long i = 0; i < value; ++i) { beepBlocking(800 + (unsigned int)value * 70, 65); delay(55); }
  Serial.print(F("DICE ")); Serial.println(value);
  delay(500); setMask(0);
}

void doCoin() {
  bool heads = random(0, 2) == 1;
  setMask(heads ? 2 : 1);
  beepBlocking(heads ? 1050 : 500, 220);
  Serial.println(heads ? F("COIN HEADS") : F("COIN TAILS"));
  delay(350); setMask(0);
}

void processCommand(char *cmd) {
  char *tokens[8];
  uint8_t count = 0;
  char *token = strtok(cmd, " \t");
  while (token && count < 8) { tokens[count++] = token; token = strtok(NULL, " \t"); }
  if (count == 0) return;
  for (uint8_t i = 0; i < count; ++i) {
    for (char *p = tokens[i]; *p; ++p) *p = (char)toupper((unsigned char)*p);
  }
  const char *op = tokens[0];

  if (strcmp(op, "PING") == 0) {
    Serial.println(F("PONG"));
  } else if (strcmp(op, "INFO") == 0) {
    Serial.println(F("INFO CLM-1 FW=1.3.0 MCU=ATmega328P BAUD=9600"));
  } else if (strcmp(op, "HELP") == 0) {
    Serial.println(F("CMDS PING INFO HELP READ STATUS BUTTONS LED LEDTEST COLOR RGB BLINK CHASE RAINBOW WAVE PARTY SIREN ALARM LASER POWERUP EXPLOSION HEARTBEAT MELODY COUNTDOWN METRO MOTOR VIBRATE BUZZ PULSE KNOB DICE COIN RANDOM GLITCH BEACON PORTAL FIREWORKS HYPERSPACE STREAM STOP RESET PANIC ECHO"));
  } else if (strcmp(op, "READ") == 0 || strcmp(op, "STATUS") == 0 || strcmp(op, "BUTTONS") == 0) {
    sendState();
  } else if (strcmp(op, "LED") == 0) {
    if (count >= 2 && strcmp(tokens[1], "ALL") == 0) {
      const char *action = count >= 3 ? tokens[2] : "ON";
      if (strcmp(action, "ON") == 0 || strcmp(action, "1") == 0) {
        setMask(7); Serial.println(F("OK LED ALL ON"));
      } else if (strcmp(action, "OFF") == 0 || strcmp(action, "0") == 0) {
        setMask(0); Serial.println(F("OK LED ALL OFF"));
      } else {
        Serial.println(F("ERR LED ALL ON|OFF"));
      }
    } else if (count == 2 && strcmp(tokens[1], "0") == 0) {
      setLed(0, false); Serial.println(F("OK LED 1 OFF"));
    } else if (count == 2 && strcmp(tokens[1], "TOGGLE") == 0) {
      setLed(0, !digitalRead(LED_PINS[0])); Serial.println(F("OK LED 1 TOGGLE"));
    } else if (count >= 2 && count <= 3) {
      long number = atol(tokens[1]);
      if (number < 1 || number > 3) { Serial.println(F("ERR LED NUMBER 1-3")); return; }
      const char *action = count == 3 ? tokens[2] : "ON";
      if (strcmp(action, "ON") == 0 || strcmp(action, "1") == 0) setLed((uint8_t)(number - 1), true);
      else if (strcmp(action, "OFF") == 0 || strcmp(action, "0") == 0) setLed((uint8_t)(number - 1), false);
      else if (strcmp(action, "TOGGLE") == 0) setLed((uint8_t)(number - 1), !digitalRead(LED_PINS[number - 1]));
      else { Serial.println(F("ERR LED ACTION ON OFF TOGGLE")); return; }
      Serial.print(F("OK LED ")); Serial.print(number); Serial.print(' '); Serial.println(action);
    } else {
      Serial.println(F("ERR LED FORMAT: LED 1|2|3 [ON|OFF|TOGGLE] or LED ALL"));
    }
  } else if (strcmp(op, "COLOR") == 0 && count == 2) {
    setColorName(tokens[1]);
  } else if (strcmp(op, "RGB") == 0 && count == 4) {
    long r = atol(tokens[1]), g = atol(tokens[2]), b = atol(tokens[3]);
    if ((r != 0 && r != 1) || (g != 0 && g != 1) || (b != 0 && b != 1)) {
      Serial.println(F("ERR RGB CHANNELS ARE ON/OFF: RGB 1 0 1")); return;
    }
    setMask((uint8_t)(r | (g << 1) | (b << 2)));
    Serial.println(F("OK RGB"));
  } else if (strcmp(op, "BLINK") == 0) {
    long led = 1, repetitions = 3, ms = 200;
    if (count == 3) { repetitions = atol(tokens[1]); ms = atol(tokens[2]); }
    else if (count >= 4) { led = atol(tokens[1]); repetitions = atol(tokens[2]); ms = atol(tokens[3]); }
    blinkLed((uint8_t)(led - 1), (uint8_t)repetitions, (uint16_t)ms);
  } else if (strcmp(op, "CHASE") == 0 || strcmp(op, "WAVE") == 0) {
    uint8_t cycles = count > 1 ? (uint8_t)atol(tokens[1]) : 2;
    uint16_t ms = count > 2 ? (uint16_t)atol(tokens[2]) : 120;
    doChase(cycles, ms, strcmp(op, "WAVE") == 0);
  } else if (strcmp(op, "RAINBOW") == 0) {
    uint8_t cycles = count > 1 ? (uint8_t)atol(tokens[1]) : 1;
    uint16_t ms = count > 2 ? (uint16_t)atol(tokens[2]) : 120;
    doRainbow(cycles, ms);
  } else if (strcmp(op, "PARTY") == 0) {
    doParty(count > 1 ? (uint8_t)atol(tokens[1]) : 5);
  } else if (strcmp(op, "SIREN") == 0 || strcmp(op, "ALARM") == 0) {
    doSiren(count > 1 ? (uint8_t)atol(tokens[1]) : 3, strcmp(op, "ALARM") == 0);
  } else if (strcmp(op, "LEDTEST") == 0) {
    doLedTest();
  } else if (strcmp(op, "GLITCH") == 0) {
    doGlitch();
  } else if (strcmp(op, "BEACON") == 0) {
    doBeacon(count > 1 ? (uint8_t)atol(tokens[1]) : 3);
  } else if (strcmp(op, "PORTAL") == 0) {
    doPortal();
  } else if (strcmp(op, "FIREWORKS") == 0) {
    doFireworks(count > 1 ? (uint8_t)atol(tokens[1]) : 3);
  } else if (strcmp(op, "HYPERSPACE") == 0) {
    doHyperspace();
  } else if (strcmp(op, "LASER") == 0) {
    doLaser();
  } else if (strcmp(op, "POWERUP") == 0) {
    doPowerup();
  } else if (strcmp(op, "EXPLOSION") == 0) {
    doExplosion();
  } else if (strcmp(op, "HEARTBEAT") == 0) {
    doHeartbeat(count > 1 ? (uint8_t)atol(tokens[1]) : 2);
  } else if (strcmp(op, "MELODY") == 0) {
    doMelody();
  } else if (strcmp(op, "COUNTDOWN") == 0) {
    doCountdown(count > 1 ? (uint8_t)atol(tokens[1]) : 3);
  } else if (strcmp(op, "METRO") == 0 && count >= 2) {
    doMetronome((uint16_t)atol(tokens[1]), count > 2 ? (uint8_t)atol(tokens[2]) : 16);
  } else if (strcmp(op, "MOTOR") == 0 || strcmp(op, "BUZZ") == 0 || strcmp(op, "VIBRATE") == 0) {
    if (count >= 2 && (strcmp(tokens[1], "OFF") == 0 || strcmp(tokens[1], "0") == 0)) {
      stopMotorNow(); Serial.println(F("OK MOTOR OFF"));
    } else {
      long level = count > 1 ? atol(tokens[1]) : 180;
      long duration = count > 2 ? atol(tokens[2]) : 350;
      if (level < 0 || level > 255 || duration < 1 || duration > 5000) {
        Serial.println(F("ERR MOTOR: LEVEL 0-255, DURATION 1-5000 MS")); return;
      }
      setMotor((uint8_t)level, (unsigned long)duration);
      Serial.println(F("OK MOTOR"));
    }
  } else if (strcmp(op, "PULSE") == 0) {
    long pulses = count > 1 ? atol(tokens[1]) : 3;
    long level = count > 2 ? atol(tokens[2]) : 180;
    long onMs = count > 3 ? atol(tokens[3]) : 100;
    long offMs = count > 4 ? atol(tokens[4]) : 120;
    if (pulses < 1 || pulses > 20 || level < 1 || level > 255 || onMs < 20 || onMs > 1000 || offMs < 20 || offMs > 1000) {
      Serial.println(F("ERR PULSE RANGE")); return;
    }
    for (long i = 0; i < pulses; ++i) { setMotor((uint8_t)level, 0); delay(onMs); stopMotorNow(); delay(offMs); }
    Serial.println(F("OK PULSE"));
  } else if (strcmp(op, "KNOB") == 0 && count >= 2) {
    if (strcmp(tokens[1], "OFF") == 0) {
      knobMode = 0; lastKnobBucket = -999; stopToneNow(); stopMotorNow();
      Serial.println(F("OK KNOB OFF"));
    } else if (strcmp(tokens[1], "TONE") == 0 || strcmp(tokens[1], "MOTOR") == 0 || strcmp(tokens[1], "COLOR") == 0) {
      knobMode = strcmp(tokens[1], "TONE") == 0 ? 1 : (strcmp(tokens[1], "MOTOR") == 0 ? 2 : 3);
      lastKnobBucket = -999;
      Serial.print(F("OK KNOB ")); Serial.println(tokens[1]);
    } else {
      Serial.println(F("ERR KNOB TONE|MOTOR|COLOR|OFF"));
    }
  } else if (strcmp(op, "BEEP") == 0 || strcmp(op, "TONE") == 0) {
    bool timed = strcmp(op, "BEEP") == 0;
    long frequency = count > 1 ? atol(tokens[1]) : 700;
    long duration = count > 2 ? atol(tokens[2]) : 300;
    if (frequency < 40 || frequency > 10000 || (timed && (duration < 1 || duration > 5000))) {
      Serial.println(F("ERR TONE RANGE")); return;
    }
    tone(SPEAKER_PIN, (unsigned int)frequency);
    toneActive = true;
    toneHasDeadline = timed;
    if (timed) toneStopAt = millis() + (unsigned long)duration;
    Serial.println(timed ? F("OK BEEP") : F("OK TONE"));
  } else if (strcmp(op, "STOP") == 0) {
    stopToneNow(); stopMotorNow();
    Serial.println(F("OK STOP"));
  } else if (strcmp(op, "RESET") == 0 || strcmp(op, "PANIC") == 0) {
    knobMode = 0; setMask(0); stopToneNow(); stopMotorNow();
    Serial.println(F("OK RESET"));
  } else if (strcmp(op, "STREAM") == 0 && count == 2 && (strcmp(tokens[1], "0") == 0 || strcmp(tokens[1], "1") == 0 || strcmp(tokens[1], "ON") == 0 || strcmp(tokens[1], "OFF") == 0)) {
    streamEnabled = strcmp(tokens[1], "0") != 0 && strcmp(tokens[1], "OFF") != 0;
    Serial.println(streamEnabled ? F("OK STREAM ON") : F("OK STREAM OFF"));
  } else if (strcmp(op, "ECHO") == 0) {
    Serial.print(F("ECHO"));
    for (uint8_t i = 1; i < count; ++i) { Serial.print(' '); Serial.print(tokens[i]); }
    Serial.println();
  } else if (strcmp(op, "DICE") == 0) {
    doDice();
  } else if (strcmp(op, "COIN") == 0) {
    doCoin();
  } else if (strcmp(op, "RANDOM") == 0) {
    setMask((uint8_t)random(1, 8));
    beepBlocking((unsigned int)random(180, 1800), 180);
    setMask(0); Serial.println(F("OK RANDOM"));
  } else {
    Serial.println(F("ERR UNKNOWN COMMAND. TYPE HELP"));
  }
}

void setup() {
  for (uint8_t i = 0; i < 3; ++i) { pinMode(LED_PINS[i], OUTPUT); setLed(i, false); }
  pinMode(SPEAKER_PIN, OUTPUT);
  pinMode(MOTOR_PIN, OUTPUT);
  stopToneNow(); stopMotorNow();
  for (uint8_t i = 0; i < 4; ++i) pinMode(BUTTON_PINS[i], INPUT_PULLUP);
  pinMode(KNOB_PIN, INPUT);
  Serial.begin(9600);
  randomSeed(analogRead(KNOB_PIN) + micros());
  Serial.println(F("CLM-1 READY FW=1.3.0"));
}

void loop() {
  while (Serial.available() > 0) {
    char incoming = (char)Serial.read();
    if (incoming == '\r') continue;
    if (incoming == '\n') {
      commandBuffer[commandLength] = '\0';
      if (commandLength > 0) processCommand(commandBuffer);
      commandLength = 0;
    } else if (commandLength < sizeof(commandBuffer) - 1) {
      commandBuffer[commandLength++] = incoming;
    } else {
      commandLength = 0;
      Serial.println(F("ERR COMMAND TOO LONG"));
    }
  }

  unsigned long now = millis();
  if (toneActive && toneHasDeadline && (long)(now - toneStopAt) >= 0) stopToneNow();
  if (motorActive && motorHasDeadline && (long)(now - motorStopAt) >= 0) stopMotorNow();

  if (knobMode != 0) {
    int knob = analogRead(KNOB_PIN);
    if (knobMode == 1) {
      int bucket = knob / 8;
      if (bucket != lastKnobBucket) {
        lastKnobBucket = bucket;
        unsigned int hz = (unsigned int)map(knob, 0, 1023, 120, 1800);
        tone(SPEAKER_PIN, hz); toneActive = true; toneHasDeadline = false;
      }
    } else if (knobMode == 2) {
      int level = map(knob, 0, 1023, 0, 255);
      if (abs(level - lastKnobBucket) >= 3) {
        lastKnobBucket = level;
        analogWrite(MOTOR_PIN, (uint8_t)level);
        motorLevel = (uint8_t)level;
        motorActive = level > 0; motorHasDeadline = false;
      }
    } else if (knobMode == 3) {
      int bucket = knob / 146;
      if (bucket > 6) bucket = 6;
      if (bucket != lastKnobBucket) {
        lastKnobBucket = bucket;
        const uint8_t colors[7] = {1, 3, 2, 6, 4, 5, 7};
        setMask(colors[bucket]);
      }
    }
  }

  if (streamEnabled && now - lastReport >= REPORT_INTERVAL_MS) {
    lastReport = now;
    sendState();
  }
}
