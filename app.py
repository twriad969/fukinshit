from flask import Flask, request, jsonify
from telethon import TelegramClient, events
import asyncio
import time
from collections import deque
import threading

# Telegram API details
api_id = 12380656
api_hash = 'd927c13beaaf5110f25c505b7c071273'
phone_number = '+8801686157963'

# Flask app
app = Flask(__name__)

# Shared asyncio event loop for Telegram client
telegram_loop = asyncio.new_event_loop()
asyncio.set_event_loop(telegram_loop)
client = TelegramClient('anon', api_id, api_hash)

# Limit counters
processed_links_last_30_minutes = deque()
processed_links_today = 0
daily_reset_timestamp = time.time()

# Limits
MAX_LINKS_30_MINUTES = 5000
MAX_LINKS_PER_DAY = 50000
THIRTY_MINUTES = 30 * 60
ONE_DAY = 24 * 60 * 60

# Initialize Telegram client
async def start_client():
    await client.start(phone=phone_number)
    print("Telegram client started!")

def start_telegram_loop():
    asyncio.set_event_loop(telegram_loop)
    telegram_loop.run_until_complete(start_client())
    telegram_loop.run_forever()

threading.Thread(target=start_telegram_loop, daemon=True).start()

# Graceful shutdown for Telegram client
def stop_telegram_client():
    asyncio.run_coroutine_threadsafe(client.disconnect(), telegram_loop)
    telegram_loop.stop()

# Interact with the bot
async def interact_with_bot(link_to_send):
    bot_response = None
    bot_username = '@LinkConvertTerabot'

    print(f"Sending the link to {bot_username}...")
    await client.send_message(bot_username, link_to_send)

    @client.on(events.NewMessage(from_users=bot_username))
    async def handler(event):
        nonlocal bot_response
        bot_response = event.message.text
        print("Bot response: ", bot_response)
        client.remove_event_handler(handler)

    start_time = time.time()
    while bot_response is None and time.time() - start_time < 30:
        await asyncio.sleep(1)

    return bot_response or link_to_send

# Helper to reset daily counters
def reset_daily_limit():
    global processed_links_today, daily_reset_timestamp
    processed_links_today = 0
    daily_reset_timestamp = time.time()

# Helper to clean up old timestamps
def clean_old_links():
    current_time = time.time()
    while processed_links_last_30_minutes and (current_time - processed_links_last_30_minutes[0]) > THIRTY_MINUTES:
        processed_links_last_30_minutes.popleft()

@app.route('/', methods=['GET'])
def send_link():
    global processed_links_today

    link = request.args.get('link')
    if not link:
        return jsonify({"error": "No link provided!"}), 400

    if time.time() - daily_reset_timestamp > ONE_DAY:
        reset_daily_limit()

    clean_old_links()

    if len(processed_links_last_30_minutes) >= MAX_LINKS_30_MINUTES or processed_links_today >= MAX_LINKS_PER_DAY:
        return jsonify({"response": link})

    future = asyncio.run_coroutine_threadsafe(interact_with_bot(link), telegram_loop)
    bot_response = future.result()

    unwanted_texts = [
        "Too many attempts, please try again later",
        "The shared file is no longer available",
        "ErrMsgLinkExpireFlag",
        "System is busy, Please try again"
    ]

    if any(unwanted_text in bot_response for unwanted_text in unwanted_texts):
        bot_response = link
    elif not bot_response.startswith('https://'):
        bot_response = link

    processed_links_last_30_minutes.append(time.time())
    processed_links_today += 1

    return jsonify({"response": bot_response})

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000)
    finally:
        stop_telegram_client()
