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

SPECIAL_USER_ID = 8457816680  # Baby ID
OWNER_USERNAME = "userxOG"
user_data = {}

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

def generate_ai_response(prompt, user_id):
    mention = get_mention(user_id)
    system_prompt = (
        f"You are Miss OG, a loving but slightly savage AI assistant with desi swag. "
        f"Address the user as {mention}. Use emojis and expressive, slightly aggressive language. "
        f"Keep answers short and sweet. Always end with a friendly question."
    )
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.9
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print("API Error:", e)
        return "Oops! Technical issue 😓"

def send_welcome(chat_id):
    bot_username = bot.get_me().username
    markup = types.InlineKeyboardMarkup(row_width=2)
    # Row 1
    markup.add(
        types.InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_username}?startgroup=true"),
        types.InlineKeyboardButton("📢 MissOG_News", url="https://t.me/MissOG_News")
    )
    # Row 2
    markup.add(
        types.InlineKeyboardButton("💬 Talk More", callback_data="talk_more"),
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
        msg = f"Which language would you like to talk in? And what should I call you? 🤔\n\nReply like this:\nEnglish {username}"
        user_data[user_id] = user_data.get(user_id, {})
        user_data[user_id]["awaiting_lang_nick"] = True
        bot.send_message(call.message.chat.id, msg)

    elif call.data == "game_soon":
        # 4 game buttons + Back
        game_markup = types.InlineKeyboardMarkup(row_width=2)
        game_markup.add(
            types.InlineKeyboardButton("🎮 Word Guessing", callback_data="game_word"),
            types.InlineKeyboardButton("🎮 TicTacToe", callback_data="game_ttt"),
            types.InlineKeyboardButton("🎮 RPC", callback_data="game_rpc"),
            types.InlineKeyboardButton("🎮 Quick Math", callback_data="game_math")
        )
        game_markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_welcome"))
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=game_markup)

    elif call.data.startswith("game_"):
        bot.answer_callback_query(call.id, f"Selected: {call.data.replace('game_','').replace('_',' ').title()} 🎮")

    elif call.data == "back_to_welcome":
        bot_username = bot.get_me().username
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_username}?startgroup=true"),
            types.InlineKeyboardButton("📢 MissOG_News", url="https://t.me/MissOG_News")
        )
        markup.add(
            types.InlineKeyboardButton("💬 Talk More", callback_data="talk_more"),
            types.InlineKeyboardButton("🎮 Game", callback_data="game_soon")
        )
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    send_welcome(message.chat.id)

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = (message.text or "").strip()
    user_data.setdefault(user_id, {})
    user_data[user_id]["last_active"] = time.time()
    user_data[user_id]["chat_id"] = message.chat.id

    if user_data.get(user_id, {}).get("awaiting_lang_nick"):
        parts = text.split()
        if len(parts) >= 2:
            lang = parts[0].lower()
            nickname = " ".join(parts[1:])
            user_data[user_id]["language"] = lang
            user_data[user_id]["nickname"] = nickname
            user_data[user_id]["awaiting_lang_nick"] = False
            bot.send_message(message.chat.id, f"Alright {format_nickname(nickname)}, how are you? 😘", reply_to_message_id=message.message_id)
        else:
            bot.send_message(message.chat.id, "Please provide both language and nickname, e.g., English OG")
        return

    if is_abusive(text):
        if not user_data[user_id].get("warned", False):
            bot.send_message(message.chat.id, "Hey! Don't use bad words! 😠")
            user_data[user_id]["warned"] = True
        return
    else:
        user_data[user_id]["warned"] = False

    # AI reply
    triggers = ["miss og", "missog", "baby", f"@{bot.get_me().username.lower()}", "miss og bot"]
    if any(t in text.lower() for t in triggers):
        ai_reply = generate_ai_response(text, user_id)
        bot.send_message(message.chat.id, ai_reply, reply_to_message_id=message.message_id)
    else:
        mention = get_mention(message)
        bot.send_message(message.chat.id, f"{mention}, please tag me or say 'MISS OG' to chat 😘", reply_to_message_id=message.message_id)

# Flask webhook
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
