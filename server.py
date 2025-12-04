def send_audio_to_esp32(audio_data):
    """إرسال إشارة للـ ESP32 لبدء التشغيل"""
    try:
        # تأكد أن هذا هو IP الـ ESP32 الصحيح
        esp32_ip = os.getenv('ESP32_IP', 'http://192.168.1.100')
        
        print(f"📡 إرسال إشارة تشغيل للـ ESP32 ({esp32_ip})...")
        
        # نرسل طلب بسيط فقط لإيقاظ الـ ESP32
        # نستخدم GET لأنه أسرع ولا يحمل بيانات
        response = requests.get(f"{esp32_ip}/audio", timeout=2)
        
        if response.status_code == 200:
            print("✅ استقبل ESP32 الإشارة وسيبدأ التشغيل")
        else:
            print(f"⚠️ رد ESP32 برمز: {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ فشل الاتصال بـ ESP32: {e}")

