# تشغيل المحرك على EC2 Windows

## 1. تجهيز بايثون
- افتح PowerShell على السيرفر.
- نزّل بايثون 3.11 من python.org (لو مش متثبت) وثبّته مع تفعيل "Add to PATH".
- تأكد إن MetaTrader 5 مثبت ومفتوح ومسجل دخول على أي حساب (نفس اللي شايفه على الديسكتوب).

## 2. نسخ الملفات
انسخ مجلد `ec2-engine` كامل على السيرفر، مثلاً في:
`C:\sniper-bot\ec2-engine`

## 3. تثبيت المكتبات
```powershell
cd C:\sniper-bot\ec2-engine
pip install -r requirements.txt
```

## 4. تحديد المفتاح السري
هتحتاج مفتاح سري (API Key) يبقى نفسه في بوت التليجرام. اعمله بنفسك (أي نص عشوائي طويل)، وحطه كمتغير بيئة دائم:

```powershell
[System.Environment]::SetEnvironmentVariable("EC2_API_KEY", "حط_هنا_مفتاح_عشوائي_طويل_وقوي", "Machine")
```
بعدها اقفل PowerShell وافتحه تاني عشان المتغير يتفعّل.

## 5. فتح الـ Port في Security Group
من AWS Console:
- EC2 → Instances → اختار الـ instance
- Security → اضغط على الـ Security Group
- Inbound Rules → Edit → Add rule:
  - Type: Custom TCP
  - Port: 8443
  - Source: Anywhere (0.0.0.0/0)

## 6. تشغيل المحرك كـ Task دائم (يشتغل حتى لو قفلت الجلسة)
استخدم **Task Scheduler**:
1. افتح Task Scheduler → Create Task
2. General: اسم المهمة "sniper-engine"، اختار "Run whether user is logged on or not"
3. Triggers: New → "At startup"
4. Actions: New →
   - Program/script: `python`
   - Add arguments: `C:\sniper-bot\ec2-engine\engine.py`
   - Start in: `C:\sniper-bot\ec2-engine`
5. Settings: فعّل "If the task fails, restart every 1 minute"
6. احفظ، وشغّله يدوي أول مرة للتأكد إنه شغال.

للتأكد إنه شغال، افتح من على أي متصفح:
```
http://<Elastic-IP>:8443/health
```
المفروض يرجعلك `{"status":"ok"}`.

## ملاحظات أمان
- ده استخدام مبدئي على **حساب تجريبي فقط**. قبل أي انتقال لحساب حقيقي لازم تضيف HTTPS (مثلاً عن طريق Caddy أو nginx مع شهادة SSL) بدل HTTP العادي، عشان بيانات تسجيل الدخول متتبعتش كنص واضح على الشبكة.
- خلي الـ EC2_API_KEY طويل وعشوائي، وماتشاركوش مع حد.
