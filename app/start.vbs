Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c pip install -r requirements.txt -q && playwright install chromium --with-deps && pythonw app.py", 0, False
