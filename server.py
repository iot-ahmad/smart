from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import openai
import os
from io import BytesIO

app = Flask(_name_)
CORS(app)

openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/")
def home():
    return "Server is running with STT + TTS!"

# -------------------------------
# 1. استلام الصوت وتحويله لنص
# -------------------------------
@app.route("/upload", methods=["POST"])
def upload_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]

    # تحويل صوت ⇒ نص (Whisper)
    transcript = openai.audio.transcriptions.create(
        model="gpt-4o-audio",
        file=audio_file
    )

    text = transcript.text
    return jsonify({"text": text})


# -------------------------------
# 2. تحويل النص إلى صوت (TTS)
# -------------------------------
@app.route("/tts", methods=["POST"])
def tts():
    data = request.json
    if "text" not in data:
        return jsonify({"error": "No text provided"}), 400

    text_input = data["text"]

    # تحويل النص إلى صوت (mp3)
    result = openai.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text_input
    )

    audio_bytes = result.read()  # صوت خام

    return send_file(
        BytesIO(audio_bytes),
        mimetype="audio/mpeg",
        as_attachment=False,
        download_name="tts.mp3"
    )


if _name_ == "_main_":
    app.run(host="0.0.0.0", port=10000)
