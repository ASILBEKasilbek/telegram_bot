import telebot
import sqlite3
import pandas as pd
import pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from telebot import types
import os

# =========================
# SOZLAMALAR
# =========================
from dotenv import load_dotenv
import os
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMINS = [5913958185,6548615329]

CHANNELS = ["@inspiringuz", "@dustov_math"]
TZ = pytz.timezone("Asia/Tashkent")

EXCEL_FILE = "certificate.xls"

bot = telebot.TeleBot(BOT_TOKEN)

# =========================
# DATABASE
# =========================
db = sqlite3.connect("bot.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    telegram_id INTEGER UNIQUE,
    username TEXT,
    first_name TEXT,
    joined_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS test_settings(
    id INTEGER PRIMARY KEY,
    test_link TEXT,
    test_date TEXT,
    start_time TEXT,
    end_time TEXT,
    is_active INTEGER
)
""")
db.commit()

# =========================
# YORDAMCHI
# =========================
def now_tashkent():
    return datetime.now(TZ)

def is_subscribed(uid):
    for ch in CHANNELS:
        try:
            s = bot.get_chat_member(ch, uid).status
            if s not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

def get_test():
    cursor.execute("SELECT * FROM test_settings WHERE id=1")
    return cursor.fetchone()

def test_is_active():
    t = get_test()
    if not t or t[5] == 0:
        return False

    now = now_tashkent()
    d = datetime.strptime(t[2], "%Y-%m-%d").date()
    s = datetime.strptime(t[3], "%H:%M").time()
    e = datetime.strptime(t[4], "%H:%M").time()

    return now.date() == d and s <= now.time() <= e

# =========================
# SERTIFIKAT (FAQAT XLS)
# =========================
def calculate_percent(score):
    score = float(score)
    return 100 if score >= 65 else round((score / 75) * 100, 1)

def read_excel():
    if not os.path.exists(EXCEL_FILE):
        return None
    return pd.read_excel(EXCEL_FILE, engine="xlrd")

def generate_certificate(uid):
    df = read_excel()
    if df is None:
        return None

    # ID 1-ustunda (#)
    row = df[df.iloc[:, 0] == uid]
    if row.empty:
        return None

    row = row.iloc[0]
    name = str(row.iloc[1])
    score = row.iloc[4]
    level = str(row.iloc[5])

    percent = calculate_percent(score)

    img = Image.open("template.png").convert("RGBA")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", 36)
    small = ImageFont.truetype("arial.ttf", 28)

    draw.text((866, 755), name, fill="black", font=font)
    draw.text((1279, 1290), f"{percent}%", fill="black", font=font)
    draw.text((1279, 1410), level, fill="black", font=font)
    draw.text(
        (400, 1790),
        now_tashkent().strftime("%d.%m.%Y"),
        fill="black",
        font=small
    )

    img.save("result.png")
    return "result.png"

# =========================
# START
# =========================
@bot.message_handler(commands=["start"])
def start(m):
    cursor.execute(
        "INSERT OR IGNORE INTO users VALUES (?,?,?,?)",
        (m.from_user.id, m.from_user.username,
         m.from_user.first_name, now_tashkent())
    )
    db.commit()

    if not is_subscribed(m.from_user.id):
        kb = types.InlineKeyboardMarkup()
        for ch in CHANNELS:
            kb.add(types.InlineKeyboardButton(
                ch, url=f"https://t.me/{ch[1:]}"
            ))
        kb.add(types.InlineKeyboardButton(
            "🔄 Tekshirish", callback_data="check_sub"
        ))
        bot.send_message(
            m.chat.id,
            "❗ Kanallarga obuna bo‘ling:",
            reply_markup=kb
        )
        return

    show_menu(m.chat.id)

def show_menu(cid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if test_is_active():
        kb.add("📝 Testga kirish")
    else:
        kb.add("➕ Test yaratish", "📝 Test ishlash")
        kb.add("🎓 Sertifikat olish")
    bot.send_message(cid, "Assalomu alaykum 👋", reply_markup=kb)

# =========================
# CALLBACK
# =========================
@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def check_sub(c):
    if is_subscribed(c.from_user.id):
        show_menu(c.message.chat.id)
    else:
        bot.answer_callback_query(c.id, "❌ Obuna emas")

# =========================
# USER
# =========================
@bot.message_handler(func=lambda m: m.text == "📝 Testga kirish")
def enter_test(m):
    t = get_test()
    if t:
        bot.send_message(m.chat.id, t[1])

@bot.message_handler(func=lambda m: m.text == "➕ Test yaratish")
def create_test(m):
    t = get_test()
    link = t[1] if t else "https://dustovmath.rf.gd/creator.html"
    bot.send_message(m.chat.id, link)

@bot.message_handler(func=lambda m: m.text == "📝 Test ishlash")
def take_test(m):
    t = get_test()
    link = t[1] if t else "https://dustovmath.rf.gd/taker.html"
    bot.send_message(m.chat.id, link)

@bot.message_handler(func=lambda m: m.text == "🎓 Sertifikat olish")
def cert(m):
    if test_is_active():
        bot.send_message(m.chat.id, "⛔ Test vaqtida mumkin emas")
        return
    bot.send_message(m.chat.id, "ID raqamingizni yuboring:")

@bot.message_handler(func=lambda m: m.text.isdigit())
def cert_id(m):
    if test_is_active():
        return
    c = generate_certificate(int(m.text))
    if not c:
        bot.send_message(m.chat.id, "❌ ID topilmadi")
        return
    with open(c, "rb") as f:
        bot.send_photo(m.chat.id, f)

# =========================
# ADMIN
# =========================
test_setup = {}

@bot.message_handler(commands=["admin"])
def admin(m):
    if m.from_user.id not in ADMINS:
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔗 Test sozlash", "📄 XLS yuklash")
    bot.send_message(m.chat.id, "👑 Admin panel", reply_markup=kb)

# =========================
# FAQAT XLS YUKLASH
# =========================
@bot.message_handler(func=lambda m: m.text == "📄 XLS yuklash")
def upload_excel(m):
    if m.from_user.id in ADMINS:
        bot.send_message(m.chat.id, "📎 Faqat .xls fayl yuboring")

@bot.message_handler(content_types=["document"])
def handle_doc(m):
    if m.from_user.id not in ADMINS:
        return

    fname = m.document.file_name.lower()
    if not fname.endswith(".xls"):
        bot.send_message(m.chat.id, "❌ Faqat .xls fayl qabul qilinadi")
        return

    file = bot.get_file(m.document.file_id)
    data = bot.download_file(file.file_path)

    with open(EXCEL_FILE, "wb") as f:
        f.write(data)

    bot.send_message(m.chat.id, "✅ XLS fayl qabul qilindi")

# =========================
# TEST SOZLASH
# =========================
@bot.message_handler(func=lambda m: m.text == "🔗 Test sozlash")
def setup_test(m):
    if m.from_user.id not in ADMINS:
        return
    test_setup[m.from_user.id] = {}
    bot.send_message(m.chat.id, "🔗 Test linkini yuboring:")

@bot.message_handler(func=lambda m: m.from_user.id in test_setup)
def setup_steps(m):
    d = test_setup[m.from_user.id]

    if "link" not in d:
        d["link"] = m.text
        bot.send_message(m.chat.id, "📅 Sana (YYYY-MM-DD):")
    elif "date" not in d:
        d["date"] = m.text
        bot.send_message(m.chat.id, "⏰ Boshlanish (HH:MM):")
    elif "start" not in d:
        d["start"] = m.text
        bot.send_message(m.chat.id, "⏰ Tugash (HH:MM):")
    else:
        d["end"] = m.text
        cursor.execute("DELETE FROM test_settings")
        cursor.execute(
            "INSERT INTO test_settings VALUES (1,?,?,?,?,1)",
            (d["link"], d["date"], d["start"], d["end"])
        )
        db.commit()
        test_setup.pop(m.from_user.id)
        bot.send_message(m.chat.id, "✅ Test faollashtirildi")

# =========================
print("🤖 Bot ishga tushdi")
bot.infinity_polling()
