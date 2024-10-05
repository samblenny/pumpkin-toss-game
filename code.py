# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# Hardware:
# - Adafruit ESP32-S3 TFT Feather - 4MB Flash, 2MB PSRAM (#5483)
# - Adafruit USB Host FeatherWing with MAX3421E (#5858)
# - 8BitDo SN30 Pro USB gamepad
#
# Pinouts:
# | TFT feather | USB Host | ST7789 TFT |
# | ----------- | -------- | ---------- |
# |  SCK        |  SCK     |            |
# |  MOSI       |  MOSI    |            |
# |  MISO       |  MISO    |            |
# |  SDA        |          |            |
# |  SCL        |          |            |
# |  D9         |  IRQ     |            |
# |  D10        |  CS      |            |
# |  D11        |          |            |
# |  TFT_CS     |          |  CS        |
# |  TFT_DC     |          |  DC        |
#
# Related Documentation:
# - https://learn.adafruit.com/adafruit-esp32-s3-tft-feather
# - https://learn.adafruit.com/adafruit-1-14-240x135-color-tft-breakout
# - https://learn.adafruit.com/adafruit-usb-host-featherwing-with-max3421e
#
from board import D9, D10, D11, I2C, SPI, TFT_CS, TFT_DC
from digitalio import DigitalInOut, Direction
from displayio import Bitmap, Group, Palette, TileGrid, release_displays
from fourwire import FourWire
import gc
from max3421e import Max3421E
from micropython import const
from supervisor import ticks_ms
from usb.core import USBError
from time import sleep

import adafruit_imageload
from adafruit_st7789 import ST7789
from catapult import Catapult
from gamepad import (
    XInputGamepad, UP, DOWN, LEFT, RIGHT, START, SELECT, A, B, X, Y)
from skeletons import Skeletons
from statemachine import StateMachine


def handle_input(machine, prev, buttons, repeat):
    # Respond to gamepad button state change events
    diff = prev ^  buttons
    mh = machine.handleGamepad
    #print(f"{buttons:016b}")

    if repeat:
        # Check for hold-time triggered repeating events
        if (buttons & A):
            mh(machine.A_HOLD)
    else:
        # Check for edge-triggered events
        if (diff & A) and (buttons & A):  # A pressed
            mh(machine.A_DN)
        elif (diff & A) and (not (buttons & A)):  # A released
            mh(machine.A_UP)
        elif (diff & SELECT) and (buttons == SELECT):  # SELECT pressed
            mh(machine.SELECT)
        elif (diff & START) and (buttons == START):  # START pressed
            mh(machine.START)


def elapsed_ms(prev, now):
    # Calculate elapsed ms between two timestamps from supervisor.ticks_ms().
    # The ticks counter rolls over at 2**29, and (2**29)-1 = 0x3fffffff
    MASK = const(0x3fffffff)
    return (now - prev) & MASK


