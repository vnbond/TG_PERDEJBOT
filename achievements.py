# -*- coding: utf-8 -*-
ACHIEVEMENTS = [
    {"key": "001", "threshold": 1,   "title": "Первый пуф",      "emoji": "🎈", "desc": "Исторический момент!"},
    {"key": "010", "threshold": 10,  "title": "Лёгкий бриз",     "emoji": "🍃", "desc": "Уверенное начало."},
    {"key": "020", "threshold": 20,  "title": "Дуновение судьбы","emoji": "🌬️","desc": "Чувствуется стиль."},
    {"key": "030", "threshold": 30,  "title": "Соло на медиуме", "emoji": "🎷", "desc": "Выходит на сцену."},
    {"key": "040", "threshold": 40,  "title": "Стабильный поток","emoji": "🚿", "desc": "Держит уровень."},
    {"key": "050", "threshold": 50,  "title": "Пятьдесят оттенков газа","emoji": "🟡","desc": "Уже заметная тяга."},
    {"key": "060", "threshold": 60,  "title": "Местный циклон",  "emoji": "🌀", "desc": "Погода меняется."},
    {"key": "070", "threshold": 70,  "title": "Флейта Пана",     "emoji": "🎶", "desc": "Музыкальный талант."},
    {"key": "080", "threshold": 80,  "title": "Газпром локальный","emoji": "🏭","desc": "Мощности растут."},
    {"key": "090", "threshold": 90,  "title": "Передув",         "emoji": "💨", "desc": "Ветер крепчает."},
    {"key": "100", "threshold": 100, "title": "Центр циклона",   "emoji": "🌀", "desc": "Круглая дата!"},
    {"key": "150", "threshold": 150, "title": "Штормовое",       "emoji": "🌪️","desc": "Только крепкие устоят."},
    {"key": "200", "threshold": 200, "title": "Торнадо",         "emoji": "🌪️","desc": "Пик напора."},
    {"key": "250", "threshold": 250, "title": "Рекордсмен двора","emoji": "🏆", "desc": "Слава в чате."},
    {"key": "300", "threshold": 300, "title": "Громовержец",     "emoji": "⚡", "desc": "Мощь и гром."},
    {"key": "400", "threshold": 400, "title": "Смерч",           "emoji": "🌪️","desc": "Буря на подходе."},
    {"key": "500", "threshold": 500, "title": "Легенда газохода","emoji": "👑", "desc": "Максимальное уважение."},
]

def newly_earned_achievements(old_count: int, new_count: int):
    res = []
    for a in ACHIEVEMENTS:
        if old_count < a["threshold"] <= new_count:
            res.append(a)
    res.sort(key=lambda x: x["threshold"])
    return res
