import requests
from bs4 import BeautifulSoup

def get_budget_data(target_id="53"):
    url = "https://openbudget.uz/boards/initiatives" # Umumiy ro'yxat sahifasi
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        # Eslatma: Haqiqiy holatda Open Budget API'dan yoki JSON orqali ma'lumot beradi
        # Quyida umumiy mantiqiy model keltirilgan
        response = requests.get(url, headers=headers)
        # Bu yerda sayt strukturasiga qarab parsing qilinadi
        # Misol uchun:
        data = [
            {"name": "Tashabbus 1", "votes": 1500, "id": "1"},
            {"name": "Sizning tashabbus", "votes": 1200, "id": "53"},
            # ... 10 talik ro'yxat
        ]
        return sorted(data, key=lambda x: x['votes'], reverse=True)
    except Exception as e:
        print(f"Xatolik: {e}")
        return None
