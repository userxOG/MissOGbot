import telebot
import openai
import os
import re
from flask import Flask, request
from dotenv import load_dotenv
from telebot import types
from langdetect import detect
import threading
import time

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_KEY

BOT_NAME = "Miss OG"
OWNER_USERNAME = "userxOG"  # Without @

# Expanded abusive words in multiple languages
ABUSIVE_WORDS = {
    "randi", "madrchd", "bhosdike", "lund", "chutiya", "bitch", "asshole", "mf",
    "bc", "mc", "bkl", "fuck", "shit", "slut", "idiot", "harami", "kutte", "kamine",
    "сука", "блядь", "пидор", "puta", "mierda", "imbécil", "cabrón"
}

user_data = {}  # Stores: language, nickname (CAPS), warnings, topic lock, last_active, awaiting_lang_nick

def is_abusive(text):
    t = text.lower()
    return any(w in t for w in ABUSIVE_WORDS)

def get_nickname(user_id):
    name = user_data.get(user_id, {}).get("nickname")
    if name:
        return name.capitalize()
    # fallback to Telegram username if exists
    try:
        user = bot.get_chat(user_id)
        if user.username:
            return user.username.capitalize()
    except Exception:
        pass
    return "Baby"

def handle_owner_query(message):
    text = message.text.lower()
    triggers = [
        "owner", "creator", "who made you", "kisne banaya", "malik", "creator kaun",
        "baby", "hubby", "husband", "jaanu", "patidev", "bf", "boyfriend", "partner", "bae"
    ]
    if any(t in text for t in triggers) or OWNER_USERNAME.lower() in text:
        if message.from_user.username and message.from_user.username.lower() == OWNER_USERNAME.lower():
            return "You ❤️"
        else:
            # cheeky shade for others
            return f"Nice try 😏 But my baby is @{OWNER_USERNAME} only. You can be a friend tho 😘"
    return None

def language_mismatch(user_id, text):
    chosen_lang = user_data.get(user_id, {}).get("language")
    if not chosen_lang:
        return False
    try:
        detected = detect(text)
        chosen = chosen_lang.lower()
        # Simple mapping for English and Hindi only, add more if needed
        if chosen == "english" and detected != "en":
            return True
        if chosen == "hindi" and detected != "hi":
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
    try:
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
    except Exception as e:
        print("API Error:", e)
        return "Oops! Some technical issue happened, try again later. 😓"

def send_welcome(chat_id, is_group=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    bot_username = bot.get_me().username
    markup.add(
        types.InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_username}?startgroup=true"),
        types.InlineKeyboardButton("📢 MissOG_News", url="https://t.me/MissOG_News"),
        types.InlineKeyboardButton("💬 Talk More", callback_data="talk_more"),
        types.InlineKeyboardButton("🎮 Game (Soon)", callback_data="game_soon"),
    )
    if is_group:
        intro = (
            "✨️ Hello Group!\n"
            "I’m Miss OG — your elegant, loving & cheeky AI companion made with love by @userxOG ❤️\n"
            "Here to upgrade your chats with style, fun, and just the right amount of sass.\n\n"
            "Click below to add me to more groups, get the latest news, chat more, or explore games. \n"
        )
    else:
        intro = (
            "👋 Hey! Welcome to Miss OG Bot!\n"
            "I’m Miss OG — your elegant, loving & cheeky AI companion made with love by @userxOG ❤️\n"
            "Here to upgrade your chats with style, fun, and just the right amount of sass.\n\n"
            "Click below to add me to more groups, get the latest news, chat more, or explore games. \n"
        )
    bot.send_message(chat_id, intro, reply_markup=markup)

def mention_user(message):
    user_id = message.from_user.id
    nickname = get_nickname(user_id)
    # reply with mention in capitalized form
    bot_username = message.from_user.username
    if bot_username:
        mention = f"@{bot_username}"
    else:
        mention = nickname
    return mention

