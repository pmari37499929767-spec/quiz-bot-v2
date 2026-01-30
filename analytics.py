import json
import os
from datetime import datetime

STATS_FILE = os.path.join(os.path.dirname(__file__), 'stats.json')

def load_stats():
    """Загрузить статистику из файла"""
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'total_starts': 0,
        'steps': {
            'start': 0,
            'quiz_started': 0,
            'q1_niche': 0,
            'q2_point_a': 0,
            'q3_goal': 0,
            'q4_perceived': 0,
            'q5_traffic': 0,
            'q6_content': 0,
            'q7_sales': 0,
            'q8_system': 0,
            'results': 0,
            'lead_sent': 0
        },
        'last_reset': datetime.now().isoformat()
    }

def save_stats(stats):
    """Сохранить статистику в файл"""
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def track_step(step_name: str):
    """Записать прохождение этапа"""
    stats = load_stats()
    if step_name in stats['steps']:
        stats['steps'][step_name] += 1
    if step_name == 'start':
        stats['total_starts'] += 1
    save_stats(stats)

def get_stats_text(admin_id: int, user_id: int) -> str:
    """Получить текст статистики (только для админа)"""
    if user_id != admin_id:
        return "У вас нет доступа к статистике."

    stats = load_stats()
    steps = stats['steps']

    # Расчёт конверсий
    starts = steps.get('start', 0) or 1  # избегаем деления на 0

    text = (
        "<b>Статистика квиз-бота</b>\n\n"
        f"Всего запусков: <b>{steps.get('start', 0)}</b>\n"
        f"Начали квиз: <b>{steps.get('quiz_started', 0)}</b>\n\n"
        "<b>Воронка по этапам:</b>\n"
        f"1. Ниша: {steps.get('q1_niche', 0)}\n"
        f"2. Точка А: {steps.get('q2_point_a', 0)}\n"
        f"3. Цель: {steps.get('q3_goal', 0)}\n"
        f"4. Главная проблема: {steps.get('q4_perceived', 0)}\n"
        f"5. Трафик: {steps.get('q5_traffic', 0)}\n"
        f"6. Контент: {steps.get('q6_content', 0)}\n"
        f"7. Продажи: {steps.get('q7_sales', 0)}\n"
        f"8. Система: {steps.get('q8_system', 0)}\n"
        f"9. Результаты: {steps.get('results', 0)}\n"
        f"10. Заявки: <b>{steps.get('lead_sent', 0)}</b>\n\n"
        f"<b>Конверсия в заявку:</b> {steps.get('lead_sent', 0) / starts * 100:.1f}%\n"
        f"<b>Конверсия в результаты:</b> {steps.get('results', 0) / starts * 100:.1f}%\n\n"
        f"<i>Статистика с {stats.get('last_reset', 'начала')[:10]}</i>"
    )

    return text

def reset_stats():
    """Сбросить статистику"""
    stats = {
        'total_starts': 0,
        'steps': {
            'start': 0,
            'quiz_started': 0,
            'q1_niche': 0,
            'q2_point_a': 0,
            'q3_goal': 0,
            'q4_perceived': 0,
            'q5_traffic': 0,
            'q6_content': 0,
            'q7_sales': 0,
            'q8_system': 0,
            'results': 0,
            'lead_sent': 0
        },
        'last_reset': datetime.now().isoformat()
    }
    save_stats(stats)
