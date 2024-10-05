# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
from displayio import Group, TileGrid
import gc
from micropython import const


class Skeletons:
    # This class manages animation cycles for the skeletons.
    # The spritesheet tile numbers used here come from the annotations in
    # sprites-with-grid.jpeg. The x,y coordinates for screen positions come
    # from bkgnd-with-grid.jpeg.

    # Names of skeleton animation cycle frames (public, for state machine)
    # CAUTION: these must match indexes of _S_TILES
    HIDE   = const(0)
    RISE1  = const(1)
    RISE2  = const(2)
    RISE3  = const(3)
    RISE4  = const(4)
    RISE5  = const(5)
    STAND1 = const(6)
    STAND2 = const(7)
    STAND3 = const(8)
    STAND4 = const(9)

    # Tile tuples for the skeleton sprite. Catapult sprite is 8x16 px. Tiles
    # in the spritesheet are 8x8. So, each frame of the catapult animation
    # cycle uses 2 tiles: (top, bottom).
    _S_TILES = (
        (30, 40),  # HIDE:  not visible (below ground or whatever)
        (31, 41),  # RISE1: 1 px of skull and sword
        (32, 42),  # RISE2: 3 px of skull and sword
        (33, 43),  # RISE3: skull, arms, full sword
        (34, 44),  # RISE4: full torso
        (35, 45),  # RISE5: most of legs
        (36, 46),  # STAND1: both legs down, sword up, R arm up
        (37, 47),  # STAND2: left leg up, sword level, R arm up
        (38, 48),  # STAND3: both legs down, sword level, R arm down
        (39, 49),  # STAND4: right leg up, sword up, R arm down
    )

    # Upper limit on skeleton mob size
    _MAX_SKELLIES = const(3)

    def __init__(self, bitmap, palette, x0, y0, x1, y1):
        # This sets up skeleton sprites.
        # Args:
        # - bitmap, palette: Shared spritesheet from adafruit_imageload
        # - x0, y0: Skeleton spawn zone top-left corner coordinate
        # - y0, y1: Skeleton spawn zone bottom-right corner coordinate
        #
        # The spritesheet has 8x8 tiles. The skeleton sprite is 8x16 (2 tiles
        # tall). So, there are 2 tiles per sprite/frame of the animation cycle
        # for each skeleton.
        #
        gc.collect()
        # Make TileGrids and group
        grp = Group(scale=1)
        skellies = []
        for i in range(_MAX_SKELLIES):
            gc.collect()
            x = x0 + (((x1 - x0) // _MAX_SKELLIES) * i)
            tg = TileGrid(
                bitmap, pixel_shader=palette, width=1, height=2,
                tile_width=8, tile_height=8, x=x, y=y0)
            skellies.append(tg)
            grp.append(tg)
        gc.collect()
        # Save object references
        self.skellies = skellies
        self.grp = grp
        # Set sprite tiles for initial animation frame
        for i in range(len(self.skellies)):
            self.set_skellie(i, i*2)

    def group(self):
        # Return the displayio.Group object for the skeleton TileGrids
        return self.grp

    def set_skellie(self, n, frame):
        # Set animation cycle frame for skeleton sprite number n.
        if (n < 0) or (n >= len(self.skellies)):
            raise Exception(f"skeleton index out of range: {n}")
        elif (frame < HIDE) or (STAND4 < frame):
            raise Exception(f"skeleton frame out of range: {frame}")
        else:
            (top, bottom) = self._S_TILES[frame]
            self.skellies[n][0] = top
            self.skellies[n][1] = bottom
