import asyncio
import httpx

from config import BOT_TOKEN


async def test():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"

    async with httpx.AsyncClient(
        timeout=30,
        http2=False,
        trust_env=False,
    ) as client:

        response = await client.get(url)

        print("Status:", response.status_code)
        print(response.text)


asyncio.run(test())