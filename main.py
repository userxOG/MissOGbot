import telebot
import openai
import os
from flask import Flask, request
from dotenv import load_dotenv
from telebot import types
import threading
import time
import random

# ================== ENV & BOT ==================
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_KEY

SPECIAL_USER_ID = 8457816680
OWNER_USERNAME = "userxOG"

# ================== STATE ==================
user_data = {}      # profiles, nickname/lang, etc.
ttt_games = {}      # per-chat game/lobby state

# ================== UTILS ==================
ABUSIVE_WORDS = {
    "randi","madrchd","bhosdike","lund","chutiya","bitch","asshole","mf","bc","mc","bkl",
    "fuck","shit","slut","idiot","harami","kutte","kamine"
}

def is_abusive(text):
    t = (text or "").lower()
    return any(w in t for w in ABUSIVE_WORDS)

def format_nickname(nickname):
    if not nickname: return "User"
    return nickname[0].upper()+nickname[1:].lower() if len(nickname)>1 else nickname.upper()

def get_username_or_display(message):
    if message.from_user.username:
        return "@"+message.from_user.username
    first = message.from_user.first_name or ""
    last = message.from_user.last_name or ""
    full = (first+" "+last).strip()
    return full or "User"

def get_mention(message):
    uid = message.from_user.id
    if SPECIAL_USER_ID and uid == SPECIAL_USER_ID:
        return "baby"
    nick = user_data.get(uid, {}).get("nickname")
    return format_nickname(nick) if nick else get_username_or_display(message)

# ================== AI ==================
def generate_ai_response(prompt, user_id):
    mention = "baby" if (SPECIAL_USER_ID and user_id==SPECIAL_USER_ID) else (user_data.get(user_id,{}).get("nickname") or "User")
    system_prompt = (
        f"You are Miss OG, a loving but slightly savage AI assistant with desi swag. "
        f"Address the user as {format_nickname(mention)}. Use emojis and expressive, slightly aggressive language. "
        f"Keep answers short and sweet. Always end with a friendly question."
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
        print("OpenAI Error:", e)
        return "Oops! Technical issue 😓"

# ================== MENUS ==================
def build_welcome_keyboard():
    bot_username = bot.get_me().username
    kb = types.InlineKeyboardMarkup(row_width=2)
    # Row 1
    kb.add(
        types.InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_username}?startgroup=true"),
        types.InlineKeyboardButton("📢 MissOG_News", url="https://t.me/MissOG_News")
    )
    # Row 2
    kb.add(
        types.InlineKeyboardButton("💬 Talk More", callback_data="talk_more"),
        types.InlineKeyboardButton("🎮 Game", callback_data="game_menu")
    )
    return kb

def build_game_menu_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎮 Word Guessing", callback_data="game_word"),
        types.InlineKeyboardButton("🎮 TicTacToe", callback_data="game_ttt"),
        types.InlineKeyboardButton("🎮 RPC", callback_data="game_rpc"),
        types.InlineKeyboardButton("🎮 Quick Math", callback_data="game_math"),
    )
    # Row 3: Back
    kb.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_welcome"))
    return kb

def send_welcome(chat_id):
    intro = (
        "✨️ Hello! I’m Miss OG — your elegant, loving & cheeky AI companion made with love by @userxOG ❤️\n"
        "Here to upgrade your chats with style, fun, and just the right amount of sass.\n\n"
        "Click below to add me to more groups, get the latest news, chat more, or explore games."
    )
    bot.send_message(chat_id, intro, reply_markup=build_welcome_keyboard())

# ================== TTT HELPERS ==================
EMPT = "⬜"
XEMO = "❌"
O_EMO = "⭕"

def ttt_new_board():
    return [" "]*9

def ttt_cell_display(v):
    if v == "X": return XEMO
    if v == "O": return O_EMO
    return EMPT

def ttt_render_keyboard(board, game_id_prefix="ttt_m_"):
    kb = types.InlineKeyboardMarkup(row_width=3)
    for r in range(3):
        row_btns = []
        for c in range(3):
            i = r*3 + c
            row_btns.append(
                types.InlineKeyboardButton(ttt_cell_display(board[i]), callback_data=f"{game_id_prefix}{i}")
            )
        kb.row(*row_btns)
    return kb

