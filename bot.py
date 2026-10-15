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
GROUP_ID = os.environ.get("GROUP_ID", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
INTERVAL = max(60, int(os.environ.get("POST_INTERVAL", "3600")))

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DARK_FILE = DATA_DIR / "DarkTunnel.dark"
CAPTION_FILE = DATA_DIR / "caption.txt"


def is_admin(update: Update) -> bool:
    return bool(
        update.effective_user
        and update.effective_user.id == ADMIN_ID
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    await update.effective_message.reply_text(
        "أهلاً بك!\n\n"
        "1- أرسل ملف Dark Tunnel بامتداد .dark\n"
        "2- أرسل رسالة الكونفيج كنص منفصل.\n"
        "3- استخدم /publish لنشرهما معاً.\n\n"
        "/id - معرفة رقم المحادثة الحالية\n"
        "/publish - النشر الآن\n"
        "/auto - تشغيل النشر التلقائي\n"
        "/stop - إيقاف النشر التلقائي"
    )


async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    chat = update.effective_chat
    await update.effective_message.reply_text(
        f"رقم هذه المحادثة هو:\n{chat.id}\n\n"
        "إذا كانت هذه مجموعتك، انسخ الرقم وضعه في GROUP_ID."
    )


async def receive_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    document = update.effective_message.document
    filename = (document.file_name or "").lower()

    if not filename.endswith(".dark"):
        await update.effective_message.reply_text(
            "أرسل ملف Dark Tunnel بامتداد .dark"
        )
        return

    if document.file_size and document.file_size > 10_000_000:
        await update.effective_message.reply_text(
            "حجم الملف يجب ألا يتجاوز 10 ميغابايت."
        )
        return

    tg_file = await document.get_file()
    content = await tg_file.download_as_bytearray()
    DARK_FILE.write_bytes(content)

    await update.effective_message.reply_text(
        "تم حفظ ملف Dark Tunnel.\n"
        "الآن أرسل رسالة الكونفيج كنص منفصل."
    )


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    text = (update.effective_message.text or "").strip()

    if text.startswith("/"):
        return

    if not DARK_FILE.exists():
        await update.effective_message.reply_text(
            "أرسل ملف .dark أولاً."
        )
        return

    CAPTION_FILE.write_text(text, encoding="utf-8")

    await update.effective_message.reply_text(
        "تم حفظ رسالة الكونفيج.\nاستخدم /publish للنشر."
    )


async def publish_to_group(context: ContextTypes.DEFAULT_TYPE):
    if not GROUP_ID:
        raise ValueError(
            "GROUP_ID غير مضبوط. احصل على رقم المجموعة باستخدام /id."
        )

    if not DARK_FILE.exists():
        raise ValueError("لم يتم استلام ملف .dark.")

    caption = (
        CAPTION_FILE.read_text(encoding="utf-8")
        if CAPTION_FILE.exists()
        else "إعدادات Dark Tunnel"
    )

    if len(caption) > 1024:
        raise ValueError(
            "رسالة الكونفيج أطول من الحد المسموح مع الملف. قصّر النص."
        )

    with DARK_FILE.open("rb") as file:
        await context.bot.send_document(
            chat_id=GROUP_ID,
            document=file,
            filename="DarkTunnel.dark",
            caption=caption,
        )


async def publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    try:
        await publish_to_group(context)
        await update.effective_message.reply_text("تم نشر الملف والرسالة معاً.")
    except Exception as exc:
        await update.effective_message.reply_text(f"تعذّر النشر: {exc}")


async def auto(context: ContextTypes.DEFAULT_TYPE):
    try:
        await publish_to_group(context)
    except Exception as exc:
        print(f"فشل النشر التلقائي: {exc}")


async def auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    if not GROUP_ID:
        await update.effective_message.reply_text(
            "اضبط GROUP_ID برقم المجموعة أولاً."
        )
        return

    if not DARK_FILE.exists() or not CAPTION_FILE.exists():
        await update.effective_message.reply_text(
            "أرسل ملف .dark ورسالة الكونفيج أولاً."
        )
        return

    jobs = context.job_queue
    if jobs.get_jobs_by_name("auto_publish"):
        await update.effective_message.reply_text(
            "النشر التلقائي يعمل بالفعل."
        )
        return

    jobs.run_repeating(
        auto,
        interval=INTERVAL,
        first=5,
        name="auto_publish",
    )

    await update.effective_message.reply_text(
        f"تم تشغيل النشر التلقائي كل {INTERVAL} ثانية."
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    for job in context.job_queue.get_jobs_by_name("auto_publish"):
        job.schedule_removal()

    await update.effective_message.reply_text(
        "تم إيقاف النشر التلقائي."
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_chat_id))
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