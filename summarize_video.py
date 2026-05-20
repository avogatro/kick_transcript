import argparse
import sys
import os
from kick_tools.utils import parse_time_to_seconds
from kick_tools.downloader import MediaDownloader
from kick_tools.transcriber import WhisperTranscriber
from kick_tools.llm import OllamaClient

def main():
    parser = argparse.ArgumentParser(description="Download a Kick video, optionally cut it, and generate a transcript summary prompt for Gemini.")
    parser.add_argument("url", nargs="?", help="The URL of the Kick video or clip. Optional if skipping steps.", default="")
    parser.add_argument("--start", help="Start time in seconds or HH:MM:SS format (e.g., 00:01:30).", default=None)
    parser.add_argument("--end", help="End time in seconds or HH:MM:SS format (e.g., 00:02:45).", default=None)
    parser.add_argument("--output", help="Output filename for the audio (default: audio.mp3)", default="audio.mp3")
    parser.add_argument("--no-transcript", help="Skip the Whisper transcription.", action="store_true")
    parser.add_argument("--vocabulary", help="Names of guests, hosts, or context to help Whisper spell them correctly (e.g., 'Destiny, Sneako').", default="")
    parser.add_argument("--model", help="Ollama model to use for summarization. If provided, the script will automatically query local Ollama.", default="gemma4")
    parser.add_argument("--whisper-model-size", help="Size of the Whisper model to use (e.g., base, small, medium, large).", default="large")
    parser.add_argument("--skip-step-to", choices=["step-transcription", "step-summary"], help="Skip directly to transcription or summarization step.", default=None)
    
    # Customize the GEM / Skill prompt here
    parser.add_argument(
        "--prompt", 
        help="Custom instruction for Gemini to summarize the transcript.", 
        default="""
You help me summarize video transcripts for learning purposes. 
Timestamps in transcript is represented as [hh:mm:ss] at the beginning of each line.
Videos can be very long. I want no skipping, especially in the middle of a long video. 
Questions and discussions about AI should not be skipped.
The summary needs to be detailed and precise. 
The language should be clear, logical, and easy to read.
Add timestamps for me to navigate and rewatch interesting sections of the video.
Add titles for sections or chapters if it makes sense.
The output should be in Markdown format so that I can easily copy and paste it into Discord.
At the end of each summary, write a short introduction and list highlights.
Do not use markdown table format.
"""
    )
    
    args = parser.parse_args()
    
    video_path = args.output
    downloader = MediaDownloader()
    
    # 1. Download / Clip Video
    if args.skip_step_to not in ["step-transcription", "step-summary"]:
        if not args.url:
            parser.error("url argument is required unless --skip-step-to is provided.")
        video_path = downloader.download(args.url, start=args.start, end=args.end, output=args.output, audio_only=True)
        if not video_path:
            sys.exit(1)
    else:
        print(f"Skipping video download based on --skip-step-to. Assuming video exists at '{video_path}' if needed.")
    
    # 2. Transcribe and Generate Prompt
    transcript = ""
    if args.skip_step_to != "step-summary":
        if not args.no_transcript:
            transcriber = WhisperTranscriber(model_size=args.whisper_model_size)
            transcript, _ = transcriber.transcribe(video_path, vocabulary=args.vocabulary)
            
            transcript_filename = "transcript.txt"
            with open(transcript_filename, "w", encoding="utf-8") as f:
                f.write(transcript)
            
            print(f"Transcript saved locally to '{os.path.abspath(transcript_filename)}'.\n")
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
            client = OllamaClient()
            summary = client.summarize(model_name, transcript, args.prompt, args.vocabulary)
            
            if summary:
                print("\n=== OLLAMA SUMMARY ===")
                print(summary)
                print("======================\n")

                with open("summary.md", "w", encoding="utf-8") as f:
                    f.write(summary)
            else:
                print("Failed to get summary from Ollama.", file=sys.stderr)
        else:
            print("=" * 60)
            print("READY FOR OLLAMA:")
            full_text = f"{args.prompt}\n\n{args.vocabulary}\n\n[Transcript from Video]:\n{transcript}"
            print(full_text)
            print("=" * 60)

if __name__ == "__main__":
    main()
