import os
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
INTERVAL = 5 * 60
CHANNEL_LINK = "https://t.me/VLessVMessTroja"
MAX_FILES = 4

DATA_DIR = Path("data")
FILES_DIR = DATA_DIR / "dark_files"
FILES_DIR.mkdir(parents=True, exist_ok=True)

GROUP_FILE = DATA_DIR / "group_id.txt"

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


def saved_files():
    return sorted(
        FILES_DIR.glob("*.dark"),
        key=lambda path: path.name.lower(),
    )[:MAX_FILES]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    await update.effective_message.reply_text(
        "أهلاً بك في بوت Dark Tunnel!\n\n"
        "أرسل 4 ملفات .dark إلى البوت.\n\n"
        "/id - معرفة أيدي المحادثة\n"
        "/setgroup ID - ضبط المجموعة\n"
        "/group - عرض المجموعة\n"
        "/files - عدد الملفات المحفوظة\n"
        "/publish - النشر الآن\n"
        "/auto - النشر كل 5 دقائق\n"
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
            "استخدم الأمر هكذا:\n/setgroup -1001234567890"
        )
        return

    try:
        chat = await context.bot.get_chat(int(context.args[0]))

        if chat.type not in ("group", "supergroup"):
            await update.effective_message.reply_text(
                "هذا الأيدي ليس لمجموعة."
            )
            return

        await context.bot.send_chat_action(
            chat_id=chat.id,
            action="typing",
        )

        GROUP_ID = str(chat.id)
        GROUP_FILE.write_text(GROUP_ID, encoding="utf-8")

        await update.effective_message.reply_text(
            f"تم حفظ المجموعة:\n{GROUP_ID}"
        )

    except Exception as exc:
        await update.effective_message.reply_text(
            f"تعذّر الوصول إلى المجموعة:\n{exc}"
        )


async def show_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    await update.effective_message.reply_text(
        f"المجموعة المحفوظة:\n{GROUP_ID or 'لم يتم ضبطها'}"
    )


async def show_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    files = saved_files()
    names = "\n".join(path.name for path in files) or "لا توجد ملفات."

    await update.effective_message.reply_text(
        f"الملفات المحفوظة: {len(files)}/{MAX_FILES}\n{names}"
    )


async def receive_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(update):
        return

    document = update.effective_message.document
    filename = document.file_name or ""

    if not filename.lower().endswith(".dark"):
        await update.effective_message.reply_text(
            "أرسل ملفاً بامتداد .dark فقط."
        )
        return

    if document.file_size and document.file_size > 10_000_000:
        await update.effective_message.reply_text(
            "حجم الملف أكبر من 10 ميغابايت."
        )
        return

    # استبدال الملف إذا كان الاسم نفسه موجوداً
    safe_name = Path(filename).name
    destination = FILES_DIR / safe_name

    if not destination.exists() and len(list(FILES_DIR.glob("*.dark"))) >= MAX_FILES:
        await update.effective_message.reply_text(
            "تم حفظ 4 ملفات بالفعل. احذف ملفات data/dark_files القديمة "
            "من المشروع قبل إضافة ملفات جديدة."
        )
        return

    tg_file = await document.get_file()
    content = await tg_file.download_as_bytearray()
    destination.write_bytes(content)

    await update.effective_message.reply_text(
        f"تم حفظ الملف: {safe_name}\n"
        f"عدد الملفات: {len(saved_files())}/{MAX_FILES}"
    )


async def publish_to_group(context: ContextTypes.DEFAULT_TYPE):
    if not GROUP_ID:
        raise ValueError("اضبط المجموعة أولاً باستخدام /setgroup.")

    files = saved_files()

    if len(files) != MAX_FILES:
        raise ValueError(
            f"يجب حفظ 4 ملفات .dark أولاً. الموجود حالياً: {len(files)}."
        )

    for path in files:
        with path.open("rb") as file:
            await context.bot.send_document(
                chat_id=int(GROUP_ID),
                document=file,
                filename=path.name,
            )

    await context.bot.send_message(
        chat_id=int(GROUP_ID),
        text=CHANNEL_LINK,
    )


async def publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    try:
        await publish_to_group(context)
        await update.effective_message.reply_text(
            "تم نشر الملفات الأربعة ورابط القناة."
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
            "اضبط المجموعة أولاً باستخدام /setgroup."
        )
        return

    if len(saved_files()) != MAX_FILES:
        await update.effective_message.reply_text(
            "أرسل 4 ملفات .dark أولاً."
        )
        return

    if context.job_queue is None:
        await update.effective_message.reply_text(
            'ثبّت الحزمة: python-telegram-bot[job-queue]'
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
        "تم تشغيل النشر التلقائي كل 5 دقائق."
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
    app.add_handler(CommandHandler("files", show_files))
    app.add_handler(CommandHandler("publish", publish))
    app.add_handler(CommandHandler("auto", auto_command))
    app.add_handler(CommandHandler("stop", stop))

    app.add_handler(
        MessageHandler(filters.Document.ALL, receive_document)
    )

    app.run_polling()


if __name__ == "__main__":
    main()