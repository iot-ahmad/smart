# استخدام صورة بايثون رسمية كأساس
FROM python:3.13-slim

# تعيين متغير بيئة لمنفذ التشغيل
ENV PORT 8080

# تثبيت تبعيات النظام المطلوبة لـ pydub (FFmpeg)
# FFmpeg ضروري لمعالجة الملفات الصوتية وتحويلها
RUN apt-get update && \
    apt-get install -y ffmpeg && \
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

# أمر بدء تشغيل التطبيق (تم التعديل لاستخدام server.py)
CMD ["python", "server.py"]