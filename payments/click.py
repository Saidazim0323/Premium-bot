# payments/click.py
import os, hashlib
from urllib.parse import quote_plus
from config import CLICK_MERCHANT_ID, CLICK_SECRET, DOMAIN, TEST_MODE

def create_click_link(amount:int, user_id:int):
    if TEST_MODE:
        # test link triggers our callback via browser (GET)
        return f"{DOMAIN}/click/callback?merchant_trans_id={user_id}&amount={amount}&sign=test"
    # Example signature — adapt to Click docs for production
    sign = hashlib.md5(f"{user_id}{amount}{CLICK_SECRET}".encode()).hexdigest()
    return f"https://my.click.uz/services/pay?merchant_id={CLICK_MERCHANT_ID}&amount={amount}&transaction_param={user_id}&sign={sign}&return_url={quote_plus(DOMAIN)}"

def verify_click(data:dict):
    if TEST_MODE:
        return True
    try:
        expected = hashlib.md5(f\"{data.get('merchant_trans_id')}{data.get('amount')}{CLICK_SECRET}\".encode()).hexdigest()
        return expected == data.get('sign','')
    except:
        return False
