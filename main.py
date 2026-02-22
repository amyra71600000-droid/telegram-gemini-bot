import os
import re
import ast
import operator as op
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# =============================
# المتغيرات من Railway
# =============================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN missing")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY missing")

client = Groq(api_key=GROQ_API_KEY)

# =============================
# نظام رياضيات آمن
# =============================

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
            raise TypeError("عملية غير مسموحة")

    node = ast.parse(expr, mode='eval').body
    return eval_(node)

def is_math(text):
    return bool(re.fullmatch(r"[0-9\.\+\-\*\/\(\) ]+", text))

# =============================
# أوامر البوت
# =============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 البوت الدراسي جاهز.\n"
        "يمكنك:\n"
        "• حل مسائل رياضيات (مثال: 5+3*2)\n"
        "• طرح أي سؤال دراسي"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    # 1️⃣ رياضيات
    if is_math(user_text):
        try:
            result = eval_expr(user_text)
            await update.message.reply_text(f"الناتج هو: {result}")
            return
        except:
            pass

    # 2️⃣ سؤال دراسي باستخدام Groq
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "أنت مساعد دراسي ذكي. أجب بإجابة واضحة ومختصرة ومفهومة للطلاب."
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ],
            temperature=0.3,
        )

        reply = response.choices[0].message.content
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text("حدث خطأ مؤقت، حاول مرة أخرى.")

# =============================
# تشغيل البوت
# =============================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🚀 Study Bot Running...")
app.run_polling()
