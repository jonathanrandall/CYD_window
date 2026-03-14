#ifndef TFT_STUFF_H_
#define TFT_STUFF_H_

#include <FS.h>
#include <SPIFFS.h>
#include <TJpg_Decoder.h>
#include <TFT_eSPI.h>  // TFT library (make sure to include the correct library for your TFT display)
#include <XPT2046_Touchscreen.h>
#include <SPI.h>

#define TFT_WIDTH  240
#define TFT_HEIGHT 320
#define GRID_SIZE  4
// #define TOUCH_CS   15
#define TOUCH_IRQ  -1
#define FILE_PATH  "/stream_config.txt"


#define XPT2046_IRQ 36
#define XPT2046_MOSI 32
#define XPT2046_MISO 39
#define XPT2046_CLK 25
#define XPT2046_CS 33

const uint16_t touchScreenMinimumX = 200, touchScreenMaximumX = 3800, touchScreenMinimumY = 250,touchScreenMaximumY = 3850;
SPIClass mySpi = SPIClass(VSPI);
XPT2046_Touchscreen ts(XPT2046_CS, XPT2046_IRQ);

TFT_eSPI tft = TFT_eSPI();

const char* base_url = "http://rpizero.local:7123/stream";
// const char* stream_url ="http://192.168.4.1:81/stream";
char stream_url[50];

const char* base_touch_url = "http://rpizero.local:7123/touch";
char touch_url[50];

static bool wasTouched = false;
static uint32_t lastTouchTime = 0;
const uint32_t TOUCH_DEBOUNCE = 250;

void notifyTouch() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(touch_url);
  http.GET();        // simple ping
  http.end();
}

void checkTouch() {
  uint32_t now = millis();
  if (now - lastTouchTime < TOUCH_DEBOUNCE) return;

  bool touched = (ts.tirqTouched() && ts.touched());

  if (touched && !wasTouched) {
    notifyTouch();        // send signal
    wasTouched = true;
    lastTouchTime = now;
  }
  else if (!touched && wasTouched) {
    wasTouched = false;
    lastTouchTime = now;
  }
}

void saveSelection(int x, int y) {
    fs::File file = SPIFFS.open(FILE_PATH, "w");
    if (file) {
        file.printf("%d%d", x, y);
        file.close();
    } else {
      Serial.println("error");
    }
}

void loadSelection(int &x, int &y) {
    if (SPIFFS.exists(FILE_PATH)) {
      Serial.println("loading file");
        fs::File file = SPIFFS.open(FILE_PATH, "r");
        if (file) {
            char buf[3];
            file.readBytes(buf, 2);
            buf[2] = '\0';
            x = buf[0] - '0';
            y = buf[1] - '0';
            file.close();
        }
    }
}

void drawGrid() {
    int cellW = TFT_WIDTH / GRID_SIZE;
    int cellH = TFT_HEIGHT / GRID_SIZE;
    for (int x = 0; x < GRID_SIZE; x++) {
        for (int y = 0; y < GRID_SIZE; y++) {
            // tft.fillRect(x * cellW, y * cellH, cellW, cellH, random(0xFFFF));
            tft.fillRect(y * cellH,x * cellW,  cellH,cellW, random(0xFFFF));
        }
    }
}

void waitForSelection(int &selX, int &selY) {
    int x,y;
    int cellW = TFT_WIDTH / GRID_SIZE;
    int cellH = TFT_HEIGHT / GRID_SIZE;
    uint32_t start = millis();
    drawGrid();
    while (millis() - start < 3000) {
        if (ts.tirqTouched() && ts.touched()) {
            TS_Point p = ts.getPoint();
            x = map(p.x,touchScreenMinimumX,touchScreenMaximumX,0,TFT_WIDTH);
            y = map(p.y,touchScreenMinimumY,touchScreenMaximumY,0,TFT_HEIGHT);
            selY = x / cellW;
            selX = y / cellH;
            Serial.println(cellH);
            Serial.println(cellW);
            Serial.println(p.x);
            Serial.println(p.y);
            saveSelection(selX, selY);
            break;
        }
    }
}

#endif
// #include <TFT_eSPI.h>

// TFT_eSPI tft = TFT_eSPI();

// void displayImage(uint8_t* buf, size_t len) {
//   // Display image on the screen
//   tft.drawBitmap(0, 0, buf, width, height, color);
// }
