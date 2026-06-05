import jwt
import time
import os
from dotenv import load_dotenv

# Explicitly load .env
load_dotenv(dotenv_path=".env", verbose=True)

api_key = os.getenv("LIVEKIT_API_KEY")
api_secret = os.getenv("LIVEKIT_API_SECRET")

print(f"DEBUG: API Key from env: '{api_key}'")
print(f"DEBUG: API Secret from env: '{api_secret}'")

if not api_key or not api_secret:
    print("Error: LIVEKIT_API_KEY or LIVEKIT_API_SECRET not found in .env file.")
    exit(1)

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

print("\n--- TOKEN ---")
print(token)
