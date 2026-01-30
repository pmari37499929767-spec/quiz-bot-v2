# СТРУКТУРА ПРОЕКТА: Квиз-бот "Новогоднее расследование"

## Дерево файлов

```
quiz_bot/
│
├── .env                          # Переменные окружения (НЕ коммитить!)
├── .gitignore                    # Игнорируемые файлы
├── requirements.txt              # Python зависимости
├── README.md                     # Документация проекта
│
├── main.py                       # Точка входа приложения
├── config.py                     # Конфигурация
│
├── handlers/                     # Обработчики событий
│   ├── __init__.py
│   ├── start.py                  # Команда /start
│   ├── quiz.py                   # Логика прохождения квиза
│   ├── results.py                # Показ результатов
│   └── lead_form.py              # Форма сбора заявок
│
├── models/                       # Модели данных (SQLAlchemy)
│   ├── __init__.py
│   ├── base.py                   # Базовая модель
│   ├── user.py                   # Модель пользователя
│   ├── quiz_session.py           # Модель сессии квиза
│   └── lead.py                   # Модель заявки
│
├── database/                     # Работа с БД
│   ├── __init__.py
│   ├── db.py                     # Подключение к БД
│   └── queries.py                # SQL-запросы
│
├── content/                      # Контент квиза
│   ├── __init__.py
│   ├── questions.py              # Банк вопросов
│   ├── scenarios.py              # Сценарии под разные ниши
│   └── results_logic.py          # Логика определения результатов
│
├── utils/                        # Вспомогательные функции
│   ├── __init__.py
│   ├── keyboards.py              # Клавиатуры
│   ├── analytics.py              # Аналитика и метрики
│   ├── notifications.py          # Уведомления
│   └── validators.py             # Валидация данных
│
└── tests/                        # Тесты (опционально)
    ├── __init__.py
    ├── test_quiz.py
    └── test_lead_form.py
```

---

## Содержимое файлов

### .env
```env
# Telegram Bot
BOT_TOKEN=your_bot_token_here
OWNER_ID=your_telegram_id_here

# Database
DATABASE_URL=sqlite+aiosqlite:///./quiz_bot.db
# DATABASE_URL=postgresql+asyncpg://user:password@localhost/quiz_bot  # для PostgreSQL

# Settings
DEBUG=True
LOG_LEVEL=INFO
```

---

### .gitignore
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Environment
.env
.env.local

# Database
*.db
*.sqlite
*.sqlite3

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
logs/
*.log

# OS
.DS_Store
Thumbs.db

# Other
exports/
backups/
```

---

### requirements.txt
```
aiogram==3.3.0
python-dotenv==1.0.0
sqlalchemy==2.0.25
aiosqlite==0.19.0
asyncpg==0.29.0
```

---

### config.py
```python
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле!")

OWNER_ID = int(os.getenv('OWNER_ID', 0))
if not OWNER_ID:
    raise ValueError("OWNER_ID не найден в .env файле!")

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./quiz_bot.db')

# Settings
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Quiz Settings
QUESTIONS_COUNT = 5  # Будет установлено автоматически из questions.py
RESULT_CATEGORIES = ['product', 'traffic', 'sales', 'system']

# Timeouts
TYPING_DELAY = 1.5  # секунды "печатания"
```

---

### main.py
```python
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, LOG_LEVEL
from handlers import start, quiz, results, lead_form
from database.db import init_db

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота"""
    
    # Инициализация БД
    logger.info("Инициализация базы данных...")
    await init_db()
    
    # Создание бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация роутеров
    logger.info("Регистрация обработчиков...")
    dp.include_router(start.router)
    dp.include_router(quiz.router)
    dp.include_router(results.router)
    dp.include_router(lead_form.router)
    
    # Запуск
    logger.info("Бот запущен и готов к работе!")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
```

---

### models/base.py
```python
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TimestampMixin:
    """Миксин для добавления временных меток"""
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

---

### models/user.py
```python
from sqlalchemy import Column, Integer, BigInteger, String
from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    
    def __repr__(self):
        return f"<User {self.telegram_id} ({self.first_name})>"
```

---

### models/quiz_session.py
```python
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, JSON
from sqlalchemy.orm import relationship
from .base import Base


class QuizSession(Base):
    __tablename__ = 'quiz_sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    
    current_question = Column(Integer, default=0)
    answers = Column(JSON, default=dict)  # {question_id: option_id}
    score = Column(JSON, default=dict)    # {category: points}
    result_category = Column(String(50))
    
    user = relationship("User", backref="quiz_sessions")
    
    def __repr__(self):
        return f"<QuizSession {self.id} (user={self.user_id})>"
```

---

### models/lead.py
```python
from sqlalchemy import Column, Integer, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin


class Lead(Base, TimestampMixin):
    __tablename__ = 'leads'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_id = Column(Integer, ForeignKey('quiz_sessions.id'))
    
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    email = Column(String(255))
    comment = Column(Text)
    
    status = Column(String(50), default='new')  # new, contacted, converted, rejected
    
    user = relationship("User", backref="leads")
    session = relationship("QuizSession", backref="leads")
    
    def __repr__(self):
        return f"<Lead {self.id} ({self.name}, {self.phone})>"
```

---

### database/db.py
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import DATABASE_URL
from models.base import Base

# Создание движка
engine = create_async_engine(DATABASE_URL, echo=False)

# Создание фабрики сессий
async_session = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def init_db():
    """Создание всех таблиц в БД"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Получение сессии БД"""
    async with async_session() as session:
        yield session
