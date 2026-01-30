import os
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from .states import QuizStates
from analytics import track_step, get_stats_text

router = Router()


@router.message(F.text == "/myid")
async def cmd_myid(message: Message):
    """Показать chat_id пользователя"""
    await message.answer(
        f"Ваш chat_id: <code>{message.from_user.id}</code>\n\n"
        "Скопируйте это число и отправьте разработчику.",
        parse_mode='HTML'
    )


@router.message(F.text == "/stats")
async def cmd_stats(message: Message):
    """Показать статистику (только для админа)"""
    admin_id = int(os.getenv('ADMIN_CHAT_ID', '0'))
    text = get_stats_text(admin_id, message.from_user.id)
    await message.answer(text, parse_mode='HTML')


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start — Экран 0 (заставка)"""
    track_step('start')

    # Сохраняем step = 0
    await state.update_data(step=0)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Начать",
                callback_data="screen0_start"
            )]
        ]
    )

    text = (
        "Быстрый разбор за 60 секунд.\n\n"
        "3 шага → диагноз → готовый текст Марине.\n\n"
        "Поехали?"
    )

    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data == "screen0_start")
async def screen0_start(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Начать' с Экрана 0 — переход к Экрану 1"""
    track_step('quiz_started')
    await callback.answer()

    # Обновляем step = 1
    await state.update_data(step=1)

    # Экран 1 — Ситуация (выбор "что болит")
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Лидов мало — тишина",
                callback_data="series_low_leads"
            )],
            [InlineKeyboardButton(
                text="Лиды есть, но не покупают",
                callback_data="series_leads_no_buy"
            )],
            [InlineKeyboardButton(
                text="«Прайс?» → и пропал",
                callback_data="series_price_ghost"
            )],
            [InlineKeyboardButton(
                text="Много переписки — мало результата",
                callback_data="series_many_chats"
            )]
        ]
    )

    text = (
        "Вы запускаете контент/трафик, а в личке всё по кругу.\n\n"
        "<b>Что сейчас болит сильнее всего?</b>"
    )

    await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(QuizStates.screen1_situation)


@router.callback_query(F.data.startswith("series_"))
async def handle_series_choice(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора ситуации на Экране 1"""
    await callback.answer()

    # Маппинг callback_data → series
    series_map = {
        "series_low_leads": "low_leads",
        "series_leads_no_buy": "leads_no_buy",
        "series_price_ghost": "price_ghost",
        "series_many_chats": "many_chats"
    }

    series = series_map.get(callback.data)
    await state.update_data(series=series)

    # Поручни (навигация)
    rails_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Продолжить", callback_data="rail_continue"),
                InlineKeyboardButton(text="Сделать быстрее", callback_data="rail_fast")
            ],
            [
                InlineKeyboardButton(text="Вернуться", callback_data="rail_back"),
                InlineKeyboardButton(text="Пропустить и получить вывод", callback_data="rail_skip")
            ]
        ]
    )

    await callback.message.answer(
        "Выберите действие:",
        reply_markup=rails_keyboard,
        parse_mode='HTML'
    )


# ========================================
# ЭКРАН 2 — Почему так происходит
# ========================================

# Данные для Экрана 2 по каждой серии
SCREEN2_DATA = {
    "low_leads": {
        "text": (
            "Часто проблема не в количестве постов.\n"
            "Люди просто не узнают себя в первом касании.\n\n"
            "<b>Что ближе в вашем случае?</b>"
        ),
        "buttons": [
            ("Неясно, кому я говорю", "cause_unclear_audience"),
            ("Оффер размытый", "cause_blurry_offer"),
            ("Канал есть, но нет системы", "cause_no_system"),
        ]
    },
    "leads_no_buy": {
        "text": (
            "Лиды могут быть нормальные.\n"
            "Чаще ломается «мост» от интереса к действию.\n\n"
            "<b>Где ломается у вас?</b>"
        ),
        "buttons": [
            ("Не дожимаю в переписке", "cause_no_followup_script"),
            ("Нет доверия/кейсов", "cause_no_proof"),
            ("Слишком много вариантов — человек теряется", "cause_too_many_options"),
        ]
    },
    "price_ghost": {
        "text": (
            "Это почти никогда не про цену.\n"
            "Обычно человек не понял, что именно получит.\n\n"
            "<b>У вас чаще как?</b>"
        ),
        "buttons": [
            ("Объясняю долго", "cause_long_explain"),
            ("Объясняю коротко, но мимо", "cause_short_miss"),
            ("Сразу кидаю прайс", "cause_price_first"),
        ]
    },
    "many_chats": {
        "text": (
            "Заготовки ответов не спасают, если у человека нет ясного запроса.\n\n"
            "<b>Что выматывает сильнее?</b>"
        ),
        "buttons": [
            ("Одни и те же вопросы", "cause_repeat_questions"),
            ("Люди пишут размыто", "cause_vague_requests"),
            ("Всё упирается в «а сколько стоит?»", "cause_price_loop"),
        ]
    }
}


# ========================================
# ЭКРАН 3 — Результат (диагноз + фиксы)
# ========================================

# Данные для Экрана 3: диагноз и фиксы по комбинации series + cause
SCREEN3_DATA = {
    # low_leads
    ("low_leads", "unclear_audience"): {
        "diag": "Вы говорите «в воздух» — аудитория не узнаёт себя",
        "fix1": "Опишите 1 конкретного человека, которому вы помогли (или хотите помочь)",
        "fix2": "Перепишите шапку/био с позиции «для кого я»"
    },
    ("low_leads", "blurry_offer"): {
        "diag": "Оффер размытый — непонятно, что человек получит",
        "fix1": "Сформулируйте результат в 1 предложении: «После работы со мной вы…»",
        "fix2": "Уберите абстракции («рост», «развитие») — добавьте конкретику"
    },
    ("low_leads", "no_system"): {
        "diag": "Канал есть, но нет системы привлечения",
        "fix1": "Выберите 1 канал трафика и делайте 1 действие в день",
        "fix2": "Настройте простую воронку: пост → призыв → личка"
    },

    # leads_no_buy
    ("leads_no_buy", "no_followup_script"): {
        "diag": "Нет скрипта дожима — лиды остывают",
        "fix1": "Напишите 3 follow-up сообщения для тех, кто замолчал",
        "fix2": "Отправьте сегодня 5 людям, которые не ответили"
    },
    ("leads_no_buy", "no_proof"): {
        "diag": "Не хватает социального доказательства",
        "fix1": "Соберите 3 отзыва/кейса (даже из бесплатной работы)",
        "fix2": "Добавьте 1 кейс в закреп или highlights"
    },
    ("leads_no_buy", "too_many_options"): {
        "diag": "Слишком много вариантов — клиент теряется",
        "fix1": "Оставьте 1-2 продукта, остальные уберите из виду",
        "fix2": "Сделайте чёткую рекомендацию: «Вам подойдёт вот это»"
    },

    # price_ghost
    ("price_ghost", "long_explain"): {
        "diag": "Объясняете слишком долго — человек теряет интерес",
        "fix1": "Сократите объяснение до 3 предложений максимум",
        "fix2": "Задайте вопрос в конце, чтобы вернуть диалог"
    },
    ("price_ghost", "short_miss"): {
        "diag": "Объясняете коротко, но мимо потребности",
        "fix1": "Сначала спросите: «Что для вас сейчас важнее всего?»",
        "fix2": "Свяжите ваш продукт с их ответом"
    },
    ("price_ghost", "price_first"): {
        "diag": "Цена без ценности — человек сравнивает только цифры",
        "fix1": "Перед ценой дайте 2-3 пункта «что входит»",
        "fix2": "Добавьте: «Это окупится, потому что…»"
    },

    # many_chats
    ("many_chats", "repeat_questions"): {
        "diag": "Одни и те же вопросы — нет FAQ или автоответов",
        "fix1": "Выпишите топ-5 вопросов и заготовьте ответы",
        "fix2": "Добавьте FAQ в закреп или бота"
    },
    ("many_chats", "vague_requests"): {
        "diag": "Люди пишут размыто — нет квалификации на входе",
        "fix1": "Добавьте в первое сообщение: «Чтобы помочь, уточните…»",
        "fix2": "Сделайте мини-анкету из 3 вопросов"
    },
    ("many_chats", "price_loop"): {
        "diag": "Все спрашивают цену — оффер не продаёт до цены",
        "fix1": "Перед ценой спросите: «Что хотите получить в итоге?»",
        "fix2": "Покажите ценность, потом цену: «Вы получите X, Y, Z — стоимость…»"
    },
}


async def show_screen1(message, state: FSMContext):
    """Показать Экран 1 — выбор ситуации"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Лидов мало — тишина",
                callback_data="series_low_leads"
            )],
            [InlineKeyboardButton(
                text="Лиды есть, но не покупают",
                callback_data="series_leads_no_buy"
            )],
            [InlineKeyboardButton(
                text="«Прайс?» → и пропал",
                callback_data="series_price_ghost"
            )],
            [InlineKeyboardButton(
                text="Много переписки — мало результата",
                callback_data="series_many_chats"
            )]
        ]
    )

    text = (
        "Вы запускаете контент/трафик, а в личке всё по кругу.\n\n"
        "<b>Что сейчас болит сильнее всего?</b>"
    )

    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(QuizStates.screen1_situation)


