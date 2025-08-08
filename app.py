# -*- coding: utf-8 -*-

import logging
import datetime
import os
import json
import re

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- مكتبة جوجل ---
import google.generativeai as genai

# --- الإعدادات الرئيسية (معلوماتك الخاصة) ---
TELEGRAM_TOKEN = "7986947716:AAHo-wdAuVo7LLGo21s-B6Cedowe3agevwc"
GEMINI_API_KEY = "AIzaSyDP8yA4S8rDSFsYEpzKuDbo-0IDNmZXxYA"

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

# --- دوال البوت ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}! أنا <b>Zekoo v6.2</b>، مساعدك الذكي.\n\n"
        f"<b>الأوامر الأساسية:</b>\n\n"
        f"<code>/list_stations</code> - لعرض كل المحطات المسجلة.\n"
        f"<code>/add [بيانات]</code> - لإضافة/تحديث بيانات محطة أو جهاز.\n"
        f"<code>/log [وصف]</code> - لتسجيل عطل أو معلومة.\n"
        f"<code>/search [وصف]</code> - للبحث الذكي عن حلول."
    )

async def list_stations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يعرض قائمة بجميع المحطات المسجلة واختصاراتها."""
    data = load_data()
    if not data:
        await update.message.reply_text("لا توجد أي محطات مسجلة في قاعدة البيانات حتى الآن.")
        return

    message = "<b>قائمة المحطات المسجلة في النظام:</b>\n\n"
    # فرز المحطات أبجدياً حسب الاختصار لسهولة القراءة
    sorted_stations = sorted(data.items())
    
    for station_key, station_info in sorted_stations:
        full_name = station_info.get('full_name', 'N/A')
        device_count = len(station_info.get('devices', {}))
        history_count = len(station_info.get('history', []))
        
        message += f"• <b>{full_name} ({station_key})</b>\n"
        message += f"  <pre>  - الأجهزة: {device_count}</pre>\n"
        message += f"  <pre>  - سجل الأعطال: {history_count}</pre>\n\n"
        
    await update.message.reply_html(message)


async def add_or_update_station_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر ذكي لإضافة أو تحديث بيانات المحطات والأجهزة باستخدام صيغة key=value."""
    text_data = " ".join(context.args)
    if not text_data:
        await update.message.reply_text("خطأ: الرجاء إدخال البيانات بعد الأمر /add.")
        return

    await update.message.reply_text("جاري تحليل البيانات. لحظات من فضلك...")

    data = load_data()
    lines = [line.strip() for line in re.split(r'\n', text_data) if line.strip()]
    
    try:
        first_line_parts = lines[0].split()
        station_key = first_line_parts[-1].upper()
        full_name = " ".join(first_line_parts[:-1])

        if station_key not in data:
            if not full_name:
                await update.message.reply_text(f"خطأ: المحطة '{station_key}' غير موجودة. لإنشائها، اكتب الاسم الكامل ثم الاختصار.")
                return
            data[station_key] = {"full_name": full_name, "devices": {}, "history": []}
            message = f"تم إنشاء محطة جديدة: {full_name} ({station_key}).\n"
        else:
            if full_name:
                data[station_key]["full_name"] = full_name
            message = f"تحديث بيانات محطة: {station_key}.\n"

        devices_updated_messages = []
        for line in lines[1:]:
            parts = line.split()
            device_name = parts[0].upper()
            
            if device_name not in data[station_key]["devices"]:
                data[station_key]["devices"][device_name] = {"status": "غير معروف", "details": {}}
            
            if "details" not in data[station_key]["devices"][device_name]:
                 data[station_key]["devices"][device_name]["details"] = {}

            details_to_add = parts[1:]
            device_message = f"- الجهاز {device_name}:\n"
            for detail in details_to_add:
                if '=' in detail:
                    key, value = detail.split('=', 1)
                    value = value.strip('"')
                    data[station_key]["devices"][device_name]["details"][key.lower()] = value
                    device_message += f"  - تم تحديث/إضافة: {key.lower()}.\n"
            devices_updated_messages.append(device_message)

        if devices_updated_messages:
            message += "\n".join(devices_updated_messages)
        
        save_data(data)
        await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء معالجة البيانات. تأكد من أن التنسيق صحيح.\nالخطأ: {e}")


