import board
import busio
import digitalio
import displayio
import keypad
import terminalio
import time
from adafruit_display_text import label
from supervisor import ticks_ms

from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC, make_key
from kmk.modules import Module
from kmk.extensions import Extension
from kmk.extensions.media_keys import MediaKeys
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

class RRPadDisplay(Extension):
    def __init__(self, display):
        self.display_driver = display
        self.mode = 'VOL'
        self.last_action = 'Ready'
        self._dirty = True
        self._last_activity = ticks_ms()

    def set_mode(self, mode):
        self.mode = mode
        self.last_action = mode
        self._dirty = True
        self._last_activity = ticks_ms()

    def set_action(self, action):
        self.last_action = action
        self._dirty = True
        self._last_activity = ticks_ms()

    def during_bootup(self, keyboard):
        self.display_driver.during_bootup(128, 32, 0)
        self.display_driver.brightness = 1

        splash = displayio.Group()
        self.title = label.Label(terminalio.FONT, text='rrpad', color=0xFFFFFF, x=0, y=8)
        self.mode_label = label.Label(terminalio.FONT, text='', color=0xFFFFFF, x=0, y=20)
        self.action_label = label.Label(terminalio.FONT, text='', color=0xFFFFFF, x=64, y=20)
        splash.append(self.title)
        splash.append(self.mode_label)
        splash.append(self.action_label)
        self.display_driver.root_group = splash
        self._render()

    def _render(self):
        self.mode_label.text = 'Mode: ' + self.mode
        self.action_label.text = self.last_action
        self.display_driver.brightness = 1
        self.display_driver.wake()
        self._dirty = False

    def before_matrix_scan(self, sandbox):
        if self._dirty:
            self._render()

    def after_matrix_scan(self, sandbox):
        return

    def before_hid_send(self, sandbox):
        return

    def after_hid_send(self, sandbox):
        return

    def on_runtime_enable(self, keyboard):
        return

    def on_runtime_disable(self, keyboard):
        return

    def on_powersave_enable(self, sandbox):
        return

    def on_powersave_disable(self, sandbox):
        return

    def deinit(self, sandbox):
        displayio.release_displays()
        self.display_driver.deinit()


rr_display = RRPadDisplay(SSD1306(i2c=i2c))
keyboard.extensions.append(rr_display)

brightness_mode = False

def toggle_encoder_mode(keyboard):
    global brightness_mode
    brightness_mode = not brightness_mode
    if brightness_mode:
        rr_display.set_mode('BRI')
    else:
        rr_display.set_mode('VOL')

def copy_pressed(key, keyboard, *args):
    rr_display.set_action('Copy')
    keyboard.tap_key(KC.LCTRL(KC.C))

def paste_pressed(key, keyboard, *args):
    rr_display.set_action('Paste')
    keyboard.tap_key(KC.LCTRL(KC.V))

make_key(names=('RR_TOG',), on_press=lambda key, keyboard, *args: toggle_encoder_mode(keyboard))
make_key(names=('RR_COPY',), on_press=copy_pressed)
make_key(names=('RR_PASTE',), on_press=paste_pressed)

class RRPadEncoder(Module):
    TRANSITIONS = {
        (0, 1): 1,
        (1, 3): 1,
        (3, 2): 1,
        (2, 0): 1,
        (0, 2): -1,
        (2, 3): -1,
        (3, 1): -1,
        (1, 0): -1,
    }

    def __init__(self, pin_a, pin_b):
        self.pin_a = digitalio.DigitalInOut(pin_a)
        self.pin_b = digitalio.DigitalInOut(pin_b)
        self.pin_a.direction = digitalio.Direction.INPUT
        self.pin_b.direction = digitalio.Direction.INPUT
        self.pin_a.pull = digitalio.Pull.UP
        self.pin_b.pull = digitalio.Pull.UP
        self._state = self._read()
        self._movement = 0

    def _read(self):
        return (1 if self.pin_a.value else 0) | (2 if self.pin_b.value else 0)

    def during_bootup(self, keyboard):
        return

    def before_matrix_scan(self, keyboard):
        global brightness_mode
        new_state = self._read()
        delta = self.TRANSITIONS.get((self._state, new_state), 0)
        self._state = new_state

        if not delta:
            return

        self._movement -= delta
        if self._movement >= 2:
            self._movement = 0
            if brightness_mode:
                keyboard.tap_key(KC.BRIGHTNESS_UP)
                rr_display.set_action('Bri +')
            else:
                keyboard.tap_key(KC.VOLU)
                rr_display.set_action('Vol +')
        elif self._movement <= -2:
            self._movement = 0
            if brightness_mode:
                keyboard.tap_key(KC.BRIGHTNESS_DOWN)
                rr_display.set_action('Bri -')
            else:
                keyboard.tap_key(KC.VOLD)
                rr_display.set_action('Vol -')

    def after_matrix_scan(self, keyboard):
        return

    def process_key(self, keyboard, key, is_pressed, int_coord):
        return key

    def before_hid_send(self, keyboard):
        return

    def after_hid_send(self, keyboard):
        return

    def on_powersave_enable(self, keyboard):
        return

    def on_powersave_disable(self, keyboard):
        return

    def deinit(self, keyboard):
        self.pin_a.deinit()
        self.pin_b.deinit()


keyboard.modules.append(RRPadEncoder(ENC_A, ENC_B))

keyboard.keymap = [
    [
        KC.RR_TOG, KC.RR_COPY, KC.RR_PASTE,
        KC.NO, KC.NO, KC.NO,
        KC.NO, KC.NO, KC.NO,
        KC.NO, KC.NO, KC.NO
    ]
]

if __name__ == '__main__':
    keyboard.go()
