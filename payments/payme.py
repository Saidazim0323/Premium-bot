# payments/payme.py
import os, requests
from config import PAYME_MERCHANT_ID, PAYME_SECRET, DOMAIN, TEST_MODE

PAYME_API = "https://checkout.paycom.uz/api"

def create_payme_invoice(amount:int, user_id:int):
    if TEST_MODE:
        # construct a simple URL that triggers our callback
        return f"{DOMAIN}/payme/callback?method=PerformTransaction&params[account][order_id]={user_id}&params[amount]={amount*100}"
    payload = {
        "id": 1,
        "method":"invoice.create",
        "params":{
            "amount": amount * 100,
            "account": {"order_id": str(user_id)},
            "description": "Premium subscription",
            "callback_url": DOMAIN + "/payme/callback"
        }
    }
    headers = {"X-Auth": PAYME_SECRET}
    r = requests.post(PAYME_API, json=payload, headers=headers, timeout=10)
    j = r.json()
    if "result" in j:
        return "https://checkout.paycom.uz/" + str(j["result"].get("invoice_id",""))
    return None

def verify_payme(payload:dict):
    if TEST_MODE:
        return True
    # Implement real verification per Payme docs
    return False