async def show_screen2(message, state: FSMContext):
    """Показать Экран 2 — почему так происходит"""
    data = await state.get_data()
    series = data.get("series")

    if not series or series not in SCREEN2_DATA:
        # Fallback к Экрану 1
        await show_screen1(message, state)
        return

    screen_data = SCREEN2_DATA[series]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=btn_text, callback_data=btn_data)]
            for btn_text, btn_data in screen_data["buttons"]
        ]
    )

    await message.answer(screen_data["text"], reply_markup=keyboard, parse_mode='HTML')
    await state.update_data(step=2)
    await state.set_state(QuizStates.screen2_cause)


async def show_screen3(message, state: FSMContext):
    """Показать Экран 3 — диагноз + фиксы"""
    data = await state.get_data()
    series = data.get("series")
    cause = data.get("cause")

    # Получаем данные диагноза
    key = (series, cause)
    if key not in SCREEN3_DATA:
        # Fallback — общий диагноз
        diag = "Нужна более детальная диагностика"
        fix1 = "Запишитесь на разбор с Мариной"
        fix2 = "Получите персональный план действий"
    else:
        screen_data = SCREEN3_DATA[key]
        diag = screen_data["diag"]
        fix1 = screen_data["fix1"]
        fix2 = screen_data["fix2"]

    # Сохраняем в state
    await state.update_data(diag=diag, fix1=fix1, fix2=fix2, step=3)

    text = (
        f"<b>Диагноз:</b> {diag}\n\n"
        f"<b>Фикс на 24 часа:</b>\n"
        f"1. {fix1}\n"
        f"2. {fix2}\n\n"
        "Вот ваш текст запроса. Нажмите кнопку.\n"
        "Дальше я в «Экспресс-Генератор 24» соберу для вас план + тексты."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Отправить Марине мой запрос",
                callback_data="send_to_marina"
            )]
        ]
    )

    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

    # Строка-страховка
    await message.answer(
        "<i>Если отвлечётесь, то вернётесь, и я продолжу с того же места.</i>",
        parse_mode='HTML'
    )

    await state.set_state(QuizStates.screen3_result)


@router.callback_query(F.data == "rail_continue")
async def handle_rail_continue(callback: CallbackQuery, state: FSMContext):
    """Продолжить — переход к следующему экрану"""
    await callback.answer()

    data = await state.get_data()
    step = data.get("step", 1)

    if step == 1:
        # Переход к Экрану 2
        await show_screen2(callback.message, state)
    elif step == 2:
        # Переход к Экрану 3
        await show_screen3(callback.message, state)
    else:
        await callback.message.answer("Вы уже на финальном экране.", parse_mode='HTML')


@router.callback_query(F.data == "rail_fast")
async def handle_rail_fast(callback: CallbackQuery, state: FSMContext):
    """Сделать быстрее — ускоренный путь"""
    await callback.answer()
    # TODO: ускоренный путь
    await callback.message.answer("Ускоренный режим...", parse_mode='HTML')


@router.callback_query(F.data == "rail_back")
async def handle_rail_back(callback: CallbackQuery, state: FSMContext):
    """Вернуться — возврат к предыдущему экрану"""
    await callback.answer()

    data = await state.get_data()
    step = data.get("step", 1)

    if step == 3:
        # Возврат к Экрану 2
        await state.update_data(step=2)
        await show_screen2(callback.message, state)
    elif step == 2:
        # Возврат к Экрану 1
        await state.update_data(step=1)
        await show_screen1(callback.message, state)
    elif step == 1:
        # Возврат к Экрану 0
        await state.update_data(step=0)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Начать", callback_data="screen0_start")]
            ]
        )
        text = (
            "Быстрый разбор за 60 секунд.\n\n"
            "3 шага → диагноз → готовый текст Марине.\n\n"
            "Поехали?"
        )
        await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await show_screen1(callback.message, state)


