import asyncio
import os
from livekit import api
from dotenv import load_dotenv

load_dotenv()

async def test():
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    print(f"Testing connection to {url}...")
    
    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity("test-bot")
        .with_grants(api.VideoGrants(room_join=True, room="test-room"))
        .to_jwt()
    )
    
    print("Token generated. Attempting to list rooms...")
    
    lkapi = api.LiveKitAPI(url, api_key, api_secret)
    try:
        rooms = await lkapi.room.list_rooms(api.ListRoomsRequest())
        print(f"Success! Found {len(rooms.rooms)} rooms.")
    except Exception as e:
        print(f"Failed: {e}")
    finally:
        await lkapi.close()

if __name__ == "__main__":
    asyncio.run(test())
