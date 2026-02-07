#include <Servo.h>

/* ====== ПИНЫ МОТОРОВ ====== */
#define MOTOR_A_IN1 3   // ЛЕВЫЙ мотор
#define MOTOR_A_IN2 5
#define MOTOR_B_IN3 6   // ПРАВЫЙ мотор
#define MOTOR_B_IN4 11

/* ====== СЕРВО ====== */
#define PIN_SERVO 9
#define SERVO1_MIN 12
#define SERVO1_MAX 30
#define PIN_SERVO2 10
#define SERVO2_MIN 60
#define SERVO2_MAX 105

Servo servo;
Servo servo2;

/* ====== КОНСТАНТЫ СКОРОСТИ ====== */
#define MIN_SPEED     65
#define SPEED_STEP    5
#define START_PWM_LEFT   130
#define START_PWM_RIGHT  130

/* ====== КОЭФФИЦИЕНТЫ МОТОРОВ ====== */
#define K_LEFT_MOTOR   1.0
#define K_RIGHT_MOTOR  0.9

#define DEBUG_OUTPUT 1

/* ====== СОСТОЯНИЕ ====== */
struct {
  uint8_t curSpeed;
  bool isForward;
  bool isBackward;
  bool isLeft;
  bool isRight;
  bool isMoving;
  bool isHolding;
  bool isUp;
  bool leftRunning;
  bool rightRunning;
} state;

/* ====== НАПРАВЛЕНИЯ ====== */
#define DIR_FORWARD  1
#define DIR_BACKWARD 2

/* ================================================== */
void setup() {
  Serial.begin(9600);

  pinMode(MOTOR_A_IN1, OUTPUT);
  pinMode(MOTOR_A_IN2, OUTPUT);
  pinMode(MOTOR_B_IN3, OUTPUT);
  pinMode(MOTOR_B_IN4, OUTPUT);

  servo.attach(PIN_SERVO);
  servo.write(SERVO1_MIN);
  servo2.attach(PIN_SERVO2);
  servo2.write(SERVO2_MIN);

  state.curSpeed = MIN_SPEED;
  stopAll();

#if DEBUG_OUTPUT
  Serial.println(F("Готов"));
#endif
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') return;
    handleCommand(c);
  }
}

/* ====== КОМАНДЫ ====== */
void handleCommand(char c) {
  switch (c) {
    case 'F': case 'f': setForward(); break;
    case 'B': case 'b': setBackward(); break;
    case 'L': case 'l': setLeft(); break;
    case 'R': case 'r': setRight(); break;
    case 'S': case 's': setStop(); break;
    case 'G': case 'g': setGrab(); break;
    case 'H': case 'h': setRelease(); break;
    case 'U': case 'u': setUp(); break;
    case 'D': case 'd': setDown(); break;
  }
}

/* ====== ДВИЖЕНИЕ ВПЕРЁД/НАЗАД ====== */
void setForward() {
  rampSpeed();
  resetDir();
  state.isForward = true;

  int leftPWM  = map(state.curSpeed * K_LEFT_MOTOR, 0, 100, 0, 255);
  int rightPWM = map(state.curSpeed * K_RIGHT_MOTOR, 0, 100, 0, 255);
  leftPWM  = max(leftPWM, START_PWM_LEFT);
  rightPWM = max(rightPWM, START_PWM_RIGHT);

  analogWrite(MOTOR_A_IN1, leftPWM);
  analogWrite(MOTOR_A_IN2, 0);

  analogWrite(MOTOR_B_IN3, rightPWM);
  analogWrite(MOTOR_B_IN4, 0);

#if DEBUG_OUTPUT
  Serial.print(F("FORWARD PWM L/R: "));
  Serial.print(leftPWM);
  Serial.print(F(" / "));
  Serial.println(rightPWM);
#endif
}

void setBackward() {
  rampSpeed();
  resetDir();
  state.isBackward = true;

  int leftPWM  = map(state.curSpeed * K_LEFT_MOTOR, 0, 100, 0, 255);
  int rightPWM = map(state.curSpeed * K_RIGHT_MOTOR, 0, 100, 0, 255);
  leftPWM  = max(leftPWM, START_PWM_LEFT);
  rightPWM = max(rightPWM, START_PWM_RIGHT);

  analogWrite(MOTOR_A_IN1, 0);
  analogWrite(MOTOR_A_IN2, leftPWM);

  analogWrite(MOTOR_B_IN3, 0);
  analogWrite(MOTOR_B_IN4, rightPWM);

#if DEBUG_OUTPUT
  Serial.print(F("BACKWARD PWM L/R: "));
  Serial.print(leftPWM);
  Serial.print(F(" / "));
  Serial.println(rightPWM);
#endif
}

/* ====== ПОВОРОТЫ ЧЕРЕЗ МАКСИМАЛЬНЫЙ PWM НА ОДНОМ КОЛЕСЕ ====== */
void setLeft() {
  resetDir();
  state.isLeft = true;

  // Левое колесо стоит
  analogWrite(MOTOR_A_IN1, 0);
  analogWrite(MOTOR_A_IN2, 0);

  // Правое колесо вперед на максимум
  analogWrite(MOTOR_B_IN3, 255);
  analogWrite(MOTOR_B_IN4, 0);

#if DEBUG_OUTPUT
  Serial.println(F("TURN LEFT: RIGHT WHEEL MAX, LEFT STOP"));
#endif
}

void setRight() {
  resetDir();
  state.isRight = true;

  // Левое колесо вперед на максимум
  analogWrite(MOTOR_A_IN1, 255);
  analogWrite(MOTOR_A_IN2, 0);

  // Правое колесо стоит
  analogWrite(MOTOR_B_IN3, 0);
  analogWrite(MOTOR_B_IN4, 0);

#if DEBUG_OUTPUT
  Serial.println(F("TURN RIGHT: LEFT WHEEL MAX, RIGHT STOP"));
#endif
}

/* ====== СТОП ====== */
void setStop() {
  stopAll();
#if DEBUG_OUTPUT
  Serial.println(F("STOP"));
#endif
}

void stopAll() {
  analogWrite(MOTOR_A_IN1, 0);
  analogWrite(MOTOR_A_IN2, 0);
  analogWrite(MOTOR_B_IN3, 0);
  analogWrite(MOTOR_B_IN4, 0);

  state.leftRunning = false;
  state.rightRunning = false;
  state.isMoving = false;
  state.curSpeed = MIN_SPEED;
}

/* ====== ВСПОМОГАТЕЛЬНОЕ ====== */
void resetDir() {
  state.isForward = state.isBackward = state.isLeft = state.isRight = false;
  state.isMoving = true;
}

void rampSpeed() {
  if (state.isMoving && state.curSpeed < 100)
    state.curSpeed += SPEED_STEP;
  else if (!state.isMoving)
    state.curSpeed = MIN_SPEED;
}

/* ====== СЕРВО 1 ====== */
void setGrab() {
  servo.write(SERVO1_MAX);
  state.isHolding = true;
}

void setRelease() {
  servo.write(SERVO1_MIN);
  state.isHolding = false;
}

/* ====== СЕРВО 2 ====== */
void setUp() {
  servo2.write(SERVO2_MAX);
  state.isUp = true;
}

void setDown() {
  servo2.write(SERVO2_MIN);
  state.isUp = false;
}
