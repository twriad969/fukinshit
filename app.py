from telethon import TelegramClient, events
from quart import Quart, request, jsonify
import asyncio

# Telegram API details
api_id = 27938879
api_hash = '86e62beef8f4195662914ebc25008b43'
phone_number = '+8801790423900'

# Quart app (async version of Flask)
app = Quart(__name__)

# Global Telegram Client
client = TelegramClient('anon', api_id, api_hash)

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

@app.route('/')
async def send_link():
    # Get the link from the query parameters
    link = request.args.get('link')

    if not link:
        return jsonify({"error": "No link provided!"}), 400

    # Check if the link originally has `=1` at the end
    had_equal_one = link.endswith('=1')

    # Remove `=1` from the link if it exists
    if had_equal_one:
        link = link[:-2]

    # Run the Telegram client interaction asynchronously
    bot_response = await interact_with_bot(link)

    # If the original link had `=1`, add `=1` back to the bot's response
    if bot_response and had_equal_one:
        bot_response += "=1"

    # Return the bot's response as JSON
    if bot_response:
        return jsonify({"response": bot_response})
    else:
        return jsonify({"error": "No response from bot!"}), 500

if __name__ == '__main__':
    # Run the Quart app using Uvicorn for async support
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)
