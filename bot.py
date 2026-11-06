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
DB_NAME = "bibizyana.db"

# --- СБАЛАНСИРОВАННАЯ СИСТЕМА РЕДКОСТЕЙ ---
RARITIES = {
    "Абычная 🐒": {"income": 1, "weight": 45, "images": ["1000097597.jpg", "normal.png"]},
    "Рицкая 🦧": {"income": 5, "weight": 30, "images": ["1000097589.jpg", "rare.png"]},
    "Эпик 👑": {"income": 20, "weight": 15, "images": ["1000097599.jpg", "epic.png"]},
    "Легенда 🚬": {"income": 100, "weight": 7, "images": ["1000097591.jpg", "1000097595.jpg"]},
    "Миф 🛸": {"income": 500, "weight": 2.9, "images": ["1000097592.jpg", "1000097596.jpg"]},
    "Батя Джунглей 🌋": {"income": 2000, "weight": 0.1, "images": ["1000097590.jpg"]},
    "Бог 🪐": {"income": 5000, "weight": 0.05, "images": ["1000097593.jpg"]},
    "Абсолют 🗿": {"income": 15000, "weight": 0.01, "images": ["1000097601.jpg"]},
    # Мемные тиры (Только из Мега Карыта)
    "sub-3 🥉": {"income": 30000, "weight": 0, "images": ["b1440287a688e886fec12b876748a2aa.jpg"]},
    "sub-5 🥈": {"income": 60000, "weight": 0, "images": ["i (1).webp"]},
    "ltb 🧢": {"income": 150000, "weight": 0, "images": ["i.webp"]},
    "mtb 👽": {"income": 300000, "weight": 0, "images": ["i (2).webp"]},
    "htb 🗿": {"income": 500000, "weight": 0, "images": ["i.jpg"]},
    "chad 🗿🍷": {"income": 1000000, "weight": 0, "images": ["1000097602.jpg", "1000097599.jpg"]},
    "true bibizan 👑🐒": {"income": 5000000, "weight": 0, "images": ["0e5f8b1da7b617cb1f6321bda48a9525.jpg", "old_god.jpg"]}
}

BESTIARY = {
    "Абычная 🐒": "Работает за еду, но иногда ворует кожуру. Очень любит спамить кнопки.",
    "Рицкая 🦧": "Уже не обезьяна, но ещё не человек. Носит очки и строит из себя интеллектуала.",
    "Эпик 👑": "Носит корону, хотя прав на трон не имеет. Дерится больно, бананы ест жадно.",
    "Легенда 🚬": "Видел всякое. Курит бамбук, рассказывает байки про старые джунгли.",
    "Миф 🛸": "Прилетел из космоса. Строит пирамиды из бананов по ночам.",
    "Батя Джунглей 🌋": "Легенда. Когда он зевает, деревья сгибаются. Может упасть с балкона.",
    "Бог 🪐": "Создатель джунглей. Может уничтожить лес одним чихом. Требует поклонения.",
    "Абсолют 🗿": "Непостижимая сущность. В его присутствии даже бананы обретают сознание.",
    "sub-3 🥉": "Бронзовый задрот. Фармит бананы 24/7, но всё еще живет в кустах.",
    "sub-5 🥈": "Серебряный стример. Умеет орать на весь лес и кринжевать.",
    "ltb 🧢": "Low Tier Bибизян. Кепка задом наперед, IQ на нуле, но бананов гребет лопатой.",
    "mtb 👽": "Mid Tier Bибизян. Уже наполовину инопланетянин. Общается телепатией.",
    "htb 🗿": "High Tier Bибизян. Выживает даже после ядерного взрыва. Смотрит на всех как на говно.",
    "chad 🗿🍷": "Настоящий Чед. Пьет банановый сок с мизинцем вверх. Все бабы джунглей его любят.",
    "true bibizan 👑🐒": "АБСОЛЮТНЫЙ БОСС. Тот, кто создал этот бот. Имеет бесконечный запас сил и бананов."
}

BOSSES = {
    "overlord": {"name": "🍌 Банановый Владыка", "hp": 500, "reward": 100, "damage": (1, 5)},
    "gorilla": {"name": "🦍 Мутировавшая Горилла", "hp": 2000, "reward": 300, "damage": (5, 15)},
    "god": {"name": "👹 Старый Бог", "hp": 5000, "reward": 500, "damage": (10, 30)},
    "robot": {"name": "🤖 Кибер-Мартышка", "hp": 10000, "reward": 1500, "damage": (20, 50)},
    "chad": {"name": "🗿🍷 Гигачад", "hp": 50000, "reward": 5000, "damage": (100, 300)},
    "true_bibizan": {"name": "👑🐒 True Bibizan", "hp": 1000000, "reward": 100000, "damage": (1000, 5000)}
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
    "🔮 **ГОРОСКОП:** Сатурн в доме бананов. Ожидайте пассивный доход.",
    "💰 **БИРЖА:** Курс True Bibizan достиг небес. Обычные обезьяны в панике.",
    "🚓 **КРИМИНАЛ:** Банда мартышек украла все носки из прачечной.",
    "🔬 **НАУКА:** Ученые выяснили, что если дать бибизяне смартфон, она скачает Telegram.",
    "📢 **РЕКЛАМА:** Скидки на карыто! 2 по цене 3-х!",
]

