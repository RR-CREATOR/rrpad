import board
import busio
import digitalio
import keypad
import time

from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC
from kmk.modules.macros import Macros, Press, Release, Tap
from kmk.modules.encoder import EncoderHandler
from kmk.extensions.media_keys import MediaKeys
from kmk.extensions.display import Display, TextEntry
from kmk.extensions.display.ssd1306 import SSD1306

COL_PINS = [board.D6, board.D10, board.D9]
ROW_PINS = [board.D0, board.D1, board.D2, board.D3]
ENC_A = board.D8
ENC_B = board.D7
SDA = board.D4
SCL = board.D5

keyboard = KMKKeyboard()

class RRPadMatrixScanner:
    offset = 0

    def __init__(self, row_pins, column_pins):
        self.rows = []
        self.cols = []
        self._pressed = set()
        self._queue = []

        for pin in row_pins:
            io = digitalio.DigitalInOut(pin)
            io.direction = digitalio.Direction.OUTPUT
            io.value = True
            self.rows.append(io)

        for pin in column_pins:
            io = digitalio.DigitalInOut(pin)
            io.direction = digitalio.Direction.INPUT
            io.pull = digitalio.Pull.UP
            self.cols.append(io)

    @property
    def key_count(self):
        return len(self.rows) * len(self.cols)

    @property
    def coord_mapping(self):
        return tuple(range(self.offset, self.offset + self.key_count))

    def scan_for_changes(self):
        if self._queue:
            key_number, pressed = self._queue.pop(0)
            return keypad.Event(key_number + self.offset, pressed)

        current = set()
        for row_index, row in enumerate(self.rows):
            row.value = False
            time.sleep(0.001)
            for col_index, col in enumerate(self.cols):
                if not col.value:
                    current.add(row_index * len(self.cols) + col_index)
            row.value = True

        for key_number in sorted(self._pressed - current):
            self._queue.append((key_number, False))
        for key_number in sorted(current - self._pressed):
            self._queue.append((key_number, True))

        self._pressed = current
        if self._queue:
            key_number, pressed = self._queue.pop(0)
            return keypad.Event(key_number + self.offset, pressed)


keyboard.matrix = RRPadMatrixScanner(
    column_pins=COL_PINS,
    row_pins=ROW_PINS,
)

keyboard.extensions.append(MediaKeys())

i2c = busio.I2C(SCL, SDA)
oled = SSD1306(i2c=i2c)

keyboard.extensions.append(
    Display(
        display=oled,
        entries=[TextEntry(text='rrpad', x=45, y=12)],
        height=32,
        dim_time=10,
        dim_target=0.2,
        off_time=1200,
        brightness=1,
    )
)

macros = Macros()
keyboard.modules.append(macros)

COPY = KC.MACRO(Press(KC.LCTRL), Tap(KC.C), Release(KC.LCTRL))
PASTE = KC.MACRO(Press(KC.LCTRL), Tap(KC.V), Release(KC.LCTRL))

encoder = EncoderHandler()
encoder.pins = ((ENC_A, ENC_B, None),)
encoder.map = [((KC.VOLU, KC.VOLD, KC.NO),)]
keyboard.modules.append(encoder)

brightness_mode = False

def toggle_encoder_mode(keyboard):
    global brightness_mode
    brightness_mode = not brightness_mode
    if brightness_mode:
        encoder.map = [((KC.BRIGHTNESS_UP, KC.BRIGHTNESS_DOWN, KC.NO),)]
    else:
        encoder.map = [((KC.VOLU, KC.VOLD, KC.NO),)]

TOGGLE_ENCODER_MODE = KC.MACRO(toggle_encoder_mode)

keyboard.keymap = [
    [
        TOGGLE_ENCODER_MODE, COPY, PASTE,
        KC.NO, KC.NO, KC.NO,
        KC.NO, KC.NO, KC.NO,
        KC.NO, KC.NO, KC.NO
    ]
]

if __name__ == '__main__':
    keyboard.go()
