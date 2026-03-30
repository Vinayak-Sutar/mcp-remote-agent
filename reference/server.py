from flask import Flask, render_template
from flask_socketio import SocketIO
import mouse
import keyboard
import socket
import logging
import subprocess
import os
import time
from zeroconf import ServiceInfo, Zeroconf
import qrcode
import sys
import hashlib
import threading

# Disable logging to make the terminal cleaner
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
# Use simple-websocket which we installed
socketio = SocketIO(app, cors_allowed_origins="*")

# Global drag state
is_dragging = False

# Prevent caching during development so the UI updates immediately
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def index():
    return render_template('index.html')

remainder_x = 0.0
remainder_y = 0.0

@socketio.on('move')
def handle_move(data):
    global is_dragging, remainder_x, remainder_y
    dx = data.get('dx', 0)
    dy = data.get('dy', 0)
    
    # We apply the multiplier sent from the mobile settings
    speed_multiplier = data.get('sens', 1.5) 
    
    if dx != 0 or dy != 0:
        try:
            # Accumulate fractional movements
            raw_x = (dx * speed_multiplier) + remainder_x
            raw_y = (dy * speed_multiplier) + remainder_y
            
            # Force integer coordinates. Windows Explorer (Desktop) often ignores sub-pixel 
            # floating point movements when trying to draw a selection box or drag an icon.
            move_x = int(raw_x)
            move_y = int(raw_y)
            
            remainder_x = raw_x - move_x
            remainder_y = raw_y - move_y
            
            if move_x != 0 or move_y != 0:
                mouse.move(move_x, move_y, absolute=False)
        except Exception as e:
            pass

@socketio.on('click')
def handle_click(data):
    btn = data.get('button', 'left')
    is_double = data.get('double', False)
    try:
        if is_double:
            mouse.double_click(btn)
        else:
            mouse.click(btn)
    except Exception as e:
        pass

@socketio.on('scroll')
def handle_scroll(data):
    dy = data.get('dy', 0)
    sens = data.get('sens', 1.0)
    if dy != 0:
        try:
            # The mouse library takes scroll amount directly (usually smaller numbers)
            # Dividing by 15 makes it feel similar to what pyautogui-10 felt like
            scroll_amount = (dy * -1 * sens) / 15.0
            if scroll_amount != 0:
                mouse.wheel(scroll_amount)
        except Exception as e:
            pass

@socketio.on('arrow')
def handle_arrow(data):
    direction = data.get('direction', '')
    if direction in ['up', 'down', 'left', 'right']:
        try:
            keyboard.send(direction)
        except Exception as e:
            pass

@socketio.on('type')
def handle_type(data):
    key = data.get('key', '')
    if key:
        print(f"DEBUG Typing: {key}")
        try:
            if key == 'backspace':
                keyboard.send('backspace')
            elif key == 'enter':
                keyboard.send('enter')
            else:
                # Sometimes keyboard.write fails silently on virtual keys.
                # Sending the actual key code string as a fallback for 1-char strings
                if len(key) == 1:
                    keyboard.send(key)
                else:
                    keyboard.write(key)
        except Exception as e:
            print(f"DEBUG Error typing: {e}")
            pass

@socketio.on('nav')
def handle_nav(data):
    direction = data.get('direction', '')
    if direction == 'back':
        try:
            keyboard.send('browser back')
        except Exception as e:
            pass
    elif direction == 'forward':
        try:
            keyboard.send('browser forward')
        except Exception as e:
            pass

@socketio.on('swipe')
def handle_swipe(data):
    direction = data.get('direction', '')
    fingers = data.get('fingers', 0)
    
    if fingers == 3:
        try:
            if direction in ['up', 'down']:
                print(f"DEBUG: 3-finger vertical swipe {direction} -> Win+D")
                keyboard.send('windows+d')
        except Exception as e:
            print(f"DEBUG Error in swipe: {e}")
            pass

@socketio.on('alt_tab')
def handle_alt_tab(data):
    action = data.get('action')
    try:
        if action == 'start':
            print("DEBUG: Alt+Tab START")
            keyboard.press('alt')
            keyboard.send('tab')
        elif action == 'step':
            direction = data.get('direction')
            print(f"DEBUG: Alt+Tab STEP {direction}")
            if direction == 'right':
                keyboard.send('tab')
            elif direction == 'left':
                keyboard.send('shift+tab')
        elif action == 'stop':
            print("DEBUG: Alt+Tab STOP")
            keyboard.release('alt')
    except Exception as e:
        print(f"DEBUG Error in alt_tab: {e}")
        pass

@socketio.on('alt_f4')
def handle_alt_f4():
    try:
        print("DEBUG: Sending Alt+F4 to close window")
        keyboard.send('alt+f4')
    except Exception as e:
        print(f"DEBUG Error in alt_f4: {e}")
        pass
@socketio.on('media')
def handle_media(data):
    action = data.get('action')
    try:
        # Sends Windows OS-level global media keys
        if action in ['play/pause media', 'next track', 'previous track', 'volume mute']:
            print(f"DEBUG: Media action {action}")
            keyboard.send(action)
    except Exception as e:
        print(f"DEBUG Error in media: {e}")
        pass
