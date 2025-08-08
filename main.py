import telebot
import openai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# Setup
bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_KEY

BOT_NAME = "Miss OG"
BOT_ABOUT = "Elegant group manager. Sweet, smart & made with love by OG. Here to upgrade your chats with class."
BOT_DESC = "Hello! I'm Miss OG, your elegant Telegram companion. Here to help you manage your groups smartly, respond sweetly when called, and bring calm & class to every chat."
BOT_UPDATES = "@MissOG_News"
BOT_CLONE = "@MissOG_CloneBot"
OWNER_INFO = "Main OG ki baby hu 💖, usne mujhe banaya hai — powered by love & care 😘"

# Function to get AI response
def get_ai_reply(user_message):
    # Check for owner-related questions
    lower_msg = user_message.lower()
    if any(q in lower_msg for q in ["owner", "creator", "kisne banaya", "tumhara malik", "creator kaun"]):
        return OWNER_INFO

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # Fast + cheap
            messages=[
                {"role": "system", "content": "Tum ek sweet, short, funny aur thodi naughty AI ho. Har jawab chhota aur pyar bhara do."},
                {"role": "user", "content": user_message}
            ]
        )
        return completion.choices[0].message["content"].strip()
    except Exception as e:
        print("API Error:", e)
        return "Baby, thoda error aa gaya 😅"

# Trigger check
def should_reply(message):
    text = message.text.lower() if message.text else ""
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.username == bot.get_me().username
    return (
        is_reply_to_bot
        or f"@{bot.get_me().username.lower()}" in text
        or "baby" in text
        or "miss og" in text
    )

# Telegram message handler
@bot.message_handler(func=lambda m: True)
def reply(message):
    if should_reply(message):
        ai_reply = get_ai_reply(message.text)
        bot.reply_to(message, ai_reply)

# Start bot
print("Bot is running... 💖")
bot.infinity_polling()
