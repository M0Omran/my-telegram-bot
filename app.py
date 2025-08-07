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

# --- الإعدادات الرئيسية ---
# !!! تأكد من وضع التوكن والمفتاح الصحيحين هنا !!!
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
        f"مرحباً {user.mention_html()}! أنا <b>Zekoo v4.0</b>، مساعدك الذكي.\n\n"
        f"<b>أنا أفهم اللغة الطبيعية!</b>\n\n"
        f"<b>لتسجيل أي معلومة (عطل، حل، تحديث):</b>\n"
        f"استخدم أمر <code>/log</code> ثم اكتب ما تريد باللغة العامية أو الفصحى.\n"
        f"<b>مثال:</b> <code>/log النهاردة في محطة العتبة، جهاز SMO كان فاصل تماماً. الحل كان تغيير كابل الباور.</code>\n\n"
        f"<b>للبحث الذكي:</b>\n"
        f"<code>/search وصف المشكلة</code>"
    )

async def log_natural_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يستخدم الذكاء الاصطناعي لتحليل مدخلات اللغة الطبيعية وتحديث قاعدة البيانات."""
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

    **قائمة المحطات الموجودة حالياً في قاعدة البيانات:**
    {stations_structure}

    **مهمتك المطلوبة:**
    1.  **اقرأ النص بعناية.**
    2.  **حدد اسم المحطة** التي يتحدث عنها النص. يجب أن يكون الاسم من ضمن قائمة المحطات الموجودة.
    3.  **استخرج وصفاً دقيقاً للعطل** أو المعلومة.
    4.  **استخرج الحل** إذا تم ذكره في النص.
    5.  **استخرج كلمات مفتاحية** (keywords) تصف المشكلة (مثل: انقطاع, تهنيج, حرارة, SMO, FEB1).
    6.  **قم بإنشاء كائن JSON** يحتوي على هذه المعلومات بالنسق التالي بالضبط. إذا لم تجد معلومة ما، اترك قيمتها فارغة (مثال: "solution": "").

    **نسق الـ JSON المطلوب (مهم جداً):**
    ```json
    {{
      "station_name": "اسم المحطة الذي حددته",
      "fault_description": "وصف العطل الذي استخرجته",
      "solution": "الحل الذي تم اتخاذه (إن وجد)",
      "keywords": ["كلمة1", "كلمة2", "كلمة3"]
    }}
    ```

    **ملاحظات هامة:**
    *   إذا لم تستطع تحديد اسم المحطة من النص، أو إذا كانت المحطة غير موجودة في القائمة، يجب أن يكون الرد هو كلمة "Error: Station not found" فقط لا غير.
    *   يجب أن يكون ردك هو كائن الـ JSON فقط، بدون أي نصوص إضافية قبله أو بعده.
    """

    if not model:
        await update.message.reply_text("عذراً، خدمة الذكاء الاصطناعي Gemini غير متاحة.")
        return

    try:
        response = await model.generate_content_async(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        
        if "Error: Station not found" in cleaned_response:
            await update.message.reply_text(f"عذراً يا {user_name}، لم أستطع تحديد اسم المحطة في رسالتك أو أن المحطة غير مسجلة. الرجاء ذكر اسم المحطة بوضوح (مثال: محطة العتبة).")
            return

        info_json = json.loads(cleaned_response)
        station_name = info_json.get("station_name")

        if station_name not in data:
            await update.message.reply_text(f"خطأ: المحطة '{station_name}' التي تم تحديدها غير موجودة في قاعدة البيانات.")
            return

        fault_record = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": user_name,
            "description": info_json.get("fault_description", ""),
            "solution": info_json.get("solution", ""),
            "keywords": info_json.get("keywords", [])
        }

        if "history" not in data[station_name]:
            data[station_name]["history"] = []
            
        data[station_name]["history"].append(fault_record)
        save_data(data)
        await update.message.reply_text(f"تم تسجيل المعلومة بنجاح في سجل محطة '{station_name}'. شكراً لك!")

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

    prompt = f"""
    أنت "كبير المهندسين Zekoo"، مساعد تقني خبير ومحلل بيانات. مهمتك هي مساعدة المهندس "{user_name}" في حل مشكلة تقنية.

    **سؤال المهندس:**
    "{search_query}"

    **قاعدة البيانات الكاملة المتاحة لك (بتنسيق JSON):**
    ```json
    {full_context}
    ```

    **مهمتك المطلوبة بدقة:**
    1.  **تحليل عميق:** اقرأ سؤال المهندس بعناية. ثم ابحث في قاعدة البيانات الكاملة عن أي معلومات ذات صلة.
    2.  **إيجاد الأعطال المشابهة:** ركز على إيجاد الأعطال السابقة التي تتشابه مع المشكلة الحالية بناءً على **وصف العطل والحلول والكلمات المفتاحية (keywords)**.
    3.  **صياغة الرد:** قم بصياغة رد احترافي ومنظم.

    **شروط تنسيق الرد النهائي (مهم جداً):**
    *   **الترحيب:** ابدأ ردك بالعبارة التالية بالضبط: "أهلاً بك يا {user_name}، بصفتي كبير المهندسين، قمت بتحليل الموقف وإليك خطة العمل المقترحة:"
    *   **التحليل المبدئي:** في فقرة قصيرة، اذكر تشخيصك المبدئي للمشكلة.
    *   **الأعطال السابقة ذات الصلة:** إذا وجدت أعطالاً سابقة مشابهة، اذكرها بإيجاز تحت عنوان "**تاريخ الأعطال المشابهة:**".
    *   **البيانات الفنية:** إذا كان الحل يتطلب معرفة IP أو حالة جهاز، اذكرها تحت عنوان "**البيانات الفنية المطلوبة:**".
    *   **خطة العمل:** قدم الحل النهائي على هيئة **خطوات مرقمة وواضحة** تحت عنوان "**خطة العمل المقترحة:**".

    إذا لم تجد أي معلومات مفيدة، اعتذر وقدم نصيحة عامة.
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
    application.add_handler(CommandHandler("log", log_natural_language)) # الأمر الجديد والذكي
    application.add_handler(CommandHandler("search", search_in_kb))
    
    print("Zekoo v4.0 (المساعد الذكي) قيد التشغيل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
