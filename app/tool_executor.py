import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import logging
from typing import Dict, Any, List
import json
import tools

logger = logging.getLogger(__name__)

def safe_parse_arguments(arguments: Any) -> Dict[str, Any]:
    """Безопасно парсит аргументы, даже если они приходят в виде строки или с ошибками."""
    if not arguments:
        return {}
        
    if isinstance(arguments, dict):
        return arguments
        
    if isinstance(arguments, str):
        try:
            # Модели иногда могут возвращать JSON с лишними пробелами или переносами
            return json.loads(arguments.strip())
        except Exception as e:
            logger.error(f"Failed to parse arguments: {e}")
            return {"error": f"Failed to parse arguments: {e}"}
            
    return {"error": f"Invalid arguments type: {type(arguments)}"}

async def execute_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """Выполняет один tool_call и возвращает результат."""
    tool_name = tool_call.get("function", {}).get("name")
    raw_arguments = tool_call.get("function", {}).get("arguments", {})
    
    # Используем безопасный парсинг
    arguments = safe_parse_arguments(raw_arguments)
    
    if "error" in arguments:
        return arguments
            
    # Сопоставление имени функции с реализацией
    if tool_name == "write_file":
        return await tools.write_file(arguments.get("relative_path"), arguments.get("content"))
    elif tool_name == "read_file":
        return await tools.read_file(arguments.get("relative_path"))
    elif tool_name == "list_dir":
        return await tools.list_dir(arguments.get("relative_path", ""))
    elif tool_name == "create_folder":
        return await tools.create_folder(arguments.get("relative_path"))
    elif tool_name == "run_command":
        return await tools.run_command(arguments.get("command"))
    elif tool_name == "run_server":
        return await tools.run_server(arguments.get("relative_path"), arguments.get("port", 8080))
    else:
        return {"error": f"Unknown tool: {tool_name}"}
