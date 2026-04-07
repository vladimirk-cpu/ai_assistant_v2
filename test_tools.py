import asyncio
import sys
sys.path.insert(0, r'D:\Вайбкодинг\ai_assistant_v2\app')
from tools import write_file, read_file, list_dir, create_folder, run_command
from config import WORKSPACE_ROOT

async def test():
    print(f"Workspace root: {WORKSPACE_ROOT}")
    
    # 1. Создание папки
    res = await create_folder("test_folder")
    print("create_folder:", res)
    
    # 2. Запись файла
    res = await write_file("test_folder/hello.txt", "Hello, AI Assistant!")
    print("write_file:", res)
    
    # 3. Чтение файла
    res = await read_file("test_folder/hello.txt")
    print("read_file:", res)
    
    # 4. Список папки
    res = await list_dir("test_folder")
    print("list_dir:", res)
    
    # 5. Выполнение разрешённой команды
    res = await run_command("echo Test command")
    print("run_command (echo):", res)
    
    # 6. Попытка выполнить запрещённую команду (должна быть ошибка)
    res = await run_command("sudo echo test")
    print("run_command (sudo):", res)
    
    # 7. Попытка выйти за пределы workspace (должна быть ошибка)
    res = await write_file("../outside.txt", "Should fail")
    print("write_file outside workspace:", res)

if __name__ == "__main__":
    asyncio.run(test())