# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
##
from micropython import const

from catapult import Catapult


class StateMachine:

    # Animation frame duration in ms for target frame rate
    _FRAME_MS = const(64)

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
    _CHARGE_MAX = const(30)

    def __init__(self, catapult, skeletons):
        self.catapult = catapult
        self.skeletons = skeletons
        self.prev_state = None
        self.new_game(state=_TITLE)
        self.frame_ms = 0
        self.need_repaint = True

    def new_game(self, state=_READY):
        self.timer = 0
        self.charge = 0
        self.state = state

    def load_pumpkin(self):
        self.timer = 0
        self.charge = 0
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
        if self.state == _TOSS:
            self.need_repaint = True
            if t1 <= _FRAME_MS * 1:
                _set_cat(Catapult.LOAD)
            elif t1 <= _FRAME_MS * 2:
                _set_cat(Catapult.TOSS1)
            elif t1 <= _FRAME_MS * 3:
                _set_cat(Catapult.TOSS2)
            elif t1 <= _FRAME_MS * 4:
                _set_cat(Catapult.TOSS3)
            elif t1 > 2000:
                print("SPLAT!")
                print("TODO: compute collision and trigger splat cycle")
                _set_cat(Catapult.LOAD)
                self.state = _READY
            else:
                print(" flying", t1)

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
            self.new_game(state=_READY)
            self.need_repaint = True
        elif a == _CHARGE:
            if self.state == _READY:
                self.state = _CHARGE
            self.charge = min(_CHARGE_MAX, self.charge + 1)
            self.need_repaint = True
        elif a == _TOSS:
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
