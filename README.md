# MCP Remote Agent

A powerful local AI agent built using the **Model Context Protocol (MCP)** and local LLMs (**Ollama/Mistral**) to autonomously execute Operating System-level tasks and manage media.

*Note: This agent is currently optimized for **Ubuntu Linux**. Windows support is planned for future updates.*

This project bridges the gap between conversational AI and functional OS execution. Instead of just answering questions, the agent dynamically parses natural language (both text and voice dictation), decides which system-level tool is needed, and invokes it seamlessly using an MCP Server-Client architecture.

## 🚀 Key Features

* **Real System Manipulation**: Adjust system settings like master volume dynamically using ALSA/PulseAudio interfaces without opening system menus.
* **Automated Media Playback**: Don't just search for songs; the agent utilizes headless HTML scraping to fetch YouTube IDs and auto-plays media instantly.
* **Local, Private, \& Free**: Powered entirely by `Ollama` and `Mistral:latest`. No API limits, no subscription fees, and no data leaving your local machine.
* **Dual Interface Architecture**: 
  * **Desktop GUI App**: A beautiful, native PyQt6 interface for direct desktop interactions.
  * **PWA Voice Server**: A Flask-based backend allowing mobile devices on the same LAN to dictate commands using browser WebRTC microphones.
* **Regex Fallback Layer**: Implements a robust extraction system that captures tool-call JSON arrays even when the LLM hallucinates raw text, ensuring deterministic execution reliability.

---

## 🧠 System Architecture

This project is divided into three core architectural layers:
1. **The Server (`mcp_server.py`)**: A `FastMCP` initialized daemon that holds the actual python OS tools (the "Hands").
2. **The Client/Agent (`agent.py`)**: Acts as the LLM orchestrator. It fetches the available tool schemas dynamically from the server, passes them to Mistral via Ollama, and analyzes intent (the "Brain").
3. **The Interfaces (`desktop_app.py` & `server.py`)**: The frontend wrappers that handle user input (text or speech-to-text) and display agent outputs. 

---

## 🛠️ Installation & Setup

### Prerequisites
* Ubuntu / Linux OS
* Python 3.10+
* Local installation of [Ollama](https://ollama.com/) 
* Pulseaudio / ALSA mappings (For Linux volume control)

### 1. Clone & Environment
```bash
git clone https://github.com/Vinayak-Sutar/mcp-remote-agent.git
cd mcp-remote-agent

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Startup Ollama
Ensure the Mistral models are pulled and running in the background.
```bash
ollama serve
ollama pull mistral
```

---

## 🎮 Usage 

### Method A: The Desktop App (PyQt6)
Launch the standalone chat UI to test operations directly on your PC.
```bash
# We've provided a simple startup script
./start_chat_interface.sh
```

**Try typing commands like:**
* *"Can you set my volume to 80 percent?"*
* *"Play Numb by Linkin Park on YouTube."*
* *"Search for Python tutorials on YouTube."*

### Method B: The Local Voice Server (Web App)
Allows you to control your PC by speaking into your mobile phone while on the same Wi-Fi network.

**1. Generate Self-Signed Certificates** (Required for browser mic access)
```bash
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
```
*(Note: Do not commit the generated .pem files to public repositories)*

**2. Start the Server**
```bash
./run_web_server.sh
```
**3. Access from Phone**
Navigate to `https://<YOUR_LOCAL_PC_IP>:5000` on your mobile browser, accept the security warning, press the microphone button, and start talking!

---

## 🏗️ Extending the Agent

Because this project utilizes the **Model Context Protocol**, adding new capabilities is incredibly easy.

1. Open `mcp_server.py`.
2. Write a standard python function using the `@mcp.tool()` decorator.
3. Include Type-Hints and a Docstring (This is what Mistral reads to understand the tool).

Example:
```python
@mcp.tool()
def take_screenshot(delay_seconds: int) -> str:
    """Takes a screenshot of the main display after a given delay."""
    # Write execution code here...
    return f"Screenshot saved successfully!"
```
4. Restart the agent. The LLM will automatically discover your new tool and know exactly when to use it!