@router.callback_query(F.data == "rail_skip")
async def handle_rail_skip(callback: CallbackQuery, state: FSMContext):
    """Пропустить и получить вывод — сразу к Экрану 3"""
    await callback.answer()
    await show_screen3(callback.message, state)


@router.callback_query(F.data == "send_to_marina")
async def handle_send_to_marina(callback: CallbackQuery, state: FSMContext):
    """Отправить запрос Марине"""
    import os
    await callback.answer()

    data = await state.get_data()
    series = data.get("series", "не указано")
    cause = data.get("cause", "не указано")
    diag = data.get("diag", "не указано")
    fix1 = data.get("fix1", "")
    fix2 = data.get("fix2", "")

    # Информация о пользователе
    user = callback.from_user
    user_link = f"@{user.username}" if user.username else f"ID: {user.id}"
    user_name = user.full_name or "Не указано"

    # Формируем заявку для Марины
    admin_message = (
        "🔔 <b>НОВЫЙ ЗАПРОС ИЗ КВИЗА!</b>\n\n"
        f"👤 <b>Пользователь:</b> {user_name}\n"
        f"📱 <b>Telegram:</b> {user_link}\n\n"
        f"📊 <b>Ситуация:</b> {series}\n"
        f"🔍 <b>Причина:</b> {cause}\n\n"
        f"<b>Диагноз:</b> {diag}\n\n"
        f"<b>Рекомендованные фиксы:</b>\n"
        f"1. {fix1}\n"
        f"2. {fix2}"
    )

    # Отправляем админу
    track_step('lead_sent')
    admin_chat_id = os.getenv('ADMIN_CHAT_ID')
    if admin_chat_id:
        try:
            await callback.bot.send_message(
                chat_id=int(admin_chat_id),
                text=admin_message,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Ошибка отправки админу: {e}")

    # Подтверждение пользователю
    await callback.message.answer(
        "✅ <b>Запрос отправлен!</b>\n\n"
        "Марина получила ваш диагноз и скоро свяжется с вами.\n\n"
        "А пока — попробуйте применить фиксы выше. Это займёт 24 часа, но даст первый результат.",
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith("cause_"))
async def handle_cause_choice(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора причины на Экране 2"""
    await callback.answer()

    # Извлекаем cause из callback_data (убираем префикс "cause_")
    cause = callback.data.replace("cause_", "")
    await state.update_data(cause=cause)

    # Поручни (навигация)
    rails_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Продолжить", callback_data="rail_continue"),
                InlineKeyboardButton(text="Сделать быстрее", callback_data="rail_fast")
            ],
            [
                InlineKeyboardButton(text="Вернуться", callback_data="rail_back"),
                InlineKeyboardButton(text="Пропустить и получить вывод", callback_data="rail_skip")
            ]
        ]
    )

    await callback.message.answer(
        "Выберите действие:",
        reply_markup=rails_keyboard,
        parse_mode='HTML'
    )


@router.callback_query(F.data == "start_quiz")
async def start_quiz(callback: CallbackQuery, state: FSMContext):
    """Обработчик нажатия на кнопку 'Да' (legacy)"""
    track_step('quiz_started')
    await callback.answer()

    text = (
        "Отлично! Прежде чем начнём расследование, представьтесь:\n\n"
        "<b>Как вас зовут?</b>"
    )

    await callback.message.answer(text, parse_mode='HTML')
    await state.set_state(QuizStates.waiting_for_name)


@router.callback_query(F.data == "decline_quiz")
async def decline_quiz(callback: CallbackQuery):
    """Обработчик нажатия на кнопку 'Нет'"""
    
    await callback.answer()
    
    text = (
        "Понимаю! 😊\n\n"
        "Когда будешь готов к расследованию — просто напиши /start\n\n"
        "Я буду ждать! 🕵️"
    )
    
    await callback.message.answer(text, parse_mode='HTML')


@router.message(QuizStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Обработка ввода имени пользователя"""
    
    name = message.text.strip()
    
    # Проверка: имя не должно быть пустым
    if not name or len(name) < 2:
        await message.answer(
            "Пожалуйста, введите корректное имя (минимум 2 символа):",
            parse_mode='HTML'
        )
        return
    
    # Сохраняем имя в состояние
    await state.update_data(name=name)
    
    # Ответ пользователю
    text = f"Приятно познакомиться, <b>{name}</b>! 👋"
    await message.answer(text, parse_mode='HTML')
    
    # Переходим к выбору ниши
    await state.set_state(QuizStates.waiting_for_niche)
    
    # Кнопки с выбором ниши
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="💼 Инфопродукты",
                callback_data="niche_infoproducts"
            )],
            [InlineKeyboardButton(
                text="📊 Консалтинг",
                callback_data="niche_consulting"
            )],
            [InlineKeyboardButton(
                text="🚀 Продажи",
                callback_data="niche_sales"
            )],
            [InlineKeyboardButton(
                text="💰 Бизнес",
                callback_data="niche_business"
            )],
            [InlineKeyboardButton(
                text="✍️ Другое (напишу сам)",
                callback_data="niche_custom"
            )]
        ]
    )
    
    await message.answer(
        "Теперь подскажи, в какой сфере ты работаешь?",
        reply_markup=keyboard,
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith("niche_"))
async def process_niche_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора ниши из кнопок"""
    
    await callback.answer()
    
    # Если выбрал "Другое" - просим написать
    if callback.data == "niche_custom":
        await callback.message.answer(
            "Напиши свою сферу деятельности:",
            parse_mode='HTML'
        )
        return
    
    # Сохраняем нишу (именительный падеж для заявки, предложный для вопросов)
    niches_nominative = {
        "niche_infoproducts": "инфопродукты",
        "niche_consulting": "консалтинг",
        "niche_sales": "продажи",
        "niche_business": "бизнес"
    }
    niches_prepositional = {
        "niche_infoproducts": "инфопродуктах",
        "niche_consulting": "консалтинге",
        "niche_sales": "продажах",
        "niche_business": "бизнесе"
    }

    niche = niches_nominative.get(callback.data, "бизнес")
    niche_prep = niches_prepositional.get(callback.data, "бизнесе")
    await state.update_data(niche=niche, niche_prep=niche_prep)
    
    # Переходим к первому вопросу
    await state.set_state(QuizStates.question_1)
    
    # Получаем имя из состояния
    data = await state.get_data()
    name = data.get('name', 'друг')
    
    # Задаём первый вопрос с подстановкой ниши
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📈 Лучше, чем предыдущие годы",
                callback_data="q1_better"
            )],
            [InlineKeyboardButton(
                text="➡️ Примерно на том же уровне",
                callback_data="q1_same"
            )],
            [InlineKeyboardButton(
                text="📉 Хуже, чем хотелось бы",
                callback_data="q1_worse"
            )]
        ]
    )
    
    question_text = (
        f"Отлично, <b>{name}</b>!\n\n"
        "Сейчас я задам тебе несколько вопросов. Это займёт всего 2 минуты.\n\n"
        "🎯 <b>Начнём с честной точки А.</b> Без чувства вины, просто факт.\n\n"
        f"<b>Вопрос 1:</b> Как ты оцениваешь свой 2025 по деньгам/результатам в <b>{niche_prep}</b>?"
    )
    
    await callback.message.answer(question_text, reply_markup=keyboard, parse_mode='HTML')


@router.message(QuizStates.waiting_for_niche)
async def process_custom_niche(message: Message, state: FSMContext):
    """Обработка кастомной ниши (когда пользователь сам пишет)"""
    
    niche_raw = message.text.strip()

    if not niche_raw or len(niche_raw) < 3:
        await message.answer("Пожалуйста, напиши сферу деятельности (минимум 3 символа):")
        return

    # Сохраняем именительный падеж для заявки
    niche = niche_raw
    # Для вопросов добавляем предлог
    niche_prep = f"сфере «{niche_raw}»"

    await state.update_data(niche=niche, niche_prep=niche_prep)
    
    # Переходим к первому вопросу
    await state.set_state(QuizStates.question_1)
    
    # Получаем имя
    data = await state.get_data()
    name = data.get('name', 'друг')
    
    # Задаём первый вопрос
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📈 Лучше, чем предыдущие годы",
                callback_data="q1_better"
            )],
            [InlineKeyboardButton(
                text="➡️ Примерно на том же уровне",
                callback_data="q1_same"
            )],
            [InlineKeyboardButton(
                text="📉 Хуже, чем хотелось бы",
                callback_data="q1_worse"
            )]
        ]
    )
    
    question_text = (
        f"Отлично, <b>{name}</b>!\n\n"
        "Сейчас я задам тебе несколько вопросов. Это займёт всего 2 минуты.\n\n"
        "🎯 <b>Начнём с честной точки А.</b> Без чувства вины, просто факт.\n\n"
        f"<b>Вопрос 1:</b> Как ты оцениваешь свой 2025 по деньгам/результатам в <b>{niche_prep}</b>?"
    )

    await message.answer(question_text, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data.in_(["q1_better", "q1_same", "q1_worse"]))
async def handle_question_1(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 1"""
    track_step('q1_niche')
    await callback.answer()

    # Сохраняем ответ
    answer_text = {
        "q1_better": "Лучше, чем предыдущие годы",
        "q1_same": "Примерно на том же уровне",
        "q1_worse": "Хуже, чем хотелось бы"
    }

    await state.update_data(question_1=answer_text[callback.data])

    # Переходим ко второму вопросу
    await state.set_state(QuizStates.question_2)

    # Вопрос 2: Доход за 2025
    keyboard_q2 = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="💵 До 50 000 в месяц",
                callback_data="q2_under50"
            )],
            [InlineKeyboardButton(
                text="💰 50–100 000",
                callback_data="q2_50to100"
            )],
            [InlineKeyboardButton(
                text="💎 100–300 000",
                callback_data="q2_100to300"
            )],
            [InlineKeyboardButton(
                text="🚀 300 000+",
                callback_data="q2_over300"
            )]
        ]
    )

    question_2_text = (
        "✅ Принято!\n\n"
        "Для начала зафиксируем, с чем ты входишь в 2026.\n"
        "Мне не нужны точные цифры, главное — порядок.\n\n"
        "<b>Вопрос 2. Доход за 2025</b>\n\n"
        "Примерно какой был твой средний ежемесячный доход в 2025?\n"
        "На каком уровне ты сейчас?"
    )

    await callback.message.answer(
        question_2_text,
        reply_markup=keyboard_q2,
        parse_mode='HTML'
    )


