import sys
import os
import asyncio
import qasync
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
import ollama

SYSTEM_PROMPT = """You are an intelligent Ubuntu Desktop MCP assistant.
YOUR CRITICAL RULES:
1. You have access to real system tools (set_volume, browser_youtube_search, play_youtube_video).
2. FIRST, carefully analyze the user's intent. Ask yourself: "Does this request explicitly require me to modify a system setting or control media?"
3. If the user is just chatting, asking a general question, or seeking information, DO NOT use any tools. Just provide a natural text response.
4. Only if the answer to step 2 is YES, you MUST use the appropriate tool.
5. If the user uses the word 'PLAY', you MUST use `play_youtube_video`. DO NOT use `browser_youtube_search`.
6. If using a tool, NEVER write conversational text or explain your intentions. YOU MUST ATTACH A JSON ARRAY containing the tool call. For example:
[{"name": "set_volume", "arguments": {"level": 100}}]
"""


class ChatApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Desktop MCP Assistant")
        self.resize(700, 800)

        # Color Palette: #84B179, #A2CB8B, #C7EABB, #E8F5BD
        self.setStyleSheet("""
            QMainWindow { background-color: #E8F5BD; }
            QTextEdit { background-color: #ffffff; color: #2c3e2d; border: 2px solid #A2CB8B; border-radius: 10px; padding: 10px; font-size: 14px; }
            QLineEdit { background-color: #ffffff; color: #2c3e2d; border: 2px solid #84B179; border-radius: 15px; padding: 10px; font-size: 14px; }
            QPushButton { background-color: #84B179; color: white; border: none; border-radius: 15px; padding: 10px 20px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #A2CB8B; }
            QPushButton:disabled { background-color: #C7EABB; }
            QLabel { color: #2c3e2d; font-weight: bold; font-size: 16px; }
        """)

        # Main Widget & Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("🤖 Ubuntu MCP Assistant")

        clear_btn = QPushButton("Clear Memory")
        clear_btn.setStyleSheet(
            "background-color: #A2CB8B; font-size:12px; padding: 5px 15px;")
        clear_btn.clicked.connect(self.clear_chat)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(clear_btn)
        main_layout.addLayout(header_layout)

        # Chat Text Box (Read Only)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Segoe UI", 12))
        main_layout.addWidget(self.chat_display)

        # Bottom Input Area
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Message your assistant...")
        self.input_field.returnPressed.connect(self.send_message)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        main_layout.addLayout(input_layout)

        # Initialization
        self.chat_history = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        self.append_to_chat(
            "Agent", "Hello! I am connected to your local MCP tools. What can I do for you?", "#A2CB8B")

    def clear_chat(self):
        self.chat_history = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        self.chat_display.clear()
        self.append_to_chat("System", "Memory wiped.", "#C7EABB")
        self.append_to_chat("Agent", "Hello! How can I help?", "#A2CB8B")

    def append_to_chat(self, sender, text, color):
        html = f'<div style="margin-bottom: 10px;"><b><font color="{color}">{sender}:</font></b> <span style="color: #2c3e2d;">{text}</span></div>'
        self.chat_display.append(html)
        # Scroll to bottom
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @qasync.asyncSlot()
    async def send_message(self):
        text = self.input_field.text().strip()
        if not text:
            return

        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Thinking...")

        self.append_to_chat("You", text, "#84B179")

        try:
            await self.run_agent_flow(text)
        except Exception as e:
            self.append_to_chat("System", f"Error: {str(e)}", "#ff0000")
        finally:
            self.input_field.setEnabled(True)
            self.send_btn.setEnabled(True)
            self.send_btn.setText("Send")
            self.input_field.setFocus()

    async def run_agent_flow(self, prompt):
        self.chat_history.append({'role': 'user', 'content': prompt})

        server_params = StdioServerParameters(
            command=sys.executable,
            args=["mcp_server.py"],
            env=os.environ.copy()
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                mcp_tools_response = await session.list_tools()

                ollama_tools = []
                for tool in mcp_tools_response.tools:
                    # Deep copy and robust cleanup of JSON Schema to match what Mistral perfectly expects
                    schema = dict(tool.inputSchema)
                    if 'title' in schema:
                        del schema['title']
                    clean_properties = {}
                    for prop_name, prop_data in schema.get('properties', {}).items():
                        clean_prop = dict(prop_data)
                        if 'title' in clean_prop:
                            del clean_prop['title']
                        # Mistral absolutely requires descriptions for parameters
                        if 'description' not in clean_prop:
                            clean_prop['description'] = f"The {prop_name} value."
                        clean_properties[prop_name] = clean_prop
                    schema['properties'] = clean_properties

                    ollama_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or f"Tool to {tool.name}",
                            "parameters": schema
                        }
                    })

                # Call Ollama
                response = await asyncio.to_thread(
                    ollama.chat,
                    model='mistral:latest',
                    messages=self.chat_history,
                    tools=ollama_tools
                )

                # Ollama Py SDK v0.4+ returns a Model object, not a raw dict. We must convert it safely.
                raw_message = response.get('message', {})
                message_dict = dict(raw_message) if isinstance(raw_message, dict) else (
                    getattr(raw_message, 'model_dump', lambda: dict(raw_message))())

                # If Ollama hallucinates the JSON string inside the message text
                content_str = message_dict.get('content', '') or ''
                tool_calls = message_dict.get('tool_calls')

                import re
                import json

                # Check for array of objects anywhere in output
                json_match = re.search(
                    r'\[\s*\{.*"name"\s*:.*\}\s*\]', content_str, re.DOTALL)

                if not tool_calls and json_match:
                    try:
                        extracted = json.loads(json_match.group(0))
                        tool_calls = []
                        for t in extracted:
                            # ensure type safety
                            args = t.get('arguments', {})
                            if isinstance(args, str):
                                args = json.loads(args)
                            tool_calls.append({
                                'function': {
                                    'name': t.get('name'),
                                    'arguments': args
                                }
                            })
                        message_dict['tool_calls'] = tool_calls
                        # Remove the JSON text from the chat display log
                        message_dict['content'] = content_str[:json_match.start()].strip(
                        )
                    except Exception as e:
                        print(f"Fallback JSON parse error: {e}", flush=True)

                if message_dict.get('tool_calls'):
                    self.chat_history.append(message_dict)

                    for tool_call in message_dict['tool_calls']:
                        try:
                            # Handle both object notations and dictionary notations safely
                            fn = tool_call.get('function') if isinstance(
                                tool_call, dict) else tool_call.function
                            func_name = fn.get('name') if isinstance(
                                fn, dict) else fn.name
                            func_args = fn.get('arguments') if isinstance(
                                fn, dict) else fn.arguments

                            if isinstance(func_args, str):
                                func_args = json.loads(func_args)

                            self.append_to_chat(
                                "System", f"⚡ Running Tool: {func_name}({func_args})", "#999999")

                            tool_result = await session.call_tool(func_name, arguments=func_args)
                            result_text = tool_result.content[0].text
                        except Exception as e:
                            result_text = f"Error executing tool: {str(e)}"
                            func_name = str(tool_call)

                        self.append_to_chat(
                            "System", f"✅ Tool Result: {result_text}", "#999999")

                        self.chat_history.append({
                            'role': 'tool',
                            'name': func_name,
                            'content': result_text
                        })

                    # Second pass to reply to User
                    final_response = await asyncio.to_thread(
                        ollama.chat,
                        model='mistral:latest',
                        messages=self.chat_history
                    )
                    final_msg = final_response.get('message', {})
                    final_dict = dict(final_msg) if isinstance(final_msg, dict) else (
                        getattr(final_msg, 'model_dump', lambda: dict(final_msg))())
                    self.chat_history.append(final_dict)
                    self.append_to_chat(
                        "Agent", final_dict.get('content', ''), "#A2CB8B")
                else:
                    self.chat_history.append(message_dict)
                    self.append_to_chat(
                        "Agent", message_dict.get('content', ''), "#A2CB8B")


async def main():
    app = QApplication.instance() or QApplication(sys.argv)
    window = ChatApp()
    window.show()

    # Keep the async loop running
    future = asyncio.Future()
    app.aboutToQuit.connect(future.cancel)
    try:
        await future
    except asyncio.CancelledError:
        pass

if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    with loop:
        loop.run_until_complete(main())
