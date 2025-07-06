import os
from datetime import datetime
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import Message

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
db = mongo_client["telegram_bot"]
admins_col = db["admins"]
force_col = db["force_channels"]
files_col = db["files"]

# Seed initial data
if admins_col.count_documents({}) == 0 and INITIAL_ADMINS:
    admins_col.insert_many([{"user_id": uid} for uid in INITIAL_ADMINS])
if force_col.count_documents({}) == 0 and INITIAL_FORCE_CHANNELS:
    force_col.insert_many([{"channel_id": cid} for cid in INITIAL_FORCE_CHANNELS])

# Pyrogram Client
bot = Client("force_sub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

async def is_admin(user_id: int) -> bool:
    return admins_col.count_documents({"user_id": user_id}) > 0

async def check_force_sub(client: Client, message: Message):
    user_id = message.from_user.id
    for fc in force_col.find():
        chan_id = fc["channel_id"]
        try:
            mem = await client.get_chat_member(chan_id, user_id)
            if mem.status not in ["member", "creator", "administrator"]:
                await message.reply(f"⚠️ Anda harus bergabung dulu di channel: {chan_id}")
                return False
        except:
            await message.reply(f"⚠️ Gagal memeriksa keanggotaan di channel: {chan_id}")
            return False
    return True

@bot.on_message(filters.command("addadmin") & filters.private)
async def add_admin(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    try:
        new_id = int(message.text.split()[1])
        if admins_col.count_documents({"user_id": new_id}) == 0:
            admins_col.insert_one({"user_id": new_id})
            await message.reply(f"✅ Admin berhasil ditambahkan: {new_id}")
        else:
            await message.reply("⚠️ User tersebut sudah menjadi admin.")
    except:
        await message.reply("Usage: /addadmin <user_id>")

@bot.on_message(filters.command("deladmin") & filters.private)
async def del_admin(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    try:
        old_id = int(message.text.split()[1])
        res = admins_col.delete_one({"user_id": old_id})
        if res.deleted_count:
            await message.reply(f"✅ Admin berhasil dihapus: {old_id}")
        else:
            await message.reply("⚠️ User tersebut bukan admin.")
    except:
        await message.reply("Usage: /deladmin <user_id>")

@bot.on_message(filters.command("addforce") & filters.private)
async def add_force(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    try:
        chan_id = int(message.text.split()[1])
        if force_col.count_documents({"channel_id": chan_id}) == 0:
            force_col.insert_one({"channel_id": chan_id})
            await message.reply(f"✅ Channel force-sub berhasil ditambahkan: {chan_id}")
        else:
            await message.reply("⚠️ Channel tersebut sudah ada di list.")
    except:
        await message.reply("Usage: /addforce <channel_id>")

@bot.on_message(filters.command("delforce") & filters.private)
async def del_force(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    try:
        chan_id = int(message.text.split()[1])
        res = force_col.delete_one({"channel_id": chan_id})
        if res.deleted_count:
            await message.reply(f"✅ Channel force-sub berhasil dihapus: {chan_id}")
        else:
            await message.reply("⚠️ Channel tersebut tidak ditemukan.")
    except:
        await message.reply("Usage: /delforce <channel_id>")

@bot.on_message(filters.private & (filters.document | filters.photo))
async def handle_upload(client: Client, message: Message):
    if not await check_force_sub(client, message):
        return
    try:
        new_msg = await client.copy_message(
            chat_id=DB_CHANNEL,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        if new_msg.document:
            file_id = new_msg.document.file_id
            file_name = new_msg.document.file_name
        elif new_msg.photo:
            file_id = new_msg.photo.file_id
            file_name = f"photo_{file_id}"
        else:
            return
        files_col.insert_one({
            "file_id": file_id,
            "file_name": file_name,
            "uploader_id": message.from_user.id,
            "upload_date": datetime.utcnow()
        })
        await message.reply(f"✅ File berhasil di-upload.\nFile ID: `{file_id}`")
    except Exception as e:
        await message.reply(f"❌ Gagal upload file: {e}")

if __name__ == "__main__":
    print("Bot is starting...")
    bot.run()
