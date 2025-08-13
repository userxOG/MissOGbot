# main.py
import os
import time
import random
from flask import Flask, request
import telebot
from telebot import types
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Set TELEGRAM_BOT_TOKEN in env")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# --- Config / state ---
BOT_NAME = "Miss OG"
OWNER_USERNAME = "userxOG"
SPECIAL_USER_ID = None  # set numeric id if you want special mention behavior

# Keep per-message TicTacToe state keyed by (chat_id, message_id)
ttt_games = {}  # { (chat_id, message_id): { board: [' ']*9, mode: 'vs_bot'|'vs_players', turn: 'X'|'O', players: { 'X': user_id, 'O': user_id or None }, starter_id: user_id } }

# --- Utilities ---
def get_display_name_from_user(user):
    if user.username:
        return "@" + user.username
    name = (user.first_name or "") + (" " + user.last_name if user.last_name else "")
    return name.strip() or "User"

def make_ttt_markup(board):
    """Return InlineKeyboardMarkup for current board"""
    markup = types.InlineKeyboardMarkup()
    buttons = []
    for i in range(9):
        symbol = board[i]
        label = symbol if symbol != " " else " "
        # Use callback data 'ttt_move:{i}'
        buttons.append(types.InlineKeyboardButton(label, callback_data=f"ttt_move:{i}"))
    # add rows
    for r in range(0,9,3):
        markup.row(buttons[r], buttons[r+1], buttons[r+2])
    return markup

def render_board_text(board):
    # Use emojis for display
    def e(c):
        if c == "X": return "❌"
        if c == "O": return "⭕"
        return "▫️"
    return f"{e(board[0])}{e(board[1])}{e(board[2])}\n{e(board[3])}{e(board[4])}{e(board[5])}\n{e(board[6])}{e(board[7])}{e(board[8])}"

WIN_COMBOS = [
    (0,1,2),(3,4,5),(6,7,8),
    (0,3,6),(1,4,7),(2,5,8),
    (0,4,8),(2,4,6)
]

def check_winner(board):
    """Return 'X' or 'O' if winner, 'Draw' if full and no winner, else None"""
    for a,b,c in WIN_COMBOS:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    if all(cell != " " for cell in board):
        return "Draw"
    return None

def start_ttt_game(chat_id, as_message_id, mode, starter_user):
    """Create initial ttt game and send board message (returns message)"""
    board = [" "] * 9
    players = {'X': starter_user.id if starter_user else None, 'O': None}
    game = {
        "board": board,
        "mode": mode,                # 'vs_bot' or 'vs_players'
        "turn": "X",                 # X always starts
        "players": players,
        "starter_id": starter_user.id if starter_user else None,
        "message_id": None,          # will set after sending
        "chat_id": chat_id
    }
    # initial board message
    text = f"TicTacToe — {'You vs Miss OG' if mode=='vs_bot' else 'Player vs Player (first click = X)'}\n\n{render_board_text(board)}\n\nTurn: ❌ (X)"
    markup = make_ttt_markup(board)
    sent = bot.send_message(chat_id, text, reply_markup=markup)
    game["message_id"] = sent.message_id
    ttt_games[(chat_id, sent.message_id)] = game
    return sent

def end_game_update(chat_id, message_id, result_text):
    """Edit message to show final board + result + action buttons."""
    key = (chat_id, message_id)
    game = ttt_games.get(key)
    if not game:
        return
    board = game["board"]
    text = f"TicTacToe — Result\n\n{render_board_text(board)}\n\n{result_text}"
    # Play Again and Menu buttons
    buttons = types.InlineKeyboardMarkup(row_width=2)
    buttons.add(
        types.InlineKeyboardButton("🔁 Play Again", callback_data=f"ttt_playagain:{message_id}"),
        types.InlineKeyboardButton("📋 Menu", callback_data=f"ttt_menu:{message_id}")
    )
    bot.edit_message_text(text, chat_id, message_id, reply_markup=buttons)

def reset_game_same_players(chat_id, message_id):
    key = (chat_id, message_id)
    game = ttt_games.get(key)
    if not game:
        return
    game["board"] = [" "] * 9
    game["turn"] = "X"
    # For vs_players we keep players; for vs_bot keep same starter
    text = f"TicTacToe — Restarted\n\n{render_board_text(game['board'])}\n\nTurn: ❌ (X)"
    markup = make_ttt_markup(game["board"])
    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)

