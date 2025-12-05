from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
import os
from dotenv import load_dotenv
from pydub import AudioSegment
import io
import requests
from gtts import gTTS
import threading
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

client = OpenAI(api_key=api_key)

# تخزين مؤقت للبيانات
esp32_data = {
    'last_audio': None,
    'status': 'ready'
}

# ========== وظيفة تحويل الصوت لنص (Whisper) ==========
def convert_audio_to_text(audio_bytes):
    """تحويل ملف صوتي لنص باستخدام OpenAI Whisper (أدق من Google)"""
    try:
        print("🎤 جاري تحويل الصوت إلى نص (Whisper)...")
        
        # 1. إعداد الملف في الذاكرة
        # ملاحظة: يجب تحديد الاسم ليعرف OpenAI نوع الملف
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
        # يمكنك هنا وضع بديل Google Speech Recognition إذا فشل Whisper
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
        
        # استخدام gTTS (مجاني)
        tts = gTTS(text=text, lang='ar', slow=False)
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        
        # تحويل من MP3 إلى WAV (الـ ESP32 يفضل WAV عادة، أو يمكنك إرسال MP3 إذا كان يدعمه)
        audio = AudioSegment.from_file(mp3_fp, format="mp3")
        
        # توحيد التردد (Sampling Rate) لضمان عمله على ESP32
        # معظم مكتبات I2S في ESP32 تعمل جيداً مع 16000Hz أو 44100Hz
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
        
        # قراءة البيانات الخام
        raw_audio_data = file.read()
        
        # تحويل أي صيغة قادمة (webm, m4a, etc) إلى wav باستخدام Pydub
        # هذا يحل مشاكل التنسيق القادمة من المتصفحات المختلفة
        try:
            input_audio = AudioSegment.from_file(io.BytesIO(raw_audio_data))
            # تصدير إلى wav في الذاكرة لإرساله إلى Whisper
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
        
        # 5️⃣ إرسال الصوت للـ ESP32 (Thread)
        esp32_data['status'] = 'sending_to_esp32'
        threading.Thread(target=send_audio_to_esp32, args=(audio_bytes,)).start()
        
        print("✅ اكتملت الدورة بنجاح")
        print("="*50 + "\n")
        
        return jsonify({
            'text': response_text,
            'audio_url': '/get-audio-stream' # الرابط الذي يمكن للمتصفح تشغيله أيضاً
        })
    
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {e}")
        return jsonify({'error': str(e)}), 500

# ========== إرسال الصوت للـ ESP32 ==========
def send_audio_to_esp32(audio_data):
    try:
        # تأكد من وضع عنوان الـ IP الصحيح للـ ESP32 في ملف .env
        # مثال: ESP32_IP=http://192.168.1.50
        esp32_ip = os.getenv('ESP32_IP')
        
        if not esp32_ip:
            print("⚠️ لم يتم تحديد ESP32_IP في ملف البيئة")
            return

        print(f"📡 إرسال {len(audio_data)} بايت إلى {esp32_ip}/audio ...")
        
        # إرسال البيانات كـ raw bytes
        response = requests.post(
            f"{esp32_ip}/audio",
            data=audio_data,
            headers={'Content-Type': 'audio/wav'}, # أو application/octet-stream حسب كود الـ ESP32
            timeout=15
        )
        
        if response.status_code == 200:
            print("✅ استلم ESP32 الملف بنجاح")
            esp32_data['status'] = 'playing'
        else:
            print(f"❌ رد غير متوقع من ESP32: {response.status_code}")
            
    except Exception as e:
        print(f"❌ فشل الاتصال بـ ESP32: {e}")
        esp32_data['status'] = 'error'

# ========== Endpoint لتحميل الصوت (للمتصفح أو ESP32 polling) ==========
@app.route('/get-audio-stream', methods=['GET'])
def get_audio_stream():
    if esp32_data['last_audio']:
        return send_file(
            io.BytesIO(esp32_data['last_audio']),
            mimetype="audio/wav",
            as_attachment=False,
            download_name="response.wav"
        )
    return "No audio", 404

# ========== فحص الحالة ==========
@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "Server is running", "openai": "configured" if api_key else "missing"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
