from mcp.server.fastmcp import FastMCP
import subprocess
import urllib.parse
import os

# Initialize our MCP Server tailored for your machine
mcp = FastMCP("UbuntuRemoteTools")


@mcp.tool()
def search_youtube(query: str) -> str:
    """Opens browser to YouTube search results. Use this when the user asks to search for a topic or video but DOES NOT explicitly restrict it to playing a song outright."""
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={encoded_query}"
        subprocess.Popen(["brave-browser", url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Successfully opened Youtube search for: {query}"
    except Exception as e:
        return f"Error opening Brave: {str(e)}"


@mcp.tool()
def play_youtube_video(query: str) -> str:
    """Finds the first video matching the query and auto-plays it in the browser. Use this when the user specifically asks to 'play [song name]' or 'play [video]'."""
    try:
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
        req = urllib.request.Request(
            search_url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req).read().decode('utf-8')

        import re
        video_ids = re.findall(r"watch\?v=(\S{11})", html)
        if not video_ids:
            return f"Could not find any videos for: {query}"

        video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
        subprocess.Popen(["brave-browser", video_url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Now playing first result for: {query}"
    except Exception as e:
        return f"Error playing YouTube video: {str(e)}"


@mcp.tool()
def set_volume(level: int) -> str:
    """Sets system volume. If user says "set volume 60", "say volume 60", or anything phonetically similar, extract the number and set the volume. level must be an integer between 0 and 100."""
    if not 0 <= level <= 100:
        return "Error: Volume level must be between 0 and 100."
    try:
        my_env = os.environ.copy()
        # In background MCP daemons, dbus/xdg flags get wiped. We MUST reconstruct them so pulseaudio accepts the command
        uid = os.getuid()
        my_env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
        my_env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"

        # Try pure amixer with dbus variables back intact
        subprocess.run(["amixer", "-D", "pulse", "sset", "Master",
                       f"{level}%"], check=True, capture_output=True, env=my_env)
        return f"System volume successfully set to {level}%."
    except Exception as e:
        return f"Error setting volume: {str(e)}"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspector", action="store_true",
                        help="Run in inspector mode")
    args = parser.parse_args()

    if args.inspector:
        print("FastMCP internal inspector is deprecated. Please run: npx @modelcontextprotocol/inspector python3 mcp_server.py", flush=True)
        # Using built-in npx inspector is the new standard.
    else:
        mcp.run()
