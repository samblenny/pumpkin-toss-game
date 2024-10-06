# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
from displayio import Group, TileGrid
import gc
from micropython import const


class Catapult:
    # This class manages animation cycles for the catapult and pumpkin.
    # The spritesheet tile numbers used here come from the annotations in
    # sprites-with-grid.jpeg. The x,y coordinates for screen positions come
    # from bkgnd-with-grid.jpeg.

    # Names of catapult animation cycle frames (public, for state machine)
    # CAUTION: these must match row indexes of _C_TILES
    LOAD  = const(0)
    TOSS1 = const(1)
    TOSS2 = const(2)
    TOSS3 = const(3)

    # Names of pumpkin animation cycle frames (public, for state machine)
    # CAUTION: these must match indexes of _P_TILES
    HIDE   = const(0)
    FLY    = const(1)
    SPLAT1 = const(2)
    SPLAT2 = const(3)
    SPLAT3 = const(4)

    # Tile tuples for the catapult sprite. Catapult sprite is 16x16 px. Tiles
    # in the spritesheet are 8x8. So, each frame of the catapult animation
    # cycle uses 4 tiles: (top-left, top-right, bottom-left, bottom-right).
    _C_TILES = (
        (12, 13, 22, 23),  # LOAD:  stopped, arm at 30°, pumpkin in basket
        (14, 15, 24, 25),  # TOSS1: moving, arm at 45°, pumpkin in basket
        (16, 17, 26, 27),  # TOSS2: moving, arm at 60°, pumpkin in basket
        (18, 19, 28, 29),  # TOSS3: stopped, arm at 60°, basket empty
    )

    # Tiles for the pumpkin sprite (in flight and splatted). Pumpkin sprite is
    # 8x8. So, each frame of the pumpkin flight-splat animation cycle uses 1
    # tile of the spritesheet.
    _P_TILES = (
        0,   # HIDE:   in-flight sprite is hidden (pumpkin is in the catapult)
        10,  # FLY:    pumpkin is flying (catapult basket empty)
        11,  # SPLAT1: partial splat at 3/4 height
        20,  # SPLAT2: partial splat at 1/2 height
        21,  # SPLAT3: full splat
    )

    # Catapult charge-up power limits (public)
    CHARGE_ZERO = const(0)   # hide the charge-up bar
    CHARGE_MAX  = const(20)  # 100% power

    # Tiles for the catapult charge-up indicator bar. The indicator bar goes
    # from 0% to 100% in 20 increments (bars) of 5% each. The charge bar is
    # seven 8x8 tiles wide. The leftmost and rightmost tiles are the ends of
    # the rounded rectangle. The 5 inner 8x8 tiles can each represent 4 bars of
    # charge (1 bar == 2 px).
    _CHG_TILES = (
        (0, 0, 0, 0, 0, 0, 0),  # CHARGE_ZERO: transparent (hide charge bar)
        (1, 3, 2, 2, 2, 2, 7),  #  1/20
        (1, 4, 2, 2, 2, 2, 7),  #  2/20
        (1, 5, 2, 2, 2, 2, 7),  #  3/20
        (1, 6, 2, 2, 2, 2, 7),  #  4/20
        (1, 6, 3, 2, 2, 2, 7),  #  5/20
        (1, 6, 4, 2, 2, 2, 7),  #  6/20
        (1, 6, 5, 2, 2, 2, 7),  #  7/20
        (1, 6, 6, 2, 2, 2, 7),  #  8/20
        (1, 6, 6, 3, 2, 2, 7),  #  9/20
        (1, 6, 6, 4, 2, 2, 7),  # 10/20
        (1, 6, 6, 5, 2, 2, 7),  # 11/20
        (1, 6, 6, 6, 2, 2, 7),  # 12/20
        (1, 6, 6, 6, 3, 2, 7),  # 13/20
        (1, 6, 6, 6, 4, 2, 7),  # 14/20
        (1, 6, 6, 6, 5, 2, 7),  # 15/20
        (1, 6, 6, 6, 6, 2, 7),  # 16/20
        (1, 6, 6, 6, 6, 3, 7),  # 17/20
        (1, 6, 6, 6, 6, 4, 7),  # 18/20
        (1, 6, 6, 6, 6, 5, 7),  # 19/20
        (1, 6, 6, 6, 6, 6, 7),  # 20/20 = CHARGE_MAX
    )

    def __init__(self, bitmap, palette, x, y, splat_y, chg_x, chg_y):
        # This sets up catapult and pumpkin sprites.
        # Args:
        # - bitmap, palette: Shared spritesheet from adafruit_imageload
        # - x, y:            Coordinate of top left corner of catapult sprite
        # - splat_y:         Ground height in pumpkin splat zone
        #
        # The spritesheet has 8x8 tiles. The pumpkin sprite is 8x8. The
        # catapult sprite is 16x16 (4 tiles per sprite/frame).
        #
        gc.collect()
        # Make catapult TileGrid
        tgc = TileGrid(
            bitmap, pixel_shader=palette, width=2, height=2,
            tile_width=8, tile_height=8, x=x, y=y)
        gc.collect()
        # Make catapult charge-up indicator TileGrid
        tgchg = TileGrid(
            bitmap, pixel_shader=palette, width=7, height=1,
            tile_width=8, tile_height=8, x=chg_x, y=chg_y)
        gc.collect()
        # Make pumpkin TileGrid
        tgp = TileGrid(
            bitmap, pixel_shader=palette, width=1, height=1,
            tile_width=8, tile_height=8, x=x, y=y)
        gc.collect()
        # Arrange TileGrids into a group
        grp = Group(scale=1)
        grp.append(tgc)
        grp.append(tgchg)
        grp.append(tgp)
        # Save arguments and object references
        self.x = x
        self.y = y
        self.splat_y = y
        self.tgc = tgc
        self.tgchg = tgchg
        self.tgp = tgp
        self.grp = grp
        # Set sprite tiles for initial animation frame
        self.set_catapult(LOAD)
        self.set_charge(CHARGE_ZERO)
        self.set_pumpkin(HIDE, 0, 0)

    def group(self):
        # Return the displayio.Group object for catapult and pumpkin TileGrids
        return self.grp

    def set_charge(self, power):
        # Set catapult charge-up indicator bar
        if (CHARGE_ZERO <= power) and (power <= CHARGE_MAX):
            for (i, tile) in enumerate(self._CHG_TILES[power]):
                self.tgchg[i] = tile
        else:
            raise Exception(f"charge power out of range: {power}")

    def set_catapult(self, frame):
        # Set catapult sprite tiles for the specified animation cycle frame
        if (LOAD <= frame) and (frame <= TOSS3):
            (topL, topR, botL, botR) = self._C_TILES[frame]
            self.tgc[0] = topL
            self.tgc[1] = topR
            self.tgc[2] = botL
            self.tgc[3] = botR
        else:
            raise Exception(f"catapult frame out of range: {frame}")

    def set_pumpkin(self, frame, x, y):
        # Set pumpkin sprite tile and relative position for the specified
        # animation cycle frame. Pumpkin (x,y) is relative to catapult (x,y).
        if (HIDE <= frame) and (frame <= SPLAT3):
            self.tgp[0] = self._P_TILES[frame]
            self.tgp.x = self.x + round(x)  # x argument can be float
            self.tgp.y = self.y + round(y)  # y argument can be float
        else:
            raise Exception(f"pumpkin frame out of range: {frame}")
