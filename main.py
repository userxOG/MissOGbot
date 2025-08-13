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
import random

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_KEY

BOT_NAME = "Miss OG"
OWNER_USERNAME = "userxOG"  # Without @, special ID to identify as baby

ABUSIVE_WORDS = {
    "randi", "madrchd", "bhosdike", "lund", "chutiya", "bitch", "asshole", "mf",
    "bc", "mc", "bkl", "fuck", "shit", "slut", "idiot", "harami", "kutte", "kamine",
    "сука", "блядь", "пидор", "puta", "mierda", "imbécil", "cabrón"
}

user_data = {}  # Stores: language, nickname, warnings, topic lock, last_active, awaiting_lang_nick

SPECIAL_USER_ID = 8457816680  # Set your Telegram numeric user id

def is_abusive(text):
    t = text.lower()
    return any(w in t for w in ABUSIVE_WORDS)

def format_nickname(nickname):
    if len(nickname) > 1:
        return nickname[0].upper() + nickname[1:].lower()
    else:
        return nickname.upper()

def get_user_display_name(message):
    first = message.from_user.first_name or ""
    last = message.from_user.last_name or ""
    full_name = (first + " " + last).strip()
    return full_name if full_name else "User"

def get_username_or_display(message):
    username = message.from_user.username
    if username:
        return "@" + username
    return get_user_display_name(message)

def get_nickname(user_id):
    data = user_data.get(user_id, {})
    nickname = data.get("nickname")
    return format_nickname(nickname) if nickname else None

def get_mention(message):
    user_id = message.from_user.id
    if SPECIAL_USER_ID is not None and user_id == SPECIAL_USER_ID:
        return "baby"
    nickname = get_nickname(user_id)
    if nickname:
        return nickname
    return get_username_or_display(message)

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
            return f"Nice try 😏 But my baby is @{OWNER_USERNAME} only. You can be a friend tho 😘"
    return None

def language_mismatch(user_id, text):
    chosen_lang = user_data.get(user_id, {}).get("language")
    if not chosen_lang:
        return False
    try:
        detected = detect(text)
        chosen = chosen_lang.lower()
        if chosen == "english" and detected != "en":
            return True
        if chosen == "hindi" and detected != "hi":
            return True
        if chosen == "hinglish" and detected not in ["en", "hi"]:
            return True
    except:
        pass
    return False

