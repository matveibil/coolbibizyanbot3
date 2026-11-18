import os
import random
import logging
import time
import asyncio
import datetime
import json
import sqlite3
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.request import HTTPXRequest

# Настройка логов
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
load_dotenv()
TOKEN = os.getenv("larp_token")

if not TOKEN:
    raise RuntimeError("❌ ОШИБКА: Не задан larp_token в файле .env")

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image")
WIN_IMAGE_PATH = os.path.join(BASE_DIR, "win.png")
LOSE_GIF_PATH = os.path.join(BASE_DIR, "lose.gif")
VOLCANO_IMAGE = os.path.join(BASE_DIR, "1000097590.jpg")
OLD_GOD_IMAGE = os.path.join(BASE_DIR, "old_god.jpg")
UNDERWATER_VOLCANO_IMAGE = os.path.join(BASE_DIR, "e42cc4c4f361aedd022e27104a17e20d.jpg")
DB_NAME = "bibizyana.db"

# --- СИСТЕМА РЕДКОСТЕЙ И МУТАЦИЙ ---
BALANCE = {
    "rebirth_income_bonus": 0.08,
    "hardcore_income_bonus": 1.10,
    "normal_box_cost": 5,
    "gold_box_cost": 50,
    "mega_box_cost": 5000,
    "boss_attack_cost": 10,
    "boss_reward_multiplier": 1.3,
    "mega_drop_bias": 1.2,
}

RARITIES = {
    "Абычная 🐒": {"income": 1, "weight": 45, "images": ["1000097597.jpg", "normal.png"]},
    "Рицкая 🦧": {"income": 3, "weight": 30, "images": ["1000097589.jpg", "rare.png"]},
    "Эпик 👑": {"income": 10, "weight": 15, "images": ["1000097599.jpg", "epic.png"]},
    "Легенда 🚬": {"income": 30, "weight": 7, "images": ["1000097591.jpg", "1000097595.jpg"]},
    "Миф 🛸": {"income": 100, "weight": 2.9, "images": ["1000097592.jpg", "1000097596.jpg"]},
    "Батя Джунглей 🌋": {"income": 500, "weight": 0.1, "images": ["1000097590.jpg"]},
    "Бог 🪐": {"income": 2000, "weight": 0.05, "images": ["1000097593.jpg"]},
    "Абсолют 🗿": {"income": 5000, "weight": 0.01, "images": ["1000097601.jpg"]},
    "sub-3 🥉": {"income": 10000, "weight": 0, "images": ["b1440287a688e886fec12b876748a2aa.jpg"]},
    "sub-5 🥈": {"income": 25000, "weight": 0, "images": ["i (1).webp"]},
    "ltb 🧢": {"income": 50000, "weight": 0, "images": ["i.webp"]},
    "mtb 👽": {"income": 100000, "weight": 0, "images": ["i (2).webp"]},
    "htb 🗿": {"income": 250000, "weight": 0, "images": ["i.jpg"]},
    "chad 🗿🍷": {"income": 500000, "weight": 0, "images": ["1000097602.jpg", "1000097599.jpg"]},
    "true bibizan 👑🐒": {"income": 1000000, "weight": 0, "images": ["0e5f8b1da7b617cb1f6321bda48a9525.jpg", "old_god.jpg"]},
    
    # МУТАНТЫ (Падают только при склещивании)
    "Золотая Абычная 🐒✨": {"income": 100, "weight": 0, "images": ["1000097597.jpg"]},
    "Кибер-Эпик 👑🤖": {"income": 1000, "weight": 0, "images": ["1000097599.jpg"]},
    "Радиоактивная Легенда 🚬☢️": {"income": 5000, "weight": 0, "images": ["1000097591.jpg"]},
    "Космический Миф 🛸🌌": {"income": 20000, "weight": 0, "images": ["1000097592.jpg"]}
}

# --- СЮЖЕТНЫЕ ГЛАВЫ ---
STORY_CHAPTERS = [
    {"id": 0, "name": "Глава 1: Первые шаги", "desc": "Открой 3 карыта", "target": 3, "type": "boxes", "reward": 500},
    {"id": 1, "name": "Глава 2: Первая кровь", "desc": "Победи в 2 махачах", "target": 2, "type": "fights", "reward": 1500},
    {"id": 2, "name": "Глава 3: Эволюция", "desc": "Склей 3-х бибизян", "target": 3, "type": "merges", "reward": 3000},
    {"id": 3, "name": "Глава 4: Богатство", "desc": "Накопи 10 000 бананов", "target": 10000, "type": "bananas", "reward": 10000},
    {"id": 4, "name": "Глава 5: Убийца Богов", "desc": "Победи любого босса", "target": 1, "type": "bosses", "reward": 50000}
]

BESTIARY = {
    "Абычная 🐒": "Работает за еду, но иногда ворует кожуру.",
    "Рицкая 🦧": "Уже не обезьяна, но ещё не человек. Строит из себя интеллектуала.",
    "Эпик 👑": "Носит корону, хотя прав на трон не имеет.",
    "Легенда 🚬": "Курит бамбук, рассказывает байки про старые джунгли.",
    "Миф 🛸": "Прилетел из космоса. Строит пирамиды по ночам.",
    "Батя Джунглей 🌋": "Легенда. Когда он зевает, деревья сгибаются.",
    "Бог 🪐": "Создатель джунглей. Требует поклонения.",
    "Абсолют 🗿": "В его присутствии даже бананы обретают сознание.",
    "sub-3 🥉": "Бронзовый задрот.",
    "sub-5 🥈": "Серебряный стример. Кринжевать умеет.",
    "ltb 🧢": "Кепка задом наперед, IQ на нуле, но бананов гребет лопатой.",
    "mtb 👽": "Наполовину инопланетянин. Общается телепатией.",
    "htb 🗿": "Выживает даже после ядерного взрыва.",
    "chad 🗿🍷": "Настоящий Чед. Пьет сок с мизинцем вверх.",
    "true bibizan 👑🐒": "АБСОЛЮТНЫЙ БОСС. Создатель этого бота.",
    "Золотая Абычная 🐒✨": "Мутант! Светится от бананов.",
    "Кибер-Эпик 👑🤖": "Мутант! Наполовину робот.",
    "Радиоактивная Легенда 🚬☢️": "Мутант! Фонит так, что бананы жарятся.",
    "Космический Миф 🛸🌌": "Мутант! Пришел из другой галактики."
}