@router.callback_query(F.data.in_(["q2_under50", "q2_50to100", "q2_100to300", "q2_over300"]))
async def handle_question_2(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 2 - Доход"""
    track_step('q2_point_a')
    await callback.answer()

    # Сохраняем ответ
    answer_text = {
        "q2_under50": "До 50 000 в месяц",
        "q2_50to100": "50–100 000",
        "q2_100to300": "100–300 000",
        "q2_over300": "300 000+"
    }

    await state.update_data(question_2=answer_text[callback.data])

    # Переходим к третьему вопросу
    await state.set_state(QuizStates.question_3)

    # Вопрос 3: Цели по доходу на 2026
    keyboard_q3 = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📊 Стабильно x2–x3 от того, что есть сейчас",
                callback_data="q3_x2x3"
            )],
            [InlineKeyboardButton(
                text="🚀 Резкий рывок x5–x10, готов(а) вкалывать, даже если страшно",
                callback_data="q3_x5x10"
            )],
            [InlineKeyboardButton(
                text="💎 Мечтаю про x100, но не понимаю \"как\"",
                callback_data="q3_x100"
            )],
            [InlineKeyboardButton(
                text="🌱 Хочу перестать выживать и жить нормально",
                callback_data="q3_survive"
            )]
        ]
    )

    question_3_text = (
        "✅ Отлично! Зафиксировали!\n\n"
        "📍 <b>Точка Б: куда хочешь прийти в 2026?</b>\n\n"
        "Теперь давай зафиксируем, чего ты хочешь от 2026 года, чтобы сказать:\n"
        "«Да, этот год я прожил(а) не зря».\n\n"
        "<b>Вопрос 3. Цель по доходу</b>\n\n"
        "Что для тебя про рост в 2026?"
    )

    await callback.message.answer(
        question_3_text,
        reply_markup=keyboard_q3,
        parse_mode='HTML'
    )


@router.callback_query(F.data.in_(["q3_x2x3", "q3_x5x10", "q3_x100", "q3_survive"]))
async def handle_question_3(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 3 - Цель по доходу на 2026"""
    track_step('q3_goal')
    await callback.answer()

    # Сохраняем ответ
    answer_text = {
        "q3_x2x3": "Стабильно x2–x3 от того, что есть сейчас",
        "q3_x5x10": "Резкий рывок x5–x10, готов(а) вкалывать",
        "q3_x100": "Мечтаю про x100, но не понимаю \"как\"",
        "q3_survive": "Хочу перестать выживать и нормально жить"
    }

    await state.update_data(question_3=answer_text[callback.data])

    # Инициализируем счётчики боли для диагностики
    await state.update_data(
        product_pain=0,
        traffic_pain=0,
        content_pain=0,
        sales_pain=0,
        system_pain=0
    )

    # Переходим к вопросу perceived (что человек ДУМАЕТ, что мешает)
    await state.set_state(QuizStates.question_perceived)

    # Вопрос PERCEIVED: Что человек ДУМАЕТ, что мешает (для твиста)
    keyboard_perceived = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📦 Слабое предложение / что продавать?",
                callback_data="perceived_product"
            )],
            [InlineKeyboardButton(
                text="👥 Мало новых людей, слабый трафик",
                callback_data="perceived_traffic"
            )],
            [InlineKeyboardButton(
                text="📝 Не доверяют / мало прогрева к продукту",
                callback_data="perceived_content"
            )],
            [InlineKeyboardButton(
                text="💰 Трудно продавать / стыдно / не умею",
                callback_data="perceived_sales"
            )],
            [InlineKeyboardButton(
                text="⚙️ Нет времени / сил / структуры",
                callback_data="perceived_system"
            )]
        ]
    )

    perceived_text = (
        "✅ Супер! Твоя цель зафиксирована!\n\n"
        "🤔 <b>Давай честно:</b>\n\n"
        "Как тебе кажется, что <b>больше всего</b> мешает росту прямо сейчас?\n\n"
        "Выбери то, что первым приходит в голову, когда думаешь: "
        "«Вот если бы ЭТО решить — сразу полегчало бы»."
    )

    await callback.message.answer(
        perceived_text,
        reply_markup=keyboard_perceived,
        parse_mode='HTML'
    )


