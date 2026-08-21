# EXENS Auto

بوت أوتوماتيك بالكامل:

- خروج كبير من Coinbase → شراء (نسبي)
- دخول كبير لـ Coinbase → بيع (نسبي)
- 20% كاش طوارئ محجوز دائمًا
- كل المفاتيح السرية بتتحط من جوه التليجرام فقط

## .env
```
TG_TOKEN=توكن_البوت_فقط
```

## التشغيل على EC2 Amazon Linux

```bash
sudo dnf update -y
sudo dnf install -y python3 python3-pip git
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env          # حط توكن البوت فقط
python main.py
```

## إعداد المراقبة الأوتوماتيك

1. اعمل قناة تليجرام خاصة
2. خلّي الرسائل من @whale_alert_io تتعملها Forward للقناة الخاصة
3. أضف البوت بتاعك كـ **Admin** في القناة الخاصة
4. البوت هيبدأ يقرأ الإشارات لوحده

## أول استخدام

1. ابعت `/start` للبوت
2. اضغط **🔑 إعدادات Bitget** وادخل المفاتيح
3. غيّر الوضع لـ `mode real` لما تكون جاهز
