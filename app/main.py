import logging
from logging.handlers import RotatingFileHandler
import uuid
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import httpx
import os
import sys
import io
import time

# Обеспечиваем работу с UTF-8 в консоли Windows
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

# Добавим путь к папке app для корректных импортов
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Абсолютные импорты (без точек)
from settings import API_BASE_URL, API_KEY, MODEL_NAME, LOGS_PATH
from scheduler import get_scheduler
from memory_bank import get_memory_bank
from security import get_security
from agents import run_sequential_pipeline

# Настройка логирования
logs_path = Path(LOGS_PATH) if isinstance(LOGS_PATH, str) else LOGS_PATH
logs_path.mkdir(parents=True, exist_ok=True)
log_file = logs_path / "app.log"

file_handler = RotatingFileHandler(
    log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Assistant Local Agent")
scheduler = get_scheduler()
memory_bank = get_memory_bank()
security = get_security()

_task_results = {}

async def process_chat_task(task_id: str, payload: dict):
    messages = payload.get("messages", [])
    agents_filter = payload.get("agents", None)
    try:
        result = await run_sequential_pipeline(messages, agents_filter=agents_filter)
        _task_results[task_id] = {"status": "completed", "result": result, "error": None}
        logger.info(f"Task {task_id} completed with sequential pipeline")
    except Exception as e:
        _task_results[task_id] = {"status": "failed", "result": None, "error": str(e)}
        logger.error(f"Task {task_id} failed: {e}")

@app.on_event("startup")
async def startup_event():
    scheduler.set_processor(process_chat_task)
    scheduler.start()
    logger.info("Application started")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.stop()
    logger.info("Application stopped")

class ChatRequest(BaseModel):
    model: Optional[str] = None
    messages: list
    temperature: float = 0.7
    max_tokens: int = 1000
    stream: bool = False
    agents: Optional[List[str]] = None

class TaskResponse(BaseModel):
    task_id: str
    status: str

class TaskResult(BaseModel):
    task_id: str
    status: str
    result: dict = None
    error: Optional[str] = None

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest, async_mode: bool = Query(False, alias="async")):
    # Потоковая передача пока не поддерживается, принудительно отключаем
    if request.stream:
        logger.info("Streaming requested but not supported, forcing stream=False")
        request.stream = False

    if async_mode:
        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "type": "chat_completion",
            "payload": request.dict(),
            "status": "queued"
        }
        scheduler.add_task(task)
        _task_results[task_id] = {"status": "queued", "result": None, "error": None}
        logger.info(f"Task {task_id} queued")
        return TaskResponse(task_id=task_id, status="queued")
    else:
        # Синхронный режим — ждём результат
        messages = request.messages
        agents_filter = request.agents
        try:
            result = await run_sequential_pipeline(messages, agents_filter=agents_filter)
            final_response = result.get("_final_response", "Нет ответа")
            tool_calls = []
            
            # Проверяем, есть ли tool_calls от последнего агента
            for agent_result in result.values():
                if isinstance(agent_result, dict) and "tool_calls" in agent_result:
                    tool_calls = agent_result["tool_calls"]
                    break
            
            response_body = {
                "id": f"chatcmpl-{uuid.uuid4().hex}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model or "local",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": final_response,
                        "tool_calls": tool_calls
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            }
            
            # Логируем полный ответ для отладки
            logger.info(f"Response body: {response_body}")
            
            return response_body
        except Exception as e:
            logger.error(f"Sync task failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/task/{task_id}")
async def get_task_status(task_id: str) -> TaskResult:
    result = _task_results.get(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResult(
        task_id=task_id,
        status=result["status"],
        result=result.get("result"),
        error=result.get("error")
    )

@app.get("/health")
async def health():
    return {"status": "ok"}

# Для совместимости с Roo Code (без префикса /v1)
@app.post("/chat/completions")
async def chat_completions_no_v1(request: ChatRequest, async_mode: bool = Query(False, alias="async")):
    """Редирект на основной эндпоинт /v1/chat/completions"""
    return await chat_completions(request, async_mode=async_mode)

# Эндпоинт для получения списка моделей (Roo Code запрашивает /models)
@app.get("/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "local",
                "object": "model",
                "created": 0,
                "owned_by": "local"
            }
        ]
    }

# Обработка возможного двойного слеша (//models)
@app.get("//models")
async def list_models_double():
    return await list_models()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)