import os
import time
import random
import threading

import telebot
from telebot import types
import openai
from flask import Flask, request
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("BOT_TOKEN and OPENAI_API_KEY must be set in environment variables")

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

app = Flask(__name__)

# Constants
GROUP_INVITE_LINK = "https://t.me/YourGroupLink"  # Replace this with your group invite link
NEWS_CHANNEL_LINK = "https://t.me/MissOG_News"    # Replace this with your news channel link

ABUSIVE_WORDS = {"randi", "madrchd", "benched", "bc", "mc", "bkl"}

user_settings = {}

def is_abusive(text):
    text_lower = text.lower()
    for w in ABUSIVE_WORDS:
        if w in text_lower:
            return True
    return False

def get_nickname(user_id):
    return user_settings.get(user_id, {}).get("nickname", "baby")

def generate_ai_response(prompt, user_id):
    nickname = get_nickname(user_id)
    system_prompt = (
        f"You are Miss OG, a loving but slightly aggressive AI assistant with desi swag. "
        f"Address the user as @{nickname}. Use emojis and expressive language. "
        f"Add a friendly question at the end to keep the conversation going."
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
        reply = completion.choices[0].message.content.strip()
        return reply
    except Exception:
        return "Oops! Some technical problem occurred, please try again later. 😓"

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Join Group", url=GROUP_INVITE_LINK))
    markup.add(types.InlineKeyboardButton("MissOG_News", url=NEWS_CHANNEL_LINK))
    markup.add(types.InlineKeyboardButton("Talk More 💬", callback_data="talk_more"))
    markup.add(types.InlineKeyboardButton("Game 🎮 (Coming Soon)", callback_data="game_soon"))

    welcome_text = (
        "👋 Welcome to Miss OG Bot!\n\n"
        "I am your loving, caring, slightly savage AI assistant. "
        "Click the buttons below to join our group, get news, chat more, or try games soon! 😘"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id

    if call.data == "talk_more":
        msg = "In which language would you like to talk? And what should I call you? 🤔\nPlease reply like:\nEnglish John"
        bot.send_message(call.message.chat.id, msg)
        user_settings[user_id] = {"awaiting_lang_nick": True}
    elif call.data == "game_soon":
        bot.answer_callback_query(call.id, "Game feature is coming soon, please wait! 🎮")
    else:
        bot.answer_callback_query(call.id, "Unknown button clicked.")

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()

    if user_settings.get(user_id, {}).get("awaiting_lang_nick"):
        parts = text.split()
        if len(parts) >= 2:
            lang = parts[0].lower()
            nickname = " ".join(parts[1:])
            user_settings[user_id]["language"] = lang
            user_settings[user_id]["nickname"] = nickname
            user_settings[user_id]["awaiting_lang_nick"] = False
            bot.send_message(message.chat.id,
                             f"Alright {nickname}, I will now talk to you in {lang}. 😘")
        else:
            bot.send_message(message.chat.id,
                             "Please write both language and nickname, for example:\nEnglish John")
        return

    if is_abusive(text):
        warned = user_settings.get(user_id, {}).get("warned_for_abuse", False)
        if not warned:
            bot.send_message(message.chat.id,
                             "Hey, don't use bad words here! 😠 If you do it again, I won’t talk to you. Got it? 😤")
            user_settings.setdefault(user_id, {})["warned_for_abuse"] = True
        else:
            return
        return
    else:
        if user_settings.get(user_id, {}).get("warned_for_abuse", False):
            user_settings[user_id]["warned_for_abuse"] = False
            bot.send_message(message.chat.id,
                             "Alright, you’re good now. Let’s chat. Miss OG is here for you. 😌")

    msg_lower = text.lower()
    triggers = ["miss og", "missog", "baby", "@missogbot", "miss og bot"]
    if any(t in msg_lower for t in triggers) or (message.reply_to_message and message.reply_to_message.from_user.username == bot.get_me().username):
        reply = generate_ai_response(text, user_id)
        bot.send_message(message.chat.id, reply)
    else:
        bot.send_message(message.chat.id, "What do you want to say? Mention me or say 'baby' to talk. 😘")

def run_bot():
    # Use polling in a separate thread if you want
    bot.infinity_polling()

if __name__ == "__main__":
    # To use webhook, deploy and configure your server URL + BOT_TOKEN route accordingly
    print("MissOGbot is running with webhook support...")
    # Run Flask app in a thread so polling can be used simultaneously (optional)
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
