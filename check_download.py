import os
import sys
import subprocess
import shutil
import urllib.request
import json

# Ensure stdout supports UTF-8 on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def print_header(title):
    print(f"\n==================================================")
    print(f" {title}")
    print(f"==================================================")

def check_ytdlp():
    print_header("1. Checking yt-dlp Status")
    yt_dlp_cmd = shutil.which("yt-dlp") or "yt-dlp"
    try:
        res = subprocess.run([yt_dlp_cmd, "--version"], capture_output=True, text=True, check=True)
        installed_ver = res.stdout.strip()
        print(f"[OK] yt-dlp installed! Version: {installed_ver}")
    except Exception as e:
        print(f"[FAIL] Could not run yt-dlp: {e}")
        print("  -> Solution: Install yt-dlp using 'pip install -U yt-dlp'")
        return False

    # Check for latest release on PyPI
    try:
        url = "https://pypi.org/pypi/yt-dlp/json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            latest_ver = data["info"]["version"]
            if installed_ver != latest_ver:
                print(f"[WARN] Latest yt-dlp version on PyPI is {latest_ver} (you have {installed_ver}).")
                print("  -> YouTube updates often break older versions. Run: yt-dlp -U or pip install -U yt-dlp")
            else:
                print(f"[OK] You are running the latest PyPI release of yt-dlp ({latest_ver}).")
    except Exception as e:
        print(f"[NOTE] Could not check PyPI for latest yt-dlp version: {e}")

    return True

def check_ffmpeg():
    print_header("2. Checking FFmpeg Status")
    
    # Check .env first
    custom_ffmpeg = None
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    key, val = line.strip().split("=", 1)
                    if key.strip() == "CUSTOM_FFMPEG":
                        custom_ffmpeg = val.strip().strip('"').strip("'")
                        break
                        
    if not custom_ffmpeg:
        custom_ffmpeg = os.environ.get("CUSTOM_FFMPEG")

    ffmpeg_exe = "ffmpeg"
    ffmpeg_dir = None
    if custom_ffmpeg and os.path.exists(custom_ffmpeg):
        ffmpeg_dir = custom_ffmpeg
        ffmpeg_exe = os.path.join(custom_ffmpeg, "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
        print(f"[OK] Custom FFmpeg directory found in .env: {custom_ffmpeg}")
    else:
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            ffmpeg_exe = system_ffmpeg
            print(f"[OK] System FFmpeg found on PATH: {system_ffmpeg}")
        else:
            print("[FAIL] FFmpeg executable not found!")
            print("  -> Solution: Set CUSTOM_FFMPEG in .env or add FFmpeg to system PATH.")
            return False, None

    try:
        res = subprocess.run([ffmpeg_exe, "-version"], capture_output=True, text=True, check=True)
        first_line = res.stdout.split('\n')[0]
        print(f"[OK] FFmpeg binary functional! ({first_line})")
        return True, ffmpeg_dir
    except Exception as e:
        print(f"[FAIL] FFmpeg found at {ffmpeg_exe} but failed to run: {e}")
        return False, None

def check_js_engine():
    print_header("3. Checking JS Engine / Challenge Solver")
    for engine in ["deno", "node", "quickjs"]:
        path = shutil.which(engine)
        if path:
            print(f"[OK] Found JS Engine: {engine} ({path})")
            print("  -> YouTube JS challenges (n-sig) can be solved natively.")
            return True
    print("[WARN] No local JS engine (deno, node, quickjs) found in PATH.")
    print("  -> yt-dlp will fallback to remote components ('--remote-components ejs:github').")
    return True

def check_cookies():
    print_header("4. Checking YouTube Cookies")
    cookie_file = "cookies-youtube-com.txt"
    if os.path.exists(cookie_file):
        size = os.path.getsize(cookie_file)
        print(f"[OK] Cookie file '{cookie_file}' exists ({size} bytes).")
    else:
        print(f"[WARN] Cookie file '{cookie_file}' not found.")
        print("  -> yt-dlp will attempt to extract cookies from browser.")

def check_test_download(ffmpeg_dir):
    print_header("5. Testing Live YouTube Download & FFmpeg Merging")
    test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    test_out = "_test_dl_check.mp4"
    
    cmd = [
        "yt-dlp",
        "--downloader-args", "ffmpeg:-nostdin",
        "--postprocessor-args", "ffmpeg:-nostdin",
        "--remote-components", "ejs:github",
        "--download-sections", "*00:00:00-00:00:02",
        "--force-keyframes-at-cuts",
        "-S", "height:480,vcodec:h264",
        "--merge-output-format", "mp4",
        "--impersonate", "firefox",
        "--force-overwrite",
        "-o", test_out
    ]
    
    if os.path.exists("cookies-youtube-com.txt"):
        cmd.extend(["--cookies", "cookies-youtube-com.txt"])
    else:
        cmd.extend(["--cookies-from-browser", "firefox"])
        
    if ffmpeg_dir:
        cmd.extend(["--ffmpeg-location", ffmpeg_dir])
        
    cmd.append(test_url)
    
    print(f"Running test download command (2-second slice)...")
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        if res.returncode == 0 and os.path.exists(test_out):
            file_size = os.path.getsize(test_out)
            print(f"[SUCCESS] Download & FFmpeg muxing succeeded! (Test video created: {file_size} bytes)")
            try:
                os.remove(test_out)
            except Exception:
                pass
            return True
        else:
            print("[FAIL] Test download failed!")
            print("\n--- Output details ---")
            print((res.stderr or res.stdout).strip())
            print("----------------------")
            
            stderr_text = (res.stderr or "") + (res.stdout or "")
            stderr_lower = stderr_text.lower()
            if "403" in stderr_lower or "forbidden" in stderr_lower:
                print("\n[DIAGNOSIS] HTTP 403 Forbidden detected!")
                print("  -> YouTube updated player code or anti-bot mechanism.")
                print("  -> Solution 1: Update yt-dlp by running: yt-dlp -U")
                print("  -> Solution 2: Refresh 'cookies-youtube-com.txt' (run youtube_login.py or re-export browser cookies).")
            elif "ffmpeg" in stderr_lower:
                print("\n[DIAGNOSIS] FFmpeg error detected during stream post-processing!")
                print("  -> Check if FFmpeg path in .env is correct and binaries are valid.")
            else:
                print("\n[DIAGNOSIS] Stream extraction error.")
                print("  -> Try updating yt-dlp: yt-dlp -U")
            return False
    except subprocess.TimeoutExpired:
        print("[FAIL] Test download timed out (>35s). Network or stream stall.")
        return False
    except Exception as e:
        print(f"[FAIL] Exception during test download: {e}")
        return False

def main():
    print("==================================================")
    print("      YouTube Downloader & FFmpeg Health Check     ")
    print("==================================================")
    
    ytdlp_ok = check_ytdlp()
    ffmpeg_ok, ffmpeg_dir = check_ffmpeg()
    check_js_engine()
    check_cookies()
    
    if not ytdlp_ok:
        print("\n[RESULT] yt-dlp is missing or broken. Cannot perform live test.")
        sys.exit(1)
        
    if not ffmpeg_ok:
        print("\n[RESULT] FFmpeg is missing or broken. Merging/processing will fail.")
    
    dl_ok = check_test_download(ffmpeg_dir)
    
    print_header("SUMMARY")
    if ytdlp_ok and ffmpeg_ok and dl_ok:
        print("[ALL CHECKS PASSED] Download workflow is operating normally!")
    else:
        print("[WARNING] One or more checks failed. Review the recommendations above.")

if __name__ == "__main__":
    main()
