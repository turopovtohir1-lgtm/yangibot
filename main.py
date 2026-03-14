#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import telebot
import schedule
import threading
import logging
import json
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup

# ── SOZLAMALAR ─────────────────────────────────────────────────────
BOT_TOKEN    = "8769316813:AAGG_qt2faKYjXq8LxuiQhkBz56fsc6We3s"
CHAT_ID      = "@sherbilakmfy"
BOARD_ID     = 53
REGION_ID    = 13      # Namangan viloyati
DISTRICT_ID  = 1306    # Chust tumani (avtomatik topiladi)
TOP_N        = 15
INTERVAL_MIN = 5

BASE_URL = "https://openbudget.uz"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "uz-UZ,uz;q=0.9,ru;q=0.8",
    "Referer": f"https://openbudget.uz/boards/initiatives/initiative/{BOARD_ID}",
}

# ── LOGGING ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── BOT ────────────────────────────────────────────────────────────
bot = telebot.TeleBot(BOT_TOKEN)

# Global o'zgaruvchilar
group_msg_id       = None   # guruhga yuborilgan xabar ID
chust_district_id  = None   # Chust tumani ID


# ══════════════════════════════════════════════════════════════════
# 1. CHUST TUMANI ID TOPISH
# ══════════════════════════════════════════════════════════════════
def find_district_id() -> int:
    urls = [
        f"{BASE_URL}/api/district/list?regionId={REGION_ID}",
        f"{BASE_URL}/api/districts?regionId={REGION_ID}",
        f"{BASE_URL}/api/region/{REGION_ID}/districts",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            items = data if isinstance(data, list) else \
                data.get("data", data.get("content", data.get("items", [])))
            for item in items:
                name = (
                    str(item.get("nameUz", "")) + " " +
                    str(item.get("nameRu", "")) + " " +
                    str(item.get("name", ""))
                ).lower()
                if "chust" in name or "чуст" in name:
                    did = item.get("id") or item.get("districtId")
                    log.info(f"✅ Chust ID topildi: {did}")
                    return int(did)
        except Exception as e:
            log.debug(f"District so'rovi xato: {e}")
    log.warning(f"Chust ID topilmadi, standart ishlatiladi: {DISTRICT_ID}")
    return DISTRICT_ID


# ══════════════════════════════════════════════════════════════════
# 2. MA'LUMOT OLISH — JSON API
# ══════════════════════════════════════════════════════════════════
def fetch_api(did: int):
    endpoints = [
        f"{BASE_URL}/api/initiative/list?boardId={BOARD_ID}&regionId={REGION_ID}&districtId={did}&page=0&size=500&sort=voteCount,desc",
        f"{BASE_URL}/api/initiatives?boardId={BOARD_ID}&regionId={REGION_ID}&districtId={did}&size=500",
        f"{BASE_URL}/api/board/{BOARD_ID}/initiatives?regionId={REGION_ID}&districtId={did}&size=500",
        f"{BASE_URL}/api/v1/initiative?boardId={BOARD_ID}&regionId={REGION_ID}&districtId={did}&size=500",
    ]
    for url in endpoints:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            log.info(f"API [{r.status_code}] {url}")
            if r.status_code != 200:
                continue
            data = r.json()
            raw = (
                data if isinstance(data, list) else
                data.get("content", data.get("data",
                data.get("items",   data.get("initiatives",
                data.get("result", [])))))
            )
            if raw:
                parsed = build_list(raw, did)
                if parsed:
                    return parsed
        except Exception as e:
            log.debug(f"API xato: {e}")
    return None


# ══════════════════════════════════════════════════════════════════
# 3. MA'LUMOT OLISH — HTML / __NEXT_DATA__
# ══════════════════════════════════════════════════════════════════
def fetch_html(did: int):
    url = (
        f"{BASE_URL}/boards/initiatives/initiative/{BOARD_ID}"
        f"?regionId={REGION_ID}&districtId={did}"
    )
    try:
        r = requests.get(url, headers={**HEADERS, "Accept": "text/html"}, timeout=25)
        log.info(f"HTML [{r.status_code}] {url}")
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        # __NEXT_DATA__ (Next.js)
        tag = soup.find("script", id="__NEXT_DATA__")
        if tag and tag.string:
            result = parse_next_data(tag.string, did)
            if result:
                log.info(f"__NEXT_DATA__: {len(result)} ta topildi")
                return result

        # Script ichida JSON array izlash
        for sc in soup.find_all("script"):
            txt = sc.string or ""
            if "voteCount" not in txt and "votesCount" not in txt:
                continue
            for m in re.findall(r'(\[[\s\S]{20,8000}?\])', txt):
                try:
                    arr = json.loads(m)
                    if isinstance(arr, list):
                        parsed = build_list(arr, did)
                        if parsed:
                            log.info(f"Script JSON: {len(parsed)} ta topildi")
                            return parsed
                except Exception:
                    pass

    except Exception as e:
        log.error(f"HTML fetch xato: {e}")
    return None


def parse_next_data(raw: str, did: int):
    try:
        data = json.loads(raw)
    except Exception:
        return None
    found = []

    def walk(obj):
        if isinstance(obj, dict):
            has_vote = {"voteCount", "votes", "votesCount", "supportCount"} & obj.keys()
            has_name = {"nameUz", "nameRu", "name", "title"} & obj.keys()
            if has_vote and has_name:
                found.append(obj)
                return
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return build_list(found, did) if found else None


# ══════════════════════════════════════════════════════════════════
# 4. RO'YXAT TUZISH (filtr + saralash)
# ══════════════════════════════════════════════════════════════════
def build_list(raw: list, did: int) -> list:
    results = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        name = (
            item.get("nameUz") or item.get("name_uz") or
            item.get("nameRu") or item.get("name_ru") or
            item.get("name")   or item.get("title")   or ""
        ).strip()
        if not name:
            continue

        votes = 0
        for key in ("voteCount", "vote_count", "votes", "votesCount", "supportCount"):
            if item.get(key) is not None:
                try:
                    votes = int(item[key])
                    break
                except (ValueError, TypeError):
                    pass

        # Tuman filtri
        d_raw = item.get("districtId") or item.get("district_id")
        if d_raw is None and isinstance(item.get("district"), dict):
            d_raw = item["district"].get("id")
        if d_raw is not None:
            try:
                if int(d_raw) != did:
                    continue
            except (ValueError, TypeError):
                pass

        results.append({"name": name, "votes": votes})

    if not results:
        return []

    results.sort(key=lambda x: x["votes"], reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i
    return results


# ══════════════════════════════════════════════════════════════════
# 5. MA'LUMOT OLISH (API → HTML)
# ══════════════════════════════════════════════════════════════════
def get_data(did: int):
    data = fetch_api(did)
    if not data:
        log.info("API bo'sh — HTML urinilmoqda...")
        data = fetch_html(did)
    return data


# ══════════════════════════════════════════════════════════════════
# 6. XABAR MATNI
# ══════════════════════════════════════════════════════════════════
def make_message(items: list) -> str:
    now   = datetime.now().strftime("%d.%m.%Y  %H:%M")
    count = min(len(items), TOP_N)
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    lines = [
        "📊 <b>Ochiq Byudjet — Tashabbuslar reytingi</b>",
        "📍 <b>Namangan viloyati | Chust tumani</b>",
        f"🕐 <i>Yangilangan: {now}</i>",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        f"<b>🏆 TOP-{count} tashabbuslar</b>",
        "",
    ]
    for item in items[:TOP_N]:
        rank  = item["rank"]
        name  = item["name"][:60] + ("..." if len(item["name"]) > 60 else "")
        votes = item["votes"]
        icon  = medals.get(rank, f"{rank}.")
        lines.append(f"{icon} {name}")
        lines.append(f"    👍 <b>{votes:,}</b> ovoz".replace(",", " "))
        lines.append("")

    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━━",
        f'🔗 <a href="{BASE_URL}/boards/initiatives/initiative/{BOARD_ID}">Batafsil ko\'rish</a>',
    ]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# 7. GURUHGA YUBORISH / TAHRIRLASH
# ══════════════════════════════════════════════════════════════════
def update_group():
    global group_msg_id, chust_district_id

    did   = chust_district_id or DISTRICT_ID
    items = get_data(did)
    if not items:
        log.warning("Ma'lumot topilmadi, xabar yuborilmadi")
        return

    text = make_message(items)

    # Birinchi marta — yangi xabar
    if group_msg_id is None:
        try:
            sent = bot.send_message(
                CHAT_ID, text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            group_msg_id = sent.message_id
            log.info(f"✅ Yangi xabar yuborildi | ID: {group_msg_id}")
        except Exception as e:
            log.error(f"Yuborish xato: {e}")
        return

    # Keyingi safar — tahrirlaymiz
    try:
        bot.edit_message_text(
            text,
            chat_id=CHAT_ID,
            message_id=group_msg_id,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        log.info(f"✏️  Xabar yangilandi | ID: {group_msg_id}")
    except telebot.apihelper.ApiTelegramException as e:
        err = str(e)
        if "message is not modified" in err:
            log.info("ℹ️  O'zgarish yo'q")
        elif "not found" in err or "INVALID" in err:
            log.warning("Xabar topilmadi — qayta yuborilmoqda")
            group_msg_id = None
            update_group()
        else:
            log.error(f"Tahrirlash xato: {e}")


# ══════════════════════════════════════════════════════════════════
# 8. /start KOMANDASI
# ══════════════════════════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    did = chust_district_id or DISTRICT_ID
    log.info(f"/start → {msg.from_user.id}")

    wait = bot.send_message(
        msg.chat.id,
        "⏳ <i>Ma'lumotlar yuklanmoqda...</i>",
        parse_mode="HTML",
    )

    items = get_data(did)

    if not items:
        bot.edit_message_text(
            "❌ Ma'lumot olinmadi. Keyinroq urinib ko'ring.",
            chat_id=msg.chat.id,
            message_id=wait.message_id,
        )
        return

    bot.edit_message_text(
        make_message(items),
        chat_id=msg.chat.id,
        message_id=wait.message_id,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# ══════════════════════════════════════════════════════════════════
# 9. SCHEDULER THREAD
# ══════════════════════════════════════════════════════════════════
def scheduler_thread():
    schedule.every(INTERVAL_MIN).minutes.do(update_group)
    while True:
        schedule.run_pending()
        time.sleep(15)


# ══════════════════════════════════════════════════════════════════
# 10. MAIN
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    log.info("=" * 50)
    log.info("  OpenBudget TOP-15 | Namangan / Chust")
    log.info(f"  Guruh    : {CHAT_ID}")
    log.info(f"  Interval : {INTERVAL_MIN} daqiqa")
    log.info("=" * 50)

    # Chust ID topish
    chust_district_id = find_district_id()

    # Darhol birinchi xabar
    log.info("▶ Dastlabki xabar yuborilmoqda...")
    update_group()

    # Scheduler fon threadda
    t = threading.Thread(target=scheduler_thread, daemon=True)
    t.start()
    log.info(f"⏱  Scheduler ishga tushdi ({INTERVAL_MIN} daqiqa)")

    # Bot polling
    log.info("🤖 Polling boshlandi...")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except Exception as e:
            log.error(f"Polling xato: {e} — 10 soniyada qayta uriniladi")
            time.sleep(10)
