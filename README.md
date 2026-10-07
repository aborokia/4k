# 4K STORE

متجر ألعاب عربي مبني بـ Flask، ويحتوي على تسجيل حسابات، سلة مشتريات، طلبات، إثبات دفع، وقاعدة بيانات SQLite ولوحة تحكم Admin.

## تشغيل محليًا

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py app.py
```

افتح: http://127.0.0.1:5000

## بيانات الأدمن الافتراضية

- البريد: `admin@4kstore.local`
- كلمة المرور: `ChangeMe123!`

يمكن تغييرهما بمتغيري البيئة `ADMIN_EMAIL` و `ADMIN_PASSWORD`.

## تشغيل Gunicorn

```bash
gunicorn app:app
```

## النشر على Render

المشروع يحتوي على `render.yaml`. اربط مستودع GitHub بـ Render، وسيستخدم:

- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`

أضف `ADMIN_EMAIL` و`ADMIN_PASSWORD` في Environment Variables.

### ملاحظة مهمة عن قاعدة البيانات

هذه النسخة تستخدم SQLite. على استضافة تعتمد على نظام ملفات مؤقت، قد تفقد قاعدة البيانات والملفات المرفوعة عند إعادة النشر أو إعادة التشغيل. للاستخدام التجاري الحقيقي، انقل قاعدة البيانات إلى PostgreSQL واستخدم تخزينًا دائمًا للملفات/إثباتات الدفع.
