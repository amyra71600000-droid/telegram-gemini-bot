import os
import sqlite3
import random
import time
import re
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# =====================================
# ENV
# =====================================

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN missing")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY missing")

ai_client = Groq(api_key=GROQ_API_KEY)

# =====================================
# DATABASE
# =====================================

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    branch TEXT,
    xp INTEGER DEFAULT 0
)
""")
conn.commit()

# =====================================
# QUESTIONS
# =====================================

questions_bank = {
    "علمي": [
        {"q": "اشتق س^2", "a": "2س"},
        {"q": "تكامل 2س د س", "a": "س^2"},
        {"q": "حل س^2 - 9 = 0", "a": "3,-3"},
        {"q": "حل 2س + 4 = 0", "a": "-2"},
        {"q": "نهاية س→0 لـ جا س / س", "a": "1"},
    ],
    "أدبي": [
        {"q": "احسب 20% من 150", "a": "30"},
        {"q": "حل 5س = 25", "a": "5"},
        {"q": "احسب 45 ÷ 5", "a": "9"},
        {"q": "حل س - 3 = 4", "a": "7"},
        {"q": "احسب 8 × 6", "a": "48"},
    ]
}

# =====================================
# HELPERS
# =====================================

def contains_latin(text):
    return re.search(r"[A-Za-z]", text) is not None

def clean_text(text):
    return re.sub(r"[A-Za-z]", "", text)

def detect_mode(text):
    if "اشرح" in text:
        return "شرح"
    if "حل" in text:
        return "حل"
    if "تمرين" in text or "مثال" in text:
        return "أمثلة"
    return "عام"

# =====================================
# QUIZ SESSION
# =====================================

sessions = {}
spam_tracker = {}

def is_spam(user_id):
    now = time.time()
    times = spam_tracker.get(user_id, [])
    times = [t for t in times if now - t < 5]
    times.append(now)
    spam_tracker[user_id] = times
    return len(times) > 6

# =====================================
# COMMANDS
# =====================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🔬 علمي"], ["📖 أدبي"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🎓 اختر الفرع:", reply_markup=markup)

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT branch FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text("اختر الفرع أولاً باستخدام /start")
        return

    branch = row[0]
    questions = random.sample(questions_bank[branch], 5)

    sessions[user_id] = {"questions": questions, "index": 0, "score": 0}

    await update.message.reply_text(f"📘 السؤال 1:\n{questions[0]['q']}")

# =====================================
# MAIN
# =====================================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if is_spam(user_id):
        await update.message.reply_text("🚫 تم إيقافك مؤقتاً.")
        return

    if text in ["🔬 علمي", "📖 أدبي"]:
        branch = "علمي" if "علمي" in text else "أدبي"
        cursor.execute("INSERT OR REPLACE INTO users (user_id, branch) VALUES (?,?)", (user_id, branch))
        conn.commit()
        await update.message.reply_text("✅ تم اختيار الفرع.\nاكتب /quiz أو اسأل.")
        return

    if user_id in sessions:
        session = sessions[user_id]
        q = session["questions"][session["index"]]

        if text.replace(" ", "") == q["a"].replace(" ", ""):
            session["score"] += 1
            await update.message.reply_text("✅ صحيح")
        else:
            await update.message.reply_text(f"❌ خطأ\nالإجابة: {q['a']}")

        session["index"] += 1

        if session["index"] < 5:
            await update.message.reply_text(
                f"📘 السؤال {session['index']+1}:\n{session['questions'][session['index']]['q']}"
            )
        else:
            await update.message.reply_text(f"🎉 انتهى الاختبار\nالنتيجة: {session['score']}/5")
            sessions.pop(user_id)
        return

    cursor.execute("SELECT branch FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    branch = row[0] if row else "علمي"

    mode = detect_mode(text)

    system_prompt = f"""
أنت مدرس رياضيات عراقي متخصص بمنهج السادس الإعدادي - فرع {branch}.

تعليمات صارمة:
- اكتب بالعربية الفصحى فقط.
- يمنع استخدام أي حرف لاتيني.
- تأكد من صحة العمليات الحسابية بدقة.
- لا تستخدم رموز تنسيق مثل النجوم.
- استخدم ترقيم منظم.

إذا كان الطلب شرح:
- تعريف مختصر.
- شرح واضح.
- مثال محلول صحيح بالكامل.

إذا كان الطلب حل:
- حل خطوة بخطوة.
- اكتب النتيجة النهائية بوضوح.

إذا كان الطلب أمثلة:
- أعط 3 تمارين مع الحل الصحيح.

الحد الأقصى 400 كلمة.
"""

    for _ in range(2):
        try:
            response = ai_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.2,
                max_tokens=800
            )

            reply = response.choices[0].message.content

            if not contains_latin(reply):
                await update.message.reply_text(reply)
                return
            else:
                reply = clean_text(reply)

        except Exception:
            await update.message.reply_text("⚠️ خطأ في الاتصال.")
            return

    await update.message.reply_text(reply)

# =====================================
# RUN
# =====================================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("🚀 Bot Running...")
app.run_polling()