# --- Welcome & game menu ---
def send_welcome(chat_id, is_group=False):
    bot_user = bot.get_me()
    bot_username = bot_user.username if bot_user else "MissOGbot"
    markup = types.InlineKeyboardMarkup(row_width=2)
    # row 1
    markup.add(
        types.InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_username}?startgroup=true"),
        types.InlineKeyboardButton("📢 MissOG_News", url="https://t.me/MissOG_News")
    )
    # row 2
    markup.add(types.InlineKeyboardButton("💬 Talk More", callback_data="talk_more"))
    # row 3: Game button (single)
    markup.add(types.InlineKeyboardButton("🎮 Game", callback_data="game_menu"))
    intro = (
        "✨️ Hello! I’m Miss OG — your elegant, loving & cheeky AI companion made with love by @userxOG ❤️\n"
        "Here to upgrade your chats with style, fun, and just the right amount of sass.\n\n"
        "Click below to add me to more groups, get the latest news, chat more, or explore games."
    )
    bot.send_message(chat_id, intro, reply_markup=markup)

@bot.message_handler(commands=["start","help"])
def cmd_start(message):
    send_welcome(message.chat.id, is_group=(message.chat.type != "private"))

# game menu callback -> show games list
@bot.callback_query_handler(func=lambda c: c.data == "game_menu")
def show_game_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    # Provide Word Guessing etc. (we keep others simple for now)
    markup.add(
        types.InlineKeyboardButton("🎲 Word Guessing", callback_data="game_word"),
        types.InlineKeyboardButton("⭕ TicTacToe", callback_data="game_ttt")
    )
    markup.add(
        types.InlineKeyboardButton("✊✌️✋ RPC", callback_data="game_rpc"),
        types.InlineKeyboardButton("➗ Quick Math", callback_data="game_math")
    )
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

# handle selecting TicTacToe from menu -> ask mode
@bot.callback_query_handler(func=lambda c: c.data == "game_ttt")
def on_select_ttt(call):
    # show options Vs Miss OG and Vs Others
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Vs Miss OG (Play vs bot)", callback_data="ttt_start_vs_bot"),
        types.InlineKeyboardButton("Vs Others (Player vs Player)", callback_data="ttt_start_vs_players")
    )
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)

# Start modes
@bot.callback_query_handler(func=lambda c: c.data.startswith("ttt_start_"))
def on_start_mode(call):
    data = call.data
    chat_id = call.message.chat.id
    user = call.from_user
    if data == "ttt_start_vs_bot":
        # In private chat: start immediately for private; in group we also allow vs bot (bot plays O)
        sent = start_ttt_game(chat_id, None, mode="vs_bot", starter_user=user)
        bot.answer_callback_query(call.id, "Started TicTacToe vs Miss OG. You are ❌ (X).")
    elif data == "ttt_start_vs_players":
        # Create an invite message: starter becomes X; game created and waiting for other player to play (auto-join on first O move)
        board = [" "] * 9
        players = {'X': user.id, 'O': None}
        text = f"TicTacToe — Player vs Player\n\n{render_board_text(board)}\n\n{get_display_name_from_user(user)} started the game as ❌ (X). Waiting for another player to join as ⭕ (O). First different user to press a cell will become O and can play."
        markup = make_ttt_markup(board)
        sent = bot.send_message(chat_id, text, reply_markup=markup)
        ttt_games[(chat_id, sent.message_id)] = {
            "board": board,
            "mode": "vs_players",
            "turn": "X",
            "players": players,
            "starter_id": user.id,
            "message_id": sent.message_id,
            "chat_id": chat_id
        }
        bot.answer_callback_query(call.id, "Player vs Player started. Waiting for opponent.")
    else:
        bot.answer_callback_query(call.id, "Unknown option.")

