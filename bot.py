
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
DATA_FILE = Path("configs.txt")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "أرسل ملف الكونفيجات إلى مشرف البوت فقط."
        )
        return

    await update.message.reply_text(
        "أهلاً بك!\n"
        "أرسل ملف TXT يحتوي على الكونفيجات، كل كونفيج في سطر.\n"
        "/publish للنشر الآن\n"
        "/auto لتشغيل النشر التلقائي\n"
        "/stop لإيقاف النشر التلقائي"
    )


async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        return

    document = update.message.document
    if not document or not document.file_name.lower().endswith(".txt"):
        await update.message.reply_text("أرسل ملفًا بامتداد .txt")
        return

    if document.file_size and document.file_size > 1_000_000:
        await update.message.reply_text("حجم الملف يجب ألا يتجاوز 1 ميغابايت.")
        return

    tg_file = await document.get_file()
    content = await tg_file.download_as_bytearray()

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        await update.message.reply_text("تعذّر قراءة الملف. استخدم ترميز UTF-8.")
        return

    configs = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith(("vless://", "vmess://", "trojan://"))
    ]

    if not configs:
        await update.message.reply_text(
            "لم أجد روابط VLESS أو VMess أو Trojan في الملف."
        )
        return

    DATA_FILE.write_text("\n".join(configs) + "\n", encoding="utf-8")
    context.application.bot_data["configs"] = configs
    await update.message.reply_text(
        f"تم استلام {len(configs)} كونفيج.\n"
        "استخدم /publish للنشر أو /auto للنشر التلقائي."
    )


async def publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        return

    configs = context.application.bot_data.get("configs", [])
    if not configs and DATA_FILE.exists():
        configs = DATA_FILE.read_text(encoding="utf-8").splitlines()

    if not GROUP_ID or not configs:
        await update.message.reply_text(
            "تحقق من GROUP_ID وأرسل ملف الكونفيجات أولاً."
        )
        return

    sent = 0
    for config in configs:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=config,
            disable_web_page_preview=True,
        )
        sent += 1
        await asyncio.sleep(1)

    await update.message.reply_text(f"تم نشر {sent} كونفيج.")


async def auto(context: ContextTypes.DEFAULT_TYPE):
    configs = context.application.bot_data.get("configs", [])
    if not configs and DATA_FILE.exists():
        configs = DATA_FILE.read_text(encoding="utf-8").splitlines()

    if not GROUP_ID or not configs:
        return

    for config in configs:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=config,
            disable_web_page_preview=True,
        )
        await asyncio.sleep(1)


async def auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        return

    if not GROUP_ID:
        await update.message.reply_text("يجب إعداد GROUP_ID أولاً.")
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
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
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
        MessageHandler(filters.Document.ALL, receive_file)
    )

    app.run_polling()


if __name__ == "__main__":
    main()
