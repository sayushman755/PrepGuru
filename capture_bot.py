"""
Run this with: python capture_bot.py
"""
import os
import re
import random
import datetime
import threading
import time
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

from config import TELEGRAM_BOT_TOKEN
from llm_extract import extract_fields
from embed import embed_text
from db import (
    insert_entry,
    fetch_all,
    check_and_merge_entry,
    add_to_failed_queue,
    hybrid_search,
    register_chat_id,
    fetch_all_chat_ids,
    fetch_latest_market_trends,
    log_daily_activity
)
from pdf_generator import regenerate_pdf
from logger_setup import setup_logger

log = setup_logger("capture_bot")
URL_RE = re.compile(r"https?://\S+")


def is_authorized(user_id: int) -> bool:
    """
    Checks if a Telegram User ID is allowed to interact with the bot.
    If ALLOWED_TELEGRAM_USER_IDS is empty, allows all for initial setup convenience.
    """
    allowed_raw = os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").strip()
    if not allowed_raw:
        return True
    allowed_ids = [uid.strip() for uid in allowed_raw.split(",") if uid.strip()]
    return str(user_id) in allowed_ids


async def notify_admin_alert(bot, message: str):
    """
    Sends proactive process alerts to the first configured administrator.
    """
    allowed_raw = os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").strip()
    if allowed_raw:
        first_admin = [uid.strip() for uid in allowed_raw.split(",") if uid.strip()][0]
        try:
            await bot.send_message(chat_id=first_admin, text=message, parse_mode="HTML")
        except Exception as send_err:
            log.error(f"Failed to send admin process alert: {send_err}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        log.warning(f"Unauthorized access attempt block in start_command from user_id: {update.effective_user.id}")
        await update.message.reply_text("❌ Unauthorized access. You do not have permissions to write to this database.")
        return

    # Register chat_id for digest push notifications
    try:
        register_chat_id(str(update.effective_chat.id))
    except Exception:
        pass

    await update.message.reply_html(
        "👋 <b>Welcome to your Interview Q&A Capture Bot!</b>\n\n"
        "💡 <b>How to use:</b>\n"
        "1. <b>Capture Q&A</b>: Forward any LinkedIn post or paste raw Q&A text here. I will automatically structure it using AI.\n"
        "2. 📸 <b>Image Capture</b>: Upload a screenshot of a Q&A and I will extract the text using OCR and parse it!\n"
        "3. 🔍 /search &lt;query&gt;: Search your QA repository using hybrid semantic/keyword search.\n"
        "4. ⚡ /random: Get a random question to test your knowledge.\n"
        "5. 📖 /help: Display this helper menu."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return

    await update.message.reply_html(
        "📖 <b>Bot Commands:</b>\n\n"
        "⚡ /start - Welcome message and quick start\n"
        "⚡ /help - Show this guide\n"
        "⚡ /random - Practice with a random question from your repository\n"
        "⚡ <code>/search &lt;query&gt;</code> - Perform hybrid search directly in chat\n\n"
        "Simply send any other raw text, post, or screenshot image to save it to your database!"
    )


async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return

    try:
        entries = fetch_all()
        if not entries:
            await update.message.reply_text("Your repository is empty. Save some entries first by messaging me!")
            return
        
        entry = random.choice(entries)
        response = (
            f"⚡ <b>PRACTICE QUESTION</b>\n"
            f"<b>Topic:</b> {entry.get('topic', 'General')} | <b>Level:</b> {entry.get('level', 'basic').capitalize()}\n"
            f"<b>Source:</b> {entry.get('source_type', 'captured').upper()}\n\n"
            f"❓ <b>Question:</b>\n{entry.get('question')}\n\n"
            f"🔑 <b>Answer Summary (tap to reveal):</b>\n<tg-spoiler>{entry.get('answer_summary')}</tg-spoiler>"
        )
        if entry.get("example"):
            response += f"\n\n💻 <b>Example:</b>\n<tg-spoiler><code>{entry.get('example')}</code></tg-spoiler>"
            
        await update.message.reply_html(response)
    except Exception as e:
        log.exception("Failed to get random entry")
        await update.message.reply_text(f"Failed to fetch random entry: {e}")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return

    if not context.args:
        await update.message.reply_markdown("Please provide a search term. Example: `/search caching`")
        return
    
    query = " ".join(context.args)
    status_msg = await update.message.reply_text("🔍 Searching...")
    
    try:
        query_embedding = embed_text(query)
        matches = hybrid_search(query, query_embedding, match_count=3)
        
        if not matches:
            await status_msg.edit_text("No matching entries found.")
            return
        
        response = f"🎯 <b>Top Hybrid Search Matches for:</b> <i>{query}</i>\n\n"
        for idx, m in enumerate(matches, 1):
            prov = "AI-Gen" if m.get("source_type") == "ai_generated" else "Captured"
            response += (
                f"{idx}. ❓ <b>{m.get('question')}</b> ({prov})\n"
                f"🏷️ Topic: {m.get('topic', 'General')} | Level: {m.get('level', 'basic').capitalize()}\n"
                f"💡 <b>Answer:</b> <tg-spoiler>{m.get('answer_summary')}</tg-spoiler>\n\n"
            )
        await status_msg.delete()
        await update.message.reply_html(response)
    except Exception as e:
        log.exception("Failed to search")
        await status_msg.edit_text(f"Search failed: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        log.warning(f"Unauthorized message capture block from user_id: {update.effective_user.id}")
        await update.message.reply_text("❌ Unauthorized access.")
        return

    raw_text = update.message.text
    if not raw_text or not raw_text.strip():
        return

    status_msg = await update.message.reply_text("Got it - processing raw text...")

    try:
        fields = extract_fields(raw_text)
        embedding = embed_text(f"{fields.get('question', '')} {fields.get('answer_summary', '')}")
        url_match = URL_RE.search(raw_text)
        source_url = url_match.group(0) if url_match else None

        # Deduplication Check
        merged = check_and_merge_entry(fields, raw_text, source_url, embedding)
        if merged:
            await status_msg.edit_text("🔄 Duplicate detected! References auto-merged into existing card.")
        else:
            insert_entry(
                fields,
                raw_text,
                source_url,
                embedding,
                source_type="captured",
                ai_supplemented=fields.get("ai_supplemented", False)
            )
            log_daily_activity()
            await status_msg.edit_text(
                "Saved ✅\n"
                f"Level: {fields.get('level')}\n"
                f"Topic: {fields.get('topic')}\n"
                f"Q: {fields.get('question')}"
            )
        regenerate_pdf()
    except Exception as e:
        log.exception("Failed to process message")
        add_to_failed_queue(raw_text, str(e))
        await status_msg.edit_text(f"Something went wrong: {e}. Raw content saved to failed queue for manual review.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized access.")
        return

    status_msg = await update.message.reply_text("📸 Screenshot received. Downloading and running OCR text extraction...")
    
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        await status_msg.edit_text("❌ OCR packages (pytesseract or Pillow) are not installed on the server hosting this bot.")
        return

    try:
        # Download photo
        photo_file = await update.message.photo[-1].get_file()
        os.makedirs("temp", exist_ok=True)
        temp_photo_path = os.path.join("temp", f"{photo_file.file_unique_id}.jpg")
        await photo_file.download_to_drive(temp_photo_path)
        
        # OCR Extraction
        extracted_text = pytesseract.image_to_string(Image.open(temp_photo_path))
        
        try:
            os.remove(temp_photo_path)
        except Exception:
            pass
            
        caption_text = (update.message.caption or "").strip()
        combined_text = extracted_text
        if caption_text:
            combined_text = f"Context: {caption_text}\n\nContent:\n{extracted_text}"

        if not extracted_text or not extracted_text.strip():
            await status_msg.edit_text("❌ Could not extract any readable text from this screenshot. Make sure the text is clear.")
            return
            
        await status_msg.edit_text(f"📝 OCR Extracted Text Preview:\n\n`{extracted_text[:150]}...`\n\nParsing Q&A structure...")
        
        # Process extracted text
        fields = extract_fields(combined_text)
        embedding = embed_text(f"{fields.get('question', '')} {fields.get('answer_summary', '')}")
        
        # Deduplication Check
        merged = check_and_merge_entry(fields, combined_text, None, embedding)
        if merged:
            await update.message.reply_text("🔄 Duplicate detected! References auto-merged into existing card.")
        else:
            insert_entry(
                fields,
                combined_text,
                None,
                embedding,
                source_type="captured",
                ai_supplemented=fields.get("ai_supplemented", False)
            )
            log_daily_activity()
            await update.message.reply_text(
                "Saved ✅\n"
                f"Level: {fields.get('level')}\n"
                f"Topic: {fields.get('topic')}\n"
                f"Q: {fields.get('question')}"
            )
        regenerate_pdf()
    except Exception as ocr_err:
        log.exception("Failed OCR processing")
        try:
            if 'extracted_text' in locals() and extracted_text.strip():
                add_to_failed_queue(extracted_text, f"OCR structure error: {ocr_err}")
                await status_msg.edit_text(f"❌ Photo structure parsing failed: {ocr_err}. Text saved to failed queue for review.")
                return
        except Exception:
            pass
        await status_msg.edit_text(f"❌ Photo processing failed: {ocr_err}")


# Background Loop function for Weekly push notification summaries
async def weekly_digest_loop(bot):
    while True:
        try:
            now = datetime.datetime.now()
            # Send digest every Sunday at 10:00 AM
            if now.weekday() == 6 and now.hour == 10:
                chat_ids = fetch_all_chat_ids()
                if chat_ids:
                    entries = fetch_all()
                    trends = fetch_latest_market_trends()
                    
                    digest_text = (
                         "⏰ <b>Prep Companion Weekly Digest</b>\n\n"
                         f"📚 <b>Total Questions in Database:</b> {len(entries)}\n"
                    )
                    if trends:
                        digest_text += (
                             f"\n🔍 <b>Latest Tech Market Trends:</b>\n"
                             f"Trending skills: {', '.join(trends.get('trending_skills', []))}\n\n"
                             f"{trends.get('summary')[:350]}...\n"
                        )
                    digest_text += "\n💡 <i>Keep studying! Don't let your streak slip.</i>"
                    
                    for cid in chat_ids:
                        try:
                            await bot.send_message(chat_id=cid, text=digest_text, parse_mode="HTML")
                        except Exception as send_err:
                            log.error(f"Failed to send weekly digest to {cid}: {send_err}")
                            
                # Sleep for 23 hours to prevent double firing on the same Sunday hour
                await asyncio.sleep(23 * 3600)
        except Exception as loop_err:
            log.error(f"Weekly digest loop error: {loop_err}")
            
        await asyncio.sleep(3600)  # Check every hour


def run_weekly_digest_scheduler(bot):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(weekly_digest_loop(bot))


def main():
    if not TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN is missing. Please set it in your .env file.")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("random", random_command))
    app.add_handler(CommandHandler("search", search_command))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Start background scheduler thread for digests
    threading.Thread(target=run_weekly_digest_scheduler, args=(app.bot,), daemon=True).start()
    
    # Webhook Toggle
    USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
    PORT = int(os.getenv("PORT", "8443"))

    # Send startup alert to admin
    asyncio.run(notify_admin_alert(app.bot, "🟢 <b>Prep Companion Bot is ONLINE</b>"))

    try:
        if USE_WEBHOOK and WEBHOOK_URL:
            log.info("Starting bot in WEBHOOK mode...")
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path="webhook",
                webhook_url=f"{WEBHOOK_URL}/webhook"
            )
        else:
            log.info("Starting bot in POLLING mode...")
            app.run_polling()
    except Exception as crash_err:
        log.critical(f"Bot process crashed: {crash_err}")
        # Send crash alert to admin
        try:
            asyncio.run(notify_admin_alert(app.bot, f"🔴 <b>Prep Companion Bot CRASHED!</b>\n\nError: <code>{crash_err}</code>"))
        except Exception:
            pass
        raise crash_err


if __name__ == "__main__":
    main()
