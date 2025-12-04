import os
import asyncio
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Update

from database import (
    add_user, get_all_users, set_subscription, add_payment,
    add_promocode, get_promocode, is_active, add_referral
)
from payments.click import create_click_link, verify_click
from payments.payme import create_payme_invoice, verify_payme
from scheduler import auto_kick_task
from config import BOT_TOKEN, ADMIN_PASSWORD, CHANNEL_ID, DOMAIN, TEST_MODE

# --- Initialize Bot & App ---
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- Helper: Process Payment ---
async def process_payment(user_id: int, amount: int, method: str, test: bool = False):
    add_payment(user_id, amount, method)
    months = 1 if amount == 20000 else 3 if amount == 55000 else 6 if amount == 100000 else 1
    set_subscription(user_id, months)

    try:
        invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
        msg_prefix = "✅ TEST" if test else "✅"
        await bot.send_message(user_id, f"{msg_prefix} To'lov qabul qilindi. Kanalga kirish: {invite.invite_link}")
    except Exception as e:
        await bot.send_message(user_id, "To'lov qabul qilindi, ammo kanal linki yaratilmadi. Admin bilan bog'laning.")


# --- Admin Dashboard ---
@app.get("/", response_class=HTMLResponse)
async def admin_index(request: Request, pw: str = ""):
    if pw != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")

    users = get_all_users()
    cur = __import__("database").cur
    cur.execute("SELECT id, user_id, amount, method, created_at FROM payments ORDER BY created_at DESC")
    payments = cur.fetchall()
    return templates.TemplateResponse("admin.html", {"request": request, "users": users, "payments": payments, "admin_pw": ADMIN_PASSWORD})


@app.post("/add_promocode")
async def add_promocode_endpoint(
    code: str = Form(...),
    bonus: int = Form(...),
    discount: int = Form(...),
    pw: str = Form(...)
):
    if pw != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")

    add_promocode(code, bonus, discount)
    return JSONResponse({"status": "ok"})


# --- Telegram Webhook ---
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update(**data)
    await dp.feed_update(bot, update)
    return JSONResponse({"ok": True})


# --- Create Invoice Endpoints ---
@app.get("/create_invoice/click/{user_id}/{amount}")
async def create_click_invoice(user_id: int, amount: int):
    return JSONResponse({"url": create_click_link(amount, user_id)})


@app.get("/create_invoice/payme/{user_id}/{amount}")
async def create_payme_invoice(user_id: int, amount: int):
    return JSONResponse({"url": create_payme_invoice(amount, user_id)})


# --- Click Callback ---
@app.post("/click/callback")
async def click_callback(request: Request):
    try:
        form = await request.form()
        data = dict(form)
    except Exception:
        data = await request.json()

    if not verify_click(data):
        return JSONResponse({"status": "error", "reason": "invalid sign"})

    user_id = int(data.get("merchant_trans_id") or data.get("transaction_param") or 0)
    amount = int(float(data.get("amount", 0)))
    await process_payment(user_id, amount, "click")

    return JSONResponse({"status": "success"})


# --- Payme Callback ---
@app.post("/payme/callback")
async def payme_callback(request: Request):
    body = await request.json()
    params = body.get("params", {})

    if TEST_MODE:
        user_id = int(params.get("account", {}).get("order_id") or 0)
        amount = int(params.get("amount", 0)) // 100
        await process_payment(user_id, amount, "payme_test", test=True)
        return JSONResponse({"result": {"ok": True}})

    method = body.get("method")
    if method == "PerformTransaction":
        user_id = int(params.get("account", {}).get("order_id") or 0)
        amount = int(params.get("amount", 0)) // 100
        await process_payment(user_id, amount, "payme")
        return JSONResponse({"result": {"transaction": params.get("id")}})

    return JSONResponse({"error": "unsupported"})


# --- Bot Handlers ---
@dp.message()
async def handle_all(message: types.Message):
    text = (message.text or "").strip()
    user_id = message.from_user.id

    add_user(user_id, getattr(message.from_user, "username", None))

    if text.startswith("/start"):
        parts = text.split()
        if len(parts) > 1 and parts[1].isdigit():
            add_referral(user_id, int(parts[1]))

        if is_active(user_id):
            await message.reply("Sizda faol obuna mavjud ✅")
        else:
            await message.reply("Obuna yo'q. /buy 1 — 1 oy, /buy 3 — 3 oy, /buy 6 — 6 oy")

    elif text.startswith("/buy"):
        parts = text.split()
        months = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        amount = 20000 if months == 1 else 55000 if months == 3 else 100000

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Click", url=create_click_link(amount, user_id))],
            [InlineKeyboardButton(text="Payme", url=create_payme_invoice(amount, user_id))]
        ])
        await message.reply(f"To'lov uchun tanlang: {amount} so'm", reply_markup=kb)

    elif text.startswith("/promo"):
        parts = text.split()
        if len(parts) < 2:
            await message.reply("Promo kod yuboring: /promo CODE")
            return

        code = parts[1].upper()
        promo = get_promocode(code)
        if not promo:
            await message.reply("Promo kod topilmadi.")
            return

        bonus, discount = promo
        set_subscription(user_id, bonus)
        await message.reply(f"Promo qabul qilindi! +{bonus} oy qo'shildi.")

    elif text == "/check":
        if is_active(user_id):
            await message.reply("Sizda faol obuna mavjud ✅")
        else:
            await message.reply("Obuna topilmadi ❌")


# --- Startup & Shutdown Events ---
@app.on_event("startup")
async def on_startup():
    if DOMAIN:
        webhook_url = DOMAIN.rstrip("/") + "/webhook"
        try:
            await bot.set_webhook(webhook_url)
            print(f"Webhook set to {webhook_url}")
        except Exception as e:
            print("Webhook set error:", e)

    asyncio.create_task(auto_kick_task())


@app.on_event("shutdown")
async def on_shutdown():
    try:
        await bot.delete_webhook()
    finally:
        await bot.session.close()
        
