# Final corrected code for Axesso API on RapidAPI

import os
import requests
import json
import threading
import time
from flask import Flask

database = {}

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running.", 200

def run_flask_app():
    app.run(host='0.0.0.0', port=10000)

def get_product_details_from_api(url: str):
    RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY')
    if not RAPIDAPI_KEY:
        print("Error: RAPIDAPI_KEY not found in environment variables.")
        return None

    try:
        # Extract ASIN from any Amazon URL format
        asin = None
        if '/dp/' in url:
            asin = url.split('/dp/')[1].split('/')[0].split('?')[0]
        elif '/gp/product/' in url:
            asin = url.split('/gp/product/')[1].split('/')[0].split('?')[0]
        
        if not asin:
            print(f"Could not extract ASIN from URL: {url}")
            return None
    except IndexError:
        print(f"Could not extract ASIN from URL: {url}")
        return None
    
    # This is the correct API endpoint for product details
    api_url = "https://axesso-axesso-amazon-data-service-v1.p.rapidapi.com/amz/amazon-search-by-asin"
    
    querystring = {"asin": asin}
    
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "axesso-axesso-amazon-data-service-v1.p.rapidapi.com"
    }
    
    try:
        response = requests.get(api_url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data and data.get('responseStatus') == 'SUCCESS' and data.get('product'):
            product_data = data['product']
            title = product_data.get('productTitle', 'Product')
            price = product_data.get('price', {}).get('currentPrice', 0)
            
            # Ensure price is an integer
            if price:
                price = int(price)
            else:
                price = 0

            return {"title": title, "price": price}
        else:
            print(f"API returned an error or no product data: {data.get('message', 'Unknown error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error calling RapidAPI for ASIN {asin}: {e}")
        return None

def send_telegram_message(chat_id, text):
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
    send_message_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(send_message_url, json=payload)
    except Exception as e:
        print(f"Error sending message: {e}")

def handle_update(update):
    if "message" not in update: return

    chat_id = update["message"]["chat"]["id"]
    message_text = update["message"]["text"]
    
    if message_text == "/start":
        send_telegram_message(chat_id, "Welcome! Send an Amazon product link to track its price.")
    
    elif 'amazon' in message_text or 'amzn' in message_text:
        send_telegram_message(chat_id, "⏳ *Fetching product details via API...*")
        details = get_product_details_from_api(message_text)
        
        if details and details.get("price") is not None:
            title, price = details["title"], details["price"]
            
            if price > 0:
                database[message_text] = {"chat_id": chat_id, "title": title, "last_price": price}
                reply_message = (
                    f"✅ **Tracking Started!**\n\n"
                    f"**Product:** `{title}`\n"
                    f"**Current Price:** `₹{price}`"
                )
            else:
                reply_message = f"Found product: `{title}`\nBut the price is currently unavailable."

            send_telegram_message(chat_id, reply_message)
        else:
            send_telegram_message(chat_id, "❌ Sorry, I could not fetch details. The product might be unavailable or the API limit is reached.")
    else:
        send_telegram_message(chat_id, "This is not a valid Amazon link.")

def poll_telegram_updates():
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
    offset = 0
    print("Bot polling started...")
    while True:
        try:
            poll_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=60"
            response = requests.get(poll_url, timeout=70)
            updates = response.json().get("result", [])
            
            if updates:
                for update in updates:
                    handle_update(update)
                    offset = update["update_id"] + 1
                    
        except Exception as e:
            print(f"Error in polling: {e}")
            time.sleep(15)

# Price checker function is omitted for simplicity for now.
# The main goal is to get the initial price fetch working reliably.

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()
    
    poll_telegram_updates()
