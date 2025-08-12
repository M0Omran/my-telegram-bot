# -*- coding: utf-8 -*-

import logging
import datetime
import os
import json
import re
import requests # استيراد المكتبة الجديدة

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- الإعدادات الرئيسية (تم التحديث النهائي) ---
TELEGRAM_TOKEN = "7986947716:AAF3L0zIrXfsNWOvsXqMH3liEYBx8asrqs8"
# لا حاجة لمفتاح API هنا لأننا سنستخدم واجهة عامة مؤقتاً

# --- أسماء ملفات قواعد البيانات ---
STATIONS_DATA_FILE = "stations_data.json"
PROCEDURES_FILE = "procedures.json"
GENERAL_EVENTS_FILE = "general_events.json"

# --- إعدادات التشغيل الأساسية ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- دوال مساعدة للتعامل مع ملفات JSON ---
def load_data(file_path):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_data(data, file_path):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- دالة البحث عن اختصار المحطة ---
def find_station_key(text, stations_data):
    words = re.findall(r'\b\w+\b', text.upper())
    for word in words:
        for key, station_info in stations_data.items():
            if station_info.get("short_name", "").upper() == word:
                return key
    return None

# --- دوال الأوامر الأساسية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}! أنا <b>Zekoo v8.0 (متصل بـ Manus)</b>، مساعدك الذكي.\n\n"
        f"<b>لتسجيل أي معلومة:</b> <code>/log</code>\n"
        f"<b>للبحث الذكي:</b> <code>/search</code>\n"
        f"<b>لإضافة بيانات:</b> <code>/add</code>\n"
        f"<b>لعرض المحطات:</b> <code>/list_stations</code> أو <code>#اختصار</code>"
    )

