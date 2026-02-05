#include <Servo.h>

/* ====== ПИНЫ МОТОРОВ ====== */
#define MOTOR_A_IN1 3   // ЛЕВЫЙ мотор
#define MOTOR_A_IN2 5

#define MOTOR_B_IN3 6   // ПРАВЫЙ мотор
#define MOTOR_B_IN4 11

/* ====== СЕРВО ====== */
#define PIN_SERVO 9
#define SERVO1_MIN 15
#define SERVO1_MAX 30

#define PIN_SERVO2 10
#define SERVO2_MIN 0
#define SERVO2_MAX 90

Servo servo;
Servo servo2;


/* ====== КОНСТАНТЫ СКОРОСТИ ====== */
#define MIN_SPEED     50
#define SPEED_STEP    5

#define START_PWM_LEFT   130
#define START_PWM_RIGHT  130

#define TURN_MIN_SPEED   35

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

/* ====== ДВИЖЕНИЕ ====== */
void setForward() {
  rampSpeed();
  resetDir();
  state.isForward = true;
  runMotors(state.curSpeed, state.curSpeed, DIR_FORWARD);
}

void setBackward() {
  rampSpeed();
  resetDir();
  state.isBackward = true;
  runMotors(state.curSpeed, state.curSpeed, DIR_BACKWARD);
}

void setLeft() {
  rampSpeed();
  resetDir();
  state.isLeft = true;

  float turnCoef = 0.3;
  uint8_t l = state.curSpeed * (1.0 - turnCoef);
  uint8_t r = state.curSpeed * (1.0 + turnCoef);

  if (l < TURN_MIN_SPEED) l = TURN_MIN_SPEED;
  runMotors(l, r, DIR_FORWARD);
}

void setRight() {
  rampSpeed();
  resetDir();
  state.isRight = true;

  float turnCoef = 0.3;
  uint8_t l = state.curSpeed * (1.0 + turnCoef);
  uint8_t r = state.curSpeed * (1.0 - turnCoef);

  if (r < TURN_MIN_SPEED) r = TURN_MIN_SPEED;
  runMotors(l, r, DIR_FORWARD);
}

void setStop() {
  stopAll();
#if DEBUG_OUTPUT
  Serial.println(F("STOP"));
#endif
}

/* ====== МОТОРЫ (ПИНЫ) ====== */
void runMotors(uint8_t leftPct, uint8_t rightPct, uint8_t dir) {
  leftPct  = constrain(leftPct, 0, 100);
  rightPct = constrain(rightPct, 0, 100);

  int leftPWM  = map(leftPct  * K_LEFT_MOTOR,  0, 100, 0, 255);
  int rightPWM = map(rightPct * K_RIGHT_MOTOR, 0, 100, 0, 255);

  if (leftPWM > 0 && !state.leftRunning) {
    leftPWM = max(leftPWM, START_PWM_LEFT);
    state.leftRunning = true;
  }
  if (rightPWM > 0 && !state.rightRunning) {
    rightPWM = max(rightPWM, START_PWM_RIGHT);
    state.rightRunning = true;
  }

  leftPWM  = constrain(leftPWM, 0, 255);
  rightPWM = constrain(rightPWM, 0, 255);

  /* ЛЕВЫЙ МОТОР */
  if (dir == DIR_FORWARD) {
    analogWrite(MOTOR_A_IN1, leftPWM);
    analogWrite(MOTOR_A_IN2, 0);
  } else {
    analogWrite(MOTOR_A_IN1, 0);
    analogWrite(MOTOR_A_IN2, leftPWM);
  }

  /* ПРАВЫЙ МОТОР */
  if (dir == DIR_FORWARD) {
    analogWrite(MOTOR_B_IN3, rightPWM);
    analogWrite(MOTOR_B_IN4, 0);
  } else {
    analogWrite(MOTOR_B_IN3, 0);
    analogWrite(MOTOR_B_IN4, rightPWM);
  }

#if DEBUG_OUTPUT
  Serial.print(F("PWM L/R: "));
  Serial.print(leftPWM);
  Serial.print(F(" / "));
  Serial.println(rightPWM);
#endif
}

/* ====== СТОП ====== */
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
