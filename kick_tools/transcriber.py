import os
import re
import sys
from .utils import format_timestamp, ensure_package_installed

class WhisperTranscriber:
    def __init__(self, model_size="large"):
        self.model_size = model_size
        self.model = None

    def _load_model(self):
        if self.model is None:
            ensure_package_installed("openai-whisper", "whisper")
            ensure_package_installed("torch")
            import whisper
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Loading Whisper model '{self.model_size}' on {device.upper()}...")
            self.model = whisper.load_model(self.model_size, device=device)

    def transcribe(self, file_path, vocabulary="", offset_seconds=0):
        self._load_model()
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        fp16_val = True if device == "cuda" else False

        print(f"Transcribing '{file_path}'...")
        transcribe_kwargs = {"fp16": fp16_val}
        if vocabulary:
            transcribe_kwargs["initial_prompt"] = vocabulary
            transcribe_kwargs["carry_initial_prompt"] = True

        result = self.model.transcribe(file_path, **transcribe_kwargs)
        
        transcript_lines = []
        for segment in result.get("segments", []):
            seg_start = segment["start"] + offset_seconds
            timestamp = format_timestamp(seg_start)
            text = segment["text"].strip()
            transcript_lines.append(f"[{timestamp}] {text}")
            
        return "\n".join(transcript_lines), result.get("segments", [])

def clean_vtt_content(vtt_content):
    """
    Cleans WEBVTT content, deduplicating lines and removing tags.
    """
    blocks = re.split(r'\n\s*\n', vtt_content)
    clean_lines = []
    last_text = ""
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue
        
        timestamp_line = ""
        text_lines = []
        for line in lines:
            if '-->' in line:
                timestamp_line = line
            elif timestamp_line and not any(line.startswith(s) for s in ['WEBVTT', 'Kind:', 'Language:']):
                text_lines.append(line)
        
        if timestamp_line and text_lines:
            start_time = timestamp_line.split('-->')[0].strip()
            text = ' '.join(text_lines)
            text = re.sub(r'<[^>]+>', '', text)
            
            if text and text != last_text:
                if text.startswith(last_text) or last_text in text:
                    pass
                elif last_text.startswith(text):
                    continue
                else:
                    clean_lines.append((start_time, text))
                last_text = text

    final_output = []
    for t, txt in clean_lines:
        if final_output and final_output[-1].split('] ')[1] == txt:
            continue
        final_output.append(f"[{t}] {txt}")

    return '\n'.join(final_output)

def generate_srt(segments, offset_seconds=0):
    """
    Generates SRT content from Whisper segments.
    """
    srt_blocks = []
    for i, segment in enumerate(segments):
        start_str = format_timestamp(segment["start"] + offset_seconds, include_ms=True)
        end_str = format_timestamp(segment["end"] + offset_seconds, include_ms=True)
        text = segment["text"].strip()
        srt_blocks.append(f"{i+1}\n{start_str} --> {end_str}\n{text}\n")
    return "\n".join(srt_blocks)
