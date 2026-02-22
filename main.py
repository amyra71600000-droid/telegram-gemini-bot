import os
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# قراءة المتغيرات من Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# تفعيل Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

# أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 بوت Gemini يعمل بنجاح!\nأرسل لي أي سؤال.")

# الرد على الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash-latest",
            contents=user_message
        )

        if response.text:
            await update.message.reply_text(response.text)
        else:
            await update.message.reply_text("لم يتم استلام رد من جيميني")

    except Exception as e:
        await update.message.reply_text(f"حصل خطأ:\n{e}")

# تشغيل البوت
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("البوت يعمل...")
app.run_polling()
