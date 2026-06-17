from playwright.sync_api import sync_playwright
import time
import os

COOKIES_FILE = "cookies-youtube-com.txt"

def save_cookies_netscape(cookies, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# http://curl.haxx.se/rfc/cookie_spec.html\n")
        f.write("# This is a generated file!  Do not edit.\n\n")
        for cookie in cookies:
            domain = cookie['domain']
            domain_specified = "TRUE" if domain.startswith('.') else "FALSE"
            path = cookie['path']
            secure = "TRUE" if cookie['secure'] else "FALSE"
            expires = str(int(cookie['expires'])) if cookie['expires'] > 0 else "0"
            name = cookie['name']
            value = cookie['value']
            f.write(f"{domain}\t{domain_specified}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")

def login_youtube():
    print("Launching Playwright browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"]
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        print("Navigating to YouTube...")
        page.goto("https://www.youtube.com")
        
        print("\n" + "="*50)
        print("ACTION REQUIRED:")
        print("1. If prompted, solve the CAPTCHA or 'Confirm you are not a bot'.")
        print("2. Alternatively, log in to your Google Account (a dummy account is recommended).")
        print("3. WAIT until the homepage is fully loaded and you're confirmed as human.")
        input("Press [ENTER] here in the console to continue and save cookies...")
        print("="*50 + "\n")
        
        cookies = context.cookies()
        save_cookies_netscape(cookies, COOKIES_FILE)
        print(f"Saved {len(cookies)} cookies to {COOKIES_FILE}!")
        browser.close()

if __name__ == "__main__":
    login_youtube()
