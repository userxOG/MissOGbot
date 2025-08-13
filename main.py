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

# ---------- ENV & BOT ----------
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_KEY

SPECIAL_USER_ID = 8457816680
OWNER_USERNAME = "userxOG"

# ---------- STATE ----------
user_data = {}          # per-user profile
ttt_games = {}          # per-chat game/lobby state: { chat_id: {...} }

# ---------- UTILS ----------
ABUSIVE_WORDS = {"randi","madrchd","bhosdike","lund","chutiya","bitch","asshole","mf","bc","mc","bkl","fuck","shit","slut","idiot","harami","kutte","kamine"}

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

# ---------- AI ----------
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
            max_tokens=150, temperature=0.9
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI Error:", e)
        return "Oops! Technical issue 😓"

# ---------- WELCOME ----------
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
        types.InlineKeyboardButton("🎮 Game", callback_data="game_menu")
    )
    intro = (
        "✨️ Hello! I’m Miss OG — your elegant, loving & cheeky AI companion made with love by @userxOG ❤️\n"
        "Here to upgrade your chats with style, fun, and just the right amount of sass.\n\n"
        "Click below to add me to more groups, get the latest news, chat more, or explore games."
    )
    bot.send_message(chat_id, intro, reply_markup=markup)

def build_welcome_keyboard():
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
        types.InlineKeyboardButton("🎮 Game", callback_data="game_menu")
    )
    return markup

def build_game_menu_keyboard():
    k = types.InlineKeyboardMarkup(row_width=2)
    k.add(
        types.InlineKeyboardButton("🎮 Word Guessing", callback_data="game_word"),
        types.InlineKeyboardButton("🎮 TicTacToe", callback_data="game_ttt"),
        types.InlineKeyboardButton("🎮 RPC", callback_data="game_rpc"),
        types.InlineKeyboardButton("🎮 Quick Math", callback_data="game_math"),
    )
    # Row 3: Back (as per your layout wish)
    k.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_welcome"))
    return k

# ---------- TIC TAC TOE HELPERS ----------
def ttt_new_board():
    return [" "]*9  # indices 0..8

def ttt_render_keyboard(board, game_id_prefix="ttt_m_"):
    # 3x3 grid of buttons
    kb = types.InlineKeyboardMarkup(row_width=3)
    def cell_text(i):
        return " " if board[i]==" " else board[i]
    for row in range(3):
        buttons = []
        for col in range(3):
            i = row*3 + col
            txt = cell_text(i)
            # show • for empty (looks neat on Telegram)
            display = txt if txt != " " else "•"
            buttons.append(types.InlineKeyboardButton(display, callback_data=f"{game_id_prefix}{i}"))
        kb.row(*buttons)
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
    # Simple random valid move
    empty = [i for i,v in enumerate(board) if v==" "]
    if not empty: return None
    return random.choice(empty)

def ttt_reset_chat(chat_id):
    if chat_id in ttt_games:
        # cancel timers if any
        g = ttt_games[chat_id]
        for t in ["lobby_timer","start_timer"]:
            if g.get(t):
                try:
                    g[t].cancel()
                except:
                    pass
        ttt_games.pop(chat_id, None)