@router.callback_query(F.data.in_([
    "perceived_product",
    "perceived_traffic",
    "perceived_content",
    "perceived_sales",
    "perceived_system"
]))
async def handle_perceived(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на perceived вопрос (что человек ДУМАЕТ, что мешает)"""

    await callback.answer()

    # Маппинг callback_data -> зона
    perceived_zone_map = {
        "perceived_product": "product",
        "perceived_traffic": "traffic",
        "perceived_content": "content",
        "perceived_sales": "sales",
        "perceived_system": "system",
    }

    perceived_zone = perceived_zone_map[callback.data]

    # Сохраняем perceived зону
    await state.update_data(perceived_zone=perceived_zone)

    # Переходим к диагностическим вопросам (вопрос 4)
    await state.set_state(QuizStates.question_4)

    # Вопрос 4: Диагностика - Продукт
    keyboard_q4 = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Да, у меня есть понятное предложение",
                callback_data="q4_clear"
            )],
            [InlineKeyboardButton(
                text="🤔 Примерно могу, но запинаюсь",
                callback_data="q4_medium"
            )],
            [InlineKeyboardButton(
                text="😵 Миллион идей, хочу всё и сразу",
                callback_data="q4_chaos"
            )]
        ]
    )

    question_4_text = (
        "✅ Супер! Твоя цель зафиксирована!\n\n"
        "🔍 <b>Диагностика: 5 зон, где «течёт» результат</b>\n\n"
        "Теперь проверим 5 ключевых точек, где чаще всего теряются деньги.\n"
        "Я задам по одному вопросу на каждую зону — отвечай честно.\n\n"
        "📦 <b>Продукт/предложение</b>\n\n"
        "Начнём с самого очевидного вопроса: что ты продаёшь?\n\n"
        "Представь, что я твой идеальный клиент.\n"
        "Можешь ли ты за 1–2 предложения объяснить, что именно я у тебя могу купить? "
        "Чем ты мне можешь помочь?"
    )

    await callback.message.answer(
        question_4_text,
        reply_markup=keyboard_q4,
        parse_mode='HTML'
    )


@router.callback_query(F.data.in_(["q4_clear", "q4_medium", "q4_chaos"]))
async def handle_question_4(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 4 - Диагностика продукта"""
    track_step('q4_perceived')
    await callback.answer()

    # Получаем текущие данные
    data = await state.get_data()
    product_pain = data.get('product_pain', 0)

    # Начисляем баллы боли в зависимости от ответа
    pain_points = {
        "q4_clear": 0,      # Понятное предложение - нет боли
        "q4_medium": 1,     # Запинается - средняя боль
        "q4_chaos": 2       # Каша в голове - высокая боль
    }

    product_pain += pain_points[callback.data]

    # Жалобность варианта (для fallback perceived)
    complaint_levels = {
        "q4_clear": 0,
        "q4_medium": 1,
        "q4_chaos": 2
    }

    # Обновляем complaint_best если нужно
    complaint = complaint_levels[callback.data]
    complaint_best = data.get('complaint_best')
    if not complaint_best or complaint > complaint_best[1]:
        await state.update_data(complaint_best=("product", complaint))

    # Сохраняем обновлённый счётчик и ответ
    answer_text = {
        "q4_clear": "Да, у меня есть понятное предложение",
        "q4_medium": "Примерно могу, но запинаюсь",
        "q4_chaos": "Нет, у меня миллион идей и форматов"
    }

    await state.update_data(
        question_4=answer_text[callback.data],
        product_pain=product_pain
    )

    # Переходим к пятому вопросу
    await state.set_state(QuizStates.question_5)

    # Вопрос 5: Диагностика - Трафик
    keyboard_q5 = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Стабильно приходят каждую неделю",
                callback_data="q5_stable"
            )],
            [InlineKeyboardButton(
                text="🤷 Иногда прибавляются, иногда тишина",
                callback_data="q5_unstable"
            )],
            [InlineKeyboardButton(
                text="😞 Всё те же лица, новых нет",
                callback_data="q5_stagnant"
            )]
        ]
    )

    question_5_text = (
        "✅ Принято!\n\n"
        "👥 <b>Поток людей (трафик)</b>\n\n"
        "Хороший продукт без людей — это как концерт в пустом зале.\n\n"
        "Насколько стабильно к тебе приходят новые люди?"
    )

    await callback.message.answer(
        question_5_text,
        reply_markup=keyboard_q5,
        parse_mode='HTML'
    )


