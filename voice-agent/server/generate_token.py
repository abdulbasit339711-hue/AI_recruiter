import jwt
import time
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("LIVEKIT_API_KEY")
api_secret = os.getenv("LIVEKIT_API_SECRET")

# Generate token
token = jwt.encode(
    {
        "video": {"roomJoin": True, "room": "test-room"},
        "sub": "bot",
        "iss": api_key,
        "exp": time.time() + 3600,
    },
    api_secret,
    algorithm="HS256",
)

print(token)
