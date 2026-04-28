import argparse
import subprocess
import sys
import os

def parse_time_to_seconds(time_str):
    if not time_str:
        return 0
    if time_str.isdigit():
        return int(time_str)
    parts = time_str.split(':')
    if len(parts) == 3: # hh:mm:ss
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2: # mm:ss
        return int(parts[0]) * 60 + int(parts[1])
    return 0

def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def download_video(url, start_time, end_time, output_filename="audio.mp3"):
    """
    Downloads a video from Kick using yt-dlp.
    Optionally clips the video given start and end times.
    """
    print(f"Downloading video from {url}...")
    
    # Build the yt-dlp command
    # extract audio as mp3 and use impersonation for Cloudflare bypass
    command = [
        "yt-dlp",
        "-S","height:360",
        "-f", "bestaudio/best",
        "--extract-audio",
        "--audio-format", "mp3",
        "-o", output_filename,
        "--force-overwrite",
        "--impersonate", "chrome",
    ]
    
    # Add section download arguments if both start and end times are provided
    if start_time and end_time:
        print(f"Clipping section from {start_time} to {end_time}...")
        # The syntax for passing start and end into yt-dlp via ffmpeg
        command.extend(["--download-sections", f"*{start_time}-{end_time}"])
    elif start_time or end_time:
        print("Warning: Both --start and --end must be provided to clip the video. Downloading the full video instead.")

    command.append(url)
    
    try:
        subprocess.run(command, check=True)
        print(f"Video downloaded successfully as '{output_filename}'.")
        return output_filename
    except subprocess.CalledProcessError as e:
        print(f"Error downloading video: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'yt-dlp' is not installed or not in PATH.", file=sys.stderr)
        sys.exit(1)

def transcribe_and_prepare_prompt(video_path, prompt_text, whisper_model_size="base", offset_seconds=0, vocabulary=""):
    """
    Uses OpenAI's Whisper locally to transcribe the video.
    Once done, formats a prompt and transcript for Gemini.
    """
    try:
        import whisper
    except ImportError:
        print("Error: 'openai-whisper' is not installed. Run 'pip install openai-whisper'.", file=sys.stderr)
        sys.exit(1)
        
    print(f"\nLoading Whisper model '{whisper_model_size}' (this may take a moment or download weights the first time)...")
    model = whisper.load_model(whisper_model_size)
    
    print("Transcribing video (this will take some time depending on your CPU/GPU)...")
    
    transcribe_kwargs = {"fp16": False}
    if vocabulary:
        transcribe_kwargs["initial_prompt"] = vocabulary
        transcribe_kwargs["carry_initial_prompt"] = True
        
        
    result = model.transcribe(video_path, **transcribe_kwargs)
    
    transcript_lines = []
    for segment in result.get("segments", []):
        seg_start = segment["start"] + offset_seconds
        timestamp = format_timestamp(seg_start)
        text = segment["text"].strip()
        transcript_lines.append(f"[{timestamp}] {text}")
        
    transcript = "\n".join(transcript_lines)
    
    transcript_filename = "transcript.txt"
    with open(transcript_filename, "w", encoding="utf-8") as f:
        f.write(transcript)
    
    abs_path = os.path.abspath(transcript_filename)
    print(f"Transcript saved locally to '{abs_path}'.\n")
    print("=" * 60)
    return transcript

def main():
    parser = argparse.ArgumentParser(description="Download a Kick video, optionally cut it, and generate a transcript summary prompt for Gemini.")
    parser.add_argument("url", nargs="?", help="The URL of the Kick video or clip. Optional if skipping steps.", default="")
    parser.add_argument("--start", help="Start time in seconds or HH:MM:SS format (e.g., 00:01:30).", default=None)
    parser.add_argument("--end", help="End time in seconds or HH:MM:SS format (e.g., 00:02:45).", default=None)
    parser.add_argument("--output", help="Output filename for the audio (default: audio.mp3)", default="audio.mp3")
    parser.add_argument("--no-transcript", help="Skip the Whisper transcription.", action="store_true")
    parser.add_argument("--vocabulary", help="Names of guests, hosts, or context to help Whisper spell them correctly (e.g., 'Destiny, Sneako').", default="")
    parser.add_argument("--model", help="Ollama model to use for summarization. If provided, the script will automatically query local Ollama.", default="minimax-m2.7:cloud")
    parser.add_argument("--skip-step-to", choices=["step-transcription", "step-summary"], help="Skip directly to transcription or summarization step.", default=None)
    
    # Customize the GEM / Skill prompt here
    parser.add_argument(
        "--prompt", 
        help="Custom instruction for Gemini to summarize the transcript.", 
        default="""
You help me summarize video transcripts for learning purposes. 
Videos can be 2 to 3 hours long. I want no skipping, especially in the middle of a long video. 
Questions and discussions about AI cannot be skipped.
I would like the summary to be detailed and precise. 
The language should be clear, logical, and easy to read.
Add timestamps for me to navigate and rewatch interesting parts of the video.
Add titles for sections or chapters if it makes sense.
The output should be in Markdown format so that I can easily copy and paste it into Discord.
At the end of each summary, write a short introduction and list some highlights. 
Do not use markdown table format.
Time is represented as [hh:mm:ss] at the beginning of each line.
"""
    )
    
    args = parser.parse_args()
    
    video_path = args.output
    # 1. Download / Clip Video
    if args.skip_step_to not in ["step-transcription", "step-summary"]:
        if not args.url:
            parser.error("url argument is required unless --skip-step-to is provided.")
        video_path = download_video(args.url, args.start, args.end, args.output)
    else:
        print(f"Skipping video download based on --skip-step-to. Assuming video exists at '{video_path}' if needed.")
    
    # 2. Transcribe and Generate Prompt
    transcript = ""
    if args.skip_step_to != "step-summary":
        if not args.no_transcript:
            offset = 0
            # offset = parse_time_to_seconds(args.start)
            transcript = transcribe_and_prepare_prompt(video_path, args.prompt, offset_seconds=offset, vocabulary=args.vocabulary)
        else:
            print("\nSkipping transcription as --no-transcript was provided.")
    else:
        print("\nSkipping transcription step. Loading existing transcript from 'transcript.txt'...")
        try:
            with open("transcript.txt", "r", encoding="utf-8") as f:
                transcript = f.read()
        except FileNotFoundError:
            print("Error: 'transcript.txt' not found. Cannot skip to summary.", file=sys.stderr)
            sys.exit(1)

    # 3. Automatic Ollama API Call
    if transcript:
        model_name = args.model
        if model_name:
            print("\n" + "=" * 60)
            print(f"CALLING OLLAMA ({model_name})...")
            try:
                import requests
                url = "http://localhost:11434/api/generate"
                payload = {
                    "model": model_name,
                    "prompt": f"{args.prompt}\n\nf{args.vocabulary}\n\n[Transcript]:\n{transcript}",
                    "stream": False
                }
                response = requests.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                print("\n=== OLLAMA SUMMARY ===")
                print(result.get("response", ""))
                print("======================\n")

                with open("summary.md", "w", encoding="utf-8") as f:
                    f.write(result.get("response"))
            except ImportError:
                print("Error: 'requests' is not installed. Run 'pip install requests'.", file=sys.stderr)
            except Exception as e:
                print(f"Failed to query Ollama API: {e}", file=sys.stderr)
        else:
            print("=" * 60)
            print("READY FOR OLLAMA:")
            full_text = f"{args.prompt}\n\nf{args.vocabulary}\n\n[Transcript from Video]:\n{transcript}"
            print(full_text)
            print("=" * 60)

if __name__ == "__main__":
    main()
