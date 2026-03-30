import os
import glob
from pathlib import Path

paths = [
    os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
]

apps = {}

for p in paths:
    for root, dirs, files in os.walk(p):
        for file in files:
            if file.endswith('.lnk'):
                name = file[:-4]
                full_path = os.path.join(root, file)
                apps[name] = full_path

for name in list(apps.keys())[:10]:
    print(name, apps[name])
