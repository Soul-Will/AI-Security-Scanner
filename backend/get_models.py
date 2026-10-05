import os
import asyncio
import json
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

async def run():
    client = AsyncGroq(api_key=os.environ.get('GROQ_API_KEY'))
    models = await client.models.list()
    print(json.dumps([m.id for m in models.data]))

asyncio.run(run())