```

---

### database/queries.py
```python
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User
from models.quiz_session import QuizSession
from models.lead import Lead


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str, first_name: str) -> User:
    """Получить или создать пользователя"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    
    return user


async def create_quiz_session(session: AsyncSession, user_id: int) -> QuizSession:
    """Создать новую сессию квиза"""
    from datetime import datetime
    
    quiz_session = QuizSession(
        user_id=user_id,
        started_at=datetime.now(),
        answers={},
        score={'product': 0, 'traffic': 0, 'sales': 0, 'system': 0}
    )
    session.add(quiz_session)
    await session.commit()
    await session.refresh(quiz_session)
    
    return quiz_session


async def save_answer(session: AsyncSession, session_id: int, question_id: int, option_id: int, score_delta: dict):
    """Сохранить ответ на вопрос"""
    result = await session.execute(
        select(QuizSession).where(QuizSession.id == session_id)
    )
    quiz_session = result.scalar_one()
    
    # Обновление ответов
    quiz_session.answers[str(question_id)] = option_id
    
    # Обновление баллов
    for category, points in score_delta.items():
        quiz_session.score[category] = quiz_session.score.get(category, 0) + points
    
    await session.commit()


async def complete_quiz_session(session: AsyncSession, session_id: int, result_category: str):
    """Завершить сессию квиза"""
    from datetime import datetime
    
    result = await session.execute(
        select(QuizSession).where(QuizSession.id == session_id)
    )
    quiz_session = result.scalar_one()
    
    quiz_session.completed_at = datetime.now()
    quiz_session.result_category = result_category
    
    await session.commit()


async def create_lead(session: AsyncSession, user_id: int, session_id: int, name: str, phone: str, email: str = None, comment: str = None) -> Lead:
    """Создать лид"""
    lead = Lead(
        user_id=user_id,
        session_id=session_id,
        name=name,
        phone=phone,
        email=email,
        comment=comment
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    
    return lead


async def get_stats(session: AsyncSession) -> dict:
    """Получить статистику"""
    # Всего пользователей
    total_users = await session.scalar(select(func.count(User.id)))
    
    # Всего сессий
    total_sessions = await session.scalar(select(func.count(QuizSession.id)))
    
    # Завершённых сессий
    completed_sessions = await session.scalar(
        select(func.count(QuizSession.id)).where(QuizSession.completed_at.isnot(None))
    )
    
    # Всего лидов
    total_leads = await session.scalar(select(func.count(Lead.id)))
    
    # Результаты по категориям
    results = {}
    for category in ['product', 'traffic', 'sales', 'system']:
        count = await session.scalar(
            select(func.count(QuizSession.id)).where(QuizSession.result_category == category)
        )
        results[category] = count
    
    # Конверсии
    cr1 = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
    cr2 = (total_leads / completed_sessions * 100) if completed_sessions > 0 else 0
    
    return {
        'total_users': total_users,
        'total_sessions': total_sessions,
        'completed_sessions': completed_sessions,
        'total_leads': total_leads,
        'results': results,
        'cr1': cr1,
        'cr2': cr2
    }


async def get_all_leads(session: AsyncSession) -> list[dict]:
    """Получить все лиды для экспорта"""
    result = await session.execute(
        select(Lead, User, QuizSession)
        .join(User, Lead.user_id == User.id)
        .join(QuizSession, Lead.session_id == QuizSession.id)
        .order_by(Lead.created_at.desc())
    )
    
    leads = []
    for lead, user, quiz_session in result:
        leads.append({
            'id': lead.id,
            'name': lead.name,
            'phone': lead.phone,
            'email': lead.email or '',
            'telegram': f"@{user.username}" if user.username else '',
            'bottleneck': quiz_session.result_category,
            'comment': lead.comment or '',
            'created_at': lead.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return leads
```

---

### content/questions.py
```python
"""
Банк вопросов для квиза.

