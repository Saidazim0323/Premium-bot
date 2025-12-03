# scheduler.py
import asyncio
from database import get_expired_users
from aiogram import Bot
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID","0"))

async def auto_kick_task():
    bot = Bot(BOT_TOKEN)
    while True:
        expired = get_expired_users()
        for user_id in expired:
            try:
                # ban then unban to kick
                await bot.ban_chat_member(CHANNEL_ID, user_id)
                await bot.unban_chat_member(CHANNEL_ID, user_id)
                print(f"Kicked expired user {user_id}")
            except Exception as e:
                print("Kick error:", e)
        await asyncio.sleep(60*60)  # check hourly
