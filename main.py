import os
import json
import random
import telebot
from flask import Flask, request
from groq import Groq

# =========================
# إعدادات
# =========================

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
client = Groq(api_key=GROQ_API_KEY)

DATA_FILE = "data.json"

# =========================
# تحميل / حفظ البيانات
# =========================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users = load_data()

# =========================
# بنك الأسئلة حسب المرحلة
# =========================

question_bank = {
    "السادس ابتدائي": [
        ("كم يساوي 5 + 7؟", "12"),
        ("كم يساوي 9 × 3؟", "27"),
        ("ما هو ناتج 20 ÷ 4؟", "5"),
    ],
    "الثالث متوسط": [
        ("حل المعادلة: 2x + 4 = 10", "3"),
        ("بسّط: 3(2+4)", "18"),
        ("كم يساوي 6^2؟", "36"),
    ],
    "السادس الإعدادي": [
        ("ما مشتقة x^2؟", "2x"),
        ("حل المعادلة: x^2 = 16", "4"),
        ("كم يساوي sin(90)؟", "1"),
    ]
}

# =========================
# /start
# =========================

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("السادس ابتدائي", "الثالث متوسط", "السادس الإعدادي")
    bot.send_message(message.chat.id, "📚 اختر مرحلتك:", reply_markup=markup)

# =========================
# اختيار المرحلة
# =========================

@bot.message_handler(func=lambda m: m.text in question_bank.keys())
def choose_level(message):
    users[str(message.chat.id)] = {
        "level": message.text,
        "score": 0,
        "question_index": 0,
        "premium": False
    }
    save_data(users)
    bot.send_message(message.chat.id, f"✅ تم اختيار {message.text}\nاكتب /quiz لبدء الاختبار")

# =========================
# بدء اختبار
# =========================

@bot.message_handler(commands=['quiz'])
def quiz(message):
    user_id = str(message.chat.id)
    
    if user_id not in users:
        bot.send_message(message.chat.id, "اختر مرحلتك أولاً باستخدام /start")
        return
    
    users[user_id]["score"] = 0
    users[user_id]["question_index"] = 0
    save_data(users)
    
    send_question(message.chat.id)

def send_question(chat_id):
    user_id = str(chat_id)
    level = users[user_id]["level"]
    questions = question_bank[level]
    
    if users[user_id]["question_index"] >= 5:
        finish_quiz(chat_id)
        return
    
    question = random.choice(questions)
    users[user_id]["current_answer"] = question[1]
    users[user_id]["question_index"] += 1
    save_data(users)
    
    bot.send_message(chat_id, f"📘 السؤال {users[user_id]['question_index']}:\n{question[0]}")

def finish_quiz(chat_id):
    user_id = str(chat_id)
    score = users[user_id]["score"]
    
    rating = "👑 ممتاز" if score >= 4 else "👍 جيد" if score >= 2 else "📚 يحتاج مراجعة"
    
    bot.send_message(chat_id, f"🏁 انتهى الاختبار\n📊 نتيجتك: {score}/5\n{rating}")
    save_data(users)

# =========================
# الذكاء الصناعي (مدرس)
# =========================

def ask_ai(question, level):
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": f"أجب كمدرس رياضيات للمرحلة {level} فقط. لا تجب عن أي موضوع خارج الرياضيات."},
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content

# =========================
# استقبال الرسائل
# =========================

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    user_id = str(message.chat.id)
    
    if user_id in users and "current_answer" in users[user_id]:
        if message.text.strip() == users[user_id]["current_answer"]:
            users[user_id]["score"] += 1
            bot.send_message(message.chat.id, "✅ إجابة صحيحة")
        else:
            bot.send_message(message.chat.id, f"❌ خطأ\nالإجابة الصحيحة: {users[user_id]['current_answer']}")
        
        save_data(users)
        send_question(message.chat.id)
        return
    
    # مدرس الذكاء الصناعي
    if user_id in users:
        try:
            reply = ask_ai(message.text, users[user_id]["level"])
            bot.send_message(message.chat.id, reply)
        except:
            bot.send_message(message.chat.id, "⚠ حدث خطأ في المعالجة")

# =========================
# Webhook Railway
# =========================

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "Bot Running"

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
