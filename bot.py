import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# Sozlamalar
API_TOKEN = '8769316813:AAGG_qt2faKYjXq8LxuiQhkBz56fsc6We3s'
ADMIN_ID = 7740552653
GROUP_ID = -100123456789  # @sherbilakmfy guruhi ID'sini kiriting
TARGET_INITIATIVE_ID = "53"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

last_msg_id = None

async def format_report():
    # Bu yerda scraper ishga tushadi
    # Hozircha namunaviy jadval
    text = "📊 **Top 10 Tashabbuslar:**\n\n"
    text += "| № | Tashabbus nomi | Ovoz |\n"
    text += "|---|----------------|------|\n"
    
    # Namuna uchun ma'lumot
    for i in range(1, 11):
        text += f"| {i} | Tashabbus {i} | {2000 - i*100} |\n"
    
    text += f"\n♻️ Oxirgi yangilanish: {datetime.now().strftime('%H:%M:%S')}"
    text += "\n⚠️ _Xar besh daqiqada yangilanmoqda_"
    return text

async def update_group_message():
    global last_msg_id
    text = await format_report()
    
    if last_msg_id:
        try:
            await bot.edit_message_text(text, GROUP_ID, last_msg_id, parse_mode="Markdown")
        except Exception:
            msg = await bot.send_message(GROUP_ID, text, parse_mode="Markdown")
            last_msg_id = msg.message_id
    else:
        msg = await bot.send_message(GROUP_ID, text, parse_mode="Markdown")
        last_msg_id = msg.message_id

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        report = await format_report()
        await message.answer(f"Xush kelibsiz, Admin!\nReal vaqt rejimi:\n\n{report}", parse_mode="Markdown")
    else:
        await message.answer("Siz admin emassiz.")

async def main():
    scheduler.add_job(update_group_message, "interval", minutes=5)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
