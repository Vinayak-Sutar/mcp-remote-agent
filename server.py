from agent import run_agent
#!/usr/bin/env python3
"""PC Remote backend for Ubuntu/Wayland using evdev + uinput and Flask."""

import time
import threading
import logging
import os
from dataclasses import dataclass
from typing import Any

from evdev import UInput, ecodes
from flask import Flask, render_template
from flask_socketio import SocketIO

HOST = "0.0.0.0"
PORT = 5000

# Reasonable upper bound to prevent extremely large injected deltas.
MAX_DELTA = 200

try:
    from faster_whisper import WhisperModel
    import tempfile
    import os
    print("Loading Whisper model (base.en) on GPU...")
    # Initialize the model on CUDA using float16 for max speed on RTX 3060
    whisper_model = WhisperModel("base.en", device="cuda", compute_type="float16")
    print("Whisper model loaded!")
except ImportError:
    print("faster-whisper not installed. Voice commands will not work.")
    whisper_model = None
except Exception as e:
    print(f"Error loading Whisper: {e}. Falling back to none.")
    whisper_model = None



def _keyboard_capabilities() -> list[int]:
    return list(range(ecodes.KEY_ESC, ecodes.KEY_MICMUTE + 1))


@dataclass
class InputInjector:
    ui: UInput

    @classmethod
    def create(cls) -> "InputInjector":
        capabilities = {
            ecodes.EV_REL: [
                ecodes.REL_X,
                ecodes.REL_Y,
                ecodes.REL_WHEEL,
                ecodes.REL_HWHEEL,
            ],
            ecodes.EV_KEY: [
                ecodes.BTN_LEFT,
                ecodes.BTN_RIGHT,
                ecodes.BTN_MIDDLE,
                *_keyboard_capabilities(),
            ],
        }

        ui = UInput(
            events=capabilities,
            name="PC Remote Virtual Input",
            version=0x0003,
        )
        logging.info("Created virtual input device: %s", ui.device.path)
        return cls(ui=ui)

    def close(self) -> None:
        self.ui.close()

    def move_mouse(self, dx: int, dy: int) -> None:
        dx = max(-MAX_DELTA, min(MAX_DELTA, int(dx)))
        dy = max(-MAX_DELTA, min(MAX_DELTA, int(dy)))

        if dx == 0 and dy == 0:
            return

        self.ui.write(ecodes.EV_REL, ecodes.REL_X, dx)
        self.ui.write(ecodes.EV_REL, ecodes.REL_Y, dy)
        self.ui.syn()

    def mouse_button(self, button: str, state: str) -> None:
        button_map = {
            "left": ecodes.BTN_LEFT,
            "right": ecodes.BTN_RIGHT,
            "middle": ecodes.BTN_MIDDLE,
        }
        code = button_map.get(button.lower())
        if code is None:
            return

        normalized_state = state.lower()
        if normalized_state == "down":
            self.ui.write(ecodes.EV_KEY, code, 1)
            self.ui.syn()
        elif normalized_state == "up":
            self.ui.write(ecodes.EV_KEY, code, 0)
            self.ui.syn()
        elif normalized_state in {"click", "press"}:
            self.ui.write(ecodes.EV_KEY, code, 1)
            self.ui.syn()

            # Need a tiny sleep to let the OS register the click before releasing
            import time
            time.sleep(0.02)

            self.ui.write(ecodes.EV_KEY, code, 0)
            self.ui.syn()

    def scroll(self, dy: int = 0, dx: int = 0) -> None:
        dy = int(dy)
        dx = int(dx)
        if dy:
            self.ui.write(ecodes.EV_REL, ecodes.REL_WHEEL, dy)
        if dx:
            self.ui.write(ecodes.EV_REL, ecodes.REL_HWHEEL, dx)
        if dy or dx:
            self.ui.syn()

    def key_event(self, key: str | int, state: str) -> None:
        try:
            # Handle shifted characters like 'H' or '!'
            needs_shift = False
            if isinstance(key, str) and len(key) == 1:
                if key.isupper():
                    needs_shift = True
                elif key in '!@#$%^&*()_+{}|:"<>?~':
                    needs_shift = True
                    # Let's map the shifted symbol back to its unshifted keycode for evdev
                    shift_map = {'!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8',
                                 '(': '9', ')': '0', '_': '-', '+': '=', '{': '[', '}': ']', '|': '\\', ':': ';', '"': "'", '<': ',', '>': '.', '?': '/', '~': '`'}
                    key = shift_map.get(key, key)

            code = self._resolve_key_code(key)
        except ValueError:
            return

        normalized_state = state.lower()
        if normalized_state == "down":
            if needs_shift:
                self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
                self.ui.syn()
            self.ui.write(ecodes.EV_KEY, code, 1)
            self.ui.syn()
        elif normalized_state == "up":
            self.ui.write(ecodes.EV_KEY, code, 0)
            self.ui.syn()
            if needs_shift:
                self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
                self.ui.syn()
        elif normalized_state in {"press", "click"}:
            if needs_shift:
                self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
                self.ui.syn()

            self.ui.write(ecodes.EV_KEY, code, 1)
            self.ui.syn()

            import time
            time.sleep(0.02)

            self.ui.write(ecodes.EV_KEY, code, 0)
            self.ui.syn()

            if needs_shift:
                self.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
                self.ui.syn()

    def _resolve_key_code(self, key: str | int) -> int:
        if isinstance(key, int):
            return key

        if key == " ":
            return int(ecodes.KEY_SPACE)

        candidate = key.strip()
        if not candidate:
            raise ValueError("Key cannot be empty")

        if len(candidate) == 1:
            if candidate.isalpha():
                candidate = f"KEY_{candidate.upper()}"
            elif candidate.isdigit():
                candidate = f"KEY_{candidate}"
            elif candidate == " ":
                candidate = "KEY_SPACE"

        aliases = {
            "ENTER": "KEY_ENTER",
            "RETURN": "KEY_ENTER",
            "ESC": "KEY_ESC",
            "ESCAPE": "KEY_ESC",
            "SPACE": "KEY_SPACE",
            "TAB": "KEY_TAB",
            "BACKSPACE": "KEY_BACKSPACE",
            "DELETE": "KEY_DELETE",
            "UP": "KEY_UP",
            "DOWN": "KEY_DOWN",
            "LEFT": "KEY_LEFT",
            "RIGHT": "KEY_RIGHT",
            "CTRL": "KEY_LEFTCTRL",
            "ALT": "KEY_LEFTALT",
            "SHIFT": "KEY_LEFTSHIFT",
            "SUPER": "KEY_LEFTMETA",
            "META": "KEY_LEFTMETA",
            ".": "KEY_DOT",
            ",": "KEY_COMMA",
            "/": "KEY_SLASH",
            "\\": "KEY_BACKSLASH",
            "-": "KEY_MINUS",
            "=": "KEY_EQUAL",
            ";": "KEY_SEMICOLON",
            "'": "KEY_APOSTROPHE",
            "[": "KEY_LEFTBRACE",
            "]": "KEY_RIGHTBRACE",
            "`": "KEY_GRAVE"
        }

        upper = candidate.upper()
        if upper in aliases:
            upper = aliases[upper]
        elif not upper.startswith("KEY_"):
            upper = f"KEY_{upper}"

        code = getattr(ecodes, upper, None)
        if code is None:
            raise ValueError(f"Unsupported key: {key}")
        return int(code)


