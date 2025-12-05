# استخدام صورة بايثون رسمية كأساس
FROM python:3.13-slim

# تعيين متغير بيئة لمنفذ التشغيل
ENV PORT 8080

# تثبيت تبعيات النظام المطلوبة
# - ffmpeg: لمعالجة الصوت (Pydub/gTTS)
# - libasound-dev, portaudio19-dev: لدعم مكتبات الصوت
# - python3-dev: لتوفير ملفات الرأس لوحدات Python المدمجة مثل audioop
RUN apt-get update && \
    apt-get install -y ffmpeg libasound-dev portaudio19-dev python3-dev -y && \
    rm -rf /var/lib/apt/lists/*

# تعيين مجلد العمل داخل الحاوية
WORKDIR /app

# نسخ ملفات متطلبات بايثون لتثبيت التبعيات
COPY requirements.txt .

# تثبيت تبعيات بايثون
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات التطبيق (server.py, .env, etc.)
COPY . .

# الإعلان عن المنفذ الذي سيعمل عليه التطبيق
EXPOSE 8080

# أمر بدء تشغيل التطبيق (باستخدام server.py)
CMD ["python", "server.py"]
