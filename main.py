import telebot
import openai
import os
import re
import threading
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
BOT_UPDATES = "@MissOG_News"
BOT_CLONE = "@MissOG_CloneBot"
OWNER_USERNAME = "userxOG"  # without @

ABUSIVE_WORDS = {
    "randi", "madrchd", "bhosdike", "lund", "chutiya", "bitch", "asshole", "mf",
    "bc", "mc", "bkl", "fuck", "shit", "slut", "idiot", "harami", "kutte", "kamine",
    "сука", "блядь", "пидор", "puta", "mierda", "imbécil", "cabrón"
}

user_data = {}  # user_id: {nickname:str, language:str, warned:bool, awaiting_lang_nick:bool, topic:str, inactive_timer:threading.Timer}

def is_abusive(text):
    t = text.lower()
    return any(w in t for w in ABUSIVE_WORDS)

def get_nickname(user_id):
    nick = user_data.get(user_id, {}).get("nickname")
    if nick:
        return nick.upper()
    else:
        return None

def handle_owner_query(text, username):
    lowered = text.lower()
    triggers = [
        "owner", "creator", "who made you", "kisne banaya", "malik", "creator kaun",
        "baby", "hubby", "husband", "jaanu", "patidev", "bf", "boyfriend", "partner", "bae"
    ]
    if any(t in lowered for t in triggers) or OWNER_USERNAME.lower() in lowered:
        if username and username.lower() == OWNER_USERNAME.lower():
            return f"You ❤️"
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
        # Add more languages as needed
    except:
        pass
    return False

def generate_ai_response(prompt, user_id):
    nickname = get_nickname(user_id) or "BABY"
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

def reminder_inactive(user_id, chat_id):
    nick = get_nickname(user_id) or "BABY"
    msg = f"{nick}, don’t go silent! Mention me or say 'MISS OG' to keep chatting 😉"
    bot.send_message(chat_id, msg)
    # Restart timer for next reminder
    timer = threading.Timer(120, reminder_inactive, args=(user_id, chat_id))
    user_data.setdefault(user_id, {})["inactive_timer"] = timer
    timer.start()

def reset_inactive_timer(user_id, chat_id):
    if user_id in user_data and "inactive_timer" in user_data[user_id]:
        user_data[user_id]["inactive_timer"].cancel()
    timer = threading.Timer(120, reminder_inactive, args=(user_id, chat_id))
    user_data.setdefault(user_id, {})["inactive_timer"] = timer
    timer.start()

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
        intro = f"🎉 Hello Group!\n👑 I’m Miss OG — your elegant, slightly loving, caring, and cheeky AI companion made with love by @{OWNER_USERNAME} ❤️\n\n" + intro
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
        suggested_name = username if username else "YOUR NAME"
        msg = (
            f"Which language would you like to talk in? And what should I call you? 🤔\n\n"
            f"Reply like this:\nEnglish {suggested_name}"
        )
        user_data.setdefault(user_id, {})
        user_data[user_id]["awaiting_lang_nick"] = True
        bot.send_message(call.message.chat.id, msg)
    elif call.data == "game_soon":
        bot.answer_callback_query(call.id, "🎮 Game feature coming soon, stay tuned!")
    else:
        bot.answer_callback_query(call.id, "Unknown option.")

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip() if message.text else ""
    username = message.from_user.username or ""

    # Reset inactivity timer on every message
    reset_inactive_timer(user_id, chat_id)

    # Owner query
    owner_reply = handle_owner_query(text, username)
    if owner_reply:
        bot.send_message(chat_id, owner_reply, reply_to_message_id=message.message_id)
        return

    # Language & nickname setup after Talk More button
    if user_data.get(user_id, {}).get("awaiting_lang_nick"):
        parts = text.split()
        if len(parts) >= 2:
            lang = parts[0]
            nickname = " ".join(parts[1:]).replace("@", "").upper()
            user_data[user_id]["language"] = lang.lower()
            user_data[user_id]["nickname"] = nickname
            user_data[user_id]["awaiting_lang_nick"] = False
            bot.send_message(chat_id, f"Alright {nickname}, I'll chat with you in {lang}. 😘", reply_to_message_id=message.message_id)
        else:
            bot.send_message(chat_id, "Please provide both language and nickname, e.g.,\nEnglish John")
        return

    # Language mismatch reminder
    if language_mismatch(user_id, text):
        chosen_lang = user_data[user_id]["language"].capitalize()
        bot.send_message(chat_id, f"You chose {chosen_lang} 😏 Please speak in it, or tell me if you want to change.", reply_to_message_id=message.message_id)
        return

    # Abusive word handling
    if is_abusive(text):
        warned = user_data.get(user_id, {}).get("warned", False)
        if not warned:
            bot.send_message(chat_id, "Hey! Don't use bad words! 😠 Do it again and I won't talk to you.", reply_to_message_id=message.message_id)
            user_data.setdefault(user_id, {})["warned"] = True
        return
    else:
        if user_data.get(user_id, {}).get("warned"):
            user_data[user_id]["warned"] = False

    # Topic lock logic
    text_lower = text.lower()
    topic_lock_phrases = ["let's talk about", "let's play", "baat kare", "game khele", "talk about", "play game"]
    stop_phrases = ["stop", "change topic", "end topic", "topic end"]

    if any(phrase in text_lower for phrase in topic_lock_phrases):
        user_data[user_id]["topic"] = text
        bot.send_message(chat_id, f"Alright, we’re sticking to this topic: {text} 😉", reply_to_message_id=message.message_id)
        return
    if "topic" in user_data.get(user_id, {}) and not any(phrase in text_lower for phrase in stop_phrases):
        ai_reply = generate_ai_response(text, user_id)
        nick = get_nickname(user_id) or username.upper() or "BABY"
        bot.send_message(chat_id, f"@{nick} {ai_reply}", reply_to_message_id=message.message_id)
        return
    elif any(phrase in text_lower for phrase in stop_phrases):
        user_data[user_id].pop("topic", None)
        bot.send_message(chat_id, "Okay, topic unlocked. What now? 😏", reply_to_message_id=message.message_id)
        return

    # Normal triggers for reply
    triggers = ["miss og", "missog", "baby", f"@{bot.get_me().username.lower()}", "miss og bot"]
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.username == bot.get_me().username

    if any(t in text_lower for t in triggers) or is_reply_to_bot:
        ai_reply = generate_ai_response(text, user_id)
        nick = get_nickname(user_id) or username.upper() or "BABY"
        bot.send_message(chat_id, f"@{nick} {ai_reply}", reply_to_message_id=message.message_id)
    else:
        # Reminder to tag bot or say MISS OG if user is not doing so
        nick = get_nickname(user_id) or username.upper() or "BABY"
        reminder = f"@{nick} Please mention me or say 'MISS OG' to chat 😉"
        if message.chat.type == "private":
            bot.send_message(chat_id, reminder, reply_to_message_id=message.message_id)
        else:
            # In groups, reply tagging user with reminder
            bot.reply_to(message, reminder)

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
