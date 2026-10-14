import os
import asyncio
from pathlib import Path
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GROUP_ID = os.environ.get("GROUP_ID", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
INTERVAL = max(60, int(os.environ.get("POST_INTERVAL", "3600")))

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DARK_FILE = DATA_DIR / "DarkTunnel.dark"
CAPTION_FILE = DATA_DIR / "caption.txt"


def is_admin(update):
    return (
        update.effective_user
        and update.effective_user.id == ADMIN_ID
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    await update.message.reply_text(
        "أهلاً بك!\n\n"
        "1- أرسل ملف Dark Tunnel بامتداد .dark\n"
        "2- أرسل رسالة الكونفيج كنص منفصل.\n"
        "3- استخدم /publish لنشر الملف والرسالة معاً.\n\n"
        "/publish - نشر الآن\n"
        "/auto - تشغيل النشر التلقائي\n"
        "/stop - إيقاف النشر التلقائي"
    )


async def receive_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    document = update.message.document
    filename = (document.file_name or "").lower()

    if document.file_size and document.file_size > 10_000_000:
        await update.message.reply_text("حجم الملف يجب ألا يتجاوز 10 ميغابايت.")
        return

    if not filename.endswith(".dark"):
        await update.message.reply_text(
            "أرسل ملف Dark Tunnel بامتداد .dark"
        )
        return

    tg_file = await document.get_file()
    content = await tg_file.download_as_bytearray()

    DARK_FILE.write_bytes(content)
    context.application.bot_data["dark_file"] = str(DARK_FILE)

    await update.message.reply_text(
        "تم حفظ ملف Dark Tunnel.\n"
        "الآن أرسل رسالة الكونفيج كنص منفصل."
    )


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    text = (update.message.text or "").strip()

    if text.startswith("/"):
        return

    if not DARK_FILE.exists():
        await update.message.reply_text(
            "أرسل ملف .dark أولاً، ثم أرسل رسالة الكونفيج."
        )
        return

    CAPTION_FILE.write_text(text, encoding="utf-8")
    context.application.bot_data["caption"] = text

    await update.message.reply_text(
        "تم حفظ رسالة الكونفيج.\n"
        "استخدم /publish لنشر الملف والرسالة في منشور واحد."
    )


async def publish_to_group(context: ContextTypes.DEFAULT_TYPE):
    if not GROUP_ID:
        raise ValueError("GROUP_ID غير مضبوط")

    if not DARK_FILE.exists():
        raise ValueError("لم يتم استلام ملف .dark")

    caption = (
        CAPTION_FILE.read_text(encoding="utf-8")
        if CAPTION_FILE.exists()
        else ""
    )

    if len(caption) > 1024:
        raise ValueError(
            "الرسالة أطول من الحد المسموح مع الملف. قصّر النص."
        )

    with DARK_FILE.open("rb") as file:
        await context.bot.send_document(
            chat_id=GROUP_ID,
            document=file,
            filename="DarkTunnel.dark",
            caption=caption or "إعدادات Dark Tunnel",
        )


async def publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    try:
        await publish_to_group(context)
        await update.message.reply_text(
            "تم نشر ملف Dark Tunnel ورسالة الكونفيج معاً."
        )
    except Exception as exc:
        await update.message.reply_text(f"تعذّر النشر: {exc}")


async def auto(context: ContextTypes.DEFAULT_TYPE):
    await publish_to_group(context)


async def auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    if not GROUP_ID:
        await update.message.reply_text("أضف GROUP_ID إلى متغيرات البيئة أولاً.")
        return

    if not DARK_FILE.exists() or not CAPTION_FILE.exists():
        await update.message.reply_text(
            "أرسل ملف .dark ورسالة الكونفيج أولاً."
        )
        return

    jobs = context.job_queue
    if jobs.get_jobs_by_name("auto_publish"):
        await update.message.reply_text("النشر التلقائي يعمل بالفعل.")
        return

    jobs.run_repeating(
        auto,
        interval=INTERVAL,
        first=5,
        name="auto_publish",
    )

    await update.message.reply_text(
        f"تم تشغيل النشر التلقائي كل {INTERVAL} ثانية."
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    for job in context.job_queue.get_jobs_by_name("auto_publish"):
        job.schedule_removal()

    await update.message.reply_text("تم إيقاف النشر التلقائي.")


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("publish", publish))
    app.add_handler(CommandHandler("auto", auto_command))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(
        MessageHandler(filters.Document.ALL, receive_document)
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)
    )

    app.run_polling()


if __name__ == "__main__":
    main()