BOSSES = {
    "overlord": {"name": "🍌 Банановый Владыка", "hp": 500, "reward": 250, "damage": (1, 6)},
    "gorilla": {"name": "🦍 Мутировавшая Горилла", "hp": 2200, "reward": 900, "damage": (6, 18)},
    "god": {"name": "👹 Старый Бог", "hp": 5500, "reward": 3000, "damage": (12, 35)},
    "robot": {"name": "🤖 Кибер-Мартышка", "hp": 12000, "reward": 10000, "damage": (25, 60)},
    "chad": {"name": "🗿🍷 Гигачад", "hp": 60000, "reward": 50000, "damage": (120, 350)},
    "true_bibizan": {"name": "👑🐒 True Bibizan", "hp": 1200000, "reward": 180000, "damage": (1200, 5500)}
}

ACHIEVEMENTS = {
    "first_box": {"name": "📦 Первый шаг", "desc": "Открыть первое карыто", "reward": 50},
    "rich_1000": {"name": "💰 Первый миллионер", "desc": "Накопить 1000 бананов", "reward": 200},
    "rich_10000": {"name": "🤑 Банановый магнат", "desc": "Накопить 10 000 бананов", "reward": 1000},
    "killer_10": {"name": "🩸 Начало положено", "desc": "Победить в 10 битвах", "reward": 100},
    "killer_50": {"name": "⚔️ Мастер махача", "desc": "Победить в 50 битвах", "reward": 500},
    "merge_10": {"name": "🧬 Селекционер", "desc": "Склещить бибизян 10 раз", "reward": 300},
    "robber_5": {"name": "🥷 Криминальный авторитет", "desc": "Успешно ограбить 5 игроков", "reward": 300},
    "casino_win_5": {"name": "🎰 Любимчик фортуны", "desc": "Выиграть в казино 5 раз", "reward": 200},
    "internet_3": {"name": "🌐 Добросовестный юзер", "desc": "Оплатить интернет 3 раза", "reward": 150},
    "mythic_owner": {"name": "🛸 Контактер", "desc": "Получить Мифическую бибизяну", "reward": 500},
    "legend_owner": {"name": "🚬 Крутой перец", "desc": "Получить Легендарную бибизяну", "reward": 300},
    "boss_slayer": {"name": "🗡 Убийца Богов", "desc": "Победить любого босса", "reward": 500},
    "all_bosses": {"name": "👑 Гроза Боссов", "desc": "Победить всех 4 боссов", "reward": 1000},
    "mega_owner": {"name": "🚀 Мега-Лудоман", "desc": "Открыть Мега карыто", "reward": 1000},
    "true_owner": {"name": "👑🐒 Святая Святых", "desc": "Получить True Bibizan", "reward": 100000},
    "completionist": {"name": "🏆 Абсолютный Вожак", "desc": "Получить ВСЕ остальные достижения", "reward": 50000}
}

DAILY_TASKS = {
    "box_5": {"text": "Открыть 5 карыт", "target": 5, "reward": 100},
    "slot_3": {"text": "Сыграть 3 раза в слот", "target": 3, "reward": 100},
    "fight_1": {"text": "Победить в 1 махаче", "target": 1, "reward": 150}
}

MONKEY_NEWS_IMAGES = [os.path.join(BASE_DIR, f"{i}.jpg") for i in range(1, 13)]
WAR_IMAGES = [os.path.join(BASE_DIR, "orig.jpg"), os.path.join(BASE_DIR, "orig (1).jpg"), os.path.join(BASE_DIR, "orig (2).jpg"), os.path.join(BASE_DIR, "orig (3).jpg")]
ATTACK_TYPES = ["Удар хвостом в табло 🦍", "Засада в лианах 🌿", "Банановая бомбежка 🍌", "Ночной махач 🌙", "Абезьяний крик 🗣", "Кидание какашек 💩", "Стырить бананы 🥷"]

NEWS_LIST = [
    "🌧 **ПОГОДА:** Завтра ожидается дождь из кокосов. Рекомендуется носить каску.",
    "☀️ **ПОГОДА:** Аномальная жара! Бананы плавятся прямо на деревьях.",
    "🤪 **МЕМ:** В лесу заметили Гигачада. Он несет бананы и не смотрит на взрыв.",
    "🎮 **ДОТА:** Бибизяна-мидер затащила игру 1v9, но проиграла катку, потому что тиммейты — макаки.",
    "💰 **БИРЖА:** Курс True Bibizan достиг небес. Обычные обезьяны в панике.",
    "🗿 **СЛУХИ:** Старый бог снова упал с балкона. Местные уже ставят ставки.",
    "🦟 **БЕДА:** Нашествие саранчи. Бананы стали солоноватыми.",
    "🍻 **ПРАЗДНИК:** В джунглях день рождения у Гигачада. Все пьют сок.",
]

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ БЛОКИРОВОК ---
user_locks = {}

# ================= ФУНКЦИИ =================
def get_title(bananas):
    if bananas >= 10000000: return "👑 Бог Джунглей"
    if bananas >= 1000000: return "🤑 Обезьяний Олигарх"
    if bananas >= 100000: return "💰 Банановый Барон"
    if bananas >= 10000: return "🌿 Плантатор"
    if bananas >= 1000: return "🍌 Продвинутый"
    return "🐒 Новичок"

