# -*- coding: utf-8 -*-

import logging
import datetime
import os
import json
import re

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- الإعدادات الرئيسية (تم التحديث النهائي) ---
TELEGRAM_TOKEN = "7986947716:AAF3L0zIrXfsNWOvsXqMH3liEYBx8asrqs8"
MANUS_API_KEY = "YOUR_MANUS_API_KEY_HERE" # استبدل هذا بمفتاح Manus API الفعلي

# --- أسماء ملفات قواعد البيانات ---
STATIONS_DATA_FILE = "stations_data.json"
PROCEDURES_FILE = "procedures.json"
GENERAL_EVENTS_FILE = "general_events.json" # ملف جديد للأحداث العامة

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
            # إذا كان الملف فارغاً، أرجع قاموساً فارغاً
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
    # يبحث عن كلمات كاملة تتطابق مع اختصارات المحطات
    words = re.findall(r'\b\w+\b', text.upper())
    for word in words:
        for key, station_info in stations_data.items():
            if station_info.get("short_name", "").upper() == word:
                return key # يرجع اسم المحطة الكامل
    return None

# --- دوال الأوامر الأساسية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}! أنا <b>Zekoo v7.0</b>، مساعدك الذكي.\n\n"
        f"<b>لتسجيل أي معلومة (عطل، حل، تحديث):</b>\n"
        f"استخدم أمر <code>/log</code> ثم اكتب ما تريد. إذا كانت المعلومة تخص محطة، اذكر اختصارها (مثل ATA).\n"
        f"مثال لمحطة: <code>/log عطل في جهاز SMO بمحطة ATA</code>\n"
        f"مثال لحدث عام: <code>/log تم تحديث نظام الطاقة في الـ CCP</code>\n\n"
        f"<b>للبحث الذكي:</b>\n"
        f"<code>/search وصف المشكلة</code>\n\n"
        f"<b>لإضافة أو تحديث بيانات جهاز:</b>\n"
        f"<code>/add اسم_المحطة اسم_الجهاز key1=value1 key2=value2 ...</code>\n\n"
        f"<b>لعرض كل المحطات:</b>\n"
        f"<code>/list_stations</code>\n\n"
        f"<b>لعرض بيانات محطة بالاختصار:</b>\n"
        f"اكتب الهاشتاج متبوعاً بالاختصار (مثال: <code>#ATA</code>)"
    )

async def log_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = " ".join(context.args)
    user_name = update.message.from_user.first_name

    if not user_message:
        await update.message.reply_text("الرجاء كتابة المعلومة التي تريد تسجيلها بعد أمر /log.")
        return

    await update.message.reply_text("فهمت. لحظات من فضلك، أقوم بتحليل وتخزين المعلومة...")

    stations_data = load_data(STATIONS_DATA_FILE)
    station_key = find_station_key(user_message, stations_data)

    record = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": user_name,
        "message": user_message
    }

    if station_key:
        # إذا تم العثور على محطة، سجل في تاريخ المحطة
        if "history" not in stations_data[station_key]:
            stations_data[station_key]["history"] = []
        stations_data[station_key]["history"].append(record)
        save_data(stations_data, STATIONS_DATA_FILE)
        await update.message.reply_text(f"تم تسجيل المعلومة بنجاح في سجل محطة '{station_key}'. شكراً لك!")
    else:
        # إذا لم يتم العثور على محطة، سجل كحدث عام
        general_events = load_data(GENERAL_EVENTS_FILE)
        if "events" not in general_events:
            general_events["events"] = []
        general_events["events"].append(record)
        save_data(general_events, GENERAL_EVENTS_FILE)
        await update.message.reply_text("لم أجد اختصار محطة، لذا تم تسجيل المعلومة كـ 'حدث عام'. شكراً لك!")

# --- باقي الدوال (add, list_stations, search, hashtag_handler) تبقى كما هي ---
# (تم حذفها من هنا للاختصار، لكن يجب أن تكون موجودة في ملفك)
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("خطأ.\nمثال: /add Attaba SMO ip=10.1.29.20 user=smo pass=123")
        return

    station_name, device_name, *device_details = args
    stations_data = load_data(STATIONS_DATA_FILE)

    # البحث عن اسم المحطة الكامل
    target_station_key = None
    for key, info in stations_data.items():
        if info.get("short_name", "").upper() == station_name.upper() or key.upper() == station_name.upper():
            target_station_key = key
            break
    
    if not target_station_key:
        # إنشاء محطة جديدة إذا لم تكن موجودة
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
    await update.message.reply_text(f"تم إضافة/تحديث بيانات جهاز '{device_name.upper()}' في محطة '{target_station_key}' بنجاح.")

async def list_stations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    stations_data = load_data(STATIONS_DATA_FILE)
    if not stations_data:
        await update.message.reply_text("لا توجد أي محطات مسجلة في النظام حتى الآن.")
        return

    message = "<b>قائمة المحطات المسجلة في النظام:</b>\n\n"
    for name, data in sorted(stations_data.items()):
        short_name = data.get('short_name', 'N/A')
        devices_count = len(data.get('devices', {}))
        history_count = len(data.get('history', []))
        message += f"• <b>{name} ({short_name})</b>\n"
        message += f"    - الأجهزة: {devices_count}\n"
        message += f"    - سجل الأعطال: {history_count}\n\n"

    await update.message.reply_html(message)

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # هذا هو كود البحث باستخدام Manus API
    # سيتم استبدال Gemini بـ Manus هنا
    pass # سنقوم بتطوير هذه الدالة لاحقاً

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
        await update.message.reply_text(f"لم أجد محطة بالاختصار '{hashtag}'. استخدم /list_stations لمعرفة الاختصارات المتاحة.")
        return

    # بناء الرسالة
    full_name = target_station_key
    short_name = station_info.get("short_name", "N/A")
    devices = station_info.get("devices", {})
    history = station_info.get("history", [])

    reply = f"<b>📁 بطاقة معلومات محطة: {full_name} ({short_name})</b>\n"
    reply += "-----------------------------------\n"
    
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
        # عرض آخر 5 أعطال فقط
        for record in reversed(history[-5:]):
            reply += f"  - <b>{record['date']}</b> (بواسطة: {record['user']}): {record['message']}\n"
    else:
        reply += "لا يوجد سجل أعطال لهذه المحطة.\n"

    await update.message.reply_html(reply, disable_web_page_preview=True)

def main() -> None:
    """الدالة الرئيسية لتشغيل البوت."""
    # التأكد من وجود الملفات عند بدء التشغيل
    load_data(STATIONS_DATA_FILE)
    load_data(PROCEDURES_FILE)
    load_data(GENERAL_EVENTS_FILE)
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("log", log_message))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("list_stations", list_stations))
    # application.add_handler(CommandHandler("search", search)) # معطل مؤقتاً
    application.add_handler(MessageHandler(filters.Regex(r'^#\w+'), hashtag_handler))
    
    print("Zekoo v7.0 (المساعد الذكي) قيد التشغيل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
