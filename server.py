"""
Smart Voice Assistant Server - FREE VERSION
Flask server with Groq (Whisper + Llama3) and Google TTS (gTTS) integration
Fixed for Python 3.13 - No pydub dependency
"""

import os
import io
import logging
from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
from openai import OpenAI
from gtts import gTTS  # إضافة مكتبة الصوت المجانية
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure max upload size (10MB)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

# Initialize Groq client (using OpenAI library format)
try:
    # استخدم مفتاح Groq هنا
    api_key = os.getenv('GROQ_API_KEY') or os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        logger.error("GROQ_API_KEY not found in environment variables")
        client = None
    else:
        # توجيه العميل لسيرفرات Groq المجانية
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        logger.info("Groq client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Groq client: {str(e)}")
    client = None

# Global state for ESP32 communication
esp32_data = {
    'status': 'ready',  # ready, processing, sending_to_esp32
    'audio_data': None,
    'has_audio': False,
    'text': '',
    'response_text': ''
}

# HTML page with embedded CSS and JavaScript
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مساعد صوتي ذكي - Smart Voice Assistant</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 600px;
            width: 100%;
            animation: fadeIn 0.5s ease-in;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        h1 {
            color: #667eea;
            text-align: center;
            margin-bottom: 10px;
            font-size: 32px;
            font-weight: bold;
        }
        
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        
        .controls {
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
            justify-content: center;
            flex-wrap: wrap;
        }
        
        button {
            padding: 15px 30px;
            border: none;
            border-radius: 50px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            color: white;
            font-family: inherit;
        }
        
        #recordBtn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        #stopBtn {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            display: none;
        }
        
        #clearBtn {
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        }
        
        button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        }
        
        button:active:not(:disabled) {
            transform: translateY(0);
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .status {
            background: #f7f9fc;
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            min-height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid #e0e7ff;
        }
        
        .status-text {
            color: #555;
            font-size: 16px;
            text-align: center;
        }
        
        .recording {
            animation: pulse 1.5s ease-in-out infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .result {
            background: #e8f5e9;
            padding: 20px;
            border-radius: 15px;
            margin-top: 20px;
            display: none;
            animation: slideIn 0.3s ease-out;
        }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .result h3 {
            color: #2e7d32;
            margin-bottom: 10px;
            font-size: 18px;
        }
        
        .result p {
            color: #333;
            line-height: 1.6;
            font-size: 15px;
        }
        
        .loader {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .error {
            background: #ffebee;
            border: 2px solid #ef5350;
        }
        
        .error .status-text {
            color: #c62828;
        }
        
        .success {
            background: #e8f5e9;
            border: 2px solid #66bb6a;
        }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #e0e7ff;
            color: #666;
            font-size: 12px;
        }
        
        .footer a {
            color: #667eea;
            text-decoration: none;
        }
        
        .footer a:hover {
            text-decoration: underline;
        }
        
        @media (max-width: 600px) {
            .container {
                padding: 20px;
            }
            
            h1 {
                font-size: 24px;
            }
            
            button {
                padding: 12px 20px;
                font-size: 14px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎤 مساعد صوتي ذكي</h1>
        <p class="subtitle">مدعوم بـ Groq Whisper و Llama 3 (نسخة مجانية)</p>
        
        <div class="controls">
            <button id="recordBtn">🎙️ ابدأ التسجيل</button>
            <button id="stopBtn">⏹️ إيقاف التسجيل</button>
            <button id="clearBtn">🗑️ مسح</button>
        </div>
        
        <div class="status" id="statusBox">
            <div class="status-text" id="statusText">اضغط على زر التسجيل للبدء</div>
        </div>
        
        <div class="result" id="result">
            <h3>📝 النص المحول:</h3>
            <p id="transcriptText"></p>
            <h3 style="margin-top: 15px;">🤖 رد المساعد:</h3>
            <p id="responseText"></p>
        </div>
        
        <div class="footer">
            <p>🚀 مشروع مفتوح المصدر | Powered by Groq & Google TTS</p>
        </div>
    </div>

    <script>
        let mediaRecorder;
        let audioChunks = [];
        const recordBtn = document.getElementById('recordBtn');
        const stopBtn = document.getElementById('stopBtn');
        const clearBtn = document.getElementById('clearBtn');
        const statusBox = document.getElementById('statusBox');
        const statusText = document.getElementById('statusText');
        const result = document.getElementById('result');
        const transcriptText = document.getElementById('transcriptText');
        const responseText = document.getElementById('responseText');

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            statusText.innerHTML = '❌ المتصفح لا يدعم تسجيل الصوت';
            statusBox.classList.add('error');
            recordBtn.disabled = true;
        }

        recordBtn.addEventListener('click', async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        sampleRate: 44100
                    } 
                });
                
                const options = { mimeType: 'audio/webm' };
                if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                    options.mimeType = 'audio/ogg; codecs=opus';
                    if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                        options.mimeType = 'audio/mp4';
                    }
                }
                
                mediaRecorder = new MediaRecorder(stream, options);
                audioChunks = [];

                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: options.mimeType });
                    await uploadAudio(audioBlob);
                };

                mediaRecorder.start();
                recordBtn.style.display = 'none';
                stopBtn.style.display = 'inline-block';
                clearBtn.disabled = true;
                statusText.innerHTML = '🔴 جاري التسجيل... تحدث الآن';
                statusText.classList.add('recording');
                statusBox.classList.remove('error', 'success');
                result.style.display = 'none';
            } catch (error) {
                console.error('Error:', error);
                statusText.innerHTML = '❌ خطأ في الوصول للميكروفون. تأكد من السماح بالوصول.';
                statusBox.classList.add('error');
            }
        });

        stopBtn.addEventListener('click', () => {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                mediaRecorder.stream.getTracks().forEach(track => track.stop());
            }
            stopBtn.style.display = 'none';
            recordBtn.style.display = 'inline-block';
            statusText.classList.remove('recording');
            statusBox.classList.remove('error', 'success');
            statusText.innerHTML = '<div class="loader"></div>';
        });

        clearBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/clear', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                if (response.ok) {
                    result.style.display = 'none';
                    statusText.innerHTML = 'تم المسح بنجاح ✅';
                    statusBox.classList.add('success');
                    setTimeout(() => {
                        statusText.innerHTML = 'اضغط على زر التسجيل للبدء';
                        statusBox.classList.remove('success');
                    }, 2000);
                }
            } catch (error) {
                console.error('Clear error:', error);
            }
        });

        async function uploadAudio(audioBlob) {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (data.status === 'ok') {
                    statusText.innerHTML = '✅ تم المعالجة بنجاح!';
                    statusBox.classList.add('success');
                    transcriptText.textContent = data.text;
                    responseText.textContent = data.response;
                    result.style.display = 'block';
                    clearBtn.disabled = false;
                } else {
                    statusText.innerHTML = '❌ حدث خطأ: ' + (data.error || 'خطأ غير معروف');
                    statusBox.classList.add('error');
                    clearBtn.disabled = false;
                }
            } catch (error) {
                console.error('Upload error:', error);
                statusText.innerHTML = '❌ خطأ في الاتصال بالسيرفر. حاول مرة أخرى.';
                statusBox.classList.add('error');
                clearBtn.disabled = false;
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template_string(HTML_PAGE)

@app.route('/upload', methods=['POST'])
def upload_audio():
    """
    Handle audio upload from web interface
    Process: Audio -> Groq Whisper (STT) -> Groq Llama3 -> gTTS -> Store for ESP32
    """
    try:
        if client is None:
            logger.error("Groq client not initialized")
            return jsonify({
                'status': 'error',
                'error': 'Groq API key not configured'
            }), 500

        if 'audio' not in request.files:
            logger.warning("No audio file in request")
            return jsonify({
                'status': 'error',
                'error': 'لم يتم إرسال ملف صوتي'
            }), 400
        
        audio_file = request.files['audio']
        
        if audio_file.filename == '':
            logger.warning("Empty audio filename")
            return jsonify({
                'status': 'error',
                'error': 'اسم الملف فارغ'
            }), 400
        
        logger.info(f"Received audio file: {audio_file.filename}")
        
        esp32_data['status'] = 'processing'
        
        # Step 1: Transcribe audio using Groq Whisper (FREE)
        logger.info("Starting Whisper transcription (Groq)...")
        try:
            audio_file.seek(0)
            audio_bytes = audio_file.read()
            
            transcript = client.audio.transcriptions.create(
                model="whisper-large-v3",  # موديل مجاني وسريع
                file=(audio_file.filename, audio_bytes, audio_file.mimetype),
                language="ar"
            )
            user_text = transcript.text
            esp32_data['text'] = user_text
            logger.info(f"Transcription: {user_text[:50]}...")
        except Exception as e:
            logger.error(f"Whisper error: {str(e)}")
            esp32_data['status'] = 'ready'
            return jsonify({
                'status': 'error',
                'error': f'خطأ في تحويل الصوت: {str(e)}'
            }), 500
        
        # Step 2: Get AI response using Groq Llama 3 (FREE)
        logger.info("Getting AI response (Llama 3)...")
        try:
            chat_response = client.chat.completions.create(
                model="llama3-8b-8192",  # موديل مجاني ذكي
                messages=[
                    {
                        "role": "system",
                        "content": "أنت مساعد صوتي ذكي ومفيد. أجب بشكل مختصر ومفيد باللغة العربية."
                    },
                    {
                        "role": "user",
                        "content": user_text
                    }
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            response_text = chat_response.choices[0].message.content
            esp32_data['response_text'] = response_text
            logger.info(f"AI response: {response_text[:50]}...")
        except Exception as e:
            logger.error(f"AI error: {str(e)}")
            esp32_data['status'] = 'ready'
            return jsonify({
                'status': 'error',
                'error': f'خطأ في الذكاء الاصطناعي: {str(e)}'
            }), 500
        
        # Step 3: Convert to speech using Google TTS (FREE)
        logger.info("Converting to speech (gTTS)...")
        try:
            tts = gTTS(text=response_text, lang='ar')
            
            mp3_fp = io.BytesIO()
            tts.write_to_fp(mp3_fp)
            mp3_fp.seek(0)
            
            audio_bytes = mp3_fp.getvalue()
            
            esp32_data['audio_data'] = audio_bytes
            esp32_data['has_audio'] = True
            esp32_data['status'] = 'sending_to_esp32'
            logger.info("TTS successful")
        except Exception as e:
            logger.error(f"TTS error: {str(e)}")
            esp32_data['status'] = 'ready'
            return jsonify({
                'status': 'error',
                'error': f'خطأ في TTS: {str(e)}'
            }), 500
        
        logger.info("Processing completed successfully")
        return jsonify({
            'status': 'ok',
            'text': user_text,
            'response': response_text,
            'audio_url': '/get-audio-stream'
        })
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        esp32_data['status'] = 'ready'
        return jsonify({
            'status': 'error',
            'error': f'خطأ غير متوقع: {str(e)}'
        }), 500

@app.route('/tts', methods=['POST'])
def text_to_speech():
    """Convert text to speech using gTTS (FREE)"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'لم يتم إرسال نص'}), 400
        
        logger.info(f"TTS request: {text[:50]}...")
        
        tts = gTTS(text=text, lang='ar')
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        
        logger.info("TTS generation successful")
        
        return send_file(
            mp3_fp,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name='speech.mp3'
        )
        
    except Exception as e:
        logger.error(f"TTS error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get-audio-stream', methods=['GET'])
def get_audio_stream():
    """Return audio for ESP32"""
    try:
        if not esp32_data['has_audio'] or esp32_data['audio_data'] is None:
            logger.warning("No audio available")
            return jsonify({'error': 'No audio available'}), 404
        
        audio_bytes = esp32_data['audio_data']
        logger.info("Sending audio to ESP32")
        
        esp32_data['status'] = 'ready'
        
        return send_file(
            io.BytesIO(audio_bytes),
            mimetype='audio/mpeg',
            as_attachment=False
        )
        
    except Exception as e:
        logger.error(f"Error sending audio: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/status', methods=['GET'])
def get_status():
    """Return system status"""
    status = {
        'server': 'online',
        'esp32_status': esp32_data['status'],
        'has_audio': esp32_data['has_audio']
    }
    return jsonify(status)

@app.route('/clear', methods=['POST'])
def clear_audio():
    """Clear audio buffer"""
    esp32_data['audio_data'] = None
    esp32_data['has_audio'] = False
    esp32_data['status'] = 'ready'
    esp32_data['text'] = ''
    esp32_data['response_text'] = ''
    
    logger.info("Buffer cleared")
    return jsonify({'status': 'cleared'})

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'الملف كبير جداً. الحد الأقصى 10MB'}), 413

@app.errorhandler(500)
def internal_server_error(error):
    logger.error(f"Internal error: {str(error)}")
    return jsonify({'error': 'خطأ في السيرفر'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
