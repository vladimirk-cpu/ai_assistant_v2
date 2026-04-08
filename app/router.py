import json
import logging
import httpx
from typing import Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_ROUTING = {
    "task_type": "general",
    "complexity": "regular",
    "agents": ["Architect", "Code"],
    "reason": "fallback"
}

async def route_request(user_message: str) -> Dict[str, Any]:
    if not user_message or len(user_message.strip()) < 3:
        logger.info("Router: пустой запрос, возвращаю fallback")
        return DEFAULT_ROUTING

    prompt = f"""Ты — интеллектуальный роутер. Проанализируй запрос пользователя и верни ТОЛЬКО JSON (без пояснений) в формате:
{{
"task_type": "coding|debugging|review|research|general",
"complexity": "simple|regular|complex",
"agents": ["Architect", "Code", "Debug", "Review"],
"reason": "краткое объяснение"
}}

Запрос: {user_message}
"""

    try:
        from app.settings import API_BASE_URL, API_KEY, ROUTER_MODEL
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": ROUTER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 500
                }
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if "```json" in content: 
                content = content.split("```json")[1].split("```")[0] 
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            routing = json.loads(content.strip())
            if not all(k in routing for k in ("task_type", "complexity", "agents", "reason")):
                raise ValueError("Missing fields")
            logger.info(f"Router decision: {routing}")
            return routing
    except Exception as e:
        logger.error(f"Router failed: {e}, using fallback")
        return DEFAULT_ROUTING
