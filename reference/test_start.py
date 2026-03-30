import subprocess
try:
    subprocess.Popen('start "" chrome', shell=True)
    print("SUCCESS")
except Exception as e:
    print("ERROR:", e)