Каждый вопрос имеет структуру:
{
    'id': int,
    'text': str,
    'type': 'choice' | 'scale' | 'text',
    'options': [
        {
            'text': str,
            'score': {'product': int, 'traffic': int, 'sales': int, 'system': int}
        }
    ]
}
"""

QUESTIONS = [
    {
        'id': 0,
        'text': '🎯 Как вы оцениваете свой 2025 год?',
        'type': 'choice',
        'options': [
            {
                'text': '💚 Отлично! Лучший год в моей жизни',
                'score': {'product': 0, 'traffic': 0, 'sales': 0, 'system': 0}
            },
            {
                'text': '😐 Нормально, но мог быть значительно лучше',
                'score': {'product': 1, 'traffic': 1, 'sales': 1, 'system': 1}
            },
            {
                'text': '😔 Хуже, чем я ожидал(а)',
                'score': {'product': 2, 'traffic': 2, 'sales': 2, 'system': 2}
            },
            {
                'text': '😤 Провальный год, нужно всё менять',
                'score': {'product': 3, 'traffic': 3, 'sales': 3, 'system': 3}
            }
        ]
    },
    
    {
        'id': 1,
        'text': '💼 Сколько у вас продуктов или услуг?',
        'type': 'choice',
        'options': [
            {
                'text': 'Один флагманский продукт',
                'score': {'product': 0, 'traffic': 2, 'sales': 2, 'system': 1}
            },
            {
                'text': '2-3 основных продукта',
                'score': {'product': 1, 'traffic': 1, 'sales': 1, 'system': 1}
            },
            {
                'text': 'Много продуктов, не знаю какой продавать',
                'score': {'product': 5, 'traffic': 1, 'sales': 2, 'system': 2}
            },
            {
                'text': 'У меня нет чёткого продукта/услуги',
                'score': {'product': 7, 'traffic': 0, 'sales': 0, 'system': 0}
            }
        ]
    },
    
    {
        'id': 2,
        'text': '📢 Сколько людей узнаёт о вас каждую неделю?',
        'type': 'choice',
        'options': [
            {
                'text': '100+ новых людей в неделю',
                'score': {'product': 1, 'traffic': 0, 'sales': 2, 'system': 1}
            },
            {
                'text': '30-100 новых людей',
                'score': {'product': 1, 'traffic': 2, 'sales': 1, 'system': 1}
            },
            {
                'text': 'Меньше 30 новых людей',
                'score': {'product': 2, 'traffic': 5, 'sales': 1, 'system': 1}
            },
            {
                'text': 'Не знаю / практически никто',
                'score': {'product': 1, 'traffic': 7, 'sales': 0, 'system': 0}
            }
        ]
    },
    
    {
        'id': 3,
        'text': '💰 Что происходит с вашими заявками?',
        'type': 'choice',
        'options': [
            {
                'text': 'Конвертирую большинство в продажи',
                'score': {'product': 1, 'traffic': 1, 'sales': 0, 'system': 2}
            },
            {
                'text': 'Конверсия 20-50%',
                'score': {'product': 1, 'traffic': 1, 'sales': 2, 'system': 1}
            },
            {
                'text': 'Много заявок, но мало покупают',
                'score': {'product': 2, 'traffic': 0, 'sales': 6, 'system': 1}
            },
            {
                'text': 'Заявок почти нет',
                'score': {'product': 2, 'traffic': 5, 'sales': 2, 'system': 0}
            }
        ]
    },
    
    {
        'id': 4,
        'text': '⚙️ Как вы работаете?',
        'type': 'choice',
        'options': [
            {
                'text': 'Всё систематизировано, есть процессы',
                'score': {'product': 1, 'traffic': 1, 'sales': 1, 'system': 0}
            },
            {
                'text': 'Частично есть система',
                'score': {'product': 1, 'traffic': 1, 'sales': 1, 'system': 3}
            },
            {
                'text': 'Работаю хаотично, всё держу в голове',
                'score': {'product': 2, 'traffic': 1, 'sales': 1, 'system': 6}
            },
            {
                'text': 'Полный хаос, выгораю',
                'score': {'product': 1, 'traffic': 1, 'sales': 1, 'system': 8}
            }
        ]
    }
]

# Автоматически устанавливаем количество вопросов
QUESTIONS_COUNT = len(QUESTIONS)
```

---

### content/results_logic.py
```python
"""
Логика определения результата квиза
"""

from typing import Dict


def determine_bottleneck(score: Dict[str, int]) -> dict:
    """
    Определяет узкое место на основе баллов
    
    Args:
        score: Словарь с баллами по категориям
        
    Returns:
        Словарь с результатом
    """
    # Находим категорию с максимальными баллами
    max_category = max(score, key=score.get)
    
    results = {
        'product': {
            'emoji': '💡',
            'title': 'ПРОДУКТ',
            'description': (
                'Ваше узкое место — нечёткое позиционирование или слабая упаковка продукта. '
                'У вас может быть слишком много предложений, или наоборот — непонятно, что именно вы продаёте. '
                'Клиенты не видят ценности.'
            ),
            'steps': [
                'Выберите ОДИН флагманский продукт на Q1 2025',
                'Пропишите уникальность: чем вы отличаетесь от конкурентов',
                'Соберите 10 кейсов/отзывов клиентов для социальных доказательств'
            ]
        },
        'traffic': {
            'emoji': '📢',
            'title': 'ТРАФИК',
            'description': (
                'У вас есть продукт, но мало людей о вас знают. '
                'Вы либо не создаёте контент регулярно, либо он не попадает в целевую аудиторию. '
                'Нет стабильного потока новых людей.'
            ),
            'steps': [
                'Запустите контент-стратегию: минимум 3-5 постов в неделю',
                'Выберите 1-2 основных канала трафика (блог, reels, YouTube)',
                'Настройте таргетированную рекламу или начните коллаборации'
            ]
        },
        'sales': {
            'emoji': '💰',
            'title': 'ПРОДАЖИ',
            'description': (
                'Трафик есть, заявки приходят, но они не конвертируются в деньги. '
                'Проблема в воронке продаж, скриптах или работе с возражениями. '
                'Возможно, цена не соответствует ценности.'
            ),
            'steps': [
                'Пересмотрите воронку: на каком этапе теряются клиенты',
                'Отработайте скрипты продаж или настройте автоворонки',
                'Добавьте триггеры срочности (дедлайны, бонусы, ограниченность)'
            ]
        },
        'system': {
            'emoji': '⚙️',
            'title': 'СИСТЕМА',
            'description': (
                'Вы зарабатываете, но работаете хаотично и без процессов. '
                'Всё держите в голове, постоянно выгораете. '
                'Нет делегирования и автоматизации.'
            ),
            'steps': [
                'Делегируйте рутину: наймите ассистента или настройте автоматизацию',
                'Внедрите CRM для учёта клиентов и задач',
                'Создайте чек-листы для повторяющихся процессов'
            ]
        }
    }
    
    result = results[max_category]
    result['category'] = max_category
    
    return result


def format_result_message(name: str, result: dict) -> str:
    """
    Форматирует итоговое сообщение с результатом
    
    Args:
        name: Имя пользователя
        result: Результат от determine_bottleneck()
        
    Returns:
        Отформатированное сообщение
    """
    steps_text = '\n'.join([f'✅ {step}' for step in result['steps']])
    
    message = f"""
{result['emoji']} <b>РЕЗУЛЬТАТ РАССЛЕДОВАНИЯ</b>

