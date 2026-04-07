import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import re
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)

class SecurityPolicy:
    def __init__(self, policies_path: Optional[str] = None):
        if policies_path is None:
            # Ищем policies.yaml в папке config относительно проекта
            base = Path(__file__).parent.parent / "config"
            policies_path = base / "policies.yaml"
        else:
            policies_path = Path(policies_path)
        
        self.policies_path = policies_path
        self.forbidden_commands = []
        self.dangerous_patterns = []
        self.requires_approval_keywords = []
        self.load_policies()
    
    def load_policies(self):
        try:
            if self.policies_path.exists():
                with open(self.policies_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    self.forbidden_commands = data.get('forbidden_commands', [])
                    self.dangerous_patterns = data.get('dangerous_patterns', [])
                    self.requires_approval_keywords = data.get('requires_approval_keywords', [
                        "rm", "del", "erase", "format", "reg delete", "shutdown", "net user", 
                        "sc delete", "taskkill", "wmic", "cscript", "powershell -Command"
                    ])
                logger.info(f"Loaded policies from {self.policies_path}")
            else:
                logger.warning(f"Policies file not found: {self.policies_path}, using defaults")
        except Exception as e:
            logger.error(f"Error loading policies: {e}")
    
    def is_command_allowed(self, command: str) -> Tuple[bool, Optional[str]]:
        """
        Проверяет, разрешена ли команда.
        Возвращает (разрешено, причина_запрета)
        """
        command_lower = command.lower().strip()
        
        # Проверка запрещённых команд (точное совпадение или начало)
        for forbidden in self.forbidden_commands:
            if command_lower == forbidden.lower() or command_lower.startswith(forbidden.lower()):
                return False, f"Command '{forbidden}' is forbidden"
        
        # Проверка опасных паттернов (регулярные выражения)
        for pattern in self.dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Dangerous pattern '{pattern}' detected"
        
        return True, None
    
    def requires_approval(self, command: str) -> bool:
        cmd_lower = command.lower()
        for kw in self.requires_approval_keywords:
            if kw.lower() in cmd_lower:
                return True
        return False

    def check_command_safety(self, command: str) -> Dict[str, Any]:
        """Комплексная проверка безопасности команды"""
        allowed, reason = self.is_command_allowed(command)
        if not allowed:
            return {"allowed": False, "requires_approval": False, "reason": reason}
        needs_approval = self.requires_approval(command)
        return {"allowed": True, "requires_approval": needs_approval, "reason": None}

# Глобальный экземпляр
_security_instance = None

def get_security() -> SecurityPolicy:
    global _security_instance
    if _security_instance is None:
        _security_instance = SecurityPolicy()
    return _security_instance

def is_safe_path(base_dir: str, target_path: str) -> bool:
    """Проверяет, находится ли целевой путь внутри разрешённой директории."""
    try:
        base = os.path.realpath(base_dir)
        # Если target_path абсолютный, realpath его обработает.
        # Если относительный, он будет объединён с base.
        target = os.path.realpath(os.path.join(base, target_path))
        return os.path.commonpath([target, base]) == base
    except Exception:
        return False

def is_safe_cd(command: str, workspace_root: str) -> Tuple[bool, Optional[str]]:
    """
    Проверяет команду cd на безопасность.
    Разрешает cd только если целевой путь внутри workspace_root.
    """
    parts = command.split()
    if not parts or parts[0].lower() != "cd":
        return True, None
    
    if len(parts) < 2:
        return True, None # cd без аргументов обычно ведет в HOME, но в нашем контексте это безопасно (никуда не перейдет за пределы shell)
    
    target_dir = parts[1].strip('"\'')
    if is_safe_path(workspace_root, target_dir):
        return True, None
    
    return False, f"Переход в директорию '{target_dir}' запрещён (вне рабочей области)"

def is_command_allowed(command: str, allowed_list: List[str], forbidden_list: List[str], workspace_root: str = None) -> Tuple[bool, Optional[str]]:
    """Проверяет, разрешена ли команда."""
    cmd_lower = command.lower().strip()
    
    # Блокируем опасные паттерны
    for forbidden in forbidden_list:
        if forbidden.lower() in cmd_lower:
            return False, f"Команда содержит запрещённый паттерн: {forbidden}"
    
    # Специальная обработка cd (даже если в цепочке &&)
    if "cd " in cmd_lower:
        # Проверяем основной сегмент cd (упрощенно: первый попавшийся cd)
        # В идеале нужно парсить всю цепочку, но пока ограничимся простейшим
        segments = re.split(r'(&&|;|\|)', command)
        for seg in segments:
            seg = seg.strip()
            if seg.lower().startswith("cd "):
                allowed_cd, reason = is_safe_cd(seg, workspace_root or os.getcwd())
                if not allowed_cd:
                    return False, reason

    # Проверяем начало команды (первое слово)
    first_word = cmd_lower.split()[0] if cmd_lower.split() else ""
    if first_word in allowed_list:
        return True, None
    
    return False, f"Команда '{first_word}' не входит в список разрешённых"

