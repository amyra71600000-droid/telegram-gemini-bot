import os
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# قراءة المتغيرات من Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# تفعيل Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 بوت Gemini يعمل بنجاح!\nأرسل لي أي سؤال.")

# الرد على الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    try:
        response = model.generate_content(user_message)

        if response and hasattr(response, "text") and response.text:
            await update.message.reply_text(response.text)
        else:
            await update.message.reply_text("لم يتم استلام رد من جيميني")

    except Exception as e:
        await update.message.reply_text(f"حصل خطأ:\n{e}")