# ---------- CALLBACKS ----------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    uid = call.from_user.id
    uname = "@"+call.from_user.username if call.from_user.username else call.from_user.first_name

    # TALK MORE
    if call.data == "talk_more":
        username = call.from_user.username or "YOURNAME"
        msg = f"Which language would you like to talk in? And what should I call you? 🤔\n\nReply like this:\nEnglish {username}"
        user_data[uid] = user_data.get(uid, {})
        user_data[uid]["awaiting_lang_nick"] = True
        bot.send_message(chat_id, msg)
        bot.answer_callback_query(call.id)
        return

    # GAME MENU (first screen)
    if call.data == "game_menu":
        game_kb = build_game_menu_keyboard()
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=game_kb)
        bot.answer_callback_query(call.id)
        return

    # BACK TO WELCOME
    if call.data == "back_to_welcome":
        kb = build_welcome_keyboard()
        try:
            bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=kb)
        except:
            bot.edit_message_text("Back to main menu ↓", chat_id=chat_id, message_id=call.message.message_id, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    # WORD / RPC / MATH placeholders
    if call.data in ["game_word","game_rpc","game_math"]:
        bot.answer_callback_query(call.id, "Coming soon 😉")
        return

    # ---------- TTT ENTRY ----------
    if call.data == "game_ttt":
        # Private chat → immediate 1v1 vs bot
        if call.message.chat.type == "private":
            ttt_reset_chat(chat_id)
            board = ttt_new_board()
            ttt_games[chat_id] = {
                "mode": "pvb",
                "board": board,
                "pX": uid,
                "pO": "bot",
                "turn": "X",
                "msg_id": None
            }
            text = "TicTacToe — You (X) vs Miss OG (O)\nYour turn!"
            kb = ttt_render_keyboard(board)
            msg = bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, reply_markup=kb)
            ttt_games[chat_id]["msg_id"] = msg.message_id
            bot.answer_callback_query(call.id)
            return
        else:
            # Group → open lobby (10s), join button
            if chat_id in ttt_games and ttt_games[chat_id].get("status") in ["lobby","active"]:
                bot.answer_callback_query(call.id, "A TTT game/lobby is already running in this chat.")
                return
            ttt_reset_chat(chat_id)
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(types.InlineKeyboardButton("✅ Join", callback_data="ttt_join"))
            kb.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_welcome"))
            msg = bot.edit_message_text(
                "🕹️ TicTacToe Lobby\nPlayer matching… 10s",
                chat_id=chat_id, message_id=call.message.message_id, reply_markup=kb
            )
            ttt_games[chat_id] = {
                "mode":"pvp",
                "status":"lobby",
                "host": uid,
                "player1": uid,
                "player2": None,
                "lobby_msg_id": msg.message_id,
                "lobby_expires_at": time.time()+10,
                "lobby_timer": None,
                "start_timer": None
            }
            # Start 10s countdown updater
            def lobby_countdown():
                while True:
                    g = ttt_games.get(chat_id)
                    if not g or g.get("status") != "lobby":
                        break
                    remaining = int(g["lobby_expires_at"] - time.time())
                    if remaining <= 0:
                        # timeout
                        if g.get("status") == "lobby":
                            try:
                                bot.edit_message_text(
                                    "⏳ Lobby timed out. No one joined.\nTap Game → TicTacToe again to host.",
                                    chat_id=chat_id, message_id=g["lobby_msg_id"], reply_markup=build_game_menu_keyboard()
                                )
                            except:
                                pass
                            ttt_reset_chat(chat_id)
                        break
                    # update message timer text
                    try:
                        kb2 = types.InlineKeyboardMarkup(row_width=1)
                        kb2.add(types.InlineKeyboardButton("✅ Join", callback_data="ttt_join"))
                        kb2.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_welcome"))
                        bot.edit_message_text(
                            f"🕹️ TicTacToe Lobby\nPlayer matching… {remaining}s",
                            chat_id=chat_id, message_id=g["lobby_msg_id"], reply_markup=kb2
                        )
                    except:
                        pass
                    time.sleep(1)

            t = threading.Thread(target=lobby_countdown, daemon=True)
            t.start()
            ttt_games[chat_id]["lobby_timer"] = t
            bot.answer_callback_query(call.id)
            return

    # GROUP: JOIN LOBBY
    if call.data == "ttt_join":
        g = ttt_games.get(chat_id)
        if not g or g.get("status") != "lobby":
            bot.answer_callback_query(call.id, "No active lobby.")
            return
        if uid == g["player1"]:
            bot.answer_callback_query(call.id, "You are already in lobby as Player 1.")
            return
        if g.get("player2"):
            bot.answer_callback_query(call.id, "Lobby is already full.")
            return

        g["player2"] = uid
        g["status"] = "starting"

        p1 = g["player1"]
        p1name = "@" + bot.get_chat_member(chat_id, p1).user.username if bot.get_chat_member(chat_id, p1).user.username else get_username_or_display(call.message)
        p2name = "@" + call.from_user.username if call.from_user.username else call.from_user.first_name

        # 3s start countdown then launch game
        def start_in_3s():
            try:
                for sec in [3,2,1]:
                    bot.edit_message_text(
                        f"Match found! {p1name} (X) vs {p2name} (O)\nGame starts in {sec}s…",
                        chat_id=chat_id, message_id=g["lobby_msg_id"]
                    )
                    time.sleep(1)
            except:
                pass
            # Start game
            board = ttt_new_board()
            ttt_games[chat_id] = {
                "mode":"pvp",
                "status":"active",
                "board": board,
                "pX": g["player1"],
                "pO": g["player2"],
                "turn":"X",
                "msg_id": g["lobby_msg_id"]
            }
            kb = ttt_render_keyboard(board)
            try:
                bot.edit_message_text(
                    f"TicTacToe — {p1name} (X) vs {p2name} (O)\nTurn: X",
                    chat_id=chat_id, message_id=g["lobby_msg_id"], reply_markup=kb
                )
            except:
                pass

        t = threading.Thread(target=start_in_3s, daemon=True)
        t.start()
        ttt_games[chat_id]["start_timer"] = t
        bot.answer_callback_query(call.id, "Joined! 🎮")
        return

    # ---------- TTT MOVE HANDLERS ----------
    if call.data.startswith("ttt_m_"):
        g = ttt_games.get(chat_id)
        if not g or g.get("status") not in ["active"] or "board" not in g:
            bot.answer_callback_query(call.id, "No active game.")
            return

        idx = int(call.data.split("_")[-1])
        if idx<0 or idx>8:
            bot.answer_callback_query(call.id, "Invalid cell.")
            return

        board = g["board"]
        if board[idx] != " ":
            bot.answer_callback_query(call.id, "Cell already taken!")
            return

        # Determine whose turn
        if g["mode"] == "pvp":
            current_symbol = g["turn"]
            current_uid = g["pX"] if current_symbol=="X" else g["pO"]
            other_uid   = g["pO"] if current_symbol=="X" else g["pX"]
            if uid != current_uid:
                bot.answer_callback_query(call.id, "Not your turn.")
                return
            # make move
            board[idx] = current_symbol
            # update UI
            winner = ttt_check_winner(board)
            if winner:
                end_text = ""
                if winner == "draw":
                    end_text = "Game over: Draw 🤝"
                else:
                    win_user = current_uid
                    win_name = "@"+bot.get_chat_member(chat_id, win_user).user.username if bot.get_chat_member(chat_id, win_user).user.username else "Player"
                    end_text = f"Game over: {win_name} ({winner}) wins! 🏆"
                kb = ttt_render_keyboard(board)
                # Disable further moves by changing callbacks to noop
                kb = ttt_render_keyboard(board, game_id_prefix="noop_")
                bot.edit_message_text(end_text, chat_id=chat_id, message_id=g["msg_id"], reply_markup=kb)
                ttt_reset_chat(chat_id)
                bot.answer_callback_query(call.id)
                return
            # switch turn
            g["turn"] = "O" if g["turn"]=="X" else "X"
            turn_text = f"Turn: {g['turn']}"
            kb = ttt_render_keyboard(board)
            bot.edit_message_text(
                f"TicTacToe — Turn: {g['turn']}",
                chat_id=chat_id, message_id=g["msg_id"], reply_markup=kb
            )
            bot.answer_callback_query(call.id)
            return

        elif g["mode"] == "pvb":
            # player's turn always X
            if g["turn"] != "X":
                bot.answer_callback_query(call.id, "Wait, my turn 😏")
                return
            board[idx] = "X"
            winner = ttt_check_winner(board)
            if winner:
                end_text = "Game over: Draw 🤝" if winner=="draw" else "You (X) win! 🏆"
                kb = ttt_render_keyboard(board, game_id_prefix="noop_")
                bot.edit_message_text(end_text, chat_id=chat_id, message_id=g["msg_id"], reply_markup=kb)
                ttt_reset_chat(chat_id)
                bot.answer_callback_query(call.id)
                return
            # bot move
            g["turn"] = "O"
            bot_move = ttt_bot_move(board)
            if bot_move is not None:
                board[bot_move] = "O"
            winner = ttt_check_winner(board)
            if winner:
                end_text = "Game over: Draw 🤝" if winner=="draw" else "Miss OG (O) wins! 😎"
                kb = ttt_render_keyboard(board, game_id_prefix="noop_")
                bot.edit_message_text(end_text, chat_id=chat_id, message_id=g["msg_id"], reply_markup=kb)
                ttt_reset_chat(chat_id)
                bot.answer_callback_query(call.id)
                return
            # back to player
            g["turn"] = "X"
            kb = ttt_render_keyboard(board)
            bot.edit_message_text("Your turn!", chat_id=chat_id, message_id=g["msg_id"], reply_markup=kb)
            bot.answer_callback_query(call.id)
            return

    # NOOP (to swallow taps on finished boards)
    if call.data.startswith("noop_"):
        bot.answer_callback_query(call.id, "Game finished.")
        return

# ---------- COMMANDS ----------
@bot.message_handler(commands=["start","help"])
def handle_start(message):
    send_welcome(message.chat.id)

# ---------- MESSAGES ----------
@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    uid = message.from_user.id
    text = (message.text or "").strip()
    user_data.setdefault(uid, {})
    user_data[uid]["last_active"] = time.time()

    # Language & nickname set
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

    # Abusive
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

# ---------- FLASK / WEBHOOK ----------
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
