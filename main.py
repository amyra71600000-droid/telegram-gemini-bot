import os
import re
import ast
import sqlite3
import random
import time
import operator as op
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===============================
# متغيرات Railway
# ===============================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN missing")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY missing")

client = Groq(api_key=GROQ_API_KEY)

# ===============================
# قاعدة البيانات SQLite
# ===============================

conn = sqlite3.connect("students.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    grade TEXT,
    total_quizzes INTEGER DEFAULT 0,
    total_score INTEGER DEFAULT 0,
    best_score INTEGER DEFAULT 0
)
""")
conn.commit()

# ===============================
# بنك الأسئلة
# ===============================

questions_bank = {
    "السادس ابتدائي": [
        {"question": "كم يساوي 5 × 6؟", "answer": "30"},
        {"question": "احسب: 12 ÷ 3", "answer": "4"},
        {"question": "كم يساوي 7 + 8؟", "answer": "15"},
        {"question": "ما هو مربع العدد 4؟", "answer": "16"},
        {"question": "احسب: 9 - 3", "answer": "6"},
    ],
    "الثالث متوسط": [
        {"question": "حل المعادلة: 2x + 4 = 10", "answer": "3"},
        {"question": "حل المعادلة: 3x = 15", "answer": "5"},
        {"question": "بسّط: 3(2 + 4)", "answer": "18"},
        {"question": "حل المعادلة: x - 7 = 3", "answer": "10"},
        {"question": "كم يساوي 5^2؟", "answer": "25"},
    ],
    "السادس الإعدادي": [
        {"question": "اشتق: x^2", "answer": "2x"},
        {"question": "تكامل: 2x dx", "answer": "x^2"},
        {"question": "حل: x^2 - 9 = 0", "answer": "3,-3"},
        {"question": "إذا كان sin 30° = ؟", "answer": "0.5"},
        {"question": "حل المعادلة: 2x - 4 = 0", "answer": "2"},
    ]
}

user_sessions = {}
user_message_times = {}

# ===============================
# حماية سبام
# ===============================

def is_spamming(user_id):
    now = time.time()
    times = user_message_times.get(user_id, [])
    times = [t for t in times if now - t < 5]
    times.append(now)
    user_message_times[user_id] = times
    return len(times) > 5

# ===============================
# نظام العمليات الحسابية
# ===============================

allowed_operators = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
}

def eval_expr(expr):
    def eval_(node):
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.BinOp):
            return allowed_operators[type(node.op)](
                eval_(node.left),
                eval_(node.right)
            )
        else:
            raise TypeError
    node = ast.parse(expr, mode='eval').body
    return eval_(node)

def is_math(text):
    return bool(re.fullmatch(r"[0-9.+\-*/^ ]+", text))

# ===============================
# الأوامر
# ===============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["السادس ابتدائي"],
        ["الثالث متوسط"],
        ["السادس الإعدادي"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "📚 أهلاً بك في منصة الرياضيات!\nاختر مرحلتك:",
        reply_markup=reply_markup
    )

async def mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    cursor.execute("SELECT total_quizzes, total_score, best_score FROM users WHERE user_id=?",(user_id,))
    data = cursor.fetchone()

    if not data:
        await update.message.reply_text("📊 لا توجد بيانات بعد. ابدأ اختباراً أولاً.")
        return

    total_quizzes, total_score, best_score = data
    avg = total_score / total_quizzes if total_quizzes else 0

    await update.message.reply_text(
        f"📊 إحصائياتك:\n\n"
        f"عدد الاختبارات: {total_quizzes}\n"
        f"أفضل نتيجة: {best_score}/5\n"
        f"متوسط الأداء: {avg:.2f}"
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    cursor.execute("SELECT grade FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text("⚠ اختر مرحلتك أولاً.")
        return

    grade = row[0]
    selected = random.sample(questions_bank[grade], 5)

    user_sessions[user_id] = {
        "questions": selected,
        "current": 0,
        "score": 0
    }

    await update.message.reply_text(f"📘 السؤال 1:\n{selected[0]['question']}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if is_spamming(user_id):
        await update.message.reply_text("🚫 تم إيقافك مؤقتاً بسبب الإرسال المتكرر.")
        return

    # اختيار مرحلة
    if text in questions_bank:
        cursor.execute("INSERT OR IGNORE INTO users (user_id, grade) VALUES (?,?)",(user_id,text))
        cursor.execute("UPDATE users SET grade=? WHERE user_id=?",(text,user_id))
        conn.commit()
        await update.message.reply_text(f"✅ تم اختيار {text}\nاكتب /quiz للبدء.")
        return

    # جلسة اختبار
    if user_id in user_sessions:
        session = user_sessions[user_id]
        q = session["questions"][session["current"]]
        correct = q["answer"]

        if text.lower() == correct.lower():
            session["score"] += 1
            await update.message.reply_text("✅ صحيح")
        else:
            await update.message.reply_text(f"❌ خطأ\nالإجابة: {correct}")

            # شرح ذكي
            try:
                explanation = client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[
                        {"role":"system","content":"اشرح الحل بشكل مختصر وبسيط."},
                        {"role":"user","content":q["question"]}
                    ]
                )
                await update.message.reply_text("🧠 شرح:\n"+explanation.choices[0].message.content)
            except:
                pass

        session["current"] += 1

        if session["current"] < 5:
            await update.message.reply_text(
                f"📘 السؤال {session['current']+1}:\n"
                f"{session['questions'][session['current']]['question']}"
            )
        else:
            score = session["score"]

            cursor.execute("""
            UPDATE users
            SET total_quizzes = total_quizzes + 1,
                total_score = total_score + ?,
                best_score = MAX(best_score, ?)
            WHERE user_id=?
            """,(score,score,user_id))
            conn.commit()

            await update.message.reply_text(f"🎓 انتهى الاختبار\nنتيجتك: {score}/5\nاكتب /mystats لرؤية مستواك.")
            del user_sessions[user_id]
        return

    # عمليات حسابية
    if is_math(text):
        try:
            result = eval_expr(text.replace("^","**"))
            await update.message.reply_text(f"📐 النتيجة: {result}")
            return
        except:
            pass

    # ذكاء صناعي عام
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role":"system","content":"أجب كمدرس رياضيات بشكل واضح."},
                {"role":"user","content":text}
            ]
        )
        await update.message.reply_text(response.choices[0].message.content)
    except:
        await update.message.reply_text("حدث خطأ.")

# ===============================
# تشغيل
# ===============================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(CommandHandler("mystats", mystats))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("البوت الاحترافي يعمل...")
app.run_polling()
