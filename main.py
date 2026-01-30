import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import os
from dotenv import load_dotenv
from aiogram.types import BotCommand


# Импортируем наш обработчик старта
from handlers import start

# Загружаем переменные из .env
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Настройка логирования (чтобы видеть, что происходит)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота"""
    
    logger.info("🚀 Запуск бота...")
    
    # Создаём бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создаём диспетчер (обработчик сообщений)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Подключаем обработчики из handlers/start.py
    dp.include_router(start.router)
    
    logger.info("✅ Бот готов к работе!")
    
    # Запускаем бота (он будет ждать сообщений)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⛔ Бот остановлен")
        