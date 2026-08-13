import argparse
import sys
import os
import re
import shutil
from kick_tools.utils import parse_time_to_seconds, format_timestamp
from kick_tools.downloader import MediaDownloader
from kick_tools.transcriber import WhisperTranscriber, generate_srt
from kick_tools.llm import OllamaClient

def process_srt_file(input_file, output_file, start_offset=0.0, speed=1.0, end_time=None):
    # This remains here as it's specific to SRT file post-processing for speed/offset
    # unless it's used elsewhere. For now, let's keep it here but clean it up.
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

                start_sec -= start_offset
                end_sec -= start_offset

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

                start_sec /= speed
                end_sec /= speed

                new_start_str = format_timestamp(start_sec, include_ms=True)
                new_end_str = format_timestamp(end_sec, include_ms=True)
                new_time_line = f"{new_start_str} --> {new_end_str}"
                
                new_block = f"{index}\n{new_time_line}\n" + "\n".join(lines[2:])
                new_blocks.append(new_block)
                index += 1

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(new_blocks) + "\n")

def run_downloader(args):
    downloader = MediaDownloader()
    
    if args.local_video:
        if not os.path.exists(args.local_video):
            print(f"Error: Local video '{args.local_video}' not found.", file=sys.stderr)
            sys.exit(1)
        downloaded_file = args.local_video
    else:
        if not args.url:
            print("Error: You must provide a URL or use --local-video.", file=sys.stderr)
            sys.exit(1)
        
        # Simplified output resolution for refactor
        download_subs = not args.whisper_subs and (args.subs or args.embed_subs or args.edit_subs or args.burn_subs)
        downloaded_file = downloader.download(
            url=args.url,
            quality=args.quality,
            start=args.start,
            end=args.end,
            output=args.output,
            audio_only=args.audio_only,
            impersonate="firefox",
            download_subs=download_subs,
            sub_lang=args.sub_lang
        )
        if not downloaded_file:
            sys.exit(1)

    # 1. Speed Adjustment
    if args.speed != 1.0:
        downloaded_file = downloader.adjust_speed(downloaded_file, args.speed, audio_only=args.audio_only)

    # 2. Subtitle processing
    if args.subs or args.embed_subs or args.edit_subs or args.burn_subs:
        base, _ = os.path.splitext(downloaded_file)
        processed_srt = f"{base}.processed.srt"
        has_valid_srt = False
        
        if args.whisper_subs:
            transcriber = WhisperTranscriber(model_size=args.whisper_model)
            _, segments = transcriber.transcribe(downloaded_file)
            srt_content = generate_srt(segments)
            
            with open(processed_srt, "w", encoding="utf-8") as f:
                f.write(srt_content)
            has_valid_srt = True
            
            if args.translate_to.lower() != "english":
                print(f"Translating subtitles to {args.translate_to}...")
                client = OllamaClient()
                # Simplified translation logic for refactor
                with open(processed_srt, 'r', encoding='utf-8') as f:
                    srt_content = f.read()
                
                blocks = [b for b in re.split(r'\n\s*\n', srt_content.strip()) if b.strip()]
                translated_blocks = []
                for block in blocks:
                    lines = block.split('\n')
                    if len(lines) >= 3:
                        idx, time, text = lines[0], lines[1], "\n".join(lines[2:])
                        translated_text = client.translate_subtitle(args.translation_model, text, args.translate_to)
                        translated_blocks.append(f"{idx}\n{time}\n{translated_text}")
                
                with open(processed_srt, 'w', encoding='utf-8') as f:
                    f.write("\n\n".join(translated_blocks) + "\n")
        else:
            # Look for yt-dlp downloaded subs
            possible_srt_paths = [f"{downloaded_file}.{args.sub_lang}.srt", f"{base}.{args.sub_lang}.srt"]
            original_srt = next((p for p in possible_srt_paths if os.path.exists(p)), None)
            
            if original_srt:
                start_offset = parse_time_to_seconds(args.start)
                end_seconds = parse_time_to_seconds(args.end) if args.end else None
                process_srt_file(original_srt, processed_srt, start_offset=start_offset, speed=args.speed, end_time=end_seconds)
                has_valid_srt = True

        if has_valid_srt:
            if args.edit_subs:
                input(f"Press Enter here when you are ready to continue after editing {processed_srt}... ")
            
            if (args.embed_subs or args.burn_subs) and not args.audio_only:
                action = "burn" if args.burn_subs else "embed"
                downloader.process_subtitles(downloaded_file, processed_srt, action=action, burn_color=args.burn_color, burn_bg=args.burn_bg)

def main():
    parser = argparse.ArgumentParser(description="Download strings and videos using yt-dlp with simple arguments.")
    parser.add_argument("url", nargs="?", help="The URL of the video to download. Optional if using --local-video.", default="")
    parser.add_argument("--check", help="Run diagnostic health check to verify yt-dlp, FFmpeg, cookies, and live downloading.", action="store_true")
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
    parser.add_argument("--burn-color", help="Color of the text when using --burn-subs (e.g. 'yellow', 'white', 'green', 'red'). Default: yellow", default="yellow")
    parser.add_argument("--whisper-subs", help="Use local Whisper AI to transcribe audio instead of downloading yt-dlp subtitles.", action="store_true")
    parser.add_argument("--whisper-model", help="Whisper model to use (default: turbo).", default="turbo")
    parser.add_argument("--translate-to", help="Target language to translate subtitles to via Whisper/Ollama (default: English).", default="English")
    parser.add_argument("--translation-model", help="Ollama model for translation if not English.", default="gemma4")
    parser.add_argument("--burn-bg", help="Draw a solid black background behind burned subtitles (useful for hiding hardcoded text).", action="store_true")
    
    args = parser.parse_args()

    if args.check:
        import check_download
        check_download.main()
        return

    run_downloader(args)

if __name__ == "__main__":
    main()
