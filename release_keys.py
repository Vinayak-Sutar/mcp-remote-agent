from evdev import UInput, ecodes
import time
ui = UInput()
ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTALT, 0)
ui.write(ecodes.EV_KEY, ecodes.KEY_RIGHTALT, 0)
ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 0)
ui.syn()
ui.close()
