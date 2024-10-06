from telethon import TelegramClient, events
from quart import Quart, request, jsonify
import asyncio
import time
from collections import deque

# Telegram API details
api_id = 27938879
api_hash = '86e62beef8f4195662914ebc25008b43'
phone_number = '+8801790423900'

# Quart app (async version of Flask)
app = Quart(__name__)

# Global Telegram Client
client = TelegramClient('anon', api_id, api_hash)

# Limit counters
processed_links_last_30_minutes = deque()  # Track timestamps of the last 30 mins processed links
processed_links_today = 0  # Count of processed links today
daily_reset_timestamp = time.time()  # Timestamp when the daily limit was last reset

# Limits
MAX_LINKS_30_MINUTES = 5000
MAX_LINKS_PER_DAY = 50000
THIRTY_MINUTES = 30 * 60  # 30 minutes in seconds
ONE_DAY = 24 * 60 * 60  # 1 day in seconds

# Start the client globally once
@app.before_serving
async def startup():
    print("Starting Telegram client...")
    await client.start(phone=phone_number)

@app.after_serving
async def shutdown():
    print("Stopping Telegram client...")
    await client.disconnect()

# Interact with the bot in a non-blocking way
async def interact_with_bot(link_to_send):
    bot_response = None

    # The bot username
    bot_username = '@LinkConvertTerabot'

    # Send the link to the bot
    print(f"Sending the link to {bot_username}...")
    await client.send_message(bot_username, link_to_send)

    # Create an event handler to capture the bot's response
    @client.on(events.NewMessage(from_users=bot_username))
    async def handler(event):
        nonlocal bot_response
        bot_response = event.message.text
        print("Bot response: ", bot_response)
        # Stop listening once the response is captured
        client.remove_event_handler(handler)

    # Wait until the bot response is received or a timeout
    try:
        while bot_response is None:
            await asyncio.sleep(1)  # Non-blocking wait
    except asyncio.TimeoutError:
        bot_response = "Timed out waiting for bot's response"

    return bot_response

# Helper to reset daily counters
def reset_daily_limit():
    global processed_links_today, daily_reset_timestamp
    processed_links_today = 0
    daily_reset_timestamp = time.time()

# Helper to clean up old timestamps in the last 30-minute window
def clean_old_links():
    current_time = time.time()
    while processed_links_last_30_minutes and (current_time - processed_links_last_30_minutes[0]) > THIRTY_MINUTES:
        processed_links_last_30_minutes.popleft()

@app.route('/')
async def send_link():
    global processed_links_today

    # Get the link from the query parameters
    link = request.args.get('link')

    if not link:
        return jsonify({"error": "No link provided!"}), 400

    # Check if the link ends with `=1`
    if not link.endswith('=1'):
        return jsonify({"response": link})  # Return the original link if it doesn't end with `=1`

    # Remove `=1` from the link before processing
    link = link[:-2]

    # Reset daily limit if a new day has started
    if time.time() - daily_reset_timestamp > ONE_DAY:
        reset_daily_limit()

    # Clean up old links from the 30-minute window
    clean_old_links()

    # Check if either the 30-minute or daily limit has been exceeded
    if len(processed_links_last_30_minutes) >= MAX_LINKS_30_MINUTES or processed_links_today >= MAX_LINKS_PER_DAY:
        return jsonify({"response": link + '=1'})  # Return the original link if limits are exceeded

    # Run the Telegram client interaction asynchronously
    bot_response = await interact_with_bot(link)

    # List of texts that indicate an issue with the bot response
    unwanted_texts = [
        "Too many attempts, please try again later",
        "The shared file is no longer available",
        "ErrMsgLinkExpireFlag"
    ]

    # Check if the bot response contains any unwanted text
    if any(unwanted_text in bot_response for unwanted_text in unwanted_texts):
        bot_response = link  # Return the original link if any unwanted text is found
    elif not bot_response.startswith('https://'):
        bot_response = link  # Return the original link if the bot's response is invalid

    # Add `=1` back to the bot's response
    bot_response += "=1"

    # Track this link processing event
    processed_links_last_30_minutes.append(time.time())  # Record the current timestamp
    processed_links_today += 1  # Increment the daily counter

    # Return the bot's response as JSON
    return jsonify({"response": bot_response})

if __name__ == '__main__':
    # Run the Quart app using Uvicorn for async support
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)