# Handle ttt cell presses
@bot.callback_query_handler(func=lambda c: c.data.startswith("ttt_move:"))
def on_ttt_move(call):
    data = call.data.split(":")
    if len(data) != 2:
        bot.answer_callback_query(call.id, "Invalid move.")
        return
    idx = int(data[1])
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    key = (chat_id, message_id)
    game = ttt_games.get(key)
    user = call.from_user

    if not game:
        bot.answer_callback_query(call.id, "Game not found or already finished.")
        return

    board = game["board"]
    mode = game["mode"]
    turn = game["turn"]
    players = game["players"]

    # Check valid index
    if idx < 0 or idx > 8:
        bot.answer_callback_query(call.id, "Invalid cell.")
        return

    # If cell occupied
    if board[idx] != " ":
        bot.answer_callback_query(call.id, "Cell already taken.")
        return

    # Determine who is allowed to move
    if mode == "vs_bot":
        # In vs_bot, only the starter user (X) should make moves; after X moves, bot will move automatically.
        starter_id = game["starter_id"]
        # If message is in group, many users could press; restrict to starter only
        if user.id != starter_id:
            bot.answer_callback_query(call.id, "Only the player who started the game can play against Miss OG.")
            return
        # It's human's turn?
        if turn != "X":
            bot.answer_callback_query(call.id, "Wait for your turn.")
            return
        # Make human move as X
        board[idx] = "X"
        # Check winner
        winner = check_winner(board)
        if winner:
            # X might win immediately
            if winner == "X":
                result_text = f"🎉 You win! {get_display_name_from_user(user)} beat Miss OG."
            elif winner == "O":
                result_text = "😢 You lose! Miss OG won."
            else:  # Draw
                result_text = "Game over: Draw 🤝"
            end_game_update(chat_id, message_id, result_text)
            # remove game state
            ttt_games.pop(key, None)
            bot.answer_callback_query(call.id)
            return
        # If not finished, bot (O) moves
        # simple bot move: random available
        avail = [i for i,c in enumerate(board) if c == " "]
        if avail:
            bot_idx = random.choice(avail)
            board[bot_idx] = "O"
            game["turn"] = "X"  # back to human
            winner2 = check_winner(board)
            if winner2:
                if winner2 == "X":
                    result_text = f"🎉 You win! {get_display_name_from_user(user)} beat Miss OG."
                elif winner2 == "O":
                    result_text = "😢 You lose! Miss OG won."
                else:
                    result_text = "Game over: Draw 🤝"
                end_game_update(chat_id, message_id, result_text)
                ttt_games.pop(key, None)
                bot.answer_callback_query(call.id)
                return
        # Update message board and continue
        text = f"TicTacToe — You vs Miss OG\n\n{render_board_text(board)}\n\nTurn: ❌ (X)"
        markup = make_ttt_markup(board)
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
        ttt_games[key] = game
        bot.answer_callback_query(call.id)
        return

    else:  # mode == 'vs_players'
        # If O player is not yet set and the pressing user is different than starter -> auto-join as O and treat move as their move if their turn
        starter_id = game["starter_id"]
        x_id = players.get("X")
        o_id = players.get("O")
        # Determine caller role
        caller_role = None
        if user.id == x_id:
            caller_role = "X"
        elif o_id and user.id == o_id:
            caller_role = "O"
        else:
            # not previously joined as O
            if user.id != x_id and o_id is None:
                # auto-join as O and allow them to play if it's O's turn; otherwise they become O and wait
                players["O"] = user.id
                o_id = user.id
                caller_role = "O"
            else:
                # someone else (not starter and O already assigned) trying to play
                bot.answer_callback_query(call.id, "You are not part of this game.")
                return

        # Now ensure it's caller's turn
        if game["turn"] != caller_role:
            bot.answer_callback_query(call.id, "Wait for your turn.")
            return

        # place move
        board[idx] = caller_role
        # switch turn
        game["turn"] = "O" if game["turn"] == "X" else "X"

        # check winner
        winner = check_winner(board)
        if winner:
            # Build proper display names
            x_user = None
            o_user = None
            try:
                x_user = bot.get_chat_member(chat_id, players["X"]).user
            except Exception:
                x_user = None
            if players.get("O"):
                try:
                    o_user = bot.get_chat_member(chat_id, players["O"]).user
                except Exception:
                    o_user = None

            x_name = get_display_name_from_user(x_user) if x_user else str(players.get("X"))
            o_name = get_display_name_from_user(o_user) if o_user else str(players.get("O"))

            if winner == "X":
                # X won
                if players.get("O") and players.get("X"):
                    result_text = f"🎉 {x_name} won against {o_name}!"
                else:
                    # shouldn't happen
                    result_text = f"🎉 {x_name} wins!"
            elif winner == "O":
                if players.get("O") and players.get("X"):
                    result_text = f"🎉 {o_name} won against {x_name}!"
                else:
                    result_text = f"🎉 {o_name} wins!"
            else:  # Draw
                # draw case handled below but keep for completeness
                result_text = f"Game over: Draw 🤝 (between {x_name} and {o_name})"
            end_game_update(chat_id, message_id, result_text)
            ttt_games.pop(key, None)
            bot.answer_callback_query(call.id)
            return

        # if draw
        if check_winner(board) == "Draw":
            x_user = None
            o_user = None
            try:
                x_user = bot.get_chat_member(chat_id, players["X"]).user
            except Exception:
                x_user = None
            if players.get("O"):
                try:
                    o_user = bot.get_chat_member(chat_id, players["O"]).user
                except Exception:
                    o_user = None
            x_name = get_display_name_from_user(x_user) if x_user else str(players.get("X"))
            o_name = get_display_name_from_user(o_user) if o_user else str(players.get("O"))
            result_text = f"Game over: Draw 🤝 (between {x_name} and {o_name})"
            end_game_update(chat_id, message_id, result_text)
            ttt_games.pop(key, None)
            bot.answer_callback_query(call.id)
            return

        # otherwise update board and continue
        text = f"TicTacToe — Player vs Player\n\n{render_board_text(board)}\n\nTurn: {'❌ (X)' if game['turn']=='X' else '⭕ (O)'}"
        markup = make_ttt_markup(board)
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
        # store updated players / board
        ttt_games[key] = game
        bot.answer_callback_query(call.id)
        return