def main():
    release_displays()
    gc.collect()
    spi = SPI()

    # Initialize ST7789 display with native display size of 240x135px.
    TFT_W = const(240)
    TFT_H = const(135)
    bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS)
    display = ST7789(bus, rotation=270, width=TFT_W, height=TFT_H, rowstart=40,
        colstart=53, auto_refresh=False)
    gc.collect()

    # Configure display's root group
    gc.collect()
    # Background image with moon, trees, hill, and grass
    (bmp, pal) = adafruit_imageload.load(
        "pumpkin-toss-bkgnd.png", bitmap=Bitmap, palette=Palette)
    bkgnd = TileGrid(bmp, pixel_shader=pal)
    gc.collect()
    # Load shared spritesheet for catapult, pumpkin and skeleton cycles
    (bmp, pal) = adafruit_imageload.load(
        "pumpkin-toss-sprites.png", bitmap=Bitmap, palette=Palette)
    # Mark background color (black) as transparent
    pal.make_transparent(0)
    # Prepare catapult and skeletons (they manage their own TileGrid Groups)
    cat = Catapult(bmp, pal, x=0, y=25, splat_y=57)
    skels = Skeletons(bmp, pal, x0=60, y0=46, x1=112, y1=40)
    # Arrange Groups
    grp = Group(scale=2)
    grp.append(bkgnd)
    grp.append(cat.group())
    grp.append(skels.group())
    display.root_group = grp
    display.refresh()

    # Start state machine with catapult and skeleton object references so it
    # can update the sprite animations as needed
    machine = StateMachine(cat, skels)

    # Initialize MAX3421E USB host chip which is needed by usb.core.
    print("Initializing USB host port...")
    gc.collect()
    usbHost = Max3421E(spi, chip_select=D10, irq=D9)
    gc.collect()
    sleep(0.1)

    # Gamepad status update strings
    GP_FIND   = 'Finding USB gamepad'
    GP_READY  = 'gamepad ready'
    GP_DISCON = 'gamepad disconnected'
    GP_ERR    = 'gamepad connection error'

    # Cache frequently used callables to save time on dictionary name lookups
    _collect = gc.collect
    _elapsed = elapsed_ms
    _ms = ticks_ms
    _refresh = display.refresh

    # MAIN EVENT LOOP
    # Establish and maintain a gamepad connection
    gp = XInputGamepad()
    print(GP_FIND)
    # OUTER LOOP: try to connect to a USB gamepad.
    # Start timers for gamepad button hold detection.
    DELAY_MS  = const(300)  # Gamepad button hold delay before repeat (ms)
    REPEAT_MS = const(300)  # Gamepad button interval between repeats (ms)
    prev_ms = _ms()
    hold_tmr = 0
    repeat_tmr = 0
    while True:
        _collect()
        now_ms = _ms()
        interval = _elapsed(prev_ms, now_ms)
        if interval >= 16:
            prev_ms = now_ms
            # Update animations and display if needed
            if machine.tick(interval):
                _refresh()
        try:
            # Attempt to connect to USB gamepad
            if gp.find_and_configure():
                print(gp.device_info_str())
                connected = True
                # INNER LOOP: poll gamepad for button events
                prev_btn = 0
                hold_tmr = 0
                repeat_tmr = 0
                for buttons in gp.poll():
                    # Update A-button timers
                    now_ms = _ms()
                    interval = _elapsed(prev_ms, now_ms)
                    prev_ms = now_ms
                    if buttons & A:
                        hold_tmr += interval
                        repeat_tmr += interval
                    else:
                        hold_tmr = 0
                        repeat_tmr = 0
                    # Handle hold-time triggered gamepad input events
                    if hold_tmr >= DELAY_MS:
                        if hold_tmr == repeat_tmr:
                            # First re-trigger event after initial delay
                            repeat_tmr -= DELAY_MS
                            handle_input(machine, prev_btn, buttons, True)
                        elif repeat_tmr >= REPEAT_MS:
                            # Another re-trigger event after repeat interval
                            repeat_tmr -= REPEAT_MS
                            handle_input(machine, prev_btn, buttons, True)
                    # Handle edge-triggered gamepad input events
                    if prev_btn != buttons:
                        handle_input(machine, prev_btn, buttons, False)
                    # Save button values
                    prev_btn = buttons
                    # UPDATE ANIMATIONS and refresh display if needed
                    need_refresh = machine.tick(interval)
                    if need_refresh:
                        _refresh()
                # If loop stopped, gamepad connection was lost
                print(GP_DISCON)
                print(GP_FIND)
            else:
                # No connection yet, so sleep briefly then try again
                sleep(0.1)
        except USBError as e:
            # This might mean gamepad was unplugged, or maybe some other
            # low-level USB thing happened which this driver does not yet
            # know how to deal with. So, log the error and keep going
            print(GP_ERR)
            print(GP_FIND)
            _setMsg(GP_FIND, top=False)
            _refresh()


main()
