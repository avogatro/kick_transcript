import argparse
import sys
import os
from kick_tools.utils import parse_time_to_seconds
from kick_tools.downloader import MediaDownloader
from kick_tools.transcriber import WhisperTranscriber
from kick_tools.llm import OllamaClient

def get_or_prompt_gemini_api_key():
    # 1. Check environment variable
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return api_key

    # 2. Check .env file
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    key, val = line.strip().split("=", 1)
                    if key.strip() == "GEMINI_API_KEY":
                        val_cleaned = val.strip().strip('"').strip("'")
                        if val_cleaned:
                            return val_cleaned

    # 3. Prompt user for key
    print("Gemini API key not found in GEMINI_API_KEY environment variable or .env file.")
    print("You can get a FREE key from: https://aistudio.google.com/")
    try:
        user_key = input("Please enter your Gemini API Key: ").strip()
    except EOFError:
        print("Error: Standard input is not available to prompt for API key.", file=sys.stderr)
        return None
        
    if not user_key:
        print("Error: No API key provided.", file=sys.stderr)
        return None

    # 4. Save to .env
    lines = []
    key_written = False
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            if line.strip().startswith("GEMINI_API_KEY="):
                lines[i] = f"GEMINI_API_KEY={user_key}\n"
                key_written = True
                break
    
    if not key_written:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f"GEMINI_API_KEY={user_key}\n")
        
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"API key successfully saved to '{env_path}'.")

    # 5. Add to .gitignore if not already there
    gitignore_path = ".gitignore"
    has_env = False
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() == ".env":
                    has_env = True
                    break
        if not has_env:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                content = f.read()
            with open(gitignore_path, "a", encoding="utf-8") as f:
                if content and not content.endswith("\n"):
                    f.write("\n")
                f.write(".env\n")
            print("Added '.env' to .gitignore.")
    else:
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(".env\n")
        print("Created .gitignore and added '.env'.")

    return user_key

def main():
    parser = argparse.ArgumentParser(description="Download a Kick video, optionally cut it, and generate a transcript summary prompt for Gemini.")
    parser.add_argument("url", nargs="?", help="The URL of the Kick video or clip. Optional if skipping steps.", default="")
    parser.add_argument("--start", help="Start time in seconds or HH:MM:SS format (e.g., 00:01:30).", default=None)
    parser.add_argument("--end", help="End time in seconds or HH:MM:SS format (e.g., 00:02:45).", default=None)
    parser.add_argument("--output", help="Output filename for the audio (default: audio.mp3)", default="audio.mp3")
    parser.add_argument("--no-transcript", help="Skip the Whisper transcription.", action="store_true")
    parser.add_argument("--vocabulary", help="Names of guests, hosts, or context to help Whisper spell them correctly (e.g., 'Destiny, Sneako').", default="")
    parser.add_argument("--model", help="LLM model to use for summarization. Use 'gemma4' or another model name for Ollama, or 'gemini-3.5-flash' / 'gemini-1.5-flash' for Gemini (requires GEMINI_API_KEY environment variable).", default="gemma4")
    parser.add_argument("--whisper-model-size", help="Size of the Whisper model to use (e.g., base, small, medium, large, turbo).", default="turbo")
    parser.add_argument("--skip-step-to", choices=["step-transcription", "step-summary"], help="Skip directly to transcription or summarization step.", default=None)
    
    # Customize the GEM / Skill prompt here
    parser.add_argument(
        "--prompt", 
        help="Custom instruction for Gemini to summarize the transcript.", 
        default="""
You are an expert AI learning assistant and technical scribe. Your goal is to transform the provided video transcript into comprehensive, highly structured, and educational study notes.
Follow these strict rules when generating your response:
1. **No Skipping/Loss of Detail**: Summarize the ENTIRE transcript comprehensively. Do not gloss over or skip sections, especially in the middle of long videos. 
    Ensure all technical explanations, deep dives, questions, and discussions—particularly those regarding AI and technology—are captured with detailed precision.
    
2. **Chronological Chapters**: Break the video down into logical, chronological chapters or themed sections that make sense.

3. **Format & Navigation**:
   - For every chapter or section, create a clear Markdown heading in this exact format: `## [HH:MM:SS] - Chapter Title` using the precise timestamp from the transcript.
   - Use standard Markdown (`##`, `###`, bolding, list bullets) optimized for copy-pasting into Discord.
   - **NEVER use Markdown tables** (they do not render correctly in Discord).

4. **Style & Tone**: Ensure the language is exceptionally clear, logical, educational, professional, and easy to read.
### Required Output Structure:

First, provide the chronological chapter-by-chapter detailed summary:
- **`## [HH:MM:SS] - Section/Chapter Title`**
  -  A detailed, logical explanation of the concepts, arguments, and discussions of this chapter
At the very end of your response, output a horizontal separator `---` followed by this final section:
---

### 📌 Video Overview & Key Highlights
- **Introduction**: A short, high-level overview introducing the main topic, context, and core thesis of the entire video.
- **Highlights**: A bulleted list of 3-5 of the most valuable, high-impact takeaways or key moments.
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
                print(transcript)
        except FileNotFoundError:
            print("Error: 'transcript.txt' not found. Cannot skip to summary.", file=sys.stderr)
            sys.exit(1)

    # 3. Automatic LLM API Call
    if transcript:
        model_name = args.model
        if model_name:
            print("\n" + "=" * 60)
            if model_name.startswith("gemini"):
                print(f"CALLING GEMINI ({model_name})...")
                api_key = get_or_prompt_gemini_api_key()
                if not api_key:
                    sys.exit(1)
                from kick_tools.llm import GeminiClient
                client = GeminiClient(api_key=api_key)
                summary = client.summarize(model_name, transcript, args.prompt, args.vocabulary)
                provider = "GEMINI"
            else:
                print(f"CALLING OLLAMA ({model_name})...")
                client = OllamaClient()
                summary = client.summarize(model_name, transcript, args.prompt, args.vocabulary)
                provider = "OLLAMA"
            
            if summary:
                print(f"\n=== {provider} SUMMARY ===")
                print(summary)
                print("======================\n")

                with open("summary.md", "w", encoding="utf-8") as f:
                    f.write(summary)
            else:
                print(f"Failed to get summary from {provider}.", file=sys.stderr)
        else:
            print("=" * 60)
            print("READY FOR OLLAMA:")
            full_text = f"{args.prompt}\n\n{args.vocabulary}\n\n[Transcript from Video]:\n{transcript}"
            print(full_text)
            print("=" * 60)

if __name__ == "__main__":
    main()
