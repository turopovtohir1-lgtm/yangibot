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
GROUP_ID = -1001549017357  # Siz bergan guruh ID
# ------------------

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
last_msg_id = None

def get_real_budget_data():
    """Open Budget API-dan real ma'lumotlarni yuklab olish"""
    # Chust tumani (districtCode=1714227) uchun API manzili
    url = "https://openbudget.uz/api/v1/user/initiatives?page=0&size=100&districtCode=1714227&order=count,desc"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            initiatives = data.get('content', [])
            
            # Ma'lumotlarni saralash va formatlash
            results = []
            for item in initiatives:
                results.append({
                    'title': item.get('title', 'Nomsiz tashabbus'),
                    'votes': item.get('count', 0)
                })
            
            # Ovozlar bo'yicha qayta saralash (eng ko'pdan kamiga)
            sorted_results = sorted(results, key=lambda x: x['votes'], reverse=True)
            return sorted_results[:10]  # Top 10 talik
        else:
            logging.error(f"Sayt xatosi: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Ulanish xatosi: {e}")
        return None

async def build_table_text():
    """Jadval ko'rinishidagi matnni tayyorlash"""
    data = get_real_budget_data()
    
    if not data:
        return "⚠️ Ma'lumotlarni olishda xatolik yuz berdi. Sayt yuklanmayapti."

    now = datetime.now().strftime("%H:%M")
    text = "📊 **CHUST TUMANI - TOP 10 REYTING**\n"
    text += f"🕒 Oxirgi yangilanish: {now}\n\n"
    
    # Jadval sarlavhasi
    text += "№ | Ovoz | Tashabbus nomi\n"
    text += "---|---|---\n"
    
    for i, item in enumerate(data, 1):
        # Nomni qisqartirish (Telegram jadvaliga sig'ishi uchun)
        clean_name = item['title'].replace('\n', ' ').strip()
        short_name = clean_name[:35] + "..." if len(clean_name) > 35 else clean_name
        text += f"{i} | **{item['votes']}** | {short_name}\n"
    
    text += "\n♻️ _Xabar har 5 daqiqada yangilanmoqda_"
    return text

async def refresh_group_message():
    """Guruhdagi xabarni tahrirlash yoki yangi yuborish"""
    global last_msg_id
    new_text = await build_table_text()
    
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
        # Agar xabar tahrirlanmasa (masalan o'chirilgan bo'lsa), yangi yuboramiz
        msg = await bot.send_message(GROUP_ID, new_text, parse_mode="Markdown")
        last_msg_id = msg.message_id
        logging.info("Yangi xabar yuborildi.")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Admin uchun start buyrug'i"""
    if message.from_user.id == ADMIN_ID:
        current_report = await build_table_text()
        await message.answer(f"✅ Bot faol!\n\nReal vaqt rejimi:\n{current_report}", parse_mode="Markdown")
    else:
        await message.answer("Siz admin emassiz.")

async def main():
    # Bot ishga tushishi bilan birinchi xabarni yuborish
    await refresh_group_message()
    
    # Rejalashtiruvchi: Har 5 daqiqada ishlaydi
    scheduler.add_job(refresh_group_message, "interval", minutes=5)
    scheduler.start()
    
    # Botni polling rejimida ishga tushirish
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
