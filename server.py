from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import uuid
from openai import OpenAI

app = Flask(_name_)
CORS(app)

# Load API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Temporary folder
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================================
# 📌 الصفحة الرئيسية – فيها CSS
# ================================
@app.route("/", methods=["GET"])
def home():
    return """
    <html>
    <head>
        <title>Smart Voice AI Server</title>
        <style>
            body {
                background: #0d1117;
                color: #e6edf3;
                font-family: Arial, sans-serif;
                text-align: center;
                padding-top: 80px;
            }
            .card {
                background: #161b22;
                padding: 30px;
                width: 70%;
                margin: auto;
                border-radius: 14px;
                box-shadow: 0 0 20px #000;
            }
            h1 {
                color: #58a6ff;
                font-size: 32px;
            }
            p {
                color: #c9d1d9;
                font-size: 18px;
            }
            .status {
                margin-top: 20px;
                padding: 15px;
                background: #238636;
                display: inline-block;
                color: white;
                border-radius: 8px;
                font-size: 20px;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 Smart Voice AI Server</h1>
            <p>Your server is live and ready to receive audio!</p>
            <div class="status">✓ Running</div>
        </div>
    </body>
    </html>
    """

# ================================
# 📌 API – رفع الصوت
# ================================
@app.route("/upload", methods=["POST"])
def upload_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file received"}), 400

    audio = request.files["audio"]
    file_id = str(uuid.uuid4()) + ".wav"
    save_path = os.path.join(UPLOAD_FOLDER, file_id)
    audio.save(save_path)

    # 🎤 تحويل صوت → نص
    with open(save_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=f
        )

    text = transcript.text

    # 🤖 إرسال النص للذكاء الاصطناعي
    response = client.responses.create(
        model="gpt-4.1",
        input=text
    )

    ai_text = response.output_text

    # 🔊 تحويل الرد إلى صوت
    tts_file = save_path.replace(".wav", "_reply.wav")
    with open(tts_file, "wb") as f:
        speech = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=ai_text
        )
        f.write(speech.read())

    return jsonify({
        "status": "ok",
        "text": ai_text,
        "audio_url": f"/audio/{file_id.replace('.wav', '_reply.wav')}"
    })

# ================================
# 📌 API – تحميل الصوت النهائي
# ================================
@app.route("/audio/<filename>", methods=["GET"])
def get_audio(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, mimetype="audio/wav")

# ================================
# 📌 التشغيل
# ================================
if _name_ == "_main_":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Running server on port {port}...")
    app.run(host="0.0.0.0", port=port)