@socketio.on('volume')
def handle_volume(data):
    action = data.get('action')
    try:
        if action == 'up':
            keyboard.send('volume up')
            keyboard.send('volume up')
        elif action == 'down':
            keyboard.send('volume down')
            keyboard.send('volume down')
    except Exception as e:
        pass

@socketio.on('drag')
def handle_drag(data):
    global is_dragging
    action = data.get('action')
    btn = data.get('button', 'left')
    try:
        if action == 'start':
            is_dragging = True
            print(f"DEBUG: Drag START (Mouse Down {btn})")
            
            x, y = mouse.get_position()
            mouse.move(10, 10, absolute=False)
            mouse.move(x, y, absolute=True)
            
            mouse.press(btn)
        elif action == 'stop':
            is_dragging = False
            print(f"DEBUG: Drag STOP (Mouse Up {btn})")
            mouse.release(btn)
    except Exception as e:
        print(f"DEBUG Error in drag: {e}")
        pass

@socketio.on('open_app')
def handle_open_app(data):
    app_cmd = data.get('app')
    print(f"DEBUG: Open App / CMD: {app_cmd}")
    if app_cmd:
        try:
            # We use shell=True and a formatted string to properly execute Windows 'start'
            # The empty "" is to bypass the 'start' command's title restriction.
            subprocess.Popen(f'start "" "{app_cmd}"', shell=True)
        except Exception as e:
            print(f"DEBUG Error opening app {app_cmd}: {e}")

@socketio.on('get_pc_apps')
def handle_get_pc_apps():
    print("DEBUG: Fetching installed apps from Start Menu")
    paths = [
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
    ]
    apps = []
    seen_names = set()
    
    for p in paths:
        if os.path.exists(p):
            for root, dirs, files in os.walk(p):
                for file in files:
                    if file.endswith('.lnk'):
                        name = file[:-4]
                        
                        # Filter out common junk
                        name_lower = name.lower()
                        if "uninstall" in name_lower or "help" in name_lower or "setup" in name_lower:
                            continue
                            
                        # Avoid duplicates
                        if name not in seen_names:
                            full_path = os.path.join(root, file)
                            apps.append({"name": name, "cmd": full_path})
                            seen_names.add(name)
    
    # Sort alphabetically by name
    apps = sorted(apps, key=lambda x: x['name'].lower())
    
    # Add icons to each app
    for app_info in apps:
        app_info['icon'] = get_app_icon(app_info['cmd'])
        
    socketio.emit('pc_apps_list', apps)

def get_app_icon(filepath):
    """Extracts icon from a file or shortcut and returns its relative URL."""
    if not filepath or not os.path.exists(filepath):
        return None
        
    # Generate a unique filename for the icon based on filepath hash
    path_hash = hashlib.md5(filepath.encode()).hexdigest()
    icon_filename = f"{path_hash}.png"
    icon_rel_path = f"static/app_icons/{icon_filename}"
    icon_abs_path = os.path.join(os.getcwd(), icon_rel_path)
    
    # If icon already exists, return it immediately
    if os.path.exists(icon_abs_path):
        return f"/{icon_rel_path}"
        
    try:
        # PowerShell command to extract icon
        # We use [System.Drawing.Icon]::ExtractAssociatedIcon which handles .exe, .lnk, etc.
        ps_cmd = f"""
        Add-Type -AssemblyName System.Drawing
        $icon = [System.Drawing.Icon]::ExtractAssociatedIcon('{filepath}')
        $bitmap = $icon.ToBitmap()
        $bitmap.Save('{icon_abs_path}', [System.Drawing.Imaging.ImageFormat]::Png)
        """
        # Run PowerShell silently
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, check=True)
        
        if os.path.exists(icon_abs_path):
            return f"/{icon_rel_path}"
    except Exception as e:
        print(f"DEBUG Error extracting icon for {filepath}: {e}")
        
    return None

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def print_qr(url):
    qr = qrcode.QRCode(version=1, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    # Using 'ascii' for a simple terminal QR code
    # On Windows, using inverted colors might look better depending on theme
    qr.print_ascii(invert=True)

def register_mdns(ip, port):
    desc = {'path': '/'}
    info = ServiceInfo(
        "_http._tcp.local.",
        "pc-remote._http._tcp.local.",
        addresses=[socket.inet_aton(ip)],
        port=port,
        properties=desc,
        server="pc-remote.local.",
    )
    zeroconf = Zeroconf()
    zeroconf.register_service(info)
    return zeroconf, info

if __name__ == '__main__':
    ip = get_local_ip()
    port = 5000
    host_url = f"http://{ip}:{port}"
    mdns_url = f"http://pc-remote.local:{port}"

    print("\n" + "=" * 50)
    print("🚀 REMOTE PC TRACKPAD IS RUNNING!")
    print(f"📱 Local IP:  {host_url}")
    print(f"🔗 Static URL: {mdns_url} (Try this first!)")
    print("=" * 50)
    
    print("\n📱 SCAN TO CONNECT:")
    print_qr(host_url)
    print("=" * 50 + "\n")
    
    # Register mDNS in background
    zc, info = register_mdns(ip, port)
    
    try:
        socketio.run(app, host='0.0.0.0', port=port)
    finally:
        zc.unregister_service(info)
        zc.close()