@router.callback_query(F.data.in_(["q5_stable", "q5_unstable", "q5_stagnant"]))
async def handle_question_5(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 5 - Диагностика трафика"""
    track_step('q5_traffic')
    await callback.answer()

    # Получаем текущие данные
    data = await state.get_data()
    traffic_pain = data.get('traffic_pain', 0)

    # Начисляем баллы боли в зависимости от ответа
    pain_points = {
        "q5_stable": 0,      # Стабильный трафик - нет боли
        "q5_unstable": 1,    # Нестабильный - средняя боль
        "q5_stagnant": 2     # Нет новых людей - высокая боль
    }

    traffic_pain += pain_points[callback.data]

    # Жалобность варианта (для fallback perceived)
    complaint_levels = {
        "q5_stable": 0,
        "q5_unstable": 1,
        "q5_stagnant": 2
    }

    # Обновляем complaint_best если нужно
    complaint = complaint_levels[callback.data]
    complaint_best = data.get('complaint_best')
    if not complaint_best or complaint > complaint_best[1]:
        await state.update_data(complaint_best=("traffic", complaint))

    # Сохраняем обновлённый счётчик и ответ
    answer_text = {
        "q5_stable": "Новые люди стабильно приходят каждую неделю",
        "q5_unstable": "Иногда прибавляется кто-то, иногда тишина",
        "q5_stagnant": "Практически одни и те же лица везде, никого нового"
    }

    await state.update_data(
        question_5=answer_text[callback.data],
        traffic_pain=traffic_pain
    )

    # Переходим к шестому вопросу
    await state.set_state(QuizStates.question_6)

    # Вопрос 6: Диагностика - Контент/доверие
    keyboard_q6 = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Регулярно с темами и рубриками",
                callback_data="q6_regular"
            )],
            [InlineKeyboardButton(
                text="🎨 Пишу по вдохновению, без системы",
                callback_data="q6_irregular"
            )],
            [InlineKeyboardButton(
                text="📚 Даю пользу, но не веду к продаже",
                callback_data="q6_no_funnel"
            )]
        ]
    )

    # Получаем нишу пользователя для персонализации
    data = await state.get_data()
    niche = data.get('niche', 'соцсетях')

    question_6_text = (
        "✅ Зафиксировали!\n\n"
        "📝 <b>Контент / доверие</b>\n\n"
        "Люди покупают не только продукт, но и историю, в которую ты их зовёшь.\n\n"
        "Как ты ведёшь контент в своих основных площадках?"
    )

    await callback.message.answer(
        question_6_text,
        reply_markup=keyboard_q6,
        parse_mode='HTML'
    )


@router.callback_query(F.data.in_(["q6_regular", "q6_irregular", "q6_no_funnel"]))
async def handle_question_6(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 6 - Диагностика контента/доверия"""
    track_step('q6_content')
    await callback.answer()

    # Получаем текущие данные
    data = await state.get_data()
    content_pain = data.get('content_pain', 0)

    # Начисляем баллы боли в зависимости от ответа
    pain_points = {
        "q6_regular": 0,       # Регулярный контент с логикой - нет боли
        "q6_irregular": 2,     # Нерегулярно, как попало - высокая боль
        "q6_no_funnel": 4      # Нет логики прогрева к продукту - высокая боль
    }

    content_pain += pain_points[callback.data]

    # Жалобность варианта (для fallback perceived)
    complaint_levels = {
        "q6_regular": 0,
        "q6_irregular": 2,
        "q6_no_funnel": 4
    }

    # Обновляем complaint_best если нужно
    complaint = complaint_levels[callback.data]
    complaint_best = data.get('complaint_best')
    if not complaint_best or complaint > complaint_best[1]:
        await state.update_data(complaint_best=("content", complaint))

    # Сохраняем обновлённый счётчик и ответ
    answer_text = {
        "q6_regular": "Регулярно, с понятными темами и рубриками",
        "q6_irregular": "Пишу когда есть вдохновение, как попало",
        "q6_no_funnel": "Часто даю пользу, но почти не веду к продукту"
    }

    await state.update_data(
        question_6=answer_text[callback.data],
        content_pain=content_pain
    )

    # Переходим к седьмому вопросу
    await state.set_state(QuizStates.question_7)

    # Вопрос 7: Диагностика - Продажи и офферы
    keyboard_q7 = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Продаю регулярно, не стесняюсь",
                callback_data="q7_regular"
            )],
            [InlineKeyboardButton(
                text="🤔 Иногда, когда уже прижало",
                callback_data="q7_sometimes"
            )],
            [InlineKeyboardButton(
                text="😳 Стыдно, жду пока сами спросят",
                callback_data="q7_ashamed"
            )]
        ]
    )

    question_7_text = (
        "✅ Понял!\n\n"
        "💰 <b>Продажи и офферы</b>\n\n"
        "Теперь про самое «любимое» — продажи.\n\n"
        "Как часто ты прямо и спокойно говоришь людям:\n"
        "«Вот мой формат работы, вот стоимость, вот как записаться»?"
    )

    await callback.message.answer(
        question_7_text,
        reply_markup=keyboard_q7,
        parse_mode='HTML'
    )


