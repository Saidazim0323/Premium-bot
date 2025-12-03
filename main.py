# main.py
import os, asyncio
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from database import add_user, get_user, set_subscription, add_payment, get_all_users, get_expired_users, add_promocode, get_promocode
from payments.click import create_click_link, verify_click
from payments.payme import create_payme_invoice, verify_payme
from scheduler import auto_kick_task
from config import BOT_TOKEN, ADMIN_PASSWORD, CHANNEL_ID, DOMAIN, TEST_MODE

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Environment(loader=FileSystemLoader("templates"))

# Admin dashboard
@app.get("/", response_class=HTMLResponse)
async def admin_index(request: Request, pw: str = ""):
    if pw != ADMIN_PASSWORD:
        return HTMLResponse("<h3>Unauthorized — use ?pw=ADMIN_PASSWORD</h3>")
    users = get_all_users()
    cur = __import__("database").cur
    cur.execute("SELECT id, user_id, amount, method, created_at FROM payments ORDER BY created_at DESC")
    payments = cur.fetchall()
    t = templates.get_template("admin.html")
    return HTMLResponse(t.render(users=users, payments=payments, admin_pw=ADMIN_PASSWORD))

@app.post("/add_promocode")
async def add_promocode_endpoint(code: str = Form(...), bonus: int = Form(...), discount: int = Form(...), pw: str = Form(...)):
    if pw != ADMIN_PASSWORD:
        return HTMLResponse("<h3>Unauthorized</h3>")
    add_promocode(code, bonus, discount)
    return JSONResponse({"status":"ok"})

# Telegram webhook
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update(**data)
    await dp.process_update(update)
    return JSONResponse({"ok": True})

# Create invoice endpoints (bot uses these)
@app.get("/create_invoice/click/{user_id}/{amount}")
async def create_click_invoice(user_id:int, amount:int):
    url = create_click_link(amount, user_id)
    return JSONResponse({"url": url})

@app.get("/create_invoice/payme/{user_id}/{amount}")
async def create_payme_invoice(user_id:int, amount:int):
    url = create_payme_invoice(amount, user_id)
    return JSONResponse({"url": url})

# Click callback
@app.post("/click/callback")
async def click_callback(request: Request):
    # accept both form and json
    try:
        form = await request.form()
        data = dict(form)
    except:
        data = await request.json()
    ok = verify_click(data)
    if not ok:
        return JSONResponse({"status":"error","reason":"invalid sign"})
    user_id = int(data.get("merchant_trans_id") or data.get("transaction_param") or 0)
    amount = int(float(data.get("amount",0)))
    add_payment(user_id, amount, "click")
    months = 1 if amount==20000 else 3 if amount==55000 else 6 if amount==100000 else 1
    set_subscription(user_id, months)
    # send one-time invite
    try:
        invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
        await bot.send_message(user_id, f"✅ To'lov qabul qilindi. Kanalga kirish: {invite.invite_link}")
    except Exception as e:
        await bot.send_message(user_id, "To'lov qabul qilindi, ammo kanal linki yaratilmadi. Admin bilan bog'laning.")
    return JSONResponse({"status":"success"})

# Payme callback
@app.post("/payme/callback")
async def payme_callback(request: Request):
    body = await request.json()
    # support test mode simple params in query
    if TEST_MODE:
        # allow both query params and JSON
        q = request.query_params
        user_id = int(q.get("params[account][order_id]") or body.get("params",{}).get("account",{}).get("order_id") or 0)
        amount = int((q.get("params[amount]") or body.get("params",{}).get("amount") or 0))
        if amount and amount > 1000:  # amount in cents in some tests
            amount = int(amount/100)
        add_payment(user_id, amount, "payme_test")
        months = 1 if amount==20000 else 3 if amount==55000 else 6 if amount==100000 else 1
        set_subscription(user_id, months)
        try:
            invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
            await bot.send_message(user_id, f"✅ TEST To'lov qabul qilindi. Kanalga kirish: {invite.invite_link}")
        except:
            pass
        return JSONResponse({"result": {"ok": True}})
    # real Payme handling (simplified)
    method = body.get("method")
    if method == "PerformTransaction":
        params = body.get("params", {})
        user_id = int(params.get("account",{}).get("order_id") or 0)
        amount = int(params.get("amount",0)/100) if params.get("amount") else 0
        add_payment(user_id, amount, "payme")
        months = 1 if amount==20000 else 3 if amount==55000 else 6 if amount==100000 else 1
        set_subscription(user_id, months)
        try:
            invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
            await bot.send_message(user_id, f"✅ To'lov qabul qilindi. Kanalga kirish: {invite.invite_link}")
        except:
            pass
        return JSONResponse({"result":{"transaction": params.get("id")}})
    return JSONResponse({"error":"unsupported"})

# BOT handlers (basic)
@dp.message()
async def handle_all(msg):
    text = (msg.text or "").strip()
    user_id = msg.from_user.id
    from database import add_user, get_user
    add_user(user_id, getattr(msg.from_user, "username", None))
    if text.startswith("/start"):
        # referral: /start 12345
        parts = text.split()
        if len(parts) > 1 and parts[1].isdigit():
            ref = int(parts[1])
            add_ref = __import__("database").add_referral
            add_ref(user_id, ref)
        if __import__("database").is_active(user_id):
            await msg.reply("Sizda faol obuna mavjud ✅")
        else:
            await msg.reply("Obuna yo'q. /buy 1 — 1 oy, /buy 3 — 3 oy, /buy 6 — 6 oy")
    elif text.startswith("/buy"):
        parts = text.split()
        months = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        amount = 20000 if months==1 else 55000 if months==3 else 100000
        click_url = create_click_link(amount, user_id)
        payme_url = create_payme_invoice(amount, user_id)
        kb = __import__("aiogram").types.InlineKeyboardMarkup()
        kb.add(__import__("aiogram").types.InlineKeyboardButton("Click", url=click_url))
        kb.add(__import__("aiogram").types.InlineKeyboardButton("Payme", url=payme_url))
        await msg.reply(f"To'lov uchun tanlang: {amount} so'm", reply_markup=kb)
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
        set_subscription(user_id, bonus)
        await msg.reply(f"Promo qabul qilindi! +{bonus} oy qo'shildi.")
    elif text == "/check":
        if __import__("database").is_active(user_id):
            await msg.reply("Sizda faol obuna mavjud ✅")
        else:
            await msg.reply("Obuna topilmadi ❌")

# Startup: set webhook and start kicker
@app.on_event("startup")
async def on_startup():
    # set webhook if DOMAIN provided
    if DOMAIN:
        webhook_url = DOMAIN.rstrip("/") + "/webhook"
        try:
            await bot.set_webhook(webhook_url)
            print("Webhook set to", webhook_url)
        except Exception as e:
            print("Webhook set error:", e)
    # start auto-kick background
    loop = asyncio.get_event_loop()
    loop.create_task(auto_kick_task())

@app.on_event("shutdown")
async def on_shutdown():
    try:
        await bot.delete_webhook()
    except:
        pass
    await bot.session.close()
