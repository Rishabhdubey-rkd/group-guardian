import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
from pyrogram import Client,filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import re
import json
from pathlib import Path
import config

url = "https://api.safone.me/nsfw"
SPOILER = config.SPOILER_MODE
slangf = 'slang_words.txt'
with open(slangf, 'r') as f:
    slang_words = set(line.strip().lower() for line in f)

Bot = Client(
    "antinude",
    bot_token=config.BOT_TOKEN,
    api_id=config.API_ID,
    api_hash=config.API_HASH
)

#-----------------------------------------------------------------

@Bot.on_message(filters.private & filters.command(["start", "help"]))
async def start(bot, update):
    text = (
        "Welcome to Group Guardian!\\n\\n"
        "I help keep your Telegram group safe with word filtering "
        "and image filtering.\\n\\n"
        "Add me to your group and promote me to admin to use "
        "the moderation features."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Help & Commands", callback_data="help")],
        [InlineKeyboardButton("➕ Add to Group", url="https://t.me/" + (await bot.get_me()).username + "?startgroup=true")]
    ])
    await update.reply(text, reply_markup=keyboard)

@Bot.on_callback_query(filters.regex("^help$"))
async def help_menu(bot, query):
    await query.answer()
    await query.message.edit_text(
        "📚 Help & Commands\\n\\n"
        "/start - Open the welcome menu\\n"
        "/help - Show this help menu\\n\\n"
        "Current features: inappropriate-word filtering and image filtering in groups."
    )

#-----------------------------------------------------------------

@Bot.on_message(filters.group & filters.photo)
async def image(bot, message):
    sender = await Bot.get_chat_member(message.chat.id, message.from_user.id)
    isadmin = sender.privileges
    if not isadmin:
        x = await message.download()
        files = {"image": open(x, "rb")}
        roi = requests.post(url, files=files)
        data = roi.json()
        nsfw = data["data"]["is_nsfw"]
        porn = data["data"]["porn"]
        if nsfw:
            name = message.from_user.first_name
            await message.delete()
            if SPOILER:
                await message.reply_photo(x, caption=f"""**WARNING ⚠️** (nude photo)

 **{name}** sent a nude photo

{porn}% porn""", has_spoiler = True)


#-----------------------------------------------------------------

@Bot.on_message(filters.group & filters.text)
async def slang(bot, message):
    sender = await Bot.get_chat_member(message.chat.id, message.from_user.id)
    isadmin = sender.privileges
    if not isadmin:
        sentence = message.text
        sent = re.sub(r'\W+', ' ', sentence)
        isslang = False
        for word in sent.split():
            if word.lower() in slang_words:
                isslang = True
                await message.delete()
                sentence = sentence.replace(word, f'||{word}||')
        if isslang:
            name = message.from_user.first_name
            msgtxt = f"""{name} your message has been deleted due to the presence of inappropriate language. Here is a censored version of your message:

{sentence}
            """
            if SPOILER:
                await message.reply(msgtxt)

#--------------------------------------------------------------------------------------------------


# --- Added group commands ---
DATA_FILE = "group_data.json"

def load_group_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_group_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

@Bot.on_message((filters.private | filters.group) & filters.command("id"))
async def show_id(bot, message):
    user_id = message.from_user.id if message.from_user else "Unavailable"
    await message.reply_text(
        f"Your ID: {user_id}\nChat ID: {message.chat.id}"
    )

@Bot.on_message(filters.group & filters.command("rules"))
async def show_rules(bot, message):
    data = load_group_data()
    rules = data.get(str(message.chat.id), {}).get("rules")
    await message.reply_text(
        rules if rules else "No rules set yet. An admin can use /setrules followed by the rules."
    )

@Bot.on_message(filters.group & filters.command("setrules"))
async def set_rules(bot, message):
    if not message.from_user:
        return
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ("administrator", "owner"):
        await message.reply_text("Only group admins can set rules.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage: /setrules Be respectful and follow group rules.")
        return
    data = load_group_data()
    data.setdefault(str(message.chat.id), {})["rules"] = parts[1]
    save_group_data(data)
    await message.reply_text("Group rules saved!")

@Bot.on_message(filters.group & filters.command("filter"))
async def add_filter(bot, message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply_text("Usage: /filter trigger reply")
        return
    data = load_group_data()
    group = data.setdefault(str(message.chat.id), {})
    group.setdefault("filters", {})[parts[1].lower()] = parts[2]
    save_group_data(data)
    await message.reply_text(f"Filter saved for: {parts[1]}")

@Bot.on_message(filters.group & filters.command("filters"))
async def list_filters(bot, message):
    data = load_group_data()
    saved = data.get(str(message.chat.id), {}).get("filters", {})
    if not saved:
        await message.reply_text("No custom filters saved.")
    else:
        await message.reply_text("Saved filters:\n" + "\n".join(saved.keys()))

@Bot.on_message(filters.group & filters.command("stop"))
async def remove_filter(bot, message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage: /stop trigger")
        return
    data = load_group_data()
    saved = data.get(str(message.chat.id), {}).get("filters", {})
    if saved.pop(parts[1].lower(), None) is None:
        await message.reply_text("That filter was not found.")
    else:
        save_group_data(data)
        await message.reply_text("Filter removed.")

@Bot.on_message(filters.group & filters.text, group=1)
async def respond_to_filter(bot, message):
    if not message.text or message.text.startswith("/"):
        return
    data = load_group_data()
    saved = data.get(str(message.chat.id), {}).get("filters", {})
    text = message.text.lower()
    for trigger, response in saved.items():
        if trigger in text:
            await message.reply_text(response)
            break


Bot.run()
