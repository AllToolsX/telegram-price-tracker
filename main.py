
import os
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import threading
import time
from flask import Flask

# --- Flask App Setup (To keep the bot alive on Render) ---
app = Flask(__name__)

@app.route('/')
def home():
    # This page will be pinged by UptimeRobot
    return "I am alive!", 200

def run_flask_app():
    app.run(host='0.0.0.0', port=8080)

# --- Main Bot Logic (Remains mostly the same) ---

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
        
# This is a simplified function to demonstrate the logic. 
# For a real bot, you'll expand this with more commands.
def handle_update(update):
    if "message" not in update:
        return

    chat_id = update["message"]["chat"]["id"]
    message_text = update["message"]["text"]
    
    if message_text == "/start":
        reply_text = "Welcome! Send me a link to get started."
        send_telegram_message(chat_id, reply_text)
    else:
        # You would add your price tracking logic here
        reply_text = f"You sent: {message_text}"
        send_telegram_message(chat_id, reply_text)
        
def poll_telegram_updates():
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
    offset = 0
    print("Bot polling started...")
    while True:
        try:
            poll_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=100"
            response = requests.get(poll_url, timeout=120)
            updates = response.json().get("result", [])
            
            if updates:
                for update in updates:
                    handle_update(update)
                    offset = update["update_id"] + 1
            
            time.sleep(1)
        except Exception as e:
            print(f"Error in polling: {e}")
            time.sleep(10)

if __name__ == "__main__":
    # Start the Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()
    
    # Start the Telegram bot polling in the main thread
    poll_telegram_updates()
