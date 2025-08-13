# -*- coding: utf-8 -*-

import logging
import datetime
import os
import json
import re

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- الإعدادات الرئيسية ---
TELEGRAM_TOKEN = "7986947716:AAF3L0zIrXfsNWOvsXqMH3liEYBx8asrqs8"

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

# --- دوال مساعدة ---
def load_data(file_path):
    if not os.path.exists(file_path): return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            return json.loads(content) if content else {}
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_data(data, file_path):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def find_station_key(text, stations_data):
    words = re.findall(r'\b\w+\b', text.upper())
    for word in words:
        for key, station_info in stations_data.items():
            if station_info.get("short_name", "").upper() == word:
                return key
    return None

# --- العقل التحليلي المدمج (مع تنسيق محسن للإجابات) ---
def local_manus_analysis(prompt, search_query, stations_data, procedures, general_events):
    # 1. البحث عن إجراء قياسي (الأولوية القصوى)
    for proc_key, proc_details in procedures.items():
        search_area = proc_details.get('title', '') + ' ' + ' '.join(proc_details.get('keywords', []))
        if any(word.lower() in search_area.lower() for word in search_query.split()):
            response = f"بناءً على قاعدة المعرفة الرسمية، هذه المشكلة لها إجراء إصلاح قياسي.\n\n"
            response += f"<b>📜 {proc_details.get('title', 'بلا عنوان')}</b>\n\n"
            # --- التحسين هنا ---
            for step_data in proc_details.get('steps', []):
                step_title = step_data.get('title', 'خطوة')
                step_details = step_data.get('details', 'لا توجد تفاصيل.')
                response += f"<b>- {step_title}:</b> {step_details}\n"
            return response

    # 2. إذا لم يوجد إجراء، ابحث في سجلات الأعطال
    response = "لم أجد إجراءً قياسياً لهذه المشكلة، ولكن بناءً على الخبرات السابقة، إليك التحليل:\n\n"
    found_info = False
    
    search_words = set(search_query.lower().split())
    
    # البحث في تاريخ المحطات
    for station_name, station_info in stations_data.items():
        station_aliases = {station_name.lower(), station_info.get("short_name", "").lower()}
        if search_words.intersection(station_aliases):
            history = station_info.get("history", [])
            if history:
                found_info = True
                response += f"<b>في محطة {station_name}:</b>\n"
                for record in reversed(history[-2:]):
                    response += f"- بتاريخ {record['date']}، سجل المستخدم '{record['user']}' الآتي: '{record['message']}'\n"
                response += "\n"

    # البحث في الأحداث العامة
    events = general_events.get("events", [])
    for event in events:
        if any(word.lower() in event.get('message', '').lower() for word in search_query.split()):
            found_info = True
            response += f"<b>حدث عام مسجل قد يكون ذا صلة:</b>\n"
            response += f"- بتاريخ {event['date']}، سجل المستخدم '{event['user']}' الآتي: '{event['message']}'\n\n"

    if not found_info:
        response = "عذراً، لم أجد أي معلومات ذات صلة في قاعدة البيانات الحالية حول هذا الموضوع."

    return response

# --- دوال الأوامر (تبقى كما هي) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}! أنا <b>Zekoo v9.1 (بعقل مدمج وعرض محسن)</b>، مساعدك الذكي.\n\n"
        f"أنا الآن أعمل بشكل مستقل تماماً. جرب أمر <code>/search</code> لترى التحليل الفوري."
    )

async def log_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = " ".join(context.args)
    user_name = update.message.from_user.first_name
    if not user_message:
        await update.message.reply_text("الرجاء كتابة المعلومة بعد أمر /log.")
        return
    await update.message.reply_text("فهمت. لحظات من فضلك، أقوم بتخزين المعلومة...")
    stations_data = load_data(STATIONS_DATA_FILE)
    station_key = find_station_key(user_message, stations_data)
    record = {"date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "user": user_name, "message": user_message}
    if station_key:
        stations_data.setdefault(station_key, {}).setdefault("history", []).append(record)
        save_data(stations_data, STATIONS_DATA_FILE)
        await update.message.reply_text(f"تم تسجيل المعلومة بنجاح في سجل محطة '{station_key}'.")
    else:
        general_events = load_data(GENERAL_EVENTS_FILE)
        general_events.setdefault("events", []).append(record)
        save_data(general_events, GENERAL_EVENTS_FILE)
        await update.message.reply_text("تم تسجيل المعلومة كـ 'حدث عام'.")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.message.from_user.first_name
    search_query = " ".join(context.args)
    if not search_query:
        await update.message.reply_text("الرجاء كتابة وصف للمشكلة بعد الأمر /search.")
        return

    await update.message.reply_text(f"أهلاً بك يا {user_name}. لحظات من فضلك، أقوم بالتحليل الفوري...")

    stations_data = load_data(STATIONS_DATA_FILE)
    procedures = load_data(PROCEDURES_FILE)
    general_events = load_data(GENERAL_EVENTS_FILE)

    analysis_result = local_manus_analysis(None, search_query, stations_data, procedures, general_events)
    
    await update.message.reply_html(analysis_result)

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
    
    devices = stations_data[target_station_key].setdefault("devices", {})
    device = devices.setdefault(device_name.upper(), {})
    
    for detail in device_details:
        if '=' in detail:
            key, value = detail.split('=', 1)
            device[key.lower()] = value
            
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
    print("Zekoo v9.1 (بعقل مدمج وعرض محسن) قيد التشغيل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
