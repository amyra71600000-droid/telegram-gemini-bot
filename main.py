import os
import sqlite3
import random
import time
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# =====================================
# Environment Variables
# =====================================

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN missing")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY missing")

ai_client = Groq(api_key=GROQ_API_KEY)

# =====================================
# Database Setup (Expandable Structure)
# =====================================

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

# =====================================
# Question Bank
# =====================================

questions_bank = {
    "علمي": [
        {"q": "اشتق x^2", "a": "2x"},
        {"q": "تكامل 2x dx", "a": "x^2"},
        {"q": "حل x^2 - 4 = 0", "a": "2,-2"},
        {"q": "نهاية x→0 لـ sinx/x", "a": "1"},
        {"q": "حل 2x + 6 = 0", "a": "-3"},
    ],
    "أدبي": [
        {"q": "احسب 15% من 200", "a": "30"},
        {"q": "حل 3x = 12", "a": "4"},
        {"q": "احسب 8 + 9", "a": "17"},
        {"q": "احسب 45 ÷ 5", "a": "9"},
        {"q": "حل x - 7 = 2", "a": "9"},
    ]
}

# =====================================
# Session Management
# =====================================

sessions = {}
spam_tracker = {}

# =====================================
# Anti-Spam
# =====================================

def is_spam(user_id):
    now = time.time()
    times = spam_tracker.get(user_id, [])
    times = [t for t in times if now - t < 5]
    times.append(now)
    spam_tracker[user_id] = times
    return len(times) > 6

# =====================================
# Levels System
# =====================================

def get_level(xp):
    if xp < 50:
        return "مبتدئ"
    elif xp < 150:
        return "متوسط"
    elif xp < 300:
        return "متقدم"
    else:
        return "خبير"

# =====================================
# Commands
# =====================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    keyboard = [["🔬 علمي"], ["📖 أدبي"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    sessions.pop(user_id, None)

    await update.message.reply_text(
        "🎓 منصة رياضيات السادس الإعدادي\nاختر فرعك:",
        reply_markup=markup
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT user_id, xp FROM users ORDER BY xp DESC LIMIT 10")
    top = cursor.fetchall()

    if not top:
        await update.message.reply_text("لا يوجد بيانات بعد.")
        return

    msg = "🏆 أفضل 10 طلاب:\n\n"
    for i, (uid, xp) in enumerate(top, 1):
        msg += f"{i}- ID:{uid} | XP: {xp}\n"

    await update.message.reply_text(msg)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT xp,total_quizzes,correct_answers FROM users WHERE user_id=?", (user_id,))
    data = cursor.fetchone()

    if not data:
        await update.message.reply_text("ابدأ أولاً باستخدام /start")
        return

    xp, quizzes, correct = data
    level = get_level(xp)
    accuracy = (correct / (quizzes * 5) * 100) if quizzes else 0

    await update.message.reply_text(
        f"📊 تقريرك:\n"
        f"XP: {xp}\n"
        f"المستوى: {level}\n"
        f"عدد الاختبارات: {quizzes}\n"
        f"نسبة النجاح: {accuracy:.1f}%"
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

# =====================================
# Main Message Handler
# =====================================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if is_spam(user_id):
        await update.message.reply_text("🚫 يرجى عدم الإرسال المتكرر.")
        return

    # Branch Selection
    if text in ["🔬 علمي", "📖 أدبي"]:
        branch = "علمي" if "علمي" in text else "أدبي"
        cursor.execute("INSERT OR IGNORE INTO users (user_id, branch) VALUES (?,?)", (user_id, branch))
        cursor.execute("UPDATE users SET branch=? WHERE user_id=?", (branch, user_id))
        conn.commit()

        await update.message.reply_text(
            f"تم اختيار {branch}\nاكتب /quiz لبدء اختبار\nاكتب سؤالك لشرح مباشر."
        )
        return

    # Quiz Mode
    if user_id in sessions:
        session = sessions[user_id]
        q = session["questions"][session["index"]]

        if text.lower() == q["a"].lower():
            session["score"] += 1
            await update.message.reply_text("✅ صحيح (+10 XP)")
        else:
            await update.message.reply_text(f"❌ خطأ\nالإجابة: {q['a']}")

        session["index"] += 1

        if session["index"] < 5:
            await update.message.reply_text(
                f"📘 السؤال {session['index']+1}:\n"
                f"{session['questions'][session['index']]['q']}"
            )
        else:
            score = session["score"]
            xp_gain = score * 10

            cursor.execute("""
            UPDATE users
            SET xp = xp + ?,
                total_quizzes = total_quizzes + 1,
                correct_answers = correct_answers + ?
            WHERE user_id=?
            """, (xp_gain, score, user_id))
            conn.commit()

            await update.message.reply_text(f"🎉 انتهى الاختبار\nنتيجتك: {score}/5\n+{xp_gain} XP")
            sessions.pop(user_id)

        return

    # AI Mode
    try:
        response = ai_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "أجب كمدرس رياضيات عراقي للسادس الإعدادي."},
                {"role": "user", "content": text}
            ]
        )
        await update.message.reply_text(response.choices[0].message.content)
    except:
        await update.message.reply_text("حدث خطأ في الذكاء الصناعي.")

# =====================================
# Run App
# =====================================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CommandHandler("profile", profile))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("🚀 Bot Running...")
app.run_polling()
