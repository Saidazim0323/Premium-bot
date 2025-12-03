# main.py
import os
import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from database import add_subscription, add_payment, get_all_users, cur
from database import add_referral, add_promocode, get_promocode
from payments.click import create_click_link, verify_click
from payments.payme import create_payme_invoice, verify_payme
from scheduler import auto_kick_task

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Environment(loader=FileSystemLoader("templates"))

# ADMIN DASHBOARD
@app.get("/", response_class=HTMLResponse)
async def admin(request: Request, pw: str = ""):
    if pw != ADMIN_PASSWORD:
        return HTMLResponse("<h3>Unauthorized — provide ?pw=ADMIN_PASSWORD</h3>")
    cur.execute("SELECT user_id, subscribed_until FROM users")
    users = cur.fetchall()
    cur.execute("SELECT id, user_id, amount, method, created_at FROM payments ORDER BY created_at DESC")
    payments = cur.fetchall()
    t = templates.get_template("admin.html")
    return HTMLResponse(t.render(users=users, payments=payments))

@app.post("/add_promocode")
async def add_promocode_endpoint(code: str = Form(...), bonus: int = Form(...), discount: int = Form(...), pw: str = Form(...)):
    if pw != ADMIN_PASSWORD:
        return HTMLResponse("<h3>Unauthorized</h3>")
    add_promocode(code, bonus, discount)
    return JSONResponse({"status":"ok"})

# TELEGRAM WEBHOOK (set webhook to RENDER_URL + /webhook)
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update(**data)
    await dp.process_update(update)
    return JSONResponse({"ok": True})

# CREATE INVOICE ENDPOINTS (bot can call these)
@app.get("/create_invoice/click/{user_id}/{amount}")
async def create_click(user_id:int, amount:int):
    url = create_click_link(amount, user_id, test_mode=TEST_MODE)
    return JSONResponse({"url": url})

@app.get("/create_invoice/payme/{user_id}/{amount}")
async def create_payme(user_id:int, amount:int):
    url = create_payme_invoice(amount, user_id, test_mode=TEST_MODE)
    return JSONResponse({"url": url})

# CLICK CALLBACK
@app.post("/click/callback")
async def click_callback(request: Request):
    # Click may send form data; accept both JSON and form
    try:
        form = await request.form()
        data = dict(form)
    except:
        data = await request.json()
    ok = verify_click(data, test_mode=TEST_MODE)
    if not ok:
        return JSONResponse({"status":"error","reason":"invalid sign"})
    user_id = int(data.get("merchant_trans_id") or data.get("transaction_param") or 0)
    amount = int(float(data.get("amount", 0)))
    add_payment(user_id, amount, "click")
    # map amounts to months
    months = 1 if amount == 20000 else 3 if amount == 55000 else 6 if amount == 100000 else 1
    add_subscription(user_id, months)
    # referral reward: see referrals table logic (not auto here)
    # create one-time invite link
    try:
        invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
        await bot.send_message(user_id, f"✅ To'lov qabul qilindi. Kanalga kirish: {invite.invite_link}")
    except Exception:
        await bot.send_message(user_id, "To'lov qabul qilindi, lekin kanal linki berilmadi. Admin bilan bog'laning.")
    return JSONResponse({"status":"success"})

# PAYME CALLBACK
@app.post("/payme/callback")
async def payme_callback(request: Request):
    body = await request.json()
    method = body.get("method")
    params = body.get("params", {})
    if TEST_MODE:
        # test mode: accept simple query or perform-like payload
        user_id = int(params.get("account", {}).get("order_id") or request.query_params.get("params[account][order_id]") or 0)
        amount = int((params.get("amount") or request.query_params.get("params[amount]") or 0) / 100) if params.get("amount") else int(request.query_params.get("params[amount]",0))
        add_payment(user_id, amount, "payme_test")
        months = 1 if amount==20000 else 3 if amount==55000 else 6 if amount==100000 else 1
        add_subscription(user_id, months)
        try:
            invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
            await bot.send_message(user_id, f"✅ TEST To'lov qabul qilindi. Kanalga kirish: {invite.invite_link}")
        except:
            pass
        return JSONResponse({"result":{"ok":True}})
    # Real mode:
    if method == "PerformTransaction":
        user_id = int(params.get("account",{}).get("order_id") or 0)
        amount = int(params.get("amount",0)/100)
        # verify with verify_payme(...) if you implement
        add_payment(user_id, amount, "payme")
        months = 1 if amount==20000 else 3 if amount==55000 else 6 if amount==100000 else 1
        add_subscription(user_id, months)
        try:
            invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
            await bot.send_message(user_id, f"✅ To'lov qabul qilindi. Kanalga kirish: {invite.invite_link}")
        except:
            pass
        return JSONResponse({"result":{"transaction": params.get("id")}})
    return JSONResponse({"error":"unsupported"})

# BOT handlers (basic start + check + promo + referral)
from aiogram import types
from database import is_active, add_referral, get_promocode, add_promocode as db_add_promocode

@dp.message()
async def handle_messages(msg: types.Message):
    text = msg.text or ""
    user_id = msg.from_user.id
    # start with referral
    if text.startswith("/start"):
        parts = text.split()
        if len(parts) > 1:
            ref = parts[1]
            if ref.isdigit() and int(ref) != user_id:
                add_referral(user_id, int(ref))
        if is_active(user_id):
            await msg.reply("Sizda faol obuna mavjud ✅")
        else:
            await msg.reply("Obuna yo'q. /buy orqali obunani tanlang.")
    elif text.startswith("/buy"):
        # quick buy: /buy 1  -> 1 month
        parts = text.split()
        months = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        amount = 20000 if months==1 else 55000 if months==3 else 100000
        # create invoice url
        click_url = create_click_link(amount, user_id, test_mode=TEST_MODE)
        payme_url = create_payme_invoice(amount, user_id, test_mode=TEST_MODE)
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Click", url=click_url))
        kb.add(types.InlineKeyboardButton("Payme", url=payme_url))
        await msg.reply(f"To'lov uchun tanlang: {amount} soʻm", reply_markup=kb)
    elif text.startswith("/promo"):
        parts = text.split()
        if len(parts) < 2:
            await msg.reply("Promo kod yuboring: /promo CODE")
            return
        code = parts[1].upper()
        p = get_promocode(code)
        if not p:
            await msg.reply("Promo kod topilmadi.")
            return
        bonus, discount = p
        add_subscription(user_id, bonus)
        await msg.reply(f"Promo qabul qilindi! +{bonus} oy qo'shildi.")
    elif text == "/check":
        if is_active(user_id):
            await msg.reply("Obunangiz mavjud ✅")
        else:
            await msg.reply("Obuna topilmadi ❌")

# STARTUP: set webhook and background tasks
@app.on_event("startup")
async def on_startup():
    # set Telegram webhook if RENDER_URL provided
    if RENDER_URL:
        webhook_url = RENDER_URL.rstrip("/") + "/webhook"
        await bot.set_webhook(webhook_url)
    # start auto-kick task
    loop = asyncio.get_event_loop()
    loop.create_task(auto_kick_task())

# shutdown: delete webhook
@app.on_event("shutdown")
async def on_shutdown():
    try:
        await bot.delete_webhook()
    except:
        pass