async def log_natural_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.message.from_user.first_name
    natural_text = " ".join(context.args)
    if not natural_text:
        await update.message.reply_text("الرجاء كتابة وصف للمعلومة بعد الأمر /log.")
        return
    await update.message.reply_text("فهمت. لحظات من فضلك، أقوم بتحليل وتخزين المعلومة...")
    data = load_data()
    stations_structure = json.dumps(list(data.keys()), ensure_ascii=False)
    prompt = f"""
    أنت مساعد ذكي ومحلل بيانات، مهمتك هي تحليل النص التالي الذي كتبه المهندس "{user_name}" وتحويله إلى بيانات منظمة.
    **النص المكتوب من المهندس:** "{natural_text}"
    **قائمة اختصارات المحطات الموجودة حالياً في قاعدة البيانات:** {stations_structure}
    **مهمتك المطلوبة:**
    1. **اقرأ النص بعناية شديدة.** ابحث عن أي كلمة قد تشير إلى اختصار محطة من القائمة المتوفرة لك.
    2. **حدد اختصار المحطة:** ابذل قصارى جهدك لتحديد اختصار المحطة.
    3. **استخرج وصفاً دقيقاً للعطل** أو المعلومة.
    4. **استخرج الحل** إذا تم ذكره في النص.
    5. **استخرج كلمات مفتاحية** (keywords) تصف المشكلة.
    6. **قم بإنشاء كائن JSON** بالنسق التالي:
    ```json
    {{
      "station_key": "اختصار المحطة الذي استطعت تحديده",
      "fault_description": "وصف العطل",
      "solution": "الحل (إن وجد)",
      "keywords": ["كلمة1", "كلمة2"]
    }}
    ```
    **ملاحظات هامة:**
    * إذا لم تتمكن بشكل مؤكد من تحديد أي اختصار محطة، يجب أن تكون قيمة `station_key` في الـ JSON هي `null`.
    * يجب أن يكون ردك هو كائن الـ JSON فقط.
    """
    if not model:
        await update.message.reply_text("عذراً، خدمة الذكاء الاصطناعي Gemini غير متاحة.")
        return
    try:
        response = await model.generate_content_async(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        info_json = json.loads(cleaned_response)
        station_key = info_json.get("station_key")
        if not station_key:
            await update.message.reply_text(f"عذراً يا {user_name}، لم أستطع تحديد اختصار المحطة في رسالتك. الرجاء ذكر اختصار المحطة بوضوح (مثل: ATA, Rod, KIT).")
            return
        if station_key not in data:
            await update.message.reply_text(f"خطأ: المحطة بالاختصار '{station_key}' غير موجودة.")
            return
        fault_record = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": user_name,
            "description": info_json.get("fault_description", ""),
            "solution": info_json.get("solution", ""),
            "keywords": info_json.get("keywords", [])
        }
        if "history" not in data[station_key]:
            data[station_key]["history"] = []
        data[station_key]["history"].append(fault_record)
        await update.message.reply_text(f"تم تسجيل المعلومة بنجاح في سجل محطة '{station_key}'. شكراً لك!")
    except Exception as e:
        await update.message.reply_text(f"عذراً، واجهت خطأ. الخطأ: {e}")


async def search_in_kb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.message.from_user.first_name
    search_query = " ".join(context.args)
    if not search_query:
        await update.message.reply_text("الرجاء كتابة وصف للمشكلة بعد الأمر /search.")
        return
    await update.message.reply_text(f"أهلاً بك يا {user_name}. لحظات من فضلك، أقوم بتحليل البيانات لأجد لك أفضل حل...")
    data = load_data()
    full_context = json.dumps(data, ensure_ascii=False, indent=2)
    prompt = f"""
    أنت "كبير المهندسين Zekoo"، مساعد تقني خبير. مهمتك هي مساعدة المهندس "{user_name}" في حل مشكلة.
    **سؤال المهندس:** "{search_query}"
    **قاعدة البيانات الكاملة المتاحة لك:**
    ```json
    {full_context}
    ```
    **مهمتك المطلوبة:**
    1. **فهم السؤال:** حلل سؤال المهندس. حدد اسم/اختصار المحطة والأجهزة المذكورة.
    2. **استخراج البيانات الفنية:** إذا حددت محطة وجهازاً، **يجب عليك استخراج وعرض كل التفاصيل (`details`) المتعلقة بهما مباشرة من قاعدة البيانات**. هذا يشمل الـ IP، اسم المستخدم، كلمة المرور، وأي تفاصيل أخرى. لا تكتفِ بالإشارة لوجودها، بل اعرضها.
    3. **إيجاد الأعطال المشابهة:** ابحث في سجل الأعطال (`history`) عن مشاكل سابقة مشابهة.
    4. **صياغة الرد:** قم بصياغة رد احترافي ومنظم.
    **شروط تنسيق الرد:**
    * **الترحيب:** ابدأ بـ "أهلاً بك يا {user_name}، بصفتي كبير المهندسين، إليك خطة العمل:"
    * **البيانات الفنية:** تحت عنوان "**البيانات الفنية ذات الصلة:**"، اعرض بشكل مباشر أي تفاصيل وجدتها.
    * **تاريخ الأعطال:** تحت عنوان "**تاريخ الأعطال المشابهة:**"، اذكر الأعطال السابقة.
    * **خطة العمل:** قدم الحل النهائي في خطوات مرقمة وواضحة.
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
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list_stations", list_stations)) # الأمر الجديد
    application.add_handler(CommandHandler("add", add_or_update_station_data))
    application.add_handler(CommandHandler("log", log_natural_language))
    application.add_handler(CommandHandler("search", search_in_kb))
    
    print("Zekoo v6.2 (المساعد الخبير) قيد التشغيل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
