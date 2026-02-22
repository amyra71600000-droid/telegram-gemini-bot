import os
import re
import ast
import random
import operator as op
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ==============================
# متغيرات Railway
# ==============================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN missing")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY missing")

client = Groq(api_key=GROQ_API_KEY)

# ==============================
# بنك الأسئلة
# ==============================

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
user_grades = {}

# ==============================
# نظام حل العمليات
# ==============================

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
            raise TypeError("عملية غير مدعومة")

    node = ast.parse(expr, mode='eval').body
    return eval_(node)

def is_math(text):
    return bool(re.fullmatch(r"[0-9\.\+\-\*\/\(\)\^ ]+", text))

# ==============================
# أوامر البوت
# ==============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["السادس ابتدائي"],
        ["الثالث متوسط"],
        ["السادس الإعدادي"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "📚 أهلاً بك في منصة الرياضيات!\n\nاختر مرحلتك الدراسية:",
        reply_markup=reply_markup
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in user_grades:
        await update.message.reply_text("⚠ اختر مرحلتك أولاً باستخدام /start")
        return

    grade = user_grades[user_id]
    selected_questions = random.sample(questions_bank[grade], 5)

    user_sessions[user_id] = {
        "questions": selected_questions,
        "current": 0,
        "score": 0
    }

    await update.message.reply_text(
        f"📘 السؤال 1 من 5:\n{selected_questions[0]['question']}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    user_id = update.message.from_user.id

    # حفظ المرحلة
    if user_text in questions_bank:
        user_grades[user_id] = user_text
        await update.message.reply_text(
            f"✅ تم اختيار {user_text}\nاكتب /quiz لبدء الاختبار."
        )
        return

    # نظام الاختبار
    if user_id in user_sessions:
        session = user_sessions[user_id]
        current_index = session["current"]
        correct_answer = session["questions"][current_index]["answer"]

        if user_text.lower() == correct_answer.lower():
            session["score"] += 1
            await update.message.reply_text("✅ إجابة صحيحة!")
        else:
            await update.message.reply_text(
                f"❌ إجابة خاطئة.\nالإجابة الصحيحة: {correct_answer}"
            )

        session["current"] += 1

        if session["current"] < 5:
            next_question = session["questions"][session["current"]]["question"]
            await update.message.reply_text(
                f"📘 السؤال {session['current'] + 1} من 5:\n{next_question}"
            )
        else:
            final_score = session["score"]

            ratings = {
                5: ("👑 ممتاز جداً", "أداء رائع! استمر هكذا."),
                4: ("⭐ جيد جداً", "قريب من الكمال!"),
                3: ("👍 جيد", "مستوى جيد لكن تحتاج مراجعة."),
                2: ("📚 يحتاج تحسين", "راجع الدروس الأساسية."),
            }

            rating, advice = ratings.get(
                final_score,
                ("⚠ ضعيف", "أعد دراسة الفصل ثم أعد الاختبار.")
            )

            await update.message.reply_text(
                f"🎓 انتهى الاختبار!\n\n"
                f"📊 نتيجتك: {final_score} من 5\n"
                f"{rating}\n"
                f"💡 {advice}"
            )

            del user_sessions[user_id]

        return

    # حل العمليات
    if is_math(user_text):
        try:
            expression = user_text.replace("^", "**")
            result = eval_expr(expression)
            await update.message.reply_text(f"📐 النتيجة: {result}")
            return
        except:
            pass

    # ذكاء صناعي
    try:
        grade = user_grades.get(user_id, "الثالث متوسط")

        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": f"أجب كمدرس رياضيات لمرحلة {grade} بشكل واضح ومختصر."},
                {"role": "user", "content": user_text}
            ]
        )

        reply = response.choices[0].message.content
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text("حدث خطأ أثناء المعالجة.")

# ==============================
# تشغيل البوت
# ==============================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("البوت يعمل...")
app.run_polling()
