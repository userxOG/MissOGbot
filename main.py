import telebot
import openai
import os
import re
from flask import Flask, request
from dotenv import load_dotenv
from telebot import types
import threading
import time

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_KEY

# Special user for "baby" lock
SPECIAL_USER_ID = 8457816680

# Store user settings
user_languages = {}
user_nicknames = {}
waiting_for_language = {}
waiting_for_nickname = {}
user_data = {}

# Flask app
app = Flask(__name__)

def get_mention(message):
    user_id = message.from_user.id
    if user_id == SPECIAL_USER_ID:
        return "baby"
    if user_id in user_nicknames:
        return user_nicknames[user_id]
    if message.from_user.username:
        return f"@{message.from_user.username}"
    return message.from_user.first_name

# -------------------- /language command --------------------
@bot.message_handler(commands=['language'])
def set_language_cmd(message):
    if message.chat.type != "private":
        bot.reply_to(message, "❌ This command works only in private chat.")
        return
    waiting_for_language[message.from_user.id] = True
    bot.reply_to(message, "Which language do you want me to talk in? 🌐")

@bot.message_handler(func=lambda m: m.from_user.id in waiting_for_language)
def save_language(message):
    lang = message.text.strip()
    user_languages[message.from_user.id] = lang
    waiting_for_language.pop(message.from_user.id, None)
    waiting_for_nickname[message.from_user.id] = True
    bot.reply_to(message, "Got it! Now tell me, what should I call you? 📝")

@bot.message_handler(func=lambda m: m.from_user.id in waiting_for_nickname)
def save_nickname(message):
    name = message.text.strip()
    user_nicknames[message.from_user.id] = name
    waiting_for_nickname.pop(message.from_user.id, None)
    bot.reply_to(message, f"Done! I’ll call you {name} and talk in {user_languages.get(message.from_user.id)} 😏")

# -------------------- Start / Welcome --------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("➕ Add Me to Group", url="https://t.me/YourBotUsername?startgroup=true"),
        types.InlineKeyboardButton("📢 News", url="https://t.me/MissOG_News"),
        types.InlineKeyboardButton("💬 Talk More", callback_data="talk_more"),
        types.InlineKeyboardButton("🎮 Game (Soon)", callback_data="game_soon")
    )
    bot.send_message(message.chat.id,
                     "✨ Hello!\nI’m Miss OG — your loving, cheeky AI companion 😏",
                     reply_markup=markup)

# -------------------- Callback handler --------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    if call.data == "talk_more":
        waiting_for_language[user_id] = True
        bot.send_message(call.message.chat.id,
                         "Which language would you like to talk in? And what should I call you? 🤔\nReply like this:\nEnglish OG")
    elif call.data == "game_soon":
        bot.answer_callback_query(call.id, "🎮 Game feature coming soon, stay tuned!")
    else:
        bot.answer_callback_query(call.id, "Unknown option.")

# -------------------- Handle all messages --------------------
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    user_id = message.from_user.id
    mention = get_mention(message)
    lang = user_languages.get(user_id, "English")
    text = message.text.strip() if message.text else ""

    # Skip meaningless confirmations from language flow
    if user_id in user_languages and re.fullmatch(r"(ok|okay|sure|haan|haan ji)", text, re.I):
        bot.reply_to(message, f"Haan {mention}, chalo baat shuru karein 😏")
        return

    # Topic lock check
    locked_topic = user_data.get(user_id, {}).get("topic")
    if locked_topic:
        if re.search(r"\b(stop|change topic|end topic|exit)\b", text.lower()):
            user_data[user_id].pop("topic", None)
            bot.send_message(message.chat.id, "Okay, topic unlocked. What now? 😏")
        else:
            # Generate AI response
            try:
                completion = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system",
                               "content": f"Talk in short, loving, swaggy style in {lang}."},
                              {"role": "user", "content": text}]
                )
                reply = completion.choices[0].message["content"].strip()
                bot.send_message(message.chat.id, reply.replace("{name}", mention))
            except Exception as e:
                bot.send_message(message.chat.id, f"Error: {str(e)}")
        return

    # Triggered by mention or direct message
    triggers = ["miss og", "missog", "baby", f"@{bot.get_me().username.lower()}", "miss og bot"]
    is_triggered = any(t in text.lower() for t in triggers) or (message.reply_to_message and message.reply_to_message.from_user.username == bot.get_me().username)

    if is_triggered:
        try:
            completion = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "system",
                           "content": f"Talk in short, loving, swaggy style in {lang}."},
                          {"role": "user", "content": text}]
            )
            reply = completion.choices[0].message["content"].strip()
            bot.send_message(message.chat.id, reply.replace("{name}", mention))
        except Exception as e:
            bot.send_message(message.chat.id, f"Error: {str(e)}")
    else:
        if message.chat.type == "private":
            bot.send_message(message.chat.id, f"{mention}, please tag me or say 'MISS OG' to chat 😘")
        else:
            bot.send_message(message.chat.id, f"{mention}, please mention me or say 'MISS OG' to talk! 😘")

# -------------------- Inactivity checker --------------------
def remind_to_tag(user_id, chat_id, last_message_id):
    mention = get_mention(types.Message())
    messages = [
        f"{mention}, tag me or say 'MISS OG' to talk! 😘",
        f"Hey {mention}, don't forget to mention me or say 'MISS OG'! 😉"
    ]
    import random
    msg = random.choice(messages)
    bot.send_message(chat_id, msg, reply_to_message_id=last_message_id)

def user_inactive_checker():
    while True:
        now = time.time()
        for user_id, data in list(user_data.items()):
            last_active = data.get("last_active")
            chat_id = data.get("chat_id")
            last_message_id = data.get("last_message_id")
            topic = data.get("topic")
            if last_active and chat_id and last_message_id and topic:
                if now - last_active > 120:  # 2 minutes inactivity
                    remind_to_tag(user_id, chat_id, last_message_id)
                    user_data[user_id]["last_active"] = now + 180
        time.sleep(30)

threading.Thread(target=user_inactive_checker, daemon=True).start()

# -------------------- Flask webhook --------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "Miss OG is alive 💖"

if __name__ == "__main__":
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        webhook_url = f"{render_url}/{BOT_TOKEN}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"Webhook set to: {webhook_url}")
    else:
        print("RENDER_EXTERNAL_URL not found! Set webhook manually if needed.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
