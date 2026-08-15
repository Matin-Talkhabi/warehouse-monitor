import os
import sys
import json
import time
import http.client
from datetime import datetime, timedelta
import pytz
import requests

# ===== LOAD .env MANUALLY =====
def load_env_from_file():
    """Load config from .env if present"""
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
        print("✅ فایل .env با موفقیت بارگذاری شد.")
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"⚠️ خطا در خواندن فایل .env: {e}")
        return False

load_env_from_file()

# ===== CONFIGURATION =====
def get_env_int(key, default):
    value = os.getenv(key)
    if value is None or value == '':
        return default
    try:
        return int(value)
    except ValueError:
        return default

def get_env_str(key, default=''):
    value = os.getenv(key)
    if value is None or value == '':
        return default
    return value

WAREHOUSE_ID = get_env_int('WAREHOUSE_ID', 72)
CHECK_INTERVAL = get_env_int('CHECK_INTERVAL', 30)
ALERT_COOLDOWN = get_env_int('ALERT_COOLDOWN', 300)

SMS_PATTERN_CODE = get_env_str('SMS_PATTERN_CODE', 'kondvd1hhs5h3ld')
SMS_SENDER = get_env_str('SMS_SENDER', '3000505')
SMS_RECIPIENT = get_env_str('SMS_RECIPIENT', '')
SMS_API_KEY = get_env_str('SMS_API_KEY', '')
SMS_COOKIE = get_env_str('SMS_COOKIE', '')

BASE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "fa,en-US;q=0.9,en;q=0.8",
    "dnt": "1",
    "referer": "https://seller.digikala.com/pwa/package/package-creation-revamp",
    "origin": "https://seller.digikala.com",
    "sec-ch-ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": os.getenv(
        'USER_AGENT',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
    ),
}

# ===== SMART COOKIE & HEADER PARSER =====
COOKIE_ATTRIBUTES = {
    'expires', 'max-age', 'path', 'domain', 'samesite',
    'secure', 'httponly', 'priority', 'true', 'false',
    'none', 'lax', 'strict', 'set-cookie', 'cookie'
}

def parse_raw_cookie_dump(raw_text):
    """
    استخراج هوشمند کوکی‌ها و توکن‌ها از هر نوع فرمت پیست شده (DevTools، هدر خام یا کوکی رشته‌ای)
    """
    cookies = {}
    lines = raw_text.strip().splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # حذف برچسب‌های مرسوم هدر
        if line.lower() in ('set-cookie', 'cookie'):
            continue
        if line.lower().startswith(('set-cookie:', 'cookie:')):
            line = line.split(':', 1)[1].strip()

        # تفکیک مقادیر با سمی‌کالن
        parts = line.split(';')
        for part in parts:
            part = part.strip()
            if '=' in part:
                k, v = part.split('=', 1)
                k = k.strip()
                v = v.strip()
                
                # فیلتر کردن اتریبیوت‌های غیراصلی
                if k.lower() not in COOKIE_ATTRIBUTES and not k.lower().startswith('x-') and len(k) > 0:
                    cookies[k] = v

    return cookies

def get_cookies_interactively():
    """دریافت ورودی چندخطی از ترمینال هنگام اجرای اسکریپت"""
    print("\n" + "=" * 70)
    print("📋 لطفاً متن هدرها یا کوکی‌های کپی شده را اینجا پیست کنید:")
    print("👉 (پس از پیست کردن، ۲ بار کلید Enter را بزنید یا کلمه DONE را تایپ کنید)")
    print("=" * 70)

    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == "DONE":
                break
            if line == "" and lines and lines[-1] == "":
                lines.pop()
                break
            lines.append(line)
        except EOFError:
            break

    raw_text = "\n".join(lines).strip()
    if not raw_text:
        # بررسی وجود متغیر پیش‌فرض در .env
        raw_text = os.getenv('COOKIE_STRING', '')

    cookies = parse_raw_cookie_dump(raw_text)
    return cookies

def build_session(cookies):
    """ایجاد نشست با کوکی‌ها و هدرهای تزریق شده"""
    session = requests.Session()
    session.headers.update(BASE_HEADERS)

    if not cookies:
        print("❌ هیچ کوکی معتبری یافت نشد!")
        sys.exit(1)

    cookie_header_parts = []
    print("\n📦 کوکی‌های شناسایی شده:")
    for k, v in cookies.items():
        print(f"  • {k}: {v[:25]}..." if len(v) > 25 else f"  • {k}: {v}")
        session.cookies.set(k, v, domain='.digikala.com')
        session.cookies.set(k, v, domain='seller.digikala.com')
        cookie_header_parts.append(f"{k}={v}")

    # اضافه کردن مستقیم به هدر جهت جلوگیری از نادیده گرفته شدن به خاطر تفاوت دامنه‌ها در requests
    session.headers['Cookie'] = "; ".join(cookie_header_parts)
    return session

# ===== SMS SENDER =====
def send_sms_with_capacity_code(capacity_code):
    if not SMS_API_KEY or not SMS_RECIPIENT:
        print("⚠️ تنظیمات پیامک (SMS_API_KEY / SMS_RECIPIENT) ست نشده است.")
        return False
    try:
        conn = http.client.HTTPSConnection("api2.ippanel.com")
        payload = json.dumps({
            "code": SMS_PATTERN_CODE,
            "sender": SMS_SENDER,
            "recipient": SMS_RECIPIENT,
            "variable": {"code": capacity_code}
        })
        headers = {
            'apikey': SMS_API_KEY,
            'Content-Type': 'application/json',
            'Cookie': SMS_COOKIE
        }
        conn.request("POST", "/api/v1/sms/pattern/normal/send", payload, headers)
        res = conn.getresponse()
        res.read()
        print(f"📱 پیامک با موفقیت ارسال شد. کد ظرفیت: {capacity_code}")
        return True
    except Exception as e:
        print(f"❌ خطا در ارسال پیامک: {e}")
        return False

