# scheduler.py
import asyncio
from database import get_expired_users, remove_user
from aiogram import Bot
import os

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def auto_kick_task():
    bot = Bot(BOT_TOKEN)
    while True:
        expired = get_expired_users()
        for user_id in expired:
            try:
                # kick (ban then unban) to prevent immediate rejoin if desired
                await bot.ban_chat_member(CHANNEL_ID, user_id)
                await bot.unban_chat_member(CHANNEL_ID, user_id)
            except Exception:
                pass
        await asyncio.sleep(60 * 60)  # hourly
