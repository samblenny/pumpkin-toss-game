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

    def __init__(self, bitmap, palette, x, y, splat_y):
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
        # Make pumpkin TileGrid
        tgp = TileGrid(
            bitmap, pixel_shader=palette, width=1, height=1,
            tile_width=8, tile_height=8, x=x, y=y)
        gc.collect()
        # Arrange TileGrids into a group
        grp = Group(scale=1)
        grp.append(tgc)
        grp.append(tgp)
        # Save arguments and object references
        self.x = x
        self.y = y
        self.splat_y = y
        self.tgc = tgc
        self.tgp = tgp
        self.grp = grp
        # Set sprite tiles for catapult and pumpkin to initial animation frame
        self.set_catapult(LOAD)
        self.set_pumpkin(HIDE, 0, 0)

    def group(self):
        # Return the displayio.Group object for catapult and pumpkin TileGrids
        return self.grp

    def set_catapult(self, frame):
        # Set catapult sprite tiles for the specified animation cycle frame
        print(f"SET_CATAPULT({frame})")
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
