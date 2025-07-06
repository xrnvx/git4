import os
from datetime import datetime
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# Configuration from environment
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
MONGO_URI = os.environ["MONGO_URI"]
DB_CHANNEL = int(os.environ["DB_CHANNEL"])
INITIAL_ADMINS = [int(x) for x in os.environ.get("INITIAL_ADMINS", "").split(",") if x]
INITIAL_FORCE_CHANNELS = [int(x) for x in os.environ.get("INITIAL_FORCE_CHANNELS", "").split(",") if x]

# MongoDB setup
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.get_database("telegram_bot")
admins_col = db.get_collection("admins")
force_col = db.get_collection("force_channels")
files_col = db.get_collection("files")

# Seed initial data
if admins_col.count_documents({}) == 0 and INITIAL_ADMINS:
    admins_col.insert_many([{"user_id": uid} for uid in INITIAL_ADMINS])
if force_col.count_documents({}) == 0 and INITIAL_FORCE_CHANNELS:
    force_col.insert_many([{"channel_id": cid} for cid in INITIAL_FORCE_CHANNELS])

# Pyrogram Client
bot = Client(
    "file_sharing_force_sub",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

async def is_admin(user_id: int) -> bool:
    return admins_col.count_documents({"user_id": user_id}) > 0

async def check_force_sub(client: Client, message: Message):
    user_id = message.from_user.id
    for fc in force_col.find():
        chan_id = fc["channel_id"]
        try:
            mem = await client.get_chat_member(chan_id, user_id)
            if mem.status not in ["member", "creator", "administrator"]:
                # Prepare button to join channel
                chat = await client.get_chat(chan_id)
                if chat.username:
                    url = f"https://t.me/{chat.username}"
                else:
                    id_str = str(chan_id)
                    url = f"https://t.me/c/{id_str.lstrip('-100')}"
                keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Join Channel", url=url)]]
