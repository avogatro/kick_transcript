import argparse
import subprocess
import sys
import os

def download_video(url, quality="480p", start=None, end=None, output=None, audio_only=False, speed=1.0):
    """
    Downloads a video from a given URL using yt-dlp.
    Supports clipping, quality selection, and audio-only extraction.
    """
    print(f"Downloading video from {url}...")
    
    command = ["yt-dlp"]
    
    # 1. Handle Audio Only or Quality
    if audio_only:
        command.extend([
            "-f", "bestaudio/best",
            "--extract-audio"
        ])
    else:
        # Parse quality, e.g., "480p" -> "480"
        height = quality.replace('p', '') if quality.endswith('p') else quality
        command.extend([
            # Use -S to specify max height. It's the modern way in yt-dlp for sorting formats
            "-S", f"height:{height}",
            # Force output to be merged/remuxed into mp4 format
            "--merge-output-format", "mp4"
        ])

    # 2. Handle Output Filename
    final_output = output

    if not final_output:
        # To determine the autoname before downloading (to handle existence check), we do a dry-run
        # replicate format flags so yt-dlp knows the exact extension 
        dry_run_cmd = ["yt-dlp", "--print", "filename", "-o", "%(title).60B.%(ext)s", "--restrict-filenames"]
        if audio_only:
            dry_run_cmd.extend(["-f", "bestaudio/best", "--extract-audio"])
        else:
            height = quality.replace('p', '') if quality.endswith('p') else quality
            dry_run_cmd.extend(["-S", f"height:{height}", "--merge-output-format", "mp4"])
        dry_run_cmd.append(url)
        
        print("Resolving final filename...")
        try:
            out = subprocess.check_output(dry_run_cmd, stderr=subprocess.DEVNULL)
            final_output = out.decode('utf-8').strip()
        except subprocess.CalledProcessError:
            # Fallback if dry run fails
            final_output = "video.mp4"

    # Auto-number if file exists (append 2, 3, 4...)
    base, ext = os.path.splitext(final_output)
    counter = 2
    actual_output = final_output
    while os.path.exists(actual_output):
        actual_output = f"{base} {counter}{ext}"
        counter += 1

    command.extend(["-o", actual_output])

    # 3. Handle Clipping
    if start and end:
        print(f"Clipping section from {start} to {end}...")
        command.extend(["--download-sections", f"*{start}-{end}"])
    elif start or end:
        print("Warning: Both --start and --end must be provided to clip the video. Downloading the full video instead.")

    # 4. Attempt to bypass Cloudflare and similar blocks like in summarize_video
    command.extend(["--impersonate", "chrome"])

    command.append(url)
    
    speed_file = ".dl_info.txt"
    if speed != 1.0:
        if os.path.exists(speed_file):
            os.remove(speed_file)
        # Use --exec to write the final filename to a temporary text file so we can read it back inside Python
        command.extend(["--exec", f"echo %(filepath)q > {speed_file}"])
    
    # Print the command for debugging purposes
    cmd_str = ' '.join(command)
    print(f"Running command: {cmd_str}\n")
    
    try:
        subprocess.run(command, check=True)
        print("\nDownload completed successfully.")
        
        # Post-process for speed adjustments if required
        if speed != 1.0:
            if os.path.exists(speed_file):
                with open(speed_file, 'r', encoding='utf-8') as f:
                    downloaded_file = f.read().strip().strip('"').strip("'")
                os.remove(speed_file)
                
                if downloaded_file and os.path.exists(downloaded_file):
                    print(f"\nAdjusting speed to {speed}x... This may take a while as it re-encodes the file using ffmpeg.")
                    name, ext = os.path.splitext(downloaded_file)
                    temp_file = f"{name}_speed{ext}"
                    
                    ffmpeg_cmd = ["ffmpeg", "-y", "-i", downloaded_file]
                    
                    # ffmpeg requires chaining 'atempo' filters for audio speeds outside the 0.5 - 2.0 range
                    filters = []
                    s = speed
                    while s > 2.0:
                        filters.append("atempo=2.0")
                        s /= 2.0
                    while s < 0.5:
                        filters.append("atempo=0.5")
                        s /= 0.5
                    filters.append(f"atempo={s}")
                    af_str = ",".join(filters)
                    
                    if audio_only:
                        ffmpeg_cmd.extend(["-filter:a", af_str])
                    else:
                        ffmpeg_cmd.extend([
                            "-filter:v", f"setpts={1.0/speed}*PTS", 
                            "-filter:a", af_str
                        ])
                    
                    ffmpeg_cmd.append(temp_file)
                    try:
                        # Hide the noisy ffmpeg output unless it crashes
                        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                        os.replace(temp_file, downloaded_file)
                        print(f"Speed adjustment complete. Overwrote '{downloaded_file}'.")
                    except subprocess.CalledProcessError as e:
                        print(f"Error during speed adjustment: ffmpeg failed.", file=sys.stderr)
                else:
                    print(f"Could not find the downloaded file at '{downloaded_file}' to adjust speed.", file=sys.stderr)
            else:
                print("Could not find downloaded file info to adjust speed.", file=sys.stderr)

    except subprocess.CalledProcessError as e:
        print(f"\nError downloading video: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("\nError: 'yt-dlp' is not installed or not in PATH.", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Download strings and videos using yt-dlp with simple arguments.")
    parser.add_argument("url", help="The URL of the video to download.")
    parser.add_argument("--quality", help="Video quality (e.g., '480p', '1080p'). Default: 480p", default="480p")
    parser.add_argument("--start", help="Start time in seconds or HH:MM:SS format (e.g., 00:01:30).", default=None)
    parser.add_argument("--end", help="End time in seconds or HH:MM:SS format (e.g., 00:02:45).", default=None)
    parser.add_argument("--output", help="Output filename. If not provided, defaults to a safe, truncated video title.", default=None)
    parser.add_argument("--audio-only", help="Download audio only and bypass video download.", action="store_true")
    parser.add_argument("--speed", help="Speed to play the video/audio at (e.g., 1.5, 2.0). Default is 1.0 (normal).", type=float, default=1.0)
    
    args = parser.parse_args()
    
    download_video(
        url=args.url,
        quality=args.quality,
        start=args.start,
        end=args.end,
        output=args.output,
        audio_only=args.audio_only,
        speed=args.speed
    )

if __name__ == "__main__":
    main()
