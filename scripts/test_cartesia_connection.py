import os
import asyncio
import logging
from dotenv import load_dotenv
from pipecat.services.cartesia.tts import CartesiaHttpTTSService
from loguru import logger

# Enable verbose logging for websockets
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('websockets').setLevel(logging.DEBUG)

load_dotenv("voice-agent/server/.env")

async def test_cartesia():
    api_key = os.getenv("CARTESIA_API_KEY")
    voice_id = os.getenv("CARTESIA_VOICE_ID", "71a7ad14-091c-4e8e-a314-022ece01c121")
    
    logger.info(f"Testing Cartesia HTTP with Key: {api_key[:5]}... and Voice: {voice_id}")

    try:
        tts = CartesiaHttpTTSService(
            api_key=api_key,
            voice_id=voice_id,
        )
        # Attempt to connect (if it has a connect method)
        # Assuming Http service might not need an explicit connect, or might have different methods
        logger.info("Created CartesiaHttpTTSService.")
    except Exception as e:
        logger.error(f"Failed to create CartesiaHttpTTSService: {e}")

if __name__ == "__main__":
    asyncio.run(test_cartesia())
