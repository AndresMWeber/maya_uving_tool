import uvpacker.plugins.pmaya as pmaya


class Settings(object):
    NUM_BLOCKS_X = 10
    NUM_BLOCKS_Y = 10
    WIDTH = 30
    HEIGHT = 30
    TOTAL_WIDTH = NUM_BLOCKS_X * WIDTH
    TOTAL_HEIGHT = NUM_BLOCKS_Y * HEIGHT
    UV_STROKE_WIDTH = 0.01
    PLUGIN = pmaya.MayaInterface()
