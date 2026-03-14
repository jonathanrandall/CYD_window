#include <WiFi.h>

#include <HTTPClient.h>

#include "tft_stuff.h"



const char *ssid = "";
const char *password = "";


//home/jonny/Arduino/test_stuff/wifi_scan/wifi_scan.ino
// TFT_eSPI tft = TFT_eSPI();  // Initialize TFT display
WiFiClient client;

#define PART_BOUNDARY "123456789000000000000987654321"
static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length ";//%u\r\n\r\n";

bool tft_output(int16_t x, int16_t y, uint16_t w, uint16_t h, uint16_t* bitmap){
  if ( y >= tft.height() ) return 0;
  tft.pushImage(x, y, w, h, bitmap);
  return 1;
}





void drawJpeg(uint8_t* image_data, size_t length) {
  Serial.println("Processing full image...");
  TJpgDec.drawJpg(0, 0, (const uint8_t*)image_data, length);
  // Display or process the complete image here (e.g., render it on the TFT)
}

void init_wifi()
{
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
    Serial.println("");
    Serial.println("WiFi connected");
    Serial.println("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.println("");
    return;
 
}

void setup() {
  Serial.begin(115200);
  init_wifi();

if(!SPIFFS.begin(true)){
  Serial.println("error mounting spiffs");
  // return;
}

  // Connect to the ESP32-CAM Access Point
  // WiFi.softAP(ssid, password);
  // Serial.println("Connecting to ESP32-CAM...");

  tft.init();
  tft.fillScreen(TFT_BLACK);  // Clear screen
  mySpi.begin(XPT2046_CLK, XPT2046_MISO, XPT2046_MOSI, XPT2046_CS);
  ts.begin(mySpi);
  ts.setRotation(1);
  

  tft.setRotation(1);
  tft.setTextColor(TFT_WHITE,TFT_BLACK); 
  tft.fillScreen(TFT_BLACK);
  tft.invertDisplay(true); //original and aliexpress but not elecrows
  tft.setSwapBytes(true);
  tft.fillScreen(TFT_GREEN);
  delay(500);
  tft.fillScreen(TFT_BLACK);
  tft.setTextFont(4);
  tft.writecommand(ILI9341_GAMMASET); //Gamma curve selected for original one only but no aliexpress or elecrow.
  tft.writedata(2);
  
  // tft.writecommand(ILI9341_GAMMASET); //Gamma curve selected
  tft.writedata(1);
  // analogWrite(21,64);

  TJpgDec.setJpgScale(1);
  delay(100);
  TJpgDec.setCallback(tft_output);
  int selX = 0, selY = 0;
  loadSelection(selX, selY);
  waitForSelection(selX, selY);
  snprintf(stream_url, sizeof(stream_url), "%s%d%d.mjpg", base_url, selX, selY);
  snprintf(touch_url, sizeof(touch_url), "%s%d%d", base_touch_url, selX, selY);
  Serial.println(stream_url);
  tft.println(stream_url);
  delay(2000);
  
  // Start the image stream
  // startStream();
}



void loop() {
   if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    
    // Start the HTTP connection to the ESP32-CAM stream
    http.begin(stream_url);
    int httpCode = http.GET();

    if (httpCode == HTTP_CODE_OK) {
      WiFiClient * stream = http.getStreamPtr();
      bool in_image = false;
      size_t content_length = 0;
      uint8_t *imageBuffer = nullptr;

      while (stream->connected()) {
      	checkTouch();
        if (stream->available()) {
          String line = stream->readStringUntil('\n');

          // Check for boundary marker
          if (line.startsWith("--")) {
            in_image = false;
            if (imageBuffer) {
              // Display the received image on the TFT
              drawJpeg(imageBuffer, content_length);
              free(imageBuffer);
              imageBuffer = nullptr;
            }
            content_length = 0;  // Reset the content length for the next image
          }

          // Check if the line is the content length header
          if (line.startsWith("Content-Length: ")) {
            content_length = line.substring(15).toInt();  // Use 16 when ends with a semi-colon
            Serial.printf("Content-Length: %d\n", content_length);
            imageBuffer = (uint8_t *)malloc(content_length);  // Allocate memory for the image
            in_image = true;  // Indicate that the image is coming
          }

          // If we're in the image data, read it into the buffer
          if (in_image && imageBuffer) {
            size_t remaining = content_length;
            size_t bytes_read = 0;

            while (remaining > 0 && stream->available()) {
              bytes_read += stream->readBytes(imageBuffer + bytes_read, remaining);
              remaining = content_length - bytes_read;
            }

            if (remaining == 0) {
              //Serial.println("Image received!");
              in_image = false;  // Image is fully received
            }
          }
        }
      }
    } else {
      Serial.printf("HTTP GET failed, error: %d\n", httpCode);
    }

    http.end(); // Close the HTTP connection
  }

  // delay(5000); // Adjust the delay as necessary for the next request
  delay(20);
}

