# Video & Audio Downloader (`video_audio_downloader.py`)

A lightweight, powerful Python tool designed to download, trim, and process YouTube/Kick videos from the CLI. This script uses `yt-dlp` to fetch media and `ffmpeg` to handle complex post-processing features natively.

## Key Features

- **Quality Selection:** Fetch specific high-definition (1080p) or standard (480p) resolutions natively.
- **Smart Formatting:** The output is always safely constrained and forced into a highly compatible `.mp4` container.
- **Section Clipping:** Selectively download only the specific chapters/timestamps you want—saving massive amounts of bandwidth and memory.
- **Speed Adjustment:** Increase or decrease video and audio speed perfectly in sync using built-in `ffmpeg` filtering.
- **Intelligent Collision Avoidance:** If a file with the same title already exists, the tool handles appending sequential numbers to the end seamlessly (e.g., `Video 2.mp4`) instead of crashing or overwriting your work.
- **Smart Subtitles:** Download, intelligently offset/scale subtitles to match your clipping and speed adjustments, and even optionally edit them manually before embedding them into your final video.

---

## Prerequisites

Ensure you have both of the following installed and accessible in your system's `PATH`:
- `yt-dlp`
- `ffmpeg`

---

## 🛠️ Usage & Parameter Examples

### Basic usage
Downloads a video at the default 480p resolution and automatically saves it as the YouTube Video's title.
```powershell
python video_audio_downloader.py "https://www.youtube.com/watch?v=YOUR_URL"
```

### 1. `quality` (Quality Setting)
Define the maximum vertical resolution the tool should target. Defaults to `480p`.
```powershell
python video_audio_downloader.py "https://www.youtube.com/watch?v=YOUR_URL" --quality 1080p
```
```powershell
python video_audio_downloader.py "https://www.youtube.com/watch?v=YOUR_URL" --quality 720p
```

### 2. `start` and `end` (Clipping)
Only fetch a specific section of the video to save space and time. You can use purely seconds (`60`) or `HH:MM:SS` format. *Note: Both a start and end parameter must be provided to clip successfully.*
```powershell
python video_audio_downloader.py "https://www.youtube.com/watch?v=YOUR_URL" --start 00:46:49 --end 00:47:51
```

### 3. `speed` (Speed Adjustment)
Speeds up or slows down the final file. This runs an automatic `ffmpeg` script under the hood after downloading the video, keeping audio and video synchronized properly.
```powershell
# Speeds up the clip by 1.5x
python video_audio_downloader.py "https://www.youtube.com/watch?v=YOUR_URL" --speed 1.5

# Slows down the clip by half
python video_audio_downloader.py "https://www.youtube.com/watch?v=YOUR_URL" --speed 0.5
```

### 4. `audio-only` (Extract Audio)
Bypasses fetching the video track and only outputs the best quality audio as a track.
```powershell
python video_audio_downloader.py "https://www.youtube.com/watch?v=YOUR_URL" --audio-only
```

### 5. `output` (Custom Output Name)
Want to name the file yourself rather than using the video title? Specify an output! Don't worry, if you pick a name that already exists in the folder, the script will append a number to prevent overwriting your existing file.
```powershell
python video_audio_downloader.py "https://www.youtube.com/watch?v=YOUR_URL" --output "my_funny_clip.mp4"
```

### 6. Subtitles (`--subs`, `--embed-subs`, `--edit-subs`)
You can download subtitles natively with `yt-dlp` and embed them accurately, even when combining clipping and speed adjustments!
- `--subs`: Only downloads the external `.srt` file.
- `--embed-subs`: Downloads and burns/embeds the `.srt` subtitles directly into the resulting `.mp4` file.
- `--edit-subs`: Pauses the downloader right before embedding so you can manually correct the downloaded `.srt` file!

```powershell
# Automatically download and embed subtitles for a video
python video_audio_downloader.py "https://www.youtube.com/watch?v=YOUR_URL" --embed-subs

# Interactive mode to manually correct subtitles before they are embedded
python video_audio_downloader.py "https://www.youtube.com/watch?v=YOUR_URL" --edit-subs
```

### Putting It All Together
An advanced example: Grabbing a specific 2-minute section of a 1080p video, adjusting the playback speed to 1.15x, and naming it manually.
```powershell
python video_audio_downloader.py "https://www.youtube.com/watch?v=YOUR_URL" --start 01:21:08 --end 01:23:17 --quality 1080p --speed 1.15 --output "sped_up_section.mp4"
```
