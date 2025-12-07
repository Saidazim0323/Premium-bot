import os
from dotenv import load_dotenv

# .env faylni yuklaymiz
load_dotenv()

def to_int(value, default=0):
    try:
        return int(value)
    except:
        return default

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = to_int(os.getenv("ADMIN_ID"))
CHANNEL_ID = to_int(os.getenv("CHANNEL_ID"))

# Admin panel paroli
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# CLICK to'lovi
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "")
CLICK_SECRET = os.getenv("CLICK_SECRET", "")

# PAYME to'lovi
PAYME_MERCHANT_ID = os.getenv("PAYME_MERCHANT_ID", "")
PAYME_SECRET = os.getenv("PAYME_SECRET", "")

# Domen (Render yoki boshqa server link)
DOMAIN = os.getenv("DOMAIN", "").rstrip("/")

# Test rejimi (true/false)
TEST_MODE = os.getenv("TEST_MODE", "true").strip().lower() == "true"

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/db.sqlite3")
