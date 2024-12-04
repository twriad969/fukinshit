from telethon import TelegramClient, events
from quart import Quart, request, jsonify
import asyncio
import time
from collections import deque
import os
import requests
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
import urllib.parse

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

# Flask API for link resolution
flask_app = Flask(__name__)

# Add more comprehensive CORS configuration
cors_config = {
    'origins': [
        'http://localhost:3000',  # React development server
        'https://nanoplayer.vercel.app',  # Production domain (replace with actual domain)
        'http://127.0.0.1:3000',  # Alternative localhost
        '*'  # Wildcard for development (remove in production)
    ],
    'methods': ['GET', 'OPTIONS'],
    'allow_headers': [
        'Content-Type', 
        'Authorization', 
        'Access-Control-Allow-Credentials'
    ]
}

# Apply CORS with more granular configuration
CORS(flask_app, 
     resources={r"/*": cors_config},
     supports_credentials=True  # Allow credentials if needed
)

def resolve_link(link):
    """
    Attempt to resolve and validate the given link.
    
    Args:
        link (str): The original link to resolve
    
    Returns:
        str: A resolved, safe URL or the original link
    """
    try:
        # Decode the link in case it's URL encoded
        decoded_link = urllib.parse.unquote(link)
        
        # Add some basic validation
        if not decoded_link.startswith(('http://', 'https://')):
            return link
        
        # Follow redirects and get the final URL
        response = requests.head(
            decoded_link, 
            allow_redirects=True, 
            timeout=5,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        
        # Return the final URL after redirects
        return response.url
    
    except requests.exceptions.RequestException as e:
        # If resolution fails, return original link
        print(f"Link resolution error: {e}")
        return link

@flask_app.route('/', methods=['GET'])
def resolve_video_link():
    """
    Endpoint to resolve video links.
    
    Query Parameters:
        link (str): The video link to resolve
    
    Returns:
        JSON response with resolved link
    """
    link = request.args.get('link')
    
    if not link:
        abort(400, description="No link provided")
    
    try:
        resolved_link = resolve_link(link)
        return jsonify({
            "response": resolved_link,
            "original_link": link
        })
    
    except Exception as e:
        return jsonify({
            "error": str(e),
            "original_link": link
        }), 500

@flask_app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": str(error)}), 400

@flask_app.errorhandler(500)
def server_error(error):
    return jsonify({"error": "Internal server error"}), 500

@app.route('/flask', methods=['GET'])
async def flask_api():
    return flask_app.run(host='0.0.0.0', port=5001, debug=True)

@app.route('/')
async def send_link():
    global processed_links_today

    # Get the link from the query parameters
    link = request.args.get('link')

    if not link:
        return jsonify({"error": "No link provided!"}), 400

    # Reset daily limit if a new day has started
    if time.time() - daily_reset_timestamp > ONE_DAY:
        reset_daily_limit()

    # Clean up old links from the 30-minute window
    clean_old_links()

    # Check if either the 30-minute or daily limit has been exceeded
    if len(processed_links_last_30_minutes) >= MAX_LINKS_30_MINUTES or processed_links_today >= MAX_LINKS_PER_DAY:
        return jsonify({"response": link})  # Return the original link if limits are exceeded

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

    # Track this link processing event
    processed_links_last_30_minutes.append(time.time())  # Record the current timestamp
    processed_links_today += 1  # Increment the daily counter

    # Return the bot's response as JSON
    return jsonify({"response": bot_response})

if __name__ == '__main__':
    # Run the Quart app using Uvicorn for async support
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)
