import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import logging
from typing import Union, List, Dict, Any
import httpx
from settings import API_BASE_URL, API_KEY

logger = logging.getLogger(__name__)

async def call_model(payload: dict) -> str:
    """Универсальный вызов модели OpenRouter, возвращает текстовый ответ."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0
        )
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']

def extract_text_from_content(content: Union[str, List[Dict[str, Any]]]) -> str:
    """
    Извлекает текстовое содержимое из поля `content`, которое может быть:
    - строкой (обычный текст)
    - списком частей в формате Roo Code: [{"type": "text", "text": "..."}]
    Возвращает строку.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        return " ".join(text_parts)
    # fallback
    return str(content)