@router.callback_query(F.data.in_(["q7_regular", "q7_sometimes", "q7_ashamed"]))
async def handle_question_7(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 7 - Диагностика продаж"""
    track_step('q7_sales')
    await callback.answer()

    # Получаем текущие данные
    data = await state.get_data()
    sales_pain = data.get('sales_pain', 0)

    # Начисляем баллы боли в зависимости от ответа
    pain_points = {
        "q7_regular": 0,       # Регулярно продаёт - нет боли
        "q7_sometimes": 1,     # Иногда, когда прижало - средняя боль
        "q7_ashamed": 3        # Стыдно продавать - ЖИРНАЯ БОЛЬ
    }

    sales_pain += pain_points[callback.data]

    # Жалобность варианта (для fallback perceived)
    complaint_levels = {
        "q7_regular": 0,
        "q7_sometimes": 1,
        "q7_ashamed": 3        # САМАЯ ЖАЛОБНАЯ - стыдно продавать
    }

    # Обновляем complaint_best если нужно
    complaint = complaint_levels[callback.data]
    complaint_best = data.get('complaint_best')
    if not complaint_best or complaint > complaint_best[1]:
        await state.update_data(complaint_best=("sales", complaint))

    # Сохраняем обновлённый счётчик и ответ
    answer_text = {
        "q7_regular": "Регулярно, мне ок с продажами. Не стесняюсь",
        "q7_sometimes": "Иногда, когда уже прижало",
        "q7_ashamed": "Стыдно продавать, надеюсь, что сами догадаются"
    }

    await state.update_data(
        question_7=answer_text[callback.data],
        sales_pain=sales_pain
    )

    # Переходим к восьмому вопросу
    await state.set_state(QuizStates.question_8)

    # Вопрос 8: Диагностика - Система/ресурс
    keyboard_q8 = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Распланирую и справлюсь",
                callback_data="q8_scale"
            )],
            [InlineKeyboardButton(
                text="😰 Напрягусь, но как-нибудь справлюсь",
                callback_data="q8_struggle"
            )],
            [InlineKeyboardButton(
                text="🔥 Выгорю, запутаюсь, всё испорчу",
                callback_data="q8_burnout"
            )]
        ]
    )

    question_8_text = (
        "✅ Зафиксировал!\n\n"
        "⚙️ <b>Система / ресурс</b>\n\n"
        "И ещё вопрос не про цифры, а про выживание.\n\n"
        "Если к тебе завтра придут 20 клиентов одновременно, что произойдёт?"
    )

    await callback.message.answer(
        question_8_text,
        reply_markup=keyboard_q8,
        parse_mode='HTML'
    )


@router.callback_query(F.data.in_(["q8_scale", "q8_struggle", "q8_burnout"]))
async def handle_question_8(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 8 - Диагностика системы/ресурсов"""
    track_step('q8_system')
    await callback.answer()

    # Получаем текущие данные
    data = await state.get_data()
    system_pain = data.get('system_pain', 0)

    # Начисляем баллы боли в зависимости от ответа
    pain_points = {
        "q8_scale": 0,        # Готов масштабироваться - нет боли
        "q8_struggle": 1,     # Напрячётся, но справится - средняя боль
        "q8_burnout": 3       # Сгорит и запутается - высокая боль (нет масштабируемости)
    }

    system_pain += pain_points[callback.data]

    # Жалобность варианта (для fallback perceived)
    complaint_levels = {
        "q8_scale": 0,
        "q8_struggle": 1,
        "q8_burnout": 3
    }

    # Обновляем complaint_best если нужно
    complaint = complaint_levels[callback.data]
    complaint_best = data.get('complaint_best')
    if not complaint_best or complaint > complaint_best[1]:
        await state.update_data(complaint_best=("system", complaint))

    # Сохраняем обновлённый счётчик и ответ
    answer_text = {
        "q8_scale": "Распланирую и справлюсь",
        "q8_struggle": "Придётся напрячься, но вытяну",
        "q8_burnout": "Сгорю, запутаюсь и начну сливать"
    }

    await state.update_data(
        question_8=answer_text[callback.data],
        system_pain=system_pain
    )

    # Все вопросы пройдены - переходим к результатам
    track_step('results')
    await state.set_state(QuizStates.show_result)

    # Вычисляем финальный результат с помощью scoring модуля
    from scoring import AnswersState, compute_result, build_final_message, get_result_buttons
    from config import DEFAULT_TEMPLATE

    # Получаем все данные
    data = await state.get_data()

    # Формируем AnswersState
    answers_state = AnswersState(
        scores={
            "product": data.get('product_pain', 0),
            "traffic": data.get('traffic_pain', 0),
            "content": data.get('content_pain', 0),
            "sales": data.get('sales_pain', 0),
            "system": data.get('system_pain', 0),
        },
        perceived_zone=data.get('perceived_zone'),
        complaint_best=data.get('complaint_best')
    )

    # Вычисляем результат
    result = compute_result(answers_state)

    # Строим финальное сообщение и кнопки
    final_message = build_final_message(result, DEFAULT_TEMPLATE)
    result_buttons = get_result_buttons(result, DEFAULT_TEMPLATE)

    await callback.message.answer(
        "✅ Отлично! Диагностика завершена.\n\n"
        "По твоим ответам я вижу одну интересную штуку.\n\n"
        "Сейчас проанализирую твои результаты и покажу результат...",
        parse_mode='HTML'
    )

    # Короткая пауза для эффекта
    import asyncio
    await asyncio.sleep(2)

    # Создаем клавиатуру с кнопками
    keyboard = None
    if result_buttons:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[btn] for btn in result_buttons]
        )

    # Отправляем финальный результат с кнопками
    await callback.message.answer(
        final_message,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


# ========================================
# ОБРАБОТЧИКИ КНОПОК РЕЗУЛЬТАТА
# ========================================

@router.callback_query(F.data == "to_consult")
async def handle_to_consult(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Хочу разбор с {ЭКСПЕРТ}'"""
    await callback.answer()

    from config import DEFAULT_TEMPLATE

    # Блок 1: Информация о разборе
    consult_message = (
        f"<b>Разбор с {DEFAULT_TEMPLATE.expert_name}</b> — 60 минут в Телемост.\n\n"
        f"За одну встречу:\n"
        f"— находим узкое горлышко (что реально тормозит заявки/доход)\n"
        f"— собираем план на 14 дней\n"
        f"— даю 2 сценария квиза под вашу нишу (короткий и «мини-сериал»)\n\n"
        f"<b>Стоимость: 6 900 ₽</b>"
    )

    # Блок 2: Кнопка записи
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📝 Записаться на разбор",
                callback_data="consult_signup"
            )]
        ]
    )

    await callback.message.answer(
        consult_message,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


@router.callback_query(F.data == "paid_diagnostic")
async def handle_paid_diagnostic(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Полная диагностика + сценарии — 6 900 ₽'"""
    await callback.answer()

    from config import DEFAULT_TEMPLATE

    # Информация о платной диагностике
    diagnostic_message = (
        f"<b>Полная диагностика с {DEFAULT_TEMPLATE.expert_name}</b> — 60 минут в Телемост.\n\n"
        f"За одну встречу:\n"
        f"— находим узкое горлышко (что реально тормозит заявки/доход)\n"
        f"— собираем план на 14 дней\n"
        f"— даю 2 сценария квиза под вашу нишу (короткий и «мини-сериал»)\n\n"
        f"<b>Стоимость: 6 900 ₽</b>"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📝 Записаться на диагностику",
                callback_data="consult_signup"
            )]
        ]
    )

    await callback.message.answer(
        diagnostic_message,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


@router.callback_query(F.data == "consult_signup")
async def handle_consult_signup(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Записаться на разбор' - микровопрос перед личкой"""
    await callback.answer()

    from config import DEFAULT_TEMPLATE

    # Блок 3: Микровопрос перед переходом в личку
    micro_question = (
        "Чтобы я пришла подготовленной, ответьте в 2 строках:\n\n"
        "1️⃣ <b>Ниша и что продаёте</b>\n"
        "2️⃣ <b>Где сейчас основной поток:</b> ВК / ТГ / сайт\n\n"
        "Напишите ответ прямо сюда 👇"
    )

    await callback.message.answer(
        micro_question,
        parse_mode='HTML'
    )

    # Устанавливаем состояние ожидания ответа на микровопрос
    await state.set_state(QuizStates.waiting_for_consult_info)


@router.message(QuizStates.waiting_for_consult_info)
async def handle_consult_info(message: Message, state: FSMContext):
    """Обработка ответа на микровопрос перед консультацией"""

    from config import DEFAULT_TEMPLATE

    # Сохраняем информацию
    await state.update_data(consult_info=message.text)

    # Финальное сообщение
    final_message = (
        "Спасибо! Записала 🙌\n\n"
        "<b>Разбор</b> — 60 минут в Телемост, стоимость <b>6 900 ₽</b>.\n\n"
        "Выберите удобное время для встречи 👇"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📋 Шаблон 1 (быстро)",
                callback_data="template_1"
            )],
            [InlineKeyboardButton(
                text="🌙 Шаблон 2 (вечер/выходные)",
                callback_data="template_2"
            )],
            [InlineKeyboardButton(
                text="⚡ Шаблон 3 (срочно)",
                callback_data="template_3"
            )]
        ]
    )

    await message.answer(
        final_message,
        reply_markup=keyboard,
        parse_mode='HTML'
    )

    # Переходим в состояние выбора шаблона
    await state.set_state(QuizStates.choosing_template)


