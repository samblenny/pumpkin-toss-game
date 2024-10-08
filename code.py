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
# |  D9         |  IRQ     |            |
# |  D10        |  CS      |            |
# |  TFT_CS     |          |  CS        |
# |  TFT_DC     |          |  DC        |
#
# Related Documentation:
# - https://learn.adafruit.com/adafruit-esp32-s3-tft-feather
# - https://learn.adafruit.com/adafruit-1-14-240x135-color-tft-breakout
# - https://learn.adafruit.com/adafruit-usb-host-featherwing-with-max3421e
# - https://docs.circuitpython.org/en/latest/shared-bindings/displayio/
# - https://docs.circuitpython.org/projects/display_text/en/latest/api.html
# - https://learn.adafruit.com/circuitpython-display_text-library?view=all
#
from board import D9, D10, SPI, TFT_CS, TFT_DC
from digitalio import DigitalInOut, Direction
from displayio import Bitmap, Group, Palette, TileGrid, release_displays
from fourwire import FourWire
import gc
from max3421e import Max3421E
from micropython import const
from supervisor import ticks_ms
from usb.core import USBError
from terminalio import FONT
from time import sleep

from adafruit_display_text import bitmap_label
import adafruit_imageload
from adafruit_st7789 import ST7789
from catapult import Catapult
from gamepad import (
    XInputGamepad, UP, DOWN, LEFT, RIGHT, START, SELECT, A, B, X, Y)
from skeletons import Skeletons
from statemachine import StateMachine


def handle_input(machine, prev, buttons, repeat):
    # Respond to gamepad button state change events.
    #
    # This function translates from the packed bitfield of gamepad button
    # states into the state machine's input event constants. If you wanted to
    # remap the gamepad buttons, or convert this program to use a different
    # type of gamepad (or keyboard, or mouse, etc), this function would be a
    # great place to start. If you want to change how the input device works
    # here, you'll probably also need to make some matching changes in main().
    #
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
    #
    # The CircuitPython ticks counter rolls over at 2**29, so this uses a bit
    # mask of (2**29)-1 = 0x3fffffff for the subtraction. If you want to learn
    # more about why doing it this way gives the correct result even when the
    # interval spans a rollover, try reading about "modular arithmetic",
    # "integer overflow", and "two's complement" arithmetic.
    #
    MASK = const(0x3fffffff)
    return (now - prev) & MASK


