import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import re
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from settings import MEMORY_BANK_PATH

logger = logging.getLogger(__name__)

class MemoryBank:
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path or MEMORY_BANK_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        logger.info(f"MemoryBank initialized at {self.base_path}")
    
    def _validate_filename(self, filename: str) -> bool:
        """Разрешить только безопасные имена файлов (без path traversal)"""
        # Запрещаем любые разделители путей, точки в начале и спецсимволы
        if not filename:
            return False
        if '..' in filename or '/' in filename or '\\' in filename:
            return False
        # Разрешаем буквы, цифры, точки, дефисы, подчёркивания
        if not re.match(r'^[\w\-.]+$', filename):
            return False
        return True
    
    def _get_file_path(self, filename: str) -> Optional[Path]:
        if not self._validate_filename(filename):
            logger.error(f"Invalid filename: {filename}")
            return None
        return self.base_path / filename
    
    def read(self, filename: str) -> str:
        file_path = self._get_file_path(filename)
        if not file_path:
            return ""
        try:
            with self._lock:
                if not file_path.exists():
                    logger.warning(f"File {filename} not found")
                    return ""
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Error reading {filename}: {e}")
            return ""
    
    def write(self, filename: str, content: str, append: bool = False):
        file_path = self._get_file_path(filename)
        if not file_path:
            return
        try:
            with self._lock:
                mode = 'a' if append else 'w'
                with open(file_path, mode, encoding='utf-8') as f:
                    f.write(content)
                logger.debug(f"Written to {filename} (append={append})")
        except Exception as e:
            logger.error(f"Error writing to {filename}: {e}")
    
    def update_context(self, agent_name: str, result: str):
        new_entry = f"\n## {agent_name}\n{result}\n"
        self.write("activeContext.md", new_entry, append=True)
        logger.info(f"Updated activeContext with {agent_name}")
    
    def get_full_context(self) -> Dict[str, str]:
        files = ["productContext.md", "activeContext.md", "progress.md", "decisionLog.md", "checklists.md", "code_quality_checklist.md"]
        context = {}
        for fname in files:
            content = self.read(fname)
            if content:
                context[fname] = content
        return context
    
    def initialize_defaults(self):
        defaults = {
            "productContext.md": "# Product Context\n## Цель проекта\nСоздать локального AI-агента для Windows.\n\n## Текущая миссия\nРазработать приложение с Sequential-протоколом.\n",
            "activeContext.md": "# Active Context\n## Последние действия\nИнициализация Memory Bank.\n",
            "progress.md": "# Progress\n## Выполнено\n- Создан базовый HTTP-сервер FastAPI\n- Настроено проксирование в OpenRouter\n- Memory Bank с блокировками\n\n## В работе\n- Планировщик Sequential\n\n## Следующие шаги\n- Безопасность и политики\n",
            "decisionLog.md": "# Decision Log\n## 2026-04-03: Выбор архитектуры\nПринято решение использовать Memory Bank на файлах, Sequential-протокол, отказ от MCP.\n",
            "checklists.md": "# Checklists\n## Архитектура\n- [x] FastAPI сервер\n- [x] Прокси в OpenRouter\n- [ ] Планировщик с очередью\n- [ ] Безопасность и политики\n",
            "code_quality_checklist.md": "# Code Quality Checklist\n\n## Перед отправкой кода проверь:\n\n### Общее\n- [ ] Код читаем и понятен (осмысленные имена переменных/функций)\n- [ ] Есть обработка ошибок (try/except, проверки граничных условий)\n- [ ] Нет закомментированного кода или отладочных print\n- [ ] Код не дублируется (вынесены повторяющиеся части)\n\n### Зависимости\n- [ ] Указаны версии всех библиотек/пакетов\n- [ ] Предложена изоляция окружения (venv, requirements.txt)\n\n### Безопасность (Windows)\n- [ ] Нет опасных команд (rm -rf, del /f /s, reg delete и т.д.)\n- [ ] Работа с файлами только в разрешённых папках\n- [ ] Нет инъекций (eval, exec на пользовательском вводе)\n\n### Тестируемость\n- [ ] Код можно протестировать (функции не слишком длинные, нет жёстких зависимостей)\n- [ ] Есть хотя бы пример использования\n\n### Совместимость\n- [ ] Если меняется существующий код, не нарушена обратная совместимость\n"
        }
        for fname, content in defaults.items():
            if not self._get_file_path(fname):
                continue
            if not self._get_file_path(fname).exists():
                self.write(fname, content)
                logger.info(f"Created default {fname}")

_memory_bank_instance = None

def get_memory_bank() -> MemoryBank:
    global _memory_bank_instance
    if _memory_bank_instance is None:
        _memory_bank_instance = MemoryBank()
        _memory_bank_instance.initialize_defaults()
    return _memory_bank_instance
