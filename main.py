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

ABUSIVE_WORDS = {"randi","madrchd","bhosdike","lund","chutiya","bitch","asshole","mf","bc","mc","bkl","fuck","shit","slut","idiot","harami","kutte","kamine"}

user_data = {}

def format_nickname(nickname):
    return nickname[0].upper() + nickname[1:].lower() if len(nickname) > 1 else nickname.upper()

def get_username_or_display(message):
    if message.from_user.username:
        return "@" + message.from_user.username
    else:
        return (message.from_user.first_name + " " + (message.from_user.last_name or "")).strip() or "User"

def get_nickname(user_id):
    data = user_data.get(user_id, {})
    return format_nickname(data.get("nickname")) if data.get("nickname") else None

def get_mention(message):
    user_id = message.from_user.id
    if user_id == SPECIAL_USER_ID:
        return "baby"
    nickname = get_nickname(user_id)
    return nickname if nickname else get_username_or_display(message)

def is_abusive(text):
    t = text.lower()
    return any(w in t for w in ABUSIVE_WORDS)

def language_mismatch(user_id, text):
    chosen_lang = user_data.get(user_id, {}).get("language")
    if not chosen_lang: return False
    try:
        detected = detect(text)
        chosen = chosen_lang.lower()
        if chosen == "english" and detected != "en": return True
        if chosen == "hindi" and detected != "hi": return True
        if chosen == "hinglish" and detected not in ["en","hi"]: return True
    except:
        pass
    return False

def generate_ai_response(prompt, user_id):
    mention = "baby" if user_id == SPECIAL_USER_ID else get_nickname(user_id) or "User"
    system_prompt = (
        f"You are Miss OG, loving but slightly savage AI assistant with desi swag. "
        f"Address the user as {mention}, use emojis, keep answers short, always end with a friendly question."
    )
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system_prompt},{"role":"user","content":prompt}],
            max_tokens=150,
            temperature=0.9
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print("API Error:", e)
        return "Oops! Technical issue, try again later 😓"

def send_welcome(chat_id, is_group=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    bot_username = bot.get_me().username
    # Normal buttons
    markup.add(
        types.InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_username}?startgroup=true"),
        types.InlineKeyboardButton("📢 MissOG_News", url="https://t.me/MissOG_News")
    )
    # Talk more & Game
    game_markup = types.InlineKeyboardMarkup(row_width=2)
    game_markup.add(
        types.InlineKeyboardButton("Word Guessing", callback_data="game_word"),
        types.InlineKeyboardButton("TicTacToe", callback_data="game_ttt"),
        types.InlineKeyboardButton("RPC", callback_data="game_rpc"),
        types.InlineKeyboardButton("Quick Math", callback_data="game_math")
    )
    markup.add(
        types.InlineKeyboardButton("💬 Talk More", callback_data="talk_more"),
        types.InlineKeyboardButton("🎮 Game (Soon)", callback_data="game_soon")
    )
    intro = (
        "✨️ Hello! I’m Miss OG — your elegant, loving & cheeky AI companion made with love by @userxOG ❤️\n"
        "Here to upgrade your chats with style, fun, and just the right amount of sass.\n\n"
        "Click below to add me to more groups, get the latest news, chat more, or explore games.\n"
    )
    bot.send_message(chat_id, intro, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    if call.data == "talk_more":
        msg = f"Which language would you like to talk in? And what should I call you? 🤔\n\nReply like this:\nEnglish {call.from_user.first_name}"
        user_data[user_id] = user_data.get(user_id,{})
        user_data[user_id]["awaiting_lang_nick"] = True
        bot.send_message(call.message.chat.id, msg)
    elif call.data == "game_soon":
        bot.answer_callback_query(call.id, "🎮 Game feature coming soon!")
    elif call.data.startswith("game_"):
        bot.answer_callback_query(call.id, f"Selected: {call.data.replace('game_','').replace('_',' ').title()} 🎮")

@bot.message_handler(commands=["start","help"])
def handle_start(message):
    send_welcome(message.chat.id, is_group=(message.chat.type!="private"))

@bot.message_handler(func=lambda m: True)
def handle_messages(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""

    user_data.setdefault(user_id,{})
    user_data[user_id]["last_active"] = time.time()
    user_data[user_id]["chat_id"] = message.chat.id
    user_data[user_id]["last_message_id"] = message.message_id

    # Owner check
    if handle_owner_query(message):
        bot.send_message(message.chat.id, handle_owner_query(message))
        return

    # Nickname + language selection
    if user_data[user_id].get("awaiting_lang_nick"):
        parts = text.split()
        if len(parts)>=2:
            lang = parts[0].lower()
            nickname = " ".join(parts[1:]).replace("@","")
            user_data[user_id]["language"] = lang
            user_data[user_id]["nickname"] = nickname
            user_data[user_id]["awaiting_lang_nick"] = False
            greet = {"english":"Alright","hinglish":"Alright","hindi":"Thik hai"}
            bot.send_message(message.chat.id,f"{greet.get(lang,'Alright')} {format_nickname(nickname)}, how are you? 😘")
        else:
            bot.send_message(message.chat.id,"Please provide both language and nickname, e.g.,\nEnglish OG")
        return

    # Language confirmation Yes/No
    if user_data[user_id].get("awaiting_lang_confirm"):
        low_text = text.lower()
        if low_text.startswith("yes"):
            bot.send_message(message.chat.id,"Great! 😘 Ab is language me continue karte hain.")
            user_data[user_id]["awaiting_lang_confirm"] = False
            return
        elif low_text.startswith("no"):
            bot.send_message(message.chat.id,"Theek hai 😏 Ab batao kaunsi language me baat karna chahte ho?")
            user_data[user_id]["language"] = None
            user_data[user_id]["awaiting_lang_confirm"] = False
            return

    # Abusive check
    if is_abusive(text):
        warned = user_data[user_id].get("warned",False)
        if not warned:
            bot.send_message(message.chat.id,"Hey! Don't use bad words! 😠 Do it again and I won't talk to you.")
            user_data[user_id]["warned"] = True
        return
    else:
        user_data[user_id]["warned"] = False

    # Language mismatch detection
    if language_mismatch(user_id,text):
        bot.send_message(message.chat.id,f"Arre baby 😇, tumne abhi {user_data[user_id]['language'].capitalize()} select kiya tha. Agar tum isme baat karna chahte ho, Yes likho, warna No.")
        user_data[user_id]["awaiting_lang_confirm"] = True
        return

    # AI response triggers
    triggers = ["miss og","missog","baby",f"@{bot.get_me().username.lower()}","miss og bot"]
    if any(t in text.lower() for t in triggers):
        ai_reply = generate_ai_response(text,user_id)
        bot.send_message(message.chat.id,ai_reply,reply_to_message_id=message.message_id)
    else:
        bot.send_message(message.chat.id,f"{get_mention(message)}, please tag me or say 'MISS OG' to chat 😘", reply_to_message_id=message.message_id)

# Flask webhook
app = Flask(__name__)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK",200

@app.route("/",methods=["GET"])
def index():
    return "Miss OG is alive 💖"

if __name__=="__main__":
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        bot.remove_webhook()
        bot.set_webhook(url=f"{render_url}/{BOT_TOKEN}")
        print(f"Webhook set to: {render_url}/{BOT_TOKEN}")
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
