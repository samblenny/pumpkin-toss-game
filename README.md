<!-- SPDX-License-Identifier: MIT -->
<!-- SPDX-FileCopyrightText: Copyright 2024 Sam Blenny -->
# Pumpkin Toss Game

**WORK IN PROGRESS (ALPHA)**


## Hardware


### Parts

- Adafruit ESP32-S3 TFT Feather - 4MB Flash, 2MB PSRAM
  ([product page](https://www.adafruit.com/product/5483),
  [learn guide](https://learn.adafruit.com/adafruit-esp32-s3-tft-feather))

- Adafruit USB Host FeatherWing with MAX3421E
  ([product page](https://www.adafruit.com/product/5858),
  [learn guide](https://learn.adafruit.com/adafruit-usb-host-featherwing-with-max3421e))

- Adafruit FeatherWing Doubler
  ([product page](https://www.adafruit.com/product/2890))

- 8BitDo SN30 Pro USB gamepad
  ([product page](https://www.8bitdo.com/sn30-pro-usb-gamepad/))


### Pinouts

| TFT feather | USB Host | ST7789 TFT |
| ----------- | -------- | ---------- |
|  SCK        |  SCK     |            |
|  MOSI       |  MOSI    |            |
|  MISO       |  MISO    |            |
|  D9         |  IRQ     |            |
|  D10        |  CS      |            |
|  TFT_CS     |          |  CS        |
|  TFT_DC     |          |  DC        |


### Tools and Consumables

You will need soldering tools and solder.


### Soldering the Headers

The TFT Feather, USB Host FeatherWing and the Doubler all come in kit form, so
you will need to solder the headers.

If you are unfamiliar with soldering headers, you might want to read:

- [Adafruit Guide To Excellent Soldering](https://learn.adafruit.com/adafruit-guide-excellent-soldering/tools)

- [How To Solder Headers](https://learn.adafruit.com/how-to-solder-headers)


## Updating CircuitPython

**NOTE: To update CircuitPython on the ESP32-S3 TFT Feather with 2MB PSRAM and
4MB Flash, you need to use the .BIN file (combination bootloader and
CircuitPython core)**

1. Download the CircuitPython 9.1.4 **.BIN** file from the
   [Feather ESP32-S3 TFT PSRAM](https://circuitpython.org/board/adafruit_feather_esp32s3_tft/)
   page on circuitpython.org

2. Follow the instructions in the
   [Web Serial ESPTool](https://learn.adafruit.com/circuitpython-with-esp32-quick-start/web-serial-esptool)
   section of the "CircuitPython on ESP32 Quick Start" learn guide to update
   your board: first erase the flash, then program the .BIN file.


## Installing CircuitPython Code

To copy the project bundle files to your CIRCUITPY drive:

1. Download the project bundle .zip file using the button on the Playground
   guide or the attachment download link on the GitHub repo Releases page.

2. Expand the zip file by opening it, or use `unzip` in a Terminal. The zip
   archive should expand to a folder. When you open the folder, it should
   contain a `README.txt` file and a `CircuitPython 9.x` folder.

3. Open the CircuitPython 9.x folder and copy all of its contents to your
   CIRCUITPY drive.

To learn more about copying libraries to your CIRCUITPY drive, check out the
[CircuitPython Libraries](https://learn.adafruit.com/welcome-to-circuitpython/circuitpython-libraries)
section of the
[Welcome to CircuitPython!](https://learn.adafruit.com/welcome-to-circuitpython)
learn guide.


## Sprites and Background

I use these zoomed in and annotated views of my background and spritesheet to
get coordinates and sprite numbers to put in my code.


### Background

![lofi pixel art background with hill, trees, moon, catapult, and skeletons](bkgnd-with-grid.jpeg)


## Spritesheet

![lofi pixel art sprites for pumpkin, catapult, and skeletons](sprites-with-grid.jpeg)


## Pumpkin Flight Physics

These are some notes from my lazy attempt at modeling vaguely accurate pumpkin
ballistics. To read about doing this properly, some potentially useful search
terms include: rigid body dynamics, projectile motion, classical mechanics,
drag coefficient, drag equation, and ballistic flight.

The most readily useable references I found for calculating displacement as a
function of time and initial velocity were from NASA's Glenn Research Center:
- [Ballistic Flight Calculator](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/fltcalc/)
- [Ballistic Flight Equations](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ballistic-flight-equations/)
- [Flight Equations with Drag](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/flight-equations-with-drag/)

Apparently, a medium pie pumpkin could plausibly measure 20 cm in diameter with
a mass of 3 kg. So, I'll base my calculations on a standard "spherical" pumpkin
with these stats:

| Mass | Diameter | Cross-sectional Area | Drag Coefficient |
| ---- | -------- | -------------------- | ---------------- |
| 3 kg | 0.2 m    | 0.031 m^2            | 0.7              |
