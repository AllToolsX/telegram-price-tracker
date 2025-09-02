import os
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse

def get_product_details(url: str):
    API_KEY = os.environ.get('SCRAPER_API_KEY')
    if not API_KEY:
        print("Error: SCRAPER_API_KEY not found.")
        return None
        
    encoded_url = urllib.parse.quote(url)
    scraperapi_url = f'http://api.scraperapi.com?api_key={API_KEY}&url={encoded_url}'
    
    try:
        response = requests.get(scraperapi_url, timeout=30)
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

def handle_telegram_webhook(request):
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
    if not TELEGRAM_TOKEN:
        return "Telegram Token not set.", 500

    # Extract the message data from Telegram's request
    update = request.get_json()
    
    if "message" not in update:
        return "OK", 200

    chat_id = update["message"]["chat"]["id"]
    message_text = update["message"]["text"]
    
    # This is where the main logic of your bot goes
    if message_text == "/start":
        reply_text = "Welcome! Send me an Amazon link to get its price."
    elif "amazon" in message_text or "amzn" in message_text:
        details = get_product_details(message_text)
        if details and details.get("price"):
            title, price = details["title"], details["price"]
            reply_text = (
                f"✅ **Product Found!**\n\n"
                f"**Product:** `{title}`\n"
                f"**Current Price:** `₹{price}`"
            )
        else:
            reply_text = "❌ Sorry, I could not fetch the product details."
    else:
        reply_text = "Please send a valid Amazon link."

    # Send the reply back to the user
    send_message_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": reply_text,
        "parse_mode": "Markdown"
    }
    requests.post(send_message_url, json=payload)
    
    # Tell Telegram "I got the message, thank you"
    return "OK", 200
