import telebot
import openai
import os
from flask import Flask, request
from dotenv import load_dotenv
from telebot import types

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
OWNER_INFO = "I'm OG's baby 💖, made with love and care by him 😘"

OWNER_USERNAME = "userxOG"  # OG's Telegram username without @

ABUSIVE_WORDS = {"randi", "madrchd", "benched", "bc", "mc", "bkl"}

user_data = {}  # Store user info like nickname, language, warnings

def is_abusive(text):
    text_lower = text.lower()
    for w in ABUSIVE_WORDS:
        if w in text_lower:
            return True
    return False

def get_nickname(user_id):
    return user_data.get(user_id, {}).get("nickname", "baby")

def handle_owner_query(text):
    triggers = ["owner", "creator", "who made you", "who is your owner", "kisne banaya", "tumhara malik", "creator kaun"]
    lowered = text.lower()
    if any(t in lowered for t in triggers):
        return OWNER_INFO
    if OWNER_USERNAME.lower() in lowered:
        return OWNER_INFO
    return None

def generate_ai_response(prompt, user_id):
    nickname = get_nickname(user_id)
    system_prompt = (
        f"You are Miss OG, a loving but slightly savage AI assistant with desi swag. "
        f"Address the user as @{nickname}. Use emojis and expressive, slightly aggressive language. "
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

def should_reply(message):
    text = message.text.lower() if message.text else ""
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.username == bot.get_me().username
    return (
        is_reply_to_bot
        or f"@{bot.get_me().username.lower()}" in text
        or "baby" in text
        or "miss og" in text
    )

# Private chat welcome message with buttons
def send_welcome_private(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Join Group", url="https://t.me/YourGroupLink"),
        types.InlineKeyboardButton("MissOG_News", url="https://t.me/MissOG_News"),
        types.InlineKeyboardButton("Talk More 💬", callback_data="talk_more"),
        types.InlineKeyboardButton("Game 🎮 (Soon)", callback_data="game_soon"),
    )
    welcome_text = (
        "👋 Hey! Welcome to Miss OG Bot!\n\n"
        "I'm your loving, caring, slightly savage AI assistant. "
        "Click below to join our group, get the latest news, chat more, or try games soon! 😘"
    )
    bot.send_message(chat_id, welcome_text, reply_markup=markup)

@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    if message.chat.type == "private":
        send_welcome_private(message.chat.id)
    else:
        bot.reply_to(message, "Hey! Mention me or say 'baby' to chat with me. 😘")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id

    if call.data == "talk_more":
        msg = (
            "Which language would you like to talk in? And what should I call you? 🤔\n\n"
            "Reply like this:\nEnglish John"
        )
        bot.send_message(call.message.chat.id, msg)
        user_data[user_id] = user_data.get(user_id, {})
        user_data[user_id]["awaiting_lang_nick"] = True

    elif call.data == "game_soon":
        bot.answer_callback_query(call.id, "Game feature coming soon, stay tuned! 🎮")
    else:
        bot.answer_callback_query(call.id, "Unknown option selected.")

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""

    # First check if it is an owner query
    owner_reply = handle_owner_query(text)
    if owner_reply:
        bot.send_message(message.chat.id, owner_reply)
        return

    # Handle language and nickname after Talk More button
    if user_data.get(user_id, {}).get("awaiting_lang_nick"):
        parts = text.split()
        if len(parts) >= 2:
            lang = parts[0].lower()
            nickname = " ".join(parts[1:])
            user_data[user_id]["language"] = lang
            user_data[user_id]["nickname"] = nickname
            user_data[user_id]["awaiting_lang_nick"] = False
            bot.send_message(message.chat.id, f"Alright {nickname}, I'll chat with you in {lang}. 😘")
        else:
            bot.send_message(message.chat.id, "Please provide both language and nickname, e.g.,\nEnglish John")
        return

    # Abusive word handling
    if is_abusive(text):
        warned = user_data.get(user_id, {}).get("warned", False)
        if not warned:
            bot.send_message(message.chat.id, "Hey! Don't use bad words here! 😠 If you do again, I won't talk to you. Got it? 😤")
            user_data.setdefault(user_id, {})["warned"] = True
        return
    else:
        if user_data.get(user_id, {}).get("warned", False):
            user_data[user_id]["warned"] = False
            bot.send_message(message.chat.id, "Okay, you're good now. Let's chat. Miss OG is here for you. 😌")

    # Reply only when triggered
    text_lower = text.lower()
    triggers = ["miss og", "missog", "baby", f"@{bot.get_me().username.lower()}", "miss og bot"]
    if any(t in text_lower for t in triggers) or (message.reply_to_message and message.reply_to_message.from_user.username == bot.get_me().username):
        ai_reply = generate_ai_response(text, user_id)
        bot.send_message(message.chat.id, ai_reply)
    else:
        if message.chat.type == "private":
            bot.send_message(message.chat.id, "Mention me or say 'baby' to talk. 😘")

# Flask app for webhook (unchanged from your original code)
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
    import requests
    render_url = os.getenv("RENDER_EXTERNAL_URL")  # Render auto sets this
    if render_url:
        webhook_url = f"{render_url}/{BOT_TOKEN}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"Webhook set to: {webhook_url}")
    else:
        print("RENDER_EXTERNAL_URL not found! Set webhook manually if needed.")

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
