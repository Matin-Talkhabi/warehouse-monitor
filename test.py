from openai import OpenAI

# کلید یکپارچه از داشبورد
UNIFIED_KEY = "freellmapi-ffc704679d187e321d84e92cee0126bb30bc9f103d4fb9e6"

client = OpenAI(
    base_url="http://127.0.0.1:31415/v1",  # ✅ پورت صحیح 31415
    api_key=UNIFIED_KEY,
)

try:
    response = client.chat.completions.create(
        model="auto",
        messages=[{"role": "user", "content": "سلام! به فارسی پاسخ بده."}]
    )
    print("پاسخ:", response.choices[0].message.content)
    print("ارائه‌دهنده:", response.headers.get("x-routed-via"))
except Exception as e:
    print(f"خطا: {e}")