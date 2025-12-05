from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
import os
from dotenv import load_dotenv
from pydub import AudioSegment
import io
# يجب استيراد gTTS لأن وظيفة convert_text_to_audio تعتمد عليها
from gtts import gTTS
# تم إزالة import requests و import import threading 
# لأن السيرفر لن يقوم بالاتصال بـ ESP32 (نموذج السحب/Pull)
import time 

# تحميل متغيرات البيئة
load_dotenv()

app = Flask(__name__)
CORS(app)

# ==========================================
# إعدادات OpenAI (النسخة الحديثة v1.0+)
# ==========================================
# تأكد من وجود OPENAI_API_KEY في ملف .env
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    print("⚠️ تحذير: لم يتم العثور على مفتاح OpenAI API")

# تهيئة عميل OpenAI
client = OpenAI(api_key=api_key)

# تخزين مؤقت للبيانات
# 'last_audio' هو الملف الصوتي الجاهز الذي ينتظر سحبه من قبل ESP32
esp32_data = {
    'last_audio': None, 
    'status': 'ready'
}

# ========== وظيفة تحويل الصوت لنص (Whisper) ==========
def convert_audio_to_text(audio_bytes):
    """تحويل ملف صوتي لنص باستخدام OpenAI Whisper (محدث للتعامل مع ملفات الذاكرة)"""
    try:
        print("🎤 جاري تحويل الصوت إلى نص (Whisper)...")
        
        # 1. إعداد الملف في الذاكرة (مهم: تحديد الاسم لتجنب خطأ الملف)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "input_audio.wav" 

        # 2. الاستدعاء باستخدام واجهة OpenAI الحديثة
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )
        
        text = transcript.text
        print(f"✅ النص المستخرج: {text}")
        return text
    except Exception as e:
        print(f"❌ خطأ في تحويل الصوت (Whisper): {e}")
        return None

# ========== وظيفة استدعاء ChatGPT ==========
def get_chatgpt_response(text):
    """الحصول على رد من ChatGPT (النسخة الحديثة)"""
    try:
        print("🤖 جاري إرسال للـ ChatGPT...")
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "أنت مساعد ذكي ومختصر جداً. ردودك قصيرة ومناسبة للمحادثة الصوتية."},
                {"role": "user", "content": text}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        reply = response.choices[0].message.content
        print(f"✅ رد ChatGPT: {reply}")
        return reply
    except Exception as e:
        print(f"❌ خطأ في ChatGPT: {e}")
        return None

# ========== وظيفة تحويل النص لصوت ==========
def convert_text_to_audio(text):
    """تحويل نص لملف صوتي باستخدام gTTS"""
    try:
        print("🔊 جاري تحويل النص إلى صوت...")
        
        # استخدام gTTS
        tts = gTTS(text=text, lang='ar', slow=False)
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        
        # تحويل من MP3 إلى WAV وتوحيد التردد
        audio = AudioSegment.from_file(mp3_fp, format="mp3")
        # توحيد لـ 16kHz أحادي القناة لضمان عمله على ESP32
        audio = audio.set_frame_rate(16000).set_channels(1) 
        
        wav_stream = io.BytesIO()
        audio.export(wav_stream, format="wav")
        wav_stream.seek(0)
        
        return wav_stream
    except Exception as e:
        print(f"❌ خطأ في تحويل الصوت: {e}")
        return None

# ========== Endpoint الرئيسي ==========
@app.route('/process-audio', methods=['POST'])
def process_audio():
    """استقبال الصوت من الويب ومعالجته"""
    try:
        print("\n" + "="*50)
        print("📥 استقبال طلب صوتي جديد")
        
        if 'audio' not in request.files:
            return jsonify({'error': 'لم يتم العثور على ملف صوتي'}), 400
        
        file = request.files['audio']
        raw_audio_data = file.read()
        
        # معالجة الملف الصوتي وتحويله إلى WAV (لضمان عمل Whisper)
        try:
            input_audio = AudioSegment.from_file(io.BytesIO(raw_audio_data))
            wav_buffer = io.BytesIO()
            input_audio.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            final_audio_bytes = wav_buffer.read()
        except Exception as e:
            print(f"خطأ في معالجة ملف الصوت القادم: {e}")
            return jsonify({'error': 'ملف صوتي تالف أو غير مدعوم'}), 400

        # 1️⃣ تحويل الصوت إلى نص
        text = convert_audio_to_text(final_audio_bytes)
        if not text:
            return jsonify({'error': 'فشل تحويل الصوت للنص'}), 500
        
        # 2️⃣ إرسال النص إلى ChatGPT
        response_text = get_chatgpt_response(text)
        if not response_text:
            return jsonify({'error': 'فشل في الحصول على رد'}), 500
        
        # 3️⃣ تحويل الرد للصوت
        audio_stream = convert_text_to_audio(response_text)
        if not audio_stream:
            return jsonify({'error': 'فشل تحويل النص للصوت'}), 500
        
        # 4️⃣ حفظ الصوت للـ ESP32
        audio_bytes = audio_stream.getvalue()
        esp32_data['last_audio'] = audio_bytes
        esp32_data['status'] = 'ready_for_pull'
        
        # لا يتم تنفيذ إرسال متزامن هنا
        
        print("✅ اكتملت المعالجة بنجاح. الصوت متاح للسحب بواسطة ESP32.")
        print("="*50 + "\n")
        
        return jsonify({
            'text': response_text,
            'audio_url': '/get-audio-stream' 
        })
    
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {e}")
        return jsonify({'error': str(e)}), 500

# ========== Endpoint لتحميل الصوت (الـ ESP32 سيقوم بعمل GET على هذا الرابط) ==========
@app.route('/get-audio-stream', methods=['GET'])
def get_audio_stream():
    """إرسال الصوت الأخير للـ ESP32 أو المتصفح"""
    if esp32_data['last_audio']:
        # إعادة تعيين الحالة بعد إرسال الملف مرة واحدة
        # يمكن لـ ESP32 قراءة هذا الرابط وسحبه
        audio_to_send = esp32_data['last_audio']
        esp32_data['last_audio'] = None
        esp32_data['status'] = 'ready' 
        return send_file(
            io.BytesIO(audio_to_send),
            mimetype="audio/wav",
            as_attachment=False,
            download_name="response.wav"
        )
    return "No audio", 404

# ========== فحص الحالة ==========
@app.route('/status', methods=['GET'])
def get_status():
    """الحصول على حالة النظام"""
    # يمكن لـ ESP32 استخدام هذا Endpoint لفحص ما إذا كان هناك صوت جديد جاهز (status = ready_for_pull)
    return jsonify({
        'server_status': 'online',
        'audio_pull_status': esp32_data['status'],
        'openai_configured': api_key is not None
    })

# ========== Endpoint للاختبار ==========
@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "Server is running", "openai": "configured" if api_key else "missing"})

if __name__ == '__main__':
    # الاستماع على جميع الواجهات في المنفذ 5000 (مطلوب للاستضافة على Render)
    app.run(host='0.0.0.0', port=os.getenv('PORT', 5000), debug=True)
