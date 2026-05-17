import argparse
import subprocess
import sys
import os
import re

def parse_time_to_seconds(time_str):
    if not time_str:
        return 0.0
    if isinstance(time_str, (int, float)):
        return float(time_str)
    if time_str.isdigit():
        return float(time_str)
    parts = time_str.split(':')
    if len(parts) == 3: # hh:mm:ss
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2: # mm:ss
        return float(parts[0]) * 60 + float(parts[1])
    return 0.0

def format_seconds_to_srt_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def process_srt_file(input_file, output_file, start_offset=0.0, speed=1.0, end_time=None):
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.split(r'\n\s*\n', content.strip())
    new_blocks = []
    index = 1

    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 2:
            time_line = lines[1]
            match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', time_line)
            if match:
                start_str, end_str = match.groups()
                
                def srt_to_sec(s):
                    h, m, s_ms = s.split(':')
                    s, ms = s_ms.split(',')
                    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0

                start_sec = srt_to_sec(start_str)
                end_sec = srt_to_sec(end_str)

                # 1. Apply start offset
                start_sec -= start_offset
                end_sec -= start_offset

                # 2. Filter out blocks before 0 or after end_time
                if end_sec <= 0:
                    continue
                if start_sec < 0:
                    start_sec = 0
                    
                if end_time is not None:
                    duration = end_time - start_offset
                    if start_sec >= duration:
                        continue
                    if end_sec > duration:
                        end_sec = duration

                # 3. Apply speed
                start_sec /= speed
                end_sec /= speed

                new_start_str = format_seconds_to_srt_time(start_sec)
                new_end_str = format_seconds_to_srt_time(end_sec)

                new_time_line = f"{new_start_str} --> {new_end_str}"
                
                new_block = f"{index}\n{new_time_line}\n" + "\n".join(lines[2:])
                new_blocks.append(new_block)
                index += 1

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(new_blocks) + "\n")

def download_video(url, quality="480p", start=None, end=None, output=None, audio_only=False, speed=1.0, subs=False, embed_subs=False, edit_subs=False, sub_lang="en"):
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
            "-S", f"height:{height},vcodec:h264",
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
            dry_run_cmd.extend(["-S", f"height:{height},vcodec:h264", "--merge-output-format", "mp4"])
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
        command.extend([
            "--download-sections", f"*{start}-{end}",
            "--force-keyframes-at-cuts"
        ])
    elif start or end:
        print("Warning: Both --start and --end must be provided to clip the video. Downloading the full video instead.")

    # 4. Attempt to bypass Cloudflare and similar blocks like in summarize_video
    command.extend(["--impersonate", "chrome"])

    if subs or embed_subs or edit_subs:
        command.extend([
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", sub_lang,
            "--convert-subs", "srt"
        ])

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

        # Subtitle processing
        if subs or embed_subs or edit_subs:
            final_video_file = downloaded_file if ('downloaded_file' in locals() and downloaded_file and os.path.exists(downloaded_file)) else actual_output
            base, _ = os.path.splitext(actual_output)
            original_srt = f"{base}.{sub_lang}.srt"
            
            if os.path.exists(original_srt):
                processed_srt = f"{base}.processed.srt"
                start_offset = parse_time_to_seconds(start)
                end_seconds = parse_time_to_seconds(end) if end else None
                
                print(f"\nProcessing subtitles from '{original_srt}'...")
                process_srt_file(original_srt, processed_srt, start_offset=start_offset, speed=speed, end_time=end_seconds)
                
                if edit_subs:
                    print(f"\n=======================================================")
                    print(f"Subtitles downloaded and prepared at: {os.path.abspath(processed_srt)}")
                    print(f"Please open this file, make any manual corrections, and save it.")
                    input(f"Press Enter here when you are ready to continue embedding... ")
                    print(f"=======================================================\n")
                
                if embed_subs or edit_subs:
                    if not audio_only:
                        print(f"Embedding subtitles into video...")
                        temp_vid = f"{base}_subbed.mp4"
                        ffmpeg_sub_cmd = [
                            "ffmpeg", "-y", "-i", final_video_file, "-i", processed_srt,
                            "-c", "copy", "-c:s", "mov_text", temp_vid
                        ]
                        try:
                            subprocess.run(ffmpeg_sub_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                            os.replace(temp_vid, final_video_file)
                            print(f"Subtitles embedded successfully.")
                        except subprocess.CalledProcessError:
                            print(f"Error embedding subtitles using ffmpeg.", file=sys.stderr)
                    else:
                        print(f"Skipping subtitle embedding because --audio-only was requested.")
            else:
                print(f"\nWarning: Subtitle file '{original_srt}' was not found. No subtitles to process.", file=sys.stderr)

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
    parser.add_argument("--subs", help="Download subtitles (default lang: en).", action="store_true")
    parser.add_argument("--embed-subs", help="Automatically embed the subtitles into the final video file.", action="store_true")
    parser.add_argument("--edit-subs", help="Pause the script to let you manually edit the downloaded .srt file before embedding.", action="store_true")
    parser.add_argument("--sub-lang", help="Subtitle language to download. Default: en", default="en")
    
    args = parser.parse_args()
    
    download_video(
        url=args.url,
        quality=args.quality,
        start=args.start,
        end=args.end,
        output=args.output,
        audio_only=args.audio_only,
        speed=args.speed,
        subs=args.subs,
        embed_subs=args.embed_subs,
        edit_subs=args.edit_subs,
        sub_lang=args.sub_lang
    )

if __name__ == "__main__":
    main()