{name}, ваше узкое место: <b>{result['title']}</b>

{result['description']}

<b>Что делать дальше:</b>
{steps_text}

───────────────

<i>P.S. Хотите разобрать вашу ситуацию детально с экспертом?</i>
    """
    
    return message.strip()
```

---

## СЛЕДУЮЩИЕ ШАГИ

1. **Скопируйте структуру** выше в свой проект
2. **Установите зависимости**: `pip install -r requirements.txt`
3. **Создайте .env файл** с вашими токенами
4. **Начните разработку** с handlers/start.py
5. **Следуйте плану** из development_plan.md

---

## ПОЛЕЗНЫЕ КОМАНДЫ

```bash
# Создание виртуального окружения
python3 -m venv venv

# Активация (Linux/Mac)
source venv/bin/activate

# Активация (Windows)
venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt

# Запуск бота
python main.py

# Создание БД (происходит автоматически при запуске)
# Но можно сделать отдельно:
python -c "import asyncio; from database.db import init_db; asyncio.run(init_db())"
```

---

## FAQ

**Q: Как добавить новый вопрос?**
A: Отредактируйте `content/questions.py`, добавьте словарь в список QUESTIONS

**Q: Как изменить тексты результатов?**
A: Отредактируйте `content/results_logic.py`, функцию determine_bottleneck()

**Q: Как добавить нового админа?**
A: Измените OWNER_ID в .env файле (или добавьте проверку на список ID в handlers)

**Q: Как экспортировать лиды?**
A: Отправьте команду /export боту (только для владельца)

---

Удачи в разработке! 🚀
