import telebot
import openai
import os
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
OWNER_USERNAME = "userxOG"
SPECIAL_USER_ID = 8457816680

user_data = {}  # Stores language, nickname, warnings, etc.

# Abusive words set
ABUSIVE_WORDS = {"randi","madrchd","bhosdike","lund","chutiya","bitch","asshole","mf","bc","mc","bkl","fuck","shit","slut","idiot","harami","kutte","kamine"}

def is_abusive(text):
    t = text.lower()
    return any(w in t for w in ABUSIVE_WORDS)

def format_nickname(nickname):
    if len(nickname) > 1:
        return nickname[0].upper() + nickname[1:].lower()
    else:
        return nickname.upper()

def get_username_or_display(message):
    username = message.from_user.username
    if username:
        return "@" + username
    else:
        first = message.from_user.first_name or ""
        last = message.from_user.last_name or ""
        full_name = (first + " " + last).strip()
        return full_name if full_name else "User"

def get_mention(message):
    user_id = message.from_user.id
    if SPECIAL_USER_ID is not None and user_id == SPECIAL_USER_ID:
        return "baby"
    nickname = user_data.get(user_id, {}).get("nickname")
    if nickname:
        return format_nickname(nickname)
    return get_username_or_display(message)

def send_welcome(chat_id, is_group=False):
    bot_username = bot.get_me().username
    markup = types.InlineKeyboardMarkup(row_width=2)

    # Row 1
    markup.add(
        types.InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_username}?startgroup=true"),
        types.InlineKeyboardButton("📢 MissOG_News", url="https://t.me/MissOG_News")
    )

    # Row 2
    markup.add(
        types.InlineKeyboardButton("💬 Talk More", callback_data="talk_more")
    )

    # Row 3 - Single Game Button
    markup.add(
        types.InlineKeyboardButton("🎮 Game", callback_data="game_soon")
    )

    intro = (
        "✨️ Hello! I’m Miss OG — your elegant, loving & cheeky AI companion made with love by @userxOG ❤️\n"
        "Here to upgrade your chats with style, fun, and just the right amount of sass.\n\n"
        "Click below to add me to more groups, get the latest news, chat more, or explore games."
    )
    bot.send_message(chat_id, intro, reply_markup=markup)

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
        # Replace single Game button with 4 actual game options
        game_markup = types.InlineKeyboardMarkup(row_width=2)
        game_markup.add(
            types.InlineKeyboardButton("🎮 Word Guessing", callback_data="game_word"),
            types.InlineKeyboardButton("🎮 TicTacToe", callback_data="game_ttt"),
            types.InlineKeyboardButton("🎮 RPC", callback_data="game_rpc"),
            types.InlineKeyboardButton("🎮 Quick Math", callback_data="game_math")
        )
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=game_markup)
    elif call.data.startswith("game_"):
        bot.answer_callback_query(call.id, f"Selected: {call.data.replace('game_','').replace('_',' ').title()} 🎮")

@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    send_welcome(message.chat.id, is_group=(message.chat.type != "private"))

# Background thread and other message handling code remains same as earlier
# (language detection, nickname setup, AI reply generation, abusive word check, etc.)

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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
