import requests
import time
from datetime import datetime, timedelta
import pytz
import http.client
import json
import os
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ===== CONFIGURATION FROM ENV =====
WAREHOUSE_ID = int(os.getenv('WAREHOUSE_ID', '71'))
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '10'))
ALERT_COOLDOWN = int(os.getenv('ALERT_COOLDOWN', '10'))

# Cookies from .env
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
    
    # فقط از فرمتی استفاده کن که جواب داده (با Z در آخر)
    date_param = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    
    url = f"https://seller.digikala.com/api/v2/packages/warehouses/{WAREHOUSE_ID}"
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
            print(f"⚠️ HTTP {response.status_code}: {response.text[:100]}")
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
    
    # فقط ساعات با ظرفیت را نشان بده
    available_hours_only = [f"{hour_range}({digit})✅" for hour_range, digit in zip(hour_ranges, capacity_code) if digit == "1"]
    
    if available_hours_only:
        print(f"   Available: {' | '.join(available_hours_only)}")
    else:
        print(f"   No available hours")
    
    print(f"   Full Code: {capacity_code}")
    
    if all_available_hours:
        print("\n📋 AVAILABLE HOURS:")
        hours_list = [f"{slot['start']:02d}:00-{slot['end']:02d}:00" for slot in all_available_hours]
        print(f"   {', '.join(hours_list)}")
    
    print("="*70)

# ===== MAIN LOOP =====
if __name__ == "__main__":
    print("\n🚀 STARTING WAREHOUSE CAPACITY MONITOR...")
    print(f"📦 Warehouse ID: {WAREHOUSE_ID}")
    print(f"⏰ Checking every {CHECK_INTERVAL} seconds")
    print(f"🕐 Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("💡 Will alert when ANY capacity becomes available")
    print("❌ Press Ctrl+C to stop")
    print("="*70)
    
    last_sms_code = None
    iteration_count = 0
    
    try:
        while True:
            iteration_count += 1
            
            # Simple status update
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking... (#{iteration_count})")
            
            result = check_capacity_now()
            
            if result[0] is not None:
                available_slots, all_available_hours, all_capacities, capacity_code, hour_ranges = result
                
                # Show current code
                print(f"   Code: {capacity_code}")
                
                if available_slots and len(available_slots) > 0:
                    # Has capacity
                    if capacity_code != last_sms_code:
                        print(f"\n🎉 NEW CAPACITY DETECTED! Code changed to: {capacity_code}")
                        send_sms_with_capacity_code(capacity_code)
                        last_sms_code = capacity_code
                        print_alert(available_slots, all_available_hours, capacity_code, hour_ranges)
                    else:
                        print(f"   ✅ Capacity available (already alerted)")
                        # Still show available hours
                        if all_available_hours:
                            hours_str = ", ".join([f"{slot['start']:02d}:00" for slot in all_available_hours])
                            print(f"   📋 Available: {hours_str}")
                else:
                    # No capacity
                    if any(d == '1' for d in capacity_code):
                        # This shouldn't happen
                        pass
                    else:
                        if iteration_count % 6 == 0:  # هر 3 دقیقه یکبار (چون هر 30 ثانیه)
                            print(f"   ❌ No capacity available (code: {capacity_code})")
                            # Show when next slots might be available
                            if hour_ranges:
                                print(f"   🕐 Check hours: {', '.join(hour_ranges)}")
            else:
                print(f"   ⚠️ Failed to get data")
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped.")
        print(f"📊 Total checks: {iteration_count}")