# ================= БАЗА ДАННЫХ =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY, name TEXT, bananas INTEGER, defeated INTEGER,
            last_internet_pay REAL, boxes_opened INTEGER, merges INTEGER, robberies INTEGER,
            casino_wins INTEGER, internet_payments INTEGER, last_seen REAL, monkeys TEXT,
            achievements TEXT, bosses_defeated TEXT, daily_quests TEXT, boss_id TEXT, boss_hp INTEGER,
            story_chapter INTEGER DEFAULT 0, rebirths INTEGER DEFAULT 0, hardcore INTEGER DEFAULT 0
        )
    ''')
    conn.commit()

    cursor.execute("PRAGMA table_info(players)")
    columns = [col[1] for col in cursor.fetchall()]
    for column_name, default_sql in [
        ("story_chapter", "INTEGER DEFAULT 0"),
        ("rebirths", "INTEGER DEFAULT 0"),
        ("hardcore", "INTEGER DEFAULT 0"),
    ]:
        if column_name not in columns:
            cursor.execute(f"ALTER TABLE players ADD COLUMN {column_name} {default_sql}")

    conn.commit()
    conn.close()


def load_player(user_id: int, user_name: str = "Бибизяна") -> dict:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row:
        cursor.execute("PRAGMA table_info(players)")
        columns = [col[1] for col in cursor.fetchall()]
        col_index = {name: idx for idx, name in enumerate(columns)}

        def get_value(name: str, default=None):
            idx = col_index.get(name)
            if idx is None or idx >= len(row):
                return default
            return row[idx]

        monkeys_raw = get_value("monkeys", "{}")
        achievements_raw = get_value("achievements", "[]")
        bosses_raw = get_value("bosses_defeated", "[]")
        daily_raw = get_value("daily_quests", "{}")

        data = {
            "user_id": get_value("user_id", user_id),
            "name": get_value("name", user_name),
            "bananas": get_value("bananas", 0),
            "defeated": get_value("defeated", 0),
            "last_internet_pay": get_value("last_internet_pay", 0),
            "boxes_opened": get_value("boxes_opened", 0),
            "merges": get_value("merges", 0),
            "robberies": get_value("robberies", 0),
            "casino_wins": get_value("casino_wins", 0),
            "internet_payments": get_value("internet_payments", 0),
            "last_seen": get_value("last_seen", time.time()),
            "monkeys": json.loads(monkeys_raw) if monkeys_raw else {rarity: 0 for rarity in RARITIES.keys()},
            "achievements": json.loads(achievements_raw) if achievements_raw else [],
            "bosses_defeated": json.loads(bosses_raw) if bosses_raw else [],
            "daily_quests": json.loads(daily_raw) if daily_raw else {"date": datetime.date.today().isoformat(), "tasks": list(DAILY_TASKS.keys()), "progress": {t: 0 for t in DAILY_TASKS.keys()}, "rewarded": False},
            "boss_id": get_value("boss_id"),
            "boss_hp": get_value("boss_hp", 0),
            "story_chapter": get_value("story_chapter", 0),
            "rebirths": get_value("rebirths", 0),
            "hardcore": get_value("hardcore", 0),
        }
        for rarity in RARITIES.keys():
            if rarity not in data["monkeys"]: data["monkeys"][rarity] = 0
    else:
        today = datetime.date.today().isoformat()
        data = {
            "user_id": user_id, "name": user_name, "bananas": 0, "defeated": 0,
            "last_internet_pay": 0, "boxes_opened": 0, "merges": 0, "robberies": 0,
            "casino_wins": 0, "internet_payments": 0, "last_seen": time.time(), 
            "monkeys": {rarity: 0 for rarity in RARITIES.keys()},
            "achievements": [], "bosses_defeated": [], 
            "daily_quests": {"date": today, "tasks": list(DAILY_TASKS.keys()), "progress": {t: 0 for t in DAILY_TASKS.keys()}, "rewarded": False}, 
            "boss_id": None, "boss_hp": 0, "story_chapter": 0, "rebirths": 0, "hardcore": 0
        }
        save_player(user_id, data)
    conn.close()
    return data

def save_player(user_id: int, data: dict):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO players (
            user_id, name, bananas, defeated, last_internet_pay, boxes_opened, merges,
            robberies, casino_wins, internet_payments, last_seen, monkeys,
            achievements, bosses_defeated, daily_quests, boss_id, boss_hp, story_chapter, rebirths, hardcore
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, data["name"], data["bananas"], data["defeated"], data["last_internet_pay"],
        data["boxes_opened"], data["merges"], data["robberies"], data["casino_wins"],
        data["internet_payments"], data["last_seen"], json.dumps(data["monkeys"], ensure_ascii=False),
        json.dumps(data["achievements"], ensure_ascii=False), json.dumps(data["bosses_defeated"], ensure_ascii=False),
        json.dumps(data["daily_quests"], ensure_ascii=False), data.get("boss_id"), data.get("boss_hp", 0),
        data.get("story_chapter", 0), data.get("rebirths", 0), data.get("hardcore", 0)
    ))
    conn.commit()
    conn.close()

def get_all_player_ids():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM players")
    ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return ids

def build_game_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("Бежать до сваих"), KeyboardButton("Махаться с чужими")],
        [KeyboardButton("Вскрыть карыто (5 🍌)"), KeyboardButton("🌟 Золотое карыто (50 🍌)")],
        [KeyboardButton("🚀 МЕГА КАРЫТО (5000 🍌)"), KeyboardButton("🎰 Слот-машина")],
        [KeyboardButton("👹 Логово Босса"), KeyboardButton("🥷 Ограбить")],
        [KeyboardButton("🧬 Склещить бибизян"), KeyboardButton("📰 Бибизяни новости")],
        [KeyboardButton("📖 Сюжет"), KeyboardButton("🎖 Ачивки")],
        [KeyboardButton("🏆 Вожаки стаи"), KeyboardButton("📜 Квесты")],
        [KeyboardButton("📖 Кодекс"), KeyboardButton("🌐 Оплатить связь (50 🍌)")],
        [KeyboardButton("Чо в кармане?")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================= РАСЧЕТ ДОХОДА (С УЧЕТОМ РЕБИТОВ) =================
def calculate_income(monkeys: dict, rebirths: int, hardcore: int) -> int:
    base_income = 0
    for rarity, count in monkeys.items():
        if count <= 0:
            continue
        base_income += count * RARITIES[rarity]["income"]

    multiplier = 1.0 + (rebirths * BALANCE["rebirth_income_bonus"])
    if hardcore:
        multiplier *= BALANCE["hardcore_income_bonus"]

    return int(base_income * multiplier)

# ================= ФОНОВЫЕ ЗАДАЧИ =================
async def passive_income_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    current_time = time.time()
    user_ids = get_all_player_ids()
    
    global_event = None
    if random.random() < 0.03:
        event_type = random.choice(["rain", "locusts", "sun", "hangover", "riot"])
        if event_type == "rain": global_event = "🌧 **БАНАНОВЫЙ ДОЖДЬ!** Всем +50 🍌!"
        elif event_type == "locusts": global_event = "🦗 **НАШЕСТВИЕ САРАНЧИ!** Все потеряли 10% бананов!"
        elif event_type == "sun": global_event = "☀️ **АНОМАЛЬНАЯ ЖАРА!** Всем +25 🍌!"
        elif event_type == "hangover": global_event = "🥃 **БАНАНОВОЕ ПОХМЕЛЬЕ!** Все бибизяны работают х2 быстрее на 10 минут!"
        elif event_type == "riot": global_event = "🥊 **БУНТ В СТАЕ!** Заплатите 100 бананов, или стая объявит забастовку!"

    for uid in user_ids:
        user_data = load_player(uid)
        needs_save = False
        
        # Глобальные ивенты
        if global_event:
            if event_type == "rain": user_data["bananas"] += 50
            elif event_type == "locusts": user_data["bananas"] = max(0, int(user_data["bananas"] * 0.9))
            elif event_type == "sun": user_data["bananas"] += 25
            elif event_type == "hangover": 
                user_data["hangover_bonus"] = current_time + 600
                user_data["bananas"] += 50 # Доп. стартовый бонус
            elif event_type == "riot":
                if user_data["bananas"] >= 100:
                    user_data["bananas"] -= 100
                    user_data["bananas"] += 50 # Взнос за спокойствие
                else:
                    user_data["strike"] = current_time + 600 # Забастовка на 10 минут
            try: await context.bot.send_message(chat_id=uid, text=global_event, parse_mode="Markdown")
            except: pass
            needs_save = True

        # Проверка интернета
        if (current_time - user_data.get("last_internet_pay", 0)) >= 86400:
            try: await context.bot.send_message(chat_id=uid, text="⚠️ **ИНТЕРНЕТ ОТКЛЮЧЕН!**", parse_mode="Markdown")
            except: pass
            save_player(uid, user_data)
            continue

        # Пассивный доход
        income = calculate_income(user_data["monkeys"], user_data["rebirths"], user_data["hardcore"])
        
        # Бафф от похмелья
        if "hangover_bonus" in user_data and current_time < user_data["hangover_bonus"]:
            income *= 2
        
        # Дебафф от забастовки
        if "strike" in user_data and current_time < user_data["strike"]:
            income = 0
        
        if income > 0:
            user_data["bananas"] += income
            try: await context.bot.send_message(chat_id=uid, text=f"🏪 Бибизяны натаскали **+{income} 🍌**!", parse_mode="Markdown")
            except: pass
            needs_save = True
        
        # Редкие катастрофы (шанс 0.01% в минуту)
        if random.random() < 0.0001:
            if user_data["bananas"] > 0 or sum(user_data["monkeys"].values()) > 0:
                try:
                    with open(VOLCANO_IMAGE, "rb") as photo:
                        await context.bot.send_photo(chat_id=uid, photo=photo, caption="🌋 **ВАХУН! ИЗВЕРЖЕНИЕ!**\nСмыло 50% бананов и половину стаи!", parse_mode="Markdown")
                    user_data["bananas"] = int(user_data["bananas"] * 0.5)
                    for rarity in user_data["monkeys"]: user_data["monkeys"][rarity] = int(user_data["monkeys"][rarity] * 0.5)
                    needs_save = True
                except: pass
                
        if needs_save:
            save_player(uid, user_data)

# ================= ОБРАБОТЧИКИ =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.effective_user.first_name or "Бибизяна"
    user_data = load_player(update.effective_user.id, user_name)
    now = time.time()
    time_offline = now - user_data["last_seen"]
    offline_msg = ""
    
    if time_offline > 60:
        time_offline = min(time_offline, 8 * 3600)
        income = calculate_income(user_data["monkeys"], user_data["rebirths"], user_data["hardcore"])
        earned = int(income * (time_offline / 60))
        if earned > 0:
            user_data["bananas"] += earned
            offline_msg = f"\n\n💤 **Пока тебя не было, бибизяны работали!**\nТы заработал: **+{earned} 🍌**"
    
    user_data["last_seen"] = now
    save_player(update.effective_user.id, user_data)

    title = get_title(user_data["bananas"])
    await update.message.reply_text(
        f"🍌 Уа-уа, **{user_name}**! Твой титул: {title}\nЖми кнопки, чтобы лутать бананы!{offline_msg}\n\n⚠️ *Не забудь оплатить интернет!*",
        reply_markup=build_game_keyboard(), parse_mode="Markdown"
    )

async def check_achievements(context: ContextTypes.DEFAULT_TYPE, chat_id: int, ud: dict) -> dict:
    def grant(key: str):
        if key in ud.get("achievements", []):
            return
        ud.setdefault("achievements", []).append(key)
        reward = ACHIEVEMENTS[key]["reward"]
        if ud.get("hardcore", 0) == 1:
            reward = int(reward / 2)
        ud["bananas"] += reward
        granted.append((key, reward))

    granted = []
    keys = ud.get("achievements", [])
    ud["achievements"] = keys

    if ud.get("boxes_opened", 0) >= 1:
        grant("first_box")
    if ud.get("bananas", 0) >= 1000:
        grant("rich_1000")
    if ud.get("bananas", 0) >= 10000:
        grant("rich_10000")
    if ud.get("defeated", 0) >= 10:
        grant("killer_10")
    if ud.get("defeated", 0) >= 50:
        grant("killer_50")
    if ud.get("merges", 0) >= 10:
        grant("merge_10")
    if ud.get("robberies", 0) >= 5:
        grant("robber_5")
    if ud.get("casino_wins", 0) >= 5:
        grant("casino_win_5")
    if ud.get("internet_payments", 0) >= 3:
        grant("internet_3")
    if ud.get("monkeys", {}).get("Миф 🛸", 0) > 0:
        grant("mythic_owner")
    if ud.get("monkeys", {}).get("Легенда 🚬", 0) > 0:
        grant("legend_owner")
    if ud.get("bosses_defeated") and len(ud["bosses_defeated"]) > 0:
        grant("boss_slayer")
    if len(set(ud.get("bosses_defeated", []))) >= len(BOSSES):
        grant("all_bosses")
    if ud.get("monkeys", {}).get("true bibizan 👑🐒", 0) > 0:
        grant("true_owner")
    if "mega_owner" in ud.get("achievements", []):
        grant("mega_owner")

    required = [key for key in ACHIEVEMENTS.keys() if key != "completionist"]
    if all(key in ud.get("achievements", []) for key in required):
        grant("completionist")

    if granted and context is not None:
        lines = [f"🎖 **{ACHIEVEMENTS[key]['name']}** (+{reward} 🍌)" for key, reward in granted]
        await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode="Markdown")

    return ud

async def handler_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text: return
    user_id = update.effective_user.id
    
    # Блокировка Race Condition
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()

    async with user_locks[user_id]:
        ud = load_player(user_id, update.effective_user.first_name or "Бибизяна")
        ud["last_seen"] = time.time()
        text = update.message.text
        current_time = time.time()

        # Очистка старых дебаффов
        if "strike" in ud and current_time > ud["strike"]: ud.pop("strike")
        if "hangover_bonus" in ud and current_time > ud["hangover_bonus"]: ud.pop("hangover_bonus")

        # --- КНОПКИ ---
        multiplier = 10 if ud.get("hardcore", 0) == 1 else 1

        if text == "📖 Сюжет":
            chap_id = ud.get("story_chapter", 0)
            if chap_id >= len(STORY_CHAPTERS):
                await update.message.reply_text("🏆 **Ты прошел весь сюжет!** Ты стал легендой джунглей!")
                save_player(user_id, ud)
                return
            chap = STORY_CHAPTERS[chap_id]
            progress = 0
            if chap["type"] == "boxes": progress = ud["boxes_opened"]
            elif chap["type"] == "fights": progress = ud["defeated"]
            elif chap["type"] == "merges": progress = ud["merges"]
            elif chap["type"] == "bananas": progress = ud["bananas"]
            elif chap["type"] == "bosses": progress = len(ud["bosses_defeated"])
            
            if progress >= chap["target"]:
                ud["story_chapter"] += 1
                ud["bananas"] += chap["reward"]
                await update.message.reply_text(f"🎉 **{chap['name']} ВЫПОЛНЕНА!**\n💰 Награда: **+{chap['reward']} 🍌**", parse_mode="Markdown")
                save_player(user_id, ud)
                return
            
            await update.message.reply_text(
                f"📖 **{chap['name']}**\n\n📝 Задание: {chap['desc']}\n📊 Прогресс: {progress} / {chap['target']}\n💰 Награда: {chap['reward']} 🍌",
                parse_mode="Markdown"
            )
            save_player(user_id, ud)
            return

        elif text == "Бежать до сваих":
            is_win = random.choice([True, False])
            if is_win:
                ud["bananas"] += 1
                try:
                    with open(WIN_IMAGE_PATH, "rb") as photo_file:
                        await update.message.reply_photo(photo=photo_file, caption=f"ты дабежал да сваих\nБананов: {ud['bananas']}")
                except FileNotFoundError:
                    await update.message.reply_text(f"ты дабежал да сваих\nБананов: {ud['bananas']}")
            else:
                try:
                    with open(LOSE_GIF_PATH, "rb") as gif_file:
                        await update.message.reply_animation(animation=gif_file, caption=f"ты пагиб🥀\nБананов: {ud['bananas']}")
                except FileNotFoundError:
                    await update.message.reply_text(f"ты пагиб🥀\nБананов: {ud['bananas']}")
            ud = await check_achievements(context, update.effective_chat.id, ud)

        # --- КАРЫТА (с учетом Хардкора) ---
        elif text == "🚀 МЕГА КАРЫТО (5000 🍌)":
            cost = BALANCE["mega_box_cost"] * multiplier
            if ud["bananas"] < cost:
                await update.message.reply_text(f"❌ Нужно {cost} 🍌! У тебя {ud['bananas']}.")
                return
            ud["bananas"] -= cost
            ud["boxes_opened"] += 1
            ud["mega_boxes_opened"] = ud.get("mega_boxes_opened", 0) + 1
            
            mega_rarities = ["Абсолют 🗿", "sub-3 🥉", "sub-5 🥈", "ltb 🧢", "mtb 👽", "htb 🗿", "chad 🗿🍷", "true bibizan 👑🐒"]
            mega_weights = [35, 25, 15, 10, 7, 5, 2, 1]
            dropped = random.choices(mega_rarities, weights=[w * BALANCE["mega_drop_bias"] for w in mega_weights], k=1)[0]
            ud["monkeys"][dropped] += 1
            
            if "mega_owner" not in ud["achievements"]:
                reward = 1000 if ud.get("hardcore", 0) == 0 else 500
                ud["achievements"].append("mega_owner")
                ud["bananas"] += reward
                await update.message.reply_text(f"🎖 **ДОСТИЖЕНИЕ:** Мега-Лудоман (+{reward} 🍌)!", parse_mode="Markdown")

            try:
                with open(os.path.join(BASE_DIR, random.choice(RARITIES[dropped]["images"])), "rb") as f:
                    await update.message.reply_photo(photo=f, caption=f"🚀 Из **МЕГА КАРЫТА** (за {cost} 🍌) выпрыгнул: **{dropped}**!\nБананов: {ud['bananas']}", parse_mode="Markdown")
            except FileNotFoundError:
                await update.message.reply_text(f"🚀 Из **МЕГА КАРЫТА** выпрыгнул: **{dropped}**!\nБананов: {ud['bananas']}", parse_mode="Markdown")
            ud = await check_achievements(context, update.effective_chat.id, ud)

        elif text == "🌟 Золотое карыто (50 🍌)":
            cost = BALANCE["gold_box_cost"] * multiplier
            if ud["bananas"] < cost:
                await update.message.reply_text(f"❌ Нужно {cost} 🍌!")
                return
            ud["bananas"] -= cost
            ud["boxes_opened"] += 1
            dropped = random.choices(["Эпик 👑", "Легенда 🚬", "Миф 🛸", "Батя Джунглей 🌋", "Бог 🪐", "Абсолют 🗿"], weights=[40, 30, 18, 8, 3, 1], k=1)[0]
            ud["monkeys"][dropped] += 1

            try:
                with open(os.path.join(BASE_DIR, random.choice(RARITIES[dropped]["images"])), "rb") as f:
                    await update.message.reply_photo(photo=f, caption=f"🌟 Из **ЗОЛОТОГО КАРЫТА** (за {cost} 🍌) выпрыгнула: **{dropped}**!\nБананов: {ud['bananas']}", parse_mode="Markdown")
            except FileNotFoundError:
                await update.message.reply_text(f"🌟 Из **ЗОЛОТОГО КАРЫТА** выпрыгнула: **{dropped}**!\nБананов: {ud['bananas']}", parse_mode="Markdown")
            ud = await check_achievements(context, update.effective_chat.id, ud)

        elif text == "Вскрыть карыто (5 🍌)":
            cost = BALANCE["normal_box_cost"] * multiplier
            if ud["bananas"] < cost:
                await update.message.reply_text(f"❌ Надо {cost} 🍌.")
                return
            ud["bananas"] -= cost
            ud["boxes_opened"] += 1
            
            rarities_list = [r for r in RARITIES.keys() if RARITIES[r]["weight"] > 0]
            dropped = random.choices(rarities_list, weights=[RARITIES[r]["weight"] for r in rarities_list], k=1)[0]
            ud["monkeys"][dropped] += 1

            try:
                with open(os.path.join(BASE_DIR, random.choice(RARITIES[dropped]["images"])), "rb") as f:
                    await update.message.reply_photo(photo=f, caption=f"📦 Из карыта (за {cost} 🍌) выпрыгнула: **{dropped}**!\nБананов: {ud['bananas']}", parse_mode="Markdown")
            except FileNotFoundError:
                await update.message.reply_text(f"📦 Из карыта выпрыгнула: **{dropped}**!\nБананов: {ud['bananas']}", parse_mode="Markdown")
            ud = await check_achievements(context, update.effective_chat.id, ud)

        elif text == "Махаться с чужими":
            if ud["bananas"] < 5 * multiplier:
                await update.message.reply_text(f"❌ Для махача надо {5 * multiplier} 🍌!")
                return

            monkeys = ud["monkeys"]
            team = [r for r, c in monkeys.items() if c > 0]
            team_str = ", ".join(team) if team else "В адиночку 👤"

            enemy_team_list, enemy_total_count, enemy_power = [], 0, 0
            rarities_list = list(RARITIES.keys())
            weights_list = [45, 30, 15, 7, 2.9, 0.1, 0.05, 0.01, 0.001, 0.0001, 0.00001, 0.000001, 0.0000001, 0.00000001, 0.000000001] + [0]*4
            
            for _ in range(random.randint(1, 4)):
                e_rarity = random.choices(rarities_list, weights=weights_list, k=1)[0]
                enemy_team_list.append(e_rarity)
                enemy_total_count += 1
                enemy_power += RARITIES[e_rarity]["income"]
                
            player_power = sum(monkeys.get(r, 0) * d["income"] for r, d in RARITIES.items())
            final_lose_chance = max(10, min(90, 50 + (enemy_power * 0.01) - (player_power * 0.01))) 
            
            battle_text = f"⚔️ **{random.choice(ATTACK_TYPES)}!**\n\n👥 **Твоя стая:** {team_str}\n💀 **Вражья стая:** {', '.join(enemy_team_list)}\n\n📉 Шанс праиграть: {final_lose_chance}%"

            try:
                with open(random.choice(WAR_IMAGES), "rb") as photo:
                    await update.message.reply_photo(photo=photo, caption=battle_text, parse_mode="Markdown")
            except FileNotFoundError:
                await update.message.reply_text(battle_text, parse_mode="Markdown")

            if random.randint(1, 100) > final_lose_chance:
                ud["bananas"] += 5 * multiplier
                ud["defeated"] += enemy_total_count
                if "fight_1" in ud["daily_quests"]["progress"] and ud["daily_quests"]["progress"]["fight_1"] < 1:
                    ud["daily_quests"]["progress"]["fight_1"] += 1
                await update.message.reply_text(f"🎉 **ПАБЕДА!**\n💰 **+{5 * multiplier} 🍌**\n🍌 Бананов: {ud['bananas']}", parse_mode="Markdown")
            else:
                ud["bananas"] -= 5 * multiplier
                loss_msg = f"😢 **АБЛАЖАЛСЯ.**\nТы потерял {5 * multiplier} 🍌.\n"
                if team and random.randint(1, 100) <= 35:
                    dead = random.choice(team)
                    ud["monkeys"][dead] -= 1
                    loss_msg += f"\n🥀 Пагибла **{dead}**..."
                loss_msg += f"\n🍌 Бананов: {ud['bananas']}"
                await update.message.reply_text(loss_msg, parse_mode="Markdown")
            ud = await check_achievements(context, update.effective_chat.id, ud)

        elif text == "🧬 Склещить бибизян":
            monkeys = ud["monkeys"]
            msg = "🧬 **ЛАБАРАТОРИЯ СНОШАНИЯ**\n\n"
            merged = False
            tiers = ["Абычная 🐒", "Рицкая 🦧", "Эпик 👑", "Легенда 🚬", "Миф 🛸", "Батя Джунглей 🌋", "Бог 🪐", "Абсолют 🗿", "sub-3 🥉", "sub-5 🥈", "ltb 🧢", "mtb 👽", "htb 🗿", "chad 🗿🍷", "true bibizan 👑🐒"]
            
            for i in range(len(tiers) - 1):
                curr, nxt = tiers[i], tiers[i+1]
                if monkeys[curr] >= 3:
                    merge_count = monkeys[curr] // 3
                    monkeys[curr] -= merge_count * 3
                    monkeys[nxt] += merge_count
                    msg += f"✅ {merge_count * 3} шт. {curr} нарожали {merge_count} шт. {nxt}!\n"
                    merged = True
                    
                    # ШАНС МУТАЦИИ 1%
                    if random.random() < 0.01:
                        mut = random.choice(["Золотая Абычная 🐒✨", "Кибер-Эпик 👑🤖", "Радиоактивная Легенда 🚬☢️", "Космический Миф 🛸🌌"])
                        monkeys[mut] += 1
                        msg += f"🧬 **МУТАЦИЯ!** Радиация породила **{mut}**!\n"
                        
            if merged: 
                ud["merges"] += 1
                await update.message.reply_text(msg, parse_mode="Markdown")
                ud = await check_achievements(context, update.effective_chat.id, ud)
            else: await update.message.reply_text("❌ Мало бибизян. Надо по 3 штуки.", parse_mode="Markdown")

        elif text == "📜 Квесты":
            quests = ud["daily_quests"]
            today = datetime.date.today().isoformat()
            if quests.get("date") != today:
                ud["daily_quests"] = {"date": today, "tasks": list(DAILY_TASKS.keys()), "progress": {t: 0 for t in DAILY_TASKS.keys()}, "rewarded": False}
                quests = ud["daily_quests"]
                
            msg = "📜 **ЕЖЕДНЕВНЫЕ КВЕСТЫ:**\n\n"
            all_done = True
            for task_id in quests["tasks"]:
                info = DAILY_TASKS[task_id]
                prog = quests["progress"].get(task_id, 0)
                if prog >= info["target"]: msg += f"✅ {info['text']} (Выполнено!)\n"
                else:
                    msg += f"🔹 {info['text']} (Прогресс: {prog}/{info['target']})\n"
                    all_done = False
                    
            if all_done and not quests["rewarded"]:
                reward = 500 if ud.get("hardcore", 0) == 0 else 250
                ud["bananas"] += reward
                quests["rewarded"] = True
                msg += f"\n🎁 **ВСЕ КВЕСТЫ ВЫПОЛНЕНЫ!**\nТы получил сундук с **+{reward} 🍌**!"
            elif quests["rewarded"]: msg += "\n🎁 Ты уже забрал награду за сегодня. Приходи завтра!"
            else: msg += f"\n(Выполни все 3 задания, чтобы получить **+{500 if ud.get('hardcore', 0) == 0 else 250} 🍌**)"
                
            await update.message.reply_text(msg, parse_mode="Markdown")

        elif text == "🏆 Вожаки стаи":
            players = [load_player(uid) for uid in get_all_player_ids()]
            sorted_players = sorted(players, key=lambda x: x.get("bananas", 0), reverse=True)[:5]
            
            msg = "🏆 **ТОП-5 ВОЖАКОВ:**\n\n"
            for i, p in enumerate(sorted_players, 1):
                title = get_title(p.get("bananas", 0))
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔹"
                msg += f"{medal} {p.get('name')} — {p.get('bananas', 0)} 🍌 (Титул: {title})\n"
            await update.message.reply_text(msg, parse_mode="Markdown")

        elif text == "Чо в кармане?":
            monkeys = ud["monkeys"]
            speed = calculate_income(monkeys, ud["rebirths"], ud["hardcore"])
            is_active = (time.time() - ud.get("last_internet_pay", 0)) < 86400
            title = get_title(ud["bananas"])
            rebirths = ud["rebirths"]
            hardcore_status = "🔴 ХАРДКОР" if ud.get("hardcore", 0) == 1 else "🟢 Обычный"
            
            info = (
                f"💼 **ПРОФИЛЬ:**\n"
                f"🎖 Титул: **{title}**\n"
                f"🌐 Интернет: {'✅ Вкл' if is_active else '❌ Выкл'}\n"
                f"🔄 Перерождения: {rebirths} (+{rebirths * 10}% к доходу)\n"
                f"⚔️ Режим: {hardcore_status}\n"
                f"🍌 Бананы: {ud['bananas']}\n"
                f"📈 Доход: +{speed} 🍌/мин\n\n"
                f"🏆 **Стая:**\n"
            )
            for r in RARITIES.keys(): 
                if monkeys.get(r, 0) > 0: info += f"◽ {r}: {monkeys.get(r, 0)}\n"
            
            # Кнопка перерождения
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔄 ПЕРЕРОДИТЬСЯ (Ребит)", callback_data="rebirth_normal"))
            if ud["rebirths"] > 0:
                keyboard.add(InlineKeyboardButton("🔥 ХАРДКОР РЕБИТ", callback_data="rebirth_hardcore"))
            
            await update.message.reply_text(info, reply_markup=keyboard, parse_mode="Markdown")

        # --- ОПЛАТА ИНТЕРНЕТА ---
        elif text == "🌐 Оплатить связь (50 🍌)":
            cost = 50 * multiplier
            current_time = time.time()
            if current_time - ud["last_internet_pay"] < 86400:
                await update.message.reply_text(f"✅ Связь уже оплачена!")
                return
            if ud["bananas"] < cost:
                await update.message.reply_text(f"❌ Надо {cost} 🍌.")
                return
            ud["bananas"] -= cost
            ud["last_internet_pay"] = current_time
            ud["internet_payments"] += 1
            await update.message.reply_text(f"🌐 **ИНТЕРНЕТ ПОДКЛЮЧЕН!**", parse_mode="Markdown")
            ud = await check_achievements(context, update.effective_chat.id, ud)

        elif text == "🎰 Слот-машина":
            if ud["bananas"] < 10 * multiplier:
                await update.message.reply_text(f"❌ Нужно {10 * multiplier} 🍌!")
                return
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("10%", callback_data="bet_10p"), InlineKeyboardButton("25%", callback_data="bet_25p"), InlineKeyboardButton("50%", callback_data="bet_50p"), InlineKeyboardButton("ALL-IN", callback_data="bet_100p")]
            ])
            await update.message.reply_text("🎰 **Выбери ставку:**", reply_markup=keyboard, parse_mode="Markdown")
            save_player(user_id, ud)
            return

        elif text == "🥷 Ограбить":
            others = [uid for uid in get_all_player_ids() if uid != user_id]
            if not others:
                await update.message.reply_text("В джунглях никого нет.")
                return
            victim_id = random.choice(others)
            v = load_player(victim_id)
            if v["bananas"] < 10 * multiplier:
                await update.message.reply_text(f"У **{v['name']}** меньше {10 * multiplier} бананов.")
                return
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Напасть!", callback_data=f"rob_{victim_id}")], [InlineKeyboardButton("Свалить", callback_data="rob_cancel")]])
            await update.message.reply_text(f"🥷 Ты выследил **{v['name']}**!\nУ него **{v['bananas']} 🍌**.", reply_markup=keyboard)
            save_player(user_id, ud)
            return

        elif text == "👹 Логово Босса":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🍌 Владыка (500)", callback_data="boss_overlord"), InlineKeyboardButton("🦍 Горилла (2К)", callback_data="boss_gorilla")],
                [InlineKeyboardButton("👹 Старый Бог (5К)", callback_data="boss_god"), InlineKeyboardButton("🤖 Кибер (10К)", callback_data="boss_robot")],
                [InlineKeyboardButton("🗿🍷 Гигачад (50К)", callback_data="boss_chad")],
                [InlineKeyboardButton("👑🐒 True Bibizan (1М)", callback_data="boss_true_bibizan")]
            ])
            await update.message.reply_text("👹 **Выбери босса:**", reply_markup=keyboard, parse_mode="Markdown")
            save_player(user_id, ud)
            return

        elif text == "📰 Бибизяни новости":
            await update.message.reply_text(f"📰 **НОВОСТИ** ⚡️\n\n{random.choice(NEWS_LIST)}", parse_mode="Markdown")

        elif text == "🎖 Ачивки":
            msg = "🎖 **ТВОИ ДОСТИЖЕНИЯ:**\n\n"
            for key, ach in ACHIEVEMENTS.items():
                if key in ud["achievements"]: 
                    reward = ach["reward"]
                    if ud.get("hardcore", 0) == 1:
                        reward = int(reward / 2)
                    msg += f"✅ {ach['name']} (Награда: {reward} 🍌)\n"
                else: msg += f"🔒 {ach['name']}\n"
            await update.message.reply_text(msg, parse_mode="Markdown")

        elif text == "📖 Кодекс":
            msg = "📖 **КОДЕКС:**\n\n"
            for r, d in BESTIARY.items():
                count = ud['monkeys'].get(r, 0)
                msg += f"**{r}** (У тебя: {count})\n_{d}_\n\n"
            await update.message.reply_text(msg, parse_mode="Markdown")

        else:
            await update.message.reply_text("Тыкай кнопки внизу, уа-уа 👇")
            
        save_player(user_id, ud)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()

    async with user_locks[user_id]:
        ud = load_player(user_id)
        
        if query.data.startswith("rebirth_"):
            mode = query.data.split("_")[1]
            if mode == "normal":
                ud["rebirths"] += 1
                ud["bananas"] = 0
                ud["monkeys"] = {r: 0 for r in RARITIES.keys()}
                ud["boss_id"] = None
                ud["boss_hp"] = 0
                ud["achievements"] = []
                ud["bosses_defeated"] = []
                await query.edit_message_text("🔄 **ТЫ ПЕРЕРОДИЛСЯ!**\nТвои бананы и стая сброшены.\nНо теперь ты получаешь **+10%** ко всем доходам навсегда.\nУа-уа, новая жизнь!", reply_markup=build_game_keyboard())
            elif mode == "hardcore":
                if ud.get("hardcore", 0) == 1:
                    await query.answer("Ты уже в хардкоре!", show_alert=True)
                    return
                ud["rebirths"] += 1
                ud["hardcore"] = 1
                ud["bananas"] = 0
                ud["monkeys"] = {r: 0 for r in RARITIES.keys()}
                ud["boss_id"] = None
                ud["boss_hp"] = 0
                ud["achievements"] = []
                ud["bosses_defeated"] = []
                await query.edit_message_text("🔥 **ХАРДКОР АКТИВИРОВАН!**\nЦены x10. Награды за ачивки x0.5. Удачи, мазохист.", reply_markup=build_game_keyboard())
            save_player(user_id, ud)
            return

        elif query.data.startswith("boss_"):
            boss_id = query.data.split("_", 1)[1]
            if boss_id in BOSSES:
                ud["boss_id"] = boss_id
                ud["boss_hp"] = BOSSES[boss_id]["hp"]
                await query.edit_message_text(f"{BOSSES[boss_id]['name']} пробудился!\nУ него **{BOSSES[boss_id]['hp']} HP**.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Атаковать", callback_data="boss_attack")]]), parse_mode="Markdown")
        
        elif query.data == "boss_attack":
            boss_id = ud.get("boss_id")
            if not boss_id: return
            boss = BOSSES[boss_id]
            if ud.get("boss_hp", 0) <= 0:
                await query.edit_message_text("👹 Босс мертв.")
                return
            if ud["bananas"] < BALANCE["boss_attack_cost"]:
                await query.answer(f"❌ Надо {BALANCE['boss_attack_cost']} бананов!", show_alert=True)
                return

            ud["bananas"] -= BALANCE["boss_attack_cost"]
            power = sum(ud["monkeys"].get(r, 0) * d["income"] for r, d in RARITIES.items())
            dmg = max(10, power * random.randint(1, 3))
            ud["boss_hp"] -= dmg
            
            if ud["boss_hp"] <= 0:
                reward = int(boss["reward"] * BALANCE["boss_reward_multiplier"])
                if ud.get("hardcore", 0) == 1:
                    reward = int(reward / 2)
                ud["bananas"] += reward
                ud["boss_hp"] = 0
                if boss_id not in ud["bosses_defeated"]: ud["bosses_defeated"].append(boss_id)
                await query.edit_message_text(f"💀 **ПОБЕДА!**\nНаграда: **+{reward} 🍌**!", parse_mode="Markdown")
                ud["boss_id"] = None
                ud = await check_achievements(context, update.effective_chat.id, ud)
            else:
                ctr_dmg = random.randint(boss["damage"][0], boss["damage"][1])
                ud["bananas"] = max(0, ud["bananas"] - ctr_dmg)
                hp_bar = "█" * int((ud['boss_hp'] / boss['hp']) * 10) + "░" * (10 - int((ud['boss_hp'] / boss['hp']) * 10))
                await query.edit_message_text(f"{boss['name']} **БИТВА**\n❤️ {hp_bar} ({ud['boss_hp']}/{boss['hp']})\n⚔️ Урон: {dmg}. 🩸 Босс отнял {ctr_dmg} 🍌.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Атаковать", callback_data="boss_attack")]]), parse_mode="Markdown")

        elif query.data.startswith("bet_"):
            pct = int(query.data.split("_")[1].replace("p", ""))
            amount = int(ud["bananas"] * (pct / 100)) if pct < 100 else ud["bananas"]
            if amount < 1: await query.answer("Мало бананов!", show_alert=True); return
            ud["bananas"] -= amount
            await query.edit_message_text(f"🎰 Ставка: **{amount} 🍌**...", parse_mode="Markdown")
            await asyncio.sleep(1.0)
            roll = random.random()
            if roll < 0.45:
                ud["bananas"] += amount * 2
                ud["casino_wins"] = ud.get("casino_wins", 0) + 1
                await query.edit_message_text(f"🎰 **ВЫИГРЫШ x2!** +{amount*2} 🍌\nБаланс: {ud['bananas']}", parse_mode="Markdown")
                ud = await check_achievements(context, update.effective_chat.id, ud)
            elif roll < 0.90:
                await query.edit_message_text(f"🎰 **ПРОИГРЫШ.** -{amount} 🍌\nБаланс: {ud['bananas']}", parse_mode="Markdown")
            else:
                ud["bananas"] += amount * 5
                ud["casino_wins"] = ud.get("casino_wins", 0) + 1
                await query.edit_message_text(f"💎 **ДЖЕКПОТ x5!** +{amount*5} 🍌\nБаланс: {ud['bananas']}", parse_mode="Markdown")
                ud = await check_achievements(context, update.effective_chat.id, ud)
        
        elif query.data.startswith("rob_"):
            if query.data == "rob_cancel":
                await query.edit_message_text("🥷 Ты свалил.")
                return
            v_id = int(query.data.split("_")[1])
            v = load_player(v_id)
            if random.choice([True, False]):
                stolen = int(v["bananas"] * 0.15)
                ud["bananas"] += stolen
                v["bananas"] -= stolen 
                ud["robberies"] += 1
                await query.edit_message_text(f"🥷 **УСПЕХ!** Ты украл **{stolen} 🍌** у {v['name']}!", parse_mode="Markdown")
                save_player(v_id, v)
                ud = await check_achievements(context, update.effective_chat.id, ud)
            else:
                lost = int(ud["bananas"] * 0.10)
                ud["bananas"] = max(0, ud["bananas"] - lost)
                v["bananas"] += lost 
                await query.edit_message_text(f"🚨 **ПРОВАЛ!** {v['name']} отобрал у тебя **{lost} 🍌**!", parse_mode="Markdown")
                save_player(v_id, v)

        save_player(user_id, ud)

if __name__ == "__main__":
    init_db()
    req = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, write_timeout=30.0, pool_timeout=30.0)
    app = ApplicationBuilder().token(TOKEN).request(req).get_updates_request(req).build()
    
    job_queue = app.job_queue
    job_queue.run_repeating(passive_income_callback, interval=60, first=10)
    job_queue.run_daily(lambda context: None, datetime.time(hour=0, minute=0)) # Для сброса времени (заглушка)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler_text))
    app.add_handler(CallbackQueryHandler(callback_handler)) 
    
    print("✅ Бот запущен! Ребиты, Хардкор и фиксы активированы.")
    app.run_polling()