# Temporary Python patch for the server
import re
with open('/home/vinayak/FILES/code/ubuntu_remote/server.py', 'r') as f:
    content = f.read()

# Add socket handlers for 'drag', 'swipe', and 'alt_tab'
new_handlers = """
@socketio.on('drag')
def handle_drag(data):
    if injector:
        action = data.get('action')
        if action == 'start':
            injector.mouse_button('left', 'down')
        elif action == 'stop':
            injector.mouse_button('left', 'up')

@socketio.on('swipe')
def handle_swipe(data):
    if injector:
        direction = data.get('direction')
        fingers = data.get('fingers')
        # 3-finger swipe vertical -> Super+D (show desktop) or Super+Tab, etc.
        # Wayland Ubuntu: Super+D usually toggles desktop.
        if fingers == 3:
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTMETA, 1)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_D, 1)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_D, 0)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTMETA, 0)
            injector.ui.syn()

@socketio.on('alt_tab')
def handle_alt_tab(data):
    if injector:
        action = data.get('action')
        if action == 'start':
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTALT, 1)
            injector.ui.syn()
        elif action == 'step':
            # hold alt, tap tab
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_TAB, 1)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_TAB, 0)
            injector.ui.syn()
        elif action == 'stop':
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTALT, 0)
            injector.ui.syn()

if __name__ == '__main__':"""

content = content.replace("if __name__ == '__main__':", new_handlers)

with open('/home/vinayak/FILES/code/ubuntu_remote/server.py', 'w') as f:
    f.write(content)
print("Backend patched")
