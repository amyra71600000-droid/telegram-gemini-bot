import os
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# قراءة المتغيرات من Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# تأكد أن المفاتيح موجودة
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN غير موجود في Variables")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY غير موجود في Variables")

client = Groq(api_key=GROQ_API_KEY)

# رسالة البداية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك في البوت الدراسي الذكي!\n"
        "📚 أرسل سؤالك وسأجيب بدقة.\n"
        "✍️ مثال: من هو صلاح الدين الأيوبي؟"
    )

# معالجة الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": """أنت مدرس تاريخ دقيق جداً.
لا تخمّن أبداً.
إذا لم تكن متأكد من معلومة قل لا أعلم.
اكتب التواريخ بشكل صحيح (سنة الولادة ثم سنة الوفاة).
أعطِ معلومات مؤكدة فقط وبأسلوب واضح ومختصر."""
                },
                {"role": "user", "content": user_text}
            ],
            temperature=0.2
        )

        reply = response.choices[0].message.content
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ:\n{e}")

# تشغيل التطبيق
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("✅ Bot is running...")
app.run_polling()
