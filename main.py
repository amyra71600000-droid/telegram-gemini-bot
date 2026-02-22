import os
import re
import ast
import random
import operator as op
from groq import Groq
from telegram import Update
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

questions_bank = [
    {"question": "حل المعادلة: 2x + 4 = 10", "answer": "3"},
    {"question": "حل المعادلة: 3x = 15", "answer": "5"},
    {"question": "إذا كان محيط المربع 20 فما طول الضلع؟", "answer": "5"},
    {"question": "بسّط: 3(2 + 4)", "answer": "18"},
    {"question": "حل المعادلة: x - 7 = 3", "answer": "10"},
    {"question": "كم يساوي 5^2؟", "answer": "25"},
]

user_sessions = {}

# ==============================
# نظام حل العمليات الحسابية
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
    await update.message.reply_text(
        "🤖 البوت الدراسي جاهز!\n\n"
        "يمكنك:\n"
        "• حل مسائل رياضيات (مثال: 2+3*5)\n"
        "• كتابة /quiz لبدء اختبار"
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    selected_questions = random.sample(questions_bank, 5)

    user_sessions[user_id] = {
        "questions": selected_questions,
        "current": 0,
        "score": 0
    }

    first_question = selected_questions[0]["question"]

    await update.message.reply_text(
        f"📘 السؤال 1 من 5:\n{first_question}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    user_id = update.message.from_user.id

    # ==========================
    # نظام الاختبار
    # ==========================
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
            await update.message.reply_text(
                f"🎓 انتهى الاختبار!\nنتيجتك: {final_score} / 5"
            )
            del user_sessions[user_id]

        return

    # ==========================
    # حل العمليات الحسابية
    # ==========================
    if is_math(user_text):
        try:
            expression = user_text.replace("^", "**")
            result = eval_expr(expression)
            await update.message.reply_text(f"📐 النتيجة: {result}")
            return
        except:
            pass

    # ==========================
    # ذكاء صناعي للأسئلة النظرية
    # ==========================
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": "أجب كمدرس للصف الثالث متوسط بشكل واضح ومختصر."},
                {"role": "user", "content": user_text}
            ]
        )

        reply = response.choices[0].message.content
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text("حصل خطأ في المعالجة.")

# ==============================
# تشغيل البوت
# ==============================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("البوت يعمل...")
app.run_polling()
