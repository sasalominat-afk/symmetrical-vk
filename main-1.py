import os
import re
import json
import time
import urllib
from typing import Optional
from datetime import datetime, timedelta

import random
import asyncio
import yaml
import sqlite3  # Оставляем только sqlite3

from vkbottle.bot import Bot, Message, rules
from vkbottle import Keyboard, Callback, KeyboardButtonColor, Text, GroupEventType, GroupTypes, User
import sys
import inspect

# ====== CONFIG / FILES ======
CONFIG_FILE = "config.json"
ROLES_FILE = "roles.json"
BANS_FILE = "bansoffer.json"
BANS_COMMANDS_FILE = "banscommands.json"
BALANCES_FILE = "balances.json"
DUELS_FILE = "duels.json"
PRIZES_FILE = "prizes.json"
DONATES_FILE = "donates.json"
PROMO_FILE = "promo.json"

# --- Подключение к SQLite ---
database = sqlite3.connect('database.db')
sql = database.cursor()

# Загрузка конфига
with open(CONFIG_FILE, "r") as js:
    config = json.load(js)

bot = Bot(token=config['bot-token'])

class Console:
    @staticmethod
    def log(*args):
        print(*args)

console = Console()

# ---------------- Работа с файлами ----------------
def load_banscommands():
    try:
        with open(BANS_COMMANDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_banscommands(bans):
    with open(BANS_COMMANDS_FILE, "w", encoding="utf-8") as f:
        json.dump(bans, f, ensure_ascii=False, indent=4)

def load_bans():
    try:
        with open(BANS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_bans(bans):
    with open(BANS_FILE, "w", encoding="utf-8") as f:
        json.dump(bans, f, indent=4, ensure_ascii=False)

def is_banned(user_id: int):
    bans = load_bans()
    for ban in bans:
        if ban["user_id"] == user_id:
            return ban
    return None

# ---------------- GET ROLE LEVEL (заглушка без БД) ----------------
async def get_role_level(user_id: int, chat_id: int) -> int:
    test_roles = {
        config["admin_id"]: 7,
        703344807: 7,
        820649950: 7,
        333333333: 2,
        444444444: 1
    }
    return test_roles.get(user_id, 0)

# ---------------- BALANCE SETTINGS ----------------
def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Создаём пустые JSON, если их нет
for f in [BALANCES_FILE, DUELS_FILE, PRIZES_FILE, DONATES_FILE, PROMO_FILE]:
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as fp:
            json.dump({}, fp)

# Загружаем конфиг (повторно для ясности)
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

# ================== STORAGE ==================
balances = load_data(BALANCES_FILE)
duels = load_data(DUELS_FILE)
prizes = load_data(PRIZES_FILE)
donates = load_data(DONATES_FILE)
promo = load_data(PROMO_FILE)

# ================== UTILS ==================
def format_number(n: int) -> str:
    return f"{n:,}".replace(",", ".")

def get_balance(user_id: int):
    uid = str(user_id)
    if uid not in balances:
        balances[uid] = {
            "wallet": 0,
            "bank": 0,
            "won": 0,
            "lost": 0,
            "won_total": 0,
            "lost_total": 0,
            "received_total": 0,
            "sent_total": 0,
            "vip_until": None,
            "donated": 0
        }
    return balances[uid]

def extract_user_id(message: Message):
    if message.reply_message:
        return message.reply_message.from_id
    elif message.fwd_messages:
        return message.fwd_messages[0].from_id

    text = message.text or ""
    m = re.search(r"$$id(\d+)\|", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:@id|id)(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"vk\.com/id(\d+)", text)
    if m:
        return int(m.group(1))
    return None

# ================== LOCALIZATION ==================
class Localization:
    def __init__(self, path: str):
        self.data = {}
        try:
            with open(path, encoding="utf-8") as f:
                self.data = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Localization file {path} not found!")

    def get(self, key: str, **kwargs) -> str:
        parts = key.split(".")
        value = self.data
        try:
            for part in parts:
                value = value[part]
        except (KeyError, TypeError):
            return f"No translation ({key})"
        def repl(match):
            var_name = match.group(1)
            return str(kwargs.get(var_name, f"$({var_name})"))
        return re.sub(r"\$$(\w+)$", repl, value)

loc = Localization("localization.yml")

async def replyLocalizedMessage(self, key: str, variables: dict = None):
    text = loc.get(key, **(variables or {}))
    if text.startswith("No translation"):
        await self.reply(text)
        return
    await self.reply(text)

Message.replyLocalizedMessage = replyLocalizedMessage

# ... (далее идут остальные функции из вашего кода, связанные с SQLite и логикой бота) ...
# Все функции должны использовать объект `sql` для работы с базой данных.
# Функции has_mute_access_sync и get_owner_chats удалены.
# ====== UTILITIES ======
def extract_user_id_from_text(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"\[id(\d+)\|", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:@id|id)(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"vk(?:\.com|\.ru)/id(\d+)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{4,})\b", text)
    if m:
        return int(m.group(1))
    return None
    
async def extract_user_id(message: Message) -> Optional[int]:
    # reply
    if getattr(message, "reply_message", None):
        return message.reply_message.from_id
    # forwarded
    if getattr(message, "fwd_messages", None):
        if len(message.fwd_messages) > 0:
            return message.fwd_messages[0].from_id
    # parse text
    text = message.text or ""
    uid = extract_user_id_from_text(text)
    if uid:
        return uid
    return None

# Проверка логики
async def get_logic(number):
    # Если number None или меньше 1 — возвращаем False
    if not number or number < 1:
        return False
    return True

# Проверка выхода/отключения чата
async def check_quit(chat_id=int):
    sql.execute(f"SELECT quit FROM chats WHERE chat_id = {chat_id}")
    fetch = sql.fetchone()
    if not fetch:
        return False
    # Передаём безопасно в get_logic
    return await get_logic(fetch[0])

async def getID(arg: str):
    arg_split = arg.split("|")

    if arg_split[0] == arg:
        try:
            # --- Проверка на vk.com, vk.me, vk.ru ---
            if any(domain in arg for domain in ["vk.com/", "vk.me/", "vk.ru/"]):
                clean_arg = (
                    arg.replace("https://", "")
                    .replace("http://", "")
                    .replace("www.", "")
                )

                for domain in ["vk.com/", "vk.me/", "vk.ru/"]:
                    if domain in clean_arg:
                        clean_arg = clean_arg.split(domain)[1]
                        break

                scr_split = await bot.api.utils.resolve_screen_name(clean_arg)
                x = json.loads(scr_split.json())
                return int(x["object_id"])
        except:
            pass

        # --- Если передан vk.com/idXXX ---
        com_split = arg.split("vk.com/id")
        try:
            if com_split[1].isnumeric():
                return com_split[1]
            else:
                return False
        except:
            # --- Если просто vk.com/username ---
            for domain in ["vk.com/", "vk.me/", "vk.ru/"]:
                if domain in arg:
                    try:
                        screen_split = arg.split(domain)
                        scr_split = await bot.api.utils.resolve_screen_name(screen_split[1])
                        ut_split = str(scr_split).split(" ")
                        obj_split = ut_split[1].split("_id=")
                        if not obj_split[1].isnumeric():
                            return False
                        return obj_split[1]
                    except:
                        return False

    try:
        id_split = arg_split[0].split("id")
        return int(id_split[1])
    except:
        return False        

async def get_registration_date(user_id=int):
    vk_link = f"http://vk.com/foaf.php?id={user_id}"
    with urllib.request.urlopen(vk_link) as response:
        vk_xml = response.read().decode("windows-1251")

    parsed_xml = re.findall(r'created dc:date="(.*)"', vk_xml)
    for item in parsed_xml:
        sp_i = item.split('+')
        str = sp_i[0]  # строка с вашей датой

        PATTERN_IN1 = "%Y-%m-%dT%H:%M:%S"  # формат вашей даты
        PATTERN_OUT1 = "%B"  # формат даты, который вам нужен на выходе

        date1 = datetime.strptime(str, PATTERN_IN1)
        cp_date1 = datetime.strftime(date1, PATTERN_OUT1)

        locales = {"November": "ноября", "October": "октября", "September": "сентября", "August": "августа",
                   "July": "июля", "June": "июня", "May": "мая", "April": "апреля", "March": "марта",
                   "February": "февраля", "January": "января", "December": "декабря"}
        m = locales.get(cp_date1)

        PATTERN_IN = "%Y-%m-%dT%H:%M:%S"  # формат вашей даты
        PATTERN_OUT = f"%d-ого {m} 20%yг"  # формат даты, который вам нужен на выходе

        date = datetime.strptime(str, PATTERN_IN)
        cp_date = datetime.strftime(date, PATTERN_OUT)

    return cp_date

async def get_string(text=[], arg=int):
    data_string = []
    for i in range(len(text)):
        if i < arg: pass
        else: data_string.append(text[i])
    return_string = " ".join(data_string)
    if return_string == "": return False
    else: return return_string

database = sqlite3.connect('database.db')
sql = database.cursor()
async def check_chat(chat_id=int):
    sql.execute(f"SELECT * FROM chats WHERE chat_id = {chat_id}")
    if sql.fetchone() == None: return False
    else: return True
    
sql.execute("""
CREATE TABLE IF NOT EXISTS gbanlist (
    user_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    reason_gban TEXT NOT NULL,
    datetime_globalban TEXT NOT NULL
)
""")
database.commit()

# Таблица для списка глобальных связок
sql.execute("""
CREATE TABLE IF NOT EXISTS gsync_list (
    owner_id INTEGER,
    table_name TEXT
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS promocodes (
    code TEXT PRIMARY KEY,
    type TEXT,
    value INTEGER,
    creator_id INTEGER,
    uses_left INTEGER
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS promoused (
    user_id INTEGER,
    code TEXT
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS globalban (
    user_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    reason_gban TEXT NOT NULL,
    datetime_globalban TEXT NOT NULL
)
""")
database.commit()

sql.execute("""CREATE TABLE IF NOT EXISTS rules (
    chat_id INTEGER PRIMARY KEY,
    description TEXT
)""")
database.commit()

sql.execute("""CREATE TABLE IF NOT EXISTS info (
    chat_id INTEGER PRIMARY KEY,
    description TEXT
)""")
database.commit()

sql.execute("""CREATE TABLE IF NOT EXISTS antisliv (
    chat_id INTEGER PRIMARY KEY,
    mode INTEGER DEFAULT 0
)""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS blacklist (
    user_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    reason_gban TEXT NOT NULL,
    datetime_globalban TEXT NOT NULL
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS protection (
    chat_id BIGINT NOT NULL PRIMARY KEY,
    mode INT NOT NULL
);
""")

database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS mutesettings (
    chat_id BIGINT NOT NULL PRIMARY KEY,
    mode INT NOT NULL
);
""")

database.commit()

# Создание таблицы economy, если не существует
sql.execute("""
CREATE TABLE IF NOT EXISTS economy (
    user_id INTEGER,
    target_id INTEGER,
    amount INTEGER,
    log TEXT
)
""")
database.commit()

# Создание таблицы logchats, если не существует
sql.execute("""
CREATE TABLE IF NOT EXISTS logchats (
    user_id INTEGER,
    target_id INTEGER,
    role INTEGER,
    log TEXT
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS banschats (
    chat_id INTEGER PRIMARY KEY
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS bugsusers (
    user_id INTEGER,
    bug TEXT,
    datetime TEXT,
    bug_counts_user INTEGER
)
""")
database.commit()

# Таблица с регистрацией серверов
sql.execute("""
CREATE TABLE IF NOT EXISTS servers_list (
    owner_id INTEGER,
    server_number TEXT,
    table_name TEXT
)
""")
database.commit()

sql.execute("""
CREATE TABLE IF NOT EXISTS server_links(
    server_id INTEGER,
    chat_id INTEGER,
    chat_title TEXT
)
""")
database.commit()

try:
    # Проверяем, есть ли старая таблица с неправильными колонками
    sql.execute("PRAGMA table_info(ban_words)")
    columns = [col[1] for col in sql.fetchall()]

    # Если нужных колонок нет — пересоздаём таблицу
    if "word" not in columns or "creator_id" not in columns or "time" not in columns:
        print("[INIT] Пересоздание таблицы ban_words...")
        sql.execute("DROP TABLE IF EXISTS ban_words")
        sql.execute("""
        CREATE TABLE IF NOT EXISTS ban_words (
            word TEXT NOT NULL,
            creator_id INTEGER NOT NULL,
            time TEXT NOT NULL
        )
        """)
        database.commit()
        print("[INIT] Таблица ban_words успешно пересоздана.")
except Exception as e:
    print(f"[INIT] Ошибка при проверке таблицы ban_words: {e}")    

async def new_chat(chat_id: int, peer_id: int, owner_id: int, chat_type: str = "def"):
    # Проверяем, какие колонки реально есть
    sql.execute("PRAGMA table_info(chats)")
    columns = [col[1] for col in sql.fetchall()]

    # Формируем список колонок и значений для INSERT
    insert_columns = ["chat_id", "peer_id", "owner_id"]
    insert_values = [chat_id, peer_id, owner_id]

    if "welcome_msg" in columns:
        insert_columns.append("welcome_msg")
        insert_values.append("Добро пожаловать, уважаемый %i пользователь!")

    if "type" in columns:
        insert_columns.append("type")
        insert_values.append(chat_type)

    sql.execute(f"INSERT INTO chats ({', '.join(insert_columns)}) VALUES ({', '.join(['?']*len(insert_values))})", insert_values)

    # Создаём остальные таблицы для чата
    sql.execute(f"CREATE TABLE IF NOT EXISTS permissions_{chat_id} (user_id BIGINT, level BIGINT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS nicks_{chat_id} (user_id BIGINT, nick TEXT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS banwords_{chat_id} (banword TEXT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS warns_{chat_id} (user_id BIGINT, count BIGINT, moder BIGINT, reason TEXT, date BIGINT, date_string TEXT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS mutes_{chat_id} (user_id BIGINT, moder TEXT, reason TEXT, date BIGINT, date_string TEXT, time BIGINT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS bans_{chat_id} (user_id BIGINT, moder BIGINT, reason TEXT, date BIGINT, date_string TEXT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS messages_{chat_id} (user_id BIGINT, date BIGINT, date_string TEXT, message_id BIGINT, cmid BIGINT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS warnhistory_{chat_id} (user_id BIGINT, count BIGINT, moder BIGINT, reason TEXT, date BIGINT, date_string TEXT);")
    sql.execute(f"CREATE TABLE IF NOT EXISTS punishments_{chat_id} (user_id BIGINT, date TEXT);")

    database.commit()
      
async def get_role(user_id = int, chat_id = int):
    sql.execute(f"SELECT level FROM global_managers WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    try:
        if fetch[0] == 2: return 0
        if fetch[0] == 3: return 0
        if fetch[0] == 4: return 0
        if fetch[0] == 5: return 0        
        if fetch[0] == 6: return 0
        if fetch[0] == 7: return 0
    except:
        sql.execute(f"SELECT owner_id FROM chats WHERE chat_id = {chat_id}")
        if sql.fetchall()[0][0] == user_id: return 7
        sql.execute(f"SELECT level FROM permissions_{chat_id} WHERE user_id = {user_id}")
        fetch = sql.fetchone()
        if fetch == None: return 0
        else: return fetch[0]

async def get_warns(user_id=int, chat_id=int):
    sql.execute(f"SELECT count FROM warns_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    if fetch == None: return 0
    else: return fetch[0]

# === Проверка, к какой связке принадлежит чат ===
async def get_gsync_chats(chat_id):
    sql.execute("SELECT owner_id, table_name FROM gsync_list")
    gsyncs = sql.fetchall()

    for owner_id, table_name in gsyncs:
        try:
            sql.execute(f"SELECT chat_id FROM {table_name} WHERE chat_id = ?", (chat_id,))
            if sql.fetchone():
                sql.execute(f"SELECT chat_id FROM {table_name}")
                chats = sql.fetchall()
                return [c[0] for c in chats]
        except:
            continue
    return None

# === Получение связки по чату (для info) ===
async def get_gsync_table(chat_id):
    sql.execute("SELECT owner_id, table_name FROM gsync_list")
    gsyncs = sql.fetchall()

    for owner_id, table_name in gsyncs:
        try:
            sql.execute(f"SELECT chat_id FROM {table_name} WHERE chat_id = ?", (chat_id,))
            if sql.fetchone():
                return {"owner": owner_id, "table": table_name}
        except:
            continue
    return None    

async def get_user_name(user_id: int, chat_id: int | None = None) -> str:
    # Сначала проверяем ник в базе, только если chat_id задан
    if chat_id is not None:
        try:
            sql.execute(f"SELECT nick FROM nicks_{chat_id} WHERE user_id = ?", (user_id,))
            fetch = sql.fetchone()
            if fetch and fetch[0]:
                return fetch[0]
        except:
            pass  # На случай, если таблицы нет

    # Если ника нет или chat_id не задан, пытаемся получить имя и фамилию через API
    try:
        info = await bot.api.users.get(user_ids=user_id)
        if info and len(info) > 0:
            return f"{info[0].first_name} {info[0].last_name}"
    except:
        pass

    # Если ничего не получилось, возвращаем ID
    return str(user_id)
    
# Функция очистки варнов
async def clear_all_warns(chat_id: int) -> int:
    # Проверяем, есть ли записи
    sql.execute(f"SELECT DISTINCT user_id FROM warns_{chat_id}")
    users = sql.fetchall()

    if not users:
        return 0  # ничего нет

    count = len(users)

    # Удаляем все варны
    sql.execute(f"DELETE FROM warns_{chat_id}")
    database.commit()

    return count
    
async def is_nick(user_id=int, chat_id=int):
    sql.execute(f"SELECT nick FROM nicks_{chat_id} WHERE user_id = {user_id}")
    if sql.fetchone() == None: return False
    else: return True

async def setnick(user_id=int, chat_id=int, nick=str):
    sql.execute(f"SELECT nick FROM nicks_{chat_id} WHERE user_id = {user_id}")
    if sql.fetchone() == None:
        sql.execute(f"INSERT INTO nicks_{chat_id} VALUES (?, ?)", (user_id, nick))
        database.commit()
    else:
        sql.execute(f"UPDATE nicks_{chat_id} SET nick = ? WHERE user_id = ?", (nick, user_id))
        database.commit()

async def rnick(user_id=int, chat_id=int):
    sql.execute(f"DELETE FROM nicks_{chat_id} WHERE user_id = {user_id}")
    database.commit()

async def get_acc(chat_id=int, nick=str):
    sql.execute(f"SELECT user_id FROM nicks_{chat_id} WHERE nick = '{nick}'")
    fetch = sql.fetchone()
    if fetch == None: return False
    else: return fetch[0]

async def get_nick(user_id=int, chat_id=int):
    sql.execute(f"SELECT nick FROM nicks_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    if fetch == None: return False
    else: return fetch[0]

async def log_economy(user_id=None, target_id=None, amount=None, log=None):
    try:
        sql.execute(
            "INSERT INTO economy (user_id, target_id, amount, log) VALUES (?, ?, ?, ?)",
            (user_id, target_id, amount, log)
        )
        database.commit()
        print(f"[ECONOMY LOG] {user_id} -> {target_id} | {amount} | {log}")
    except Exception as e:
        print(f"[ECONOMY LOG ERROR] {e}")       
        
async def chats_log(user_id=None, target_id=None, role=None, log=None):
    try:
        sql.execute(
            "INSERT INTO logchats (user_id, target_id, role, log) VALUES (?, ?, ?, ?)",
            (user_id, target_id, role, log)
        )
        database.commit()
        print(f"[CHATS LOG] {user_id} -> {target_id} | {role} | {log}")
    except Exception as e:
        print(f"[CHATS LOG ERROR] {e}")       

async def nlist(chat_id: int, page: int):
    sql.execute(f"SELECT * FROM nicks_{chat_id}")
    fetch = sql.fetchall()
    if not fetch:
        return []

    nicks = []
    gi = 0
    with open("config.json", "r") as json_file:
        open_file = json.load(json_file)
    max_nicks = open_file.get('nicks_max', 20)

    start = (page - 1) * max_nicks
    end = page * max_nicks

    for i in fetch:
        if gi < start:
            gi += 1
            continue
        if gi >= end:
            break

        info = await bot.api.users.get(user_ids=i[0])
        if info and len(info) > 0:
            name = f"{info[0].first_name} {info[0].last_name}"
        else:
            name = "Ошибка"

        nicks.append(f"{gi+1}. @id{i[0]} ({name}) -- {i[1]}")
        gi += 1

    return nicks 

async def nonick(chat_id=int, page=int):
    sql.execute(f"SELECT * FROM nicks_{chat_id}")
    fetch = sql.fetchall()
    nicks = []
    for i in fetch:
        nicks.append(i[0])

    gi = 0
    nonick = []
    with open("config.json", "r") as json_file:
        open_file = json.load(json_file)
    max_nonick = open_file['nonick_max']
    users = await bot.api.messages.get_conversation_members(peer_id=2000000000+chat_id)
    users = json.loads(users.json())
    for i in users["profiles"]:
        if not i['id'] in nicks:
            gi = gi + 1
            if page*max_nonick >= gi and page*max_nonick-max_nonick < gi:
                nonick.append(f"{gi}) @id{i['id']} ({i['first_name']} {i['last_name']})")

    return nonick

async def warn(chat_id=int, user_id=int, moder=int, reason=str):
    actualy_warns = await get_warns(user_id, chat_id)
    date = time.time()
    cd = str(datetime.now()).split('.')
    date_string = cd[0]
    sql.execute(f"INSERT INTO warnhistory_{chat_id} VALUES (?, {actualy_warns+1}, ?, ?, {date}, '{date_string}')",(user_id, moder, reason))
    database.commit()
    if actualy_warns < 1:
        sql.execute(f"INSERT INTO warns_{chat_id} VALUES (?, 1, ?, ?, {date}, '{date_string}')", (user_id, moder, reason))
        database.commit()
        return 1
    else:
        sql.execute(f"UPDATE warns_{chat_id} SET user_id = ?, count = ?, moder = ?, reason = ?, date = {date}, date_string = '{date_string}' WHERE user_id = {user_id}", (user_id, actualy_warns+1, moder, reason))
        database.commit()
        return actualy_warns+1

async def clear_warns(chat_id=int, user_id=int):
    sql.execute(f"DELETE FROM warns_{chat_id} WHERE user_id = {user_id}")
    database.commit()

async def unwarn(chat_id=int, user_id=int):
    warns = await get_warns(user_id, chat_id)
    if warns < 2: await clear_warns(chat_id, user_id)
    else:
        sql.execute(f"UPDATE warns_{chat_id} SET count = {warns-1} WHERE user_id = {user_id}")
        database.commit()

    return warns-1

async def gwarn(user_id=int, chat_id=int):
    sql.execute(f"SELECT * FROM warns_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    if fetch == None: return False
    else:
        return {
            'count': fetch[1],
            'moder': fetch[2],
            'reason': fetch[3],
            'time': fetch[5]
        }

async def warnhistory(user_id=int, chat_id=int):
    sql.execute(f"SELECT * FROM warnhistory_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchall()
    warnhistory_mass = []
    gi = 0
    if fetch == None: return False
    else:
        for i in fetch:
            gi = gi + 1
            warnhistory_mass.append(f"{gi}) @id{i[2]} (Модератор) | {i[3]} | {i[5]}")

    return warnhistory_mass

async def warnlist(chat_id=int):
    sql.execute(f"SELECT * FROM warns_{chat_id}")
    fetch = sql.fetchall()
    warns = []
    gi = 0
    for i in fetch:
        gi = gi + 1
        warns.append(f"{gi}) @id{i[0]} (Пользователь) | {i[3]} | @id{i[2]} (Модератор) | {i[1]}/3 | {i[5]}")

    if fetch == None: return False
    return warns

async def staff(chat_id: int):
    # ==== Локальные права из чата ====
    sql.execute(f"SELECT * FROM permissions_{chat_id}")
    fetch = sql.fetchall()
    moders = []
    stmoders = []
    admins = []
    stadmins = []
    zamspecadm = []
    specadm = []
    testers = []

    if fetch:
        for i in fetch:
            level = i[1]
            user_id = i[0]
            if level == 1: moders.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            elif level == 2: stmoders.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            elif level == 3: admins.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            elif level == 4: stadmins.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            elif level == 5: zamspecadm.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            elif level == 6: specadm.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            elif level == 12: testers.append(f'@id{user_id} ({await get_user_name(user_id, chat_id)})')

    # ==== Глобальные права ====
    sql.execute("SELECT user_id, level FROM global_managers WHERE level IN (2,3,4,5,6,7)")
    global_fetch = sql.fetchall()
    zamruk = []
    oszamruk = []
    ruk = []
    dev = []
    zamglt = []
    glt = []

    for user_id, level in global_fetch:
        if level == 2: zamruk.append(f'@id{user_id} ({await get_user_name(user_id, None)})')
        elif level == 3: oszamruk.append(f'@id{user_id} ({await get_user_name(user_id, None)})')
        elif level == 4: ruk.append(f'@id{user_id} ({await get_user_name(user_id, None)})')
        elif level == 5: dev.append(f'@id{user_id} ({await get_user_name(user_id, None)})')
        elif level == 6: zamglt.append(f'@id{user_id} ({await get_user_name(user_id, None)})')
        elif level == 7: glt.append(f'@id{user_id} ({await get_user_name(user_id, None)})')

    return {
        'moders': moders,
        'stmoders': stmoders,
        'admins': admins,
        'stadmins': stadmins,
        'zamspecadm': zamspecadm,
        'specadm': specadm,
        'testers': testers,
        'zamruk': zamruk,
        'oszamruk': oszamruk,
        'ruk': ruk,
        'dev': dev,
        'zamglt': zamglt,
        'glt': glt
    }    

async def add_mute(user_id=int, chat_id=int, moder=int, reason=str, mute_time=int):
    cd = str(datetime.now()).split('.')
    date_string = cd[0]
    sql.execute(f"INSERT INTO mutes_{chat_id} VALUES (?, ?, ?, ?, ?, ?)", (user_id, moder, reason, time.time(), date_string, mute_time))
    database.commit()

async def get_mute(user_id=int, chat_id=int):
    await checkMute(chat_id, user_id)

    sql.execute(f"SELECT * FROM mutes_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()

    if fetch == None: return False
    else:
        return {
            'moder': fetch[1],
            'reason': fetch[2],
            'date': fetch[4],
            'time': fetch[5]
        }

async def unmute(user_id=int, chat_id=int):
    sql.execute(f"DELETE FROM mutes_{chat_id} WHERE user_id = {user_id}")
    database.commit()

async def mutelist(chat_id=int):
    sql.execute(f"SELECT * FROM mutes_{chat_id}")
    fetch = sql.fetchall()
    mutes = []
    if fetch==None: return False
    else:
        for i in fetch:
            if not await checkMute(chat_id, i[0]):
                do_time = datetime.fromisoformat(i[4]) + timedelta(minutes=i[5])
                mute_time = str(do_time).split('.')[0]
                try:
                    int(i[1])
                    mutes.append(f"@id{i[0]} (Пользователь) | {i[2]} | @id{i[1]} (модератор) | До: {mute_time}")
                except: mutes.append(f"@id{i[0]} (Пользователь) | {i[2]} | Бот | До: {mute_time}")

    return mutes

async def checkMute(chat_id=int, user_id=int):
    sql.execute(f"SELECT * FROM mutes_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    if not fetch == None:
        do_time = datetime.fromisoformat(fetch[4]) + timedelta(minutes=fetch[5])
        if datetime.now() > do_time:
            sql.execute(f"DELETE FROM mutes_{chat_id} WHERE user_id = {user_id}")
            database.commit()
            return True
        else: return False
    return False

async def get_banwords(chat_id=int):
    sql.execute(f"SELECT * FROM banwords_{chat_id}")
    banwords = []
    fetch = sql.fetchall()
    for i in fetch:
        banwords.append(i[0])

    return banwords

async def clear(user_id=int, chat_id=int, group_id=int, peer_id=int):
    sql.execute(f"SELECT cmid FROM messages_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchall()
    cmids = []
    gi = 0
    for i in fetch:
        gi = gi + 1
        if gi <= 199:
            cmids.append(i[0])
    try: await bot.api.messages.delete(group_id=group_id, peer_id=peer_id, delete_for_all=True, cmids=cmids)
    except: pass

    sql.execute(f"DELETE FROM messages_{chat_id} WHERE user_id = {user_id}")
    database.commit()

async def new_message(user_id=int, message_id=int, cmid=int, chat_id=int):
    cd = str(datetime.now()).split('.')
    date_string = cd[0]
    sql.execute(f"INSERT INTO messages_{chat_id} VALUES (?, ?, ?, ?, ?)", (user_id, time.time(), date_string, message_id, cmid))
    database.commit()

async def add_money(user_id, amount):
    balances = load_data(BALANCES_FILE)
    bal = balances.get(str(user_id), get_balance(user_id))
    bal["wallet"] += amount
    balances[str(user_id)] = bal
    save_data(BALANCES_FILE, balances)
    await log_economy(user_id=user_id, target_id=None, amount=amount, log=f"получил(+а) {amount}$ через промокод")
    return True

async def give_vip(user_id, days):
    balances = load_data(BALANCES_FILE)
    bal = balances.get(str(user_id), get_balance(user_id))

    now = datetime.now()
    if bal.get("vip_until"):
        try:
            until = datetime.fromisoformat(bal["vip_until"])
            if until > now:
                bal["vip_until"] = (until + timedelta(days=days)).isoformat()
            else:
                bal["vip_until"] = (now + timedelta(days=days)).isoformat()
        except:
            bal["vip_until"] = (now + timedelta(days=days)).isoformat()
    else:
        bal["vip_until"] = (now + timedelta(days=days)).isoformat()

    balances[str(user_id)] = bal
    save_data(BALANCES_FILE, balances)
    await log_economy(user_id=user_id, target_id=None, amount=None, log=f"получил(+а) VIP на {days} дней через промокод")
    return True    

# --- Функция проверки бана только в одном чате ---
async def checkban(user_id: int, chat_id: int):
    try:
        sql.execute(f"SELECT * FROM bans_{chat_id} WHERE user_id = ?", (user_id,))
        fetch = sql.fetchone()
        if not fetch:
            return False
        return {
            'moder': fetch[1],
            'reason': fetch[2],
            'date': fetch[4]
        }
    except:
        return False  # если таблицы нет   
        
async def checkban_all(user_id: int):
    sql.execute("SELECT chat_id, title FROM chats")
    chats_list = sql.fetchall()

    all_bans = []
    count_bans = 0

    i = 1
    for c in chats_list:
        chat_id_check, chat_title = c
        table_name = f"bans_{chat_id_check}"
        try:
            sql.execute(f"SELECT moderator_id, reason, date FROM {table_name} WHERE user_id = ?", (user_id,))
            user_bans = sql.fetchall()
            for ub in user_bans:
                mod_id, reason, date = ub
                all_bans.append(f"{i}) {chat_title} | @id{mod_id} (Модератор) | {reason} | {date} МСК (UTC+3)")
                i += 1
                count_bans += 1
        except:
            continue  # если таблицы нет, пропускаем

    return count_bans, all_bans        

# --- Функция добавления/обновления бана ---
async def ban(user_id: int, moder: int, chat_id: int, reason: str):
    # Проверяем, есть ли уже бан
    sql.execute(f"SELECT user_id FROM bans_{chat_id} WHERE user_id = ?", (user_id,))
    fetch = sql.fetchone()

    # Текущее время в формате YYYY-MM-DD HH:MM:SS
    date_string = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if fetch is None:
        # Добавляем нового забаненного пользователя
        sql.execute(
            f"INSERT INTO bans_{chat_id} (user_id, moder, reason, date) VALUES (?, ?, ?, ?)",
            (user_id, moder, reason, date_string)
        )
        database.commit()
    else:
        # Обновляем данные, если пользователь уже в бане
        sql.execute(
            f"UPDATE bans_{chat_id} SET moder = ?, reason = ?, date = ? WHERE user_id = ?",
            (moder, reason, date_string, user_id)
        )
        database.commit()
        
async def unban(user_id=int, chat_id=int):
    sql.execute(f"DELETE FROM bans_{chat_id} WHERE user_id = {user_id}")
    database.commit()

async def globalrole(user_id: int, level: int):
    """
    Выдаёт или обновляет глобальную роль пользователя в таблице global_managers.

    level:
        0 - удаление роли
        8 - zamruk
        9 - oszamruk
        10 - ruk
        11 - dev
    """
    # Проверяем есть ли запись
    sql.execute("SELECT user_id FROM global_managers WHERE user_id = ?", (user_id,))
    fetch = sql.fetchone()

    if fetch is None:
        if level != 0:
            sql.execute("INSERT INTO global_managers (user_id, level) VALUES (?, ?)", (user_id, level))
    else:
        if level == 0:
            sql.execute("DELETE FROM global_managers WHERE user_id = ?", (user_id,))
        else:
            sql.execute("UPDATE global_managers SET level = ? WHERE user_id = ?", (level, user_id))

    database.commit()    

async def roleG(user_id=int, chat_id=int, role=int):
    sql.execute(f"SElECT user_id FROM permissions_{chat_id} WHERE user_id = {user_id}")
    fetch = sql.fetchone()
    if fetch == None:
        if role == 0: sql.execute(f"DELETE FROM permissions_{chat_id} WHERE user_id = {user_id}")
        else: sql.execute(f"INSERT INTO permissions_{chat_id} VALUES (?, ?)", (user_id, role))
    else:
        if role == 0: sql.execute(f"DELETE FROM permissions_{chat_id} WHERE user_id = {user_id}")
        else: sql.execute(f"UPDATE permissions_{chat_id} SET level = ? WHERE user_id = ?", (role, user_id))

    database.commit()

async def banlist(chat_id=int):
    sql.execute(f"SELECT * FROM bans_{chat_id}")
    fetch = sql.fetchall()
    banlist = []
    for i in fetch:
        banlist.append(f"@id{i[0]} (Пользователь) | {i[2]} | @id{i[1]} (Модератор) | {i[4]}")

    return banlist

async def quiet(chat_id=int):
    sql.execute(f"SELECT silence FROM chats WHERE chat_id = {chat_id}")
    result = sql.fetchone()[0]
    if not await get_logic(result):
        sql.execute(f"UPDATE chats SET silence = 1 WHERE chat_id = {chat_id}")
        database.commit()
        return True
    else:
        sql.execute(f"UPDATE chats SET silence = 0 WHERE chat_id = {chat_id}")
        database.commit()
        return False

async def get_pull_chats(chat_id=int):
    sql.execute(f"SELECT owner_id, in_pull FROM chats WHERE chat_id = {chat_id}")
    fetch = sql.fetchone()
    if fetch == None: return False
    if not await get_logic(fetch[1]): return False
    sql.execute(f"SELECT chat_id FROM chats WHERE owner_id = ? AND in_pull = ?", (fetch[0], fetch[1]))
    result = []
    fetch2 = sql.fetchall()
    for i in fetch2:
        result.append(i[0])

    return result

async def get_pull_id(chat_id=int):
    sql.execute(f"SELECT in_pull FROM chats WHERE chat_id = {chat_id}")
    fetch = sql.fetchone()
    return fetch[0]

async def rnickall(chat_id=int):
    sql.execute(f"DELETE FROM nicks_{chat_id}")
    database.commit()    

async def banwords(slovo=str, delete=bool, chat_id=int):
    if delete:
        sql.execute(f"DELETE FROM banwords_{chat_id} WHERE banword = ?", (slovo, ))
        database.commit()
    else:
        sql.execute(f"SELECT * FROM banwords_{chat_id} WHERE banword = ?", (slovo, ))
        fetch = sql.fetchone()
        if fetch == None:
            sql.execute(f"INSERT INTO banwords_{chat_id} VALUES (?)", (slovo,))
            database.commit()

async def get_filter(chat_id=int):
    sql.execute(f"SELECT filter FROM chats WHERE chat_id = {chat_id}")
    fetch = sql.fetchone()
    return await get_logic(fetch[0])

async def set_filter(chat_id=int, value=int):
    sql.execute("UPDATE chats SET filter = ? WHERE chat_id = ?", (value, chat_id))
    database.commit()

async def get_antiflood(chat_id=int):
    sql.execute(f"SELECT antiflood FROM chats WHERE chat_id = {chat_id}")
    fetch = sql.fetchone()
    return await get_logic(fetch[0])

async def set_antiflood(chat_id=int, value=int):
    sql.execute("UPDATE chats SET antiflood = ? WHERE chat_id = ?", (value, chat_id))
    database.commit()

async def get_spam(user_id=int, chat_id=int):
    sql.execute(f"SELECT date_string FROM messages_{chat_id}  WHERE user_id = {user_id} ORDER BY date_string DESC LIMIT 3")
    fetch = sql.fetchall()
    list_messages = []
    for i in fetch:
        list_messages.append(datetime.fromisoformat(i[0]))
    try: list_messages = list_messages[:3]
    except: return False

    if list_messages[0] - list_messages[2] < timedelta(seconds=2): return True
    else: return False

async def set_welcome(chat_id=int, text=int):
    sql.execute(f"UPDATE chats SET welcome_text = ? WHERE chat_id = ?", (text, chat_id))
    database.commit()

async def get_welcome(chat_id=int):
    sql.execute("SELECT welcome_text FROM chats WHERE chat_id = ?", (chat_id, ))
    fetch = sql.fetchone()
    if str(fetch[0]).lower().strip() == "off": return False
    else: return str(fetch[0])

async def invite_kick(chat_id=int, change=None):
    sql.execute("SELECT invite_kick FROM chats WHERE chat_id = ?", (chat_id, ))
    fetch = sql.fetchone()
    if not change == None:
        if await get_logic(fetch[0]):
            sql.execute("UPDATE chats SET invite_kick = 0 WHERE chat_id = ?", (chat_id, ))
            database.commit()
            return False
        else:
            sql.execute("UPDATE chats SET invite_kick = 1 WHERE chat_id = ?", (chat_id,))
            database.commit()
            return True
    else:
        return await get_logic(fetch[0])

async def leave_kick(chat_id=int, change=None):
    sql.execute("SELECT leave_kick FROM chats WHERE chat_id = ?", (chat_id,))
    fetch = sql.fetchone()
    if fetch == None: return False
    if change == None: return await get_logic(fetch[0])
    if await get_logic(fetch[0]):
        sql.execute("UPDATE chats SET leave_kick = 0 WHERE chat_id = ?", (chat_id,))
        database.commit()
        return False
    else:
        sql.execute("UPDATE chats SET leave_kick = 1 WHERE chat_id = ?", (chat_id,))
        database.commit()
        return True

async def get_server_chats(chat_id):
    """
    Определяет, к какому серверу принадлежит чат, и возвращает список всех chat_id из этого сервера.
    """
    sql.execute("SELECT owner_id, server_number, table_name FROM servers_list")
    servers = sql.fetchall()

    for owner_id, server_number, table_name in servers:
        try:
            sql.execute(f"SELECT chat_id FROM {table_name} WHERE chat_id = ?", (chat_id,))
            if sql.fetchone():
                sql.execute(f"SELECT chat_id FROM {table_name}")
                chats = sql.fetchall()
                return [c[0] for c in chats]
        except:
            continue
    return None    

async def get_current_server(chat_id):
    """
    Возвращает номер сервера, к которому привязан данный chat_id, или None, если не привязан.
    """
    sql.execute("SELECT owner_id, server_number, table_name FROM servers_list")
    servers = sql.fetchall()

    for owner_id, server_number, table_name in servers:
        try:
            sql.execute(f"SELECT chat_id FROM {table_name} WHERE chat_id = ?", (chat_id,))
            if sql.fetchone():
                return server_number  # возвращаем только номер сервера
        except Exception as e:
            print(f"[get_current_server] Ошибка при проверке таблицы {table_name}: {e}")
            continue
    return None    

async def message_stats(user_id=int, chat_id=int):
    try:
        sql.execute(f"SELECT date_string FROM messages_{chat_id} WHERE user_id = ?", (user_id, ))
        fetch_all = sql.fetchall()
        sql.execute(f"SELECT date_string FROM messages_{chat_id} WHERE user_id = ? ORDER BY date_string DESC LIMIT 1", (user_id,))
        fetch_last = sql.fetchone()
        last = fetch_last[0]
        return {
            'count': len(fetch_all),
            'last': last
        }
    except: return {
        'count': 0,
        'last': 0
    }

async def set_pull(chat_id=int, value=int):
    sql.execute(f"UPDATE chats SET in_pull = ? WHERE chat_id = ?", (value, chat_id))
    database.commit()

async def get_all_peerids():
    sql.execute("SELECT peer_id FROM chats")
    fetch = sql.fetchall()
    peer_ids = []
    for i in fetch:
        peer_ids.append(i[0])

    return peer_ids

async def add_punishment(chat_id=int, user_id=int):
    cd = str(datetime.now()).split('.')
    date_string = cd[0]
    sql.execute(f"INSERT INTO punishments_{chat_id} VALUES (?, ?)", (user_id, date_string))
    database.commit()

async def get_sliv(user_id=int, chat_id=int):
    sql.execute(f"SELECT date FROM punishments_{chat_id}  WHERE user_id = {user_id} ORDER BY date DESC LIMIT 3")
    fetch = sql.fetchall()
    list_messages = []
    for i in fetch:
        list_messages.append(datetime.fromisoformat(i[0]))
    try: list_messages = list_messages[:3]
    except: return False

    if list_messages[0] - list_messages[2] < timedelta(seconds=6): return True
    else: return False

async def get_ServerChat(chat_id: int):
    try:
        # Получаем id сервера, к которому привязан chat_id
        sql.execute("SELECT server FROM server_links WHERE chat_id = ?", (chat_id,))
        result = sql.fetchone()
        if not result:
            return None

        server_id = result[0]

        # Получаем все chat_id, привязанные к этому серверу
        sql.execute("SELECT chat_id FROM server_links WHERE server = ?", (server_id,))
        chats = [row[0] for row in sql.fetchall()]

        return {
            "server": server_id,
            "chats": chats
        }
    except Exception as e:
        print(f"[SERVER] Ошибка при получении сервера: {e}")
        return None        

async def staff_zov(chat_id=int):
    sql.execute(f"SElECT user_id FROM permissions_{chat_id}")
    fetch = sql.fetchall()
    staff_zov_str = []
    for i in fetch:
        staff_zov_str.append(f"@id{i[0]} (⚜️)")

    return ''.join(staff_zov_str)

async def delete_message(group_id=int, peer_id=int, cmid=int):
    try: await bot.api.messages.delete(group_id=group_id, peer_id=peer_id, delete_for_all=True, cmids=cmid)
    except: pass

# Получить текущее состояние антислива (0 — выкл, 1 — вкл)
async def get_antisliv(chat_id):
    sql.execute("SELECT mode FROM antisliv WHERE chat_id = ?", (chat_id,))
    data = sql.fetchone()
    return data[0] if data else 0

# Установить новое состояние антислива
async def antisliv_mode(chat_id, mode):
    sql.execute("INSERT OR REPLACE INTO antisliv (chat_id, mode) VALUES (?, ?)", (chat_id, mode))
    database.commit()

async def set_onwer(user=int, chat=int):
    sql.execute("UPDATE chats SET owner_id = ? WHERE chat_id = ?", (user, chat))
    database.commit()

async def equals_roles(user_id_sender: int, user_id_two: int, chat_id: int, message):
    sender_role = await get_role(user_id_sender, chat_id)
    target_role = await get_role(user_id_two, chat_id)

    # Проверка: если пользователь пытается применить команду на участника с более высоким рангом
    if sender_role < 7 and sender_role < target_role:
        await roleG(user_id_sender, chat_id, 0)
        await message.reply(
            f"❗️ Уровень прав @id{user_id_sender} (пользователя) был снят "
            f"из-за попытки использования команды на участника с более высоким рангом!"
        )
        return 0

    # Если всё нормально — возвращаем стандартные значения
    if sender_role > target_role:
        return 2
    elif sender_role == target_role:
        return 1
    else:
        return 0       
  
chat_types = {
    "def": "общие беседы",
    "ext": "расширенная беседа",
    "pl": "беседа игроков",
    "hel": "беседа хелперов",
    "ld": "беседа лидеров",
    "adm": "беседа администраторов",
    "mod": "беседа модераторов",
    "tex": "беседа техов",
    "test": "беседа тестеров",
    "med": "беседа медиа-партнёров",
    "ruk": "беседа руководства",
    "users": "беседа пользователей"
}

@bot.on.chat_message(rules.ChatActionRule("chat_kick_user"))
async def user_leave(message: Message) -> None:
    user_id = message.from_id
    chat_id = message.chat_id
    if not await check_chat(chat_id): return True
    if not message.action.member_id == message.from_id: return True
    if await leave_kick(chat_id):
        try: await bot.api.messages.remove_chat_user(chat_id, user_id)
        except: pass
        await message.answer(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), вышел(-ла) из беседы", disable_mentions=1)
    else:
        keyboard = (
            Keyboard(inline=True)
            .add(Callback("Исключить", {"command": "kick", "user": user_id, "chatId": chat_id}), color=KeyboardButtonColor.NEGATIVE)
        )
        await message.answer(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), вышел(-ла) из беседы", disable_mentions=1, keyboard=keyboard)

@bot.on.chat_message(rules.ChatActionRule("chat_invite_user"))
async def user_joined(message: Message) -> None:
    invited_user = message.action.member_id
    user_id = message.from_id
    chat_id = message.chat_id

    # если чат не в базе — игнорируем
    if not await check_chat(chat_id):
        return True
        
    async def _safe_first_name(uid: int) -> str:
        try:
            resp = await bot.api.users.get(uid)
            if resp and len(resp) > 0:
                return resp[0].first_name
        except Exception:
            pass
        return str(uid)

    try:
        # Бот добавлен
        if invited_user == -232890128:
            await message.answer(
                "Бот добавлен в беседу, выдайте мне администратора, а затем введите /sync для синхронизации с базой данных!\n\n"
                "Также с помощью /type Вы можете выбрать тип беседы!"
            )
            return True
        
        # ==== 🔹 Проверка защиты от сторонних сообществ ====
        sql.execute("SELECT * FROM protection WHERE chat_id = ? AND mode = 1", (chat_id,))
        prot = sql.fetchone()
        if prot:
            if invited_user < 0:  # сообщество
                try:
                    await bot.api.messages.remove_chat_user(chat_id, invited_user)
                except:
                    pass
                await message.answer(
                    f"@id{user_id} ({await get_user_name(user_id, chat_id)}) добавил сообщество, это запрещено в настройках данного чата!\n\n"
                    f"Выключить можно: «/защита»",
                    disable_mentions=1
                )
                return True

        # ==== 🔹 Проверка глобального бана ====
        sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (invited_user,))
        globalban = sql.fetchone()
        if globalban:
            try:
                await bot.api.messages.remove_chat_user(chat_id, invited_user)
            except:
                pass

            first = await _safe_first_name(invited_user)
            await message.answer(
                f"@id{invited_user} ({await get_user_name(invited_user, chat_id)}) имеет глобальную блокировку!\n\n"
                f"@id{globalban[1]} (Модератор) | {globalban[2]} | {globalban[3]}",
                disable_mentions=1
            )
            return True
            
        # ==== 🔹 Проверка глобального бана ====
        sql.execute("SELECT * FROM globalban WHERE user_id = ?", (invited_user,))
        globalban = sql.fetchone()
        if globalban:
            try:
                await bot.api.messages.remove_chat_user(chat_id, invited_user)
            except:
                pass

            first = await _safe_first_name(invited_user)
            await message.answer(
                f"@id{invited_user} ({await get_user_name(invited_user, chat_id)}), имеет общую блокировку во всех беседах!\n\n"
                f"@id{globalban[1]} (Модератор) | {globalban[2]} | {globalban[3]}",
                disable_mentions=1
            )
            return True            

        # ==== Пользователь вошёл сам ====
        if user_id == invited_user:
            checkban_str = await checkban(invited_user, chat_id)
            if checkban_str:
                try:
                    await bot.api.messages.remove_chat_user(chat_id, invited_user)
                except:
                    pass

                first = await _safe_first_name(invited_user)
                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Снять бан", payload=""), color=KeyboardButtonColor.POSITIVE)
                )
                await message.answer(
                    f"@id{invited_user} ({await get_user_name(invited_user, chat_id)}) заблокирован(-а) в этой беседе!\n\n"
                    f"Информация о блокировке:\n@id{checkban_str['moder']} (Модератор) | {checkban_str['reason']} | {checkban_str['date']}",
                    disable_mentions=1,
                    keyboard=keyboard
                )
                return True

            welcome = await get_welcome(chat_id)
            if welcome:
                first = await _safe_first_name(invited_user)
                inviter_first = await _safe_first_name(user_id)
                welcome = welcome.replace('%u', f'@id{invited_user}')
                welcome = welcome.replace('%n', f'@id{invited_user} ({await get_user_name(invited_user, chat_id)})')
                welcome = welcome.replace('%i', f'@id{user_id}')
                welcome = welcome.replace('%p', f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
                await message.answer(welcome)
                return True

        # ==== Кто-то пригласил другого пользователя ====
        if await get_role(user_id, chat_id) < 1 and await invite_kick(chat_id):
            try:
                await bot.api.messages.remove_chat_user(chat_id, invited_user)
            except:
                pass
            return True

        checkban_str = await checkban(invited_user, chat_id)
        if checkban_str:
            try:
                await bot.api.messages.remove_chat_user(chat_id, invited_user)
            except:
                pass

            first = await _safe_first_name(invited_user)
            keyboard = (
                Keyboard(inline=True)
                .add(Callback("Снять бан", payload=""), color=KeyboardButtonColor.POSITIVE)
            )
            await message.answer(
                f"@id{invited_user} ({await get_user_name(invited_user, chat_id)}) заблокирован(-а) в этой беседе!\n\n"
                f"Информация о блокировке:\n@id{checkban_str['moder']} (Модератор) | {checkban_str['reason']} | {checkban_str['date']}",
                disable_mentions=1,
                keyboard=keyboard
            )
            return True

        welcome = await get_welcome(chat_id)
        if welcome:
            first = await _safe_first_name(invited_user)
            inviter_first = await _safe_first_name(user_id)
            welcome = welcome.replace('%u', f'@id{invited_user}')
            welcome = welcome.replace('%n', f'@id{invited_user} ({await get_user_name(invited_user, chat_id)})')
            welcome = welcome.replace('%i', f'@id{user_id}')
            welcome = welcome.replace('%p', f'@id{user_id} ({await get_user_name(user_id, chat_id)})')
            await message.answer(welcome)
            return True

    except Exception as e:
        print(f"[user_joined] Ошибка: {e}")
        return True        

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT, dataclass=GroupTypes.MessageEvent)
async def handlers(message: GroupTypes.MessageEvent):
    payload = message.object.payload or {}
    command = str(payload.get("command", "")).lower()
    user_id = message.object.user_id
    chat_id = payload.get("chatId")

    # Лог для каждой кнопки
    log_cmd = payload.get("log") or "нет лога"
    print(f"{user_id} использовал кнопку {command}. ВК выдало: {log_cmd}")
    if command == "nicksminus":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True
        page = payload.get("page")
        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "nicksMinus", "page": page - 1, "chatId": chat_id}),
                 color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("Без ников", {"command": "nonicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
            .add(Callback("⏩", {"command": "nicksPlus", "page": page - 1, "chatId": chat_id}),
                 color=KeyboardButtonColor.POSITIVE)
        )
        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        nicks_str = '\n'.join(await nlist(chat_id, page-1))
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"Пользователи с ником [{page-1} страница]:\n{nicks_str}\n\nПользователи без ников: «/nonick»", disable_mentions=1, random_id=0, keyboard=keyboard)

    if command == "nicksplus":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")

        nicks = await nlist(chat_id, page + 1)
        if len(nicks) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "nicksMinus", "page": page+1, "chatId": chat_id}),
                 color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("Без ников", {"command": "nonicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
            .add(Callback("⏩", {"command": "nicksPlus", "page": page+1, "chatId": chat_id}),
                 color=KeyboardButtonColor.POSITIVE)
        )
        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        nicks_str = '\n'.join(nicks)
        await bot.api.messages.send(peer_id=2000000000 + chat_id,message=f"Пользователи с ником [{page + 1} страница]:\n{nicks_str}\n\nПользователи без ников: «/nonick»",disable_mentions=1, random_id=0, keyboard=keyboard)

    if command == "chatsminus":
        if await get_role(user_id, chat_id) < 10:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")
        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        sql.execute("SELECT chat_id, owner_id FROM chats ORDER BY chat_id ASC")
        all_rows = sql.fetchall()
        total = len(all_rows)
        per_page = 5
        max_page = (total + per_page - 1) // per_page

        async def get_chats_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            selected = all_rows[start:end]
            formatted = []
            for idx, (chat_id_row, owner_id) in enumerate(selected, start=start + 1):
                rel_id = 2000000000 + chat_id_row
                try:
                    resp = await bot.api.messages.get_conversations_by_id(peer_ids=rel_id)
                    if resp.items:
                        chat_title = resp.items[0].chat_settings.title or "Без названия"
                    else:
                        chat_title = "Без названия"
                except:
                    chat_title = "Ошибка получения названия"

                try:
                    link_resp = await bot.api.messages.get_invite_link(peer_id=rel_id, reset=0)
                    chat_link = link_resp.link
                except:
                    chat_link = "Не удалось получить"

                try:
                    owner_info = await bot.api.users.get(user_ids=owner_id)
                    owner_name = f"{owner_info[0].first_name} {owner_info[0].last_name}"
                except:
                    owner_name = "Не удалось получить имя"

                formatted.append(
                    f"{idx}. 💬 Беседа №{chat_id_row}\n"
                    f"📛 Название: {chat_title}\n"
                    f"👑 Владелец: @id{owner_id} ({owner_name})\n"
                    f"🔗 Ссылка: {chat_link}\n"
                )
            return formatted

        new_page = page - 1
        chats = await get_chats_page(new_page)
        chats_text = "\n".join(chats)
        if not chats_text:
            chats_text = "Беседы отсутствуют!"

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "chatsMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "chatsPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Список зарегистрированных бесед [{new_page} страница из {max_page}]:\n\n{chats_text}\n📊 Всего бесед: {total}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True


    if command == "chatsplus":
        if await get_role(user_id, chat_id) < 10:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")

        sql.execute("SELECT chat_id, owner_id FROM chats ORDER BY chat_id ASC")
        all_rows = sql.fetchall()
        total = len(all_rows)
        per_page = 5
        max_page = (total + per_page - 1) // per_page

        async def get_chats_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            selected = all_rows[start:end]
            formatted = []
            for idx, (chat_id_row, owner_id) in enumerate(selected, start=start + 1):
                rel_id = 2000000000 + chat_id_row
                try:
                    resp = await bot.api.messages.get_conversations_by_id(peer_ids=rel_id)
                    if resp.items:
                        chat_title = resp.items[0].chat_settings.title or "Без названия"
                    else:
                        chat_title = "Без названия"
                except:
                    chat_title = "Ошибка получения названия"

                try:
                    link_resp = await bot.api.messages.get_invite_link(peer_id=rel_id, reset=0)
                    chat_link = link_resp.link
                except:
                    chat_link = "Не удалось получить"

                try:
                    owner_info = await bot.api.users.get(user_ids=owner_id)
                    owner_name = f"{owner_info[0].first_name} {owner_info[0].last_name}"
                except:
                    owner_name = "Не удалось получить имя"

                formatted.append(
                    f"{idx}. 💬 Беседа №{chat_id_row}\n"
                    f"📛 Название: {chat_title}\n"
                    f"👑 Владелец: @id{owner_id} ({owner_name})\n"
                    f"🔗 Ссылка: {chat_link}\n"
                )
            return formatted

        new_page = page + 1
        chats = await get_chats_page(new_page)
        if len(chats) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        chats_text = "\n".join(chats)
        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "chatsMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "chatsPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Список зарегистрированных бесед [{new_page} страница из {max_page}]:\n\n{chats_text}\n📊 Всего бесед: {total}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True
        
    if command == "nonicks":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        nonicks = await nonick(chat_id, 1)
        nonick_list = '\n'.join(nonicks)
        if nonick_list == "": nonick_list = "Пользователи без ников отсутствуют!"

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "nonickMinus", "page": 1, "chatId": chat_id}),
                 color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("С никами", {"command": "nicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
            .add(Callback("⏩", {"command": "nonickPlus", "page": 1, "chatId": chat_id}),
                 color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(peer_id=2000000000+chat_id, message=f"Пользователи без ников [1]:\n{nonick_list}\n\nПользователи с никами: «/nlist»", disable_mentions=1, random_id=0 ,keyboard=keyboard)

    if command == "nicks":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        nicks = await nlist(chat_id, 1)
        nick_list = '\n'.join(nicks)
        if nick_list == "": nick_list = "Ники отсутствуют!"

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "nicksMinus", "page": 1, "chatId": chat_id}),
                 color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("Без ников", {"command": "nonicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
            .add(Callback("⏩", {"command": "nicksPlus", "page": 1, "chatId": chat_id}),
                 color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(peer_id=2000000000+chat_id, message=f"Пользователи с ником [1 страница]:\n{nick_list}\n\nПользователи без ников: «/nonick»",
                            disable_mentions=1, keyboard=keyboard, random_id=0)

    if command == "nonickminus":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")
        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        nonicks = await nonick(chat_id, 1)
        nonick_list = '\n'.join(nonicks)
        if nonick_list == "": nonick_list = "Пользователи без ников отсутствуют!"

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "nonickMinus", "page": page+1, "chatId": chat_id}),
                 color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("С никами", {"command": "nicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
            .add(Callback("⏩", {"command": "nonickPlus", "page": page+1, "chatId": chat_id}),
                 color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"Пользователи без ников [{page-1}]:\n{nonick_list}\n\nПользователи с никами: «/nlist»", disable_mentions=1, random_id=0, keyboard=keyboard)

    if command == "nonickplus":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True
        page = payload.get("page")
        nonicks = await nonick(chat_id, page+1)
        if len(nonicks) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        nonicks_str = '\n'.join(nonicks)
        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(peer_id=2000000000 + chat_id,
                                    message=f"Пользователи без ников [{page + 1}]:\n{nonicks_str}\n\nПользователи с никами: «/nlist»",
                                    disable_mentions=1, random_id=0, keyboard=keyboard)

    if command == "clear":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")
        await clear(user, chat_id, message.group_id, 2000000000+chat_id)
        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000+chat_id, conversation_message_ids=message.object.conversation_message_id, group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x, conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) очистил(-а) сообщения", disable_mentions=1, random_id=0)

    if command == "unwarn":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")
        if await equals_roles(user_id, user, chat_id, message) < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Вы не можете снять пред данному пользователю!"})
            )
            return True

        await unwarn(chat_id, user)
        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,conversation_message_ids=message.object.conversation_message_id,group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x, conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) снял(-а) предупреждение @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1, random_id=0)

    if command == 'stats':
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")
        reg_data = await get_registration_date(user)
        info = await bot.api.users.get(user)
        role = await get_role(user, chat_id)
        warns = await get_warns(user, chat_id)
        if await is_nick(user_id, chat_id):
            nick = await get_user_name(user, chat_id)
        else:
            nick = "Нет"
        messages = await message_stats(user_id, chat_id)

        roles = {0: "Пользователь", 1: "Модератор", 2: "Старший Модератор", 3: "Администратор",
                 4: "Старший Администратор", 5: "Владелец беседы", 6: "Менеджер бота"}

        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,
                                                                  conversation_message_ids=message.object.conversation_message_id,
                                                                  group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x,conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}), статистика @id{user} (пользователя):\nИмя и фамилия: {info[0].first_name} {info[0].last_name}\nДата регистрации: {reg_data}\nНик: {nick}\nРоль: {roles.get(role)}\nВсего предупреждений: {warns}/3\nВсего сообщений: {messages['count']}\nПоследнее сообщение: {messages['last']}", disable_mentions=1, random_id=0)

    if command == "activewarns":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")
        warns = await gwarn(user, chat_id)
        string_info = str
        if not warns: string_info = "Активных предупреждений нет!"
        else: string_info = f"@id{warns['moder']} (Модератор) | {warns['reason']} | {warns['count']}/3 | {warns['time']}"

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("История всех предупреждений", {"command": "warnhistory", "user": user, "chatId": chat_id}),
                 color=KeyboardButtonColor.PRIMARY)
        )

        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,
                                                                  conversation_message_ids=message.object.conversation_message_id,
                                                                  group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x,
                                    conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}), информация о активных предупреждениях @id{user} (пользователя):\n{string_info}", disable_mentions=1, keyboard=keyboard, random_id=0)

    if command == "warnhistory":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")

        warnhistory_mass = await warnhistory(user, chat_id)
        if not warnhistory_mass:wh_string = "Предупреждений не было!"
        else:wh_string = '\n'.join(warnhistory_mass)

        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,
                                                                  conversation_message_ids=message.object.conversation_message_id,
                                                                  group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x,
                                    conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id, message=f"Информация о всех предупреждениях @id{user} ({await get_user_name(user, chat_id)})\nКоличество предупреждений пользователя: {await get_warns(user, chat_id)}\n\nИнформация о последних 10 предупреждений пользователя:\n{wh_string}",disable_mentions=1, random_id=0)

    if command == "unmute":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")

        if await get_role(user_id, chat_id) <= await get_role(user, chat_id):
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        await unmute(user, chat_id)
        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,
                                                                  conversation_message_ids=message.object.conversation_message_id,
                                                                  group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x,
                                    conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id,
                                    message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) размутил(-а) @id{user} ({await get_user_name(user, chat_id)})",
                                    disable_mentions=1, random_id=0)

    if command == "unban":
        if await get_role(user_id, chat_id) < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")
        if await equals_roles(user_id, user, chat_id, message) < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps(
                    {"type": "show_snackbar", "text": "Вы не можете снять бан данному пользователю!"})
            )
            return True

        await unban(user, chat_id)
        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,
                                                                  conversation_message_ids=message.object.conversation_message_id,
                                                                  group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x,
                                    conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id,
                                    message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) разблокировал(-а) @id{user} ({await get_user_name(user, chat_id)})",
                                    disable_mentions=1, random_id=0)

    if command == "kick":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        user = payload.get("user")
        if await equals_roles(user_id, user, chat_id, message) < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps(
                    {"type": "show_snackbar", "text": "Вы не можете кикнуть данного пользователя!"})
            )
            return True

        try: await bot.api.messages.remove_chat_user(chat_id, user)
        except: pass

        x = await bot.api.messages.get_by_conversation_message_id(peer_id=2000000000 + chat_id,
                                                                  conversation_message_ids=message.object.conversation_message_id,
                                                                  group_id=message.group_id)
        x = json.loads(x.json())['items'][0]['text']
        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=x,
                                    conversation_message_id=message.object.conversation_message_id, keyboard=None)
        await bot.api.messages.send(peer_id=2000000000 + chat_id,
                                    message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) кикнул(-а) @id{user} ({await get_user_name(user, chat_id)})",
                                    disable_mentions=1, random_id=0)

    if command == "approve_form" or command == "reject_form":
        # Получаем chat_id из peer_id, если нужно
        chat_id = message.object.peer_id
        if chat_id > 2000000000:  # беседа
            chat_id -= 2000000000

        # Проверка прав
        if await get_role(user_id, chat_id) < 8:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        # Получаем данные из payload безопасно
        target = payload.get("target")
        sender = payload.get("sender")
        reason = payload.get("reason", "Не указано")

        if not target or not sender:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Ошибка: нет данных пользователя"})
            )
            return True

        # Редактируем предыдущее сообщение без кнопок
        x_resp = await bot.api.messages.get_by_conversation_message_id(
            peer_id=message.object.peer_id,
            conversation_message_ids=message.object.conversation_message_id,
            group_id=message.group_id
        )
        items = json.loads(x_resp.json()).get('items', [])
        if not items:
            return True
        x_text = items[0]['text']

        await bot.api.messages.edit(
            peer_id=message.object.peer_id,
            message=x_text,
            conversation_message_id=message.object.conversation_message_id,
            keyboard=None
        )

        # Выполняем approve или reject
        if command == "approve_form":
            sql.execute(
                "INSERT INTO gbanlist (user_id, moderator_id, reason_gban, datetime_globalban) VALUES (?, ?, ?, ?)",
                (target, user_id, f"{reason} | By form | @id{sender} (пользователь)",
                 datetime.now().strftime("%d.%m.%Y %H:%M"))
            )
            database.commit()

            await bot.api.messages.send(
                peer_id=message.object.peer_id,
                message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) одобрил форму пользователя @id{sender} ({await get_user_name(sender, chat_id)})",
                disable_mentions=1,
                random_id=0
            )
        else:
            await bot.api.messages.send(
                peer_id=message.object.peer_id,
                message=f"@id{user_id} ({await get_user_name(user_id, chat_id)}) отклонил форму пользователя @id{sender} ({await get_user_name(sender, chat_id)})",
                disable_mentions=1,
                random_id=0
            )

        return True

    if command == "banwordsminus":
        if await get_role(user_id, chat_id) < 10:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id, peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")
        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id, peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        sql.execute("SELECT word, creator_id, time FROM ban_words ORDER BY time DESC")
        rows = sql.fetchall()
        total = len(rows)
        per_page = 5
        max_page = (total + per_page - 1) // per_page

        async def get_words_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            formatted = []
            for i, (word, creator, tm) in enumerate(rows[start:end], start=start + 1):
                try:
                    info = await bot.api.users.get(user_ids=creator)
                    creator_name = f"{info[0].first_name} {info[0].last_name}"
                except:
                    creator_name = "Не удалось получить имя"
                formatted.append(f"{i}. {word} | @id{creator} ({creator_name}) | Время: {tm}")
            return formatted

        new_page = page - 1
        words = await get_words_page(new_page)
        words_text = "\n\n".join(words)

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "banwordsMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "banwordsPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Запрещённые слова (Страница: {new_page}):\n\n{words_text}\n\nВсего запрещенных слов: {total}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True


    if command == "banwordsplus":
        if await get_role(user_id, chat_id) < 10:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id, peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        page = payload.get("page")

        sql.execute("SELECT word, creator_id, time FROM ban_words ORDER BY time DESC")
        rows = sql.fetchall()
        total = len(rows)
        per_page = 5
        max_page = (total + per_page - 1) // per_page

        async def get_words_page(page: int):
            start = (page - 1) * per_page
            end = start + per_page
            formatted = []
            for i, (word, creator, tm) in enumerate(rows[start:end], start=start + 1):
                try:
                    info = await bot.api.users.get(user_ids=creator)
                    creator_name = f"{info[0].first_name} {info[0].last_name}"
                except:
                    creator_name = "Не удалось получить имя"
                formatted.append(f"{i}. {word} | @id{creator} ({creator_name}) | Время: {tm}")
            return formatted

        new_page = page + 1
        words = await get_words_page(new_page)
        if len(words) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id, peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        words_text = "\n\n".join(words)
        keyboard = (
            Keyboard(inline=True)
            .add(Callback("⏪", {"command": "banwordsMinus", "page": new_page}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("⏩", {"command": "banwordsPlus", "page": new_page}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"Запрещённые слова (Страница {new_page}):\n\n{words_text}\n\nВсего запрещенных слов: {total}",
            disable_mentions=1, random_id=0, keyboard=keyboard
        )
        return True        
        
    if command == "join_duel":
        try:
            # Разбор payload
            data = {}
            if message.object.payload:
                try:
                    if isinstance(message.object.payload, str):
                        data = json.loads(message.object.payload)
                    elif isinstance(message.object.payload, dict):
                        data = message.object.payload
                    else:
                        print(f"[join_duel] payload неизвестного типа: {type(message.object.payload)}")
                except Exception as e:
                    print(f"[join_duel] Ошибка парсинга payload: {e}")

            peer = str(data.get("peer")) if data else None
            print(f"[join_duel] peer из payload: {peer}")

            if not peer or peer not in duels:
                print(f"[join_duel] Дуэль недоступна: ключ '{peer}' не найден в duels. "
                      f"Текущие ключи: {list(duels.keys())}")
                await bot.api.messages.send_message_event_answer(
                    event_id=message.object.event_id,
                    peer_id=message.object.peer_id,
                    user_id=message.object.user_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "⚔️ Дуэль недоступна"})
                )
                return True

            duel = duels[peer]
            print(f"[join_duel] Найдена дуэль: {duel}")

            author = duel["author"]
            stake = duel["stake"]
            user_id = message.object.user_id

            if user_id == author:
                print("[join_duel] Игрок пытается вступить в свою же дуэль!")
                await bot.api.messages.send_message_event_answer(
                    event_id=message.object.event_id,
                    peer_id=message.object.peer_id,
                    user_id=user_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "Ты не можешь вступить в свою же дуэль!"})
                )
                return True

            # Загружаем баланс
            balances = load_data(BALANCES_FILE)
            joiner = balances.get(str(user_id), get_balance(user_id))
            if joiner["wallet"] < stake:
                print(f"[join_duel] Недостаточно монет у {user_id}: {joiner['wallet']} < {stake}")
                await bot.api.messages.send_message_event_answer(
                    event_id=message.object.event_id,
                    peer_id=message.object.peer_id,
                    user_id=user_id,
                    event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно монет!"})
                )
                return True

            # Определяем победителя
            winner = random.choice([author, user_id])
            loser = user_id if winner == author else author
            print(f"[join_duel] Победитель: {winner}, Проигравший: {loser}")

            w_bal = balances.get(str(winner), get_balance(winner))
            l_bal = balances.get(str(loser), get_balance(loser))

            w_bal["wallet"] += stake
            w_bal["won"] += 1
            w_bal["won_total"] += stake

            l_bal["wallet"] -= stake
            l_bal["lost"] += 1
            l_bal["lost_total"] += stake

            balances[str(winner)] = w_bal
            balances[str(loser)] = l_bal
            save_data(BALANCES_FILE, balances)
            print("[join_duel] Балансы обновлены и сохранены")

            # Получаем имена
            try:
                w_info = await bot.api.users.get(user_ids=winner)
                l_info = await bot.api.users.get(user_ids=loser)
                w_name = f"{w_info[0].first_name} {w_info[0].last_name}"
                l_name = f"{l_info[0].first_name} {l_info[0].last_name}"
            except Exception as e:
                print(f"[join_duel] Ошибка получения имён: {e}")
                w_name = str(winner)
                l_name = str(loser)

            # Убираем кнопки с исходного сообщения
            try:
                x_resp = await bot.api.messages.get_by_conversation_message_id(
                    peer_id=message.object.peer_id,
                    conversation_message_ids=duel["message_id"],
                    group_id=message.group_id
                )
                items = json.loads(x_resp.json()).get('items', [])
                if items:
                    x_text = items[0]['text']
                    await bot.api.messages.edit(
                        peer_id=message.object.peer_id,
                        message=x_text,
                        conversation_message_id=duel["message_id"],
                        keyboard=None
                    )
                    print("[join_duel] Кнопки успешно убраны")
            except Exception as e:
                print(f"[join_duel] Ошибка при удалении кнопок: {e}")

            # Отправляем результат
            await bot.api.messages.send(
                peer_id=message.object.peer_id,
                message=(
                    f"💥 Дуэль завершена!\n\n"
                    f"[id{winner}|{w_name}] vs [id{loser}|{l_name}]\n"
                    f"👑 Победитель: [id{winner}|{w_name}]\n\n"
                    f"💰 Он забирает {format_number(stake)}$"
                ),
                random_id=0
            )
            print("[join_duel] Результат отправлен")

            duels.pop(peer, None)
            save_data(DUELS_FILE, duels)
            print(f"[join_duel] Дуэль {peer} удалена из списка")
            return True

        except Exception as e:
            print(f"[join_duel] Общая ошибка: {e}")
            return True
                           
    if command == "getban":
        target_user = payload.get("getban")
        if not target_user:
            return True

        # Проверяем роль того, кто нажал кнопку
        role = await get_role(user_id, chat_id)
        if role < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({
                    "type": "show_snackbar",
                    "text": "Недостаточно прав для просмотра информации о блокировках!"
                })
            )
            return True

        # Удаляем старое сообщение
        try:
            await bot.api.messages.delete(
                group_id=message.group_id,
                peer_id=message.object.peer_id,
                cmids=message.object.conversation_message_id,
                delete_for_all=True
            )
        except:
            pass

        # Отправляем /getban
        await on_chat_message(
            Message(
                text=f"/getban {target_user}",
                from_id=message.object.user_id,
                peer_id=message.object.peer_id,
                chat_id=message.object.peer_id - 2000000000,
                group_id=message.group_id,
                object=message.object,
                random_id=0
            )
        )
        return True        

        if command == "kick_blacklisted":
            # Проверка прав — если меньше 7, показываем snackbar
            if await get_role(user_id, chat_id) < 7:
                try:
                    await bot.api.messages.send_message_event_answer(
                        event_id=message.object.event_id,
                        peer_id=message.object.peer_id,
                        user_id=message.object.user_id,
                        event_data=json.dumps({
                            "type": "show_snackbar",
                            "text": "Недостаточно прав!"
                        })
                    )
                except:
                    pass
                return True

            # Получаем пользователей из blacklist
            sql.execute("SELECT user_id FROM blacklist")
            blacklisted = sql.fetchall()
            if not blacklisted:
                try:
                    await bot.api.messages.edit(
                        peer_id=message.peer_id,
                        conversation_message_id=message.conversation_message_id,
                        message="Не удалось исключить ни одного пользователя из ЧСБ.",
                        keyboard=None
                    )
                except:
                    pass
                return True

            kicked_users = ""
            i = 1
            for user_ban in blacklisted:
                user_ban_id = user_ban[0]
                try:
                    await bot.api.messages.remove_chat_user(chat_id=chat_id, member_id=user_ban_id)
                    kicked_users += f"{i}. @id{user_ban_id} ({await get_user_name(user_ban_id, chat_id)})\n"
                    i += 1
                except:
                    pass  # если не удалось кикнуть — пропускаем

            # Убираем кнопку из исходного сообщения
            try:
                await bot.api.messages.edit(
                    peer_id=message.peer_id,
                    conversation_message_id=message.conversation_message_id,
                    message="Удаление пользователей в ЧСБ, завершено...",
                    keyboard=None
                )
            except:
                pass

            # Отправляем отчёт, если кого-то реально исключили
            if kicked_users:
                await bot.api.messages.send(
                    peer_id=message.peer_id,
                    random_id=0,
                    message=(
                        f"@id{user_id} ({await get_user_name(user_id, chat_id)}), "
                        f"исключил(-а) пользователей в ЧСБ:\n\n{kicked_users}"
                    ),
                    disable_mentions=1
                )
            else:
                await bot.api.messages.send(
                    peer_id=message.peer_id,
                    random_id=0,
                    message="Не удалось исключить ни одного пользователя из ЧСБ.",
                    disable_mentions=1
                )

            return True            

    if command == "infoidminus":
        page = payload.get("page")
        target = payload.get("user")

        if await get_role(user_id, chat_id) < 10:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        if page < 2:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это первая страница!"})
            )
            return True

        sql.execute("SELECT chat_id FROM chats WHERE owner_id = ?", (target,))
        user_chats = sql.fetchall()
        per_page = 5
        start = (page - 2) * per_page
        end = start + per_page
        page_chats = user_chats[start:end]

        all_chats = []
        for idx, (chat_id_val,) in enumerate(page_chats, start=1):
            try:
                peer_id = 2000000000 + chat_id_val
                info = await bot.api.messages.get_conversations_by_id(peer_ids=peer_id)
                if info.items:
                    chat_title = info.items[0].chat_settings.title
                else:
                    chat_title = "Без названия"
                link = (await bot.api.messages.get_invite_link(peer_id=peer_id, reset=0)).link
            except:
                chat_title = "Не удалось получить"
                link = "Не удалось получить"

            all_chats.append(f"{idx}. {chat_title} | 🆔: {chat_id_val} | 🔗 Ссылка: {link}")

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("Назад", {"command": "infoidMinus", "page": page - 1, "user": target}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("Вперёд", {"command": "infoidPlus", "page": page - 1, "user": target}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        all_chats_text = "\n".join(all_chats)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"❗ Список бесед @id{target} (пользователя):\n(Страница: {page - 1})\n\n{all_chats_text}\n\n🗨️ Всего бесед у пользователя: {idx}",
            random_id=0,
            disable_mentions=1,
            keyboard=keyboard
        )
        
    if command == "infoidplus":
        page = payload.get("page")
        target = payload.get("user")

        if await get_role(user_id, chat_id) < 10:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        sql.execute("SELECT chat_id FROM chats WHERE owner_id = ?", (target,))
        user_chats = sql.fetchall()
        per_page = 5
        total_pages = (len(user_chats) + per_page - 1) // per_page

        if page >= total_pages:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Это последняя страница!"})
            )
            return True

        start = page * per_page
        end = start + per_page
        page_chats = user_chats[start:end]

        all_chats = []
        for idx, (chat_id_val,) in enumerate(page_chats, start=1):
            try:
                peer_id = 2000000000 + chat_id_val
                info = await bot.api.messages.get_conversations_by_id(peer_ids=peer_id)
                if info.items:
                    chat_title = info.items[0].chat_settings.title
                else:
                    chat_title = "Без названия"
                link = (await bot.api.messages.get_invite_link(peer_id=peer_id, reset=0)).link
            except:
                chat_title = "Не удалось получить"
                link = "Не удалось получить"

            all_chats.append(f"{idx}. {chat_title} | 🆔: {chat_id_val} | 🔗 Ссылка: {link}")

        keyboard = (
            Keyboard(inline=True)
            .add(Callback("Назад", {"command": "infoidMinus", "page": page + 1, "user": target}), color=KeyboardButtonColor.NEGATIVE)
            .add(Callback("Вперёд", {"command": "infoidPlus", "page": page + 1, "user": target}), color=KeyboardButtonColor.POSITIVE)
        )

        await delete_message(message.group_id, message.object.peer_id, message.object.conversation_message_id)
        all_chats_text = "\n".join(all_chats)
        await bot.api.messages.send(
            peer_id=message.object.peer_id,
            message=f"❗ Список бесед @id{target} (пользователя):\n(Страница: {page + 1})\n\n{all_chats_text}\n\nВсего бесед: {idx}",
            random_id=0,
            disable_mentions=1,
            keyboard=keyboard
        )        
              
    if command == "alt":
        if await get_role(user_id, chat_id) < 1:
            await bot.api.messages.send_message_event_answer(
                event_id=message.object.event_id,
                peer_id=message.object.peer_id,
                user_id=message.object.user_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Недостаточно прав!"})
            )
            return True

        commands_levels = {
            1: [
                '\nКоманды модераторов:',
                '/setnick — snick, nick, addnick, ник, сетник, аддник',
                '/removenick —  removenick, clearnick, cnick, рник, удалитьник, снятьник',
                '/getnick — gnick, гник, гетник',
                '/getacc — acc, гетакк, аккаунт, account',
                '/nlist — ники, всеники, nlist, nickslist, nicklist, nicks',
                '/nonick — nonicks, nonicklist, nolist, nnlist, безников, ноникс',
                '/kick — кик, исключить',
                '/warn — пред, варн, pred, предупреждение',
                '/unwarn — унварн, анварн, снятьпред, минуспред',
                '/getwarn — gwarn, getwarns, гетварн, гварн',
                '/warnhistory — historywarns, whistory, историяварнов, историяпредов',
                '/warnlist — warns, wlist, варны, варнлист',
                '/staff — стафф',
                '/reg — registration, regdate, рег, регистрация, датарегистрации',
                '/mute — мут, мьют, муте, addmute',
                '/unmute — снятьмут, анмут, унмут, снятьмут',
                '/alt — альт, альтернативные',
                '/getmute -- gmute, гмут, гетмут, чекмут',
                '/mutelist -- mutes, муты, мутлист',
                '/clear -- чистка, очистить, очистка',
                '/getban -- чекбан, гетбан, checkban',
                '/delete -- удалить',
                '/chatid -- чатайди, айдичата'
            ],
            2: [
                '\nКоманды старших модераторов:',
                '/ban — бан, блокировка',
                '/unban -- унбан, снятьбан',
                '/addmoder -- moder',
                '/removerole -- rrole, снятьроль',
                '/zov - зов, вызов',
                '/online - ozov, озов',
                '/onlinelist - olist, олист',
                '/banlist - bans, банлист, баны',
                '/inactive - ilist, inactive',
                '/masskick - mkick'
            ],
            3: [
                '\nКоманды администраторов:',
                '/quiet -- silence, тишина',
                '/skick -- скик, снят',
                '/sban -- сбан',
                '/sunban — сунбан, санбан',
                '/addsenmoder — senmoder',
                '/rnickall -- allrnick, arnick, mrnick',
                '/sremovenick -- srnick',
                '/szov -- serverzov, сзов',
                '/srole -- none',
                '/ssetnick -- ssnick, ссник'
            ],
            4: [
                '\nКоманды старших администраторов:',
                '/addadmin -- admin',
                '/serverinfo -- серверинфо',
                '/filter -- none',
                '/sremoverole -- srrole',
                '/bug -- баг',
                '/report -- реп, rep, жалоба'
            ],
            5: [
                '\nКоманды зам. спец. администраторов:',
                '/addsenadmin -- senadm, addsenadm, senadmin',
                '/sync -- синхронизация, сунс, синхронка',
                '/pin -- закрепить, пин',
                '/unpin -- открепить, унпин',
                '/deleteall -- удалитьвсе',
                '/gsinfo -- none',
                '/gsrnick -- none',
                '/gssnick -- none',
                '/gskick -- none',
                '/gsban -- none',
                '/gsunban -- none'
            ],
            6: [
                '\nКоманды спец. администраторов:',
                '/addzsa -- zsa, зса',
                '/server -- сервер',
                '/settings -- настройки',
                '/clearwarn -- очиститьварны',
                '/title -- none',
                '/antisliv -- антислив'
            ],
            7: [
                '\nСписок команд владельца беседы',
                '/addsa -- sa, са, spec, specadm',
                '/antiflood -- af',
                '/welcometext -- welcome, wtext',
                '/invite -- none',
                '/leave -- none',
                '/editowner -- owner',
                '/защита -- protection',
                '/settingsmute -- настройкимута',
                '/setinfo -- установитьинфо',
                '/setrules -- установитьправила',
                '/type -- тип',
                '/gsync -- привязка',
                '/gunsync -- удалитьпривязку'
            ]
        }

        user_role = await get_role(user_id, chat_id)

        commands = []
        for i in commands_levels.keys():
            if i <= user_role:
                for b in commands_levels[i]:
                    commands.append(b)

        level_commands = '\n'.join(commands)

        await bot.api.messages.edit(peer_id=2000000000 + chat_id, message=f"Альтернативные команды\n\n{level_commands}",
                                    conversation_message_id=message.object.conversation_message_id, keyboard=None)
                                                                       
@bot.on.chat_message()
async def on_chat_message(message: Message):
    bot_identifiers = ['!', '+', '/']

    user_id = message.from_id
    chat_id = message.chat_id
    peer_id = message.peer_id
    arguments = message.text.split(' ')
    arguments_lower = message.text.lower().split(' ')

    # --- Проверка на бан чата до всего остального ---
    sql.execute("SELECT chat_id FROM banschats WHERE chat_id = ?", (chat_id,))
    if sql.fetchone():
        await message.reply("Владелец беседы, не член уже BLACK MANAGER! Я не буду здесь работать.")
        return True

    # --- Проверка, зарегистрирован ли чат ---
    is_registered = await check_chat(chat_id)

    # --- Проверка на запрещённые слова ---
    if is_registered and await get_role(user_id, chat_id) <= 0:
        try:
            sql.execute("SELECT word FROM ban_words")
            banned_words = [row[0].lower() for row in sql.fetchall()]
            text_lower = message.text.lower()
            for word in banned_words:
                if word in text_lower:
                    admin = "blackrussiamanagerbot"
                    reason = "Написание запрещенных слов"
                    mute_time = 30

                    await add_mute(user_id, chat_id, admin, reason, mute_time)

                    keyboard = (
                        Keyboard(inline=True)
                        .add(Callback("Снять мут", {"command": "unmute", "user": user_id, "chatId": chat_id}), color=KeyboardButtonColor.POSITIVE)
                    )

                    await message.reply(
                        f"❗ @id{user_id} (Пользователь), вы получили мут на 30 минут за написание запрещенных слов!",
                        disable_mentions=1,
                        keyboard=keyboard
                    )

                    await bot.api.messages.delete(
                        group_id=message.group_id,
                        peer_id=message.peer_id,
                        delete_for_all=True,
                        cmids=message.conversation_message_id
                    )
                    return True
        except Exception as e:
            print(f"[BANWORDS] Ошибка проверки слов: {e}")            

    # --- Проверка мута и реакции в зависимости от настроек (только если чат активирован) ---
    if is_registered and await get_mute(user_id, chat_id) and not await checkMute(chat_id, user_id):
        sql.execute("SELECT mode FROM mutesettings WHERE chat_id = ?", (chat_id,))
        mode_data = sql.fetchone()
        mode = mode_data[0] if mode_data else 0

        warns = await get_warns(user_id, chat_id)

        if mode == 1:
            if warns < 3:
                bot_name = "blackrussiamanagerbot"
                reason = "Написание слов в муте"
                await warn(chat_id, user_id, bot_name, reason)
                await message.reply(
                    f"В данном чате запрещено отправлять сообщения во время мута.\n"
                    f"@id{user_id} ({await get_user_name(user_id, chat_id)}), вам выдано предупреждение «{warns}/3»\n\n"
                    f"При достижении 3/3 предупреждений вы будете исключены.",
                    disable_mentions=1
                )
                await bot.api.messages.delete(
                    group_id=message.group_id,
                    peer_id=message.peer_id,
                    delete_for_all=True,
                    cmids=message.conversation_message_id
                )
            else:
                try:
                    await bot.api.messages.remove_chat_user(chat_id, user_id)
                    await message.reply(
                        f"@id{user_id} ({await get_user_name(user_id, chat_id)}) был исключен за превышение лимита предупреждений!",
                        disable_mentions=1
                    )
                    await clear_warns(chat_id, user_id)
                except:
                    await message.reply(
                        f"Не удалось исключить пользователя @id{user_id}. Возможно, нет прав администратора.",
                        disable_mentions=1
                    )
        else:
            await bot.api.messages.delete(
                group_id=message.group_id,
                peer_id=message.peer_id,
                delete_for_all=True,
                cmids=message.conversation_message_id
            )

    # --- Проверка на наличие заблокированных пользователей (только если чат активирован) ---
    if is_registered:
        sql.execute("SELECT user_id, moderator_id, reason_gban FROM blacklist")
        blacklisted = sql.fetchall()

        if any(user_id == b[0] for b in blacklisted):
            users = ""
            i = 1
            for user_ban in blacklisted:
                user_ban_id, moderator, reason = user_ban
                users += f"\n{i}. @id{user_ban_id} ({await get_user_name(user_ban_id, chat_id)}) | " \
                         f"@id{moderator} (Модератор) | Причина: {reason}\n"
                i += 1

            chat_info = await bot.api.messages.get_conversations_by_id(peer_ids=message.peer_id)
            chat_title = chat_info.items[0].chat_settings.title if chat_info.items else "Неизвестная беседа"

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("Исключить всех заблокированных", {"command": "kick_blacklisted", "chatId": chat_id}),
                     color=KeyboardButtonColor.NEGATIVE)
            )

            await message.reply(
                f"В чате «{chat_title}» находятся заблокированные пользователи.\n\n"
                f"❗ | Список всех пользователей в черном списке бота:\n{users}\n\n"
                f"Рекомендуем исключить пользователей из беседы, так как они нарушили правила использования бота.",
                disable_mentions=1,
                keyboard=keyboard
            )
            return True

    # --- Теперь обрабатываем команды (команды доступны всегда) ---
    try:
        command_identifier = arguments[0].strip()[0]
        command = arguments_lower[0][1:]
    except:
        command_identifier = " "
        command = " "

    if command_identifier in bot_identifiers:
        try:
            test_admin = await bot.api.messages.get_conversation_members(peer_id=message.peer_id)
        except:
            await message.reply("Ожидаю выдачи звёздочки чтобы начать работу с чатом!", disable_mentions=1)
            return True

        # --- Если чат не активирован, разрешаем только /start ---
        if not is_registered and command not in ['start', 'старт', 'активировать']:
            await message.reply("⚠️ Сначала активируйте чат при помощи команды /start", disable_mentions=1)
            return True

        # ==== Проверка глобального бана ====
        if is_registered:
            sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (user_id,))
            check_global = sql.fetchone()
            if check_global:
                moderator_id = check_global[1]
                reason_gban = check_global[2]
                datetime_globalban = check_global[3]

                try:
                    resp = await bot.api.users.get(user_ids=user_id)
                    full_name = f"{resp[0].first_name} {resp[0].last_name}"
                except:
                    full_name = str(user_id)

                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Снять бан", {}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                    f"@id{user_id} ({full_name}) заблокирован(-а) в беседах игроков!\n\n"
                    f"Информация о блокировке:\n@id{moderator_id} (Модератор) | {reason_gban} | {datetime_globalban}",
                    disable_mentions=1,
                    keyboard=keyboard
                )
                await bot.api.messages.remove_chat_user(chat_id, user_id)
                return True
                
        # ==== Проверка глобального бана ====
        if is_registered:
            sql.execute("SELECT * FROM globalban WHERE user_id = ?", (user_id,))
            check_global = sql.fetchone()
            if check_global:
                moderator_id = check_global[1]
                reason_gban = check_global[2]
                datetime_globalban = check_global[3]

                try:
                    resp = await bot.api.users.get(user_ids=user_id)
                    full_name = f"{resp[0].first_name} {resp[0].last_name}"
                except:
                    full_name = str(user_id)

                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Снять бан", {}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                    f"@id{user_id} ({full_name}) заблокирован(-а) во всех беседах!\n\n"
                    f"Информация о блокировке:\n@id{moderator_id} (Модератор) | {reason_gban} | {datetime_globalban}",
                    disable_mentions=1,
                    keyboard=keyboard
                )
                await bot.api.messages.remove_chat_user(chat_id, user_id)
                return True                
                                        
        if command in ['start', 'старт', 'активировать']:
            if await check_chat(chat_id):
                await message.reply("Бот был ранее активирован в данной беседе!", disable_mentions=1)
                return True
            await new_chat(chat_id, peer_id, user_id)
            await message.reply("Беседа успешно занесена в базу данных бота!\n\nИспользуйте «/help» для ознакомления списка команд!", disable_mentions=1)
            return True  

        # ---------------- FORM ----------------
        if command in ["form", "форма"]:
            if chat_id != 9:
                await message.reply(
                    "❗ Команда доступна только [https://vk.me/join/Am_qZQ/ppZ90u1wU6Zrd5w0vJKGFKpN1M0M=|в формах на блокировку]"
                )
                return True

            # Определяем target
            target = None
            reason = "Не указано"
            if message.reply_message:
                target = message.reply_message.from_id
                if len(arguments) > 1:
                    reason = await get_string(arguments, 1)
            elif len(arguments) > 1 and await getID(arguments[1]):
                target = await getID(arguments[1])
                if len(arguments) > 2:
                    reason = await get_string(arguments, 2)
            else:
                await message.reply("Укажите пользователя через реплай или ID!")
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете подать форму на пользователя выше вас рангом!", disable_mentions=1)
                return True

            sender_name = await get_user_name(user_id, chat_id)
            target_name = await get_user_name(target, chat_id)
            name = datetime.now().strftime("%I:%M:%S %p")

            # Клавиатура с кнопками
            keyboard = (
                Keyboard(inline=True)
                .add(
                    Callback(
                        "Одобрить",
                        {"command": "approve_form", "target": target, "sender": user_id, "reason": reason},
                    ),
                    color=KeyboardButtonColor.POSITIVE,
                )
                .add(
                    Callback(
                        "Отказать",
                        {"command": "reject_form", "target": target, "sender": user_id, "reason": reason},
                    ),
                    color=KeyboardButtonColor.NEGATIVE,
                )
            )

            # Отправляем сообщение прямо в чат, откуда пришла команда
            await message.reply(
                (
                    f"📌 | Форма на «/gbanpl»:\n"
                    f"1. Пользователь: @id{user_id} ({sender_name})\n"
                    f"2. Нарушитель: @id{target} ({target_name})\n"
                    f"3. Причина: {reason}\n"
                    f"4. Дата подачи формы: {name} МСК (UTC+3)"
                ),
                keyboard=keyboard,
            )
            return True            

        if command in ['id', 'ид', 'getid', 'гетид', 'получитьид', 'giveid']:
            user = int
            if message.reply_message:
                user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                user = user_id
            if user < 0:
                await message.reply(f"Оригинальная ссылка [club{abs(user)}|сообщества]:\nhttps://vk.com/club{abs(user)}",disable_mentions=1)
                return True
            await message.reply(f"Оригинальная ссылка @id{user} (пользователя):\nhttps://vk.com/id{user}", disable_mentions=1)

        if message.reply_message and message.reply_message.from_id < 0:
            return True
            
        if command in ['минет', 'отсос', 'отсосать', 'minet', 'сосать']:
            if message.reply_message:
                user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                user = user_id

            # Получаем имя цели
            try:
                info = await bot.api.users.get(user_ids=user)
                name_target = f"{info[0].first_name} {info[0].last_name}"
            except:
                if user < 0:
                    name_target = f"@club{abs(user)} (Не удалось получить имя)"
                else:
                    name_target = f"@id{user} (Не удалось получить имя)"

            # Получаем имя инициатора
            try:
                info = await bot.api.users.get(user_ids=user_id)
                name = f"{info[0].first_name} {info[0].last_name}"
            except:
                name = f"@id{user_id} (Не удалось получить имя)"

            if user < 0:
                await message.reply(
                    f"🔞 | @id{user_id} ({name}) отсосал(-а) у @club{abs(user)} ({name_target})",
                    disable_mentions=1
                )
            else:
                await message.reply(
                    f"🔞 | @id{user_id} ({name}) отсосал(-а) у @id{user} ({name_target})",
                    disable_mentions=1
                )
            return True
      
        if command in ['трахнуть', 'секс', 'seks', 'трах', 'trax']:
            if message.reply_message:
                user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                user = user_id

            # Получаем имя цели
            try:
                info = await bot.api.users.get(user_ids=user)
                name_target = f"{info[0].first_name} {info[0].last_name}"
            except:
                if user < 0:
                    name_target = f"@club{abs(user)} (Не удалось получить имя)"
                else:
                    name_target = f"@id{user} (Не удалось получить имя)"

            # Получаем имя инициатора
            try:
                info = await bot.api.users.get(user_ids=user_id)
                name = f"{info[0].first_name} {info[0].last_name}"
            except:
                name = f"@id{user_id} (Не удалось получить имя)"

            if user < 0:
                await message.reply(
                    f"🔞 | @id{user_id} ({name}) принудил(-а) к интиму @club{abs(user)} ({name_target})",
                    disable_mentions=1
                )
            else:
                await message.reply(
                    f"🔞 | @id{user_id} ({name}) принудил(-а) к интиму @id{user} ({name_target})",
                    disable_mentions=1
                )
            return True      

        # ---------------- OFFER ----------------
        if command in ["offer", "предложение"]:
            try:
                user_info = await bot.api.users.get(user_ids=user_id)
                full_name = f"{user_info[0].first_name} {user_info[0].last_name}"
            except:
                full_name = f"id{user_id} (Ошибка)"

            args = message.text.split(maxsplit=1)
            if len(arguments) < 2 or len(args[1]) < 5:
                await message.reply("Укажите предложение по улучшению!")
                return

            offer = args[1]

            ADMIN_ID = 860294414

            await bot.api.messages.send(
                peer_id=2000000017,
                random_id=0,
                message=(
                    f"⭐ | Предложение по улучшению бота:\n"
                    f"1. Пользователь: [id{user_id}|{full_name}]\n"
                    f"2. Предложение по улучшению: {offer}\n"
                    f"3. Дата подачи улучшения: NULL"
                )
            )
            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"подал(-а) предложение по улучшению с содержанием: «{offer}»")            
            await message.reply("Спасибо за предложение по улучшению бота! Мы обязательно рассмотрим ваше предложение.")
            return

        if command in ['логэкономики', 'logeco', 'logeconomy', 'логиэко']:
            if await get_role(user_id, chat_id) < 8:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            target = None
            if message.reply_message:
                target = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])

            if target:
                # --- Логи конкретного пользователя ---
                sql.execute("SELECT * FROM economy WHERE user_id = ? ORDER BY rowid DESC LIMIT 9999999999999", (target,))
                logs = sql.fetchall()

                if not logs:
                    await message.reply(f"У @id{target} ({await get_user_name(target, chat_id)}) отсутствуют записи в логах экономики.", disable_mentions=1)
                    return True

                economy_text = ""
                i = 0
                for entry in logs:
                    i += 1
                    u_id, t_id, amount, log_text = entry

                    try:
                        u_info = await bot.api.users.get(user_ids=u_id)
                        u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                    except:
                        u_name = str(u_id)

                    if t_id:
                        try:
                            t_info = await bot.api.users.get(user_ids=t_id)
                            t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                            t_display = f"@id{t_id} ({t_name})"
                        except:
                            t_display = f"@id{t_id}"
                    else:
                        t_display = "None"

                    a_display = f"{format_number(amount)}$" if amount else "None"
                    l_display = log_text if log_text else "—"

                    economy_text += f"{i}. @id{u_id} ({u_name}) | Кому: {t_display} | Сколько: {a_display} | Лог: {l_display}\n\n"

                await message.reply(
                    f"Список действий с экономикой @id{target} ({await get_user_name(target, chat_id)}):\n\n{economy_text}",
                    disable_mentions=1
                )
                return True

            else:
                # --- Общие логи экономики ---
                sql.execute("SELECT * FROM economy ORDER BY rowid DESC LIMIT 9999999999999")
                logs = sql.fetchall()

                if not logs:
                    await message.reply(f"Логи экономики отсутствуют!", disable_mentions=1)
                    return True

                economy_text = ""
                i = 0
                for entry in logs:
                    i += 1
                    u_id, t_id, amount, log_text = entry

                    try:
                        u_info = await bot.api.users.get(user_ids=u_id)
                        u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                    except:
                        u_name = str(u_id)

                    if t_id:
                        try:
                            t_info = await bot.api.users.get(user_ids=t_id)
                            t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                            t_display = f"@id{t_id} ({t_name})"
                        except:
                            t_display = f"@id{t_id}"
                    else:
                        t_display = "None"

                    a_display = f"{format_number(amount)}$" if amount else "None"
                    l_display = log_text if log_text else "—"

                    economy_text += f"{i}. @id{u_id} ({u_name}) | Кому: {t_display} | Сколько: {a_display} | Лог: {l_display}\n\n"

                await message.reply(
                    f"@id{user_id} ({await get_user_name(user_id, chat_id)}), логирование общей экономики бота:\n\n{economy_text}",
                    disable_mentions=1
                )
                return True

        # === Добавление в Чёрный список ===
        if command in ['addblack', 'блеклист', 'чс', 'blackadd', 'addch']:
            if await get_role(user_id, chat_id) < 10:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            if chat_id == 23:
                await message.reply("Данная беседа проводится в специализированном чате, который предназначен исключительно для тестировщиков бота.\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
                return True

            # Определяем пользователя
            target = int
            arg = 0
            if message.reply_message:
                target = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                target = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])
                arg = 2
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            # Проверка — не в ЧС ли уже
            sql.execute("SELECT * FROM blacklist WHERE user_id = ?", (target,))
            if sql.fetchone():
                await message.reply("Данный пользователь уже находится в черном списке бота!", disable_mentions=1)
                return True

            if await equals_roles(user_id, target, chat_id, message) < 2:
                await message.reply("Вы не можете добавить данного пользователя в ЧС!", disable_mentions=1)
                return True

            reason = await get_string(arguments, arg)
            if not reason:
                await message.reply("Укажите причину блокировки!", disable_mentions=1)
                return True

            date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            sql.execute("INSERT INTO blacklist (user_id, moderator_id, reason_gban, datetime_globalban) VALUES (?, ?, ?, ?)",
                        (target, user_id, reason, date_now))
            database.commit()

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) добавил @id{target} ({await get_user_name(target, chat_id)}) в черный список бота", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=target, role=None, log=f"добавил @id{target} (пользователя) в Чёрный список. Причина: {reason}")            
            return True


        # === Удаление из Чёрного списка ===
        if command in ['unblack', 'убратьчс', 'blackdel', 'unch']:
            if await get_role(user_id, chat_id) < 10:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            if chat_id == 23:
                await message.reply("Данная беседа проводится в специализированном чате, который предназначен исключительно для тестировщиков бота.\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
                return True

            target = int
            if message.reply_message:
                target = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                target = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            sql.execute("SELECT * FROM blacklist WHERE user_id = ?", (target,))
            if not sql.fetchone():
                await message.reply("Данный пользователь не находится в черном списке бота!", disable_mentions=1)
                return True

            sql.execute("DELETE FROM blacklist WHERE user_id = ?", (target,))
            database.commit()

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) удалил @id{target} ({await get_user_name(target, chat_id)}) из черного списка бота!", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=target, role=None, log=f"удалил @id{target} (пользователя) из Чёрного списка")            
            return True           
                
        if command in ['логиобщие', 'logs', 'logsmoders', 'логи']:
            if await get_role(user_id, chat_id) < 8:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            target = None
            if message.reply_message:
                target = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])

            if target:
                # --- Логи конкретного пользователя ---
                sql.execute("SELECT * FROM logchats WHERE user_id = ? ORDER BY rowid DESC LIMIT 9999999999999", (target,))
                logs = sql.fetchall()

                if not logs:
                    await message.reply(f"У @id{target} ({await get_user_name(target, chat_id)}) отсутствуют записи в логах модерации.", disable_mentions=1)
                    return True

                economy_text = ""
                i = 0
                for entry in logs:
                    i += 1
                    u_id, t_id, amount, log_text = entry

                    try:
                        u_info = await bot.api.users.get(user_ids=u_id)
                        u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                    except:
                        u_name = str(u_id)

                    if t_id:
                        try:
                            t_info = await bot.api.users.get(user_ids=t_id)
                            t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                            t_display = f"@id{t_id} ({t_name})"
                        except:
                            t_display = f"@id{t_id}"
                    else:
                        t_display = "None"

                    a_display = f"{format_number(amount)}$" if amount else "None"
                    l_display = log_text if log_text else "—"

                    economy_text += f"{i}. @id{u_id} ({u_name}) | Кому: {t_display} | Роль: {a_display} | Лог: {l_display}\n\n"

                await message.reply(
                    f"Список действий с действиями модераторов @id{target} ({await get_user_name(target, chat_id)}):\n\n{economy_text}",
                    disable_mentions=1
                )
                return True

            else:
                # --- Общие логи экономики ---
                sql.execute("SELECT * FROM logchats ORDER BY rowid DESC LIMIT 9999999999999")
                logs = sql.fetchall()

                if not logs:
                    await message.reply(f"Логи с действиями модераторов отсутствуют!", disable_mentions=1)
                    return True

                economy_text = ""
                i = 0
                for entry in logs:
                    i += 1
                    u_id, t_id, amount, log_text = entry

                    try:
                        u_info = await bot.api.users.get(user_ids=u_id)
                        u_name = f"{u_info[0].first_name} {u_info[0].last_name}"
                    except:
                        u_name = str(u_id)

                    if t_id:
                        try:
                            t_info = await bot.api.users.get(user_ids=t_id)
                            t_name = f"{t_info[0].first_name} {t_info[0].last_name}"
                            t_display = f"@id{t_id} ({t_name})"
                        except:
                            t_display = f"@id{t_id}"
                    else:
                        t_display = "None"

                    a_display = f"{format_number(amount)}$" if amount else "None"
                    l_display = log_text if log_text else "—"

                    economy_text += f"{i}. @id{u_id} ({u_name}) | Кому: {t_display} | Роль: {a_display} | Лог: {l_display}\n\n"

                await message.reply(
                    f"@id{user_id} ({await get_user_name(user_id, chat_id)}), логирование общих действий модераторов:\n\n{economy_text}",
                    disable_mentions=1
                )
                return True
                            
        if command in ["casino", "казино"]:
            if len(arguments) < 1:
                await message.reply("🎰 Укажи сумму ставки: /казино 10000")
                return

            try:
                stake = int(arguments[-1])
            except:
                await message.reply("Ставка должна быть числом!")
                return

            if stake < 100:
                await message.reply("Минимальная ставка должна быть — 10$")
                return

            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(user_id), get_balance(user_id))

            if bal["wallet"] < stake:
                await message.reply("Недостаточно средств для ставки!")
                return

            # Эмодзи рулетки
            emojis = ["💎", "🍒", "🍀", "🪙", "🔔", "🍋", "💰", "⭐️", "🔥", "🎲"]

            # Генерация случайных трёх эмодзи
            result = random.choices(emojis, k=3)

            # Проверка на джекпот
            jackpot = False
            if result[0] == result[1] == result[2]:
                jackpot = True

            # Подсчитываем бонусы
            multiplier = 0.0
            bonuses = {
                "💎": 0.3,  # 30%
                "🪙": 0.1,  # 10%
                "🔔": 0.5   # 50%
            }

            triggered = []
            for emoji, bonus in bonuses.items():
                if emoji in result:
                    multiplier += bonus
                    triggered.append(emoji)

            # Базовый выигрыш / проигрыш
            if multiplier == 0 and not jackpot:
                # Проигрыш
                bal["wallet"] -= stake
                balances[str(user_id)] = bal
                save_data(BALANCES_FILE, balances)

                await message.reply(
                    f"🎰 Вы сыграли на ставку «{format_number(stake)}»\n"
                    f"Результат: {' '.join(result)}\n\n"
                    f"❌ Не выпали 💎, 🪙 или 🔔 — вы проиграли!"
                )
                return
            else:
                win_amount = stake

                if multiplier > 0:
                    win_amount = int(stake * (1 + multiplier))

                # Если джекпот — утроить выигрыш
                if jackpot:
                    win_amount = int(win_amount * 3)

                profit = win_amount - stake
                bal["wallet"] -= stake
                bal["wallet"] += win_amount
                balances[str(user_id)] = bal
                save_data(BALANCES_FILE, balances)
                await log_economy(user_id=user_id, target_id=None, amount=stake, log=f"сыграл(-а) в «Казино» на {stake}$")

                emoji_str = ", ".join(triggered) if triggered else "нет"
                jackpot_text = ""
                if jackpot:
                    jackpot_text = f"\n\n❗ JECKPOT! 3 одинаковых {result[0]} 🔥🔥🔥"

                await message.reply(
                    f"🎰 Вы сыграли на ставку «{format_number(stake)}»\n"
                    f"Результат: {' '.join(result)}{jackpot_text}\n\n"
                    f"Выпали: {emoji_str}\n"
                    f"📈 Общий бонус: +{int(multiplier * 100)}%\n"
                    f"💰 Выигрыш: {format_number(win_amount)}$ (прибыль: {format_number(profit)}$)"
                )
                return            
            
        # ---------------- BUG ----------------
        if command in ["bug", "баг"]:
            if await get_role(user_id, chat_id) < 4:
                await message.reply("Недостаточно прав!")
                return True
        	
            try:
                user_info = await bot.api.users.get(user_ids=user_id)
                full_name = f"{user_info[0].first_name} {user_info[0].last_name}"
            except:
                full_name = f"id{user_id} (Ошибка)"

            args = message.text.split(maxsplit=1)
            if len(arguments) < 2 or len(args[1]) < 5:
                await message.reply("Слишком короткий баг!")
                return

            offer = args[1]

            ADMIN_ID = 860294414

            await bot.api.messages.send(
                peer_id=2000000017,
                random_id=0,
                message=(
                    f"👾 | Баг-трекер:\n"
                    f"1. Пользователь: [id{user_id}|{full_name}]\n"
                    f"2. Содержимое бага: {offer}\n"
                    f"3. Дата подачи бага: NULL"
                )
            )
            
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"подал(-а) баг-репорт с содержанием: «{offer}»")            
            await message.reply("Ваш баг репорт был отправлен разработчику!")
            return            

        if command in ['stats', 'стата', 'статистика', 'stata', 'statistic']:
                # Определяем пользователя для показа статистики
                user = int
                if message.reply_message:
                    user = message.reply_message.from_id
                elif len(arguments) >= 2 and await getID(arguments[1]):
                    user = await getID(arguments[1])
                else:
                    user = user_id

                if user < 0:
                    await message.reply("Нельзя взаимодействовать с сообществом!")
                    return True

                reg_data = "-"  # вместо даты регистрации
                role = await get_role(user, chat_id)
                warns = await get_warns(user, chat_id)

                # Получаем ник
                if await is_nick(user, chat_id):
                    nick = await get_user_name(user, chat_id)
                else:
                    nick = "Нет"

                # Получаем имя и фамилию через VK
                try:
                    info = await bot.api.users.get(user_ids=user)
                    name = f"{info[0].first_name} {info[0].last_name}"
                except:
                    name = f"@id{user} (Не удалось получить имя)"

                messages = await message_stats(user, chat_id)

                # Проверка глобального бана
                sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (user,))
                gban = sql.fetchone()
                gban_status = "Да" if gban else "Нет"

                # Проверка глобального бана 2
                sql.execute("SELECT * FROM globalban WHERE user_id = ?", (user,))
                gban2 = sql.fetchone()
                globalban = "Да" if gban2 else "Нет"

                # Проверяем, есть ли мут
                sql.execute(f"SELECT * FROM mutes_{chat_id} WHERE user_id = ?", (user,))
                mute = sql.fetchone()
                mute_status = "Да" if mute else "Нет"

                # --- Проверка банов во всех чатах ---
                sql.execute("SELECT chat_id FROM chats")
                chats_list = sql.fetchall()
                bans = ""
                bans_count = 0
                i = 1
                for c in chats_list:
                    chat_id_check = c[0]
                    try:
                        sql.execute(f"SELECT moder, reason, date FROM bans_{chat_id_check} WHERE user_id = ?", (user,))
                        user_bans = sql.fetchall()
                        if user_bans:
                            bans_count += len(user_bans)
                            for ub in user_bans:
                                mod, reason, date = ub
                                bans += f"{i}) @id{mod} (Модератор) | {reason} | {date} МСК (UTC+3)\n"
                                i += 1
                    except:
                        continue  # если таблицы нет, пропускаем

                roles = {
                    0: "Пользователь",
                    1: "Модератор",
                    2: "Старший модератор",
                    3: "Администратор",
                    4: "Старший администратор",
                    5: "Зам. спец администратора",
                    6: "Спец администратор",
                    7: "Владелец беседы",
                    8: "Заместитель руководителя",
                    9: "Основной зам. руководителя",
                    10: "Специальный руководитель",
                    11: "Разработчик бота",
                    12: "👾 Тестировщик бота",
                    13: "👾 Зам. главного тестировщика бота",
                    14: "👾 Главный тестировщик бота"
                }

                # Создаём клавиатуру только если роль > 1
                keyboard = None
                if await get_role(user_id, chat_id) > 1:
                    keyboard = Keyboard(inline=True)
                    keyboard.add(
                        Callback("Все предупреждения", {"command": "activeWarns", "user": user, "chatId": chat_id}),
                        color=KeyboardButtonColor.PRIMARY
                    )
                    keyboard.add(
                        Callback("Информация о блокировках", {"command": "getban", "user": user, "chatId": chat_id}),
                        color=KeyboardButtonColor.PRIMARY
                    )

                await message.reply(
                    f"Информация о @id{user} (пользователе):\n"
                    f"Роль: {roles.get(role)}\n"
                    f"Блокировок: {bans_count}\n"
                    f"Общая блокировка в чатах: {globalban}\n"
                    f"Общая блокировка в беседах игроков: {gban_status}\n"
                    f"Активные предупреждения: {warns}\n"
                    f"Блокировка чата: {mute_status}\n"
                    f"Ник: {nick}\n"
                    f"Всего сообщений: {messages['count']}\n"
                    f"Последнее сообщение: {messages['last']}",
                    disable_mentions=1,
                    keyboard=keyboard
                )
                return True
                           
        if command in ["banid", "банчата"]:
            if await get_role(user_id, chat_id) < 10:
                await message.reply("Недостаточно прав!")
                return True

            if chat_id == 23:
                await message.reply("Данная беседа проводится в специализированном чате, который предназначен исключительно для тестировщиков бота.\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
                return True

            if len(arguments) < 2:
                await message.reply("Укажите чат!")
                return True

            try:
                target_chat = int(arguments[1])
            except:
                await message.reply("Укажите чат!")
                return True

            sql.execute("SELECT chat_id FROM banschats WHERE chat_id = ?", (target_chat,))
            if sql.fetchone():
                await message.reply("Беседа уже находится в блокировке!")
                return True

            sql.execute("INSERT INTO banschats (chat_id) VALUES (?)", (target_chat,))
            database.commit()
            
            target_peer = 2000000000 + target_chat
            await bot.api.messages.send(
                peer_id=target_peer,
                random_id=0,
                message=(
                    f"Владелец беседы — не член, уже BLACK MANAGER! Я не буду здесь работать."
                )
            )

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал(-а) беседу №«{target_chat}»")
            return True

        if command in ["unbanid", "разбанчата"]:
            if await get_role(user_id, chat_id) < 10:
                await message.reply("Недостаточно прав!")
                return True

            if chat_id == 23:
                await message.reply("Данная беседа проводится в специализированном чате, который предназначен исключительно для тестировщиков бота.\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
                return True

            if len(arguments) < 2:
                await message.reply("Укажите чат!")
                return True

            try:
                target_chat = int(arguments[-1])
            except:
                await message.reply("Укажите чат!")
                return True

            sql.execute("SELECT chat_id FROM banschats WHERE chat_id = ?", (target_chat,))
            if not sql.fetchone():
                await message.reply("Беседа и так находится в блокировке!")
                return True

            sql.execute("DELETE FROM banschats WHERE chat_id = ?", (target_chat,))
            database.commit()
            
            target_peer = 2000000000 + target_chat
            await bot.api.messages.send(
                peer_id=target_peer,
                random_id=0,
                message=(
                    f"Чат разблокирован в боте!"
                )
            )

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) разблокировал(-а) беседу №«{target_chat}»")
            return True

        if command in ['statstester', 'тестерстата', 'тестстата']:
            # Проверка: доступна только в чате тестеров
            if chat_id != 23:
                await message.reply("Данная команда доступна только в тестовом чате!", disable_mentions=1)
                return True

            # Проверка роли — только для тестеров и выше
            if await get_role(user_id, chat_id) < 12:
                await message.reply("Вы не являетесь тестировщиком бота!", disable_mentions=1)
                return True

            # Определяем пользователя для просмотра
            if message.reply_message:
                target = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                target = message.fwd_messages[0].from_id
            else:
                target = user_id

            if target < 0:
                await message.reply("Нельзя получить информацию о сообществе!", disable_mentions=1)
                return True

            # Проверка роли — только для тестеров и выше
            if await get_role(target, chat_id) < 12:
                await message.reply("🔹Указанный пользователь не тестировщик, статистика невозможна к рассмотрению!", disable_mentions=1)
                return True

            # Получаем роль
            role = await get_role(target, chat_id)

            # Проверка глобального бана
            sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (target,))
            gban = sql.fetchone()
            gban_status = "Да" if gban else "Нет"

            # Получаем количество багов
            sql.execute("SELECT COUNT(*) FROM bugsusers WHERE user_id = ?", (target,))
            bug_count = sql.fetchone()[0] or 0

            # Получаем имя и фамилию
            try:
                info = await bot.api.users.get(user_ids=target)
                name = f"{info[0].first_name} {info[0].last_name}"
            except:
                name = f"@id{target} (Не удалось получить имя)"

            # Все роли
            roles = {
                0: "Пользователь",
                1: "Модератор",
                2: "Старший модератор",
                3: "Администратор",
                4: "Старший администратор",
                5: "Зам. спец администратора",
                6: "Спец администратор",
                7: "Владелец беседы",
                8: "Зам. руководителя",
                9: "Основной зам. руководителя",
                10: "Специальный руководитель",
                11: "Разработчик бота",
                12: "👾 Тестировщик бота 👾",
                13: "👾 Зам. главного тестировщика 👾",
                14: "👾 Главный тестировщик 👾",
            }

            await message.reply(
                f"👾 Информация о @id{target} ({name}):\n\n"
                f"🔹 Роль: {roles.get(role, 'Неизвестно')}\n"
                f"🔹 Глобальная блокировка: {gban_status}\n"
                f"🔹 Всего подано багов: {bug_count}\n\n"
                f"🧩 Вы тестировщик, спасибо за большой вклад в развитие системы!",
                disable_mentions=1
            )
            return True            

        # === /bugcommand — отправка бага ===
        if command in ['bugcommand', 'багкоманда', 'багкмд', 'bugcmd', 'bagcmd']:
            # Проверка, что команда только в чате ID 23
            if chat_id != 23:
                await message.reply("Данная команда доступна только в официальном тестовом чате бота!", disable_mentions=1)
                return True

            # Проверка роли
            if await get_role(user_id, chat_id) < 12:
                await message.reply("Вы не являетесь тестировщиком бота!", disable_mentions=1)
                return True

            # Проверяем наличие текста бага
            bug_text = await get_string(arguments, 1)
            if not bug_text or len(bug_text) < 5:
                await message.reply("⚠️ Укажите описание бага (минимум 5 символов).", disable_mentions=1)
                return True

            # Получаем текущее количество багов пользователя
            sql.execute("SELECT COUNT(*) FROM bugsusers WHERE user_id = ?", (user_id,))
            bug_count = sql.fetchone()[0]

            # Формируем дату/время
            vremya = datetime.now().strftime("%d/%m/%Y %I:%M:%S %p")

            # Добавляем запись
            sql.execute("INSERT INTO bugsusers (user_id, bug, datetime, bug_counts_user) VALUES (?, ?, ?, ?)",
                        (user_id, bug_text, vremya, bug_count + 1))
            database.commit()

            # Отправляем уведомление разработчику (например, id = 123456789)
            dev_id = 860294414  # <-- сюда впиши свой VK ID
            await bot.api.messages.send(
                peer_id=dev_id,
                random_id=0,
                message=f"👾 | Новый баг-репорт команды от @id{user_id} ({await get_user_name(user_id, chat_id)}):\n\n{bug_text}\n\n🕒 {vremya}"
            )

            await message.reply(
                f"@id{user_id} ({await get_user_name(user_id, chat_id)}), Ваш баг принят!\n\n"
                f"Время подачи бага: {vremya}\n"
                f"Содержание бага — {bug_text}\n"
                f"Вы отправили уже — {bug_count + 1} баг(ов).",
                disable_mentions=1
            )
            return True


        # === /buglist — список всех багов ===
        if command in ['buglist', 'баглист', 'баги']:
            if chat_id != 23:
                await message.reply("Данная команда доступна только в тестовом чате!", disable_mentions=1)
                return True

            if await get_role(user_id, chat_id) < 12:
                await message.reply("У вас недостаточно прав для просмотра списка багов!", disable_mentions=1)
                return True

            # Получаем все баги пользователя
            sql.execute("SELECT datetime, bug, bug_counts_user FROM bugsusers WHERE user_id = ?", (user_id,))
            user_bugs = sql.fetchall()

            if not user_bugs:
                await message.reply("У вас пока нет подданых багов!", disable_mentions=1)
                return True

            # Формируем список
            bugs_text = ""
            for i, (vremya, bug, count) in enumerate(user_bugs, start=1):
                bugs_text += f"{i}) Время: {vremya} || Баг: {bug}\n"

            total_bugs = user_bugs[-1][2]  # берём последнее значение счётчика

            await message.reply(
                f"❗ | Список ваших поданных багов:\n\n{bugs_text}\n\nВсего багов подано: {total_bugs}",
                disable_mentions=1
            )
            return True            
            
        if command in ["clearchat", "удалитьчат"]:
            if await get_role(user_id, chat_id) < 10:
                await message.reply("Недостаточно прав!")
                return True

            if chat_id == 23:
                await message.reply("Данная беседа проводится в специализированном чате, который предназначен исключительно для тестировщиков бота.\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
                return True

            if len(arguments) < 2:
                await message.reply("Укажите чат!")
                return True

            try:
                target_chat = int(arguments[-1])
            except:
                await message.reply("Укажите чат!")
                return True
                
            target_peer = 2000000000 + target_chat
            await bot.api.messages.send(
                peer_id=target_peer,
                random_id=0,
                message=(
                    f"Чат удален из базы данных бота! Работа бота в чате прекращена."
                )
            )

            sql.execute("DELETE FROM chats WHERE chat_id = ?", (target_chat,))
            database.commit()

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) удалил(-а) беседу №«{target_chat}»")
            return True
                        
        if command in ['help', 'помощь', 'хелп', 'команды', 'commands']:
            commands_levels = {
                0: [
                    'Команды пользователей:',
                    '/info -- офицальные ресурсы проекта',
                    '/правила — правила чата установленные владельцем беседы',
                    '/правилабота — правила использования бота',
                    '/infobot — офицальные ресурсы бота',                    
                    '/stats -- информация о пользователе',
                    '/getid -- узнать оригинальный ID пользователя в ВК',
                    '/q -- выход из текущей беседы',
                    '/other -- другие команды (игровые, рп команды)'
                ],
                1: [
                    '\nКоманды модераторов:',
                    '/setnick — сменить ник у пользователя',
                    '/removenick — очистить ник у пользователя',
                    '/getnick — проверить ник пользователя',
                    '/getacc — узнать пользователя по нику',
                    '/nlist — просмотреть ники пользователей',
                    '/nonick — пользователи без ников',
                    '/kick — исключить пользователя из беседы',
                    '/warn — выдать предупреждение пользователю',
                    '/unwarn — снять предупреждение пользователю',
                    '/getwarn — информация о активных предупреждениях пользователя',
                    '/warnhistory — информация о всех предупреждениях пользователя',
                    '/warnlist — список пользователей с варном',
                    '/staff — пользователи с ролями',
                    '/mute — замутить пользователя',
                    '/unmute — размутить пользователя',
                    '/alt — узнать альтернативные команды',
                    '/getmute -- информация о муте пользователя',
                    '/mutelist -- список пользователей с мутом',
                    '/clear -- очистить сообщения',
                    '/getban -- информация о банах пользователя',
                    '/delete -- удалить сообщение пользователя',
                    '/chatid -- узнать оригинальный айди чата в боте'                    
                ],
                2: [
                    '\nКоманды старших модераторов:',
                    '/ban — заблокировать пользователя в беседе',
                    '/unban -- разблокировать пользователя в беседе',
                    '/addmoder -- выдать пользователю модератора',
                    '/removerole -- забрать роль у пользователя',
                    '/zov -- упомянуть всех пользователей',
                    '/online -- упомянуть пользователей онлайн',
                    '/onlinelist — посмотреть пользователей в онлайн',
                    '/banlist -- посмотреть заблокированных',
                    '/inactivelist -- список неактивных пользователей',
                    '/masskick -- исключить нескольких пользователей'
                ],
                3: [
                    '\nСписок команд администраторов:',
                    '/quiet -- Включить выключить режим тишины',
                    '/skick -- исключить пользователя с бесед сетки',
                    '/sban -- заблокировать пользователя в сетке бесед',
                    '/sunban — разбанить пользователя в сетке бесед',
                    '/addsenmoder — выдать права старшего модератора',
                    '/rnickall -- очистить все ники в беседе',
                    '/sremovenick -- очистить ник у пользователя в сетке бесед',
                    '/szov -- вызов участников бесед сетки',
                    '/srole -- выдать права в сетке бесед'
                ],
                4: [
                    '\nСписок команд старших администраторов:',
                    '/addadmin -- выдать права администратора',
                    '/serverinfo -- информация о сервере',
                    '/filter -- фильтр запрещенных слов',
                    '/sremoverole -- забрать роль у пользователя в сетке бесед',
                    '/ssetnick -- установить ник в сетке бесед',
                    '/bug -- отправить баг-трекер разработчику бота',
                    '/report -- жалоба на пользователя'                   
                ],
                5: [
                    '\nСписок команд зам. спец администратора:',
                    '/addsenadmin -- выдать права старшего администратора',
                    '/sync -- синхронизация с базой данных',
                    '/pin -- закрепить сообщение',
                    '/unpin -- открепить сообщение',
                    '/deleteall -- удалить последние 200 сообщений пользователя',
                    '/gsinfo -- информация о глобальной привязке',
                    '/gsrnick -- очистить ник у пользователя в беседах привязки',
                    '/gssnick -- поставить ник пользователю в беседах привязки',
                    '/gskick -- исключить пользователя с бесед привязки',
                    '/gsban -- заблокировать пользователя в беседах привязки',
                    '/gsunban -- разбанить пользователя в беседах привязки'                    
                ],                
                6: [
                    '\nСписок команд спец. администратора:',
                    '/addzsa -- выдать права зам. спец. администратора',
                    '/server -- привязать беседу к серверу',
                    '/settings -- показать настройки беседы',
                    '/clearwarn -- снять варны всем пользователям',
                    '/title -- изменить название беседы',
                    '/antisliv -- включить систему антислива в беседе'
                ],                
                7: [
                    '\nСписок команд владельца беседы:',
                    '/addsa -- выдать права спец. администратора',
                    '/antiflood -- режим защиты от спама',
                    '/welcometext -- текст приветствия',
                    '/invite -- система добавления пользователей только модераторами',
                    '/leave -- система исключения пользователей при выходе',
                    '/editowner -- передать права владельца беседы',
                    '/masskick -- исключить участников без ролей',
                    '/защита -- защита от сторонних сообществ',
                    '/settingsmute -- включить выдачу варнов за написание сообщений в муте',
                    '/setinfo -- установить информацию о официальных ресурсах проекта в «/info»',
                    '/setrules -- установить правила беседы в «/rules»',
                    '/type – изменить тип беседы',
                    '/gsync -- поставить глобальную синхронизацию бесед',
                    '/gunsync – отключить глобальную синхронизацию бесед'                   
                ]               
            }

            user_role = await get_role(user_id, chat_id)

            if user_role > 1:
                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Альтернативные команды", {"command": "alt", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
                )
            else:
                keyboard = None

            commands = []
            for i in commands_levels.keys():
                if i <= user_role:
                    for b in commands_levels[i]:
                        commands.append(b)

            level_commands = '\n'.join(commands)

            await message.reply(f"{level_commands}", disable_mentions=1, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) список доступных команд")            

        if command in ['snick', 'setnick', 'nick', 'addnick', 'ник', 'сетник', 'аддник']:
            if await get_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!")
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            if await equals_roles(user_id, user, chat_id, message) == 0:
                await message.reply("Вы не можете установить ник данному пользователю!", disable_mentions=1)
                return True

            new_nick = await get_string(arguments, arg)
            if not new_nick:
                await message.reply("Укажите ник пользователя!", disable_mentions=1)
                return True
            else: await setnick(user, chat_id, new_nick)

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) установил новое имя @id{user} (пользователю)!\nНовый ник: {new_nick}", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"установил(-а) новый ник @id{user} (пользователю). Новый ник: {new_nick}")                       

        if command in ['rnick', 'removenick', 'clearnick', 'cnick', 'рник', 'удалитьник', 'снятьник']:
            if await get_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            if await equals_roles(user_id, user, chat_id, message) == 0:
                await message.reply("Вы не можете удалить ник данному пользователю!", disable_mentions=1)
                return True

            await rnick(user, chat_id)
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) убрал(-а) ник у @id{user} (пользователя)!", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"удалил(-а) старый ник @id{user} (пользователю)")            

        if command in ['type', 'тип']:
            if await get_role(user_id, chat_id) < 7:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            # получаем аргумент (новый тип)
            if len(arguments) < 2:
                # тип не указан, показываем текущий тип
                sql.execute(f"SELECT type FROM chats WHERE chat_id = {chat_id}")
                current_type = sql.fetchone()
                if current_type:
                    type_value = current_type[0]
                    await message.reply(
                        f"Беседа имеет тип: {chat_types.get(type_value, type_value)}\n\n"
                        "Все типы бесед:\n" +
                        "\n".join([f"{k} -- {v}" for k, v in chat_types.items()]),
                        disable_mentions=1
                    )
                return True

            new_type = arguments[1].lower()

            # проверка на валидность
            if new_type not in chat_types:
                await message.reply(
                    "Неверный тип беседы, типы:\n" +
                    "\n".join([f"{k} -- {v}" for k, v in chat_types.items()]),
                    disable_mentions=1
                )
                return True

            # устанавливаем новый тип
            sql.execute(f"UPDATE chats SET type = ? WHERE chat_id = ?", (new_type, chat_id))
            database.commit()

            await message.reply(f"Вы установили тип беседы: {chat_types[new_type]}", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"установил(-а) новый тип беседы. Новый тип: {chat_types[new_type]}")            
            
        if command in ["settings", "настройки"]:
            if await get_role(user_id, chat_id) < 6:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return

            # Получаем владельца чата через VK API
            x = await bot.api.messages.get_conversations_by_id(
                peer_ids=peer_id,
                extended=1,
                fields='chat_settings',
                group_id=message.group_id
            )
            x = json.loads(x.json())
            chat_owner = None
            chat_title = None
            for i in x['items']:
                chat_owner = int(i["chat_settings"]["owner_id"])
                chat_title = i["chat_settings"]["title"]

            # Получаем данные из базы по chat_id
            sql.execute(f"SELECT type, in_pull, filter, leave_kick, invite_kick, antiflood FROM chats WHERE chat_id = {chat_id}")
            row = sql.fetchone()
            if row:
                type_value = chat_types.get(row[0], row[0])
                server = await get_current_server(chat_id)
                filter_text = "Включено" if row[2] == 1 else "Выключено"
                leave_text = "Включено" if row[3] == 1 else "Выключено"
                invite_text = "Включено" if row[4] == 1 else "Выключено"
                antiflood_text = "Включено" if row[5] == 1 else "Выключено"
            else:
                type_value = "Общие беседы"
                server = "0"
                filter_text = "Выключено"
                leave_text = "Выключено"
                invite_text = "Выключено"
                antiflood_text = "Выключено"

            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) текущие настройки беседы")            
            await message.reply(
                f"Название чата: {chat_title}\n"
                f"Владелец чата: @id{chat_owner} ({await get_user_name(chat_owner, chat_id)})\n"
                f"Тип беседы: {type_value}\n"
                f"Сервер: {server}\n"
                f"ID чата: {chat_id}\n"
                f"Фильтр: {filter_text}\n"
                f"Исключение при выходе: {leave_text}\n"
                f"Приглашение от модератора +: {invite_text}\n"
                f"Анти-флуд: {antiflood_text}"
            )
            return            

        if command in ['gsrnick', 'грник']:
            if await get_role(user_id, chat_id) < 5:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            gsync_chats = await get_gsync_chats(chat_id)
            if not gsync_chats:
                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)
                return True

            user = int
            if message.reply_message:
                user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            if await equals_roles(user_id, user, chat_id, message) == 0:
                await message.reply("Вы не можете снять ник у данного пользователя!", disable_mentions=1)
                return True

            for i in gsync_chats:
                try:
                    await rnick(user, i)
                except:
                    continue

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) убрал ник у @id{user} (пользователя) во всех беседах глобальной связки.", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"снял ник @id{user} (пользователю) во всех беседах глобальной связки")
            return True
            
        if command in ['gssnick', 'гссник']:
            if await get_role(user_id, chat_id) < 5:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            gsync_chats = await get_gsync_chats(chat_id)
            if not gsync_chats:
                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            if await equals_roles(user_id, user, chat_id, message) == 0:
                await message.reply("Вы не можете установить ник данному пользователю!", disable_mentions=1)
                return True

            new_nick = await get_string(arguments, arg)
            if not new_nick:
                await message.reply("Укажите ник!", disable_mentions=1)
                return True

            for i in gsync_chats:
                try:
                    await setnick(user, i, new_nick)
                except:
                    continue

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) установил ник @id{user} (пользователю) во всех беседах глобальной связки.\nНовый ник: {new_nick}", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"установил ник {new_nick} @id{user} (пользователю) во всех беседах глобальной связки")
            return True

        if command in ['gskick', 'гскик']:
            if await get_role(user_id, chat_id) < 5:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            gsync_chats = await get_gsync_chats(chat_id)
            if not gsync_chats:
                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)
                return True

            user = int
            reason = None
            if message.reply_message:
                user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете исключить данного пользователя!", disable_mentions=1)
                return True

            for i in gsync_chats:
                try:
                    await bot.api.messages.remove_chat_user(i, user)
                    msg = f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил @id{user} ({await get_user_name(user, chat_id)}) в беседах глобальной связки!"
                    if reason:
                        msg += f"\nПричина: {reason}"
                    await bot.api.messages.send(peer_id=2000000000 + i, message=msg, disable_mentions=1, random_id=0)
                except:
                    continue

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил @id{user} (пользователя) из всех бесед глобальной связки.", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"исключил @id{user} из всех бесед глобальной связки")
            return True

        if command in ['gsban', 'гсбан']:
            if await get_role(user_id, chat_id) < 5:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            gsync_chats = await get_gsync_chats(chat_id)
            if not gsync_chats:
                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете заблокировать данного пользователя!", disable_mentions=1)
                return True

            reason = await get_string(arguments, arg)
            if not reason:
                await message.reply("Укажите причину блокировки!", disable_mentions=1)
                return True

            for i in gsync_chats:
                try:
                    await ban(user, user_id, i, reason)
                    await bot.api.messages.remove_chat_user(i, user)
                    msg = f"@id{user_id} ({await get_user_name(user_id, chat_id)}) исключил @id{user} ({await get_user_name(user, chat_id)}) в беседах глобальной связки!"
                    if reason:
                        msg += f"\nПричина: {reason}"
                    await bot.api.messages.send(peer_id=2000000000 + i, message=msg, disable_mentions=1, random_id=0)
                except:
                    continue

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) заблокировал @id{user} (пользователя) во всех беседах глобальной связки.\nПричина: {reason}", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"заблокировал @id{user} (пользователя) во всех беседах глобальной связки. Причина: {reason}")
            return True            
            
        if command in ['gsunban', 'гсунбан']:
            if await get_role(user_id, chat_id) < 5:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            gsync_chats = await get_gsync_chats(chat_id)
            if not gsync_chats:
                await message.reply("Беседа не привязана к глобальной связке!", disable_mentions=1)
                return True

            user = int
            if message.reply_message:
                user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            if await equals_roles(user_id, user, chat_id, message) == 0:
                await message.reply("Вы не можете разбанить данного пользователя!", disable_mentions=1)
                return True

            for i in gsync_chats:
                try:
                    await unban(user, i)
                except:
                    continue

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) снял блокировку с @id{user} (пользователя) во всех беседах глобальной связки.", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"разблокировал @id{user} во всех беседах глобальной связки")
            return True
            
        if command in ['getacc', 'acc', 'гетакк', 'аккаунт', 'account']:
            if await get_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            nick = await get_string(arguments, 1)
            if not nick:
                await message.reply("Укажите ник!", disable_mentions=1)
                return True

            nick_result = await get_acc(chat_id, nick)

            if not nick_result: await message.reply(f"Ник {nick} никому не принадлежит!", disable_mentions=1)
            else:
                info = await bot.api.users.get(nick_result)
                await message.reply(f"Ник {nick} принадлежит @id{nick_result} ({info[0].first_name} {info[0].last_name})", disable_mentions=1)
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-a) кому принадлежит НикНейм «{nick}»")            

        if command in ['getnick', 'gnick', 'гник', 'гетник']:
            if await get_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            user = 0
            if message.reply_message: user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            nick = await get_nick(user, chat_id)
            if not nick: await message.reply(f"У данного @id{user} (пользователя) нет ника!", disable_mentions=1)
            else: await message.reply(f"Ник данного @id{user} (пользователя): {nick}", disable_mentions=1)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"посмотрел(-а) текущее имя @id{user} (пользователя). Текущий ник: «{nick}»")            

        if command in ['никлист', 'ники', 'всеники', 'nlist', 'nickslist', 'nicklist', 'nicks']:
            if await get_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            nicks = await nlist(chat_id, 1)
            nick_list = '\n'.join(nicks)
            if nick_list == "": nick_list = "Ники отсутствуют!"

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("⏪", {"command": "nicksMinus", "page": 1, "chatId": chat_id}), color=KeyboardButtonColor.NEGATIVE)
                .add(Callback("Без ников", {"command": "nonicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
                .add(Callback("⏩", {"command": "nicksPlus", "page": 1, "chatId": chat_id}), color=KeyboardButtonColor.POSITIVE)
            )

            await message.reply(f"Пользователи с ником [1 страница]:\n{nick_list}\n\nПользователи без ников: «/nonick»", disable_mentions=1, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) пользователей с ником")            

        if command in ['nonick', 'nonicks', 'nonicklist', 'nolist', 'nnlist', 'безников', 'ноникс']:
            if await get_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            nonicks = await nonick(chat_id, 1)
            nonick_list = '\n'.join(nonicks)
            if nonick_list == "": nonick_list = "Пользователи без ников отсутствуют!"

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("⏪", {"command": "nonickMinus", "page": 1, "chatId": chat_id}), color=KeyboardButtonColor.NEGATIVE)
                .add(Callback("С никами", {"command": "nicks", "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
                .add(Callback("⏩", {"command": "nonickPlus", "page": 1, "chatId": chat_id}),
                     color=KeyboardButtonColor.POSITIVE)
            )

            await message.reply(f"Пользователи без ников [1]:\n{nonick_list}\n\nПользователи с никами: «/nlist»", disable_mentions=1, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=None, role=None, log=f"посмотрел(-а) пользователей без ников")            

        if command in ['kick', 'кик', 'исключить']:
            if await get_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            if chat_id == 23:
                await message.reply("Данная беседа проводится в специализированном чате, который предназначен исключительно для тестировщиков бота.\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете исключить данного пользователя!", disable_mentions=1)
                return True

            reason = await get_string(arguments, arg)

            try: await bot.api.messages.remove_chat_user(chat_id, user)
            except:
                await message.reply(f"Не удается исключить данного @id{user} (пользователя)! Необходимо забрать у него звезду.", disable_mentions=1)
                return True

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("Очистить", {"command": "clear", "chatId": chat_id, "user": user}), color=KeyboardButtonColor.NEGATIVE)
            )

            if not reason: await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) кикнул(-а) @id{user} ({await get_user_name(user, chat_id)})", disable_mentions=1, keyboard=keyboard)
            else: await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) кикнул(-а) @id{user} ({await get_user_name(user, chat_id)})\nПричина: {reason}", disable_mentions=1, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"исключил(-а) @id{user} (пользователя) из беседы")            

            await add_punishment(chat_id, user_id)
            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы\n\n{await staff_zov(chat_id)}")

        if command in ['warn', 'пред', 'варн', 'pred', 'предупреждение']:
            if await get_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            user = int
            arg = 0
            if message.reply_message:
                user = message.reply_message.from_id
                arg = 1
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
                arg = 1
            elif len(arguments) >= 2 and await getID(arguments[1]):
                user = await getID(arguments[1])
                arg = 2
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете выдать пред данному пользователю!", disable_mentions=1)
                return True

            reason = await get_string(arguments, arg)
            if not reason:
                await message.reply("Укажите причину предупреждения!")
                return True

            warns = await warn(chat_id, user, user_id, reason)
            if warns < 3:
                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Снять варн", {"command": "unwarn", "user": user, "chatId": chat_id}), color=KeyboardButtonColor.POSITIVE)
                    .add(Callback("Очистить", {"command": "clear", "chatId": chat_id, "user": user}), color=KeyboardButtonColor.NEGATIVE)
                )
                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) предупреждение @id{user} ({await get_user_name(user, chat_id)})\nПричина: {reason}\nКоличество предупреждений: {warns}", disable_mentions=1, keyboard=keyboard)
            else:
                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Очистить", {"command": "clear", "chatId": chat_id, "user": user}),color=KeyboardButtonColor.NEGATIVE)
                )
                await message.answer(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) выдал(-а) последнее предупреждение @id{user} ({await get_user_name(user, chat_id)}) (3/3)\nПричина: {reason}\n@id{user} (Пользователь) был исключен за большое количество предупреждений!",disable_mentions=1, keyboard=keyboard)
                try: await bot.api.messages.remove_chat_user(user)
                except: pass
                await clear_warns(chat_id, user)

            await add_punishment(chat_id, user_id)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"выдал(-а) предупреждение @id{user} (пользователю). Причина: {reason}, Итого у пользователя: {warns}/3")            
            if await get_sliv(user_id, chat_id) and await get_role(user_id, chat_id) < 5:
                await roleG(user_id, chat_id, 0)
                await message.reply(
                    f"❗️ Уровень прав @id{user_id} (пользователя) был снят из-за подозрений в сливе беседы\n\n{await staff_zov(chat_id)}")

        if command in ['unwarn', 'унварн', 'анварн', 'снятьпред', 'минуспред']:
            if await get_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            if await equals_roles(user_id, user, chat_id, message) < 2:
                await message.reply("Вы не можете снять пред данному пользователю!", disable_mentions=1)
                return True

            if await get_warns(user, chat_id) < 1:
                await message.reply("У пользователя нет предупреждений!")
                return True

            warns = await unwarn(chat_id, user)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"снял(-а) предупреждение @id{user} (пользователю)")            
            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) снял(-а) предупреждение @id{user} ({await get_user_name(user, chat_id)})\nКоличество предупреждений: {warns}", disable_mentions=1)

        # --- /rules ---
        if command in ['rules', 'правила', 'правилачата']:
            sql.execute("SELECT description FROM rules WHERE chat_id = ?", (chat_id,))
            rules_text = sql.fetchone()

            if not rules_text:
                await message.reply("В этом чате ещё не установлены правила!\n\nУстановить новые правила может владелец беседы командой: «/setrules»", disable_mentions=1)
                return True

            await message.reply(f"{rules_text[0]}", disable_mentions=1)
            return True

        # --- /setrules ---
        if command in ['setrules', 'установитьправила']:
            if await get_role(user_id, chat_id) < 7:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            if len(arguments) < 2:
                await message.reply("Укажите новые правила беседы!", disable_mentions=1)
                return True

            text = " ".join(arguments[1:])
            sql.execute("INSERT OR REPLACE INTO rules (chat_id, description) VALUES (?, ?)", (chat_id, text))
            database.commit()

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) установил(-а) новые правила в беседу «/rules»:\n\n{text}", disable_mentions=1)
            return True

        if command in ['infoid', 'инфоайди', 'чатыпользователя', 'инфоид']:
                if await get_role(user_id, chat_id) < 10:
                        await message.reply("Недостаточно прав!", disable_mentions=1)
                        return True

                if len(arguments) < 2:
                        await message.reply("Укажите пользователя!", disable_mentions=1)
                        return True

                target = await getID(arguments[1])
                if not target:
                        await message.reply("Не удалось определить пользователя.", disable_mentions=1)
                        return True

                sql.execute("SELECT chat_id FROM chats WHERE owner_id = ?", (target,))
                user_chats = sql.fetchall()
                if not user_chats:
                        await message.reply("У пользователя нет зарегистрированных бесед.", disable_mentions=1)
                        return True

                # Берем первую страницу
                page = 1
                per_page = 5
                total_pages = (len(user_chats) + per_page - 1) // per_page
                start = (page - 1) * per_page
                end = start + per_page
                page_chats = user_chats[start:end]

                all_chats = []
                for idx, (chat_id_val,) in enumerate(page_chats, start=1):
                        try:
                                peer_id = 2000000000 + chat_id_val
                                info = await bot.api.messages.get_conversations_by_id(peer_ids=peer_id)
                                if info.items:
                                        chat_title = info.items[0].chat_settings.title
                                else:
                                        chat_title = "Без названия"
                                link = (await bot.api.messages.get_invite_link(peer_id=peer_id, reset=0)).link
                        except:
                                chat_title = "Не удалось получить"
                                link = "Не удалось получить"

                        all_chats.append(f"{idx}. {chat_title} | 🆔: {chat_id_val} | 🔗 Ссылка: {link}")

                all_chats_text = "\n".join(all_chats)
                keyboard = (
                    Keyboard(inline=True)
                    .add(Callback("Назад", {"command": "infoidMinus", "page": 1, "user": target}), color=KeyboardButtonColor.NEGATIVE)
                    .add(Callback("Вперёд", {"command": "infoidPlus", "page": 1, "user": target}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                        f"❗ Список бесед @id{target} (пользователя):\n(Страница: 1)\n\n{all_chats_text}\n\n🗨️ Всего бесед у пользователя: {idx}",
                        disable_mentions=1,
                        keyboard=keyboard
                )
                return True                

        if command in ['banwords', 'запрещенныеслова', 'banwordlist']:
                if await get_role(user_id, chat_id) < 10:
                        await message.reply("Недостаточно прав!", disable_mentions=1)
                        return True

                sql.execute("SELECT word, creator_id, time FROM ban_words ORDER BY time DESC")
                rows = sql.fetchall()
                if not rows:
                        await message.reply("Запрещённые слова отсутствуют!", disable_mentions=1)
                        return True

                total = len(rows)
                per_page = 5
                max_page = (total + per_page - 1) // per_page

                async def get_words_page(page: int):
                        start = (page - 1) * per_page
                        end = start + per_page
                        formatted = []
                        for i, (word, creator, tm) in enumerate(rows[start:end], start=start + 1):
                                try:
                                        info = await bot.api.users.get(user_ids=creator)
                                        creator_name = f"{info[0].first_name} {info[0].last_name}"
                                except:
                                        creator_name = "Не удалось получить имя"
                                formatted.append(f"{i}. {word} | @id{creator} ({creator_name}) | Время: {tm}")
                        return formatted

                page = 1
                page_data = await get_words_page(page)
                page_text = "\n\n".join(page_data)

                keyboard = (
                        Keyboard(inline=True)
                        .add(Callback("⏪", {"command": "banwordsMinus", "page": 1}), color=KeyboardButtonColor.NEGATIVE)
                        .add(Callback("⏩", {"command": "banwordsPlus", "page": 1}), color=KeyboardButtonColor.POSITIVE)
                )

                await message.reply(
                        f"Запрещённые слова (Страница 1):\n\n{page_text}\n\nВсего запрещенных слов: {total}",
                        disable_mentions=1, keyboard=keyboard
                )
                return True
                
        if command in ['addbanwords', 'addword', 'banword']:
                if await get_role(user_id, chat_id) < 10:
                        await message.reply("Недостаточно прав!", disable_mentions=1)
                        return True
                if len(arguments) < 2:
                        await message.reply("Пример: /addbanwords текст")
                        return True

                word = arguments[1].lower()
                time_now = datetime.now().strftime("%I:%M %p")

                sql.execute("SELECT word FROM ban_words WHERE word = ?", (word,))
                if sql.fetchone():
                        await message.reply("Слово уже находиться в списке запрещенных слов!")
                        return True

                sql.execute("INSERT INTO ban_words (word, creator_id, time) VALUES (?, ?, ?)", (word, user_id, time_now))
                database.commit()

                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) добавил(-а) слово «{word}» в список запрещенных слов!")
                return True

        if command in ['removebanwords', 'unword', 'unbanword']:
                if await get_role(user_id, chat_id) < 10:
                        await message.reply("Недостаточно прав!", disable_mentions=1)
                        return True
                if len(arguments) < 2:
                        await message.reply("Пример: /removebanwords текст")
                        return True

                word = arguments[1].lower()
                sql.execute("SELECT word FROM ban_words WHERE word = ?", (word,))
                if not sql.fetchone():
                        await message.reply("Слово отсутствует в списке запрещенных слов!")
                        return True

                sql.execute("DELETE FROM ban_words WHERE word = ?", (word,))
                database.commit()

                await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) удалил(-а) слово «{word}» из списка запрещенных слов!")
                return True
                
        # --- /info ---
        if command in ['info', 'инфо', 'информация']:
            sql.execute("SELECT description FROM info WHERE chat_id = ?", (chat_id,))
            info_text = sql.fetchone()

            if not info_text:
                await message.reply("В этом чате ещё не установлена информация!\n\nУстановить новую информацию может владелец беседы командой: «/setinfo»", disable_mentions=1)
                return True

            await message.reply(f"{info_text[0]}", disable_mentions=1)
            return True

        if command in ['other', 'другие', 'другиекмд', 'игровыекмд']:
            await message.reply(
                "/приз — получить ежедневный бонус\n"
                "/баланс — посмотреть свой баланс\n"
                "/дуэль — сыграть дуэль\n"
                "/передать — передать монеты другому пользователю\n"
                "/топ — топ самых богатых пользователей\n"
                "/положить — положить деньги в банк\n"
                "/снять — снять деньги с банка\n"
                "/благо — отправить монеты в благотворительность\n"
                "/топблаго — топ отправителей монет в благотворительность\n"
                "/buyvip — купить вип статус\n"
                "/промо — получить бонус\n"
                "/открытьдепозит — открыть депозит (для вип)\n"
                "/закрытьдепозит — закрыть депозит (для вип)\n"
                "/form — подать форму на бан (только в определенном чате)\n"
                "/offer — предложение по улучшению бота\n"
                "/казино — игра в казино на ставку\n"
                "/promo — активировать определенный промо-код\n"
                "/promolist — список активированных промо-кодов"
            )
            return True            
            
        # --- /setinfo ---
        if command in ['setinfo', 'установитьинфо']:
            if await get_role(user_id, chat_id) < 7:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            if len(arguments) < 2:
                await message.reply("Укажите новую информацию в беседе;", disable_mentions=1)
                return True

            text = " ".join(arguments[1:])
            sql.execute("INSERT OR REPLACE INTO info (chat_id, description) VALUES (?, ?)", (chat_id, text))
            database.commit()

            await message.reply(f"@id{user_id} ({await get_user_name(user_id, chat_id)}) установил(-а) новую информацию в беседу «/info»:\n\n{text}", disable_mentions=1)
            return True

        if command in ['antisliv', 'антислив']:
            if await get_role(user_id, chat_id) < 6:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            # Получаем текущее состояние антислива
            current_mode = await get_antisliv(chat_id)
            new_mode = 0 if current_mode == 1 else 1

            # Обновляем состояние
            await antisliv_mode(chat_id, new_mode)

            # Получаем имя пользователя, кто изменил режим
            user_name = await get_user_name(user_id, chat_id)

            # Формируем текст статуса
            if new_mode == 1:
                text = f"@id{user_id} ({user_name}) включил(-а) систему антислива!"
            else:
                text = f"@id{user_id} ({user_name}) выключил(-а) систему антислива!"

            await message.reply(text, disable_mentions=1)
            return True            
            
        if command in ['clearwarn', 'очиститьварны']:
            if await get_role(user_id, chat_id) < 6:  # доступ с 6 ранга
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            count = await clear_all_warns(chat_id)

            if count == 0:
                await message.reply("В данной беседе нет пользователей с наказаниями", disable_mentions=1)
            else:
                await message.reply(f"Удалены предупреждения у {count} пользователей!", disable_mentions=1)
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"очистил(-а) варны у {count} пользователей")            

            return True
            
        if command in ['getwarn', 'gwarn', 'getwarns', 'гетварн', 'гварн']:
            if await get_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.reply("Вы не указали @пользователя!", disable_mentions=1)
                return True

            warns = await gwarn(user, chat_id)
            string_info = str
            if not warns: string_info = "Активных предупреждений нет!"
            else: string_info = f"@id{warns['moder']} (Модератор) | {warns['reason']} | {warns['count']}/3 | {warns['time']}"

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("История предупреждений", {"command": "warnhistory", "user": user, "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
            )

            await message.answer(f"@id{user_id} ({await get_user_name(user_id, chat_id)}), информация о активных предупреждениях @id{user} (пользователя):\n{string_info}", disable_mentions=1, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"посмотрел(-а) активные предупреждения @id{user} (пользователя)")            

        if command in ['warnhistory', 'historywarns', 'whistory', 'историяварнов', 'историяпредов']:
            if await get_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            user = int
            if message.reply_message: user = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                user = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]): user = await getID(arguments[1])
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            warnhistory_mass = await warnhistory(user, chat_id)
            if not warnhistory_mass: wh_string = "Предупреждений не было!"
            else: wh_string = '\n'.join(warnhistory_mass)

            keyboard = (
                Keyboard(inline=True)
                .add(Callback("Активные предупреждения", {"command": "activeWarns", "user": user, "chatId": chat_id}), color=KeyboardButtonColor.PRIMARY)
                .add(Callback("Вся информация", {"command": "stats", "user": user, "chatId": chat_id}),color=KeyboardButtonColor.PRIMARY)
            )

            await message.reply(f"Информация о всех предупреждениях @id{user} ({await get_user_name(user, chat_id)})\nКоличество предупреждений пользователя: {await get_warns(user, chat_id)}\n\nИнформация о последних 10 предупреждений пользователя:\n{wh_string}", disable_mentions=1, keyboard=keyboard)
            await chats_log(user_id=user_id, target_id=user, role=None, log=f"посмотрел(-а) все предупреждения @id{user} (пользователя)")            

# GAME
        # ---------------- БАЛАНС ----------------
        if command in ["баланс"]:
            target = await extract_user_id(message)
            if not target:
                target = user_id

            # Загружаем актуальные данные из файла
            balances = load_data(BALANCES_FILE)
            if str(target) not in balances:
                balances[str(target)] = get_balance(target)  # создаём запись, если её нет
            bal = balances[str(target)]

            now = datetime.now()

            # Получаем имя в родительном падеже
            try:
                info = await bot.api.users.get(user_ids=target, name_case="gen")
                name = f"{info[0].first_name} {info[0].last_name}"
                mention = f"пользователя [id{target}|{name}]"
            except:
                mention = f"[id{target}|id{target}]"

            # Проверка на VIP
            vip_until = bal.get("vip_until")
            if vip_until:
                try:
                    vip_end = datetime.fromisoformat(vip_until)
                    if vip_end > now:
                        is_vip = True
                        delta = vip_end - now
                        days, seconds = delta.days, delta.seconds
                        hours, minutes = divmod(seconds // 60, 60)
                        vip_status = "VIP"
                        vip_time = f"⏳ До окончания статуса: {days}д {hours}ч {minutes}м"
                        transfer_limit = 500_000
                    else:
                        is_vip = False
                        vip_status = "Отсутствует"
                        vip_time = "⏳ Отсутствует"
                        transfer_limit = 100_000
                except:
                    is_vip = False
                    vip_status = "Отсутствует"
                    vip_time = "⏳ Отсутствует"
                    transfer_limit = 100_000
            else:
                is_vip = False
                vip_status = "Отсутствует"
                vip_time = "⏳ Отсутствует"
                transfer_limit = 100_000

            # Лимит переводов
            today = now.date().isoformat()
            spent_today = bal.get("transfers_today", {}).get(today, 0)
            remaining_limit = max(0, transfer_limit - spent_today)

            # Депозит
            deposit_text = ""
            deposit_amount = bal.get("deposit_amount", 0)
            deposit_until = bal.get("deposit_until")
            deposit_percent = bal.get("deposit_percent", 0)
            if deposit_amount > 1 and deposit_until:
                try:
                    end_time = datetime.fromisoformat(deposit_until)
                    if now < end_time:
                        delta = end_time - now
                        days, seconds = delta.days, delta.seconds
                        hours, minutes = divmod(seconds // 60, 60)
                        deposit_text = (
                            f"\n💸 Депозит: {format_number(deposit_amount)}$ "
                            f"на {days} дн. "
                            f"под {deposit_percent}%"
                            f"\n⏳ До вывода: {days}д {hours}ч {minutes}м"
                        )
                    else:
                        deposit_text = (
                            f"\n💸 Депозит: {format_number(deposit_amount)}$ "
                            f"под {deposit_percent}%"
                            f"\n⏳ До вывода: можно забирать!"
                        )
                except:
                    pass

            await message.reply(
                f"💰 У {mention} {format_number(bal['wallet'])}$\n"
                f"🏛 Счет в банке: {format_number(bal['bank'])}$\n"
                f"🏆 Дуэлей выиграно: {bal['won']}\n"
                f"💔 Дуэлей проиграно: {bal['lost']}\n"
                f"🎉 Всего выиграно: {format_number(bal['won_total'])}$\n"
                f"💰 Всего проиграно: {format_number(bal['lost_total'])}$\n"
                f"📤 Отправлено переводами: {format_number(bal['sent_total'])}$\n"
                f"📥 Получено переводами: {format_number(bal['received_total'])}$\n"
                f"⭐ Статус: {vip_status}\n"
                f"{vip_time}\n"
                f"🔄 Остаток лимита на сегодня: {format_number(remaining_limit)}$ / {format_number(transfer_limit)}$"
                f"{deposit_text}"
            )
            return            
          
        # ---------------- GIVEALL / РАЗДАЧА ----------------
        if command in ["giveall", "раздача"]:
            # разрешённый ВК ID администратора
            role = await get_role(user_id, chat_id)
            if role < 11:
                await message.reply("Недостаточно прав!")
                return

            if chat_id == 23:
                await message.reply("Данная беседа проводится в специализированном чате, который предназначен исключительно для тестировщиков бота.\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
                return True

            if len(arguments) < 1:
                await message.reply("💰 Пример: /раздача 1000")
                return

            try:
                amount = int(arguments[-1])
                if amount <= 0:
                    raise ValueError()
            except:
                await message.reply("Укажите сумму числом!")
                return

            # загружаем балансы
            balances = load_data(BALANCES_FILE)

            all_users_text = ""
            for i, (uid, bal) in enumerate(balances.items(), start=1):
                # обновляем кошелёк
                bal["wallet"] += amount

                # получаем имя пользователя
                try:
                    info = await bot.api.users.get(user_ids=uid)
                    full_name = f"{info[0].first_name} {info[0].last_name}"
                except:
                    full_name = f"Ошибка"

                all_users_text += f"{i}. [id{uid}|{full_name}] | 💰 Новый баланс: {format_number(bal['wallet'])}\n"

            # сохраняем обновлённые балансы
            save_data(BALANCES_FILE, balances)
            await log_economy(user_id=uid, target_id=None, amount=amount, log=f"произвел(-а) раздачу на {amount}$")            

            # формируем сообщение
            admin_name = f"@id{user_id}"  # или можно получить полное имя администратора
            await message.reply(
                f"Раздача на «{format_number(amount)}$» была успешно произведена {admin_name} (администратором бота), монеты получили:\n\n{all_users_text}"
            )
            return            

        if command in ['say', 'сообщение']:
            if await get_role(user_id, chat_id) < 10:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            if len(arguments) < 2:
                await message.reply("Укажите айди беседы!")
                return True

            # Парсим target_chat из первого аргумента
            try:
                target_chat = int(arguments[1])
            except ValueError:
                await message.reply("Укажите конкретный айди беседы!")
                return True

            # Проверка: если это беседа, прибавляем 2000000000
            if target_chat > 0:
                target_peer = 2000000000 + target_chat
            else:
                target_peer = target_chat

            # Текст сообщения — всё после первого аргумента
            text = " ".join(arguments[2:])
            if not text.strip():
                await message.reply("Укажите текст сообщения!")
                return True

            try:
                await bot.api.messages.send(
                    peer_id=target_peer,
                    message=text,
                    random_id=0
                )
                await message.reply(f"Сообщение успешно отправлено в чат ID {target_chat}.")
                await chats_log(user_id=user_id, target_id=None, role=None, log=f"отправил(-а) сообщение в чат «{target_chat}» Сообщение: {text}")            
            except Exception as e:
                await message.reply(f"Произошла ошибка при отправке: {e}")
                print(f"[say command] Ошибка отправки в чат {target_chat}: {e}")
            return True
            
        # ---------------- GIVE ----------------
        if command in ["give", "выдать"]:
            role = await get_role(user_id, chat_id)
            if role < 10:
                await message.reply("Недостаточно прав!")
                return

            if chat_id == 23:
                await message.reply("Данная беседа проводится в специализированном чате, который предназначен исключительно для тестировщиков бота.\n\nВ рамках данного обсуждения не допускается использование команд, не относящихся к работе по тестированию или функционированию системы в целом.", disable_mentions=1)
                return True

            target = await extract_user_id(message)
            if not target:
                await message.reply("Укажите пользователя!")
                return

            if len(arguments) < 1:
                await message.reply("Сумма должна быть числом.")
                return

            try:
                amount = int(arguments[-1])
            except:
                await message.reply("Сумма должна быть числом.")
                return

            # получаем баланс и обновляем
            balances = load_data(BALANCES_FILE)
            bal = balances.get(str(target), get_balance(target))
            bal["wallet"] += amount
            balances[str(target)] = bal
            await log_economy(user_id=user_id, target_id=target, amount=amount, log=f"выдал(-а) {amount}$ пользователю {target}")          
            save_data(BALANCES_FILE, balances)

            try:
                s_info = await bot.api.users.get(user_ids=user_id)
                r_info = await bot.api.users.get(user_ids=target)
                s_name = f"{s_info[0].first_name} {s_info[0].last_name}"
                r_name = f"{r_info[0].first_name} {r_info[0].last_name}"
            except:
                s_name = str(user_id)
                r_name = str(target)

            await message.reply(
                f"[id{user_id}|{s_name}] выдал(-а) «{format_number(amount)}$» пользователю [id{target}|{r_name}]"
            )
            return

        if command in ['getban', 'чекбан', 'гетбан', 'checkban']:
            if await get_role(user_id, chat_id) < 1:
                await message.reply("Недостаточно прав!", disable_mentions=1)
                return True

            # Получаем цель
            target = None
            if message.reply_message:
                target = message.reply_message.from_id
            elif message.fwd_messages and message.fwd_messages[0].from_id > 0:
                target = message.fwd_messages[0].from_id
            elif len(arguments) >= 2 and await getID(arguments[1]):
                target = await getID(arguments[1])
            else:
                await message.reply("Укажите пользователя!", disable_mentions=1)
                return True

            # --- Проверка глобальных банов ---
            sql.execute("SELECT * FROM gbanlist WHERE user_id = ?", (target,))
            gbanlist = sql.fetchone()

            sql.execute("SELECT * FROM globalban WHERE user_id = ?", (target,))
            globalban = sql.fetchone()

            globalbans_chats = ""
            if globalban and gbanlist:
                gbanchats = f"@id{globalban[1]} (Модератор) | {globalban[2]} | {globalban[3]} МСК (UTC+3)"
                gban_str = f"@id{gbanlist[1]} (Модератор) | {gbanlist[2]} | {gbanlist[3]} МСК (UTC+3)"
                globalbans_chats = f"Информация об общей блокировке в беседах:\n{gbanchats}\n\nИнформация об блокировке в беседах игроков:\n{gban_str}"
            elif globalban:
                gbanchats = f"@id{globalban[1]} (Модератор) | {globalban[2]} | {globalban[3]} МСК (UTC+3)"
                globalbans_chats = f"Информация об общей блокировке в беседах:\n{gbanchats}"
            elif gbanlist:
                gban_str = f"@id{gbanlist[1]} (Модератор) | {gbanlist[2]} | {gbanlist[3]} МСК (UTC+3)"
                globalbans_chats = f"Информация об блокировке в беседах игроков:\n{gban_str}"
            else:
                globalbans_chats = "Блокировка во всех беседах — отсутствует\nБлокировка в беседах игроков — отсутствует"

            # --- Проверка банов во всех чатах ---
            sql.execute("SELECT chat_id FROM chats")
            chats_list = sql.fetchall()
            bans = ""
            count_bans = 0
            i = 1
            for c in chats_list:
                chat_id_check = c[0]
                try:
                    sql.execute(f"SELECT moder, reason, date FROM bans_{chat_id_check} WHERE user_id = ?", (target,))
                    user_bans = sql.fetchall()
                    if user_bans:
                        # Получаем название беседы
                        rel_id = 2000000000 + chat_id_check
                        try:
                            resp = await bot.api.messages.get_conversations_by_id(peer_ids=rel_id)
                            if resp.items:
                                chat_title = resp.items[0].chat_settings.title or "Без названия"
                            else:
                                chat_title = "Без названия"
                        except:
                            chat_title = "Ошибка получения названия"

                        count_bans += 1
                        for ub in user_bans:
                            mod, reason, date = ub
                            bans += f"{i}) {chat_title} | @id{mod} (Модератор) | {reason} | {date} МСК (UTC+3)\n"
                            i += 1
                except:
                    continue  # если таблицы нет, пропускаем
                                       
            if count_bans == 0:
                bans_chats = "Блокировки в беседах отсутствуют"
            else:
                bans_chats = f"Количество бесед, в которых заблокирован пользователь: {count_bans}\nИнформация о банах пользователя:\n{bans}"

            # --- Итоговое сообщение ---
            await message.reply(
                f"Информация о блокировках @id{target} (Пользователь)\n\n"
                f"{globalbans_chats}\n\n"
                f"{bans_chats}",
                disable_mentions=1
            )

            await chats_log(
                user_id=user_id,
                target_id=target,
                role=None,
                log=f"посмотрел(-а) список блокировок @id{target} (пользователя)"
            )
            return True
                        
        # ---------------- RESETMONEY ----------------
        if command in ["resetmoney", "анулировать", "