def ttt_check_winner(b):
    lines = [
        (0,1,2),(3,4,5),(6,7,8),
        (0,3,6),(1,4,7),(2,5,8),
        (0,4,8),(2,4,6)
    ]
    for a,b2,c in lines:
        if b[a]!=" " and b[a]==b2==b[c]:
            return b[a]
    if " " not in b:
        return "draw"
    return None

def ttt_bot_move(board):
    choices = [i for i,v in enumerate(board) if v==" "]
    if not choices: return None
    return random.choice(choices)

def ttt_reset_chat(chat_id):
    g = ttt_games.pop(chat_id, None)
    if not g: return
    # stop timers if exist
    for tname in ("lobby_timer","start_timer"):
        t = g.get(tname)
        if t:
            try: t.cancel()
            except: pass

# ================== CALLBACKS ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    uid = call.from_user.id

    # TALK MORE
    if call.data == "talk_more":
        username = call.from_user.username or "YOURNAME"
        msg = f"Which language would you like to talk in? And what should I call you? 🤔\n\nReply like this:\nEnglish {username}"
        user_data[uid] = user_data.get(uid, {})
        user_data[uid]["awaiting_lang_nick"] = True
        bot.send_message(chat_id, msg)
        bot.answer_callback_query(call.id)
        return

    # GAME MENU
    if call.data == "game_menu":
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=build_game_menu_keyboard())
        bot.answer_callback_query(call.id)
        return

    # BACK
    if call.data == "back_to_welcome":
        try:
            bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=build_welcome_keyboard())
        except:
            bot.edit_message_text("Back to main menu ↓", chat_id=chat_id, message_id=call.message.message_id, reply_markup=build_welcome_keyboard())
        bot.answer_callback_query(call.id)
        return

    # PLACEHOLDERS
    if call.data in ["game_word","game_rpc","game_math"]:
        bot.answer_callback_query(call.id, "Coming soon 😉")
        return

    # ================== TTT ENTRY ==================
    if call.data == "game_ttt":
        # PRIVATE: instant Miss OG vs You (no option)
        if call.message.chat.type == "private":
            ttt_reset_chat(chat_id)
            board = ttt_new_board()
            msg = None
            try:
                msg = bot.edit_message_text("TicTacToe — You "+XEMO+" vs Miss OG "+O_EMO+"\nYour turn!", chat_id=chat_id, message_id=call.message.message_id, reply_markup=ttt_render_keyboard(board))
            except:
                msg = bot.send_message(chat_id, "TicTacToe — You "+XEMO+" vs Miss OG "+O_EMO+"\nYour turn!", reply_markup=ttt_render_keyboard(board))
            ttt_games[chat_id] = {
                "mode":"pvb", "status":"active", "board":board,
                "pX": uid, "pO": "bot", "turn":"X", "msg_id": msg.message_id
            }
            bot.answer_callback_query(call.id)
            return
        # GROUP: show two options
        else:
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("🤖 VS Miss OG", callback_data="ttt_vs_bot"),
                types.InlineKeyboardButton("👥 VS Others", callback_data="ttt_vs_others")
            )
            kb.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_welcome"))
            bot.edit_message_text("Choose mode for TicTacToe:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=kb)
            bot.answer_callback_query(call.id)
            return

    # GROUP: VS MISS OG (bot opponent in group)
    if call.data == "ttt_vs_bot":
        if call.message.chat.type == "private":
            bot.answer_callback_query(call.id)
            return
        ttt_reset_chat(chat_id)
        board = ttt_new_board()
        msg = bot.edit_message_text(
            "TicTacToe — You "+XEMO+" vs Miss OG "+O_EMO+"\nYour turn!",
            chat_id=chat_id, message_id=call.message.message_id, reply_markup=ttt_render_keyboard(board)
        )
        ttt_games[chat_id] = {
            "mode":"pvb","status":"active","board":board,
            "pX": uid,"pO":"bot","turn":"X","msg_id": msg.message_id
        }
        bot.answer_callback_query(call.id, "Game started vs Miss OG 🤖")
        return

    # GROUP: VS OTHERS (lobby + join)
    if call.data == "ttt_vs_others":
        if call.message.chat.type == "private":
            bot.answer_callback_query(call.id)
            return
        if chat_id in ttt_games and ttt_games[chat_id].get("status") in ["lobby","active"]:
            bot.answer_callback_query(call.id, "A TTT lobby/game is already running.")
            return
        ttt_reset_chat(chat_id)
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("✅ Join", callback_data="ttt_join"))
        kb.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_welcome"))
        msg = bot.edit_message_text("🕹️ TicTacToe Lobby\nPlayer matching… 10s", chat_id=chat_id, message_id=call.message.message_id, reply_markup=kb)
        ttt_games[chat_id] = {
            "mode":"pvp","status":"lobby","player1":uid,"player2":None,
            "lobby_msg_id": msg.message_id,"lobby_expires_at": time.time()+10,
            "lobby_timer": None,"start_timer": None
        }
        # countdown
        def lobby_countdown():
            while True:
                g = ttt_games.get(chat_id)
                if not g or g.get("status")!="lobby": break
                rem = int(g["lobby_expires_at"] - time.time())
                if rem <= 0:
                    try:
                        bot.edit_message_text(
                            "⏳ Lobby timed out. No one joined.\nOpen game menu again to host.",
                            chat_id=chat_id, message_id=g["lobby_msg_id"], reply_markup=build_game_menu_keyboard()
                        )
                    except: pass
                    ttt_reset_chat(chat_id)
                    break
                try:
                    kb2 = types.InlineKeyboardMarkup(row_width=1)
                    kb2.add(types.InlineKeyboardButton("✅ Join", callback_data="ttt_join"))
                    kb2.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_welcome"))
                    bot.edit_message_text(f"🕹️ TicTacToe Lobby\nPlayer matching… {rem}s", chat_id=chat_id, message_id=g["lobby_msg_id"], reply_markup=kb2)
                except: pass
                time.sleep(1)
        t = threading.Thread(target=lobby_countdown, daemon=True)
        t.start()
        ttt_games[chat_id]["lobby_timer"] = t
        bot.answer_callback_query(call.id, "Lobby opened!")
        return

    # GROUP: JOIN
    if call.data == "ttt_join":
        g = ttt_games.get(chat_id)
        if not g or g.get("status")!="lobby":
            bot.answer_callback_query(call.id, "No active lobby.")
            return
        if uid == g["player1"]:
            bot.answer_callback_query(call.id, "You are Player 1 already.")
            return
        if g.get("player2"):
            bot.answer_callback_query(call.id, "Lobby full.")
            return
        g["player2"] = uid
        g["status"] = "starting"

        p1u = g["player1"]
        try:
            p1 = bot.get_chat_member(chat_id, p1u).user
            p1name = "@"+p1.username if p1.username else (p1.first_name or "Player1")
        except:
            p1name = "Player1"
        p2 = call.from_user
        p2name = "@"+p2.username if p2.username else (p2.first_name or "Player2")

        def start_in_3():
            try:
                for s in [3,2,1]:
                    bot.edit_message_text(
                        f"Match found! {p1name} {XEMO} vs {p2name} {O_EMO}\nGame starts in {s}s…",
                        chat_id=chat_id, message_id=g["lobby_msg_id"]
                    )
                    time.sleep(1)
            except: pass
            board = ttt_new_board()
            ttt_games[chat_id] = {
                "mode":"pvp","status":"active","board":board,
                "pX": g["player1"],"pO": g["player2"],
                "turn":"X","msg_id": g["lobby_msg_id"]
            }
            try:
                bot.edit_message_text(
                    f"TicTacToe — {p1name} {XEMO} vs {p2name} {O_EMO}\nTurn: {XEMO}",
                    chat_id=chat_id, message_id=ttt_games[chat_id]["msg_id"], reply_markup=ttt_render_keyboard(board)
                )
            except: pass

        t = threading.Thread(target=start_in_3, daemon=True)
        t.start()
        ttt_games[chat_id]["start_timer"] = t
        bot.answer_callback_query(call.id, "Joined! 🎮")
        return

    # ================== TTT MOVES ==================
    if call.data.startswith("ttt_m_"):
        g = ttt_games.get(chat_id)
        if not g or g.get("status")!="active" or "board" not in g:
            bot.answer_callback_query(call.id, "No active game.")
            return

        idx = int(call.data.split("_")[-1])
        if idx < 0 or idx > 8:
            bot.answer_callback_query(call.id, "Invalid cell.")
            return
        board = g["board"]
        if board[idx] != " ":
            bot.answer_callback_query(call.id, "Cell already taken!")
            return

        # PVP
        if g["mode"]=="pvp":
            symbol = g["turn"]
            cur_uid = g["pX"] if symbol=="X" else g["pO"]
            if uid != cur_uid:
                bot.answer_callback_query(call.id, "Not your turn.")
                return
            board[idx] = symbol
            winner = ttt_check_winner(board)
            if winner:
                if winner=="draw":
                    end_text = "Game over: Draw 🤝"
                else:
                    win_emo = XEMO if winner=="X" else O_EMO
                    end_text = f"Game over: {win_emo} wins! 🏆"
                kb = ttt_render_keyboard(board, game_id_prefix="noop_")
                bot.edit_message_text(end_text, chat_id=chat_id, message_id=g["msg_id"], reply_markup=kb)
                ttt_reset_chat(chat_id)
                bot.answer_callback_query(call.id)
                return
            # switch turn
            g["turn"] = "O" if g["turn"]=="X" else "X"
            turn_text = XEMO if g["turn"]=="X" else O_EMO
            bot.edit_message_text(
                f"TicTacToe — Turn: {turn_text}",
                chat_id=chat_id, message_id=g["msg_id"], reply_markup=ttt_render_keyboard(board)
            )
            bot.answer_callback_query(call.id)
            return

        # PVB (Miss OG)
        if g["mode"]=="pvb":
            # player is X
            if g["turn"]!="X":
                bot.answer_callback_query(call.id, "Wait, my turn 😏")
                return
            board[idx] = "X"
            winner = ttt_check_winner(board)
            if winner:
                if winner=="draw":
                    end_text = "Game over: Draw 🤝"
                else:
                    end_text = "You win! 🏆 " + XEMO
                kb = ttt_render_keyboard(board, game_id_prefix="noop_")
                bot.edit_message_text(end_text, chat_id=chat_id, message_id=g["msg_id"], reply_markup=kb)
                ttt_reset_chat(chat_id)
                bot.answer_callback_query(call.id)
                return
            # bot move
            g["turn"] = "O"
            mv = ttt_bot_move(board)
            if mv is not None:
                board[mv] = "O"
            winner = ttt_check_winner(board)
            if winner:
                if winner=="draw":
                    end_text = "Game over: Draw 🤝"
                else:
                    end_text = "Miss OG wins! 😎 " + O_EMO
                kb = ttt_render_keyboard(board, game_id_prefix="noop_")
                bot.edit_message_text(end_text, chat_id=chat_id, message_id=g["msg_id"], reply_markup=kb)
                ttt_reset_chat(chat_id)
                bot.answer_callback_query(call.id)
                return
            # back to player
            g["turn"] = "X"
            bot.edit_message_text("Your turn!", chat_id=chat_id, message_id=g["msg_id"], reply_markup=ttt_render_keyboard(board))
            bot.answer_callback_query(call.id)
            return

    # NOOP taps after game end
    if call.data.startswith("noop_"):
        bot.answer_callback_query(call.id, "Game finished.")
        return