@router.callback_query(F.data.in_(["template_1", "template_2", "template_3"]))
async def handle_template_choice(callback: CallbackQuery, state: FSMContext):
    """Показ текста заявки для подтверждения"""
    await callback.answer()

    from config import DEFAULT_TEMPLATE

    # Шаблоны с "Оплата — переводом." во всех
    templates = {
        "template_1": f"{DEFAULT_TEMPLATE.expert_name}, хочу разбор. Удобно: завтра 12:00–14:00 или 18:00–20:00 (МСК). Телемост. Оплата — переводом.",
        "template_2": f"{DEFAULT_TEMPLATE.expert_name}, хочу разбор. Могу: будни после 19:00 или выходные с 12:00 до 16:00 (МСК). Телемост. Оплата — переводом.",
        "template_3": f"{DEFAULT_TEMPLATE.expert_name}, хочу разбор как можно быстрее. Сегодня могу до 22:00 (МСК) / завтра в любое время. Телемост. Оплата — переводом."
    }

    template_text = templates[callback.data]

    # Сохраняем выбранный шаблон
    await state.update_data(selected_template=template_text)

    # Показываем текст заявки для проверки
    preview_message = (
        "📝 <b>Ваша заявка:</b>\n\n"
        f"<i>{template_text}</i>\n\n"
        "Проверьте и нажмите кнопку для отправки 👇"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Подтвердить и отправить",
                callback_data="confirm_request"
            )],
            [InlineKeyboardButton(
                text="◀️ Выбрать другое время",
                callback_data="back_to_templates"
            )]
        ]
    )

    await callback.message.answer(
        preview_message,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


@router.callback_query(F.data == "back_to_templates")
async def handle_back_to_templates(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору шаблонов"""
    await callback.answer()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📋 Шаблон 1 (быстро)",
                callback_data="template_1"
            )],
            [InlineKeyboardButton(
                text="🌙 Шаблон 2 (вечер/выходные)",
                callback_data="template_2"
            )],
            [InlineKeyboardButton(
                text="⚡ Шаблон 3 (срочно)",
                callback_data="template_3"
            )]
        ]
    )

    await callback.message.answer(
        "Выберите удобное время для встречи 👇",
        reply_markup=keyboard,
        parse_mode='HTML'
    )


@router.callback_query(F.data == "confirm_request")
async def handle_confirm_request(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и отправка заявки администратору"""
    await callback.answer()

    import os
    from config import DEFAULT_TEMPLATE

    # Получаем данные пользователя
    data = await state.get_data()
    user_name = data.get('name', 'Не указано')
    user_niche = data.get('niche', 'Не указано')
    consult_info = data.get('consult_info', 'Не указано')
    template_text = data.get('selected_template', 'Не указано')

    # Информация о пользователе Telegram
    user = callback.from_user
    user_link = f"@{user.username}" if user.username else f"ID: {user.id}"

    # Формируем заявку для администратора
    admin_message = (
        "🔔 <b>НОВАЯ ЗАЯВКА НА РАЗБОР!</b>\n\n"
        f"👤 <b>Клиент:</b> {user_name}\n"
        f"📱 <b>Telegram:</b> {user_link}\n"
        f"💼 <b>Ниша:</b> {user_niche}\n\n"
        f"📝 <b>Информация от клиента:</b>\n{consult_info}\n\n"
        f"⏰ <b>Сообщение:</b>\n{template_text}"
    )

    # Отправляем заявку администратору
    track_step('lead_sent')
    admin_chat_id = os.getenv('ADMIN_CHAT_ID')
    if admin_chat_id:
        try:
            await callback.bot.send_message(
                chat_id=int(admin_chat_id),
                text=admin_message,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Ошибка отправки админу: {e}")

    # Показываем благодарность пользователю
    await callback.message.answer(
        "🙌 <b>Спасибо большое!</b>\n\n"
        "Ваша заявка отправлена. Вам ответят в ближайшее время.",
        parse_mode='HTML'
    )

    # Очищаем состояние
    await state.clear()


@router.callback_query(F.data == "to_self")
async def handle_to_self(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Попробую сам(а) по шагам'"""
    await callback.answer()

    from config import DEFAULT_TEMPLATE

    self_message = (
        "<b>Круто, что ты готов(а) пробовать сам(а).</b>\n\n"
        "Сохрани эти шаги и попробуй хотя бы 7–10 дней делать хоть что-то одно из списка.\n\n"
        f"Если поймёшь, что буксуешь, смело возвращайся к "
        f"<a href='https://t.me/{DEFAULT_TEMPLATE.expert_username}'>{DEFAULT_TEMPLATE.expert_name_dat}</a> — "
        f"{DEFAULT_TEMPLATE.pronoun_nom} не будет тебя отчитывать, "
        "а поможет спокойно довести эту историю до роста дохода."
    )

    await callback.message.answer(
        self_message,
        parse_mode='HTML'
    )
