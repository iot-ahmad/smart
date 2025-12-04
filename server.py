import os
import io
import tempfile
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
CORS(app)

# تهيئة عميل OpenAI (المفتاح من .env)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# حالة وBuffer للصوت الجاهز للـ ESP32
buffered_audio_bytes = None
buffered_mimetype = "audio/mpeg"  # سنستخدم mp3 من TTS
esp_status = "ready"  # ready / processing / sending_to_esp32 / idle


# ---------- 1) تحويل الصوت إلى نص باستخدام Whisper عبر API ----------
def convert_audio_to_text(file_bytes, filename_hint="input_audio"):
    """
    file_bytes: bytes of uploaded audio (wav/mp3/ogg...)
    returns: transcribed text or None
    """
    try:
        # احفظ مؤقتًا كملف لأن واجهة OpenAI تنتظر ملف قابل للقراءة
        with tempfile.NamedTemporaryFile(delete=False, prefix=filename_hint, suffix=".tmp") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            # نستخدم endpoint الترانسكريبشن (Whisper)
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ar"  # أو "ar-SA" إن أردت dialect محدد
            )

        # بعض إصدارات المكتبة ترجع نص في resp.text
        text = getattr(resp, "text", None) or resp.get("text") if isinstance(resp, dict) else None

        # حذف الملف المؤقت
        try:
            os.remove(tmp_path)
        except Exception:
            pass

        return text

    except Exception as e:
        print("Error in convert_audio_to_text:", e)
        return None


# ---------- 2) إرسال النص إلى ChatGPT للحصول على الرد ----------
def ask_chatgpt(prompt_text):
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",  # يمكنك تغييره إلى gpt-3.5-turbo إن أردت
            messages=[
                {"role": "system", "content": "أجب بإسلوب بسيط وواضح ولطيف."},
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=600
        )

        # الحصول على نص الرد
        if hasattr(resp, "choices"):
            choice = resp.choices[0]
            # شكل الوصول قد يختلف حسب نسخة المكتبة
            reply = (choice.message["content"] if isinstance(choice.message, dict) else choice.message.content) \
                    if hasattr(choice, "message") else choice["message"]["content"]
        else:
            # محاولة للحصول على dict-style
            reply = resp["choices"][0]["message"]["content"]

        return reply

    except Exception as e:
        print("Error in ask_chatgpt:", e)
        return None


# ---------- 3) تحويل نص ChatGPT إلى ملف صوتي باستخدام OpenAI TTS ----------
def generate_tts_bytes(text, voice="alloy", output_format="mp3"):
    """
    returns: (bytes, mimetype) or (None, None) on error
    """
    try:
        # OpenAI TTS: نطلب توليد صوت ثم نكتب النتيجة في ملف مؤقت ثم نقرأه كبايت
        tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_format}")
        tmp_out_path = tmp_out.name
        tmp_out.close()

        # إنشاء ملف الصوت عبر API
        resp = client.audio.speech.create(
            model="gpt-4o-mini-tts",  # أو "tts-1" / "tts-1-hd" حسب تفضيلك ومفتاحك
            voice=voice,
            input=text
        )

        # resp يحتوي على دالة stream_to_file() بحسب التوثيق. نستخدمها لملء الملف المؤقت.
        try:
            resp.stream_to_file(tmp_out_path)
        except Exception:
            # بعض نسخ المكتبة قد ترجع bytes مباشرة عبر resp.read() — نتحسس ذلك:
            try:
                with open(tmp_out_path, "wb") as f:
                    f.write(resp.read())
            except Exception as e:
                print("Could not stream/save TTS response:", e)
                raise

        # اقرأ الملف كـ bytes
        with open(tmp_out_path, "rb") as f:
            b = f.read()

        # احذف الملف المؤقت
        try:
            os.remove(tmp_out_path)
        except Exception:
            pass

        mimetype = "audio/mpeg" if output_format == "mp3" else "audio/wav"
        return b, mimetype

    except Exception as e:
        print("Error in generate_tts_bytes:", e)
        return None, None


# ========== Endpoint: استقبال صوت من الويب ========== 
@app.route("/process-audio", methods=["POST"])
def process_audio():
    global buffered_audio_bytes, esp_status, buffered_mimetype

    try:
        if "audio" not in request.files:
            return jsonify({"error": "لم يتم إرسال ملف صوت بالاسم 'audio'"}), 400

        esp_status = "processing"
        uploaded = request.files["audio"]
        audio_bytes = uploaded.read()

        # 1 - تحويل الصوت لنص (Whisper)
        text = convert_audio_to_text(audio_bytes, filename_hint="upload_")
        if not text:
            esp_status = "idle"
            return jsonify({"error": "فشل تحويل الصوت إلى نص"}), 500

        # 2 - إرسال النص إلى ChatGPT
        reply = ask_chatgpt(text)
        if not reply:
            esp_status = "idle"
            return jsonify({"error": "فشل الحصول على رد من ChatGPT"}), 500

        # 3 - تحويل رد ChatGPT لصوت (TTS)
        tts_bytes, tts_mimetype = generate_tts_bytes(reply, voice="alloy", output_format="mp3")
        if not tts_bytes:
            esp_status = "idle"
            return jsonify({"error": "فشل توليد الصوت (TTS)"}), 500

        # خزّن للصالح ESP32
        buffered_audio_bytes = tts_bytes
        buffered_mimetype = tts_mimetype
        esp_status = "sending_to_esp32"

        return jsonify({"text": reply})

    except Exception as e:
        print("Server error /process-audio:", e)
        esp_status = "idle"
        return jsonify({"error": str(e)}), 500


# ========== Endpoint: الـ ESP32 يسحب آخر صوت جاهز ==========
@app.route("/get-audio-stream", methods=["GET"])
def get_audio_stream():
    global buffered_audio_bytes, esp_status, buffered_mimetype

    if not buffered_audio_bytes:
        return jsonify({"error": "No audio ready"}), 404

    # بعد السحب نعتبره تم الاستهلاك
    esp_status = "idle"
    stream = io.BytesIO(buffered_audio_bytes)
    stream.seek(0)
    return send_file(stream, mimetype=buffered_mimetype, as_attachment=False, download_name="response.mp3")


# ========== Endpoint: حالة السيرفر ==========
@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "server": "online",
        "esp_status": esp_status
    })


if __name__ == "__main__":
    print("🚀 Running server on port 5000...")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
