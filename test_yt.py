import urllib.request
import urllib.parse
import re

query = urllib.parse.quote("never gonna give you up")
url = f"https://www.youtube.com/results?search_query={query}"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')
video_ids = re.findall(r"watch\?v=(\S{11})", html)
print(video_ids[0] if video_ids else "None")
