import telebot
import openai
import os
from flask import Flask, request
from dotenv import load_dotenv

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
OWNER_INFO = "Main OG ki baby hu 💖, usne mujhe banaya hai — powered by love & care 😘"

# AI reply function
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

# Reply condition check
def should_reply(message):
    text = message.text.lower() if message.text else ""
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.username == bot.get_me().username
    return (
        is_reply_to_bot
        or f"@{bot.get_me().username.lower()}" in text
        or "baby" in text
        or "miss og" in text
    )

# Message handler
@bot.message_handler(func=lambda m: True)
def reply(message):
    if should_reply(message):
        ai_reply = get_ai_reply(message.text)
        bot.reply_to(message, ai_reply)

# Flask app
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