app = Flask(__name__)
# Add basic CORS support to allow connections from local LAN devices
socketio = SocketIO(app, cors_allowed_origins="*")
injector = None


@app.route('/')
def index():
    # Serve the built-in HTML file from templates/index.html
    return render_template('index.html')


drag_lock = threading.Lock()
last_click_time = 0.0


@socketio.on('move')
def handle_move(data):
    if injector:
        with drag_lock:
            injector.move_mouse(data.get('dx', 0), data.get('dy', 0))


@socketio.on('click')
def handle_click(data):
    global last_click_time
    if injector:
        button = str(data.get('button', 'left'))
        state = str(data.get('state', 'click'))
        is_double = data.get('double', False)

        with drag_lock:
            if is_double:
                injector.mouse_button(button, 'click')
                injector.mouse_button(button, 'click')
            else:
                injector.mouse_button(button, state)

            if state in {"click", "press", "up"}:
                last_click_time = time.time()


@socketio.on('scroll')
def handle_scroll(data):
    if injector:
        with drag_lock:
            injector.scroll(data.get('dy', 0), data.get('dx', 0))


@socketio.on('key')
def handle_key(data):
    if injector:
        key = data.get('key')
        state = str(data.get('state', 'press'))
        if key is not None:
            # Handle whole strings from mobile autocomplete!
            if state == 'press' and isinstance(key, str) and len(key) > 1 and key.upper() not in ["ENTER", "BACKSPACE", "ESCAPE", "TAB", "DELETE", "SPACE"]:
                for char in key:
                    injector.key_event(char, 'press')
            else:
                injector.key_event(key, state)


@socketio.on('drag')
def handle_drag(data):
    global last_click_time
    if injector:
        action = data.get('action')
        button = data.get('button', 'left')
        if action == 'start':
            with drag_lock:
                elapsed = time.time() - last_click_time
                # 0.45s safely clears GNOME/Wayland standard 400ms double-click timeout.
                # If a user double-taps too fast (e.g. 200ms), we just secretly pad the
                # remainder so libinput recognizes it as a single hold instead of click-chain.
                if elapsed < 0.45:
                    time.sleep(0.45 - elapsed)

                injector.mouse_button(button, 'down')
        elif action == 'stop':
            with drag_lock:
                injector.mouse_button(button, 'up')


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


