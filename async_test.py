import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get("https://api.telegram.org")
        print(response.status_code)

asyncio.run(main())