# ================== COMMANDS ==================
@bot.message_handler(commands=["start","help"])
def handle_start(message):
    send_welcome(message.chat.id)

# ================== MESSAGES ==================
@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    uid = message.from_user.id
    text = (message.text or "").strip()
    user_data.setdefault(uid, {})
    user_data[uid]["last_active"] = time.time()

    # Language & nickname setup
    if user_data[uid].get("awaiting_lang_nick"):
        parts = text.split()
        if len(parts) >= 2:
            lang = parts[0].lower()
            nickname = " ".join(parts[1:]).replace("@","")
            user_data[uid]["language"] = lang
            user_data[uid]["nickname"] = nickname
            user_data[uid]["awaiting_lang_nick"] = False
            bot.send_message(message.chat.id, f"Alright {format_nickname(nickname)}, how are you? 😘", reply_to_message_id=message.message_id)
        else:
            bot.send_message(message.chat.id, "Please provide both language and nickname, e.g., English OG")
        return

    # Abusive filter
    if is_abusive(text):
        if not user_data[uid].get("warned", False):
            bot.send_message(message.chat.id, "Hey! Don't use bad words! 😠")
            user_data[uid]["warned"] = True
        return
    else:
        user_data[uid]["warned"] = False

    # AI trigger
    triggers = ["miss og","missog","baby", f"@{bot.get_me().username.lower()}", "miss og bot"]
    if any(t in text.lower() for t in triggers):
        reply = generate_ai_response(text, uid)
        bot.send_message(message.chat.id, reply, reply_to_message_id=message.message_id)
    else:
        bot.send_message(message.chat.id, f"{get_mention(message)}, please tag me or say 'MISS OG' to chat 😘", reply_to_message_id=message.message_id)

# ================== FLASK / WEBHOOK ==================
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
