import os
import sqlite3
import random
import time
import re
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ==============================
# ENV
# ==============================

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN missing")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY missing")

ai_client = Groq(api_key=GROQ_API_KEY)

# ==============================
# DATABASE
# ==============================

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    branch TEXT,
    xp INTEGER DEFAULT 0,
    total_quizzes INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0
)
""")
conn.commit()

# ==============================
# QUESTIONS
# ==============================

questions_bank = {
    "علمي": [
        {"q": "اشتق س^2", "a": "2س"},
        {"q": "تكامل 2س د س", "a": "س^2"},
        {"q": "حل س^2 - 4 = 0", "a": "2,-2"},
        {"q": "نهاية س→0 لـ جا س / س", "a": "1"},
        {"q": "حل 2س + 6 = 0", "a": "-3"},
    ],
    "أدبي": [
        {"q": "احسب 15% من 200", "a": "30"},
        {"q": "حل 3س = 12", "a": "4"},
        {"q": "احسب 8 + 9", "a": "17"},
        {"q": "احسب 45 ÷ 5", "a": "9"},
        {"q": "حل س - 7 = 2", "a": "9"},
    ]
}

# ==============================
# HELPERS
# ==============================

def contains_latin(text):
    return re.search(r"[A-Za-z]", text) is not None

def clean_text(text):
    text = re.sub(r"[A-Za-z]", "", text)
    return text.strip()

def normalize(text):
    return text.replace(" ", "").lower()

def check_answer(user_input, correct_answer):
    user_input = normalize(user_input)
    correct_answer = normalize(correct_answer)

    if "," in correct_answer:
        return set(user_input.split(",")) == set(correct_answer.split(","))

    return user_input == correct_answer

def get_level(xp):
    if xp < 50:
        return "مبتدئ"
    elif xp < 150:
        return "متوسط"
    elif xp < 300:
        return "متقدم"
    elif xp < 600:
        return "محترف"
    else:
        return "خبير"

# ==============================
# SESSION + SPAM
# ==============================

sessions = {}
spam_tracker = {}

def is_spam(user_id):
    now = time.time()
    times = spam_tracker.get(user_id, [])
    times = [t for t in times if now - t < 5]
    times.append(now)
    spam_tracker[user_id] = times
    return len(times) > 5

# ==============================
# COMMANDS
# ==============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🔬 علمي"], ["📖 أدبي"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "🎓 منصة رياضيات السادس الإعدادي\nاختر فرعك:",
        reply_markup=markup
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT branch FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text("اختر فرعك أولاً باستخدام /start")
        return

    branch = row[0]
    questions = random.sample(questions_bank[branch], 5)

    sessions[user_id] = {
        "questions": questions,
        "index": 0,
        "score": 0
    }

    await update.message.reply_text(f"📘 السؤال 1:\n{questions[0]['q']}")

# ==============================
# MAIN HANDLER
# ==============================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if is_spam(user_id):
        await update.message.reply_text("🚫 تم إيقافك مؤقتاً بسبب الإرسال المتكرر.")
        return

    # اختيار الفرع
    if text in ["🔬 علمي", "📖 أدبي"]:
        branch = "علمي" if "علمي" in text else "أدبي"
        cursor.execute("INSERT OR IGNORE INTO users (user_id, branch) VALUES (?,?)", (user_id, branch))
        cursor.execute("UPDATE users SET branch=? WHERE user_id=?", (branch, user_id))
        conn.commit()

        await update.message.reply_text("✅ تم اختيار الفرع\nاكتب /quiz أو اطرح سؤالك.")
        return

    # وضع الاختبار
    if user_id in sessions:
        session = sessions[user_id]
        q = session["questions"][session["index"]]

        if check_answer(text, q["a"]):
            session["score"] += 1
            await update.message.reply_text("✅ صحيح")
        else:
            await update.message.reply_text(f"❌ خطأ\nالإجابة: {q['a']}")

        session["index"] += 1

        if session["index"] < 5:
            await update.message.reply_text(
                f"📘 السؤال {session['index']+1}:\n"
                f"{session['questions'][session['index']]['q']}"
            )
        else:
            xp_gain = session["score"] * 10
            cursor.execute("""
            UPDATE users
            SET xp = xp + ?,
                total_quizzes = total_quizzes + 1,
                correct_answers = correct_answers + ?
            WHERE user_id=?
            """, (xp_gain, session["score"], user_id))
            conn.commit()

            await update.message.reply_text(f"🎉 انتهى الاختبار\nالنتيجة: {session['score']}/5")
            sessions.pop(user_id)
        return

    # ==============================
    # AI MODE WITH AUTO FIX
    # ==============================

    cursor.execute("SELECT branch FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    branch = row[0] if row else "علمي"

    system_prompt = f"""
أنت مدرس رياضيات عراقي متخصص بمنهج السادس الإعدادي - فرع {branch}.

تعليمات صارمة:
- اكتب بالعربية الفصحى فقط.
- يمنع استخدام أي حرف لاتيني.
- اشرح خطوة بخطوة.
- استخدم ترقيم منظم.
- لا تكتب مقدمة طويلة.
- الحد الأقصى 200 كلمة.
"""

    for _ in range(2):  # محاولة مرتين إذا ظهر خطأ لغوي
        try:
            response = ai_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.2,
                max_tokens=500
            )

            reply = response.choices[0].message.content

            if not contains_latin(reply):
                await update.message.reply_text(reply)
                return
            else:
                reply = clean_text(reply)

        except Exception as e:
            print("AI ERROR:", e)
            await update.message.reply_text("⚠️ حدث خطأ في الاتصال.")
            return

    await update.message.reply_text(reply)

# ==============================
# RUN
# ==============================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("🚀 Bot Running...")
app.run_polling()