# Play again and menu handlers
@bot.callback_query_handler(func=lambda c: c.data.startswith("ttt_playagain:") or c.data.startswith("ttt_menu:"))
def on_playagain_or_menu(call):
    data = call.data
    parts = data.split(":")
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "Invalid command.")
        return
    cmd, msgid_s = parts
    message_id = int(msgid_s)
    chat_id = call.message.chat.id
    key = (chat_id, message_id)
    game = ttt_games.get(key)

    if cmd == "ttt_playagain":
        # If game state missing, we can't reset players; create fresh based on previous if existed
        if not game:
            # Try to rebuild minimal info from message author (starter)
            # For safety, start a fresh vs_players with caller as starter
            starter = call.from_user
            board = [" "] * 9
            players = {'X': starter.id, 'O': None}
            text = f"TicTacToe — Player vs Player\n\n{render_board_text(board)}\n\n{get_display_name_from_user(starter)} started the game as ❌ (X). Waiting for another player to join as ⭕ (O). First different user to press a cell will become O and can play."
            sent = bot.send_message(chat_id, text, reply_markup=make_ttt_markup(board))
            ttt_games[(chat_id, sent.message_id)] = {
                "board": board,
                "mode": "vs_players",
                "turn": "X",
                "players": players,
                "starter_id": starter.id,
                "message_id": sent.message_id,
                "chat_id": chat_id
            }
            bot.answer_callback_query(call.id, "Started a new Player-vs-Player game.")
            return
        # Reset board but keep same players
        game["board"] = [" "] * 9
        game["turn"] = "X"
        # Edit message to new board
        text = f"TicTacToe — Restarted\n\n{render_board_text(game['board'])}\n\nTurn: ❌ (X)"
        bot.edit_message_text(text, chat_id, message_id, reply_markup=make_ttt_markup(game["board"]))
        ttt_games[key] = game
        bot.answer_callback_query(call.id, "Game restarted.")
        return

    if cmd == "ttt_menu":
        # Remove any stored state for this message
        ttt_games.pop(key, None)
        # Show main welcome menu again (we'll just edit to show the menu)
        bot.edit_message_text("Back to menu.", chat_id, message_id, reply_markup=None)
        send_welcome(chat_id, is_group=(call.message.chat.type != "private"))
        bot.answer_callback_query(call.id)
        return

# placeholders for other games
@bot.callback_query_handler(func=lambda c: c.data in ("game_word","game_rpc","game_math"))
def other_games_placeholder(call):
    bot.answer_callback_query(call.id, "This game is coming soon 🎮")

# Flask webhook endpoints
app = Flask(__name__)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "Miss OG TicTacToe ready 💖"

if __name__ == "__main__":
    # If using a hosting that requires webhook, set env var RENDER_EXTERNAL_URL or similar and configure webhook manually
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        bot.remove_webhook()
        bot.set_webhook(url=f"{render_url}/{BOT_TOKEN}")
        print("Webhook set.")
    print("Starting app...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