# ===== CAPACITY PARSER & CHECKER =====
def generate_capacity_code(capacities):
    sorted_capacities = sorted(capacities, key=lambda x: x.get("starts_at", 0))
    code_digits = []
    hour_ranges = []
    for cap in sorted_capacities:
        digit = "1" if cap.get("disabled") is False else "0"
        code_digits.append(digit)
        start = cap.get('starts_at', 0)
        end = cap.get('ends_at', 0)
        hour_ranges.append(f"{start:02d}:00-{end:02d}:00")
    return "".join(code_digits), hour_ranges

def check_capacity(session):
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    date_param = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    url = f"https://seller.digikala.com/api/v2/packages/warehouses/{WAREHOUSE_ID}"
    params = {
        "delivery_type": "seller",
        "package_type": "order_fulfilment",
        "shipping_nature_id": 2,
        "date": date_param
    }
    
    # افزودن variants و counts در صورت وجود
    if os.getenv('VARIANTS'):
        params['variants'] = os.getenv('VARIANTS')
    if os.getenv('COUNTS'):
        params['counts'] = os.getenv('COUNTS')

    try:
        response = session.get(url, params=params, timeout=12)

        if response.status_code == 200:
            try:
                data = response.json()
            except json.JSONDecodeError:
                print("⚠️ پاسخ دریافت شد ولی ساختار JSON نیست (احتمال بلاک WAF یا صفحه ورود).")
                print(f"  پیش‌نمایش بدنه: {response.text[:200]!r}")
                return None, None, None, None, None

            capacities = data.get("data", {}).get("capacities", [])
            if not capacities:
                return [], [], [], "0000000", []

            capacity_code, hour_ranges = generate_capacity_code(capacities)
            available_slots = []
            all_available_hours = []

            for cap in capacities:
                if cap.get("disabled") is False:
                    slot_info = {"start": cap["starts_at"], "end": cap["ends_at"]}
                    all_available_hours.append(slot_info)
                    available_slots.append(slot_info)

            return available_slots, all_available_hours, capacities, capacity_code, hour_ranges
        elif response.status_code in (401, 403):
            print(f"❌ خطای احراز هویت (HTTP {response.status_code}) - کوکی‌ها منقضی شده‌اند.")
            return None, None, None, None, None
        else:
            print(f"⚠️ وضعیت پاسخ ناموفق: HTTP {response.status_code}")
            print(f"  پیش‌نمایش: {response.text[:200]!r}")
            return None, None, None, None, None

    except requests.exceptions.RequestException as e:
        print(f"⚠️ خطای شبکه: {e}")
        return None, None, None, None, None
    except Exception as e:
        print(f"⚠️ خطای غیرمنتظره: {e}")
        return None, None, None, None, None

def print_alert(all_available_hours, capacity_code, hour_ranges):
    print("\n" + "=" * 70)
    print("🚨🚨🚨 ظرفیت انبار باز شد! 🚨🚨🚨")
    print(f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n📊 وضعیت بازه‌ها:")
    code_with_hours = []
    for hour_range, digit in zip(hour_ranges, capacity_code):
        status = "✅" if digit == "1" else "❌"
        code_with_hours.append(f"{hour_range}({status})")
    print(f"   {' | '.join(code_with_hours)}")
    
    if all_available_hours:
        hours_list = [f"{slot['start']:02d}:00 تا {slot['end']:02d}:00" for slot in all_available_hours]
        print(f"\n📋 ساعات در دسترس:\n   {', '.join(hours_list)}")
    print("=" * 70)

    try:
        import winsound
        winsound.Beep(1200, 800)
        winsound.Beep(1600, 600)
    except Exception:
        print("\a")

# ===== MAIN EXECUTION =====
if __name__ == "__main__":
    extracted_cookies = get_cookies_interactively()
    SESSION = build_session(extracted_cookies)

    print("\n" + "=" * 70)
    print("🚀 مانیتورینگ خودکار ظرفیت انبار دیجی‌کالا آغاز شد...")
    print(f"📦 شناسه انبار (Warehouse ID): {WAREHOUSE_ID}")
    print(f"⏱️ بازه بررسی: هر {CHECK_INTERVAL} ثانیه")
    print(f"🛑 برای توقف: Ctrl + C")
    print("=" * 70 + "\n")

    last_alert_time = 0
    last_sms_code = None
    iteration_count = 0

    try:
        while True:
            iteration_count += 1
            result = check_capacity(SESSION)

            if result[0] is not None:
                available_slots, all_available_hours, all_capacities, capacity_code, hour_ranges = result
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] بررسی #{iteration_count} | وضعیت بازه‌ها: {capacity_code}")

                if available_slots:
                    current_time = time.time()
                    if capacity_code != last_sms_code:
                        print(f"\n🎉 ظرفیت جدید باز شد! کد: {capacity_code}")
                        send_sms_with_capacity_code(capacity_code)
                        last_sms_code = capacity_code
                        last_alert_time = current_time
                        print_alert(all_available_hours, capacity_code, hour_ranges)
                    elif current_time - last_alert_time > ALERT_COOLDOWN:
                        print_alert(all_available_hours, capacity_code, hour_ranges)
                        last_alert_time = current_time
                else:
                    if iteration_count % 10 == 0:
                        print(f"  ℹ️ انبار هنوز ظرفیت خالی ندارد...")

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n👋 اسکریپت توسط کاربر متوقف شد.")