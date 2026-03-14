import asyncio
import requests
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# --- SOZLAMALAR ---
API_TOKEN = '8769316813:AAGG_qt2faKYjXq8LxuiQhkBz56fsc6We3s'
ADMIN_ID = 7740552653
GROUP_ID = -1001549017357 
# ------------------

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
last_msg_id = None

def get_real_budget_data():
    url = "https://openbudget.uz/api/v1/user/initiatives?page=0&size=100&districtCode=1714227&order=count,desc"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    }

    # 3 marta qayta urinish mexanizmi
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=30) # Timeoutni 30 soniyaga uzaytirdik
            if response.status_code == 200:
                data = response.json()
                initiatives = data.get('content', [])
                results = [{'title': i.get('title'), 'votes': i.get('count', 0)} for i in initiatives]
                return sorted(results, key=lambda x: x['votes'], reverse=True)[:10]
        except Exception as e:
            logging.warning(f"Urinish {attempt+1} muvaffaqiyatsiz: {e}")
            continue
    return None

async def build_table_text():
    data = get_real_budget_data()
    now = datetime.now().strftime("%H:%M")
    
    if not data:
        return f"⚠️ OpenBudget sayti hozirda band yoki ulanib bo'lmadi.\n🕒 Oxirgi urinish: {now}\n♻️ Qayta urinilmoqda..."

    text = "📊 **CHUST TUMANI - TOP 10 REYTING**\n"
    text += f"🕒 Yangilangan vaqt: {now}\n\n"
    text += "№ | Ovoz | Tashabbus nomi\n"
    text += "---|---|---\n"
    
    for i, item in enumerate(data, 1):
        name = item['title'].replace('\n', ' ').strip()[:35] + "..."
        text += f"{i} | **{item['votes']}** | {name}\n"
    
    text += "\n♻️ _Xabar har 5 daqiqada yangilanmoqda_"
    return text

async def refresh_group_message():
    global last_msg_id
    new_text = await build_table_text()
    
    try:
        if last_msg_id:
            await bot.edit_message_text(new_text, GROUP_ID, last_msg_id, parse_mode="Markdown")
        else:
            msg = await bot.send_message(GROUP_ID, new_text, parse_mode="Markdown")
            last_msg_id = msg.message_id
    except Exception as e:
        msg = await bot.send_message(GROUP_ID, new_text, parse_mode="Markdown")
        last_msg_id = msg.message_id

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        report = await build_table_text()
        await message.answer(f"✅ Bot ishga tushdi!\n\n{report}", parse_mode="Markdown")

async def main():
    scheduler.add_job(refresh_group_message, "interval", minutes=5)
    scheduler.start()
    await refresh_group_message()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