@socketio.on('shortcut')
def handle_shortcut(data):
    if not injector: return
    action = data.get('action')
    try:
        if action == 'copy':
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 1)
            injector.ui.syn()
            time.sleep(0.01)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_C, 1)
            injector.ui.syn()
            time.sleep(0.01)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_C, 0)
            injector.ui.syn()
            time.sleep(0.01)
        elif action == 'paste':
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 1)
            injector.ui.syn()
            time.sleep(0.01)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_V, 1)
            injector.ui.syn()
            time.sleep(0.01)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_V, 0)
            injector.ui.syn()
            time.sleep(0.01)
        elif action == 'super':
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTMETA, 1)
            injector.ui.syn()
            time.sleep(0.01)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTMETA, 0)
            injector.ui.syn()
            time.sleep(0.01)
    finally:
        if action in ['copy', 'paste']:
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 0)
            injector.ui.syn()


@socketio.on('speech_audio')
def handle_speech_audio(data):
    try:
        from faster_whisper import WhisperModel
        import tempfile
        import os
    except Exception:
        pass

    print("[Whisper] Received audio blob of size:", len(data), flush=True)

    if 'whisper_model' not in globals() or whisper_model is None:
        print("[Whisper] Error: Model not ready.")
        return
    try:
        # Write bytes blob to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
            temp_audio.write(data)
            temp_audio_path = temp_audio.name
        
        print("[Whisper] Transcribing audio chunk...", flush=True)
        segments, info = whisper_model.transcribe(temp_audio_path, beam_size=2)
        text_out = "".join([segment.text for segment in segments]).strip()
        
        print(f"\n{'='*40}\n🎙️  [VOICE]: {text_out}\n{'='*40}\n", flush=True)

        # 🧠 **TRIGGER AGENT AI BACKGROUND THREAD** 🧠
        import threading
        import asyncio
        if text_out.strip():
            def background_agent_task(prompt):
                try: asyncio.run(run_agent(prompt))
                except Exception as e: print(f"Agent Thread Error: {e}", flush=True)
            
            threading.Thread(target=background_agent_task, args=(text_out,), daemon=True).start()

        
        # Emit back to frontend so it can inject the text into the text box
        
        # Directly type the text via evdev into the currently selected window on the PC
        if injector and text_out:
            # Map standard characters to their correct python-evdev ecodes
            # Note: For capital letters and symbols, we must hold shift
            for char in text_out:
                if char.islower() or char.isdigit() or char == ' ':
                    # lower case
                    if char == ' ': code = ecodes.KEY_SPACE
                    elif char.isdigit(): code = getattr(ecodes, f"KEY_{char}")
                    else: code = getattr(ecodes, f"KEY_{char.upper()}")
                    
                    try:
                        injector.ui.write(ecodes.EV_KEY, code, 1)
                        injector.ui.syn()
                        time.sleep(0.01)
                        injector.ui.write(ecodes.EV_KEY, code, 0)
                        injector.ui.syn()
                    except Exception: pass
                elif char.isupper():
                    code = getattr(ecodes, f"KEY_{char}")
                    try:
                        injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
                        injector.ui.syn()
                        time.sleep(0.01)
                        injector.ui.write(ecodes.EV_KEY, code, 1)
                        injector.ui.syn()
                        time.sleep(0.01)
                        injector.ui.write(ecodes.EV_KEY, code, 0)
                        injector.ui.syn()
                        injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
                        injector.ui.syn()
                    except Exception: pass
                else:
                    # Very crude basic symbol mapping for standard english punctuation Whisper might emit
                    sym_map = {'.': ecodes.KEY_DOT, ',': ecodes.KEY_COMMA, '?': ecodes.KEY_SLASH, '!': ecodes.KEY_1, '-': ecodes.KEY_MINUS, "'": ecodes.KEY_APOSTROPHE}
                    shift_map = {'?': True, '!': True}
                    
                    if char in sym_map:
                        code = sym_map[char]
                        is_shift = shift_map.get(char, False)
                        try:
                            if is_shift:
                                injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
                                injector.ui.syn()
                                time.sleep(0.01)
                            injector.ui.write(ecodes.EV_KEY, code, 1)
                            injector.ui.syn()
                            time.sleep(0.01)
                            injector.ui.write(ecodes.EV_KEY, code, 0)
                            injector.ui.syn()
                            if is_shift:
                                injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
                                injector.ui.syn()
                        except Exception: pass
                time.sleep(0.01)


        
        os.remove(temp_audio_path) # Clean up
    except Exception as e:
        print(f"[Whisper] Error processing audio: {e}", flush=True)


