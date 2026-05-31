import os
import subprocess
from threading import Thread
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from flask import Flask

# ========================= CONFIG =========================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set!")

DOWNLOAD_DIR = "downloads"
OUTPUT_DIR = "outputs"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ======================= TELEGRAM BOT =======================
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    video = message.video or (message.document if message.document and 
                            message.document.mime_type and 
                            message.document.mime_type.startswith("video/") else None)
    
    if not video:
        return

    try:
        await message.reply_text("🔄 Downloading...")
        file = await context.bot.get_file(video.file_id)
        
        input_path = os.path.join(DOWNLOAD_DIR, f"{video.file_id}.mp4")
        output_path = os.path.join(OUTPUT_DIR, f"{video.file_id}.webm")

        await file.download_to_drive(input_path)
        await message.reply_text("⚙️ Converting to WebM...")

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_path, "-t", "3",
            "-vf", "crop=min(iw\\,ih):min(iw\\,ih),scale=512:512,fps=30",
            "-an", "-c:v", "libvpx-vp9", "-b:v", "150K", "-maxrate", "150K",
            "-bufsize", "300K", "-crf", "35", "-deadline", "realtime", "-cpu-used", "6",
            output_path
        ]

        subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if os.path.exists(output_path) and os.path.getsize(output_path) < 256 * 1024:
            await message.reply_document(
                document=open(output_path, "rb"),
                filename="sticker.webm",
                caption="✅ Here is your WebM sticker!"
            )
        else:
            await message.reply_text("❌ Failed or file too big (>256KB)")

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")
    finally:
        for p in (input_path, output_path):
            if os.path.exists(p):
                try: os.remove(p)
                except: pass


def run_telegram_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    print("🤖 Telegram bot polling started...")
    app.run_polling(drop_pending_updates=True)


# ======================= FLASK APP =======================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ Telegram WebM Bot is running!"

@flask_app.route('/health')
def health():
    return "OK", 200


# ======================= MAIN =======================
if __name__ == "__main__":
    # Start Telegram bot in background thread
    Thread(target=run_telegram_bot, daemon=True).start()

    # Start Flask with gunicorn (better for Render)
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Starting server on port {port}")
    
    # Use gunicorn for better compatibility
    os.system(f"gunicorn --bind 0.0.0.0:{port} --workers 1 bot:flask_app")
