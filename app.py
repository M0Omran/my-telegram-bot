# -*- coding: utf-8 -*-

import logging
import datetime
import os
import json

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- مكتبة جوجل ---
import google.generativeai as genai

# --- الإعدادات الرئيسية ---
TELEGRAM_TOKEN = "7986947716:AAHo-wdAuVo7LLGo21s-B6Cedowe3agevwc" # استبدل بالتوكن الخاص بك
GEMINI_API_KEY = "AIzaSyAWbEECTpbWSaODdFWwiAY4hpmoraiJZWA" # استبدل بمفتاح Gemini الخاص بك

# --- أسماء الملفات ---
STATIONS_DATA_FILE = "stations_data.json"

# --- إعدادات التشغيل الأساسية ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("google.api_core").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# --- إعداد نموذج Gemini ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    print("تم إعداد نموذج Gemini بنجاح.")
except Exception as e:
    print(f"حدث خطأ أثناء إعداد نموذج Gemini: {e}")
    model = None

# --- دوال مساعدة للتعامل مع ملف JSON ---
def load_data():
    if not os.path.exists(STATIONS_DATA_FILE): return {}
    try:
        with open(STATIONS_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}

def save_data(data):
    with open(STATIONS_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- دوال البوت الجديدة ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}! أنا <b>Zekoo v3.0</b>، مساعدك التقني الذكي.\n\n"
        f"<b>الأوامر الأساسية:</b>\n"
        f"<code>/add_station اسم_المحطة الاسم_المختصر SMO=ip...</code>\n"
        f"  (لإضافة بيانات محطة جديدة)\n"
        f"<code>/add_fault اسم_المحطة وصف_العطل كلمات_مفتاحية</code>\n"
        f"  (مثال: /add_fault Attaba انقطاع SMO انقطاع,تهنيج)\n"
        f"<code>/update_status اسم_المحطة اسم_الجهاز الحالة</code>\n"
        f"  (مثال: /update_status Attaba SMO يعمل)\n"
        f"<code>/search وصف_المشكلة</code>\n"
        f"  (للبحث الذكي والمتقدم)"
    )

async def add_station(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("خطأ.\nمثال: /add_station Attaba ATA SMO=10.1.29.20")
        return

    station_name, short_name, *device_args = args
    data = load_data()
    
    # إنشاء هيكل المحطة إذا لم تكن موجودة
    if station_name not in data:
        data[station_name] = {"short_name": short_name.upper(), "devices": {}, "history": []}

    # إضافة/تحديث الأجهزة
    for item in device_args:
        if '=' in item:
            device, ip = item.split('=', 1)
            data[station_name]["devices"][device.upper()] = {"ip": ip, "status": "غير معروف"}
    
    save_data(data)
    await update.message.reply_text(f"تم إضافة/تحديث بيانات محطة '{station_name}' بنجاح.")

async def add_fault(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("خطأ.\nمثال: /add_fault Attaba مشكلة في SMO انقطاع,تهنيج")
        return
    
    station_name = args[0]
    keywords = args[-1].split(',')
    fault_description = " ".join(args[1:-1])
    
    data = load_data()
    if station_name not in data:
        await update.message.reply_text(f"خطأ: المحطة '{station_name}' غير موجودة.")
        return
    
    fault_record = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": update.message.from_user.first_name,
        "description": fault_description,
        "keywords": [k.strip() for k in keywords]
    }
    data[station_name]["history"].append(fault_record)
    save_data(data)
    await update.message.reply_text(f"تم تسجيل العطل في تاريخ محطة '{station_name}'.")

async def update_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) != 3:
        await update.message.reply_text("خطأ.\nمثال: /update_status Attaba SMO يعمل")
        return
        
    station_name, device_name, status = args
    data = load_data()
    if station_name in data and device_name.upper() in data[station_name]["devices"]:
        data[station_name]["devices"][device_name.upper()]["status"] = status
        save_data(data)
        await update.message.reply_text(f"تم تحديث حالة جهاز {device_name.upper()} في محطة {station_name} إلى '{status}'.")
    else:
        await update.message.reply_text("خطأ: المحطة أو الجهاز غير موجود.")

