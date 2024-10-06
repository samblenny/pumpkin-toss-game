# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
##
from micropython import const

from catapult import Catapult


class StateMachine:

    # Animation frame duration in ms for target frame rate
    _FRAME_MS = const(33)

    # Maximum timer time in ms = (2**30) - 1
    _MAX_MS = const(1073741823)

    # Button Press Constants (public)
    # CAUTION: These values must match column indexes of StateMachine.TABLE
    A_DN   = const(0)
    A_HOLD = const(1)
    A_UP   = const(2)
    SELECT = const(3)
    START  = const(4)

    # States (private)
    # CAUTION: These values must match row indexes of StateMachine.TABLE
    _TITLE  = const(0)
    _READY  = const(1)
    _CHARGE = const(2)
    _TOSS   = const(3)
    _PAUSE  = const(4)

    # Lookup table for resolving state constants to names
    _STATE_NAMES = {
        _TITLE:   "Title",
        _READY:   "Ready",
        _CHARGE:  "Charge",
        _TOSS:    "Toss",
        _PAUSE:   "Pause",
    }

    # Actions that are not state transitions (private)
    _NOP    = const(10)
    _PLAY   = const(11)
    _LOAD   = const(12)
    _RESUME = const(13)

    # LookUp Table (private) of actions (including NOP and state transitions)
    # for possible button press events in each of the possible states. NOP is
    # short for "No OPeration", and it means to do nothing.
    _TABLE = (
        # A_DN,    A_HOLD,  A_UP,  SELECT, START      State
        (_NOP,    _NOP,    _NOP,  _NOP,    _PLAY  ),  # title (start screen)
        (_CHARGE, _NOP,    _NOP,  _PAUSE,  _NOP   ),  # ready (pumpkin loaded)
        (_NOP,    _CHARGE, _TOSS, _PAUSE,  _NOP   ),  # charge (charging launcher)
        (_NOP,    _NOP,    _NOP,  _PAUSE,  _NOP   ),  # toss (pumpkin toss animation)
        (_NOP,    _NOP,    _NOP,  _RESUME, _RESUME),  # pause
    )

    # Maximum catapult launch power (private)
    _CHARGE_MAX = const(5)

    # Pumpkin flight out-of-basket initial position (_PX, _PY)
    _PX = const(4)
    _PY = const(1)

    # Pumpkin flight initial velocity (px/ms) when catapult is 100% charged.
    # Horizontal velocity is _PU. Vertical velocity is _PV.
    _PV = 750 / 1000
    _PU = 1600 / 1000

    # Pumpkin acceleration due to gravity (px/ms)
    _PG = 10 / 1000

    def __init__(self, catapult, skeletons):
        # Initialize state machine, saving catapult and skeleton references
        self.catapult = catapult
        self.skeletons = skeletons
        self.prev_state = None
        self.load_pumpkin()
        self.state = _TITLE
        self.frame_ms = 0
        self.need_repaint = True

    def load_pumpkin(self):
        # Reset state for firing a pumpkin
        self.timer = 0
        self.charge = Catapult.CHARGE_ZERO
        self.pumpkin_xyvu = (_PX, _PY, self._PV, self._PU)
        self.catapult.set_catapult(Catapult.LOAD)
        self.catapult.set_charge(Catapult.CHARGE_ZERO)
        self.catapult.set_pumpkin(Catapult.HIDE, _PX, _PY)
        self.state = _READY

    def paint(self):
        # Repaint the scene
        s = self._STATE_NAMES[self.state]
        t = self.timer
        c = self.charge
        if self.state == _CHARGE:
            print("charge:", c)
        else:
            print(f"{s}: timer: {t}, charge: {c}")

    def tick(self, elapsed_ms):
        # Update animations and timer-based state transitions
        # Returns:
        # - True: caller should refresh the displayio display
        # - False: display does not need to be refreshed
        #
        if self.state == _PAUSE:
            # Do not update animations when paused
            return False

        t0 = self.timer
        t1 = min(_MAX_MS, t0 + elapsed_ms)
        self.timer = t1

        # Rate limit updates to match target frame length in ms
        frame_ms = self.frame_ms + elapsed_ms
        if frame_ms < _FRAME_MS:
            self.frame_ms = frame_ms
            return False   # CAUTION: this returns early, skipping code below!
        else:
            self.frame_ms = frame_ms % _FRAME_MS

        # Update pumpkin flight animation
        _set_cat = self.catapult.set_catapult
        _set_charge = self.catapult.set_charge
        _set_pumpkin = self.catapult.set_pumpkin
        if self.state == _TOSS:
            self.need_repaint = True
            (x, y, v, u) = self.pumpkin_xyvu
            if t1 <= _FRAME_MS * 1:
                _set_cat(Catapult.LOAD)
            elif t1 <= _FRAME_MS * 2:
                _set_cat(Catapult.TOSS1)
            elif t1 <= _FRAME_MS * 3:
                _set_cat(Catapult.TOSS2)
            elif t1 <= _FRAME_MS * 4:
                _set_cat(Catapult.TOSS3)
                _set_pumpkin(Catapult.FLY, x, y)
            elif (t1 > 3000) or (y >= self.catapult.splat_y):
                print("SPLAT!")
                print("TODO: compute collision and trigger splat cycle")
                self.load_pumpkin()
            else:
                # Pumpkin in flight: update position
                x += u * elapsed_ms
                y -= v * elapsed_ms
                # ajust vertical velocity for acceleration due to gravity
                v -= self._PG * elapsed_ms
                # adjust horizontal velocity for acceleration due to drag
                # (this is not physically realistic, I just tuned it for feel)
                u = max(0.2 * self._PU, u - (((u ** 2) * 0.01) * elapsed_ms))
                _set_pumpkin(Catapult.FLY, x, y)
                self.pumpkin_xyvu = (x, y, v, u)

        # Update screen; returns True if caller should refresh hardware display
        if self.need_repaint:
            self.paint()
            self.need_repaint = False
            return True
        else:
            return False

    def handleGamepad(self, button):
        # Handle a button press event
        # args:
        # - button: one of the button constants

        # Check lookup table for the action code for this button event
        if (button < 0) or (button > START):
            print("Button value out of range:", button)
            return

        # Look up action code as a function of button event and current state
        a = self._TABLE[self.state][button]

        # Handle the action code
        if a == _NOP:
            pass
        elif a == _PLAY:
            self.load_pumpkin()
            self.need_repaint = True
        elif a == _CHARGE:
            if self.state == _READY:
                self.state = _CHARGE
            self.charge = min(Catapult.CHARGE_MAX, self.charge + 1)
            self.catapult.set_charge(self.charge)
            self.need_repaint = True
        elif a == _TOSS:
            (x, y, v, u) = self.pumpkin_xyvu
            power_percent = self.charge / Catapult.CHARGE_MAX
            v = self._PV * (0.5 * (1 + power_percent))
            u = self._PU * power_percent
            self.pumpkin_xyvu = (x, y, v, u)
            self.catapult.set_charge(Catapult.CHARGE_ZERO)
            self.state = _TOSS
            self.timer = 0
            self.need_repaint = True
        elif a == _PAUSE:
            print("PAUSED")
            self.prev_state = self.state
            self.state = _PAUSE
        elif a == _RESUME:
            print("RESUMING")
            self.state = self.prev_state or _READY
            self.need_repaint = True
