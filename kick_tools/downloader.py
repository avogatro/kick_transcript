import os
import subprocess
import sys
from .utils import parse_time_to_seconds

class MediaDownloader:
    def __init__(self, output_dir="."):
        self.output_dir = output_dir

    def download(self, url, quality="480p", start=None, end=None, output=None, audio_only=False, impersonate="chrome", download_subs=False, sub_lang="en"):
        """
        Downloads media using yt-dlp.
        """
        command = ["yt-dlp"]
        
        if download_subs:
            command.extend(["--write-subs", "--write-auto-subs", "--sub-langs", sub_lang, "--convert-subs", "srt"])
        
        if audio_only:
            command.extend(["-f", "bestaudio/best", "--extract-audio", "--audio-format", "mp3"])
        else:
            height = quality.replace('p', '') if quality.endswith('p') else quality
            command.extend(["-S", f"height:{height},vcodec:h264", "--merge-output-format", "mp4"])

        if output:
            command.extend(["-o", output])
            actual_filename = output
        else:
            command.extend(["-o", "%(title).60B.%(ext)s", "--restrict-filenames"])
            # Get the actual filename that yt-dlp will use
            sim_cmd = ["yt-dlp", "--simulate", "--print", "filename"]
            if audio_only:
                sim_cmd.extend(["-f", "bestaudio/best", "--extract-audio", "--audio-format", "mp3"])
            else:
                height = quality.replace('p', '') if quality.endswith('p') else quality
                sim_cmd.extend(["-S", f"height:{height},vcodec:h264", "--merge-output-format", "mp4"])
            sim_cmd.extend(["-o", "%(title).60B.%(ext)s", "--restrict-filenames"])
            sim_cmd.append(url)
            try:
                res = subprocess.run(sim_cmd, check=True, capture_output=True, text=True)
                actual_filename = res.stdout.strip().split('\n')[0]
            except subprocess.CalledProcessError:
                actual_filename = "downloaded_file"

        if start and end:
            command.extend(["--download-sections", f"*{start}-{end}", "--force-keyframes-at-cuts"])

        command.extend(["--impersonate", impersonate, "--force-overwrite"])
        command.append(url)

        print(f"Running command: {' '.join(command)}")
        try:
            subprocess.run(command, check=True)
            return actual_filename
        except subprocess.CalledProcessError as e:
            print(f"Error downloading: {e}", file=sys.stderr)
            return None

    def adjust_speed(self, file_path, speed, audio_only=False):
        """
        Adjusts playback speed using ffmpeg.
        """
        if speed == 1.0:
            return file_path

        print(f"Adjusting speed to {speed}x...")
        name, ext = os.path.splitext(file_path)
        temp_file = f"{name}_speed{ext}"
        
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", file_path]
        
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
            ffmpeg_cmd.extend(["-filter:v", f"setpts={1.0/speed}*PTS", "-filter:a", af_str])
        
        ffmpeg_cmd.append(temp_file)
        try:
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            os.replace(temp_file, file_path)
            return file_path
        except subprocess.CalledProcessError:
            print(f"Error during speed adjustment: ffmpeg failed.", file=sys.stderr)
            return None

    def process_subtitles(self, video_file, srt_file, action="embed", burn_color="yellow", burn_bg=False):
        """
        Embeds or burns subtitles into a video file.
        """
        base, _ = os.path.splitext(video_file)
        temp_vid = f"{base}_subbed.mp4"
        
        if action == "burn":
            srt_escaped = srt_file.replace('\\', '/').replace("'", r"\'").replace(":", r"\:")
            ass_colors = {
                "white": "&HFFFFFF&", "yellow": "&H00FFFF&", "green": "&H00FF00&",
                "cyan": "&HFFFF00&", "blue": "&HFF0000&", "magenta": "&HFF00FF&",
                "red": "&H0000FF&", "black": "&H000000&"
            }
            color_code = ass_colors.get(burn_color.lower(), "&HFFFFFF&")
            if burn_bg:
                style = f"PrimaryColour={color_code},BackColour=&H00000000&,BorderStyle=3,Outline=0,Shadow=0"
            else:
                style = f"PrimaryColour={color_code},OutlineColour=&H0000&,BorderStyle=1,Outline=2,Shadow=0"
            
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", video_file,
                "-map", "0:v?", "-map", "0:a?",
                "-vf", f"subtitles='{srt_escaped}':force_style='{style}'",
                "-c:a", "copy", temp_vid
            ]
        else: # embed
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", video_file, "-i", srt_file,
                "-map", "0:v?", "-map", "0:a?", "-map", "1:s",
                "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text", temp_vid
            ]

        try:
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            os.replace(temp_vid, video_file)
            return True
        except subprocess.CalledProcessError:
            print(f"Error processing subtitles.", file=sys.stderr)
            return False
