from aiogram.fsm.state import State, StatesGroup


class QuizStates(StatesGroup):
    """Состояния для прохождения квиза"""
    
    waiting_for_name = State()
    waiting_for_niche = State()  # ← ДОБАВИЛИ для выбора ниши
    
    question_1 = State()
    question_2 = State()
    question_3 = State()

    # Вопрос perceived (что человек ДУМАЕТ, что мешает)
    question_perceived = State()

    # Диагностические вопросы
    question_4 = State()
    question_5 = State()
    question_6 = State()
    question_7 = State()
    question_8 = State()

    show_result = State()

    # Состояние ожидания информации для консультации
    waiting_for_consult_info = State()

    # Состояние выбора шаблона сообщения
    choosing_template = State()