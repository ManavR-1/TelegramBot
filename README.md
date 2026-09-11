# Premium Telegram Subscription Bot

A feature-rich Telegram bot for managing paid/VIP channel subscriptions with UPI payments, automated access provisioning, payment verification, and automated expiration handling.

---

## Features

- **Automated Subscription Lifecycle**:
  - Automatically generates one-time, expiring Telegram channel invite links upon approval.
  - Automatically reminds users before subscription expiry (3-day and 1-day reminders).
  - Automatically removes expired users from the VIP/premium channel.
- **Payment Handling via UPI**:
  - Displays UPI ID and custom payment QR code.
  - Users submit their 12-digit UTR / transaction ID for verification.
  - Prevents duplicate UTR submissions.
- **Admin Verification Panel**:
  - Interactive inline approval/rejection panel sent directly to the Telegram admin.
  - Real-time notifications for payment submissions and user updates.
  - Direct customer notifications on payment approval or rejection.
- **Marketing & Campaign Tracking**:
  - Generate trackable start links with campaign tags (/start campaign_code).
  - Track link clicks, active conversions, and user engagement metrics.
  - Broadcast promotional messages to free/public channels.
- **Database Architecture**:
  - SQLite database managed via SQLAlchemy with automatic migrations.
  - Tracks user subscriptions, payments, and marketing visits.

---

## Project Structure

`	ext
├── app.py                      # Main entry point and bot lifecycle runner
├── config.py                   # Environment variable loader
├── database.py                 # SQLAlchemy engine and database initialization
├── database/                   # SQLite database storage (payments.db)
├── handlers/
│   ├── admin.py                # Admin approval and control callbacks
│   ├── marketing.py            # Marketing campaigns and tracking handlers
│   └── payment.py              # User payment and UTR submission handlers
├── images/                     # Static assets (place your qr.png here)
├── keyboards/
│   └── menu.py                 # Inline button menus and navigation
├── models/
│   ├── marketing.py            # Marketing visit tracking models
│   ├── payment.py              # Payment and UTR models
│   └── subscription.py         # User subscription models
├── services/
│   └── subscription_service.py # Expiration checker and invite link manager
├── .env.example                # Example environment configuration template
├── requirements.txt            # Python dependencies
└── README.md                   # Documentation
`

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- A Telegram bot created via [@BotFather](https://t.me/BotFather)
- A Telegram Channel where your bot has **Administrator** privileges (specifically: *Invite Users via Link* and *Ban Users*)
- A UPI ID and payment QR code image

### Installation

1. **Clone the repository**:
   `ash
   git clone <repository-url>
   cd PremiumTelegramBot
   `

2. **Create and activate a virtual environment**:
   `ash
   # On Windows:
   python -m venv .venv
   .venv\Scripts\activate

   # On Linux/macOS:
   python3 -m venv .venv
   source .venv/bin/activate
   `

3. **Install dependencies**:
   `ash
   pip install -r requirements.txt
   `

4. **Configure Environment Variables**:
   Copy .env.example to .env:
   `ash
   cp .env.example .env
   `
   Fill in your actual credentials in .env:
   `env
   BOT_TOKEN=your_telegram_bot_token
   ADMIN_ID=your_telegram_user_id
   CHANNEL_ID=-100xxxxxxxxxx
   FREE_CHANNEL_ID=-100xxxxxxxxxx
   UPI_ID=yourname@upi
   PLAN_PRICE=299
   PLAN_DURATION_DAYS=30
   `

5. **Add your Payment QR Code**:
   Place your UPI QR code image as qr.png inside the images/ directory:
   `	ext
   images/qr.png
   `

---

## Running the Bot Permanently

### Option A: Local Windows Background Auto-Start (Runs on PC)
You can have the bot run continuously on your computer in the background with auto-restart on network drops:

1. **Auto-start on Windows boot**:
   - Double-click `install_autostart.bat` to register the bot in your Windows Startup folder. It will launch automatically and silently whenever you log in.
2. **Manual Silent Start**:
   - Double-click `start_bot_silent.vbs` to run the bot in the background with no open terminal window.
3. **View Live Logs**:
   - Check `logs/bot.log` to inspect real-time bot operations and activity.
4. **Stop the Bot**:
   - Double-click `stop_bot.bat` to stop all running bot background processes.

---

### Option B: Cloud Hosting (Runs 24/7 Online even when PC is off)

Since the repository is on GitHub, you can deploy it to free cloud platforms:

#### 1. Deploy to Render.com (Recommended)
1. Sign up at [render.com](https://render.com) and connect your GitHub account.
2. Click **New +** -> **Background Worker**.
3. Select your repository: `ManavR-1/TelegramBot`.
4. Render will automatically detect the settings from `render.yaml`:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
5. In **Environment Variables**, add the values from your `.env` (`BOT_TOKEN`, `ADMIN_ID`, `CHANNEL_ID`, `FREE_CHANNEL_ID`, `UPI_ID`, `PLAN_PRICE`, `PLAN_DURATION_DAYS`).
6. Click **Create Background Worker**. Your bot is now permanently online 24/7!

#### 2. Deploy via Docker
Build and run using the included `Dockerfile`:
```bash
docker build -t telegram-premium-bot .
docker run -d --env-file .env --name telegram-bot telegram-premium-bot
```

---

## Security Notes

- Never commit your `.env` file or live database to version control.
- Your `.env` and `images/qr.png` are excluded by default in `.gitignore`.
