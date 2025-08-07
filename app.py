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
TELEGRAM_TOKEN = "7986947716:AAHo-wdAuVo7LLGo21s-B6Cedowe3agevwc"  # استبدل بالتوكن الخاص بك
GEMINI_API_KEY = "AIzaSyAWbEECTpbWSaODdFWwiAY4hpmoraiJZWA"  # استبدل بمفتاح Gemini الخاص بك

# --- أسماء ملفات قواعد البيانات ---
STATIONS_DATA_FILE = "stations_data.json"
PROCEDURES_FILE = "procedures.json"

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

# --- دوال مساعدة للتعامل مع ملفات JSON ---
def load_data(file_path):
    """دالة عامة لتحميل البيانات من أي ملف JSON."""
    if not os.path.exists(file_path):
        # إذا كان الملف هو ملف الإجراءات ولم يكن موجوداً، ننشئه بمثال
        if file_path == PROCEDURES_FILE:
            predefined_procedures = {
                "LSB_FAULT": {
                    "title": "عطل عام في السيرفر المحلي (LSB)",
                    "keywords": ["lsb", "سيرفر", "محلي", "متوقف", "vnc"],
                    "steps": [
                        "قم بالعثور على عنوان IP الخاص بجهاز LSB من بيانات المحطة.",
                        "قم بفتح شاشة LSB باستخدام برنامج VNC للتحكم عن بعد.",
                        "تأكد من أن المؤشر (Indicator) في أعلى يمين الشاشة يعمل ويتحرك.",
                        "افتح الـ Terminal وتأكد من أن العمليات (processes) الأساسية قيد التشغيل."
                    ]
                },
                "SMO_DISCONNECT": {
                    "title": "انقطاع الاتصال مع SMO",
                    "keywords": ["smo", "انقطاع", "اتصال", "ping", "فاصل"],
                    "steps": [
                        "تحقق من الاتصال الفيزيائي (الكابلات) بجهاز SMO.",
                        "قم بعمل Ping على عنوان IP الخاص بـ SMO للتأكد من وجود استجابة.",
                        "إذا لم يكن هناك استجابة، حاول إعادة تشغيل جهاز SMO."
                    ]
                }
            }
            save_data(predefined_procedures, file_path)
            return predefined_procedures
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_data(data, file_path):
    """دالة عامة لحفظ البيانات في أي ملف JSON."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- دوال الأوامر الأساسية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}! أنا <b>Zekoo v4.0</b>، مرشدك التقني التفاعلي.\n\n"
        f"<b>الأوامر المتاحة:</b>\n"
        f"<code>/search وصف_المشكلة</code> - للبحث الذكي عن حلول.\n"
        f"<code>/add_fault اسم_المحطة وصف_العطل كلمات_مفتاحية</code> - لتسجيل خبرة جديدة.\n"
        f"<code>/add_station ...</code> - لإضافة بيانات محطة.\n"
        f"<code>/update_status ...</code> - لتحديث حالة جهاز."
    )

async def add_station(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("خطأ.\nمثال: /add_station Attaba ATA SMO=10.1.29.20")
        return

    station_name, short_name, *device_args = args
    data = load_data(STATIONS_DATA_FILE)
    
    if station_name not in data:
        data[station_name] = {"short_name": short_name.upper(), "devices": {}, "history": []}

    for item in device_args:
        if '=' in item:
            device, ip = item.split('=', 1)
            data[station_name]["devices"][device.upper()] = {"ip": ip, "status": "غير معروف"}
    
    save_data(data, STATIONS_DATA_FILE)
    await update.message.reply_text(f"تم إضافة/تحديث بيانات محطة '{station_name}' بنجاح.")

async def add_fault(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("خطأ.\nمثال: /add_fault Attaba مشكلة في SMO انقطاع,تهنيج")
        return
    
    station_name = args[0]
    keywords = args[-1].split(',')
    fault_description = " ".join(args[1:-1])
    
    data = load_data(STATIONS_DATA_FILE)
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
    save_data(data, STATIONS_DATA_FILE)
    await update.message.reply_text(f"تم تسجيل العطل كخبرة جديدة في سجل محطة '{station_name}'.")

async def update_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) != 3:
        await update.message.reply_text("خطأ.\nمثال: /update_status Attaba SMO يعمل")
        return
        
    station_name, device_name, status = args
    data = load_data(STATIONS_DATA_FILE)
    if station_name in data and device_name.upper() in data[station_name]["devices"]:
        data[station_name]["devices"][device_name.upper()]["status"] = status
        save_data(data, STATIONS_DATA_FILE)
        await update.message.reply_text(f"تم تحديث حالة جهاز {device_name.upper()} في محطة {station_name} إلى '{status}'.")
    else:
        await update.message.reply_text("خطأ: المحطة أو الجهاز غير موجود.")

# --- محرك البحث الذكي والمطور ---

async def search_in_kb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.message.from_user.first_name
    search_query = " ".join(context.args)
    if not search_query:
        await update.message.reply_text("الرجاء كتابة وصف للمشكلة بعد الأمر /search.")
        return

    await update.message.reply_text(f"أهلاً بك يا {user_name}. لحظات من فضلك، أبحث في قواعد المعرفة عن أفضل حل...")

    # تحميل كل قواعد البيانات المتاحة
    stations_history = load_data(STATIONS_DATA_FILE)
    procedures = load_data(PROCEDURES_FILE)

    # تحويل البيانات إلى نص لـ Gemini
    history_context = json.dumps(stations_history, ensure_ascii=False, indent=2)
    procedures_context = json.dumps(procedures, ensure_ascii=False, indent=2)

    prompt = f"""
    أنت "المرشد الخبير Zekoo"، مساعد تقني ذكي ومحلل بيانات. مهمتك هي مساعدة المهندس "{user_name}" في حل مشكلة تقنية.

    **سؤال المهندس:**
    "{search_query}"

    **لديك مصدران للمعلومات:**
    1.  **قاعدة الإجراءات القياسية (Procedures):** تحتوي على حلول جاهزة وموثوقة لمشاكل شائعة.
    2.  **سجل الأعطال التاريخي (History):** يحتوي على خبرات سابقة سجلها الفريق.

    **قاعدة الإجراءات القياسية المتاحة لك:**
    ```json
    {procedures_context}
    ```

    **سجل الأعطال التاريخي المتاح لك:**
    ```json
    {history_context}
    ```

    **مهمتك المطلوبة بدقة (اتبع هذا الترتيب):**
    1.  **الأولوية للإجراءات القياسية:** أولاً، تحقق إذا كان سؤال المهندس يتطابق مع أي مشكلة في "قاعدة الإجراءات القياسية" بناءً على العنوان أو الكلمات المفتاحية (keywords).
    2.  **إذا وجدت إجراءً مطابقاً:**
        *   يجب أن يكون ردك هو الإجراء القياسي فقط.
        *   ابدأ ردك بالعبارة التالية بالضبط: "حسناً يا {user_name}، بناءً على قاعدة الإجراءات المعتمدة، هذه المشكلة لها حل قياسي."
        *   ثم اعرض عنوان الإجراء وخطواته بشكل واضح ومرقم. لا تضف أي معلومات من سجل الأعطال.
    3.  **إذا لم تجد أي إجراء مطابق:**
        *   انتقل إلى تحليل "سجل الأعطال التاريخي".
        *   ابحث عن أعطال مشابهة في السجل بناءً على الوصف والكلمات المفتاحية.
        *   ابدأ ردك بالعبارة التالية بالضبط: "حسناً يا {user_name}، لم أجد إجراءً قياسياً لهذه المشكلة، ولكن بناءً على الخبرات السابقة، إليك التحليل:"
        *   لخص أهم عطل سابق مشابه والحلول التي تم استنتاجها.

    **تنسيق الرد يجب أن يكون احترافياً وواضحاً.**
    """

    if not model:
        await update.message.reply_text("عذراً، خدمة الذكاء الاصطناعي Gemini غير متاحة.")
        return
        
    try:
        request_options = {"timeout": 120}
        response = await model.generate_content_async(prompt, request_options=request_options)
        ai_response = response.text
    except Exception as e:
        await update.message.reply_text(f"عذراً، واجهت خطأ أثناء التحليل. الخطأ: {e}")
        return

    await update.message.reply_text(ai_response)

def main() -> None:
    """الدالة الرئيسية لتشغيل البوت."""
    # التأكد من إنشاء ملف الإجراءات عند بدء التشغيل
    load_data(PROCEDURES_FILE)
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_station", add_station))
    application.add_handler(CommandHandler("add_fault", add_fault))
    application.add_handler(CommandHandler("update_status", update_status))
    application.add_handler(CommandHandler("search", search_in_kb))
    
    print("Zekoo v4.0 (المرشد الخبير) قيد التشغيل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()# -*- coding: utf-8 -*-

import logging
import datetime
import os
import json

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- مكتبة جوجل ---
import google.generativeai as genai

# --- الإعدادات الرئيسية ---
TELEGRAM_TOKEN = "7986947716:AAHo-wdAuVo7LLGo21s-B6Cedowe3agevwc
"  # استبدل بالتوكن الخاص بك
GEMINI_API_KEY = "AIzaSyAWbEECTpbWSaODdFWwiAY4hpmoraiJZWA"  # استبدل بمفتاح Gemini الخاص بك

# --- أسماء ملفات قواعد البيانات ---
STATIONS_DATA_FILE = "stations_data.json"
PROCEDURES_FILE = "procedures.json"

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

# --- دوال مساعدة للتعامل مع ملفات JSON ---
def load_data(file_path):
    """دالة عامة لتحميل البيانات من أي ملف JSON."""
    if not os.path.exists(file_path):
        # إذا كان الملف هو ملف الإجراءات ولم يكن موجوداً، ننشئه بمثال
        if file_path == PROCEDURES_FILE:
            predefined_procedures = {
                "LSB_FAULT": {
                    "title": "عطل عام في السيرفر المحلي (LSB)",
                    "keywords": ["lsb", "سيرفر", "محلي", "متوقف", "vnc"],
                    "steps": [
                        "قم بالعثور على عنوان IP الخاص بجهاز LSB من بيانات المحطة.",
                        "قم بفتح شاشة LSB باستخدام برنامج VNC للتحكم عن بعد.",
                        "تأكد من أن المؤشر (Indicator) في أعلى يمين الشاشة يعمل ويتحرك.",
                        "افتح الـ Terminal وتأكد من أن العمليات (processes) الأساسية قيد التشغيل."
                    ]
                },
                "SMO_DISCONNECT": {
                    "title": "انقطاع الاتصال مع SMO",
                    "keywords": ["smo", "انقطاع", "اتصال", "ping", "فاصل"],
                    "steps": [
                        "تحقق من الاتصال الفيزيائي (الكابلات) بجهاز SMO.",
                        "قم بعمل Ping على عنوان IP الخاص بـ SMO للتأكد من وجود استجابة.",
                        "إذا لم يكن هناك استجابة، حاول إعادة تشغيل جهاز SMO."
                    ]
                }
            }
            save_data(predefined_procedures, file_path)
            return predefined_procedures
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_data(data, file_path):
    """دالة عامة لحفظ البيانات في أي ملف JSON."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- دوال الأوامر الأساسية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}! أنا <b>Zekoo v4.0</b>، مرشدك التقني التفاعلي.\n\n"
        f"<b>الأوامر المتاحة:</b>\n"
        f"<code>/search وصف_المشكلة</code> - للبحث الذكي عن حلول.\n"
        f"<code>/add_fault اسم_المحطة وصف_العطل كلمات_مفتاحية</code> - لتسجيل خبرة جديدة.\n"
        f"<code>/add_station ...</code> - لإضافة بيانات محطة.\n"
        f"<code>/update_status ...</code> - لتحديث حالة جهاز."
    )

