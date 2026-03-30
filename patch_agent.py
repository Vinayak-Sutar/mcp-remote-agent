code = open('agent.py', 'r').read()

part1 = code.split("response = ollama.chat(")[0]
part2 = """response = ollama.chat(
                    model='mistral:latest',
                    messages=messages,
                    tools=ollama_tools
                )
                
                message_dict = dict(response.get('message', {})) if isinstance(response.get('message', {}), dict) else (getattr(response.get('message', {}), 'model_dump', lambda: dict(response.get('message', {})))())
                content_str = message_dict.get('content', '') or ''
                tool_calls = message_dict.get('tool_calls')

                import re
                import json
                
                json_match = re.search(r'\\[\\s*\\{.*"name"\\s*:\\s*".*"\\}\\s*\\]', content_str, re.DOTALL)
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
                        fn = tool_call.get('function') if isinstance(tool_call, dict) else tool_call.function
                        function_name = fn.get('name') if isinstance(fn, dict) else fn.name
                        function_args = fn.get('arguments') if isinstance(fn, dict) else fn.arguments
                        if isinstance(function_args, str):
                            function_args = json.loads(function_args)
                        
                        print(f"⚡ [Agent]: Mistral decided to run -> {function_name}({function_args})", flush=True)
                        result = await session.call_tool(function_name, arguments=function_args)
                        print(f"✅ [Agent]: Tool returned -> {result.content[0].text}", flush=True)
                else:
                    print(f"💤 [Agent]: Mistral didn't trigger any tools. It says: {content_str[:100]}...", flush=True)
"""

part3 = code.split("print(f\"💤 [Agent]: Mistral didn't trigger any tools. It says: {response['message']['content'][:100]}...\", flush=True)")[1]

with open('agent.py', 'w') as f:
    f.write(part1 + part2 + part3)

print("Agent successfully patched!")