def remind_to_tag(user_id, chat_id, last_message_id):
    nickname = get_nickname(user_id)
    messages = [
        f"{nickname}, tag me or say 'MISS OG' to talk! 😘",
        f"Hey {nickname}, don't forget to mention me or say 'MISS OG'! 😉",
        f"{nickname}, you gotta tag me or call me 'MISS OG' to keep chatting! 😏",
        f"{nickname}, tag me please or say 'MISS OG' so I know you're talking to me! 😘"
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
                    # Update last_active so message not spammed continuously
                    user_data[user_id]["last_active"] = now + 180  # wait 3 mins more
        time.sleep(30)

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
        username = call.from_user.username or "yourname"  # asli username, case preserved
        msg = (
            "Which language would you like to talk in? And what should I call you? 🤔\n\n"
            f"Reply like this:\nEnglish {username}"
        )
        user_data[user_id] = user_data.get(user_id, {})
        user_data[user_id]["awaiting_lang_nick"] = True
        bot.send_message(call.message.chat.id, msg)
    elif call.data == "game_soon":
        bot.answer_callback_query(call.id, "🎮 Game feature coming soon, stay tuned!")
    else:
        bot.answer_callback_query(call.id, "Unknown option.")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""

    # Update last_active and chat info for inactivity tracking
    user_data.setdefault(user_id, {})
    user_data[user_id]["last_active"] = time.time()
    user_data[user_id]["chat_id"] = message.chat.id
    user_data[user_id]["last_message_id"] = message.message_id

    # Language + nickname setup
    if user_data.get(user_id, {}).get("awaiting_lang_nick"):
        parts = text.split()
        if len(parts) >= 2:
            lang = parts[0]
            nickname_raw = " ".join(parts[1:]).replace("@", "")
            nickname = nickname_raw.capitalize()  # first letter capital, rest small
            user_data[user_id]["language"] = lang
            user_data[user_id]["nickname"] = nickname
            user_data[user_id]["awaiting_lang_nick"] = False
            bot.send_message(message.chat.id, f"Alright {nickname}, I'll chat with you in {lang}. 😘", reply_to_message_id=message.message_id)
        else:
            bot.send_message(message.chat.id, "Please provide both language and nickname, e.g.,\nEnglish John")
        return

    # Owner query handling
    owner_reply = handle_owner_query(message)
    if owner_reply:
        bot.send_message(message.chat.id, owner_reply)
        return

    # Language mismatch reminder
    if language_mismatch(user_id, text):
        chosen_lang = user_data[user_id]["language"]
        bot.send_message(message.chat.id, f"You chose {chosen_lang} 😏 Please speak only in that language or tell me if you want to change.")
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
    locked_topic = user_data.get(user_id, {}).get("topic")
    if locked_topic:
        # If user sends stop/change topic
        if re.search(r"\b(stop|change topic|end topic|exit)\b", text.lower()):
            user_data[user_id].pop("topic", None)
            bot.send_message(message.chat.id, "Okay, topic unlocked. What now? 😏")
            return
        else:
            # Reply in topic only, no other random talk
            ai_reply = generate_ai_response(text, user_id)
            bot.send_message(message.chat.id, ai_reply, reply_to_message_id=message.message_id)
            return

    # Detect topic start phrases to lock topic
    if re.search(r"\b(let'?s talk about|let's play|baat kare|game khele|play game|talk about)\b", text.lower()):
        user_data[user_id]["topic"] = text
        bot.send_message(message.chat.id, f"Alright, we’re sticking to this topic: {text} 😉", reply_to_message_id=message.message_id)
        return

    # Reply triggers
    triggers = ["miss og", "missog", "baby", f"@{bot.get_me().username.lower()}", "miss og bot"]

    is_triggered = any(t in text.lower() for t in triggers) or (message.reply_to_message and message.reply_to_message.from_user.username == bot.get_me().username)

    if is_triggered:
        ai_reply = generate_ai_response(text, user_id)
        bot.send_message(message.chat.id, ai_reply, reply_to_message_id=message.message_id)
    else:
        if message.chat.type == "private":
            nick = get_nickname(user_id)
            bot.send_message(message.chat.id, f"{nick}, please tag me or say 'MISS OG' to chat 😘", reply_to_message_id=message.message_id)
        else:
            # In groups, remind user to tag or say MISS OG, tagging with nickname
            nick = get_nickname(user_id)
            bot.send_message(message.chat.id, f"{nick}, please mention me or say 'MISS OG' to talk! 😘", reply_to_message_id=message.message_id)

# Background thread to check inactivity for tagging reminder
threading.Thread(target=user_inactive_checker, daemon=True).start()

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
