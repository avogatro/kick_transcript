import argparse
import os
import torch
from qwen_asr import Qwen3ASRModel

def test_transcription(file_path):
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    # Qwen3-ASR uses bfloat16 by default on GPU
    dtype = torch.bfloat16 if device == "cuda:0" else torch.float32

    print(f"Loading Qwen3-ASR-1.7B model on {device}...")
    try:
        # Load the model with Forced Aligner for timestamps
        model = Qwen3ASRModel.from_pretrained(
            "Qwen/Qwen3-ASR-1.7B", 
            dtype=dtype, 
            device_map=device,
            max_inference_batch_size=32, 
            max_new_tokens=256,
            forced_aligner="Qwen/Qwen3-ForcedAligner-0.6B",
            forced_aligner_kwargs=dict(
                dtype=dtype, 
                device_map=device,
            )
        )
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    print(f"Transcribing '{file_path}'... This may take a while to download weights on the first run.")
    
    def format_seconds_to_srt_time(seconds):
        if seconds is None:
            return "00:00:00,000"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int(round((seconds - int(seconds)) * 1000))
        if millis >= 1000:
            millis -= 1000
            secs += 1
            if secs >= 60:
                secs -= 60
                minutes += 1
                if minutes >= 60:
                    minutes -= 60
                    hours += 1
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    try:
        results = model.transcribe(
            audio=[file_path],
            return_time_stamps=True
        )
        
        base, _ = os.path.splitext(file_path)
        out_file = f"{base}_qwen.srt"
        
        with open(out_file, "w", encoding="utf-8") as f:
            for r in results:
                # r.time_stamps is typically a list of tokens/words
                # We'll group them into segments of up to 10 words or until a punctuation mark
                segment_index = 1
                current_words = []
                current_start = None
                current_end = None
                
                # Depending on the exact structure returned by Qwen3ASR, time_stamps could be a nested list
                flat_timestamps = []
                if hasattr(r, 'time_stamps') and r.time_stamps:
                    # Flatten if it's a list of lists
                    for item in r.time_stamps:
                        if isinstance(item, list):
                            flat_timestamps.extend(item)
                        else:
                            flat_timestamps.append(item)
                
                for t in flat_timestamps:
                    try:
                        text = getattr(t, 'text', '') if hasattr(t, 'text') else t.get('text', '')
                        start = getattr(t, 'start_time', None) if hasattr(t, 'start_time') else t.get('start_time', None)
                        end = getattr(t, 'end_time', None) if hasattr(t, 'end_time') else t.get('end_time', None)
                    except AttributeError:
                        continue
                        
                    if current_start is None:
                        current_start = start
                    current_end = end
                    current_words.append(text)
                    
                    # Break segment if it reaches 10 words or ends with sentence punctuation
                    if len(current_words) >= 10 or text.strip()[-1:] in ['.', '!', '?', '。', '！', '？']:
                        start_str = format_seconds_to_srt_time(current_start)
                        end_str = format_seconds_to_srt_time(current_end)
                        segment_text = "".join(current_words) if r.language in ["Chinese", "Japanese"] else " ".join(current_words)
                        f.write(f"{segment_index}\n{start_str} --> {end_str}\n{segment_text.strip()}\n\n")
                        
                        segment_index += 1
                        current_words = []
                        current_start = None
                        current_end = None
                
                # Write any remaining words
                if current_words:
                    start_str = format_seconds_to_srt_time(current_start)
                    end_str = format_seconds_to_srt_time(current_end)
                    segment_text = "".join(current_words) if r.language in ["Chinese", "Japanese"] else " ".join(current_words)
                    f.write(f"{segment_index}\n{start_str} --> {end_str}\n{segment_text.strip()}\n\n")

        print("\n==============================")
        print("    Transcription Results     ")
        print("==============================\n")
        print(f"SRT successfully saved to: {out_file}")
        print("\n==============================\n")
    except Exception as e:
        print(f"Error transcribing file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test script for Qwen3-ASR-1.7B transcription.")
    parser.add_argument("file", help="Path to the local audio or video file to transcribe.")
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' not found.")
    else:
        test_transcription(args.file)
