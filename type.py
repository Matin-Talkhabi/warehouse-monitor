import time
import pyautogui


while True:
    # دریافت ورودی از کاربر
    text = input("لطفاً متنی را وارد کنید: ")
    # text = '''curl -v https://ssh.matintalkhabi.ir/matintalkhabi -H "Upgrade: websocket" -H "Connection: Upgrade" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" -H "Sec-WebSocket-Version: 13" 2>&1 | tail -15'''
    text = '''systemctl daemon-reload
systemctl enable mtg
systemctl start mtg
'''
    time.sleep(2)

    # شمارش معکوس ۳ ثانیه
    print("۳ ثانیه تا تایپ متن...")

    # تایپ متن با pyautogui
    pyautogui.typewrite(text)
    print("✅ متن تایپ شد!")
# دریافت ورودی از کاربر
text = input("لطفاً متنی را وارد کنید: ")
# text = '''wget -N https://gitlab.com/fscarmen/warp/-/raw/main/menu.sh && bash menu.sh'''


time.sleep(2)

# شمارش معکوس ۳ ثانیه
print("۳ ثانیه تا تایپ متن...")
for i in range(3, 0, -1):
    print(i)
    time.sleep(1)

# تایپ متن با pyautogui
pyautogui.typewrite(text)
print("✅ متن تایپ شد!")


