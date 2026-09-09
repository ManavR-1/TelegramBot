import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# Free/public channel used for promotions.
FREE_CHANNEL_ID = int(os.getenv("FREE_CHANNEL_ID", "0"))

UPI_ID = os.getenv("UPI_ID")
PLAN_PRICE = int(os.getenv("PLAN_PRICE"))
PLAN_DURATION_DAYS = int(os.getenv("PLAN_DURATION_DAYS"))
