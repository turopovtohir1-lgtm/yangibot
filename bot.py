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
GROUP_ID = -1001549017357  # <--- O'zingizning guruh ID-ingizni kiriting!
# ------------------

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
last_msg_id = None

def get_openbudget_data():
    """Saytdan ma'lumotlarni olish va saralash"""
    # Chust tumani va ushbu mavsum uchun API manzili (havolangizdan kelib chiqib)
    url = "https://openbudget.uz/api/v1/user/initiatives?page=0&size=60&districtCode=1714227"
    
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        
        items = []
        for init in data.get('content', []):
            items.append({
                'name': init.get('title'),
                'votes': init.get('count', 0)
            })
        
        # Ovozlar soni bo'yicha kattadan kichikka saralash
        sorted_items = sorted(items, key=lambda x: x['votes'], reverse=True)
        return sorted_items[:10] # Faqat Top 10 talik
    except Exception as e:
        print(f"Xatolik yuz berdi: {e}")
        return None

async def create_table_text():
    data = get_openbudget_data()
    if not data:
        return "⚠️ Ma'lumot olishda xatolik yuz berdi (Sayt ishlamayotgan bo'lishi mumkin)."

    now = datetime.now().strftime("%H:%M")
    text = f"📊 **TOP-10 REYTING (Real vaqtda)**\n"
    text += f"🕒 Yangilangan vaqt: {now}\n\n"
    
    text += "№ | Ovoz | Tashabbus nomi\n"
    text += "---|---|---\n"
    
    for index, item in enumerate(data, start=1):
        # Nomni juda uzun bo'lsa qisqartiramiz
        name = item['name'][:35] + "..." if len(item['name']) > 35 else item['name']
        text += f"**{index}.** | `{item['votes']}` | {name}\n"
    
    text += "\n🔄 _Xabar har 5 daqiqada avtomatik yangilanadi._"
    return text

async def refresh_message():
    global last_msg_id
    new_text = await create_table_text()
    
    try:
        if last_msg_id:
            await bot.edit_message_text(
                text=new_text,
                chat_id=GROUP_ID,
                message_id=last_msg_id,
                parse_mode="Markdown"
            )
        else:
            msg = await bot.send_message(GROUP_ID, new_text, parse_mode="Markdown")
            last_msg_id = msg.message_id
    except Exception as e:
        # Agar xabar tahrirlanmasa (masalan o'chib ketgan bo'lsa), yangi yozamiz
        msg = await bot.send_message(GROUP_ID, new_text, parse_mode="Markdown")
        last_msg_id = msg.message_id

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        current_data = await create_table_text()
        await message.answer(f"✅ Bot ishga tushdi!\n\n{current_data}", parse_mode="Markdown")
    else:
        await message.answer("Siz admin emassiz.")

async def main():
    # Har 5 daqiqada yangilash funksiyasini ishga tushirish
    scheduler.add_job(refresh_message, "interval", minutes=5)
    scheduler.start()
    
    # Botni ishga tushirish
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