def generate_ai_response(prompt, user_id):
    mention = "baby" if (SPECIAL_USER_ID is not None and user_id == SPECIAL_USER_ID) else get_nickname(user_id) or "User"
    system_prompt = (
        f"You are Miss OG, a loving but slightly savage AI assistant with desi swag. "
        f"Address the user as {mention}. Use emojis and expressive, slightly aggressive language. "
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
    intro = (
        "✨️ Hello! I’m Miss OG — your elegant, loving & cheeky AI companion made with love by @userxOG ❤️\n"
        "Here to upgrade your chats with style, fun, and just the right amount of sass.\n\n"
        "Click below to add me to more groups, get the latest news, chat more, or explore games. \n"
    )
    bot.send_message(chat_id, intro, reply_markup=markup)

def remind_to_tag(user_id, chat_id, last_message_id):
    mention = get_mention(user_data.get(user_id, {}))
    messages = [
        f"{mention}, tag me or say 'MISS OG' to talk! 😘",
        f"Hey {mention}, don't forget to mention me or say 'MISS OG'! 😉",
        f"{mention}, you gotta tag me or call me 'MISS OG' to keep chatting! 😏",
        f"{mention}, tag me please or say 'MISS OG' so I know you're talking to me! 😘"
    ]
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
                if now - last_active > 120:
                    remind_to_tag(user_id, chat_id, last_message_id)
                    user_data[user_id]["last_active"] = now + 180
        time.sleep(30)

# Commands
@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    if message.chat.type == "private":
        send_welcome(message.chat.id, is_group=False)
    else:
        send_welcome(message.chat.id, is_group=True)

@bot.message_handler(commands=["about"])
def handle_about(message):
    about_text = (
        "✨️ Hello! I’m Miss OG — your elegant, loving & cheeky AI companion made with love by @userxOG ❤️\n"
        "Here to upgrade your chats with style, fun, and just the right amount of sass.\n\n"
        "📢 **News channel:** [MissOG_News](https://t.me/MissOG_News)\n"
        "➕ **Add me to your group:** [Add Me](https://t.me/MissOGbot?startgroup=true)\n\n"
        "I’m loving, slightly savage, and always ready to chat, play games 🎮, or give advice! 💁‍♀️✨\n"
        "Tell me your mood today! 😊\n"
        "If you need anything else, **tag me** and I’ll send you the commands! 😏"
    )
    bot.send_message(message.chat.id, about_text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    if call.data == "talk_more":
        username = call.from_user.username or "YOURNAME"
        suggested_name = username
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

    # Update last_active
    user_data.setdefault(user_id, {})
    user_data[user_id]["last_active"] = time.time()
    user_data[user_id]["chat_id"] = message.chat.id
    user_data[user_id]["last_message_id"] = message.message_id

    # Owner query
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
            bot.send_message(message.chat.id, f"Alright {format_nickname(nickname)}, I'll chat with you in {lang} 😘", reply_to_message_id=message.message_id)
        else:
            bot.send_message(message.chat.id, "Please provide both language and nickname, e.g.,\nEnglish OG")
        return

    # Language mismatch
    if language_mismatch(user_id, text):
        replies = [
            f"Arre baby 😇, koi tension nahi! Language mismatch ho gaya tha. Batao, ab hum English me baat kare ya Hinglish me continue kare? ✨💖",
            f"Oops! 😅 Baby, galti ho gayi, koi baat nahi. Kaunsi language choose karni hai ab? English ya Hinglish? 😏💫",
            f"Haha baby 🙈, koi problem nahi! Language thodi confuse ho gayi thi. Batao, kaunsi style me baat karein? 😘✨"
        ]
        bot.send_message(message.chat.id, random.choice(replies), reply_to_message_id=message.message_id)
        return

    # Abusive words
    if is_abusive(text):
        warned = user_data.get(user_id, {}).get("warned", False)
        if not warned:
            bot.send_message(message.chat.id, "Hey! Don't use bad words! 😠 Do it again and I won't talk to you.")
            user_data[user_id]["warned"] = True
        return
    else:
        if user_data.get(user_id, {}).get("warned"):
            user_data[user_id]["warned"] = False

    # Topic lock
    locked_topic = user_data.get(user_id, {}).get("topic")
    if locked_topic:
        if re.search(r"\b(stop|change topic|end topic|exit)\b", text.lower()):
            user_data[user_id].pop("topic", None)
            bot.send_message(message.chat.id, "Okay, topic unlocked. What now? 😏")
            return
        else:
            ai_reply = generate_ai_response(text, user_id)
            bot.send_message(message.chat.id, ai_reply, reply_to_message_id=message.message_id)
            return

    if re.search(r"\b(let'?s talk about|let's play|baat kare|game khele|play game|talk about)\b", text.lower()):
        user_data[user_id]["topic"] = text
        bot.send_message(message.chat.id, f"Alright, we’re sticking to this topic: {text} 😉", reply_to_message_id=message.message_id)
        return

    triggers = ["miss og", "missog", "baby", f"@{bot.get_me().username.lower()}", "miss og bot"]
    is_triggered = any(t in text.lower() for t in triggers) or (message.reply_to_message and message.reply_to_message.from_user.username == bot.get_me().username)

    if is_triggered:
        ai_reply = generate_ai_response(text, user_id)
        bot.send_message(message.chat.id, ai_reply, reply_to_message_id=message.message_id)
    else:
        mention = get_mention(message)
        bot.send_message(message.chat.id, f"{mention}, please tag me or say 'MISS OG' to chat 😘", reply_to_message_id=message.message_id)

# Background inactivity checker
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
