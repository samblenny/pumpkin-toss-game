# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
##
from micropython import const


class StateMachine:

    # Animation frame duration in ms for target frame rate
    _FRAME_MS = const(64)

    # Button Press Constants (public)
    # CAUTION: These values must match column indexes of StateMachine.TABLE
    UP     = const(0)
    DOWN   = const(1)
    A_DN   = const(2)
    A_HOLD = const(3)
    A_UP   = const(4)
    START  = const(5)

    # States (private)
    # CAUTION: These values must match row indexes of StateMachine.TABLE
    _TITLE = const(0)
    _READY = const(1)
    _TOSS  = const(2)
    _SCORE = const(3)

    # Lookup table for resolving state constants to names
    _STATE_NAMES = {
        _TITLE:   "Title",
        _READY:   "Ready",
        _TOSS:    "Toss_",
        _SCORE:   "Score",
    }

    # Actions that are not state transitions (private)
    _NOP    = const(10)
    _PLAY   = const(11)
    _LOAD   = const(12)
    _AIMUP  = const(13)
    _AIMDN  = const(14)
    _CHARGE = const(15)

    # LookUp Table (private) of actions (including NOP and state transitions)
    # for possible button press events in each of the possible states. NOP is
    # short for "No OPeration", and it means to do nothing.
    _TABLE = (
        # UP      DOWN   A_DN,    A_HOLD,  A_UP,  START    State
        (_NOP,    _NOP,  _NOP,    _NOP,    _NOP,  _PLAY),  # title (start screen)
        (_AIMUP, _AIMDN, _CHARGE, _CHARGE, _TOSS, _NOP ),  # ready (pumpkin loaded)
        (_NOP,    _NOP,  _NOP,    _NOP,    _NOP,  _NOP ),  # toss (pumpkin toss animation)
        (_NOP,    _NOP,  _NOP,    _NOP,    _NOP,  _PLAY),  # score (end screen)
    )

    # Limits on launch angle and charge power (private)
    _ANGLE_MIN  = const(0)
    _ANGLE_INIT = const(45)
    _ANGLE_MAX  = const(90)
    _CHARGE_MAX = const(30)

    def __init__(self, pumpkins=10):
        self.pumpkins_init = pumpkins
        self.new_game(state=_TITLE)
        self.frame_ms = 0
        self.need_repaint = True

    def new_game(self, state=_READY):
        self.pumpkins = self.pumpkins_init
        self.timer = 0
        self.charge = 0
        self.angle = _ANGLE_INIT
        self.state = state

    def load_pumpkin(self):
        self.pumpkins = max(0, self.pumpkins - 1)
        self.timer = 0
        self.charge = 0
        self.state = _READY

    def paint(self):
        # TODO repaint the scene
        s = self._STATE_NAMES[self.state]
        a = self.angle
        t = self.timer
        c = self.charge
        p = self.pumpkins
        print(f"{s}: pumpkins: {p}, angle: {a}, timer: {t}, charge: {c}")

    def tick(self, elapsed_ms):
        # Update animations and timer-based state transitions
        # Returns:
        # - True: caller should refresh the displayio display
        # - False: display does not need to be refreshed
        t0 = self.timer
        t1 = max(0, t0 - elapsed_ms)
        self.timer = t1

        # Rate limit updates to match target frame length in ms
        frame_ms = self.frame_ms + elapsed_ms
        if(frame_ms < _FRAME_MS):
            self.frame_ms = frame_ms
            return False  # NOTE: this returns early!
        else:
            self.frame_ms = frame_ms % _FRAME_MS

        # Update pumpkin flight animation
        if self.state == _TOSS:
            if t1 <= 0:
                self.need_repaint = True
                print("SPLAT!")
                # TODO: compute collision and adjust score
                print("TODO: compute collision and adjust score")
                # Update pumpkin count
                if self.pumpkins > 0:
                    self.load_pumpkin()
                else:
                    self.state = _SCORE
                    # TODO: game over screen
                    print("TODO: game over screen")
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
        if button < UP or button > START:
            print("Button value out of range:", button)
            return
        a = self._TABLE[self.state][button]

        # Handle the action code
        if a == _NOP:
            pass
        elif a == _PLAY:
            self.new_game(state=_READY)
            self.need_repaint = True
        elif a == _AIMUP:
            self.angle = min(_ANGLE_MAX, self.angle + 5)
            self.need_repaint = True
        elif a == _AIMDN:
            self.angle = max(_ANGLE_MIN, self.angle - 5)
            self.need_repaint = True
        elif a == _CHARGE:
            self.charge = min(_CHARGE_MAX, self.charge + 1)
            self.need_repaint = True
        elif a == _TOSS:
            self.state = _TOSS
            self.timer = 1500
            self.need_repaint = True
