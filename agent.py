import asyncio
import sys
import os
import ollama
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


async def run_agent(prompt: str):
    """
    Connects to the local MCP Tools server, parses the user's prompt via Ollama (llama3.2),
    and executes whatever OS tool the LLM decides is necessary.
    """

    # We define how to launch the MCP server as a background subprocess
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py"],
        env=os.environ.copy()
    )

    print(f"🤖 [Agent]: Analyzing prompt -> '{prompt}'", flush=True)

    try:
        # Establish the dual-way JSON-RPC connection to FastMCP over stdio
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Handshake with the server
                await session.initialize()

                # Fetch dynamically available tools from the server!
                mcp_tools_response = await session.list_tools()

                # Format them into standard OpenAI/Ollama schema
                ollama_tools = []
                for tool in mcp_tools_response.tools:
                    ollama_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema
                        }
                    })

                # Ask Mistral if it wants to use any of these tools based on the voice text
                # Inject a strict System Prompt so Mistral acts intelligently instead of guessing blindly
                system_prompt = """You are an intelligent Ubuntu Desktop MCP assistant.
YOUR CRITICAL RULES:
1. You have access to real system tools (set_volume, browser_youtube_search, play_youtube_video).
2. FIRST, carefully analyze the user's intent. Ask yourself: "Does this request explicitly require me to modify a system setting or control media?"
3. If the user is just chatting, asking a general question, or seeking information, DO NOT use any tools. Just provide a natural text response.
4. Only if the answer to step 2 is YES, you MUST use the appropriate tool.
5. If the user uses the word 'PLAY', you MUST use `play_youtube_video`. DO NOT use `browser_youtube_search`.
6. If using a tool, NEVER write conversational text or explain your intentions. YOU MUST ATTACH A JSON ARRAY containing the tool call. For example:
[{"name": "set_volume", "arguments": {"level": 100}}]
"""
                messages = [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f"Execute this command if a tool matches: '{prompt}'"}
                ]

                response = ollama.chat(
                    model='mistral:latest',
                    messages=messages,
                    tools=ollama_tools
                )

                message_dict = dict(response.get('message', {})) if isinstance(response.get('message', {}), dict) else (
                    getattr(response.get('message', {}), 'model_dump', lambda: dict(response.get('message', {})))())
                content_str = message_dict.get('content', '') or ''
                tool_calls = message_dict.get('tool_calls')

                import re
                import json

                json_match = re.search(
                    r'\[\s*\{.*"name"\s*:.*\}\s*\]', content_str, re.DOTALL)
                if not tool_calls and json_match:
                    try:
                        extracted = json.loads(json_match.group(0))
                        tool_calls = []
                        for t in extracted:
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
                    except Exception as e:
                        print(f"Fallback parse error: {e}", flush=True)

                if message_dict.get('tool_calls'):
                    for tool_call in message_dict['tool_calls']:
                        fn = tool_call.get('function') if isinstance(
                            tool_call, dict) else tool_call.function
                        function_name = fn.get('name') if isinstance(
                            fn, dict) else fn.name
                        function_args = fn.get('arguments') if isinstance(
                            fn, dict) else fn.arguments
                        if isinstance(function_args, str):
                            function_args = json.loads(function_args)

                        print(
                            f"⚡ [Agent]: Mistral decided to run -> {function_name}({function_args})", flush=True)
                        result = await session.call_tool(function_name, arguments=function_args)
                        print(
                            f"✅ [Agent]: Tool returned -> {result.content[0].text}", flush=True)
                else:
                    print(
                        f"💤 [Agent]: Mistral didn't trigger any tools. It says: {content_str[:100]}...", flush=True)

    except Exception as e:
        print(f"❌ [Agent Error]: {str(e)}", flush=True)

# Small test launcher if you run this file directly
if __name__ == "__main__":
    test_prompt = "Hey computer, can you please set the screen brightness to 50 percent?"
    asyncio.run(run_agent(test_prompt))
