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
# ENV VARIABLES
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
    xp INTEGER DEFAULT 0,
    total_quizzes INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0
)
""")
conn.commit()

# =====================================
# QUESTIONS
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
# SESSION + ANTI SPAM
# =====================================

sessions = {}
spam_tracker = {}

def is_spam(user_id):
    now = time.time()
    times = spam_tracker.get(user_id, [])
    times = [t for t in times if now - t < 5]
    times.append(now)
    spam_tracker[user_id] = times
    return len(times) > 5

# =====================================
# LEVEL SYSTEM
# =====================================

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

# =====================================
# ANSWER CHECKER
# =====================================

def normalize(text):
    return text.replace(" ", "").lower()

def check_answer(user_input, correct_answer):
    user_input = normalize(user_input)
    correct_answer = normalize(correct_answer)

    if "," in correct_answer:
        return set(user_input.split(",")) == set(correct_answer.split(","))

    return user_input == correct_answer

# =====================================
# COMMANDS
# =====================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🔬 علمي"], ["📖 أدبي"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "🎓 منصة رياضيات السادس الإعدادي\nاختر فرعك للبدء:",
        reply_markup=markup
    )

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT xp,total_quizzes,correct_answers FROM users WHERE user_id=?", (user_id,))
    data = cursor.fetchone()

    if not data:
        await update.message.reply_text("ابدأ أولاً باستخدام /start")
        return

    xp, quizzes, correct = data
    level = get_level(xp)
    total_questions = quizzes * 5
    accuracy = (correct / total_questions * 100) if total_questions else 0

    await update.message.reply_text(
        f"📊 ملفك:\n"
        f"XP: {xp}\n"
        f"المستوى: {level}\n"
        f"الاختبارات: {quizzes}\n"
        f"الدقة: {accuracy:.1f}%"
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT user_id, xp FROM users ORDER BY xp DESC LIMIT 10")
    top = cursor.fetchall()

    msg = "🏆 أفضل 10 طلاب:\n\n"
    for i, (uid, xp) in enumerate(top, 1):
        msg += f"{i}- {uid} | {xp} XP\n"

    await update.message.reply_text(msg)

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
# MAIN HANDLER
# =====================================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if is_spam(user_id):
        await update.message.reply_text("🚫 تم إيقافك مؤقتاً بسبب الإرسال المتكرر.")
        return

    # Branch
    if text in ["🔬 علمي", "📖 أدبي"]:
        branch = "علمي" if "علمي" in text else "أدبي"

        cursor.execute("INSERT OR IGNORE INTO users (user_id, branch) VALUES (?,?)", (user_id, branch))
        cursor.execute("UPDATE users SET branch=? WHERE user_id=?", (branch, user_id))
        conn.commit()

        await update.message.reply_text(
            f"✅ تم اختيار {branch}\n"
            "اكتب /quiz لبدء اختبار\n"
            "أو اكتب سؤالك لشرح مباشر."
        )
        return

    # Quiz mode
    if user_id in sessions:
        session = sessions[user_id]
        q = session["questions"][session["index"]]

        if check_answer(text, q["a"]):
            session["score"] += 1
            await update.message.reply_text("✅ إجابة صحيحة (+10 XP)")
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

            # Bonus XP
            if score == 5:
                xp_gain += 20
            elif score >= 4:
                xp_gain += 10

            cursor.execute("""
            UPDATE users
            SET xp = xp + ?,
                total_quizzes = total_quizzes + 1,
                correct_answers = correct_answers + ?
            WHERE user_id=?
            """, (xp_gain, score, user_id))
            conn.commit()

            await update.message.reply_text(
                f"🎉 انتهى الاختبار\n"
                f"النتيجة: {score}/5\n"
                f"+{xp_gain} XP"
            )

            sessions.pop(user_id)

        return

    # =====================================
    # AI MODE (Dynamic System by Branch)
    # =====================================

    cursor.execute("SELECT branch FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    branch = row[0] if row else "علمي"

    system_prompt = f"""
أنت مدرس رياضيات عراقي متخصص بمنهج السادس الإعدادي - فرع {branch}.

قواعد:
- اكتب بالعربية الفصحى فقط.
- اشرح خطوة بخطوة.
- لا تكتب مقدمة طويلة.
- استخدم مثال تطبيقي إذا لزم.
- اجعل الشرح واضح ومختصر.
- الحد الأقصى 250 كلمة.
"""

    try:
        response = ai_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=600
        )

        reply = response.choices[0].message.content
        await update.message.reply_text(reply)

    except Exception as e:
        print("AI ERROR:", e)
        await update.message.reply_text("⚠️ حدث خطأ في الاتصال.")

# =====================================
# RUN
# =====================================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CommandHandler("profile", profile))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("🚀 Bot Running...")
app.run_polling()