async def add_station(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("خطأ.\nمثال: /add_station Attaba ATA SMO=10.1.29.20")
        return

    station_name, short_name, *device_args = args
    data = load_data(STATIONS_DATA_FILE)
    
    if station_name not in data:
        data[station_name] = {"short_name": short_name.upper(), "devices": {}, "history": []}

    for item in device_args:
        if '=' in item:
            device, ip = item.split('=', 1)
            data[station_name]["devices"][device.upper()] = {"ip": ip, "status": "غير معروف"}
    
    save_data(data, STATIONS_DATA_FILE)
    await update.message.reply_text(f"تم إضافة/تحديث بيانات محطة '{station_name}' بنجاح.")

async def add_fault(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("خطأ.\nمثال: /add_fault Attaba مشكلة في SMO انقطاع,تهنيج")
        return
    
    station_name = args[0]
    keywords = args[-1].split(',')
    fault_description = " ".join(args[1:-1])
    
    data = load_data(STATIONS_DATA_FILE)
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
    save_data(data, STATIONS_DATA_FILE)
    await update.message.reply_text(f"تم تسجيل العطل كخبرة جديدة في سجل محطة '{station_name}'.")

async def update_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) != 3:
        await update.message.reply_text("خطأ.\nمثال: /update_status Attaba SMO يعمل")
        return
        
    station_name, device_name, status = args
    data = load_data(STATIONS_DATA_FILE)
    if station_name in data and device_name.upper() in data[station_name]["devices"]:
        data[station_name]["devices"][device_name.upper()]["status"] = status
        save_data(data, STATIONS_DATA_FILE)
        await update.message.reply_text(f"تم تحديث حالة جهاز {device_name.upper()} في محطة {station_name} إلى '{status}'.")
    else:
        await update.message.reply_text("خطأ: المحطة أو الجهاز غير موجود.")

# --- محرك البحث الذكي والمطور ---

async def search_in_kb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.message.from_user.first_name
    search_query = " ".join(context.args)
    if not search_query:
        await update.message.reply_text("الرجاء كتابة وصف للمشكلة بعد الأمر /search.")
        return

    await update.message.reply_text(f"أهلاً بك يا {user_name}. لحظات من فضلك، أبحث في قواعد المعرفة عن أفضل حل...")

    # تحميل كل قواعد البيانات المتاحة
    stations_history = load_data(STATIONS_DATA_FILE)
    procedures = load_data(PROCEDURES_FILE)

    # تحويل البيانات إلى نص لـ Gemini
    history_context = json.dumps(stations_history, ensure_ascii=False, indent=2)
    procedures_context = json.dumps(procedures, ensure_ascii=False, indent=2)

    prompt = f"""
    أنت "المرشد الخبير Zekoo"، مساعد تقني ذكي ومحلل بيانات. مهمتك هي مساعدة المهندس "{user_name}" في حل مشكلة تقنية.

    **سؤال المهندس:**
    "{search_query}"

    **لديك مصدران للمعلومات:**
    1.  **قاعدة الإجراءات القياسية (Procedures):** تحتوي على حلول جاهزة وموثوقة لمشاكل شائعة.
    2.  **سجل الأعطال التاريخي (History):** يحتوي على خبرات سابقة سجلها الفريق.

    **قاعدة الإجراءات القياسية المتاحة لك:**
    ```json
    {procedures_context}
    ```

    **سجل الأعطال التاريخي المتاح لك:**
    ```json
    {history_context}
    ```

    **مهمتك المطلوبة بدقة (اتبع هذا الترتيب):**
    1.  **الأولوية للإجراءات القياسية:** أولاً، تحقق إذا كان سؤال المهندس يتطابق مع أي مشكلة في "قاعدة الإجراءات القياسية" بناءً على العنوان أو الكلمات المفتاحية (keywords).
    2.  **إذا وجدت إجراءً مطابقاً:**
        *   يجب أن يكون ردك هو الإجراء القياسي فقط.
        *   ابدأ ردك بالعبارة التالية بالضبط: "حسناً يا {user_name}، بناءً على قاعدة الإجراءات المعتمدة، هذه المشكلة لها حل قياسي."
        *   ثم اعرض عنوان الإجراء وخطواته بشكل واضح ومرقم. لا تضف أي معلومات من سجل الأعطال.
    3.  **إذا لم تجد أي إجراء مطابق:**
        *   انتقل إلى تحليل "سجل الأعطال التاريخي".
        *   ابحث عن أعطال مشابهة في السجل بناءً على الوصف والكلمات المفتاحية.
        *   ابدأ ردك بالعبارة التالية بالضبط: "حسناً يا {user_name}، لم أجد إجراءً قياسياً لهذه المشكلة، ولكن بناءً على الخبرات السابقة، إليك التحليل:"
        *   لخص أهم عطل سابق مشابه والحلول التي تم استنتاجها.

    **تنسيق الرد يجب أن يكون احترافياً وواضحاً.**
    """

    if not model:
        await update.message.reply_text("عذراً، خدمة الذكاء الاصطناعي Gemini غير متاحة.")
        return
        
    try:
        request_options = {"timeout": 120}
        response = await model.generate_content_async(prompt, request_options=request_options)
        ai_response = response.text
    except Exception as e:
        await update.message.reply_text(f"عذراً، واجهت خطأ أثناء التحليل. الخطأ: {e}")
        return

    await update.message.reply_text(ai_response)

def main() -> None:
    """الدالة الرئيسية لتشغيل البوت."""
    # التأكد من إنشاء ملف الإجراءات عند بدء التشغيل
    load_data(PROCEDURES_FILE)
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_station", add_station))
    application.add_handler(CommandHandler("add_fault", add_fault))
    application.add_handler(CommandHandler("update_status", update_status))
    application.add_handler(CommandHandler("search", search_in_kb))
    
    print("Zekoo v4.0 (المرشد الخبير) قيد التشغيل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

