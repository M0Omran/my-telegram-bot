# -*- coding: utf-8 -*-

import logging
import datetime
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- مكتبة جوجل ---
import google.generativeai as genai

# --- الإعدادات الرئيسية ---

# !! هام: استبدل ++++ بالـ Token الخاص ببوتك
TELEGRAM_TOKEN = "7986947716:AAHo-wdAuVo7LLGo21s-B6Cedowe3agevwc" 

# !! هام: استبدل ++++ بمفتاح Gemini API الصحيح
GEMINI_API_KEY = "AIzaSyAWbEECTpbWSaODdFWwiAY4hpmoraiJZWA"

# اسم ملف قاعدة المعرفة
KNOWLEDGE_BASE_FILE = "knowledge_base.txt"

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

# --- دوال البوت ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}! أنا البوت zekoo.\n"
        f"لتخزين معلومة، أرسل رسالة.\n"
        f"للبحث، استخدم: /search ثم وصف المشكلة."
    )

async def store_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    user_name = update.message.from_user.first_name
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{timestamp}] - {user_name}: {user_text}\n"
    
    print(f"تم استلام رسالة للحفظ: {user_text}")
    try:
        with open(KNOWLEDGE_BASE_FILE, "a", encoding="utf-8") as f:
            f.write(formatted_message)
        await update.message.reply_text("شكراً لك! تم حفظ المعلومة.")
    except Exception as e:
        print(f"خطأ في الحفظ: {e}")
        await update.message.reply_text("عذراً، خطأ في حفظ المعلومة.")

async def search_in_kb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # --- التعديل الأول: الحصول على اسم المستخدم ---
    user_name = update.message.from_user.first_name

    search_terms = context.args
    if not search_terms:
        await update.message.reply_text("مثال: /search مشكلة انقطاع الانترنت")
        return

    search_query = " ".join(search_terms)
    print(f"بدء البحث عن: {search_query} بواسطة {user_name}")
    await update.message.reply_text(f"جاري البحث والتفكير في حل لمشكلة: '{search_query}'...")

    try:
        with open(KNOWLEDGE_BASE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        await update.message.reply_text("قاعدة المعرفة فارغة.")
        return

    search_keywords = search_query.lower().split()
    results = [line.strip() for line in lines if any(keyword in line.lower() for keyword in search_keywords)]
    
    if not results:
        await update.message.reply_text(f"عذراً، لم أجد معلومات أولية متعلقة بـ '{search_query}'.")
        return

    context_for_ai = "\n".join(results[:15])

    # --- التعديل الثاني: تحديث الـ prompt بالعبارة التمهيدية الجديدة ---
    prompt = f"""
    أنت مهندس خبير ومساعد تقني. مهمتك هي تحليل البيانات المتوفرة من تجارب سابقة وتحويلها إلى دليل خطوات واضح لحل المشاكل.
    زميلك، واسمه "{user_name}"، يسأل عن المشكلة التالية: "{search_query}"

    وهذه هي البيانات والخبرات السابقة التي وجدتها في قاعدة المعرفة المتعلقة بالمشكلة:
    ---
    {context_for_ai}
    ---

    بناءً على ما سبق، قم بالآتي بدقة:
    1.  اقرأ كل البيانات السابقة وحللها بعمق.
    2.  استخلص كل الحلول والإجراءات المقترحة من البيانات.
    3.  قم بدمج الأفكار المتشابهة وتجاهل المعلومات غير المهمة.
    4.  **ابدأ إجابتك بالعبارة التمهيدية التالية بالضبط: "أهلاً بك يا {user_name}، سوف نحاول حل العطل معاً. بناءً على تحليل البيانات، إليك الخطوات المقترحة:"**
    5.  **بعد العبارة التمهيدية، قم بتنظيم الخلاصة النهائية على هيئة قائمة خطوات مرقمة وواضحة (1, 2, 3...).**
    6.  يجب أن تكون كل خطوة عملية ومباشرة. (مثال: "1. قم بفحص كابلات الشبكة.")
    7.  إذا كانت البيانات تشير إلى عدة حلول محتملة، قم بترتيبها في القائمة حسب الأهمية أو الأولوية.
    """

    print("إرسال الطلب إلى Gemini للتحليل...")
    if not model:
        await update.message.reply_text("عذراً، خدمة الذكاء الاصطناعي Gemini غير متاحة.")
        return
        
    try:
        request_options = {"timeout": 90}
        response = await model.generate_content_async(
            prompt,
            request_options=request_options
        )
        ai_response = response.text
        print("تم استلام رد ذكي من Gemini.")
    except Exception as e:
        print(f"حدث خطأ أثناء التواصل مع Gemini API: {e}")
        await update.message.reply_text(f"عذراً، واجهت خطأ أثناء محاولة التفكير في حل. الخطأ: {e}")
        return

    await update.message.reply_text(ai_response)

def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search_in_kb))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, store_message))
    print("البوت قيد التشغيل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
