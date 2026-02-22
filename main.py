import os
import re
import requests
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN missing")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY missing")

client = Groq(api_key=GROQ_API_KEY)

# 🔢 كشف سؤال رياضيات
def is_math_question(text):
    return bool(re.search(r"[\d\+\-\*/xX]", text))

def solve_math(text):
    try:
        cleaned = text.replace("x", "*").replace("X", "*")
        result = eval(cleaned)
        return f"الناتج هو: {result}"
    except:
        return None

# 🌍 البحث في ويكيبيديا
def search_wikipedia(query):
    url = "https://ar.wikipedia.org/api/rest_v1/page/summary/" + query
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get("extract")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 البوت الدراسي الاحترافي جاهز. اسأل أي سؤال.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    # 1️⃣ إذا رياضيات
    if is_math_question(user_text):
        result = solve_math(user_text)
        if result:
            await update.message.reply_text(result)
            return

    # 2️⃣ إذا معلومات عامة
    wiki_text = search_wikipedia(user_text)

    if not wiki_text:
        await update.message.reply_text("لم أجد معلومات موثوقة عن هذا الموضوع.")
        return

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

    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}")

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Level 3 Bot Running...")
app.run_polling()
