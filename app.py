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
PROCEDURES_FILE = "procedures.json" # الملف الجديد

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
def load_json_file(file_path):
    """دالة عامة لتحميل البيانات من أي ملف JSON."""
    if not os.path.exists(file_path): return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}

def save_json_file(data, file_path):
    """دالة عامة لحفظ البيانات في أي ملف JSON."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- دوال البوت ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}! أنا <b>Zekoo v7.0</b>، مساعدك الخبير.\n\n"
        f"أنا الآن أستخدم قاعدة معرفة للإجراءات القياسية بالإضافة إلى سجل الأعطال.\n\n"
        f"<b>الأوامر الأساسية:</b>\n"
        f"<code>/list_stations</code> - لعرض كل المحطات.\n"
        f"<code>/add [بيانات]</code> - لإضافة/تحديث بيانات.\n"

        f"<code>/log [وصف]</code> - لتسجيل عطل تاريخي.\n"
        f"<code>/search [وصف]</code> - للبحث الذكي عن حلول."
    )

async def list_stations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_json_file(STATIONS_DATA_FILE)
    if not data:
        await update.message.reply_text("لا توجد أي محطات مسجلة.")
        return
    message = "<b>قائمة المحطات المسجلة:</b>\n\n"
    sorted_stations = sorted(data.items())
    for station_key, station_info in sorted_stations:
        full_name = station_info.get('full_name', 'N/A')
        message += f"• <b>{full_name} ({station_key})</b>\n"
    await update.message.reply_html(message)


async def add_or_update_station_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text_data = " ".join(context.args)
    if not text_data:
        await update.message.reply_text("خطأ: الرجاء إدخال البيانات بعد الأمر /add.")
        return
    await update.message.reply_text("جاري تحليل البيانات...")
    data = load_json_file(STATIONS_DATA_FILE)
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
            if full_name: data[station_key]["full_name"] = full_name
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
        save_json_file(data, STATIONS_DATA_FILE)
        await update.message.reply_text(message)
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ. تأكد من التنسيق.\nالخطأ: {e}")


async def log_natural_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # No changes to this function
    user_name = update.message.from_user.first_name
    natural_text = " ".join(context.args)
    if not natural_text:
        await update.message.reply_text("الرجاء كتابة وصف للمعلومة بعد الأمر /log.")
        return
    await update.message.reply_text("فهمت. لحظات من فضلك، أقوم بتحليل وتخزين المعلومة...")
    data = load_json_file(STATIONS_DATA_FILE)
    stations_structure = json.dumps(list(data.keys()), ensure_ascii=False)
    prompt = f"""Analyze the following text from engineer "{user_name}" and convert it to structured JSON.
    Text: "{natural_text}"
    Available station keys: {stations_structure}
    Task:
    1. Identify the station key from the text. It must be one of the available keys.
    2. Extract a precise fault description.
    3. Extract the solution if mentioned.
    4. Extract relevant keywords.
    5. Create a JSON object in this exact format:
    ```json
    {{
      "station_key": "The identified station key",
      "fault_description": "The extracted description",
      "solution": "The solution, if any",
      "keywords": ["keyword1", "keyword2"]
    }}
    ```
    If you cannot reliably identify a station key, the value for "station_key" in the JSON must be null. Your response must be only the JSON object.
    """
    if not model:
        await update.message.reply_text("Gemini AI service is unavailable.")
        return
    try:
        response = await model.generate_content_async(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        info_json = json.loads(cleaned_response)
        station_key = info_json.get("station_key")
        if not station_key:
            await update.message.reply_text(f"Sorry {user_name}, I couldn't identify a station key in your message. Please state it clearly (e.g., ATA, Rod).")
            return
        if station_key not in data:
            await update.message.reply_text(f"Error: Station key '{station_key}' not found in the database.")
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
        save_json_file(data, STATIONS_DATA_FILE)
        await update.message.reply_text(f"Successfully logged the information in station '{station_key}'.")
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")


async def search_in_kb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search function now prioritizes standard procedures."""
    user_name = update.message.from_user.first_name
    search_query = " ".join(context.args)
    if not search_query:
        await update.message.reply_text("Please provide a problem description after /search.")
        return

    await update.message.reply_text(f"Hello {user_name}. Please wait while I consult the knowledge base...")

    stations_data = load_json_file(STATIONS_DATA_FILE)
    procedures_data = load_json_file(PROCEDURES_FILE)
    
    stations_context = json.dumps(stations_data, ensure_ascii=False, indent=2)
    procedures_context = json.dumps(procedures_data, ensure_ascii=False, indent=2)

    # The new, smarter prompt
    prompt = f"""
    You are "Zekoo, the Expert Engineer", an AI technical assistant. Your task is to help engineer "{user_name}" solve a technical problem.

    **Engineer's Query:**
    "{search_query}"

    **You have two sources of information:**
    1.  **Standard Procedures (`procedures.json`):** This is your primary source. It contains official, verified solutions for common, critical problems.
    2.  **Historical Faults (`stations_data.json`):** This contains past experiences logged by the team.

    **Available Standard Procedures:**
    ```json
    {procedures_context}
    ```

    **Available Historical Faults:**
    ```json
    {stations_context}
    ```

    **Your Mission (Follow this order strictly):**
    1.  **PRIORITY 1: CHECK PROCEDURES:** First, analyze the user's query and check if it matches any problem in the **Standard Procedures** based on the title or keywords.
    2.  **IF A PROCEDURE MATCHES:**
        *   Your response MUST start with: "Based on the standard knowledge base, this problem has an official procedure."
        *   Then, present the procedure's title and its steps clearly and in order.
        *   **DO NOT** mention or use any information from the historical faults. Your response should only be the standard procedure.
    3.  **IF NO PROCEDURE MATCHES:**
        *   Then, and only then, proceed to analyze the **Historical Faults**.
        *   Your response MUST start with: "No standard procedure was found for this issue. However, based on past experiences, here is an analysis:"
        *   Search the history for similar faults.
        *   Provide a summary of the most relevant past fault and the solution that was applied.
        *   Extract and display any relevant technical data (like IPs) for the devices involved.

    **Format your response professionally and clearly.**
    """

    if not model:
        await update.message.reply_text("Gemini AI service is unavailable.")
        return
        
    try:
        request_options = {"timeout": 120}
        response = await model.generate_content_async(prompt, request_options=request_options)
        ai_response = response.text
    except Exception as e:
        await update.message.reply_text(f"An error occurred during analysis: {e}")
        return

    await update.message.reply_text(ai_response)


def main() -> None:
    # Ensure procedures file is loaded at start
    load_json_file(PROCEDURES_FILE)
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list_stations", list_stations))
    application.add_handler(CommandHandler("add", add_or_update_station_data))
    application.add_handler(CommandHandler("log", log_natural_language))
    application.add_handler(CommandHandler("search", search_in_kb))
    
    print("Zekoo v7.0 (Knowledge Base Expert) is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
