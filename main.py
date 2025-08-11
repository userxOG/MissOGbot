import os
import time
import random
import telebot
from telebot import types
import openai
from flask import Flask, request
from dotenv import load_dotenv
import threading

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_KEY

app = Flask(__name__)

# Abusive words list
ABUSIVE_WORDS = ["randi", "madarchod", "benched", "bc", "mc", "bkl", "kutti", "bullshit"]

# Abusive replies variations
ABUSIVE_REPLIES = [
    "Bade badtameez ho yaar, yahan gaali mat do! 😠 Abki baar aisi gaali di toh main tumse baat nahi karungi. Samjhe? 😤",
    "Gaali mat do, warna OG chup ho jayegi! 😡",
    "Aisi gaali firse di toh main ignore karungi! 😤",
]

FORGIVE_REPLIES = [
    "Chalo ab thik ho, baat karte hain. Miss OG yahan tumhare saath hai. 😌",
    "Theek hai, ab pyaar se baat karte hain! Miss OG ready hai! 💖",
]

AUTO_FOLLOW_UPS = [
    "Miss OG yahin hai, @{username}! Kya haal?",
    "@{username}, OG tumhe miss kar rahi hai!",
    "Hello @{username}! Kuch bolna hai?",
    "Kya chal raha hai, @{username}?",
    "OG tumhara intezaar kar rahi hai!",
]

BANDI_REPLIES = [
    "Arre @{username}, OG tumhare liye bandi bhi laayegi, par pehle thoda charm dikhana padega! 😏🔥",
    "Bandi toh mil jayegi, bas OG ke level pe aao pehle! 😉",
    "Boss, OG ka magic chal jayega, bas thoda intezaar karo! 😘✨",
]

OWNER_INFO = "Main OG ki baby hu 💖, usne mujhe banaya hai — powered by love & care 😘"

user_muted = {}
user_nicknames = {}
last_message_time = {}

def get_nickname(message):
    user_id = message.from_user.id
    return user_nicknames.get(user_id, message.from_user.username or "baby")

def contains_abuse(text):
    text = text.lower()
    return any(word in text for word in ABUSIVE_WORDS)

def is_user_muted(user_id):
    return user_muted.get(user_id, False)

def set_user_muted(user_id, muted=True):
    user_muted[user_id] = muted

def get_random_reply(list_, username):
    return random.choice(list_).replace("{username}", username)

def get_ai_reply(user_message):
    lower_msg = user_message.lower()
    if any(q in lower_msg for q in ["owner", "creator", "kisne banaya", "tumhara malik", "creator kaun"]):
        return OWNER_INFO
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Tum ek sweet, short, funny aur thodi naughty AI ho. Har jawab chhota aur pyar bhara do."},
                {"role": "user", "content": user_message}
            ]
        )
        return completion.choices[0].message["content"].strip()
    except Exception as e:
        print("API Error:", e)
        return "Baby, thoda error aa gaya 😅"

def should_reply(message):
    text = message.text.lower() if message.text else ""
    bot_username = bot.get_me().username.lower() if bot.get_me() else "missogbot"
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.username == bot_username
    return (
        is_reply_to_bot
        or f"@{bot_username}" in text
        or "baby" in text
        or "miss og" in text
    )

# Auto follow-up thread function
def auto_follow_up(chat_id, user_id, username):
    time.sleep(120)  # 2 min
    current_time = time.time()
    if user_id in last_message_time and current_time - last_message_time[user_id] >= 120:
        msg = get_random_reply(AUTO_FOLLOW_UPS, username)
        try:
            bot.send_message(chat_id, msg)
        except Exception as e:
            print("Failed to send auto follow-up:", e)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Add to Group", url="https://t.me/YourGroupLink"))
    markup.add(types.InlineKeyboardButton("MissOG News Channel", url="https://t.me/MissOG_News"))
    markup.add(types.InlineKeyboardButton("Talk More", callback_data="talk_more"))
    markup.add(types.InlineKeyboardButton("Game (Soon)"))
    
    welcome_text = (
        "Welcome to Miss OG! 💖\n"
        "Use buttons below to interact.\n"
        "Click 'Talk More' to chat in your language and set your nickname."
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "talk_more")
def ask_language_and_nickname(call):
    bot.send_message(call.message.chat.id, "Aap kiss language me mujhe baat karna chahte hain? Aur main aapko kya keh kar bulaun?")

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    user_id = message.from_user.id
    username = get_nickname(message)
    text = message.text.lower() if message.text else ""

    last_message_time[user_id] = time.time()

    if is_user_muted(user_id):
        if contains_abuse(text):
            return
        else:
            set_user_muted(user_id, False)
            reply = get_random_reply(FORGIVE_REPLIES, username)
            bot.reply_to(message, reply)
            return

    if contains_abuse(text):
        set_user_muted(user_id, True)
        reply = get_random_reply(ABUSIVE_REPLIES, username)
        bot.reply_to(message, reply)
        return

    if "bandi patwa do" in text:
        reply = get_random_reply(BANDI_REPLIES, username)
        bot.reply_to(message, reply)
        return

    if "help" in text or "meri ek help" in text:
        bot.reply_to(message, f"Bol na, @{username}! Miss OG tumhari help ke liye ready hai! 💖")
        return

    if text in ["hello", "break"]:
        caring_replies = [
            f"Miss OG tumhare saath hai, @{username}! Kya haal hai? Koi help chahiye toh bolo! 🙌🔥",
            f"Hello @{username}! Miss OG ready hai! 💫",
        ]
        bot.reply_to(message, random.choice(caring_replies))
        return

    if should_reply(message):
        ai_reply = get_ai_reply(message.text)
        bot.reply_to(message, ai_reply)
        return

    # Start auto follow-up thread for inactivity
    threading.Thread(target=auto_follow_up, args=(message.chat.id, user_id, username), daemon=True).start()

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
    import requests
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        webhook_url = f"{render_url}/{BOT_TOKEN}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"Webhook set to: {webhook_url}")
    else:
        print("RENDER_EXTERNAL_URL not found! Set webhook manually if needed.")

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
