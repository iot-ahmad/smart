import os
import io
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
from openai import OpenAI
import tempfile

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY not found in environment")
    raise SystemExit

client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

# ====== HTML/CSS/JS للموقع ======
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مساعد ذكي صوتي</title>
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
            border-radius: 30px;
            box-shadow: 0 30px 60px rgba(0,0,0,0.3);
            padding: 50px;
            max-width: 600px;
            width: 100%;
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
        }
        
        .header h1 {
            font-size: 32px;
            color: #333;
            margin-bottom: 10px;
        }
        
        .header p {
            color: #666;
            font-size: 14px;
        }
        
        .controls {
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
            flex-wrap: wrap;
            justify-content: center;
        }
        
        .btn {
            padding: 14px 28px;
            border: none;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .btn-record {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-record:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(102, 126, 234, 0.4);
        }
        
        .btn-record:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        
        .btn-stop {
            background: #ff6b6b;
            color: white;
        }
        
        .btn-stop:hover {
            background: #ff5252;
            transform: translateY(-3px);
        }
        
        .btn-stop:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .btn-send {
            background: #51cf66;
            color: white;
        }
        
        .btn-send:hover {
            background: #40c057;
            transform: translateY(-3px);
        }
        
        .btn-send:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .recording-indicator {
            text-align: center;
            margin: 20px 0;
            display: none;
        }
        
        .recording-indicator.active {
            display: block;
        }
        
        .pulse {
            display: inline-block;
            width: 15px;
            height: 15px;
            background: #ff6b6b;
            border-radius: 50%;
            animation: pulse 1.5s infinite;
            margin-right: 10px;
        }
        
        @keyframes pulse {
            0%, 100% {
                opacity: 1;
                transform: scale(1);
            }
            50% {
                opacity: 0.5;
                transform: scale(1.1);
            }
        }
        
        .timer {
            font-size: 18px;
            color: #ff6b6b;
            font-weight: bold;
        }
        
        .waveform {
            display: flex;
            align-items: flex-end;
            justify-content: center;
            gap: 3px;
            height: 80px;
            margin: 20px 0;
            background: #f8f9fa;
            border-radius: 12px;
            padding: 15px;
            display: none;
        }
        
        .waveform.active {
            display: flex;
        }
        
        .bar {
            width: 4px;
            background: linear-gradient(to top, #667eea, #764ba2);
            border-radius: 2px;
            animation: wave 0.5s ease-in-out infinite;
        }
        
        @keyframes wave {
            0%, 100% { height: 10%; }
            50% { height: 100%; }
        }
        
        .status {
            text-align: center;
            padding: 15px;
            border-radius: 12px;
            margin: 20px 0;
            display: none;
            font-weight: 600;
        }
        
        .status.show {
            display: block;
        }
        
        .status.loading {
            background: #e7f5ff;
            color: #0066cc;
        }
        
        .status.success {
            background: #e6ffed;
            color: #2f9e44;
        }
        
        .status.error {
            background: #ffe0e0;
            color: #c92a2a;
        }
        
        .response {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            margin-top: 30px;
            border-left: 4px solid #667eea;
            display: none;
        }
        
        .response.show {
            display: block;
        }
        
        .response h3 {
            color: #333;
            margin-bottom: 12px;
            font-size: 18px;
        }
        
        .response p {
            color: #555;
            line-height: 1.8;
            font-size: 15px;
        }
        
        .ip-display {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
            border: 2px dashed #667eea;
        }
        
        .ip-display p {
            color: #666;
            margin-bottom: 5px;
            font-size: 13px;
        }
        
        .ip-display .ip-value {
            font-size: 16px;
            font-weight: bold;
            color: #667eea;
            font-family: monospace;
        }
        
        .spinner {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .info-box {
            background: #fff8e1;
            border-left: 4px solid #fbc02d;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 13px;
            color: #666;
            line-height: 1.6;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎤 مساعد ذكي صوتي</h1>
            <p>سجّل سؤالك وسيتم الرد عليه بصوت</p>
        </div>
        
        <div class="ip-display">
            <p>IP Address الجهاز:</p>
            <div class="ip-value" id="ipAddress">جاري التحميل...</div>
        </div>
        
        <div class="info-box">
            ℹ️ <strong>طريقة الاستخدام:</strong> اضغط "ابدأ التسجيل" وتحدث بسؤالك، ثم اضغط "إيقاف التسجيل" وأخيراً "إرسال"
        </div>
        
        <div class="waveform" id="waveform">
            <div class="bar" style="animation-delay: 0s;"></div>
            <div class="bar" style="animation-delay: 0.1s;"></div>
            <div class="bar" style="animation-delay: 0.2s;"></div>
            <div class="bar" style="animation-delay: 0.3s;"></div>
            <div class="bar" style="animation-delay: 0.4s;"></div>
            <div class="bar" style="animation-delay: 0.5s;"></div>
        </div>
        
        <div class="recording-indicator" id="recordingIndicator">
            <span class="pulse"></span>
            <span>جاري التسجيل...</span>
            <div class="timer" id="timer">0:00</div>
        </div>
        
        <div class="controls">
            <button class="btn btn-record" id="recordBtn">
                🔴 ابدأ التسجيل
            </button>
            <button class="btn btn-stop" id="stopBtn" disabled>
                ⏹️ إيقاف
            </button>
            <button class="btn btn-send" id="sendBtn" disabled>
                📤 إرسال
            </button>
        </div>
        
        <div class="status" id="status"></div>
        
        <div class="response" id="response">
            <h3>الإجابة:</h3>
            <p id="responseText"></p>
        </div>
    </div>

    <script>
        let mediaRecorder;
        let audioChunks = [];
        let recordingStartTime;
        let timerInterval;

        const recordBtn = document.getElementById('recordBtn');
        const stopBtn = document.getElementById('stopBtn');
        const sendBtn = document.getElementById('sendBtn');
        const status = document.getElementById('status');
        const response = document.getElementById('response');
        const responseText = document.getElementById('responseText');
        const recordingIndicator = document.getElementById('recordingIndicator');
        const waveform = document.getElementById('waveform');
        const timer = document.getElementById('timer');
        const ipAddress = document.getElementById('ipAddress');

        // عرض IP
        fetch('/get_ip')
            .then(res => res.json())
            .then(data => {
                ipAddress.textContent = data.ip;
            });

        // ابدأ التسجيل
        recordBtn.addEventListener('click', async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                mediaRecorder.ondataavailable = (e) => {
                    audioChunks.push(e.data);
                };

                mediaRecorder.start();
                recordBtn.disabled = true;
                stopBtn.disabled = false;
                recordingIndicator.classList.add('active');
                waveform.classList.add('active');
                response.classList.remove('show');
                
                recordingStartTime = Date.now();
                timerInterval = setInterval(() => {
                    const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
                    const mins = Math.floor(elapsed / 60);
                    const secs = elapsed % 60;
                    timer.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
                }, 1000);

                showStatus('⏺️ جاري التسجيل...', 'loading');
            } catch (error) {
                showStatus('❌ خطأ: تأكد من السماح بالميكروفون', 'error');
            }
        });

        // إيقاف التسجيل
        stopBtn.addEventListener('click', () => {
            mediaRecorder.stop();
            recordBtn.disabled = false;
            stopBtn.disabled = true;
            sendBtn.disabled = false;
            recordingIndicator.classList.remove('active');
            waveform.classList.remove('active');
            clearInterval(timerInterval);
            showStatus('✅ تم إيقاف التسجيل - اضغط "إرسال" لإرسال السؤال', 'success');
        });

        // إرسال الصوت
        sendBtn.addEventListener('click', () => {
            if (audioChunks.length === 0) return;

            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const formData = new FormData();
            formData.append('audio', audioBlob, 'question.wav');

            recordBtn.disabled = true;
            sendBtn.disabled = true;
            showStatus('⏳ جاري معالجة السؤال والحصول على الرد...', 'loading');

            fetch('/process_audio', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    showStatus('❌ خطأ: ' + data.error, 'error');
                    recordBtn.disabled = false;
                } else {
                    responseText.textContent = data.reply;
                    response.classList.add('show');
                    showStatus('✅ تم الحصول على الإجابة! ESP32 سيشغل الصوت الآن', 'success');
                    recordBtn.disabled = false;
                }
            })
            .catch(error => {
                showStatus('❌ خطأ في الاتصال', 'error');
                recordBtn.disabled = false;
            });
        });

        function showStatus(message, type) {
