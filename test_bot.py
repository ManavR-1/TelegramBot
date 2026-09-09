from config import BOT_TOKEN
import urllib.request

url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"

print("Testing:", url[:40] + "...")

response = urllib.request.urlopen(url)

print(response.read().decode())
