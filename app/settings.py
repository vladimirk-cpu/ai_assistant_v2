import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY = os.getenv("API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek/deepseek-chat")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Модели агентов
ARCHITECT_MODEL_REGULAR = os.getenv("ARCHITECT_MODEL_REGULAR", "deepseek/deepseek-v3.2")
ARCHITECT_MODEL_COMPLEX = os.getenv("ARCHITECT_MODEL_COMPLEX", "deepseek/deepseek-r1")
CODE_MODEL = os.getenv("CODE_MODEL", "qwen/qwen3-coder")
DEBUG_MODEL = os.getenv("DEBUG_MODEL", "deepseek/deepseek-v3.2")
REVIEW_MODEL = os.getenv("REVIEW_MODEL", "deepseek/deepseek-v3.2")

# Пути к директориям
MEMORY_BANK_PATH = os.getenv("MEMORY_BANK_PATH", os.path.join(os.environ.get("APPDATA", ""), "AI-Assistant", "memory-bank"))
LOGS_PATH = os.getenv("LOGS_PATH", os.path.join(os.environ.get("APPDATA", ""), "AI-Assistant", "logs"))

# Для совместимости с Windows
if not os.path.exists(MEMORY_BANK_PATH):
    os.makedirs(MEMORY_BANK_PATH, exist_ok=True)
if not os.path.exists(LOGS_PATH):
    os.makedirs(LOGS_PATH, exist_ok=True)

# Безопасность и песочница
WORKSPACE_ROOT = os.getenv("AGENT_WORKSPACE", os.path.join(os.environ.get("USERPROFILE", ""), "AI-Assistant", "workspace"))
ALLOWED_COMMANDS = os.getenv("ALLOWED_COMMANDS", "git,pip,npm,npx,python,node,live-server,http-server,echo,mkdir,rm,touch,cat,cd").split(',')
FORBIDDEN_COMMANDS = os.getenv("FORBIDDEN_COMMANDS", "sudo,shutdown,format,reg,taskkill,net user,sc,wmic,powershell").split(',')

