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
        f"مرحباً {user.mention_html()}! أنا <b>Zekoo v5.1</b>، مساعدك الذكي.\n\n"
        f"<b>الأوامر الأساسية:</b>\n\n"
        f"<b>لإضافة أو تحديث بيانات محطة/جهاز:</b>\n"
        f"<code>/add [بيانات المحطة أو الجهاز]</code>\n"
        f"مثال: <code>/add Heliopolis HEL\nSMO 10.5.1.20</code>\n\n"
        f"<b>لتسجيل عطل أو معلومة:</b>\n"
        f"<code>/log [وصف العطل باللغة الطبيعية]</code>\n\n"
        f"<b>للبحث الذكي:</b>\n"
        f"<code>/search [وصف المشكلة]</code>"
    )

async def add_or_update_station_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر ذكي لإضافة أو تحديث بيانات المحطات والأجهزة."""
    text_data = " ".join(context.args)
    if not text_data:
        await update.message.reply_text("خطأ: الرجاء إدخال البيانات بعد الأمر /add.")
        return

    await update.message.reply_text("جاري تحليل البيانات. لحظات من فضلك...")

    data = load_data()
    
    lines = [line.strip() for line in re.split(r'\n', text_data) if line.strip()]
    
    try:
        first_line_parts = lines[0].split()
        
        if len(first_line_parts) >= 2:
            station_key = first_line_parts[-1].upper()
            full_name = " ".join(first_line_parts[:-1])
            
            if station_key not in data:
                data[station_key] = {"full_name": full_name, "devices": {}, "history": []}
                message = f"تم إنشاء محطة جديدة: {full_name} ({station_key}).\n"
            else:
                data[station_key]["full_name"] = full_name
                message = f"تم تحديث الاسم الكامل لمحطة: {station_key}.\n"
        
        else:
            station_key = first_line_parts[0].upper()
            if station_key not in data:
                await update.message.reply_text(f"خطأ: المحطة بالاختصار '{station_key}' غير موجودة. لإنشاء محطة جديدة، استخدم الصيغة: /add Full_Name KEY")
                return
            message = f"تحديث بيانات محطة: {station_key}.\n"

        devices_added = []
        for line in lines[1:]:
            device_parts = line.split()
            if len(device_parts) >= 2:
                device_name = device_parts[0].upper()
                ip_address = " ".join(device_parts[1:])
                data[station_key]["devices"][device_name] = {"ip": ip_address, "status": "غير معروف"}
                devices_added.append(f"- {device_name}: {ip_address}")

        if devices_added:
            message += "الأجهزة التي تم إضافتها/تحديثها:\n" + "\n".join(devices_added)
        
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

    **النص المكتوب من المهندس:**
    "{natural_text}"

    **قائمة اختصارات المحطات الموجودة حالياً في قاعدة البيانات:**
    {stations_structure}

    **مهمتك المطلوبة:**
    1.  **اقرأ النص بعناية.**
    2.  **حدد اختصار المحطة** التي يتحدث عنها النص. يجب أن يكون الاختصار من ضمن قائمة الاختصارات الموجودة (مثال: "Rod", "ATA", "RIN").
    3.  **استخرج وصفاً دقيقاً للعطل** أو المعلومة.
    4.  **استخرج الحل** إذا تم ذكره في النص.
    5.  **استخرج كلمات مفتاحية** (keywords) تصف المشكلة (مثل: انقطاع, تهنيج, حرارة, SMO, LSB).
    6.  **قم بإنشاء كائن JSON** يحتوي على هذه المعلومات بالنسق التالي بالضبط. إذا لم تجد معلومة ما، اترك قيمتها فارغة (مثال: "solution": "").

    **نسق الـ JSON المطلوب (مهم جداً):**
    ```json
    {{
      "station_key": "اختصار المحطة الذي حددته",
      "fault_description": "وصف العطل الذي استخرجته",
      "solution": "الحل الذي تم اتخاذه (إن وجد)",
      "keywords": ["كلمة1", "كلمة2", "كلمة3"]
    }}
    ```

    **ملاحظات هامة:**
    *   إذا لم تستطع تحديد اختصار المحطة من النص، أو إذا كان الاختصار غير موجود في القائمة، يجب أن يكون الرد هو كلمة "Error: Station not found" فقط لا غير.
    *   يجب أن يكون ردك هو كائن الـ JSON فقط، بدون أي نصوص إضافية قبله أو بعده.
    """

    if not model:
        await update.message.reply_text("عذراً، خدمة الذكاء الاصطناعي Gemini غير متاحة.")
        return

    try:
        response = await model.generate_content_async(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        
        if "Error: Station not found" in cleaned_response:
            await update.message.reply_text(f"عذراً يا {user_name}، لم أستطع تحديد اسم المحطة في رسالتك أو أن المحطة غير مسجلة. الرجاء ذكر اختصار المحطة بوضوح (مثال: محطة ATA).")
            return

        info_json = json.loads(cleaned_response)
        station_key = info_json.get("station_key")

        if station_key not in data:
            await update.message.reply_text(f"خطأ: المحطة بالاختصار '{station_key}' التي تم تحديدها غير موجودة في قاعدة البيانات.")
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

    except json.JSONDecodeError:
        await update.message.reply_text("عذراً، لم أتمكن من تحليل النص بشكل صحيح. حاول إعادة صياغة الجملة لتكون أوضح.")
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

    # --- Prompt المطور والنهائي ---
    prompt = f"""
    أنت "كبير المهندسين Zekoo"، مساعد تقني خبير ومحلل بيانات. مهمتك هي مساعدة المهندس "{user_name}" في حل مشكلة تقنية.

    **سؤال المهندس:**
    "{search_query}"

    **قاعدة البيانات الكاملة المتاحة لك (بتنسيق JSON):**
    ```json
    {full_context}
    ```

    **مهمتك المطلوبة بدقة:**
    1.  **فهم السؤال:** حلل سؤال المهندس بعناية. حاول تحديد اسم/اختصار المحطة (مثل Rod, ATA) وأسماء الأجهزة (مثل SMO, LSB) المذكورة في السؤال.
    2.  **استخراج البيانات الفنية:** إذا حددت محطة وجهازاً، **يجب عليك استخراج وعرض البيانات الفنية المتعلقة بهما مباشرة من قاعدة البيانات**. هذا يشمل **عنوان الـ IP** وحالة الجهاز (status). لا تكتفِ بالإشارة إلى وجودها، بل اعرضها.
    3.  **إيجاد الأعطال المشابهة:** ابحث في سجل الأعطال التاريخي (`history`) عن مشاكل سابقة تتشابه مع المشكلة الحالية بناءً على الوصف والكلمات المفتاحية.
    4.  **صياغة الرد:** قم بصياغة رد احترافي ومنظم.

    **شروط تنسيق الرد النهائي (مهم جداً):**
    *   **الترحيب:** ابدأ ردك بالعبارة التالية بالضبط: "أهلاً بك يا {user_name}، بصفتي كبير المهندسين، قمت بتحليل الموقف وإليك خطة العمل المقترحة:"
    *   **التحليل المبدئي:** في فقرة قصيرة، اذكر تشخيصك المبدئي للمشكلة.
    *   **البيانات الفنية ذات الصلة (الأهم):** تحت عنوان "**البيانات الفنية ذات الصلة:**"، **اعرض بشكل مباشر** أي عناوين IP أو بيانات أخرى وجدتها. مثال: "SMO (Rod): 10.32.109.20".
    *   **تاريخ الأعطال المشابهة:** إذا وجدت أعطالاً سابقة مشابهة، اذكرها بإيجاز تحت عنوان "**تاريخ الأعطال المشابهة:**".
    *   **خطة العمل:** قدم الحل النهائي على هيئة **خطوات مرقمة وواضحة** تحت عنوان "**خطة العمل المقترحة:**".

    إذا لم تجد أي معلومات مفيدة، اعتذر وقدم نصيحة عامة ولكن حاول دائماً تقديم أي معلومة فنية متاحة.
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
    application.add_handler(CommandHandler("add", add_or_update_station_data))
    application.add_handler(CommandHandler("log", log_natural_language))
    application.add_handler(CommandHandler("search", search_in_kb))
    
    print("Zekoo v5.1 (المساعد الذكي المطور) قيد التشغيل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