def main():
    # This function has initialization code and the main event loop. Under
    # normal circumstances, this function does not return.

    # The Feather TFT defaults to using the built-in display for a console.
    # So, first, release the default display so we can re-initialize it below.
    release_displays()
    gc.collect()

    # Initialize SPI bus which gets shared by ST7783 (TFT) and Max3421E (USB)
    spi = SPI()

    # Initialize ST7789 display with native display size of 240x135px.
    # IMPORTANT: Note how auto_refresh is set to false. This gives the state
    # machine and event loop code (see below) more direct control over when the
    # display refreshes. The point is to minimize SPI bus contention between
    # the display and the USB host chip, and to hopefully reduce tearing.
    #
    TFT_W = const(240)
    TFT_H = const(135)
    bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS)
    display = ST7789(bus, rotation=270, width=TFT_W, height=TFT_H, rowstart=40,
        colstart=53, auto_refresh=False)
    gc.collect()

    # Load PNG images and put them into TileGrid objects:
    # This is is the most memory intensive thing in the whole program. Doing
    # these large heap allocations early, then keeping the objects around for
    # the the length of the program, helps to avoid memory fragmentation.
    #
    gc.collect()
    # Background image with moon, trees, hill, and grass
    (bmp0, pal0) = adafruit_imageload.load(
        "pumpkin-toss-bkgnd.png", bitmap=Bitmap, palette=Palette)
    bkgnd = TileGrid(bmp0, pixel_shader=pal0)
    gc.collect()
    # Title screen overlay
    gc.collect()
    (bmp1, pal1) = adafruit_imageload.load(
            "pumpkin-toss-title.png", bitmap=Bitmap, palette=Palette)
    x = ((TFT_W // 2) - bmp1.width) // 2
    y = ((TFT_H // 2) - bmp1.height) // 2
    title_screen = TileGrid(bmp1, pixel_shader=pal1, x=x, y=y)
    # Shared spritesheet for catapult, pumpkin and skeleton animation cycles
    (bmp2, pal2) = adafruit_imageload.load(
        "pumpkin-toss-sprites.png", bitmap=Bitmap, palette=Palette)
    gc.collect()
    # Mark background color (black) as transparent
    pal2.make_transparent(0)

    # Prepare instances of the Catapult and Skeletons classes using the shared
    # spritesheet. These objects manage the details of setting TileGrid tiles
    # to draw animation cycles for sprites. The main reasons for these classes
    # are:
    # 1. Have a dedicated spot for the lists of tile numbers that define each
    #    frame of the various animation cycles
    # 2. Export functions and constants that the state machine can use to
    #    control animations at a higher level of abstraction (without having to
    #    clutter the state machine code with tile numbers from the spritesheet)
    # The x,y coordinates come from my bkgnd-with-grid.jpeg reference image.
    #
    cat = Catapult(bmp2, pal2, x=0, y=25, splat_y=57, chg_x=0, chg_y=8)
    skels = Skeletons(bmp2, pal2, x0=54, x1=116, y=44)

    # Make a text label for status messages
    status = bitmap_label.Label(FONT, text="", color=0xFF8000)
    status.x = 8  # NOTE: these are 1x coordinates! (sprites use 2x)
    status.y = 8  # NOTE: these are 1x coordinates! (sprites use 2x)

    # Arrange all the TileGrids and sub-groups into the root display group. The
    # sprites and background use 2x scaling (grp2), but the status line goes in
    # a 1x scaled group (grp1) because the built-in font looks huge at 2x.
    #
    grp1 = Group(scale=1)
    grp2 = Group(scale=2)
    grp2.append(bkgnd)
    grp2.append(skels.group())
    grp2.append(cat.group())
    grp2.append(title_screen)
    grp1.append(grp2)
    grp1.append(status)
    display.root_group = grp1
    display.refresh()

    # This initializes the state machine object, giving it references to the
    # sprite manager objects (Catapult and Skeletons) and status text label
    # object. The point of structuring the code this way is to have the state
    # machine be responsible for higher level timing and sprite behavior, while
    # the sprite managers take care of low-level details about TileGrid
    # changes. There's also some subtle memory allocation and data flow stuff
    # going on here, with the goal of keeping display updates smooth, at a
    # steady frame rate:
    #
    # 1. The sprite manager objects (cat and skels) contain references to
    #    large bitmaps which were loaded above from PNG files. Allocating
    #    these objects early and keeping references to them alive for the whole
    #    length of the program helps to avoid memory fragmentation, flash
    #    access, and pressure on the garbage collector. This should reduce
    #    timing jitter due to memory allocations and garbage collection.
    #
    # 2. The state machine causes the sprite manager objects to update TileGrid
    #    tile numbers, but calls to displayio.Display.refresh() only happen
    #    in the event loop, here in the main() function (remember the display
    #    was initialized with auto_refresh=false). This allows several tile
    #    updates for different sprites to happen together in the same animation
    #    frame, with hopefully just one display refresh per frame.
    #
    machine = StateMachine(grp2, cat, skels, title_screen, status)

    # Initialize MAX3421E USB host chip which is needed by usb.core to make
    # gamepad input work.
    print("Initializing USB host port...")
    gc.collect()
    usbHost = Max3421E(spi, chip_select=D10, irq=D9)
    gc.collect()
    sleep(0.1)

    # Initialize gamepad manager object (see gamepad.py)
    gp = XInputGamepad()

    # Gamepad status update strings for debug prints on the serial console and
    # display status line
    GP_FIND  = 'Finding USB gamepad'
    GP_READY = 'gamepad ready'
    GP_ERR1  = 'USB ERR1: bug in code.py?'
    GP_ERR2  = 'USB ERR2: gamepad unplugged?'

    # Cache frequently used callables to save time on dictionary name lookups
    # (this is a standard MicroPython performance boosting trick)
    _collect = gc.collect
    _elapsed = elapsed_ms
    _ms = ticks_ms
    _refresh = display.refresh

    # MAIN EVENT LOOP
    # This sets up a loop to run the following sequence over and over:
    #
    #  1. Attempt to poll a USB gamepad for button press inputs
    #
    #  2. Check for gamepad input events, and if needed, call the appropriate
    #     state machine input event handler
    #
    #  3. Call the state machine's tick() function to update animations and
    #     other timer-controlled state
    #
    #  4. If requested by the state machine, refresh the display
    #

    # Initialize timers for gamepad button hold detection.
    DELAY_MS  = const(133)  # Gamepad button hold delay before repeat (ms)
    REPEAT_MS = const(133)  # Gamepad button interval between repeats (ms)
    prev_ms = _ms()
    hold_tmr = 0
    repeat_tmr = 0
    # OUTER LOOP: try to connect to a USB gamepad.
    print(GP_FIND)
    status.text = GP_FIND
    _refresh()
    while True:
        _collect()
        # Begin by updating the display, even if gamepad is not connected
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
                status.text = ""  # clear the "Finding USB gamepad" status text
                _refresh()
                print(gp.device_info_str())
                connected = True
                prev_btn = 0
                hold_tmr = 0
                repeat_tmr = 0
                # INNER LOOP: gamepad is connected, so start polling buttons
                #
                # IMPORTANT: gp.poll() here is a generator that polls the
                # gamepad buttons at the start of each iteration through this
                # loop. Doing it this way avoids many memory allocations that
                # would be required to poll using a regular class method call.
                # The point of this approach is to get a better frame rate with
                # less of latency and jitter.
                #
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
                    #
                    # --- UPDATE ANIMATIONS & DISPLAY --------------------------
                    # This part is short but very important. The call to
                    # .tick() below lets the state machine update the animation
                    # cycles for sprites and do whatever other timer-based
                    # things need to be done. You could implement this in a
                    # different way using async, but I prefer it this way. The
                    # advantage of this approach is you can see how the gamepad
                    # polling and state machine updates take turns.
                    #
                    need_refresh = machine.tick(interval)
                    if need_refresh:
                        _refresh()
                        # Doing garbage collection after every refresh makes
                        # the loop run slower. But, it seems to reduce jitter,
                        # making for a smoother frame rate. It's too close to
                        # make an easy call, but this method seems to look
                        # subjectively a little better than other ways I tried.
                        _collect()
                    # ---------------------------------------------------------
                    #
                    # [END OF INNER LOOP]

                # Making it here means gp.poll() decided to end the loop with a
                # `return`, which is possible but not normal (see gamepad.py).
                print(GP_ERR1)
                print(GP_FIND)
                status.text = GP_ERR1
                _refresh()
            else:
                # Making it here means no gamepad is connected, and when
                # gp.find_and_configure() looked, it did not find one. This
                # normal and often happens at boot time because it takes a
                # while for all the USB stuff to initialize.
                #
                # Since there is no gamepad yet, wait a bit, then try again.
                #
                sleep(0.1)
        except USBError as e:
            # Making it here means there was a USBError exception during a call
            # to gp.find_and_configure() or gp.poll().
            #
            # This is normal when someone unplugs the gamepad. When that
            # happens, it's usually possible to reconnect without resetting
            # CircuitPython. But, sometimes, more serious and mysterious
            # USBError exceptions happen and usb.core gets confused. In that
            # case, further calls to find_and_configure() don't work until
            # after resetting the board.
            #
            # So, hope for the best, log the error, and stay in the outer loop
            # so it can attempt to find a gamepad.
            #
            print(GP_ERR2)
            print(GP_FIND)
            status.text = GP_ERR2
            _refresh()


main()
