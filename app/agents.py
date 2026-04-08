import sys, os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import logging
import httpx
import re
from typing import Dict, Any, List, Optional
from settings import (
    API_BASE_URL, API_KEY,
    ARCHITECT_MODEL_REGULAR, ARCHITECT_MODEL_COMPLEX,
    CODE_MODEL, DEBUG_MODEL, REVIEW_MODEL
)
from memory_bank import get_memory_bank
from security import get_security
from utils import extract_text_from_content

logger = logging.getLogger(__name__)


class BaseAgent:
    def __init__(self, name: str, system_prompt: str, model: str):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model

    async def should_skip(self, messages: List[Dict], context: Dict[str, str]) -> bool:
        return False

    def _check_safety(self, response_text: str) -> Dict[str, Any]:
        security = get_security()
        return security.check_command_safety(response_text)

    async def _call_model_with_tools(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages
        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": False
        }
        if tools:
            payload["tools"] = tools
            
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                timeout=120.0
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']

    async def run(self, messages: List[Dict], context: Dict[str, str], available_tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        try:
            message = await self._call_model_with_tools(messages, available_tools)
            if message.get("tool_calls"):
                return {"agent": self.name, "tool_calls": message["tool_calls"], "message_obj": message}
            
            content = message.get("content")
            assistant_message = extract_text_from_content(content)
            logger.info(f"Agent {self.name} completed (model: {self.model})")
            
            # Проверка безопасности только если есть текстовое сообщение
            if assistant_message:
                safety = self._check_safety(assistant_message)
            else:
                safety = {"allowed": True, "requires_approval": False}
                
            if safety.get("requires_approval"):
                logger.warning(f"Agent {self.name} generated command requiring approval")
                return {
                    "agent": self.name,
                    "response": assistant_message,
                    "requires_approval": True,
                    "safety": safety
                }
            return {"agent": self.name, "response": assistant_message}
        except Exception as e:
            logger.error(f"Agent {self.name} failed: {e}")
            return {"agent": self.name, "error": str(e)}

# ----------------------------------------------------------------------
# Улучшенные системные промпты
# ----------------------------------------------------------------------

ARCHITECT_SYSTEM_PROMPT = """Ты — архитектор программного обеспечения. Твоя задача — помогать пользователю пройти путь от идеи до спецификации и плана реализации.

Правила работы:
1. **Сначала план, потом ответ**. Прежде чем дать финальный ответ, составь внутренний план анализа. Если задача сложная, представь план пользователю и дождись подтверждения.
2. **Задавай уточняющие вопросы**. Если требования неясны или противоречивы, задай конкретные вопросы, чтобы согласовать спецификацию.
3. **Фиксируй результат**. После обсуждения сохрани:
   - `spec.md` — согласованную спецификацию (требования, ограничения, критерии успеха).
   - `plan.md` — разбивку на логические тикеты с оценкой сложности.
   - Любые архитектурные решения — в `decisionLog.md`.
4. **Используй Memory Bank**. Перед ответом прочитай актуальные файлы (productContext, activeContext, progress). После ответа обнови activeContext и progress.
5. **Отвечай структурированно**. Используй заголовки, списки, блоки кода только для иллюстрации (не для команд). Будь краток, но содержателен.
6. **Помни про контекст Windows**. Предлагай решения, которые работают в Windows-среде без Docker/WSL, если не оговорено иное."""

CODE_SYSTEM_PROMPT = """Ты — разработчик. Пиши чистый, надёжный, воспроизводимый код.

Правила:
1. **Определи язык программирования** из контекста задачи. Если язык не указан, спроси или используй Python по умолчанию.
2. **Фиксируй зависимости**. Всегда указывай версии библиотек/пакетов. Предлагай изоляцию окружения (виртуальное окружение, требования).
3. **Работай итеративно**. Разбивай задачу на маленькие шаги, коммить изменения с понятными сообщениями. Если есть тесты — запускай их после каждого изменения.
4. **Код должен быть готов к проверке**. Следуй лучшим практикам: понятные имена, обработка ошибок, комментарии для сложных мест. Избегай дублирования.
5. **Формат ответа**: отвечай преимущественно кодом внутри блоков ```язык. Минимум пояснений — только ключевые моменты.
6. **Совместимость**. Если меняешь существующий код, объясни, почему изменения не сломают обратную совместимость.
7. **Используй Memory Bank**. Перед генерацией кода прочитай активные файлы (spec, plan). После генерации обнови activeContext и progress."""

DEBUG_SYSTEM_PROMPT = """Ты — отладчик и QA-инженер. Твоя задача — находить ошибки и предлагать исправления.

Правила:
1. **Анализируй код и окружение**. Проверяй не только синтаксис, но и логические ошибки, проблемы с зависимостями, неучтённые крайние случаи.
2. **Используй чек-лист качества**. Перед анализом прочитай `code_quality_checklist.md` из Memory Bank и следуй ему.
3. **Будь конкретен**. Указывай номер строки (если возможно), тип ошибки и предлагай точное исправление.
4. **Проверяй на типичные баги**:
   - Ошибки Copy-Paste (одинаковые блоки кода).
   - Необработанные исключения.
   - Утечки ресурсов.
   - Проблемы с безопасностью (инъекции, доступ к файлам вне разрешённых папок).
5. **Сообщай о результатах**. Если ошибок нет — напиши "Ошибок не обнаружено". Если ошибки есть — предоставь исправленный код или дифф.
6. **Обновляй Memory Bank**. После работы добавь запись в activeContext и progress, отметь найденные и исправленные проблемы."""

REVIEW_SYSTEM_PROMPT = """Ты — ревьюер. Твоя задача — оценить качество кода и процесса разработки.

Правила:
1. **Проверяй соответствие спецификации**. Сравни код с `spec.md` и `plan.md` из Memory Bank.
2. **Оценивай качество кода**:
   - Читаемость, именование, комментирование.
   - Наличие тестов (если применимо).
   - Следование лучшим практикам для выбранного языка.
3. **Проверяй воспроизводимость**. Указаны ли версии зависимостей? Предложена ли изоляция окружения?
4. **Анализируй безопасность**. Есть ли потенциальные уязвимости? Нарушает ли код политики безопасности?
5. **Выноси вердикт**:
   - **Одобрено** — код готов к принятию.
   - **Требуются доработки** — перечисли конкретные замечания.
   - **Отклонено** — объясни, почему код не может быть принят.
6. **Будь конструктивен**. Критикуй код, не разработчика. Предлагай улучшения.
7. **Обнови Memory Bank**. Запиши результат ревью в progress и decisionLog."""

class ArchitectAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Architect",
            system_prompt=ARCHITECT_SYSTEM_PROMPT,
            model=ARCHITECT_MODEL_REGULAR
        )

class CodeAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Code",
            system_prompt=CODE_SYSTEM_PROMPT,
            model=CODE_MODEL
        )

    async def should_skip(self, messages: List[Dict], context: Dict[str, str]) -> bool:
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content")
                text = extract_text_from_content(content)
                last_user_msg = text.lower()
                break
        if not last_user_msg:
            return True
        code_keywords = ["напиши", "создай", "реализуй", "покажи код", "сгенерируй", "дай код",
                         "напиши функцию", "напиши класс", "напиши программу", "напиши скрипт",
                         "код на", "пример кода", "как написать", "реализация", "исходник"]
        if any(kw in last_user_msg for kw in code_keywords):
            return False
        arch_keywords = ["архитектур", "спроектируй", "структур", "дизайн", "как лучше сделать"]
        if any(kw in last_user_msg for kw in arch_keywords):
            logger.info("CodeAgent skipping: architecture discussion without code request")
            return True
        arch_resp = context.get("activeContext.md", "").lower()
        if "```" in arch_resp and ("код" in arch_resp or "функция" in arch_resp):
            logger.info("CodeAgent skipping: Architect already provided code")
            return True
        logger.info("CodeAgent skipping: no code request")
        return True

class DebugAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Debug",
            system_prompt=DEBUG_SYSTEM_PROMPT,
            model=DEBUG_MODEL
        )

    async def should_skip(self, messages: List[Dict], context: Dict[str, str]) -> bool:
        active = context.get("activeContext.md", "")
        has_code = "```" in active or bool(re.search(r'(def |class |import |print\()', active))
        if not has_code:
            logger.info("DebugAgent skipping: no code found")
            return True
        last_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content")
                text = extract_text_from_content(content)
                last_msg = text.lower()
                break
        if not last_msg:
            return True
        debug_words = ["ошибк", "баг", "не работает", "debug", "отлад", "исправ", "почему не", "сбой"]
        if any(kw in last_msg for kw in debug_words):
            return False
        if any(kw in last_msg for kw in ["напиши", "создай", "как сделать"]):
            logger.info("DebugAgent skipping: code request, not debugging")
            return True
        logger.info("DebugAgent skipping: code present but no debug request")
        return True

class ReviewAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Review",
            system_prompt=REVIEW_SYSTEM_PROMPT,
            model=REVIEW_MODEL
        )

    async def should_skip(self, messages: List[Dict], context: Dict[str, str]) -> bool:
        active = context.get("activeContext.md", "")
        has_code = "```" in active or bool(re.search(r'(def |class |import )', active))
        if not has_code:
            logger.info("ReviewAgent skipping: no code to review")
            return True
        last_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content")
                text = extract_text_from_content(content)
                last_msg = text.lower()
                break
        if not last_msg:
            return True
        review_words = ["ревью", "проверь", "качество", "безопасность", "оцени", "найди ошибки"]
        if any(kw in last_msg for kw in review_words):
            return False
        if any(kw in last_msg for kw in ["напиши", "создай", "реализуй"]):
            logger.info("ReviewAgent skipping: code requested but no review request")
            return True
        logger.info("ReviewAgent skipping: no review request")
        return True

AGENTS_ORDER = [ArchitectAgent(), CodeAgent(), DebugAgent(), ReviewAgent()]

async def run_sequential_pipeline(initial_messages: List[Dict], agents_filter: Optional[List[str]] = None) -> Dict[str, Any]:
    from tools import TOOLS_SCHEMAS
    from tool_executor import execute_tool_call
    import json
    from app.router import route_request
    from utils import extract_text_from_content
    
    memory_bank = get_memory_bank()
    context = memory_bank.get_full_context()
    messages = initial_messages.copy()
    results = {}
    
    # Извлечение последнего сообщения пользователя для роутера
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            last_user_msg = extract_text_from_content(content)
            break
            
    # Запрос к роутеру
    router_decision = await route_request(last_user_msg)
    logger.info(f"Router decision: {router_decision}")
    
    agents_from_router = router_decision.get("agents", ["Architect", "Code"])
    complexity = router_decision.get("complexity", "simple")
    
    # Если передан фильтр agents_filter, пересекаем его с router_decision
    if agents_filter is not None:
        agents_from_router = [a for a in agents_from_router if a in agents_filter]
        
    agents_to_run = [a for a in AGENTS_ORDER if a.name in agents_from_router]
    
    for agent in agents_to_run:
        # Динамическое назначение модели для Architect
        if agent.name == "Architect":
            agent.model = ARCHITECT_MODEL_COMPLEX if complexity == "complex" else ARCHITECT_MODEL_REGULAR
            logger.info(f"Architect using model: {agent.model}")
        if await agent.should_skip(messages, context):
            logger.info(f"Agent {agent.name} skipped")
            results[agent.name] = {"status": "skipped", "agent": agent.name}
            continue
            
        context_text = "\n".join([f"# {filename}\n{content}" for filename, content in context.items()])
        agent_messages = messages + [{"role": "user", "content": f"Current project context:\n{context_text}"}]
        
        # Определяем доступные инструменты для конкретного агента
        if agent.name == "Debug" or agent.name == "Review":
            available_tools = [t for t in TOOLS_SCHEMAS if t["function"]["name"] in ["read_file", "list_dir"]]
        else:
            available_tools = TOOLS_SCHEMAS
            
        iteration = 0
        MAX_ITERATIONS = 10
        blocked_commands_tracker = {} # command -> count

        while iteration < MAX_ITERATIONS:
            iteration += 1
            agent_result = await agent.run(agent_messages, context, available_tools=available_tools)
            
            if "error" in agent_result:
                results[agent.name] = agent_result
                logger.error(f"Pipeline stopped due to error in {agent.name}")
                break
                
            if "tool_calls" in agent_result:
                if agent.name not in results:
                    results[agent.name] = {}
                if "tool_calls" not in results[agent.name]:
                    results[agent.name]["tool_calls"] = []
                results[agent.name]["tool_calls"].extend(agent_result["tool_calls"])
                
                # Добавляем сообщение с tool_calls в историю
                agent_messages.append(agent_result["message_obj"])
                
                # Выполняем каждый инструмент
                for tool_call in agent_result["tool_calls"]:
                    res = await execute_tool_call(tool_call)
                    
                    # Проверка на зацикливание заблокированных команд
                    if res.get("blocked"):
                        func = tool_call.get("function", {})
                        args = func.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except:
                                args = {}
                        cmd = args.get("command", "")
                        blocked_commands_tracker[cmd] = blocked_commands_tracker.get(cmd, 0) + 1
                        if blocked_commands_tracker[cmd] >= 2:
                            error_msg = f"Команда '{cmd}' заблокирована политикой безопасности. Пожалуйста, не пытайтесь выполнить её снова."
                            res = {"error": error_msg, "final_block": True}
                            logger.warning(f"Repeated blocked command detected: {cmd}")

                    agent_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": tool_call["function"]["name"],
                        "content": json.dumps(res, ensure_ascii=False)
                    })
                # Делаем следующий виток цикла, чтобы отправить результаты в модель
                continue
            else:
                # Получен текстовый ответ от агента
                if agent.name in results and "tool_calls" in results[agent.name]:
                    agent_result["tool_calls"] = results[agent.name]["tool_calls"]
                results[agent.name] = agent_result
                if agent_result.get("requires_approval"):
                    logger.info(f"Agent {agent.name} requires approval, pausing pipeline")
                    results[agent.name]["requires_approval"] = True
                    break
                    
                # Нормальное завершение агента
                memory_bank.update_context(agent.name, agent_result.get("response", ""))
                messages.append({"role": "assistant", "content": f"[{agent.name}]: {agent_result.get('response', '')}"})
                context = memory_bank.get_full_context()
                break # Выход из while True для перехода к следующему агенту
        
        if iteration >= MAX_ITERATIONS:
            logger.warning(f"Agent {agent.name} reached MAX_ITERATIONS ({MAX_ITERATIONS})")
            if agent.name not in results:
                results[agent.name] = {"error": "Превышено максимальное количество итераций вызова инструментов."}
                
        if "error" in agent_result or agent_result.get("requires_approval"):
            break

    summary_lines = []
    for name, res in results.items():
        if not isinstance(res, dict):
            continue
        if res.get("status") == "skipped":
            summary_lines.append(f"- {name}: пропущен")
        elif "error" in res:
            summary_lines.append(f"- {name}: ошибка - {res['error']}")
        elif res.get("requires_approval"):
            summary_lines.append(f"- {name}: требуется подтверждение")
        else:
            summary_lines.append(f"- {name}: выполнено")
    results["_summary"] = "## Отчёт о выполнении агентов\n" + "\n".join(summary_lines)
    
    # Извлекаем последний содержательный ответ
    final_response = None
    for agent_instance in reversed(AGENTS_ORDER):
        agent_name = agent_instance.name
        if agent_name in results and "response" in results[agent_name]:
            final_response = results[agent_name]["response"]
            break
            
    if not final_response:
        final_response = results.get("_summary", "Задача выполнена, но ответ не получен.")
        
    results["_final_response"] = final_response
    
    return results
