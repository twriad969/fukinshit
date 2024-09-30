from telethon import TelegramClient

# Use your own values from my.telegram.org
api_id = 27938879
api_hash = '86e62beef8f4195662914ebc25008b43'

# The first parameter is the .session file name (absolute paths allowed)
with TelegramClient('anon', api_id, api_hash) as client:
    client.loop.run_until_complete(client.send_message('me', 'Hello, myself!'))