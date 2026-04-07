import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import asyncio
import subprocess
import logging
from typing import Dict, Any
from settings import WORKSPACE_ROOT, ALLOWED_COMMANDS, FORBIDDEN_COMMANDS, LOGS_PATH
from security import is_safe_path, is_command_allowed
from utils import extract_text_from_content

logger = logging.getLogger(__name__)

def _ensure_workspace():
    """Создаёт рабочую папку, если её нет."""
    os.makedirs(WORKSPACE_ROOT, exist_ok=True)

async def write_file(relative_path: str, content: str) -> Dict[str, Any]:
    """Записывает содержимое в файл внутри рабочей папки."""
    content_text = extract_text_from_content(content)
    _ensure_workspace()
    full_path = os.path.join(WORKSPACE_ROOT, relative_path)
    if not is_safe_path(WORKSPACE_ROOT, full_path):
        return {"error": f"Access denied: path outside workspace"}
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content_text)
        logger.info(f"File written: {full_path}")
        return {"success": True, "path": full_path}
    except Exception as e:
        logger.error(f"Write failed: {e}")
        return {"error": str(e)}

async def read_file(relative_path: str) -> Dict[str, Any]:
    """Читает содержимое файла внутри рабочей папки."""
    _ensure_workspace()
    full_path = os.path.join(WORKSPACE_ROOT, relative_path)
    if not is_safe_path(WORKSPACE_ROOT, full_path):
        return {"error": "Access denied"}
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"success": True, "content": content, "path": full_path}
    except FileNotFoundError:
        return {"error": "File not found"}
    except Exception as e:
        return {"error": str(e)}

async def list_dir(relative_path: str = "") -> Dict[str, Any]:
    """Возвращает список файлов и папок внутри рабочей папки."""
    _ensure_workspace()
    full_path = os.path.join(WORKSPACE_ROOT, relative_path)
    if not is_safe_path(WORKSPACE_ROOT, full_path):
        return {"error": "Access denied"}
    try:
        items = os.listdir(full_path)
        return {"success": True, "path": full_path, "items": items}
    except Exception as e:
        return {"error": str(e)}

async def create_folder(relative_path: str) -> Dict[str, Any]:
    """Создаёт папку внутри рабочей папки."""
    _ensure_workspace()
    full_path = os.path.join(WORKSPACE_ROOT, relative_path)
    if not is_safe_path(WORKSPACE_ROOT, full_path):
        return {"error": "Access denied"}
    try:
        os.makedirs(full_path, exist_ok=True)
        return {"success": True, "path": full_path}
    except Exception as e:
        return {"error": str(e)}

async def run_command(command: str) -> Dict[str, Any]:
    """Выполняет команду в рабочей папке (только разрешённые команды)."""
    _ensure_workspace()
    allowed, reason = is_command_allowed(command, ALLOWED_COMMANDS, FORBIDDEN_COMMANDS, workspace_root=WORKSPACE_ROOT)
    if not allowed:
        logger.warning(f"Command blocked: {command} - {reason}")
        return {"error": reason, "blocked": True}
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=WORKSPACE_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return {
            "success": process.returncode == 0,
            "returncode": process.returncode,
            "stdout": stdout.decode('utf-8', errors='replace'),
            "stderr": stderr.decode('utf-8', errors='replace')
        }
    except Exception as e:
        return {"error": str(e)}

async def run_server(relative_path: str, port: int = 8080) -> Dict[str, Any]:
    """Запускает веб-сервер (live-server или http.server)."""
    _ensure_workspace()
    full_path = os.path.join(WORKSPACE_ROOT, relative_path)
    if not is_safe_path(WORKSPACE_ROOT, full_path):
        return {"error": "Access denied: path outside workspace"}
    
    # Пытаемся запустить npx live-server
    command = f'npx live-server "{full_path}" --port={port} --no-browser'
    res = await run_command(command)
    
    if res.get("error") and not res.get("blocked"):
        # Если не сработал live-server, пробуем python http.server
        logger.info("live-server failed, falling back to python http.server")
        command = f'python -m http.server --directory "{full_path}" {port}'
        return await run_command(command)
    
    return res

# Схемы инструментов для OpenAI (будут использоваться позже)
TOOLS_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Записать содержимое в файл",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string", "description": "Путь относительно workspace"},
                    "content": {"type": "string", "description": "Содержимое файла"}
                },
                "required": ["relative_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Прочитать содержимое файла",
            "parameters": {
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": ["relative_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "Показать содержимое папки",
            "parameters": {
                "type": "object",
                "properties": {"relative_path": {"type": "string", "default": ""}}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Создать папку",
            "parameters": {
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": ["relative_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Выполнить команду в терминале (разрешены только: git, pip, npm, python, node, live-server, cd и др.)",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_server",
            "description": "Запустить веб-сервер в указанной директории",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string", "description": "Путь до папки с сайтом"},
                    "port": {"type": "integer", "default": 8080}
                },
                "required": ["relative_path"]
            }
        }
    }
]
