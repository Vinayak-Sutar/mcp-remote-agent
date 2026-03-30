# PC Remote Backend (Ubuntu Wayland)

This backend receives input events from your mobile app over WebSocket and injects them through a virtual input device using `evdev` + `uinput`.

## 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Ensure `/dev/uinput` is available

```bash
sudo modprobe uinput
ls -l /dev/uinput
```

If `/dev/uinput` does not exist, load module at boot:

```bash
echo uinput | sudo tee /etc/modules-load.d/uinput.conf
```

## 3. Run server

### Option A: Run with sudo (quickest)

```bash
sudo -E .venv/bin/python server.py
```

### Option B: Run as normal user via udev rule

Create udev rule:

```bash
echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Add your user to input group and re-login:

```bash
sudo usermod -aG input "$USER"
```

After re-login, run normally:

```bash
.venv/bin/python server.py
```

## 4. Optional auth token

Set a shared token to prevent random LAN clients from controlling the PC:

```bash
export REMOTE_TOKEN='change-me'
```

If set, first client packet must be:

```json
{ "type": "auth", "token": "change-me" }
```

## 5. Test locally

Use browser devtools console from any machine on same LAN:

```javascript
const ws = new WebSocket("ws://<ubuntu-ip>:5000");

ws.onopen = () => {
  // Send this first only if REMOTE_TOKEN is enabled:
  // ws.send(JSON.stringify({ type: "auth", token: "change-me" }));

  ws.send(JSON.stringify({ type: "move", dx: 30, dy: 0 }));
  ws.send(JSON.stringify({ type: "click", button: "left", state: "click" }));
  ws.send(JSON.stringify({ type: "scroll", dy: -1 }));
  ws.send(JSON.stringify({ type: "key", key: "H", state: "press" }));
  ws.send(JSON.stringify({ type: "key", key: "i", state: "press" }));
};
```

## 6. Message format summary

- Mouse move: `{"type":"move","dx":12,"dy":-4}`
- Click: `{"type":"click","button":"left|right|middle","state":"down|up|click"}`
- Scroll: `{"type":"scroll","dy":1,"dx":0}`
- Key: `{"type":"key","key":"KEY_A"|"A"|"ENTER", "state":"down|up|press"}`
- Ping: `{"type":"ping"}` -> server responds with pong JSON.
