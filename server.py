from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os, io, time, threading
import speech_recognition as sr
from pydub import AudioSegment
from gtts import gTTS
import requests
from dotenv import load_dotenv
import openai

load_dotenv()

app = Flask(_name_)
CORS(app)

openai.api_key = os.getenv("OPENAI_API_KEY")

# تخزين آخر صوت جاهز للـ ESP32
buffered_audio = None
esp_status = "ready"  # ready / processing / sending_to_esp32 / idle

# ============== 1. تحويل الصوت إلى نص ==============
def convert_audio_to_text(audio_bytes):
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
        audio = audio.set_frame_rate(16000)
        audio.export("temp.wav", format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile("temp.wav") as source:
            data = recognizer.record(source)

        text = recognizer.recognize_google(data, language="ar-SA")
        print("🎤 النص:", text)
        return text
    except Exception as e:
        print("❌ Error in STT:", e)
        return None

# ============== 2. إرسال النص للذكاء الاصطناعي ==============
def ask_chatgpt(text):
    try:
        print("🤖 سؤال ChatGPT...")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "أجب بإسلوب بسيط وواضح ولطيف."},
                {"role": "user", "content": text}
            ]
        )
        reply = response['choices'][0]['message']['content']
        print("🔊 رد ChatGPT:", reply)
        return reply
    except Exception as e:
        print("❌ ChatGPT error:", e)
        return None

# ============== 3. تحويل النص إلى صوت WAV ==============
def text_to_wav(text):
    try:
        tts = gTTS(text=text, lang='ar', slow=False)
        mp3_stream = io.BytesIO()
        tts.write_to_fp(mp3_stream)
        mp3_stream.seek(0)

        audio = AudioSegment.from_mp3(mp3_stream)
        wav_stream = io.BytesIO()
        audio.export(wav_stream, format="wav")
        wav_stream.seek(0)
        print("🎼 تم إنشاء الصوت")
        return wav_stream.getvalue()
    except Exception as e:
        print("❌ Error in TTS:", e)
        return None

# ============== المسار 1: استقبال صوت الويب ==============
@app.route("/process-audio", methods=["POST"])
def process_audio():
    global buffered_audio, esp_status

    try:
        if "audio" not in request.files:
            return jsonify({"error": "لم يتم إرسال ملف صوت"}), 400

        esp_status = "processing"
        audio_file = request.files['audio'].read()

        text = convert_audio_to_text(audio_file)
        if not text:
            esp_status = "idle"
            return jsonify({"error": "فشل تحويل الصوت لنص"}), 500

        reply = ask_chatgpt(text)
        if not reply:
            esp_status = "idle"
            return jsonify({"error": "خطأ في ChatGPT"}), 500

        wav_data = text_to_wav(reply)
        if not wav_data:
            esp_status = "idle"
            return jsonify({"error": "فشل إنشاء الصوت"}), 500

        buffered_audio = wav_data
        esp_status = "sending_to_esp32"

        return jsonify({"text": reply})
    except Exception as e:
        print("❌ Server Error:", e)
        esp_status = "idle"
        return jsonify({"error": str(e)}), 500

# ============== المسار 2: الـ ESP32 يسحب الصوت ==============
@app.route("/get-audio-stream", methods=["GET"])
def send_audio():
    global buffered_audio, esp_status

    if not buffered_audio:
        return jsonify({"error": "لا يوجد صوت جاهز"}), 404
    
    esp_status = "idle"
    return send_file(io.BytesIO(buffered_audio), mimetype="audio/wav")

# ============== المسار 3: حالة النظام ==============
@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "server": "online",
        "esp_status": esp_status
    })

# ============== تشغيل السيرفر ==============
if _name_ == "_main_":
    print("🚀 Running server on port 5000...")
    app.run(host="0.0.0.0", port=5000)
