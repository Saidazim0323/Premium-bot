# database.py
import os, sqlite3
from datetime import datetime, timedelta

DB_PATH = os.getenv("DATABASE_URL", "sqlite:///data/db.sqlite3").replace("sqlite:///", "")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY,
  username TEXT,
  referral_by INTEGER,
  promo_code TEXT,
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
CREATE TABLE IF NOT EXISTS promocodes(
  code TEXT PRIMARY KEY,
  bonus_month INTEGER,
  discount INTEGER
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS referrals(
  invited_user INTEGER PRIMARY KEY,
  invited_by INTEGER
)
""")
conn.commit()

def add_user(user_id:int, username:str=None, referral_by:int=None):
    cur.execute("INSERT OR IGNORE INTO users(user_id, username, referral_by) VALUES(?,?,?)",
                (user_id, username, referral_by))
    conn.commit()

def get_user(user_id:int):
    cur.execute("SELECT user_id, username, referral_by, promo_code, subscribed_until FROM users WHERE user_id=?",
                (user_id,))
    return cur.fetchone()

def set_subscription(user_id:int, months:int):
    now = datetime.utcnow()
    cur.execute("SELECT subscribed_until FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if row and row[0]:
        try:
            current = datetime.fromisoformat(row[0])
        except:
            current = now
        if current > now:
            new_until = current + timedelta(days=30*months)
        else:
            new_until = now + timedelta(days=30*months)
    else:
        new_until = now + timedelta(days=30*months)
    cur.execute("UPDATE users SET subscribed_until=? WHERE user_id=?", (new_until.isoformat(), user_id))
    conn.commit()

def is_active(user_id:int)->bool:
    cur.execute("SELECT subscribed_until FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if not row or not row[0]:
        return False
    try:
        return datetime.fromisoformat(row[0]) > datetime.utcnow()
    except:
        return False

def add_payment(user_id:int, amount:int, method:str):
    cur.execute("INSERT INTO payments(user_id, amount, method, created_at) VALUES(?,?,?,?)",
                (user_id, amount, method, datetime.utcnow().isoformat()))
    conn.commit()

def add_promocode(code:str, bonus_month:int, discount:int):
    cur.execute("REPLACE INTO promocodes(code, bonus_month, discount) VALUES(?,?,?)",
                (code.upper(), bonus_month, discount))
    conn.commit()

def get_promocode(code:str):
    cur.execute("SELECT bonus_month, discount FROM promocodes WHERE code=?", (code.upper(),))
    return cur.fetchone()

def add_referral(invited_user:int, invited_by:int):
    try:
        cur.execute("INSERT INTO referrals(invited_user, invited_by) VALUES(?,?)", (invited_user, invited_by))
        conn.commit()
    except sqlite3.IntegrityError:
        pass

def get_all_users():
    cur.execute("SELECT user_id, subscribed_until FROM users")
    return cur.fetchall()

def get_expired_users():
    cur.execute("SELECT user_id, subscribed_until FROM users")
    rows = cur.fetchall()
    expired = []
    from datetime import datetime
    for r in rows:
        try:
            if r[1] is None:
                continue
            until = datetime.fromisoformat(r[1])
            if until <= datetime.utcnow():
                expired.append(r[0])
        except:
            expired.append(r[0])
    return expired
