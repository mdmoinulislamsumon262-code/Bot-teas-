import os
import threading
from flask import Flask

# ... আপনার আগের বাকি সব কোড ...

# ── Render Keep-Alive Web Server ──────────────────────────────
app = Flask(__name__)


@app.route("/")
def home():
    return "🤖 Bot is running 24/7 successfully!"


def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


# ── বটের মেইন রানার ──────────────────────────────────────────
if __name__ == "__main__":
    # ব্যাকগ্রাউন্ডে Flask সার্ভার চালু হবে (Render Port Binding এর জন্য)
    threading.Thread(target=run_web, daemon=True).start()

    print("🚀 Shop Bot is starting on Render...")
    bot.infinity_polling(skip_pending=True)