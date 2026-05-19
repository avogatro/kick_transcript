import sys
import re

def parse_vtt(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by double blank lines
    blocks = re.split(r'\n\s*\n', content)
    
    clean_lines = []
    last_text = ""
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue
        
        # Look for timestamp line
        timestamp_line = ""
        text_lines = []
        for line in lines:
            if '-->' in line:
                timestamp_line = line
            elif timestamp_line and not line.startswith('WEBVTT') and not line.startswith('Kind:') and not line.startswith('Language:'):
                text_lines.append(line)
        
        if timestamp_line and text_lines:
            # VTT format: 00:00:00.000 --> 00:00:02.000
            start_time = timestamp_line.split('-->')[0].strip()
            # clean tags like <c> or <00:00:00.000>
            text = ' '.join(text_lines)
            text = re.sub(r'<[^>]+>', '', text)
            
            # YouTube auto-subs repeat the same text as it rolls. 
            # We only keep the last line of the block or try to deduplicate.
            # Usually, the last line in a block of auto-subs is the new word.
            # But simpler: just strip and if it's the same, ignore.
            # A better way for YT auto-subs: just take the whole text, but YT adds line by line.
            # Actually, YT vtt with auto-subs usually has word-by-word timestamps inside <00:00:00.000>.
            # If we remove the tags, we get the full line. We can just keep lines that are not substrings of the previous line.
            
            if text and text != last_text:
                # If the previous text is a prefix of the current text, just update it.
                if text.startswith(last_text) or last_text in text:
                    pass # We will just use the new longer text
                elif last_text.startswith(text):
                    continue # Skip this
                else:
                    clean_lines.append((start_time, text))
                last_text = text

    # deduplicate adjacent similar lines further if needed
    final_output = []
    for t, txt in clean_lines:
        if final_output and final_output[-1][1] == txt:
            continue
        final_output.append(f"[{t}] {txt}")

    with open('transcript_clean.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_output))

if __name__ == "__main__":
    parse_vtt(sys.argv[1])
