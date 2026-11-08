import os
from telethon import TelegramClient, events
from telethon.errors.rpcerrorlist import AuthKeyError
from telethon.sync import TelegramClient as SyncTelegramClient

api_id = int(os.getenv('TG_API_ID', '0'))
api_hash = os.getenv('TG_API_HASH', '')
session_name = os.getenv('TG_SESSION_NAME', 'tg_session')
# chat_names = ['Test', 'groupid']
# keywords = ['123', 'keyword2']

try:
    client = TelegramClient(session_name, api_id, api_hash)
    client.start()
except AuthKeyError:
    client = SyncTelegramClient(session_name, api_id, api_hash)
    client.start()

@client.on(events.NewMessage())
async def handle_new_message(event):
    message_text = event.message.message
    chat = await event.get_chat()
    title = chat.title
    sender = await event.get_sender()
    # 可能为None
    if sender:
        if hasattr(sender, "first_name"):
            sender_name = sender.first_name
            print(f"message from {sender_name} in chat '{title}': {message_text}")
        else:
            print(f"{title}: {message_text}")
        print(f"{dir(sender)}")

# print(f"Listening for messages containing {keywords} in chats {chat_names}...")
# client.run_until_disconnected()