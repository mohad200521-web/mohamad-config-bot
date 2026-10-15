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
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
INTERVAL = 15 * 60

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DARK_FILE = DATA_DIR / "DarkTunnel.dark"
CAPTION_FILE = DATA_DIR / "caption.txt"
GROUP_FILE = DATA_DIR / "group_id.txt"

# تحميل أيدي المجموعة المحفوظ، إن وجد
GROUP_ID = (
    GROUP_FILE.read_text(encoding="utf-8").strip()
    if GROUP_FILE.exists()
    else os.environ.get("GROUP_ID", "").strip()
)


def is_admin(update: Update) -> bool:
    return bool(
        update.effective_user
        and ADMIN_ID != 0
        and update.effective_user.id == ADMIN_ID
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    await update.effective_message.reply_text(
        "أهلاً بك في بوت Dark Tunnel!\n\n"
        "1. أرسل ملف .dark\n"
        "2. أرسل رسالة الكونفيج كنص منفصل\n\n"
        "/id - معرفة أيدي المحادثة الحالية\n"
        "/setgroup ID - ضبط أيدي المجموعة من الخاص\n"
        "/group - عرض أيدي المجموعة المحفوظ\n"
        "/publish - النشر الآن\n"
        "/auto - النشر كل 15 دقيقة\n"
        "/stop - إيقاف النشر التلقائي"
    )


async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    await update.effective_message.reply_text(
        f"أيدي هذه المحادثة:\n{update.effective_chat.id}"
    )


async def setgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GROUP_ID

    if not is_admin(update):
        return

    if not context.args:
        await update.effective_message.reply_text(
            "أرسل الأمر مع أيدي المجموعة هكذا:\n"
            "/setgroup -1001234567890"
        )
        return

    new_id = context.args[0]

    try:
        chat = await context.bot.get_chat(int(new_id))

        if chat.type not in ("group", "supergroup"):
            await update.effective_message.reply_text(
                "هذا الأيدي ليس لمجموعة أو مجموعة فائقة."
            )
            return

        # التأكد من أن البوت يستطيع إرسال رسالة إلى المجموعة
        await context.bot.send_chat_action(
            chat_id=chat.id,
            action="typing",
        )

        GROUP_ID = str(chat.id)
        GROUP_FILE.write_text(GROUP_ID, encoding="utf-8")

        await update.effective_message.reply_text(
            f"تم حفظ المجموعة بنجاح.\n"
            f"GROUP_ID = {GROUP_ID}\n\n"
            "جرّب /publish للنشر."
        )

    except Exception as exc:
        await update.effective_message.reply_text(
            "تعذّر الوصول إلى المجموعة.\n"
            "تأكد أن الأيدي صحيح وأن البوت عضو في المجموعة "
            "ويملك صلاحية إرسال الرسائل.\n\n"
            f"التفاصيل: {exc}"
        )


async def show_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    await update.effective_message.reply_text(
        f"أيدي المجموعة المحفوظ:\n{GROUP_ID or 'لم يتم ضبط المجموعة بعد'}"
    )


async def receive_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
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
            "الحد الأقصى لحجم الملف 10 ميغابايت."
        )
        return

    tg_file = await document.get_file()
    content = await tg_file.download_as_bytearray()
    DARK_FILE.write_bytes(content)

    await update.effective_message.reply_text(
        "تم حفظ ملف Dark Tunnel.\n"
        "أرسل الآن رسالة الكونفيج كنص منفصل."
    )


async def receive_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
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

    if len(text) > 1024:
        await update.effective_message.reply_text(
            "اختصر رسالة الكونفيج إلى 1024 حرف أو أقل."
        )
        return

    CAPTION_FILE.write_text(text, encoding="utf-8")

    await update.effective_message.reply_text(
        "تم حفظ رسالة الكونفيج.\n"
        "استخدم /publish للنشر الآن أو /auto للتكرار."
    )


async def publish_to_group(context: ContextTypes.DEFAULT_TYPE):
    if not GROUP_ID:
        raise ValueError(
            "لم تضبط أيدي المجموعة. أرسل /setgroup أيدي_المجموعة في الخاص."
        )

    if not DARK_FILE.exists():
        raise ValueError("أرسل ملف .dark أولاً.")

    caption = (
        CAPTION_FILE.read_text(encoding="utf-8")
        if CAPTION_FILE.exists()
        else "إعدادات Dark Tunnel"
    )

    if len(caption) > 1024:
        raise ValueError("رسالة الكونفيج أطول من الحد المسموح.")

    with DARK_FILE.open("rb") as file:
        await context.bot.send_document(
            chat_id=int(GROUP_ID),
            document=file,
            filename="DarkTunnel.dark",
            caption=caption,
        )


async def publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    try:
        await publish_to_group(context)
        await update.effective_message.reply_text(
            "تم نشر الملف ورسالة الكونفيج معاً."
        )
    except Exception as exc:
        print(f"Publish error: {exc}")
        await update.effective_message.reply_text(
            f"فشل النشر: {exc}"
        )


async def auto(context: ContextTypes.DEFAULT_TYPE):
    try:
        await publish_to_group(context)
        print("Auto publication successful")
    except Exception as exc:
        print(f"Auto publication error: {exc}")


async def auto_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(update):
        return

    if not GROUP_ID:
        await update.effective_message.reply_text(
            "أرسل /setgroup أيدي_المجموعة أولاً."
        )
        return

    if not DARK_FILE.exists() or not CAPTION_FILE.exists():
        await update.effective_message.reply_text(
            "أرسل ملف .dark ورسالة الكونفيج أولاً."
        )
        return

    if context.job_queue is None:
        await update.effective_message.reply_text(
            "ميزة النشر التلقائي غير مفعّلة. "
            "ثبّت الحزمة: python-telegram-bot[job-queue]"
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
        first=INTERVAL,
        name="auto_publish",
    )

    await update.effective_message.reply_text(
        "تم تشغيل النشر التلقائي كل 15 دقيقة."
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    if context.job_queue is not None:
        for job in context.job_queue.get_jobs_by_name("auto_publish"):
            job.schedule_removal()

    await update.effective_message.reply_text(
        "تم إيقاف النشر التلقائي."
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_chat_id))
    app.add_handler(CommandHandler("setgroup", setgroup))
    app.add_handler(CommandHandler("group", show_group))
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