# ================= БАЗА ДАННЫХ =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY, name TEXT, bananas INTEGER, defeated INTEGER,
            last_internet_pay REAL, boxes_opened INTEGER, merges INTEGER, robberies INTEGER,
            casino_wins INTEGER, internet_payments INTEGER, last_seen REAL, monkeys TEXT,
            achievements TEXT, bosses_defeated TEXT, daily_quests TEXT, boss_id TEXT, boss_hp INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def load_player(user_id: int, user_name: str = "Бибизяна") -> dict:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row:
        data = {
            "user_id": row[0], "name": row[1], "bananas": row[2], "defeated": row[3],
            "last_internet_pay": row[4], "boxes_opened": row[5], "merges": row[6],
            "robberies": row[7], "casino_wins": row[8], "internet_payments": row[9],
            "last_seen": row[10], "monkeys": json.loads(row[11]),
            "achievements": json.loads(row[12]), "bosses_defeated": json.loads(row[13]),
            "daily_quests": json.loads(row[14]), "boss_id": row[15], "boss_hp": row[16]
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
            "boss_id": None, "boss_hp": 0
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
            achievements, bosses_defeated, daily_quests, boss_id, boss_hp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, data["name"], data["bananas"], data["defeated"], data["last_internet_pay"],
        data["boxes_opened"], data["merges"], data["robberies"], data["casino_wins"],
        data["internet_payments"], data["last_seen"], json.dumps(data["monkeys"], ensure_ascii=False),
        json.dumps(data["achievements"], ensure_ascii=False), json.dumps(data["bosses_defeated"], ensure_ascii=False),
        json.dumps(data["daily_quests"], ensure_ascii=False), data.get("boss_id"), data.get("boss_hp", 0)
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

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================
def build_game_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("Бежать до сваих"), KeyboardButton("Махаться с чужими")],
        [KeyboardButton("Вскрыть карыто (5 🍌)"), KeyboardButton("🌟 Золотое карыто (50 🍌)")],
        [KeyboardButton("🚀 МЕГА КАРЫТО (1500 🍌)"), KeyboardButton("🎰 Слот-машина")],
        [KeyboardButton("👹 Логово Босса"), KeyboardButton("🥷 Ограбить")],
        [KeyboardButton("📰 Бибизяни новости"), KeyboardButton("🧬 Склещить бибизян")],
        [KeyboardButton("🏆 Вожаки стаи"), KeyboardButton("🎖 Ачивки")],
        [KeyboardButton("📖 Кодекс"), KeyboardButton("📜 Квесты")],
        [KeyboardButton("🌐 Оплатить связь (50 🍌)"), KeyboardButton("Чо в кармане?")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def check_achievements(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_data: dict):
    unlocked = user_data["achievements"]
    new_unlocks = []
    
    def unlock(ach_id):
        if ach_id not in unlocked:
            user_data["bananas"] += ACHIEVEMENTS[ach_id]["reward"]
            unlocked.append(ach_id)
            new_unlocks.append(ACHIEVEMENTS[ach_id])

    if user_data["boxes_opened"] >= 1: unlock("first_box")
    if user_data["bananas"] >= 1000: unlock("rich_1000")
    if user_data["bananas"] >= 10000: unlock("rich_10000")
    if user_data["defeated"] >= 10: unlock("killer_10")
    if user_data["defeated"] >= 50: unlock("killer_50")
    if user_data["merges"] >= 10: unlock("merge_10")
    if user_data["robberies"] >= 5: unlock("robber_5")
    if user_data["casino_wins"] >= 5: unlock("casino_win_5")
    if user_data["internet_payments"] >= 3: unlock("internet_3")
    
    if user_data["monkeys"].get("Миф 🛸", 0) >= 1: unlock("mythic_owner")
    if user_data["monkeys"].get("Легенда 🚬", 0) >= 1: unlock("legend_owner")
    if user_data["monkeys"].get("true bibizan 👑🐒", 0) >= 1: unlock("true_owner")
    
    if len(user_data["bosses_defeated"]) >= 4: unlock("all_bosses")
    if len(unlocked) == len(ACHIEVEMENTS) - 1 and "completionist" not in unlocked: unlock("completionist")

    for ach in new_unlocks:
        await context.bot.send_message(chat_id=chat_id, text=f"🎖 **НОВОЕ ДОСТИЖЕНИЕ:** {ach['name']}!\n{ach['desc']}\n💰 Награда: +{ach['reward']} 🍌", parse_mode="Markdown")
    return user_data

# ================= ФОНОВЫЕ ЗАДАЧИ =================
async def passive_income_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    current_time = time.time()
    user_ids = get_all_player_ids()
    
    global_event = None
    if random.random() < 0.03:
        event_type = random.choice(["rain", "locusts", "sun"])
        global_event = {
            "rain": "🌧 **БАНАНОВЫЙ ДОЖДЬ!** С неба падают бананы! Всем игрокам начислено **+50 🍌**!",
            "locusts": "🦗 **НАШЕСТВИЕ САРАНЧИ!** Все потеряли 10% бананов!",
            "sun": "☀️ **АНАМАЛЬНАЯ ЖАРА!** Всем начислено **+25 🍌**!"
        }[event_type]

    for uid in user_ids:
        user_data = load_player(uid)
        if global_event:
            if event_type == "rain": user_data["bananas"] += 50
            elif event_type == "locusts": user_data["bananas"] = max(0, int(user_data["bananas"] * 0.9))
            elif event_type == "sun": user_data["bananas"] += 25
            try: await context.bot.send_message(chat_id=uid, text=global_event, parse_mode="Markdown")
            except: pass

        if (current_time - user_data["last_internet_pay"]) >= 86400:
            try: await context.bot.send_message(chat_id=uid, text="⚠️ **ИНТЕРНЕТ ОТКЛЮЧЕН!**", parse_mode="Markdown")
            except: pass
            save_player(uid, user_data)
            continue

        monkeys = user_data["monkeys"]
        income = sum(monkeys.get(rarity, 0) * data["income"] for rarity, data in RARITIES.items())
        
        if income > 0:
            user_data["bananas"] += income
            try: await context.bot.send_message(chat_id=uid, text=f"🏪 Бибизяны натаскали **+{income} 🍌**!", parse_mode="Markdown")
            except: pass
        
        # ВУЛКАН (Шанс 0.01%)
        if random.random() < 0.0001:
            if user_data["bananas"] > 0 or sum(monkeys.values()) > 0:
                try:
                    with open(VOLCANO_IMAGE, "rb") as photo:
                        await context.bot.send_photo(chat_id=uid, photo=photo, caption="🌋 **ВАХУН! ИЗВЕРЖЕНИЕ!**\nСмыло ВСЕ бананы и половину стаи!", parse_mode="Markdown")
                    user_data["bananas"] = 0
                    for rarity in monkeys: monkeys[rarity] = monkeys[rarity] // 2
                except: pass
                
        # СТАРЫЙ БОГ (Шанс 0.005%)
        elif random.random() < 0.00005:
            user_data["bananas"] += 50
            try:
                with open(OLD_GOD_IMAGE, "rb") as photo:
                    await context.bot.send_photo(chat_id=uid, photo=photo, caption="🤣 **Старый бог упал с балкона!** Ты подобрал **+50 🍌**!", parse_mode="Markdown")
            except FileNotFoundError:
                await context.bot.send_message(chat_id=uid, text="🤣 **Старый бог упал с балкона!** Ты подобрал **+50 🍌**!")
                
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
        income = sum(user_data["monkeys"].get(r, 0) * d["income"] for r, d in RARITIES.items())
        earned = int(income * (time_offline / 60))
        if earned > 0:
            user_data["bananas"] += earned
            offline_msg = f"\n\n💤 **Пока тебя не было, бибизяны работали!**\nТы заработал: **+{earned} 🍌**"
    
    user_data["last_seen"] = now
    save_player(update.effective_user.id, user_data)

    await update.message.reply_text(
        f"🍌 Уа-уа, **{user_name}**! Жми кнопки, чтобы лутать бананы!{offline_msg}\n\n⚠️ *Не забудь оплатить интернет!*",
        reply_markup=build_game_keyboard(), parse_mode="Markdown"
    )

async def handler_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text: return
    user_id = update.effective_user.id
    ud = load_player(user_id, update.effective_user.first_name or "Бибизяна")
    ud["last_seen"] = time.time()
    text = update.message.text
    
    if text == "Бежать до сваих":
        is_win = random.choice([True, False])
        if is_win:
            ud["bananas"] += 1
            try:
                with open(WIN_IMAGE_PATH, "rb") as photo_file:
                    await update.message.reply_photo(photo=photo_file, caption=f"ты дабежал да сваих\nБананов: {ud['bananas']}")
            except FileNotFoundError: pass
        else:
            try:
                with open(LOSE_GIF_PATH, "rb") as gif_file:
                    await update.message.reply_animation(animation=gif_file, caption=f"ты пагиб🥀\nБананов: {ud['bananas']}")
            except FileNotFoundError: pass
        ud = await check_achievements(context, update.effective_chat.id, ud)

    elif text == "🚀 МЕГА КАРЫТО (1500 🍌)":
        if ud["bananas"] < 1500:
            await update.message.reply_text(f"❌ Нужно 1500 🍌 для Мега карыта! У тебя {ud['bananas']}.")
            return

        ud["bananas"] -= 1500
        ud["boxes_opened"] += 1
        
        mega_rarities = ["Абсолют 🗿", "sub-3 🥉", "sub-5 🥈", "ltb 🧢", "mtb 👽", "htb 🗿", "chad 🗿🍷", "true bibizan 👑🐒"]
        mega_weights = [50, 25, 15, 7, 2.5, 0.4, 0.09, 0.001] 
        
        dropped_rarity = random.choices(mega_rarities, weights=mega_weights, k=1)[0]
        ud["monkeys"][dropped_rarity] += 1
        
        if "mega_owner" not in ud["achievements"]:
            ud["achievements"].append("mega_owner")
            ud["bananas"] += ACHIEVEMENTS["mega_owner"]["reward"]
            await update.message.reply_text(f"🎖 **ДОСТИЖЕНИЕ:** Мега-Лудоман (+1000 🍌)!", parse_mode="Markdown")

        photo_path = os.path.join(BASE_DIR, random.choice(RARITIES[dropped_rarity]["images"]))
        try:
            with open(photo_path, "rb") as f:
                await update.message.reply_photo(photo=f, caption=f"🚀 Из **МЕГА КАРЫТА** выпрыгнул: **{dropped_rarity}**!\nБананов осталось: {ud['bananas']}", parse_mode="Markdown")
        except FileNotFoundError: 
            await update.message.reply_text(f"🚀 Из **МЕГА КАРЫТА** выпрыгнул: **{dropped_rarity}**!\nБананов: {ud['bananas']}", parse_mode="Markdown")
        
        ud = await check_achievements(context, update.effective_chat.id, ud)

    elif text == "🌟 Золотое карыто (50 🍌)":
        if ud["bananas"] < 50:
            await update.message.reply_text(f"❌ Нужно 50 🍌!")
            return
        ud["bananas"] -= 50
        ud["boxes_opened"] += 1
        
        rarities_list = ["Эпик 👑", "Легенда 🚬", "Миф 🛸", "Батя Джунглей 🌋", "Бог 🪐", "Абсолют 🗿"]
        weights_list = [40, 30, 18, 8, 3, 1]
        dropped_rarity = random.choices(rarities_list, weights=weights_list, k=1)[0]
        ud["monkeys"][dropped_rarity] += 1
        
        photo_path = os.path.join(BASE_DIR, random.choice(RARITIES[dropped_rarity]["images"]))
        try:
            with open(photo_path, "rb") as f:
                await update.message.reply_photo(photo=f, caption=f"🌟 Из **ЗОЛОТОГО КАРЫТА** выпрыгнула: **{dropped_rarity}**!\nБананов осталось: {ud['bananas']}", parse_mode="Markdown")
        except FileNotFoundError: 
            await update.message.reply_text(f"🌟 Из **ЗОЛОТОГО КАРЫТА** выпрыгнула: **{dropped_rarity}**!", parse_mode="Markdown")
        ud = await check_achievements(context, update.effective_chat.id, ud)

    elif text == "Вскрыть карыто (5 🍌)":
        if ud["bananas"] < 5:
            await update.message.reply_text(f"❌ Надо 5 🍌.")
            return
        ud["bananas"] -= 5
        ud["boxes_opened"] += 1
        
        rarities_list = [r for r in RARITIES.keys() if RARITIES[r]["weight"] > 0]
        weights_list = [RARITIES[r]["weight"] for r in rarities_list]
        
        dropped_rarity = random.choices(rarities_list, weights=weights_list, k=1)[0]
        ud["monkeys"][dropped_rarity] += 1
        
        photo_path = os.path.join(BASE_DIR, random.choice(RARITIES[dropped_rarity]["images"]))
        try:
            with open(photo_path, "rb") as f:
                await update.message.reply_photo(photo=f, caption=f"📦 Из карыта выпрыгнула: **{dropped_rarity}**!\nБананов: {ud['bananas']}", parse_mode="Markdown")
        except FileNotFoundError: await update.message.reply_text(f"📦 Выпала **{dropped_rarity}**!", parse_mode="Markdown")
        ud = await check_achievements(context, update.effective_chat.id, ud)

    elif text == "Махаться с чужими":
        if ud["bananas"] < 5:
            await update.message.reply_text("❌ Для махача надо 5 🍌!")
            return

        monkeys = ud["monkeys"]
        team = [r for r, c in monkeys.items() if c > 0]
        team_str = ", ".join(team) if team else "В адиночку 👤"

        enemy_team_list, enemy_total_count, enemy_power = [], 0, 0
        rarities_list = list(RARITIES.keys())
        weights_list = [45, 30, 15, 7, 2.9, 0.1, 0.05, 0.01, 0.001, 0.0001, 0.00001, 0.000001, 0.0000001, 0.00000001, 0.000000001]
        
        for _ in range(random.randint(1, 4)):
            e_rarity = random.choices(rarities_list, weights=weights_list, k=1)[0]
            enemy_team_list.append(e_rarity)
            enemy_total_count += 1
            enemy_power += RARITIES[e_rarity]["income"]
            
        player_power = sum(monkeys.get(r, 0) * d["income"] for r, d in RARITIES.items())
        final_lose_chance = max(10, min(90, 50 + (enemy_power * 0.01) - (player_power * 0.01))) 
        attack_type = random.choice(ATTACK_TYPES)

        battle_text = f"⚔️ **{attack_type}!**\n\n👥 **Твоя стая:** {team_str}\n💀 **Вражья стая:** {', '.join(enemy_team_list)}\n\n📉 Шанс праиграть: {final_lose_chance}%"

        try:
            with open(random.choice(WAR_IMAGES), "rb") as photo:
                await update.message.reply_photo(photo=photo, caption=battle_text, parse_mode="Markdown")
        except: await update.message.reply_text(battle_text, parse_mode="Markdown")

        if random.randint(1, 100) > final_lose_chance:
            ud["bananas"] += 5
            ud["defeated"] += enemy_total_count
            await update.message.reply_text(f"🎉 **ПАБЕДА!**\n💰 **+5 🍌**\n🍌 Бананов: {ud['bananas']}", parse_mode="Markdown")
        else:
            ud["bananas"] -= 5
            loss_msg = f"😢 **АБЛАЖАЛСЯ.**\nТы потерял 5 🍌.\n"
            if team and random.randint(1, 100) <= 35:
                dead_monkey = random.choice(team)
                ud["monkeys"][dead_monkey] -= 1
                loss_msg += f"\n🥀 Пагибла **{dead_monkey}**..."
            loss_msg += f"\n🍌 Бананов: {ud['bananas']}"
            await update.message.reply_text(loss_msg, parse_mode="Markdown")
        ud = await check_achievements(context, update.effective_chat.id, ud)

    elif text == "🧬 Склещить бибизян":
        monkeys = ud["monkeys"]
        msg = "🧬 **ЛАБАРАТОРИЯ СНОШАНИЯ**\n\n"
        merged = False
        tiers = list(RARITIES.keys())
        for i in range(len(tiers) - 1):
            curr, nxt = tiers[i], tiers[i+1]
            if monkeys[curr] >= 3:
                merge_count = monkeys[curr] // 3
                monkeys[curr] -= merge_count * 3
                monkeys[nxt] += merge_count
                msg += f"✅ {merge_count * 3} шт. {curr} нарожали {merge_count} шт. {nxt}!\n"
                merged = True
        if merged: 
            ud["merges"] += 1
            await update.message.reply_text(msg, parse_mode="Markdown")
            ud = await check_achievements(context, update.effective_chat.id, ud)
        else: await update.message.reply_text("❌ Мало бибизян. Надо по 3 штуки.", parse_mode="Markdown")

    elif text == "📖 Кодекс":
        msg = "📖 **КОДЕКС БИБИЗЯН:**\n\n"
        for rarity, desc in BESTIARY.items():
            count = ud["monkeys"].get(rarity, 0)
            msg += f"**{rarity}** (У тебя: {count})\n_{desc}_\n\n"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "📜 Квесты":
        quests = ud["daily_quests"]
        today = datetime.date.today().isoformat()
        if quests.get("date") != today:
            ud["daily_quests"] = {"date": today, "tasks": list(DAILY_TASKS.keys()), "progress": {t: 0 for t in DAILY_TASKS.keys()}, "rewarded": False}
            quests = ud["daily_quests"]
            
        msg = "📜 **ЕЖЕДНЕВНЫЕ КВЕСТЫ:**\n\n"
        all_done = True
        for task_id in quests["tasks"]:
            task_info = DAILY_TASKS[task_id]
            prog = quests["progress"].get(task_id, 0)
            target = task_info["target"]
            
            if prog >= target: msg += f"✅ {task_info['text']} (Выполнено!)\n"
            else:
                msg += f"🔹 {task_info['text']} (Прогресс: {prog}/{target})\n"
                all_done = False
                
        if all_done and not quests["rewarded"]:
            ud["bananas"] += 500
            quests["rewarded"] = True
            msg += "\n🎁 **ВСЕ КВЕСТЫ ВЫПОЛНЕНЫ!**\nТы получил сундук с **+500 🍌**!"
        elif quests["rewarded"]: msg += "\n🎁 Ты уже забрал награду за сегодня. Приходи завтра!"
        else: msg += "\n(Выполни все 3 задания, чтобы получить **+500 🍌**)"
            
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "🏆 Вожаки стаи":
        all_ids = get_all_player_ids()
        players = [load_player(uid) for uid in all_ids]
        sorted_players = sorted(players, key=lambda x: x.get("bananas", 0), reverse=True)[:5]
        
        msg = "🏆 **САМЫЕ БОГАТЫЕ ВОЖАКИ:**\n\n"
        for i, p in enumerate(sorted_players, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔹"
            msg += f"{medal} {p.get('name', 'Бибизяна')} — {p.get('bananas', 0)} 🍌 (Загрыз: {p.get('defeated', 0)} 💀)\n"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "🎖 Ачивки":
        msg = "🎖 **ТВОИ ДОСТИЖЕНИЯ:**\n\n"
        unlocked = ud["achievements"]
        for key, ach in ACHIEVEMENTS.items():
            if key in unlocked: msg += f"✅ {ach['name']} — {ach['desc']}\n"
            else: msg += f"🔒 {ach['name']} — {ach['desc']} (Награда: {ach['reward']} 🍌)\n"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "Чо в кармане?":
        monkeys = ud["monkeys"]
        current_speed = sum(monkeys.get(r, 0) * d["income"] for r, d in RARITIES.items())
        is_internet_active = (time.time() - ud.get("last_internet_pay", 0)) < 86400
        
        info_msg = (
            f"💼 **ЧО В КАРМАНЕ:**\n"
            f"🌐 Интернет: {'✅ Вкл' if is_internet_active else '❌ Выкл'}\n"
            f"🍌 Бананы: {ud['bananas']} ( Доход: +{current_speed} 🍌/мин )\n\n"
            f"🏆 **Твоя стая:**\n"
        )
        for rarity in RARITIES.keys(): 
            if monkeys.get(rarity, 0) > 0:
                info_msg += f"◽ {rarity}: {monkeys.get(rarity, 0)}\n"
        await update.message.reply_text(info_msg, parse_mode="Markdown")

    elif text == "🌐 Оплатить связь (50 🍌)":
        current_time = time.time()
        if current_time - ud["last_internet_pay"] < 86400:
            await update.message.reply_text(f"✅ Связь уже оплачена! Осталось: {int((86400 - (current_time - ud['last_internet_pay'])) // 3600)} ч.")
            return
            
        if ud["bananas"] < 50:
            await update.message.reply_text(f"❌ Надо 50 🍌.")
            return
            
        ud["bananas"] -= 50
        ud["last_internet_pay"] = current_time
        ud["internet_payments"] += 1
        await update.message.reply_text(f"🌐 **ИНТЕРНЕТ ПОДКЛЮЧЕН!**\nОстаток: {ud['bananas']} 🍌", parse_mode="Markdown")
        ud = await check_achievements(context, update.effective_chat.id, ud)

    elif text == "🎰 Слот-машина":
        if ud["bananas"] < 10:
            await update.message.reply_text("❌ Нужно 10 🍌!")
            return
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Ставка 10% 🍌", callback_data="bet_10p"), InlineKeyboardButton("Ставка 25% 🍌", callback_data="bet_25p")],
            [InlineKeyboardButton("Ставка 50% 🍌", callback_data="bet_50p"), InlineKeyboardButton("🔥 ВСЁ ИЛИ НИЧЕГО", callback_data="bet_100p")]
        ])
        await update.message.reply_text("🎰 **Выбери свою ставку:**", reply_markup=keyboard, parse_mode="Markdown")
        save_player(user_id, ud)
        return

    elif text == "🥷 Ограбить":
        all_ids = get_all_player_ids()
        others = [uid for uid in all_ids if uid != user_id]
        if not others:
            await update.message.reply_text("В джунглях пока никого нет.")
            return
        victim_id = random.choice(others)
        victim_data = load_player(victim_id)
        if victim_data["bananas"] < 10:
            await update.message.reply_text(f"У **{victim_data['name']}** меньше 10 бананов. Грабить нищего — грех.")
            return
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Напасть!", callback_data=f"rob_{victim_id}")], [InlineKeyboardButton("Свалить", callback_data="rob_cancel")]])
        await update.message.reply_text(f"🥷 Ты выследил **{victim_data['name']}**!\nУ него **{victim_data['bananas']} 🍌**. Нападаем?", reply_markup=keyboard)
        save_player(user_id, ud)
        return

    elif text == "👹 Логово Босса":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍌 Владыка (500 HP)", callback_data="boss_overlord"), InlineKeyboardButton("🦍 Горилла (2К HP)", callback_data="boss_gorilla")],
            [InlineKeyboardButton("👹 Старый Бог (5К HP)", callback_data="boss_god"), InlineKeyboardButton("🤖 Кибер (10К HP)", callback_data="boss_robot")],
            [InlineKeyboardButton("🗿🍷 Гигачад (50К HP)", callback_data="boss_chad")],
            [InlineKeyboardButton("👑🐒 True Bibizan (1М HP)", callback_data="boss_true_bibizan")]
        ])
        await update.message.reply_text("👹 **Выбери босса:**", reply_markup=keyboard, parse_mode="Markdown")
        save_player(user_id, ud)
        return

    elif text == "📰 Бибизяни новости":
        if random.random() < 0.30:
            interactives = [
                {"text": "🥸 **ТАИНСТВЕННЫЙ НЕЗНАКОМЕЦ!**\nК тебе подошел странный тип и просит 20 бананов.", "buttons": [[InlineKeyboardButton("Дать 20 🍌", callback_data="news_stranger_give"), InlineKeyboardButton("Послать", callback_data="news_stranger_no")]]},
                {"text": "🤯 **ШАХТА!**\nВ джунглях нашли заброшенную шахту с золотыми бананами!", "buttons": [[InlineKeyboardButton("Спуститься", callback_data="news_mine_yes")], [InlineKeyboardButton("Пройти мимо", callback_data="news_mine_no")]]}
            ]
            event = random.choice(interactives)
            try:
                with open(random.choice(MONKEY_NEWS_IMAGES), "rb") as photo:
                    await update.message.reply_photo(photo=photo, caption=f"📰 **ЭКСТРЕННЫЕ НОВОСТИ** ⚡️\n\n{event['text']}", reply_markup=InlineKeyboardMarkup(event['buttons']), parse_mode="Markdown")
            except: pass
            save_player(user_id, ud)
            return
        news_text = random.choice(NEWS_LIST)
        try:
            with open(random.choice(MONKEY_NEWS_IMAGES), "rb") as photo:
                await update.message.reply_photo(photo=photo, caption=f"📰 **НОВОСТИ** ⚡️\n\n{news_text}", parse_mode="Markdown")
        except FileNotFoundError: await update.message.reply_text(f"📰 **НОВОСТИ:** {news_text}", parse_mode="Markdown")

    else:
        await update.message.reply_text("Тыкай кнопки внизу, уа-уа 👇")
        
    save_player(user_id, ud)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    ud = load_player(user_id)
    
    if query.data.startswith("boss_"):
        boss_id = query.data.split("_", 1)[1]
        if boss_id in BOSSES:
            boss = BOSSES[boss_id]
            ud["boss_id"] = boss_id
            ud["boss_hp"] = boss["hp"]
            await query.edit_message_text(f"{boss['name']} пробудился!\nУ него **{boss['hp']} HP**.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Атаковать", callback_data="boss_attack")]]), parse_mode="Markdown")
    
    elif query.data == "boss_attack":
        boss_id = ud.get("boss_id")
        if not boss_id or boss_id not in BOSSES: return
        boss = BOSSES[boss_id]
        if ud.get("boss_hp", 0) <= 0:
            await query.edit_message_text("👹 Босс уже мертв.")
            return
        if ud["bananas"] < 10:
            await query.answer("❌ Надо 10 бананов!", show_alert=True)
            return

        ud["bananas"] -= 10
        monkeys = ud["monkeys"]
        player_power = sum(monkeys.get(r, 0) * d["income"] for r, d in RARITIES.items())
        damage = max(10, player_power * random.randint(1, 3))
        ud["boss_hp"] -= damage
        
        if ud["boss_hp"] <= 0:
            ud["boss_hp"] = 0
            ud["bananas"] += boss["reward"]
            if boss_id not in ud["bosses_defeated"]: ud["bosses_defeated"].append(boss_id)
            
            await query.edit_message_text(f"💀 **ПОБЕДА!**\nТы убил {boss['name']}!\n💰 Награда: **+{boss['reward']} 🍌**!\nТвой баланс: {ud['bananas']}", parse_mode="Markdown")
            ud["boss_id"] = None
            ud = await check_achievements(context, update.effective_chat.id, ud)
        else:
            counter_damage = random.randint(boss["damage"][0], boss["damage"][1])
            ud["bananas"] = max(0, ud["bananas"] - counter_damage)
            hp_bar = "█" * int((ud['boss_hp'] / boss['hp']) * 10) + "░" * (10 - int((ud['boss_hp'] / boss['hp']) * 10))
            await query.edit_message_text(f"{boss['name']} **БИТВА**\n\n❤️ HP: {hp_bar} ({ud['boss_hp']} / {boss['hp']})\n\n⚔️ Урон: **{damage}**.\n🩸 Босс отнял **{counter_damage} 🍌**.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Атаковать", callback_data="boss_attack")]]), parse_mode="Markdown")

    elif query.data.startswith("bet_"):
        bet_pct = int(query.data.split("_")[1].replace("p", ""))
        bet_amount = int(ud["bananas"] * (bet_pct / 100))
        if bet_amount < 1:
            await query.answer("Мало бананов!", show_alert=True)
            return
        if bet_pct == 100: bet_amount = ud["bananas"] 
            
        ud["bananas"] -= bet_amount
        await query.edit_message_text(f"🎰 Ставка: **{bet_amount} 🍌**. Крутим...\n[ 🍒 | 🍌 | 🍋 ]", parse_mode="Markdown")
        await asyncio.sleep(1.0)
        await query.edit_message_text(f"🎰 Ставка: **{bet_amount} 🍌**. Крутим...\n[ 🍌 | 🍋 | 🍒 ]", parse_mode="Markdown")
        await asyncio.sleep(1.0)
        
        roll = random.random()
        if roll < 0.45:
            win = bet_amount * 2
            ud["bananas"] += win
            await query.edit_message_text(f"🎰 **ВЫИГРЫШ!** x2: **+{win} 🍌**!\nБаланс: {ud['bananas']} 🍌\n[ 🍌 | 🍌 | 🍋 ]", parse_mode="Markdown")
        elif roll < 0.90:
            await query.edit_message_text(f"🎰 **ПРОИГРЫШ.** Ты потерял {bet_amount} 🍌.\nБаланс: {ud['bananas']} 🍌\n[ 🍒 | 🍋 | 🍒 ]", parse_mode="Markdown")
        else:
            win = bet_amount * 5
            ud["bananas"] += win
            await query.edit_message_text(f"💎 **ДЖЕКПОТ!!!** x5: **+{win} 🍌**!\nБаланс: {ud['bananas']} 🍌\n[ 🍌 | 🍌 | 🍌 ]", parse_mode="Markdown")
    
    elif query.data == "news_stranger_give":
        if ud["bananas"] >= 20:
            ud["bananas"] -= 20
            if random.random() < 0.3:
                ud["bananas"] += 200
                await query.edit_message_caption(caption="🥸 **НЕЗНАКОМЕЦ ОКАЗАЛСЯ МЕЦЕНАТОМ!**\nОн вернул тебе долг с процентами: **+200 🍌**!\nТвой баланс: " + str(ud["bananas"]), parse_mode="Markdown")
            else:
                await query.edit_message_caption(caption=f"🥸 **ТЕБЯ КИНУЛИ!**\nНезнакомец скрылся в кустах с твоими 20 бананами.\nТвой баланс: {ud['bananas']}", parse_mode="Markdown")
        else:
            await query.edit_message_caption(caption="❌ У тебя нет 20 бананов!", parse_mode="Markdown")
            
    elif query.data == "news_stranger_no":
        await query.edit_message_caption(caption="🥸 Ты прогнал незнакомца.", parse_mode="Markdown")

    elif query.data == "news_mine_yes":
        if random.choice([True, False]):
            ud["bananas"] += 100
            await query.edit_message_caption(caption=f"💎 **УДАЧА!**\nТы нашел **+100 🍌**!\nБананов: {ud['bananas']}", parse_mode="Markdown")
        else:
            ud["bananas"] = max(0, ud["bananas"] - 20)
            await query.edit_message_caption(caption=f"💀 **ОБВАЛ!**\nТы потерял **20 🍌**.\nБананов: {ud['bananas']}", parse_mode="Markdown")
            
    elif query.data == "news_mine_no":
        await query.edit_message_caption(caption=f"🚶‍♂️ Ты прошел мимо. Целее будешь.", parse_mode="Markdown")

    elif query.data.startswith("rob_"):
        if query.data == "rob_cancel":
            await query.edit_message_text("🥷 Ты решил не рисковать и свалил в кусты.")
            return
        victim_id = int(query.data.split("_")[1])
        victim_data = load_player(victim_id)
        if random.choice([True, False]):
            stolen = int(victim_data["bananas"] * 0.15)
            ud["bananas"] += stolen
            victim_data["bananas"] -= stolen 
            ud["robberies"] += 1
            await query.edit_message_text(f"🥷 **УСПЕХ!**\nТы обчистил **{victim_data['name']}** и украл **{stolen} 🍌**!\nТвой баланс: {ud['bananas']}", parse_mode="Markdown")
            save_player(victim_id, victim_data)
            ud = await check_achievements(context, update.effective_chat.id, ud)
        else:
            lost = int(ud["bananas"] * 0.10)
            ud["bananas"] = max(0, ud["bananas"] - lost)
            victim_data["bananas"] += lost 
            await query.edit_message_text(f"🚨 **ПРОВАЛ!**\n**{victim_data['name']}** поймал тебя и отобрал **{lost} 🍌**!\nТвой баланс: {ud['bananas']}", parse_mode="Markdown")
            save_player(victim_id, victim_data)

    save_player(user_id, ud)

if __name__ == "__main__":
    print("Инициализация базы данных...")
    init_db()
    
    print("Запускаю банановую бибизяну...")
    req = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, write_timeout=30.0, pool_timeout=30.0)
    app = ApplicationBuilder().token(TOKEN).request(req).get_updates_request(req).build()
    
    job_queue = app.job_queue
    job_queue.run_repeating(passive_income_callback, interval=60, first=10)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler_text))
    app.add_handler(CallbackQueryHandler(callback_handler)) 
    
    print("✅ Бибизяна успешно вырвалась на волю!")
    app.run_polling()