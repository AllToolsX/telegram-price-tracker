import os
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import threading
import time
from flask import Flask

# This is a temporary in-memory database.
# Note: Data will be lost if the bot restarts on Render's free tier.
database = {}

# --- Flask App Setup (To keep the bot alive on Render) ---
app = Flask(__name__)

@app.route('/')
def home():
    # This page will be pinged to keep the service alive
    return "Bot is running.", 200

def run_flask_app():
    # Runs the Flask app
    app.run(host='0.0.0.0', port=10000)

# --- Bot Logic ---

def get_product_details(url: str):
    API_KEY = os.environ.get('SCRAPER_API_KEY')
    if not API_KEY:
        print("Error: SCRAPER_API_KEY not found.")
        return None
        
    encoded_url = urllib.parse.quote(url)
    scraperapi_url = f'http://api.scraperapi.com?api_key={API_KEY}&url={encoded_url}'
    
    try:
        response = requests.get(scraperapi_url, timeout=45)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "lxml")
        
        title_element = soup.find(id="productTitle")
        title = title_element.get_text(strip=True) if title_element else "Product"

        price = None
        price_span = soup.find("span", {"class": "a-price-whole"})
        if price_span:
            price_text = price_span.get_text(strip=True).replace(',', '').replace('.', '')
            price = int(price_text)
        else:
            price_span_2 = soup.select_one('.a-price .a-offscreen')
            if price_span_2:
                price_text = ''.join(filter(str.isdigit, price_span_2.get_text()))
                price = int(price_text[:-2]) if len(price_text) > 2 else int(price_text)
        
        return {"title": title, "price": price}
        
    except requests.exceptions.RequestException as e:
        print(f"Error calling ScraperAPI for {url}: {e}")
        return None

def send_telegram_message(chat_id, text):
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
    if not TELEGRAM_TOKEN:
        print("Telegram Token not set.")
        return

    send_message_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(send_message_url, json=payload)
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")

def handle_update(update):
    if "message" not in update:
        return

    chat_id = update["message"]["chat"]["id"]
    message_text = update["message"]["text"]
    
    if message_text == "/start":
        reply_text = "Welcome! Send an Amazon link to track its price."
        send_telegram_message(chat_id, reply_text)
    
    elif message_text == "/myproducts":
        user_products = [url for url, data in database.items() if data.get("chat_id") == chat_id]
        if not user_products:
            send_telegram_message(chat_id, "You are not tracking any products yet.")
            return
        
        message = "📜 **You are currently tracking:**\n\n"
        for i, url in enumerate(user_products, 1):
            title = database[url].get("title", "Product")
            last_price = database[url].get("last_price", "N/A")
            message += f"*{i}.* `{title}`\n   - *Last Price:* `₹{last_price}`\n\n"
        send_telegram_message(chat_id, message)
        
    elif 'amazon' in message_text or 'amzn' in message_text:
        send_telegram_message(chat_id, "⏳ *Fetching product details...*")
        details = get_product_details(message_text)
        
        if details and details.get("price"):
            title, price = details["title"], details["price"]
            database[message_text] = {"chat_id": chat_id, "title": title, "initial_price": price, "last_price": price}
            
            reply_message = (
                f"✅ **Tracking Started!**\n\n"
                f"**Product:** `{title}`\n"
                f"**Current Price:** `₹{price}`\n\n"
                f"I will notify you if the price drops."
            )
            send_telegram_message(chat_id, reply_message)
        else:
            send_telegram_message(chat_id, "❌ Sorry, I could not fetch the product details.")
    else:
        send_telegram_message(chat_id, "This is not a valid Amazon link.")

def poll_telegram_updates():
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
    offset = 0
    print("Bot polling started in a separate thread...")
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

def price_checker_job():
    print("Background price checker thread started...")
    while True:
        # Check every 1 hour
        time.sleep(3600) 
        print("Running background price check...")
        for url, data in list(database.items()):
            try:
                details = get_product_details(url)
                if details and details.get("price"):
                    current_price, last_price = details["price"], data["last_price"]
                    
                    if current_price < last_price:
                        chat_id, title = data["chat_id"], data["title"]
                        message = (
                            f"🚨 **PRICE DROP ALERT!** 🚨\n\n"
                            f"**Product:** `{title}`\n"
                            f"**Old Price:** `~₹{last_price}~`\n"
                            f"**New Price:** **`₹{current_price}`**\n\n"
                            f"Grab the deal now:\n{url}"
                        )
                        send_telegram_message(chat_id, message)
                        
                        database[url]["last_price"] = current_price
            except Exception as e:
                print(f"Error in price_checker_job for {url}: {e}")

if __name__ == "__main__":
    # Start the Flask app
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()
    
    # Start the background price checker
    checker_thread = threading.Thread(target=price_checker_job)
    checker_thread.start()
    
    # Start the Telegram bot polling
    poll_telegram_updates()