async def log_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = " ".join(context.args)
    user_name = update.message.from_user.first_name
    if not user_message:
        await update.message.reply_text("الرجاء كتابة المعلومة بعد أمر /log.")
        return
    await update.message.reply_text("فهمت. لحظات من فضلك، أقوم بتحليل وتخزين المعلومة...")
    stations_data = load_data(STATIONS_DATA_FILE)
    station_key = find_station_key(user_message, stations_data)
    record = {"date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "user": user_name, "message": user_message}
    if station_key:
        if "history" not in stations_data[station_key]:
            stations_data[station_key]["history"] = []
        stations_data[station_key]["history"].append(record)
        save_data(stations_data, STATIONS_DATA_FILE)
        await update.message.reply_text(f"تم تسجيل المعلومة بنجاح في سجل محطة '{station_key}'.")
    else:
        general_events = load_data(GENERAL_EVENTS_FILE)
        if "events" not in general_events:
            general_events["events"] = []
        general_events["events"].append(record)
        save_data(general_events, GENERAL_EVENTS_FILE)
        await update.message.reply_text("تم تسجيل المعلومة كـ 'حدث عام'.")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("خطأ.\nمثال: /add Attaba SMO ip=10.1.29.20")
        return
    station_name, device_name, *device_details = args
    stations_data = load_data(STATIONS_DATA_FILE)
    target_station_key = None
    for key, info in stations_data.items():
        if info.get("short_name", "").upper() == station_name.upper() or key.upper() == station_name.upper():
            target_station_key = key
            break
    if not target_station_key:
        stations_data[station_name] = {"short_name": station_name.upper(), "devices": {}, "history": []}
        target_station_key = station_name
    if "devices" not in stations_data[target_station_key]:
        stations_data[target_station_key]["devices"] = {}
    if device_name.upper() not in stations_data[target_station_key]["devices"]:
        stations_data[target_station_key]["devices"][device_name.upper()] = {}
    for detail in device_details:
        if '=' in detail:
            key, value = detail.split('=', 1)
            stations_data[target_station_key]["devices"][device_name.upper()][key.lower()] = value
    save_data(stations_data, STATIONS_DATA_FILE)
    await update.message.reply_text(f"تم إضافة/تحديث بيانات جهاز '{device_name.upper()}' في محطة '{target_station_key}'.")

async def list_stations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    stations_data = load_data(STATIONS_DATA_FILE)
    if not stations_data:
        await update.message.reply_text("لا توجد أي محطات مسجلة.")
        return
    message = "<b>قائمة المحطات المسجلة:</b>\n\n"
    for name, data in sorted(stations_data.items()):
        short_name = data.get('short_name', 'N/A')
        devices_count = len(data.get('devices', {}))
        history_count = len(data.get('history', []))
        message += f"• <b>{name} ({short_name})</b> | أجهزة: {devices_count} | سجل: {history_count}\n"
    await update.message.reply_html(message)

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.message.from_user.first_name
    search_query = " ".join(context.args)
    if not search_query:
        await update.message.reply_text("الرجاء كتابة وصف للمشكلة بعد الأمر /search.")
        return

    await update.message.reply_text(f"أهلاً بك يا {user_name}. لحظات من فضلك، أقوم بتحليل البيانات لأجد لك أفضل حل...")

    stations_data = load_data(STATIONS_DATA_FILE)
    procedures = load_data(PROCEDURES_FILE)
    general_events = load_data(GENERAL_EVENTS_FILE)

    stations_context = json.dumps(stations_data, ensure_ascii=False, indent=2)
    procedures_context = json.dumps(procedures, ensure_ascii=False, indent=2)
    general_events_context = json.dumps(general_events, ensure_ascii=False, indent=2)

    prompt = f"""
    أنت "المرشد الخبير Zekoo"، مساعد تقني ذكي ومحلل بيانات. مهمتك هي مساعدة المهندس "{user_name}" في حل مشكلة تقنية.
    **سؤال المهندس:** "{search_query}"
    **لديك ثلاثة مصادر للمعلومات:**
    1. **قاعدة الإجراءات القياسية (Procedures):** الأولوية القصوى.
    2. **سجل أعطال المحطات (Stations Data):** يحتوي على بيانات الأجهزة (IPs) وتاريخ الأعطال.
    3. **سجل الأحداث العامة (General Events):** ملاحظات عامة.
    **قاعدة الإجراءات:**\n{procedures_context}
    **بيانات المحطات:**\n{stations_context}
    **الأحداث العامة:**\n{general_events_context}
    **مهمتك المطلوبة بدقة:**
    1. **الأولوية للإجراءات:** ابحث أولاً في "قاعدة الإجراءات". إذا وجدت تطابقاً، اعرضه فقط.
    2. **إذا لم تجد:** حلل السجلات الأخرى وقدم ملخصاً للخبرات السابقة. إذا كانت المشكلة تخص جهازاً، **يجب** أن تذكر الـ IP الخاص به.
    """
    
    # --- استدعاء Manus API الحقيقي ---
    api_url = "https://manus-api-knower-dev.up.railway.app/ask"
    payload = {"question": prompt}
    
    try:
        response = requests.post(api_url, json=payload, timeout=60)
        response.raise_for_status()  # سيرفع استثناء لأكواد الخطأ (4xx or 5xx)
        api_response = response.json().get("answer", "لم أتمكن من الحصول على إجابة.")
    except requests.exceptions.RequestException as e:
        logger.error(f"خطأ في الاتصال بـ Manus API: {e}")
        api_response = "عذراً، واجهت مشكلة في الاتصال بخادم الذكاء الاصطناعي. يرجى المحاولة مرة أخرى لاحقاً."
    
    await update.message.reply_text(api_response)

async def hashtag_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message_text = update.message.text
    hashtag = message_text.lstrip('#').upper()
    stations_data = load_data(STATIONS_DATA_FILE)
    target_station_key = None
    station_info = None
    for key, info in stations_data.items():
        if info.get("short_name", "").upper() == hashtag:
            target_station_key = key
            station_info = info
            break
    if not target_station_key:
        await update.message.reply_text(f"لم أجد محطة بالاختصار '{hashtag}'.")
        return
    full_name, short_name = target_station_key, station_info.get("short_name", "N/A")
    devices, history = station_info.get("devices", {}), station_info.get("history", [])
    reply = f"<b>📁 بطاقة معلومات محطة: {full_name} ({short_name})</b>\n-----------------------------------\n"
    if devices:
        reply += "<b>💻 الأجهزة المسجلة:</b>\n"
        for device_name, details in devices.items():
            reply += f"  • <b>{device_name}</b>\n"
            if details:
                for key, value in details.items():
                    reply += f"    - {key.capitalize()}: <code>{value}</code>\n"
            else:
                reply += "    - لا توجد تفاصيل مسجلة.\n"
    else:
        reply += "لا توجد أجهزة مسجلة لهذه المحطة.\n"
    reply += "-----------------------------------\n"
    if history:
        reply += "<b>📜 آخر 5 أعطال مسجلة:</b>\n"
        for record in reversed(history[-5:]):
            reply += f"  - <b>{record['date']}</b> ({record['user']}): {record['message']}\n"
    else:
        reply += "لا يوجد سجل أعطال لهذه المحطة.\n"
    await update.message.reply_html(reply, disable_web_page_preview=True)

def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("log", log_message))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("list_stations", list_stations))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(MessageHandler(filters.Regex(r'^#\w+'), hashtag_handler))
    print("Zekoo v8.0 (متصل بـ Manus) قيد التشغيل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
