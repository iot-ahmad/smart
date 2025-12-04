import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY not found in environment")
    raise SystemExit

client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

@app.get("/")
def home():
    return jsonify({"status": "ok", "message": "ESP32 cloud server is running"})

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
