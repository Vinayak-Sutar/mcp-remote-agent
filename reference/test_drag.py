import pyautogui
import time

pyautogui.moveTo(500, 500)
pyautogui.click()
time.sleep(0.1)

# Teleport cursor away and back to break double-click sequence
x, y = pyautogui.position()
pyautogui.moveTo(x+20, y+20)
pyautogui.moveTo(x, y)

pyautogui.mouseDown()
pyautogui.move(200, 200)
time.sleep(1)
pyautogui.mouseUp()
