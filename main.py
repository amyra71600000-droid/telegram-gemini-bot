import os
import re
import requests
import ast
import operator as op
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# =============================
# إعداد المتغيرات
# =============================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN missing")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY missing")

client = Groq(api_key=GROQ_API_KEY)

# =============================
# 🔢 نظام رياضيات آمن
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
            return allowed_operators[type(node.op)](eval_(node.left), eval_(node.right))
        else:
            raise TypeError("عملية غير مسموحة")

    node = ast.parse(expr, mode='eval').body
    return eval_(node)

def is_math(text):
    return bool(re.search(r'^[0-9\.\+\-\*\/\(\) ]+$', text))

# =============================
# 🌍 بحث ويكيبيديا احترافي
# =============================

def search_wikipedia(query):
    try:
        search_url = "https://ar.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json"
        }

        search_response = requests.get(search_url, params=params, timeout=10)
        search_data = search_response.json()

        if not search_data["query"]["search"]:
            return None

        title = search_data["query"]["search"][0]["title"]

        summary_url = "https://ar.wikipedia.org/api/rest_v1/page/summary/" + title
        summary_response = requests.get(summary_url, timeout=10)

        if summary_response.status_code == 200:
            summary_data = summary_response.json()
            return summary_data.get("extract")

    except:
        return None

    return None

# =============================
# 🚀 أوامر البوت
# =============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 البوت الدراسي الاحترافي جاهز. اسأل ما تريد.")

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

    # 2️⃣ بحث ويكيبيديا
    wiki_text = search_wikipedia(user_text)

    if wiki_text:
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": "لخص النص التالي بدقة بدون إضافة أي معلومات خارج النص."
                    },
                    {
                        "role": "user",
                        "content": wiki_text
                    }
                ],
                temperature=0.2
            )

            reply = response.choices[0].message.content
            await update.message.reply_text(reply)
            return

        except Exception as e:
            await update.message.reply_text("حدث خطأ أثناء التلخيص.")
            return

    # 3️⃣ إذا لم يجد شيء
    await update.message.reply_text("لم أجد معلومات كافية عن هذا الموضوع.")

# =============================
# تشغيل البوت
# =============================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🚀 Level 3 Professional Bot Running...")
app.run_polling()
