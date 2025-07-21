import board
import busio

from kmk.kmk_keyboard import KMKKeyboard
from kmk.scanners.keypad import MatrixScanner
from kmk.scanners import DiodeOrientation
from kmk.keys import KC
from kmk.modules.macros import Macros, Press, Release, Tap
from kmk.modules.encoder import EncoderHandler
from kmk.extensions.media_keys import MediaKeys
from kmk.extensions.display import Display, TextEntry
from kmk.extensions.display.ssd1306 import SSD1306

COL_PINS = [board.D6, board.D7, board.D8]
ROW_PINS = [board.D0, board.D1, board.D2, board.D3]
ENC_A = board.D9
ENC_B = board.D10
SDA = board.D4
SCL = board.D5

keyboard = KMKKeyboard()

keyboard.matrix = MatrixScanner(
    column_pins=COL_PINS,
    row_pins=ROW_PINS,
    columns_to_anodes=DiodeOrientation.COL2ROW,
    interval=0.02,
    max_events=64,
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

ALT_TAB = KC.MACRO(Press(KC.LALT), Tap(KC.TAB), Release(KC.LALT))

encoder = EncoderHandler()
encoder.pins = ((ENC_A, ENC_B, None),)
encoder.map = [((KC.VOLU, KC.VOLD, KC.NO),)]
keyboard.modules.append(encoder)

brightness_mode = False
last_toggle_state = False

def after_matrix_scan(keyboard):
    global brightness_mode, last_toggle_state
    enc_btn_pressed = keyboard.keys[0].pressed
    if enc_btn_pressed and not last_toggle_state:
        brightness_mode = not brightness_mode
        if brightness_mode:
            encoder.map = [((KC.BRIGHTNESS_UP, KC.BRIGHTNESS_DOWN, KC.NO),)]
        else:
            encoder.map = [((KC.VOLU, KC.VOLD, KC.NO),)]
    last_toggle_state = enc_btn_pressed

keyboard.after_matrix_scan = after_matrix_scan

keyboard.keymap = [
    [
        KC.NO, ALT_TAB, KC.NO,
        KC.NO, KC.NO, KC.NO,
        KC.NO, KC.NO, KC.NO,
        KC.NO, KC.NO, KC.NO
    ]
]

if __name__ == '__main__':
    keyboard.go()
