import telebot
import openai
import os
import re
from flask import Flask, request
from dotenv import load_dotenv
from telebot import types
from langdetect import detect

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_KEY

BOT_NAME = "Miss OG"
BOT_ABOUT = "Elegant group manager. Sweet, smart & made with love by OG. Here to upgrade your chats with class."
BOT_DESC = "Hello! I'm Miss OG, your elegant Telegram companion. Here to help you manage your groups smartly, respond sweetly when called, and bring calm & class to every chat."
BOT_UPDATES = "@MissOG_News"
BOT_CLONE = "@MissOG_CloneBot"
OWNER_USERNAME = "userxOG"  # Without @

# Expanded abusive words in multiple languages
ABUSIVE_WORDS = {
    "randi", "madrchd", "bhosdike", "lund", "chutiya", "bitch", "asshole", "mf",
    "bc", "mc", "bkl", "fuck", "shit", "slut", "idiot", "harami", "kutte", "kamine",
    "сука", "блядь", "пидор", "puta", "mierda", "imbécil", "cabrón"
}

user_data = {}  # Store language, nickname, warnings, topic lock

def is_abusive(text):
    t = text.lower()
    return any(w in t for w in ABUSIVE_WORDS)

def get_nickname(user_id):
    return user_data.get(user_id, {}).get("nickname", f"{user_id}")

def handle_owner_query(message):
    text = message.text.lower()
    triggers = [
        "owner", "creator", "who made you", "kisne banaya", "malik", "creator kaun",
        "baby", "hubby", "husband", "jaanu", "patidev"
    ]
    if any(t in text for t in triggers) or OWNER_USERNAME.lower() in text:
        if message.from_user.username and message.from_user.username.lower() == OWNER_USERNAME.lower():
            return "You ❤️"
        else:
            return f"Nice try 😏 But my baby is @{OWNER_USERNAME} only. You can be a friend tho 😘"
    return None

def language_mismatch(user_id, text):
    chosen_lang = user_data.get(user_id, {}).get("language")
    if not chosen_lang:
        return False
    try:
        detected = detect(text)
        if chosen_lang.lower() == "english" and detected != "en":
            return True
        if chosen_lang.lower() == "hindi" and detected != "hi":
            return True
    except:
        pass
    return False

def generate_ai_response(prompt, user_id):
    nickname = get_nickname(user_id)
    system_prompt = (
        f"You are Miss OG, a loving but slightly savage AI assistant with desi swag. "
        f"Address the user as {nickname}. Use emojis and expressive, slightly aggressive language. "
        f"Keep answers short and sweet. Always end with a friendly question to keep the conversation going."
    )
    completion = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150,
        temperature=0.9,
        n=1,
    )
    return completion.choices[0].message.content.strip()

# Welcome message for private/group
def send_welcome(chat_id, is_group=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    bot_username = bot.get_me().username
    markup.add(
        types.InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_username}?startgroup=true"),
        types.InlineKeyboardButton("📢 MissOG_News", url="https://t.me/MissOG_News"),
        types.InlineKeyboardButton("💬 Talk More", callback_data="talk_more"),
        types.InlineKeyboardButton("🎮 Game (Soon)", callback_data="game_soon"),
    )
    intro = (
        f"👋 Hey! Welcome to Miss OG Bot!\n\n"
        f"I'm your loving, caring, slightly savage AI assistant. "
        f"Click below to add me to your group, get the latest news, chat more, or try games soon! 😘"
    )
    if is_group:
        intro = f"Hello Group! 🎉 I’m {BOT_NAME} — {BOT_ABOUT}\n\n" + intro
    bot.send_message(chat_id, intro, reply_markup=markup)

@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    if message.chat.type == "private":
        send_welcome(message.chat.id, is_group=False)
    else:
        send_welcome(message.chat.id, is_group=True)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    if call.data == "talk_more":
        username = call.from_user.username or ""
        suggested_name = username if username else "your name"
        msg = f"Which language would you like to talk in? And what should I call you? 🤔\n\nReply like this:\nEnglish {suggested_name}"
        user_data[user_id] = user_data.get(user_id, {})
        user_data[user_id]["awaiting_lang_nick"] = True
        bot.send_message(call.message.chat.id, msg)
    elif call.data == "game_soon":
        bot.answer_callback_query(call.id, "🎮 Game feature coming soon, stay tuned!")
    else:
        bot.answer_callback_query(call.id, "Unknown option.")

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""

    # Owner query handling
    owner_reply = handle_owner_query(message)
    if owner_reply:
        bot.send_message(message.chat.id, owner_reply)
        return

    # Language + nickname setup
    if user_data.get(user_id, {}).get("awaiting_lang_nick"):
        parts = text.split()
        if len(parts) >= 2:
            lang = parts[0]
            nickname = " ".join(parts[1:]).replace("@", "")
            user_data[user_id]["language"] = lang
            user_data[user_id]["nickname"] = nickname
            user_data[user_id]["awaiting_lang_nick"] = False
            bot.send_message(message.chat.id, f"Alright {nickname}, I'll chat with you in {lang}. 😘", reply_to_message_id=message.message_id)
        else:
            bot.send_message(message.chat.id, "Please provide both language and nickname, e.g.,\nEnglish John")
        return

    # Language mismatch reminder
    if language_mismatch(user_id, text):
        chosen_lang = user_data[user_id]["language"]
        bot.send_message(message.chat.id, f"You chose {chosen_lang} 😏 Speak in it, or tell me if you want to change.")
        return

    # Abusive word handling
    if is_abusive(text):
        warned = user_data.get(user_id, {}).get("warned", False)
        if not warned:
            bot.send_message(message.chat.id, "Hey! Don't use bad words! 😠 Do it again and I won't talk to you.")
            user_data.setdefault(user_id, {})["warned"] = True
        return
    else:
        if user_data.get(user_id, {}).get("warned"):
            user_data[user_id]["warned"] = False

    # Topic lock mode
    if re.search(r"(let'?s talk about|let's play|baat kare|game khele)", text.lower()):
        topic = text
        user_data[user_id]["topic"] = topic
        bot.send_message(message.chat.id, f"Alright, we’re sticking to this topic: {topic} 😉")
        return
    if "topic" in user_data.get(user_id, {}) and not re.search(r"(stop|change topic)", text.lower()):
        ai_reply = generate_ai_response(text, user_id)
        bot.send_message(message.chat.id, ai_reply)
        return
    elif re.search(r"(stop|change topic)", text.lower()):
        user_data[user_id].pop("topic", None)
        bot.send_message(message.chat.id, "Okay, topic unlocked. What now? 😏")
        return

    # Normal reply triggers
    triggers = ["miss og", "missog", "baby", f"@{bot.get_me().username.lower()}", "miss og bot"]
    if any(t in text.lower() for t in triggers) or (message.reply_to_message and message.reply_to_message.from_user.username == bot.get_me().username):
        ai_reply = generate_ai_response(text, user_id)
        bot.send_message(message.chat.id, ai_reply)
    else:
        if message.chat.type == "private":
            bot.send_message(message.chat.id, f"{get_nickname(user_id)}, mention me or say 'MISS OG' to talk 😘", reply_to_message_id=message.message_id)

# Flask app for webhook
app = Flask(__name__)

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
