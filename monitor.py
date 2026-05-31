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

def get_env_str(key, default=''):
    """Safely get string from environment variable"""
    value = os.getenv(key)
    if value is None or value == '':
        return default
    return value

# Use safe parsing for all values
WAREHOUSE_ID = get_env_int('WAREHOUSE_ID', 72)
CHECK_INTERVAL = get_env_int('CHECK_INTERVAL', 30)
ALERT_COOLDOWN = get_env_int('ALERT_COOLDOWN', 300)

# SMS Config - ALL from environment
SMS_PATTERN_CODE = get_env_str('SMS_PATTERN_CODE', 'kondvd1hhs5h3ld')
SMS_SENDER = get_env_str('SMS_SENDER', '3000505')
SMS_RECIPIENT = get_env_str('SMS_RECIPIENT', '')
SMS_API_KEY = get_env_str('SMS_API_KEY', '')
SMS_COOKIE = get_env_str('SMS_COOKIE', 'TS0177e476=0150a3e24e04874134dfd1bd5c65872f68c46a920efd859609d593ca9d48072507268ec821466d8aa3136e08191fcd1c9bfcc5abdd')

# Check if critical secrets are available
if not os.getenv('SELLER_API_ACCESS_TOKEN'):
    print("❌ ERROR: SELLER_API_ACCESS_TOKEN not found!")
    print("Please set it in GitHub Secrets or .env file")
    sys.exit(1)

print("="*70)
print("🔧 CONFIGURATION LOADED:")
print(f"   WAREHOUSE_ID: {WAREHOUSE_ID}")
print(f"   CHECK_INTERVAL: {CHECK_INTERVAL} seconds")
print(f"   ALERT_COOLDOWN: {ALERT_COOLDOWN} seconds")
print(f"   SELLER_API_ACCESS_TOKEN: {'✅ SET' if os.getenv('SELLER_API_ACCESS_TOKEN') else '❌ MISSING'}")
print(f"   VARIANTS: {os.getenv('VARIANTS', 'NOT SET')[:50]}...")
print(f"   COUNTS: {os.getenv('COUNTS', 'NOT SET')}")
print(f"   SMS_PATTERN_CODE: {SMS_PATTERN_CODE}")
print(f"   SMS_SENDER: {SMS_SENDER}")
print(f"   SMS_RECIPIENT: {SMS_RECIPIENT}")
print(f"   SMS_API_KEY: {'✅ SET' if SMS_API_KEY else '❌ MISSING'}")
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
    
    url = f"https://seller.digikala.com/api/v2/packages/warehouses/72?delivery_type=seller&date=2026-05-31T21%3A30%3A00.000Z&package_type=order_fulfilment&shipping_nature_id=2&variants=77054087%2C76261961%2C76225984&counts=1%2C1%2C1"
    params = BASE_PARAMS.copy()
    params["date"] = date_param
    
    try:
        response = requests.get(url, headers=HEADERS, cookies=COOKIES, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            capacities = data.get("data", {}).get("capacities", [])
            
            if not capacities:
                return [], [], [], "0000000", []
            
            capacity_code, hour_ranges = generate_capacity_code(capacities)
            
            available_slots = []
            all_available_hours = []
            
            for cap in capacities:
                if cap.get("disabled") == False:
                    slot_info = {"start": cap["starts_at"], "end": cap["ends_at"]}
                    all_available_hours.append(slot_info)
                    available_slots.append(slot_info)
            
            return available_slots, all_available_hours, capacities, capacity_code, hour_ranges
        else:
            print(f"⚠️ HTTP {response.status_code}")
            return None, None, None, None, None
            
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None, None, None, None, None

def print_alert(available_slots, all_available_hours, capacity_code, hour_ranges):
    """Print alert in English with all available time slots"""
    print("\n" + "="*70)
    print("🚨🚨🚨 WAREHOUSE CAPACITY AVAILABLE! 🚨🚨🚨")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n📊 CAPACITY CODE:")
    code_with_hours = []
    for hour_range, digit in zip(hour_ranges, capacity_code):
        status = "✅" if digit == "1" else "❌"
        code_with_hours.append(f"{hour_range}({digit}){status}")
    
    print(f"   {' | '.join(code_with_hours)}")
    print(f"   Full Code: {capacity_code}")
    
    if all_available_hours:
        print("\n📋 AVAILABLE HOURS:")
        hours_list = [f"{slot['start']:02d}:00-{slot['end']:02d}:00" for slot in all_available_hours]
        print(f"   {', '.join(hours_list)}")
    
    print("="*70)
    
    # Beep sound for Windows
    try:
        import winsound
        winsound.Beep(1000, 1000)
        winsound.Beep(1500, 500)
    except:
        print("\a")

# ===== MAIN LOOP WITH while True =====
if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 STARTING CONTINUOUS WAREHOUSE CAPACITY MONITOR...")
    print(f"📦 Warehouse ID: {WAREHOUSE_ID}")
    print(f"⏰ Checking every {CHECK_INTERVAL} seconds")
    print(f"💡 Alert cooldown: {ALERT_COOLDOWN} seconds")
    print(f"🕐 Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🖥️ Running on local computer (infinite loop)")
    print("❌ Press Ctrl+C to stop")
    print("="*70 + "\n")
    
    last_alert_time = 0
    last_sms_code = None
    iteration_count = 0
    
    try:
        while True:
            iteration_count += 1
            
            # Simple status update every 10 iterations
            if iteration_count % 10 == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 💓 Still running... (Check #{iteration_count})")
            
            result = check_capacity_now()
            
            if result[0] is not None:
                available_slots, all_available_hours, all_capacities, capacity_code, hour_ranges = result
                
                # Show current code (every iteration)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Code: {capacity_code}")
                
                if available_slots and len(available_slots) > 0:
                    current_time = time.time()
                    
                    # Check if code changed
                    if capacity_code != last_sms_code:
                        print(f"\n🎉 NEW CAPACITY DETECTED! Code changed to: {capacity_code}")
                        send_sms_with_capacity_code(capacity_code)
                        last_sms_code = capacity_code
                        last_alert_time = current_time
                        print_alert(available_slots, all_available_hours, capacity_code, hour_ranges)
                    elif current_time - last_alert_time > ALERT_COOLDOWN:
                        print_alert(available_slots, all_available_hours, capacity_code, hour_ranges)
                        last_alert_time = current_time
                    else:
                        # Just show available hours
                        if all_available_hours:
                            hours_str = ", ".join([f"{slot['start']:02d}:00" for slot in all_available_hours])
                            print(f"   ✅ Available: {hours_str}")
                else:
                    # No capacity - show occasionally to avoid spam
                    if iteration_count % 6 == 0:
                        # Show when next slots might be available
                        if hour_ranges:
                            print(f"   🕐 Warehouse hours: {', '.join(hour_ranges[:3])}...")
            else:
                print(f"⚠️ Failed to fetch data")
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped by user.")
        print(f"📊 Total checks: {iteration_count}")
        print(f"🕐 End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")