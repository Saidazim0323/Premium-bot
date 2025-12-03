# config.py
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "")
CLICK_SECRET = os.getenv("CLICK_SECRET", "")
PAYME_MERCHANT_ID = os.getenv("PAYME_MERCHANT_ID", "")
PAYME_SECRET = os.getenv("PAYME_SECRET", "")

DOMAIN = os.getenv("DOMAIN", "")  # e.g. https://yourapp.up.railway.app
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/db.sqlite3")
