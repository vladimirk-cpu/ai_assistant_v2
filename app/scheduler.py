import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import queue
import threading
import logging
import asyncio
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        self.task_queue = queue.Queue()
        self.worker_thread = None
        self.is_running = False
        self.processor: Optional[Callable] = None  # функция-обработчик
    
    def set_processor(self, processor: Callable):
        """Устанавливает асинхронную функцию для обработки задач"""
        self.processor = processor
    
    def start(self):
        if self.is_running:
            logger.warning("Scheduler already running")
            return
        if not self.processor:
            logger.error("No processor set. Call set_processor() first.")
            return
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._process_tasks, daemon=True)
        self.worker_thread.start()
        logger.info("Scheduler started")
    
    def stop(self):
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Scheduler stopped")
    
    def add_task(self, task: Dict[str, Any]):
        self.task_queue.put(task)
        logger.debug(f"Task added: {task.get('id', 'unknown')}")
    
    def _process_tasks(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while self.is_running:
            try:
                task = self.task_queue.get(timeout=1)
                task_id = task.get('id', 'unknown')
                logger.info(f"Processing task: {task_id}")
                try:
                    # Вызываем асинхронную функцию-обработчик
                    if self.processor:
                        loop.run_until_complete(self.processor(task_id, task.get('payload', {})))
                    else:
                        logger.error("No processor set for task")
                        # Отметим задачу как ошибочную где-то (например, через глобальное хранилище)
                    self.task_queue.task_done()
                except Exception as e:
                    logger.error(f"Error processing task {task_id}: {e}")
                    self.task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in scheduler loop: {e}")
        loop.close()

# Глобальный экземпляр
_scheduler_instance = None

def get_scheduler() -> Scheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = Scheduler()
    return _scheduler_instance
