from telethon import TelegramClient, events
from flask import Flask, request, jsonify
import asyncio

# Telegram API details
api_id = 27938879
api_hash = '86e62beef8f4195662914ebc25008b43'
phone_number = '+8801790423900'

# Flask app
app = Flask(__name__)

async def interact_with_bot(link_to_send):
    bot_response = None

    # Create a new Telegram client for each request
    async with TelegramClient('anon', api_id, api_hash) as client:
        # Connect to the client
        await client.start(phone=phone_number)

        # The bot username
        bot_username = '@LinkConvertTerabot'

        # Send the link to the bot
        print(f"Sending the link to {bot_username}...")
        await client.send_message(bot_username, link_to_send)

        # Wait for the bot's response
        @client.on(events.NewMessage(from_users=bot_username))
        async def handler(event):
            nonlocal bot_response
            # Capture the bot's response
            bot_response = event.message.text
            print("Bot response: ", bot_response)

            # Disconnect after getting the bot's response
            await client.disconnect()

        # Keep the script running until we get the bot's response
        await client.run_until_disconnected()

    return bot_response

@app.route('/')
def send_link():
    # Get the link from the query parameters
    link = request.args.get('link')

    if not link:
        return jsonify({"error": "No link provided!"}), 400

    # Run the Telegram client and interact with the bot asynchronously
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot_response = loop.run_until_complete(interact_with_bot(link))

    # Return the bot's response as JSON
    if bot_response:
        return jsonify({"response": bot_response})
    else:
        return jsonify({"error": "No response from bot!"}), 500

if __name__ == '__main__':
    # Start the Flask server
    app.run(host='0.0.0.0', port=5000)
