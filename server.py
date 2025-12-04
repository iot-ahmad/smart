# server.py
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import io
import time
from dotenv import load_dotenv
import openai
import speech_recognition as sr
from pydub import AudioSegment
from gtts import gTTS

load_dotenv()

app = Flask(_name_)
CORS(app)

openai.api_key = os.getenv("OPENAI_API_KEY")

# -------------------------
# حالة مخزن الصوت مؤقتاً
# -------------------------
esp32_data = {
    "last_audio": None,   # bytes WAV
    "status": "ready"     # ready, processing, sending_to_esp32, playing
}

# ============================
# الصفحة الرئيسية (CSS بسيط)
# ============================
@app.route("/", methods=["GET"])
def home():
    return """
    <html>
    <head>
      <meta charset="utf-8"/>
      <title>Smart Voice AI Server</title>
      <style>
        body { background:#0b1221; color:#e6eef6; font-family: Arial, sans-serif; text-align:center; padding:60px; }
        .card { background:#0f1724; width:80%; margin:auto; padding:30px; border-radius:12px; box-shadow: 0 10px 30px rgba(2,6,23,0.6); }
        h1 { color:#60a5fa; }
        p { color:#cbd5e1; }
        .badge { display:inline-block; margin-top:12px; padding:10px 16px; background:#16a34a; color:white; border-radius:8px; }
        a { color:#93c5fd; text-decoration:none; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>🚀 Smart Voice AI Server</h1>
        <p>السيرفر شغّال — ارسل ملف صوتي إلى <code>/process-audio</code></p>
        <div class="badge">Status: Running</div>
        <p style="margin-top:18px;"><a href="/status">/status</a> — حالة النظام</p>
      </div>
    </body>
    </html>
    """

# ============================
# تحويل ملف WAV إلى نص (STT)
# ============================
def convert_audio_to_text(audio_bytes):
    try:
        # نتوقع ملف WAV من المتصفح
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        if audio.frame_rate != 16000:
            audio = audio.set_frame_rate(16000)

        tmp = io.BytesIO()
        audio.export(tmp, format="wav")
        tmp.seek(0)

        recognizer = sr.Recognizer()
        with sr.AudioFile(tmp) as source:
            rec_data = recognizer.record(source)

        text = recognizer.recognize_google(rec_data, language="ar-SA")
        print("STT text:", text)
        return text
    except Exception as e:
        print("Error in STT:", e)
        return None

# ============================
# تحويل نص إلى WAV باستخدام gTTS
# ============================
def text_to_wav_bytes(text):
    try:
        tts = gTTS(text=text, lang='ar', slow=False)
        mp3_buf = io.BytesIO()
        tts.write_to_fp(mp3_buf)
        mp3_buf.seek(0)

        audio = AudioSegment.from_mp3(mp3_buf)
        wav_buf = io.BytesIO()
        audio.export(wav_buf, format="wav")
        wav_buf.seek(0)
        return wav_buf.read()
    except Exception as e:
        print("Error in TTS:", e)
        return None

# ============================
# المسار: استقبال صوت من الويب
# ============================
@app.route("/process-audio", methods=["POST"])
def process_audio():
    try:
        if 'audio' not in request.files:
            return jsonify({"error": "لا يوجد ملف صوتي في الطلب (field name must be 'audio')"}), 400

        esp32_data['status'] = 'processing'
        audio_file = request.files['audio']
        audio_bytes = audio_file.read()

        # 1) STT
        text = convert_audio_to_text(audio_bytes)
        if not text:
            esp32_data['status'] = 'ready'
            return jsonify({"error": "فشل تحويل الصوت إلى نص"}), 500

        # 2) إرسال النص للـ OpenAI ChatGPT
        try:
            print("Sending to OpenAI...")
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role":"system", "content":"أنت مساعد يرد بالعربية بشكل ودّي ومختصر."},
                    {"role":"user", "content": text}
                ],
                max_tokens=200,
                temperature=0.7
            )
            ai_reply = resp['choices'][0]['message']['content'].strip()
            print("AI reply:", ai_reply)
        except Exception as e:
            print("OpenAI error:", e)
            esp32_data['status'] = 'ready'
            return jsonify({"error": "فشل الاتصال بـ OpenAI"}), 500

        # 3) تحويل رد الـ AI لصوت (WAV)
        wav_bytes = text_to_wav_bytes(ai_reply)
        if not wav_bytes:
            esp32_data['status'] = 'ready'
            return jsonify({"error": "فشل تحويل النص إلى صوت"}), 500

        # احفظ في الذاكرة المؤقتة
        esp32_data['last_audio'] = wav_bytes
        esp32_data['status'] = 'sending_to_esp32'

        return jsonify({"status":"ok", "text": ai_reply, "audio_url": "/get-audio-stream"})
    except Exception as e:
        print("Server error in /process-audio:", e)
        esp32_data['status'] = 'ready'
        return jsonify({"error": str(e)}), 500

# ============================
# المسار: الـ ESP32 يسحب الصوت
# ============================
@app.route("/get-audio-stream", methods=["GET"])
def get_audio_stream():
    if not esp32_data['last_audio']:
        return jsonify({"error":"لا يوجد صوت جاهز"}), 404
    # بعد تسليم الملف نعتبره مستلم ونعيد الحالة ready
    data = io.BytesIO(esp32_data['last_audio'])
    # لا نفرغ last_audio تلقائياً لأن قد ترغب بإعادة التشغيل؛ لكن نغيّر الحالة
    esp32_data['status'] = 'ready'
    return send_file(data, mimetype="audio/wav", as_attachment=False)

# ============================
# المسار: حالة السيرفر
# ============================
@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "server": "online",
        "esp32_status": esp32_data['status'],
        "has_audio": esp32_data['last_audio'] is not None,
        "timestamp": time.time()
    })

# ============================
# تشغيل السيرفر
# ============================
if _name_ == "_main_":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting server on port {port}...")
    app.run(host="0.0.0.0", port=port)
