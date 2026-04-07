import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import logging
from typing import Dict, Any, List
import json
import tools

logger = logging.getLogger(__name__)

async def execute_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """Выполняет один tool_call и возвращает результат."""
    tool_name = tool_call.get("function", {}).get("name")
    arguments = tool_call.get("function", {}).get("arguments", {})
    
    # arguments приходят как JSON-строка, нужно распарсить
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception as e:
            logger.error(f"Failed to parse arguments: {e}")
            arguments = {}
            
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