@socketio.on('alt_tab')
def handle_alt_tab(data):
    if injector:
        action = data.get('action')
        if action == 'start':
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTALT, 1)
            injector.ui.syn()
            # Press tab to open switcher and move beyond currently focused app
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_TAB, 1)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_TAB, 0)
            injector.ui.syn()
        elif action == 'step':
            direction = data.get('direction')
            if direction == 'right':
                injector.ui.write(ecodes.EV_KEY, ecodes.KEY_TAB, 1)
                injector.ui.write(ecodes.EV_KEY, ecodes.KEY_TAB, 0)
                injector.ui.syn()
            elif direction == 'left':
                # Shift+Tab to go backwards
                injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
                injector.ui.write(ecodes.EV_KEY, ecodes.KEY_TAB, 1)
                injector.ui.syn()
                injector.ui.write(ecodes.EV_KEY, ecodes.KEY_TAB, 0)
                injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
                injector.ui.syn()
        elif action == 'stop':
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTALT, 0)
            injector.ui.syn()



@socketio.on('volume')
def handle_volume(data):
    if not injector: return
    action = data.get('action')
    try:
        if action == 'up':
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_VOLUMEUP, 1)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_VOLUMEUP, 0)
            injector.ui.syn()
        elif action == 'down':
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_VOLUMEDOWN, 1)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_VOLUMEDOWN, 0)
            injector.ui.syn()
    except Exception as ex:
        print(f"Error handling volume: {ex}")

@socketio.on('arrow')
def handle_arrow(data):
    if not injector: return
    direction = data.get('direction', '')
    keys = {
        'up': ecodes.KEY_UP,
        'down': ecodes.KEY_DOWN,
        'left': ecodes.KEY_LEFT,
        'right': ecodes.KEY_RIGHT
    }
    if direction in keys:
        try:
            injector.ui.write(ecodes.EV_KEY, keys[direction], 1)
            injector.ui.write(ecodes.EV_KEY, keys[direction], 0)
            injector.ui.syn()
        except Exception as ex:
            print(f"Error handling arrow: {ex}")

@socketio.on('nav')
def handle_nav(data):
    if not injector: return
    direction = data.get('direction', '')
    keys = {
        'back': ecodes.KEY_BACK,
        'forward': ecodes.KEY_FORWARD
    }
    if direction in keys:
        try:
            injector.ui.write(ecodes.EV_KEY, keys[direction], 1)
            injector.ui.write(ecodes.EV_KEY, keys[direction], 0)
            injector.ui.syn()
        except Exception as ex:
            print(f"Error handling nav: {ex}")

@socketio.on('alt_f4')
def handle_alt_f4():
    try:
        print("DEBUG: Sending Alt+F4 to close window")
        if injector:
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTALT, 1)
            injector.ui.syn()
            time.sleep(0.05)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_F4, 1)
            injector.ui.syn()
            time.sleep(0.05)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_F4, 0)
            injector.ui.syn()
            time.sleep(0.01)
            injector.ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTALT, 0)
            injector.ui.syn()
    except Exception as ex:
        print(f"DEBUG Error in alt_f4: {ex}")




@socketio.on('open_app')
def handle_open_app(data):
    app_cmd = data.get('app')
    print(f"DEBUG: Open App / CMD: {app_cmd}")
    if app_cmd:
        try:
            import subprocess
            # Ubuntu/Wayland uses gio to launch desktop files
            subprocess.Popen(['gio', 'launch', app_cmd])
        except Exception as e:
            print(f"DEBUG Error opening app {app_cmd}: {e}")

@socketio.on('get_pc_apps')
def handle_get_pc_apps():
    import os
    print("DEBUG: Fetching installed apps from Linux desktop files")
    
    paths = [
        '/usr/share/applications',
        os.path.expanduser('~/.local/share/applications')
    ]
    
    apps = []
    seen_names = set()
    
    for p in paths:
        if os.path.exists(p):
            for file in os.listdir(p):
                if file.endswith('.desktop'):
                    full_path = os.path.join(p, file)
                    name = None
                    nodisplay = False
                    try:
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith('Name=') and not name:
                                    name = line[5:]
                                elif line.startswith('NoDisplay=true'):
                                    nodisplay = True
                        
                        if name and not nodisplay and name not in seen_names:
                            apps.append({'name': name, 'cmd': full_path})
                            seen_names.add(name)
                    except Exception as e:
                        pass
    
    apps = sorted(apps, key=lambda x: x['name'].lower())
    socketio.emit('pc_apps_list', apps)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        injector = InputInjector.create()
        print(f"Server starting on https://{HOST}:{PORT}\n\n🚨 MAKE SURE TO TYPE https:// AND ACCEPT CERT WARNING 🚨")
        socketio.run(app, host=HOST, port=PORT, ssl_context='adhoc', allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        pass
    finally:
        if injector:
            injector.close()
