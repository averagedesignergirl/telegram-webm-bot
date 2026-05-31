import os
import subprocess
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
import asyncio
from threading import Thread
from flask import Flask

# ========================= CONFIG =========================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set!")

DOWNLOAD_DIR = "downloads"
OUTPUT_DIR = "outputs"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ======================= HANDLER =======================
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    video = message.video or (message.document if message.document and 
                            message.document.mime_type and 
                            message.document.mime_type.startswith("video/") else None)
    
    if not video:
        return

    try:
        await message.reply_text("🔄 Downloading video...")

        file = await context.bot.get_file(video.file_id)
        input_path = os.path.join(DOWNLOAD_DIR, f"{video.file_id}.mp4")
        output_path = os.path.join(OUTPUT_DIR, f"{video.file_id}.webm")

        await file.download_to_drive(input_path)

        await message.reply_text("⚙️ Converting to WebM sticker...")

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-t", "3",                    # First 3 seconds
            "-vf", "crop=min(iw\\,ih):min(iw\\,ih),scale=512:512,fps=30",
            "-an",                        # No audio
            "-c:v", "libvpx-vp9",
            "-b:v", "150K",
            "-maxrate", "150K",
            "-bufsize", "300K",
            "-crf", "35",
            "-deadline", "realtime",
            "-cpu-used", "6",
            output_path
        ]

        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if os.path.exists(output_path) and os.path.getsize(output_path) < 256 * 1024:
            await message.reply_document(
                document=open(output_path, "rb"),
                filename="sticker.webm",
                caption="✅ Here is your WebM sticker!"
            )
        else:
            await message.reply_text("❌ Conversion failed or file is too big (>256KB).")

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")
    
    finally:
        # Cleanup files
        for path in (input_path, output_path):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass


# ======================= MAIN =======================
def run_bot():
    """Run the Telegram bot"""
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    
    print("🤖 Bot is running...")
    app.run_polling(drop_pending_updates=True)


def main():
    # Start bot in background thread
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Flask server to satisfy Render Web Service requirement
    port = int(os.environ.get("PORT", 10000))
    flask_app = Flask(__name__)

    @flask_app.route('/')
    def home():
        return "✅ Telegram WebM Bot is running!"

    @flask_app.route('/health')
    def health():
        return "OK", 200

    print(f"🌐 Starting Flask server on port {port}")
    flask_app.run(host='0.0.0.0', port=port)


if __name__ == "__main__":
    main()
