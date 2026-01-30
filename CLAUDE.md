# Claude Code Instructions

## Проект

Telegram квиз-бот на Python с использованием aiogram 3.x.

## Структура проекта

- `main.py` — точка входа, запуск бота
- `config.py` — конфигурация и тексты сообщений
- `handlers/` — обработчики команд и сообщений
- `scoring.py` — логика подсчёта результатов
- `analytics.py` — сбор статистики

## Запуск

```bash
source venv/bin/activate
python main.py
```

## Зависимости

- aiogram >= 3.4.0
- python-dotenv

Установка: `pip install -r requirements.txt`

## Переменные окружения

Файл `.env`:
- `BOT_TOKEN` — токен Telegram бота

## Стиль кода

- Язык комментариев и сообщений: русский
- Асинхронный код (async/await)
- Типизация по возможности
