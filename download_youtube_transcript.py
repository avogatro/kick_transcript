import argparse
import subprocess
import sys
import os

def download_transcript(url, lang="en", output_dir=".", cookies_file=None):
    """
    Downloads the transcript/subtitles for a given YouTube URL using yt-dlp.
    """
    # Base command for yt-dlp
    command = [
        "yt-dlp",
        "--skip-download",          # Do not download the video
        "--write-subs",             # Write subtitle file
        "--write-auto-subs",        # Write auto-generated subtitle if normal is not available
        "--sub-langs", lang,        # Choose language
        "--convert-subs", "srt",    # Convert to SRT format
        "-o", os.path.join(output_dir, "%(title)s.%(ext)s")
    ]
    
    # Handle cookies for age-restricted or premium videos
    if cookies_file and os.path.exists(cookies_file):
        command.extend(["--cookies", cookies_file])
    else:
        # Fallback to existing cookies file in directory or browser cookies
        if os.path.exists("cookies-youtube-com.txt"):
            command.extend(["--cookies", "cookies-youtube-com.txt"])
        elif os.path.exists("youtube_cookies.txt"):
            command.extend(["--cookies", "youtube_cookies.txt"])
        else:
            # You can change this to 'chrome', 'edge', etc. based on what you use
            command.extend(["--cookies-from-browser", "firefox"])

    # Append the URL
    command.append(url)

    print(f"Running command: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
        print("Transcript downloaded successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error downloading transcript: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Download YouTube video transcript using yt-dlp.")
    parser.add_argument("url", help="The URL of the YouTube video.")
    parser.add_argument("--lang", help="Language code for subtitles (default: en).", default="en")
    parser.add_argument("--output-dir", help="Directory to save the transcript (default: current directory).", default=".")
    parser.add_argument("--cookies", help="Path to a cookies.txt file.", default=None)
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        
    download_transcript(args.url, args.lang, args.output_dir, args.cookies)

if __name__ == "__main__":
    main()
