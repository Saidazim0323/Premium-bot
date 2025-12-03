# database.py
import os
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.getenv("DATABASE_URL", "sqlite:///data/db.sqlite3").replace("sqlite:///", "")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

# tables
cur.execute("""
CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY,
  subscribed_until TEXT
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  amount INTEGER,
  method TEXT,
  created_at TEXT
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS referrals(
  invited_user INTEGER PRIMARY KEY,
  invited_by INTEGER
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS promocodes(
  code TEXT PRIMARY KEY,
  bonus_month INTEGER,
  discount INTEGER
)
""")
conn.commit()

# helpers
def add_subscription(user_id:int, months:int):
    cur.execute("SELECT subscribed_until FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    now = datetime.utcnow()
    if row and row[0]:
        current = datetime.fromisoformat(row[0])
        if current > now:
            new_until = current + timedelta(days=30*months)
        else:
            new_until = now + timedelta(days=30*months)
    else:
        new_until = now + timedelta(days=30*months)
    cur.execute("REPLACE INTO users(user_id, subscribed_until) VALUES(?,?)", (user_id, new_until.isoformat()))
    conn.commit()

def is_active(user_id:int) -> bool:
    cur.execute("SELECT subscribed_until FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if not row or not row[0]:
        return False
    return datetime.fromisoformat(row[0]) > datetime.utcnow()

def add_payment(user_id:int, amount:int, method:str):
    cur.execute("INSERT INTO payments(user_id, amount, method, created_at) VALUES(?,?,?,?)",
                (user_id, amount, method, datetime.utcnow().isoformat()))
    conn.commit()

def get_all_users():
    cur.execute("SELECT user_id, subscribed_until FROM users")
    return cur.fetchall()

def get_expired_users():
    cur.execute("SELECT user_id, subscribed_until FROM users")
    rows = cur.fetchall()
    from datetime import datetime
    expired = []
    for r in rows:
        try:
            until = datetime.fromisoformat(r[1])
            if until <= datetime.utcnow():
                expired.append(r[0])
        except:
            expired.append(r[0])
    return expired

def add_referral(invited_user:int, invited_by:int):
    try:
        cur.execute("INSERT INTO referrals(invited_user, invited_by) VALUES(?,?)", (invited_user, invited_by))
        conn.commit()
    except sqlite3.IntegrityError:
        pass

def add_promocode(code:str, bonus_month:int, discount:int):
    cur.execute("REPLACE INTO promocodes(code, bonus_month, discount) VALUES(?,?,?)",
                (code.upper(), bonus_month, discount))
    conn.commit()

def get_promocode(code:str):
    cur.execute("SELECT bonus_month, discount FROM promocodes WHERE code=?", (code.upper(),))
    return cur.fetchone()
