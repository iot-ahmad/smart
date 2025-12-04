import os
import io
from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
from openai import OpenAI
import subprocess
import tempfile

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY not found in environment")
    raise SystemExit

client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

@app.get("/")
def home():
    return jsonify({"status": "ok", "message": "ESP32 Voice Assistant is running"})

# ====== Endpoint النصي ======
@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    user_text = data.get("text", "").strip()
    if not user_text:
        return jsonify({"error": "no text provided"}), 400

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": user_text}
            ],
            max_tokens=200,
            temperature=0.7,
        )
        reply = response.choices[0].message.content
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ====== Endpoint الصوت (جديد) ======
@app.post("/voice")
def voice():
    """
    1) استقبل WAV من ESP32
    2) حول إلى نص (Whisper)
    3) أجب بـ ChatGPT
    4) حول الرد إلى صوت WAV (pyttsx3 أو espeak)
    5) أرجع ملف WAV
    """
    
    try:
        # ===== استقبال الصوت =====
        if 'audio' not in request.files:
            return jsonify({"error": "no audio file"}), 400
        
        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({"error": "empty file"}), 400

        audio_data = audio_file.read()
        
        # ===== 1) تحويل الصوت إلى نص (Whisper) =====
        print("[1] تحويل الصوت إلى نص...")
        
        audio_io = io.BytesIO(audio_data)
        audio_io.name = "audio.wav"
        
        transcript_response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_io,
            language="ar"
        )
        user_text = transcript_response.text
        print(f"✓ النص: {user_text}")
        
        if not user_text or user_text.strip() == "":
            return jsonify({"error": "could not transcribe audio"}), 400

        # ===== 2) الحصول على رد من ChatGPT =====
        print("[2] الحصول على رد من ChatGPT...")
        
        chat_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": user_text}
            ],
            max_tokens=300,
            temperature=0.7,
        )
        reply_text = chat_response.choices[0].message.content
        print(f"✓ الرد: {reply_text}")

        # ===== 3) تحويل النص إلى صوت WAV =====
        print("[3] تحويل النص إلى صوت...")
        
        wav_data = None
        
        # محاولة 1: pyttsx3
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            engine.setProperty('volume', 0.9)
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name
            
            engine.save_to_file(reply_text, tmp_path)
            engine.runAndWait()
            
            with open(tmp_path, 'rb') as wav_file:
                wav_data = wav_file.read()
            
            os.unlink(tmp_path)
            print("✓ TTS: pyttsx3")
        
        except Exception as e1:
            print(f"⚠ pyttsx3 فشل: {str(e1)}")
            
            # محاولة 2: espeak + ffmpeg
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    tmp_path = tmp.name
                
                # استخدم espeak لتوليد الصوت
                cmd = f"espeak -w {tmp_path} '{reply_text}' -l ar"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                    with open(tmp_path, 'rb') as wav_file:
                        wav_data = wav_file.read()
                    
                    os.unlink(tmp_path)
                    print("✓ TTS: espeak")
                else:
                    print(f"⚠ espeak فشل: {result.stderr}")
            
            except Exception as e2:
                print(f"⚠ espeak فشل: {str(e2)}")
        
        # إذا فشل TTS، أرجع النص فقط
        if wav_data is None:
            print("❌ TTS غير متاح، أرجع النص فقط")
            return jsonify({
                "text": reply_text,
                "message": "الرد نصي (TTS غير متاح)"
            }), 200
        
        # ===== أرجع ملف WAV =====
        wav_io = io.BytesIO(wav_data)
        return send_file(
            wav_io,
            mimetype='audio/wav',
            as_attachment=True,
            download_name='response.wav'
        )

    except Exception as e:
        print(f"[❌] خطأ عام: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
