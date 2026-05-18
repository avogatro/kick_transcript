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

def download_video(url="", quality="480p", start=None, end=None, output=None, audio_only=False, speed=1.0, subs=False, embed_subs=False, edit_subs=False, burn_subs=False, sub_lang="en", burn_color="white", whisper_subs=False, whisper_model="base", translate_to="English", translation_model="minimax-m2.7:cloud", burn_bg=False, local_video=None):
    """
    Downloads a video from a given URL using yt-dlp, or processes a local video.
    Supports clipping, quality selection, and audio-only extraction.
    """
    if local_video:
        if not os.path.exists(local_video):
            print(f"Error: Local video '{local_video}' not found.", file=sys.stderr)
            sys.exit(1)
        print(f"Skipping download. Using local video: {local_video}")
        actual_output = local_video
        downloaded_file = local_video
    else:
        if not url:
            print("Error: You must provide a URL or use --local-video.", file=sys.stderr)
            sys.exit(1)
        print(f"Downloading video from {url}...")
        
        command = ["yt-dlp"]
    
    if not local_video:
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
        command.extend(["--impersonate", "firefox"])
    
        if (subs or embed_subs or edit_subs or burn_subs) and not whisper_subs:
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
            
            # Use --exec output to find actual downloaded filename (important for dynamic extensions)
            if speed != 1.0 and os.path.exists(speed_file):
                with open(speed_file, 'r', encoding='utf-8') as f:
                    downloaded_file = f.read().strip().strip('"').strip("'")
                os.remove(speed_file)
            else:
                downloaded_file = actual_output
                
        except subprocess.CalledProcessError as e:
            print(f"\nError downloading video: {e}", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError:
            print("\nError: 'yt-dlp' is not installed or not in PATH.", file=sys.stderr)
            sys.exit(1)
                
    try:
            # Post-process for speed adjustments if required
            if speed != 1.0 and ('downloaded_file' in locals() and downloaded_file and os.path.exists(downloaded_file)):
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
            elif speed != 1.0:
                print(f"Could not find the downloaded file at '{downloaded_file}' to adjust speed.", file=sys.stderr)
    
            # Subtitle processing
            if subs or embed_subs or edit_subs or burn_subs:
                final_video_file = downloaded_file if ('downloaded_file' in locals() and downloaded_file and os.path.exists(downloaded_file)) else actual_output
                base, _ = os.path.splitext(final_video_file)
                
                processed_srt = f"{base}.processed.srt"
                has_valid_srt = False
                
                if whisper_subs:
                    try:
                        import whisper
                        import torch
                        
                        device = "cuda" if torch.cuda.is_available() else "cpu"
                        fp16_val = True if device == "cuda" else False
                        
                        print(f"\nLoading Whisper model '{whisper_model}' on {device.upper()} to transcribe '{final_video_file}'...")
                        model = whisper.load_model(whisper_model, device=device)
                        
                        # If translating to English, we can use Whisper's native task
                        task = "translate" if translate_to.lower() == "english" else "transcribe"
                        print(f"Running Whisper ({task})... This may take a while depending on hardware.")
                        
                        result = model.transcribe(final_video_file, fp16=fp16_val, task=task)
                        
                        # Generate SRT format directly from Whisper segments
                        original_whisper_srt = f"{base}.original.srt"
                        with open(original_whisper_srt, 'w', encoding='utf-8') as f:
                            for i, segment in enumerate(result.get("segments", [])):
                                start_str = format_seconds_to_srt_time(segment["start"])
                                end_str = format_seconds_to_srt_time(segment["end"])
                                text = segment["text"].strip()
                                f.write(f"{i+1}\n{start_str} --> {end_str}\n{text}\n\n")
                        
                        print(f"Whisper raw transcription saved to '{original_whisper_srt}'.")
                        import shutil
                        shutil.copy(original_whisper_srt, processed_srt)
                        has_valid_srt = True
                        
                        # Handle non-English translation using Ollama if needed
                        if translate_to.lower() != "english":
                            print(f"\nTranslating subtitles to {translate_to} using Ollama ({translation_model})...")
                            try:
                                import requests
                                
                                with open(processed_srt, 'r', encoding='utf-8') as f:
                                    srt_content = f.read()
                                    
                                blocks = [b for b in re.split(r'\n\s*\n', srt_content.strip()) if b.strip()]
                                translated_blocks = []
                                
                                for idx, block in enumerate(blocks):
                                    print(f"Translating block {idx+1}/{len(blocks)}...", end='\r')
                                    lines = block.split('\n')
                                    if len(lines) >= 3:
                                        index = lines[0]
                                        time_line = lines[1]
                                        text_to_translate = "\n".join(lines[2:])
                                        
                                        prompt = f"Translate the following subtitle text to {translate_to}. Output ONLY the raw translated text, nothing else.\n\nText: {text_to_translate}"
                                        payload = {
                                            "model": translation_model,
                                            "prompt": prompt,
                                            "stream": False
                                        }
                                        
                                        response = requests.post("http://localhost:11434/api/generate", json=payload)
                                        response.raise_for_status()
                                        translated_text = response.json().get("response", "").strip()
                                        
                                        if not translated_text:
                                            translated_text = text_to_translate
                                            
                                        translated_blocks.append(f"{index}\n{time_line}\n{translated_text}")
                                
                                print("\nOllama translation complete.")
                                with open(processed_srt, 'w', encoding='utf-8') as f:
                                    f.write("\n\n".join(translated_blocks) + "\n")
                                    
                            except Exception as e:
                                print(f"\nError during Ollama translation: {e}", file=sys.stderr)
                                print(f"Falling back to untranslated Whisper transcription.", file=sys.stderr)
                                
                    except ImportError:
                        print("Error: 'openai-whisper' is not installed. Run 'pip install openai-whisper'.", file=sys.stderr)
                        has_valid_srt = False
                else:
                    # yt-dlp sometimes appends .en.srt to the full filename including the extension, and sometimes to the base name.
                    possible_srt_paths = [
                        f"{actual_output}.{sub_lang}.srt", # e.g., video.mp4.en.srt
                        f"{base}.{sub_lang}.srt"           # e.g., video.en.srt
                    ]
                    
                    original_srt = None
                    for p in possible_srt_paths:
                        if os.path.exists(p):
                            original_srt = p
                            break
                    
                    if original_srt:
                        start_offset = parse_time_to_seconds(start)
                        end_seconds = parse_time_to_seconds(end) if end else None
                        
                        print(f"\nProcessing subtitles from '{original_srt}'...")
                        process_srt_file(original_srt, processed_srt, start_offset=start_offset, speed=speed, end_time=end_seconds)
                        has_valid_srt = True
                    else:
                        print(f"\nWarning: Subtitle file was not found (checked {possible_srt_paths}). No subtitles to process.", file=sys.stderr)
                
                if has_valid_srt:
                    
                    if edit_subs:
                        print(f"\n=======================================================")
                        print(f"Subtitles prepared at: {os.path.abspath(processed_srt)}")
                        print(f"Please open this file, make any manual corrections, and save it.")
                        input(f"Press Enter here when you are ready to continue embedding/burning... ")
                        print(f"=======================================================\n")
                    
                    if embed_subs or burn_subs:
                        if not audio_only:
                            print(f"{'Burning' if burn_subs else 'Embedding'} subtitles into video...")
                            temp_vid = f"{base}_subbed.mp4"
                            
                            if burn_subs:
                                srt_escaped = processed_srt.replace('\\', '/').replace("'", r"\'").replace(":", r"\:")
                                
                                # FFmpeg's libass uses BGR color codes: &HBBGGRR&
                                ass_colors = {
                                    "white": "&HFFFFFF&",
                                    "yellow": "&H00FFFF&",
                                    "green": "&H00FF00&",
                                    "cyan": "&HFFFF00&",
                                    "blue": "&HFF0000&",
                                    "magenta": "&HFF00FF&",
                                    "red": "&H0000FF&",
                                    "black": "&H000000&"
                                }
                                color_code = ass_colors.get(burn_color.lower(), "&HFFFFFF&")
                                
                                if burn_bg:
                                    # Solid black opaque background box
                                    style = f"PrimaryColour={color_code},BackColour=&H00000000&,BorderStyle=3,Outline=0,Shadow=0"
                                else:
                                    # Standard transparent background with black outline
                                    style = f"PrimaryColour={color_code},OutlineColour=&H000000&,BorderStyle=1,Outline=2,Shadow=0"
                                
                                ffmpeg_sub_cmd = [
                                    "ffmpeg", "-y", "-i", final_video_file,
                                    "-map", "0:v?", "-map", "0:a?",
                                    "-vf", f"subtitles='{srt_escaped}':force_style='{style}'",
                                    "-c:a", "copy", temp_vid
                                ]
                            else:
                                ffmpeg_sub_cmd = [
                                    "ffmpeg", "-y", "-i", final_video_file, "-i", processed_srt,
                                    "-map", "0:v?", "-map", "0:a?", "-map", "1:s",
                                    "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text", temp_vid
                                ]
                            try:
                                subprocess.run(ffmpeg_sub_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                                os.replace(temp_vid, final_video_file)
                                print(f"Subtitles {'burned' if burn_subs else 'embedded'} successfully.")
                            except subprocess.CalledProcessError:
                                print(f"Error embedding subtitles using ffmpeg.", file=sys.stderr)
                        else:
                            print(f"Skipping subtitle embedding because --audio-only was requested.")
                else:
                    print(f"\nWarning: Subtitle file was not found (checked {possible_srt_paths}). No subtitles to process.", file=sys.stderr)
                    
    except Exception as e:
        print(f"\nAn error occurred during processing: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description="Download strings and videos using yt-dlp with simple arguments.")
    parser.add_argument("url", nargs="?", help="The URL of the video to download. Optional if using --local-video.", default="")
    parser.add_argument("--local-video", help="Bypass yt-dlp and use a local video file instead.", default=None)
    parser.add_argument("--quality", help="Video quality (e.g., '480p', '1080p'). Default: 480p", default="480p")
    parser.add_argument("--start", help="Start time in seconds or HH:MM:SS format (e.g., 00:01:30).", default=None)
    parser.add_argument("--end", help="End time in seconds or HH:MM:SS format (e.g., 00:02:45).", default=None)
    parser.add_argument("--output", help="Output filename. If not provided, defaults to a safe, truncated video title.", default=None)
    parser.add_argument("--audio-only", help="Download audio only and bypass video download.", action="store_true")
    parser.add_argument("--speed", help="Speed to play the video/audio at (e.g., 1.5, 2.0). Default is 1.0 (normal).", type=float, default=1.0)
    parser.add_argument("--subs", help="Download subtitles (default lang: en).", action="store_true")
    parser.add_argument("--embed-subs", help="Automatically embed the subtitles into the final video file as soft subtitles.", action="store_true")
    parser.add_argument("--burn-subs", help="Hard burn the subtitles directly into the video pixels (re-encodes video).", action="store_true")
    parser.add_argument("--edit-subs", help="Pause the script to let you manually edit the downloaded .srt file before embedding/burning.", action="store_true")
    parser.add_argument("--sub-lang", help="Subtitle language to download. Default: en", default="en")
    parser.add_argument("--burn-color", help="Color of the text when using --burn-subs (e.g. 'yellow', 'white', 'green', 'red'). Default: white", default="yellow")
    parser.add_argument("--whisper-subs", help="Use local Whisper AI to transcribe audio instead of downloading yt-dlp subtitles.", action="store_true")
    parser.add_argument("--whisper-model", help="Whisper model to use (default: base).", default="base")
    parser.add_argument("--translate-to", help="Target language to translate subtitles to via Whisper/Ollama (default: English).", default="English")
    parser.add_argument("--translation-model", help="Ollama model for translation if not English.", default="minimax-m2.7:cloud")
    parser.add_argument("--burn-bg", help="Draw a solid black background behind burned subtitles (useful for hiding hardcoded text).", action="store_true")
    
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
        burn_subs=args.burn_subs,
        sub_lang=args.sub_lang,
        burn_color=args.burn_color,
        whisper_subs=args.whisper_subs,
        whisper_model=args.whisper_model,
        translate_to=args.translate_to,
        translation_model=args.translation_model,
        burn_bg=args.burn_bg,
        local_video=args.local_video
    )

if __name__ == "__main__":
    main()
