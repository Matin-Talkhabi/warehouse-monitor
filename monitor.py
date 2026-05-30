import requests
import time
from datetime import datetime
import pytz
import http.client
import json
import os
import sys

# ===== LOAD .env MANUALLY =====
def load_env_from_file():
    """Simple .env file loader"""
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
        print("✅ Loaded .env file successfully")
        return True
    except FileNotFoundError:
        print("⚠️ .env file not found, using GitHub Secrets")
        return False
    except Exception as e:
        print(f"⚠️ Error loading .env: {e}")
        return False

# Load .env file if exists (for local development)
load_env_from_file()

# ===== CONFIGURATION WITH SAFE PARSING =====
def get_env_int(key, default):
    """Safely get integer from environment variable"""
    value = os.getenv(key)
    if value is None or value == '':
        return default
    try:
        return int(value)
    except ValueError:
        print(f"⚠️ Warning: {key} value '{value}' is invalid, using default {default}")
        return default

# Use safe parsing for all integer values
WAREHOUSE_ID = get_env_int('WAREHOUSE_ID', 72)
CHECK_INTERVAL = get_env_int('CHECK_INTERVAL', 30)
ALERT_COOLDOWN = get_env_int('ALERT_COOLDOWN', 300)

# Check if critical secrets are available
if not os.getenv('SELLER_API_ACCESS_TOKEN'):
    print("❌ ERROR: SELLER_API_ACCESS_TOKEN not found!")
    print("Please set it in GitHub Secrets")
    sys.exit(1)

print("="*70)
print("🔧 CONFIGURATION LOADED:")
print(f"   WAREHOUSE_ID: {WAREHOUSE_ID}")
print(f"   CHECK_INTERVAL: {CHECK_INTERVAL} seconds")
print(f"   ALERT_COOLDOWN: {ALERT_COOLDOWN} seconds")
print(f"   SELLER_API_ACCESS_TOKEN: {'✅ SET' if os.getenv('SELLER_API_ACCESS_TOKEN') else '❌ MISSING'}")
print(f"   VARIANTS: {os.getenv('VARIANTS', 'NOT SET')[:50]}...")
print(f"   COUNTS: {os.getenv('COUNTS', 'NOT SET')}")
print(f"   SMS_API_KEY: {'✅ SET' if os.getenv('SMS_API_KEY') else '❌ MISSING'}")
print(f"   SMS_RECIPIENT: {os.getenv('SMS_RECIPIENT', 'NOT SET')}")
print("="*70)

# Cookies from environment
COOKIES = {
    "seller_api_access_token": os.getenv('SELLER_API_ACCESS_TOKEN', ''),
    "tracker_glob_new": os.getenv('TRACKER_GLOB_NEW', ''),
    "tracker_session": os.getenv('TRACKER_SESSION', ''),
    "TS01ddd49f": os.getenv('TS01DDD49F', ''),
    "TS018d011a": os.getenv('TS018D011A', ''),
}

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9,fa;q=0.8,en-GB;q=0.7,haw;q=0.6",
    "dnt": "1",
    "referer": "https://seller.digikala.com/pwa/package/package-creation-revamp",
    "user-agent": os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
}

BASE_PARAMS = {
    "delivery_type": "seller",
    "package_type": "order_fulfilment",
    "shipping_nature_id": 2,
    "variants": os.getenv('VARIANTS', ''),
    "counts": os.getenv('COUNTS', '')
}

# SMS Config
SMS_PATTERN_CODE = "kondvd1hhs5h3ld"
SMS_SENDER = "3000505"
SMS_RECIPIENT = os.getenv('SMS_RECIPIENT', '')
SMS_API_KEY = os.getenv('SMS_API_KEY', '')
SMS_COOKIE = "TS0177e476=0150a3e24e04874134dfd1bd5c65872f68c46a920efd859609d593ca9d48072507268ec821466d8aa3136e08191fcd1c9bfcc5abdd"

def send_sms_with_capacity_code(capacity_code):
    """Send SMS with capacity code"""
    if not SMS_API_KEY or not SMS_RECIPIENT:
        print("⚠️ SMS not configured - skipping")
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
        data = res.read()
        print(f"📱 SMS sent successfully with code: {capacity_code}")
        return True
    except Exception as e:
        print(f"❌ Failed to send SMS: {e}")
        return False

def generate_capacity_code(capacities):
    """Generate dynamic capacity code based on actual hours"""
    sorted_capacities = sorted(capacities, key=lambda x: x["starts_at"])
    code_digits = []
    hour_ranges = []
    
    for cap in sorted_capacities:
        digit = "1" if cap.get("disabled") == False else "0"
        code_digits.append(digit)
        hour_ranges.append(f"{cap['starts_at']:02d}:00-{cap['ends_at']:02d}:00")
    
    return "".join(code_digits), hour_ranges

def get_current_tehran_time():
    tehran_tz = pytz.timezone('Asia/Tehran')
    now_tehran = datetime.now(tehran_tz)
    return now_tehran.replace(microsecond=0)

def check_capacity_now():
    now = get_current_tehran_time()
    
    # Use the working format
    date_param = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    
    url = f"https://seller.digikala.com/api/v2/packages/warehouses/{WAREHOUSE_ID}"
    params = BASE_PARAMS.copy()
    params["date"] = date_param
    
    try:
        print(f"🔍 Checking capacity for date: {date_param}")
        response = requests.get(url, headers=HEADERS, cookies=COOKIES, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            capacities = data.get("data", {}).get("capacities", [])
            
            if not capacities:
                print("⚠️ No capacity data received")
                return [], [], [], "0000000", []
            
            capacity_code, hour_ranges = generate_capacity_code(capacities)
            print(f"📊 Capacity code: {capacity_code}")
            
            available_slots = []
            all_available_hours = []
            
            for cap in capacities:
                if cap.get("disabled") == False:
                    slot_info = {"start": cap["starts_at"], "end": cap["ends_at"]}
                    all_available_hours.append(slot_info)
                    available_slots.append(slot_info)
            
            return available_slots, all_available_hours, capacities, capacity_code, hour_ranges
        else:
            print(f"⚠️ HTTP {response.status_code}: {response.text[:100]}")
            return None, None, None, None, None
            
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None, None, None, None, None

# ===== MAIN - One time check for GitHub Actions =====
if __name__ == "__main__":
    print("\n🚀 CHECKING WAREHOUSE CAPACITY...")
    print(f"📦 Warehouse ID: {WAREHOUSE_ID}")
    print("-" * 50)
    
    result = check_capacity_now()
    
    if result[0] is not None:
        available_slots, all_available_hours, all_capacities, capacity_code, hour_ranges = result
        
        if available_slots and len(available_slots) > 0:
            print(f"\n✅✅✅ CAPACITY AVAILABLE! ✅✅✅")
            print(f"📊 Code: {capacity_code}")
            
            # Show which hours are available
            available_hours = []
            for hour_range, digit in zip(hour_ranges, capacity_code):
                if digit == "1":
                    available_hours.append(hour_range)
            
            if available_hours:
                print(f"🕐 Available hours: {', '.join(available_hours)}")
            
            # Send SMS
            print("\n📱 Sending SMS alert...")
            send_sms_with_capacity_code(capacity_code)
        else:
            print(f"\n❌ No capacity available")
            print(f"📊 Current code: {capacity_code}")
            
            # Show schedule
            if hour_ranges:
                print(f"🕐 Warehouse hours: {', '.join(hour_ranges)}")
    else:
        print("❌ Failed to fetch capacity data")
    
    print("\n✅ Check completed")