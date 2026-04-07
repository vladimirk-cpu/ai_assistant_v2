@echo off
cd /d D:\Вайбкодинг\ai_assistant_v2
echo Installing pyinstaller...
pip install pyinstaller
echo Building exe...
pyinstaller --onefile --name ai-assistant --paths app --add-data "config;config" --hidden-import=uvicorn --hidden-import=httpx --hidden-import=dotenv app\main.py
echo Done. Exe is in dist\ai-assistant.exe
