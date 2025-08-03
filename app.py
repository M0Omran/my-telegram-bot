# -*- coding: utf-8 -*-

import logging
import datetime
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- مكتبة جوجل ---
import google.generativeai as genai

# --- الإعدادات الرئيسية (المفاتيح مكتوبة مباشرة هنا) ---

# مفتاح التليجرام الخاص بك
TELEGRAM_TOKEN = "7986947716:AAHo-wdAuVo7LLGo21s-B6Cedowe3agevwc" 

# مفتاح Gemini API الجديد والصحيح
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
        f"مرحباً {user.mention_html()}! أنا البوت zekoo (الإصدار النهائي).\n"
        f"لتخزين معلومة جديدة، أرسل رسالة.\n"
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
    search_terms = context.args
    if not search_terms:
        await update.message.reply_text("مثال: /search مشكلة انقطاع الانترنت")
        return

    search_query = " ".join(search_terms)
    print(f"بدء البحث عن: {search_query}")
    await update.message.reply_text(f"جاري البحث والتفكير (باستخدام Gemini) في حل لمشكلة: '{search_query}'...")

    try:
        with open(KNOWLEDGE_BASE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        # سنقوم بإنشاء الملف إذا لم يكن موجوداً
        with open(KNOWLEDGE_BASE_FILE, "w", encoding="utf-8") as f:
            pass
        await update.message.reply_text("قاعدة المعرفة كانت فارغة، تم إنشاؤها الآن. قم بإضافة بعض المعلومات أولاً.")
        return

    search_keywords = search_query.lower().split()
    results = [line.strip() for line in lines if any(keyword in line.lower() for keyword in search_keywords)]
    
    if not results:
        await update.message.reply_text(f"عذراً، لم أجد أي معلومات أولية متعلقة بـ '{search_query}'.")
        return

    context_for_ai = "\n".join(results[:15])

    prompt = f"""
    أنت خبير فني متخصص في حل المشاكل ضمن فريق عمل. مهمتك هي مساعدة زملائك.
    زميلك يسأل عن المشكلة التالية: "{search_query}"

    وهذه هي البيانات والخبرات السابقة التي وجدتها في قاعدة المعرفة المتعلقة بالمشكلة:
    ---
    {context_for_ai}
    ---

    بناءً على ما سبق، قم بالآتي:
    1.  حلل المشكلة والبيانات المتوفرة.
    2.  استخلص الحلول أو الخطوات المقترحة الأكثر صلة.
    3.  أعد صياغة الإجابة النهائية في فقرة أو عدة نقاط واضحة وموجزة باللغة العربية.
    4.  اجعل إجابتك مباشرة وموجهة للمستخدم. ابدأ بعبارة مثل "بناءً على الخبرات السابقة..." أو "إليك ملخص الحلول المقترحة...".
    5.  إذا كانت البيانات غير كافية، اذكر ذلك واقترح حلاً عاماً إن أمكن.
    """

    print("إرسال الطلب إلى Gemini للتحليل...")
    if not model:
        await update.message.reply_text("عذراً، خدمة الذكاء الاصطناعي Gemini غير متاحة بسبب خطأ في الإعداد.")
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
    """بدء تشغيل البوت."""
    if not model:
        print("لا يمكن تشغيل البوت بسبب فشل إعداد النموذج.")
        return
            
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search_in_kb))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, store_message))

    print("البوت قيد التشغيل (بمحرك Gemini النهائي)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()