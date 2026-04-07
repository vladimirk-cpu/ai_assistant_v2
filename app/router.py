import json
import logging
import asyncio
from typing import Dict, Any, List
from settings import API_BASE_URL, API_KEY, ARCHITECT_MODEL_REGULAR
from utils import call_model

logger = logging.getLogger(__name__)

ROUTER_PROMPT = """Ты — интеллектуальный маршрутизатор запросов для мультиагентной системы. Проанализируй сообщение пользователя и определи:

1. Тип задачи (один из: architecture, code, debug, review, mixed).
2. Сложность (simple или complex). Simple — если задача не требует глубокого рассуждения, complex — если нужен сложный анализ, планирование, архитектура.
3. Какие агенты должны быть вызваны (список из: Architect, Code, Debug, Review). Порядок должен быть логичным (Architect перед Code, Debug и Review после).

Ответь ТОЛЬКО в формате JSON, без пояснений:
{
    "task_type": "code",
    "complexity": "simple",
    "agents": ["Code"],
    "reason": "Краткое пояснение решения"
}
"""

async def route_request(user_message: str) -> Dict[str, Any]:
    """
    Отправляет запрос на модель и возвращает решение о маршрутизации.
    В случае ошибки возвращает fallback.
    """
    try:
        messages = [
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user", "content": user_message}
        ]
        payload = {
            "model": ARCHITECT_MODEL_REGULAR,  # deepseek/deepseek-v3.2 или другая из конфигурации
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 300
        }
        response = await asyncio.wait_for(
            call_model(payload),
            timeout=10.0
        )
        # Очистка возможных маркеров markdown
        response = response.strip().strip('```json').strip('```').strip()
        result = json.loads(response)
        # Валидация
        if not isinstance(result.get("agents"), list):
            raise ValueError("agents not a list")
        return result
    except Exception as e:
        logger.error(f"Router failed: {e}, using fallback")
        return {
            "task_type": "mixed",
            "complexity": "simple",
            "agents": ["Architect", "Code"],
            "reason": "fallback due to error"
        }
