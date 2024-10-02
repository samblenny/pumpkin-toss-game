# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# Gamepad driver for XInput compatible USB wired gamepad with MAX421E.
#
# The button names used here match the Nintendo SNES style button
# cluster layout, but the USB IDs and protocol match the Xbox 360 USB
# wired controller. This is meant to work with widely available USB
# wired xinput compatible gamepads for the retrogaming market. In
# particular, I tested this package using my 8BitDo SN30 Pro USB wired
# gamepad.
#
# CAUTION: If you try to use a USB adapter with a wireless xinput
# compatible gamepad, it probably won't work with this driver in its
# current form. In my testing, compared to wired gamepads, USB wireless
# adapters have extra delays and errors that require retries and
# low-level error handling. I haven't been able to get a USB wireless
# gamepad adapter working yet in CircuitPython yet.
#
from micropython import const
from struct import unpack
from time import sleep
from usb import core
from usb.core import USBError, USBTimeoutError


# Gamepad button bitmask constants
UP     = const(0x0001)  # dpad: Up
DOWN   = const(0x0002)  # dpad: Down
LEFT   = const(0x0004)  # dpad: Left
RIGHT  = const(0x0008)  # dpad: Right
START  = const(0x0010)
SELECT = const(0x0020)
L      = const(0x0100)  # Left shoulder button
R      = const(0x0200)  # Right shoulder button
B      = const(0x1000)  # button cluster: bottom button (Nintendo B, Xbox A)
A      = const(0x2000)  # button cluster: right button  (Nintendo A, Xbox B)
Y      = const(0x4000)  # button cluster: left button   (Nintendo Y, Xbox X)
X      = const(0x8000)  # button cluster: top button    (Nintendo X, Xbox Y)

class XInputGamepad:

    # Constants for USB device IO
    _INTERFACE  = const(0)
    _TIMEOUT_MS = const(100)
    _ENDPOINT   = const(0x81)

    def __init__(self):
        # Initialize buffer used in polling USB gamepad events
        self.buf64 = bytearray(64)
        # Variable to hold the gamepad's usb.core.Device object
        self.device = None

    def find_and_configure(self):
        # Connect to a USB wired Xbox 360 style gamepad (vid:pid=045e:028e)
        #
        # Returns: True = success, False = device not found or config failed
        # Exceptions: may raise usb.core.USBError or usb.core.USBTimeoutError
        #
        device = core.find(idVendor=0x045e, idProduct=0x028e)
        sleep(0.1)
        if device:
            self._configure(device)  # may raise usb.core.USBError
            return True              # end retry loop
        else:
            # No gamepad was found
            self.reset()
            return False

    def _configure(self, device):
        # Prepare USB gamepad for use (set configuration, drain buffer, etc)
        #
        # Exceptions: may raise usb.core.USBError or usb.core.USBTimeoutError
        #
        try:
            # Make sure CircuitPython core is not claiming the device
            if device.is_kernel_driver_active(_INTERFACE):
                device.detach_kernel_driver(_INTERFACE)
            # Make sure that configuration is set
            device.set_configuration()
        except USBError as e:
            self.reset()
            raise e
        # Initial reads may give old data, so drain gamepad's buffer. This
        # may raise an exception (with no string description nor errno!)
        # when buffer is already empty. If that happens, ignore it.
        try:
            sleep(0.1)
            for _ in range(8):
                __ = device.read(0x81, self.buf64, timeout=_TIMEOUT_MS)
        except USBTimeoutError:
            pass
        except USBError as e:
            self.reset()
            raise e
        # All good, so save a reference to the device object
        self.device = device

    def poll(self):
        # Generator to poll gamepad for button changes (ignore sticks/triggers)
        # Yields:
        #   buttons: Uint16 containing bitfield of individual button values
        # Exceptions: may raise usb.core.USBError or usb.core.USBTimeoutError
        #
        # This generator is meant to be used with a `for` loop. The point is to
        # allow for faster polling by reducing the Python VM overhead spent on
        # memory allocation, method calls, and dictionary lookups. To read more
        # about generators, see https://peps.python.org/pep-0255/
        #
        # Expected endpoint 0x81 report format:
        #  bytes 0,1:    prefix that doesn't change      [ignored]
        #  bytes 2,3:    button bitfield for dpad, ABXY, etc (uint16)
        #  byte  4:      L2 left trigger (analog uint8)  [ignored]
        #  byte  5:      R2 right trigger (analog uint8) [ignored]
        #  bytes 6,7:    LX left stick X axis (int16)    [ignored]
        #  bytes 8,9:    LY left stick Y axis (int16)    [ignored]
        #  bytes 10,11:  RX right stick X axis (int16)   [ignored]
        #  bytes 12,13:  RY right stick Y axis (int16)   [ignored]
        #  bytes 14..19: ???, but they don't change
        #
        if self.device is None:
            # Caller is trying to poll buttons when gamepad is not connected
            return
        # Caching frequently used objects saves time on dictionary name lookups
        _devread = self.device.read
        _buf = self.buf64
        _unpack = unpack
        # Generator loop (note how this uses yield instead of return)
        prev = 0
        while True:
            try:
                # Poll gamepad endpoint to get button and joystick status bytes
                n = _devread(_ENDPOINT, _buf, timeout=_TIMEOUT_MS)
                if n < 14:
                    # skip unexpected responses (too short to be a full report)
                    yield prev
                # Only bytes 2 and 3 are interesting (ignore sticks/triggers)
                (buttons,) = _unpack('<H', self.buf64[2:4])
                prev = buttons
                yield buttons
            except USBTimeoutError:
                pass
            except USBError as e:
                self.reset()
                raise e

    def device_info_str(self):
        # Return string describing gamepad device (or lack thereof)
        d = self.device
        if d is None:
            return "[Gamepad not connected]"
        (v, pi, pr, m) = (d.idVendor, d.idProduct, d.product, d.manufacturer)
        if (v is None) or (pi is None):
            # Sometimes the usb.core or Max3421E will return 0000:0000 for
            # reasons that I do not understand
            return "[bad vid:pid]"
        else:
            return "Connected: %04x:%04x prod='%s' mfg='%s'" % (v, pi, pr, m)

    def reset(self):
        # Reset USB device and gamepad button polling state
        self.device = None