async def search_in_kb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.message.from_user.first_name
    search_query = " ".join(context.args)
    if not search_query:
        await update.message.reply_text("الرجاء كتابة وصف للمشكلة بعد الأمر /search.")
        return

    await update.message.reply_text(f"أهلاً بك يا {user_name}. لحظات من فضلك، أقوم بتحليل البيانات لأجد لك أفضل حل...")

    data = load_data()
    # تحويل كل بياناتنا إلى نص لـ Gemini
    full_context = json.dumps(data, ensure_ascii=False, indent=2)

    prompt = f"""
    أنت "كبير المهندسين Zekoo"، مساعد تقني خبير ومحلل بيانات. مهمتك هي مساعدة المهندس "{user_name}" في حل مشكلة تقنية.

    **سؤال المهندس:**
    "{search_query}"

    **قاعدة البيانات الكاملة المتاحة لك (بتنسيق JSON):**
    ```json
    {full_context}
    ```

    **مهمتك المطلوبة بدقة:**
    1.  **تحليل عميق:** اقرأ سؤال المهندس بعناية. ثم ابحث في قاعدة البيانات الكاملة عن أي معلومات ذات صلة (محطات, أجهزة, IPs, حالات, أوصاف أعطال, كلمات مفتاحية).
    2.  **إيجاد الأعطال المشابهة:** ركز على إيجاد الأعطال السابقة التي تتشابه مع المشكلة الحالية بناءً على **وصف العطل والكلمات المفتاحية (keywords)**. لا تعتمد على التاريخ فقط.
    3.  **استخلاص الحلول:** بناءً على الأعطال السابقة المشابهة، استخلص الخطوات التي تم اتخاذها لحلها.
    4.  **صياغة الرد:** قم بصياغة رد احترافي ومنظم.

    **شروط تنسيق الرد النهائي (مهم جداً):**
    *   **الترحيب:** ابدأ ردك بالعبارة التالية بالضبط: "أهلاً بك يا {user_name}، بصفتي كبير المهندسين، قمت بتحليل الموقف وإليك خطة العمل المقترحة:"
    *   **التحليل المبدئي:** في فقرة قصيرة، اذكر تشخيصك المبدئي للمشكلة.
    *   **الأعطال السابقة ذات الصلة:** إذا وجدت أعطالاً سابقة مشابهة، اذكرها بإيجاز تحت عنوان "**تاريخ الأعطال المشابهة:**". اذكر تاريخ ووصف أهم عطل سابق.
    *   **البيانات الفنية:** إذا كان الحل يتطلب معرفة IP أو حالة جهاز، اذكرها تحت عنوان "**البيانات الفنية المطلوبة:**".
    *   **خطة العمل:** قدم الحل النهائي على هيئة **خطوات مرقمة وواضحة** تحت عنوان "**خطة العمل المقترحة:**".

    إذا لم تجد أي معلومات مفيدة، اعتذر وقدم نصيحة عامة.
    """

    if not model:
        await update.message.reply_text("عذراً، خدمة الذكاء الاصطناعي Gemini غير متاحة.")
        return
        
    try:
        request_options = {"timeout": 120} # زيادة المهلة قليلاً للتحليل المعقد
        response = await model.generate_content_async(prompt, request_options=request_options)
        ai_response = response.text
    except Exception as e:
        await update.message.reply_text(f"عذراً، واجهت خطأ أثناء التحليل. الخطأ: {e}")
        return

    await update.message.reply_text(ai_response)

def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_station", add_station))
    application.add_handler(CommandHandler("add_fault", add_fault))
    application.add_handler(CommandHandler("update_status", update_status))
    application.add_handler(CommandHandler("search", search_in_kb))
    print("Zekoo v3.0 (المساعد الذكي) قيد التشغيل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
