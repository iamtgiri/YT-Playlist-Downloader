
# 🎬 YT Playlist Downloader

A simple **desktop app** to download full YouTube playlists or single videos with a clean PyQt5-based GUI.  
This project bundles **FFmpeg** internally, so you don’t need to install Python or extra dependencies when using the `.exe` release.

---

## 📦 Project Structure
```

youtube-downloader-gui/
├── app/
│   ├── __init__.py
│   └── main.py         # main application code
├── requirements.txt     # dependencies for running from source
├── README.md            # this file
├── LICENSE              # GPL-3.0 License
├── setup.py             # optional: pip installable
├── .gitignore
└── assets/
└── icon.png         # application tray/icon

```

---

## 🚀 How to Use

### Option 1: Run the Prebuilt `.exe` (Recommended for Windows Users)
1. Download the latest release from **[Releases](https://github.com/iamtgiri/YT-Playlist-Downloader/releases)**.  
   Example:  
   [⬇️ Download `YT-Playlist-Downloader.exe`](https://github.com/iamtgiri/YT-Playlist-Downloader/releases/download/v1.0.0/YT-Playlist-Downloader-v1.0.0.exe)  
2. Double-click the `.exe` to launch the app.  
3. Paste a YouTube playlist or video link.  
4. Choose whether to download as **video (MP4)** or **audio (MP3)**.  
5. The app will download and process automatically using FFmpeg.  

⚠️ On first run, Windows SmartScreen might warn because the executable isn’t code-signed. Click **More Info → Run Anyway** to proceed.

---

### Option 2: Run from Source (For Developers)
1. Clone the repository:
   ```bash
   git clone https://github.com/iamtgiri/YT-Playlist-Downloader.git
   cd YT-Playlist-Downloader
    ```

2. Create and activate a virtual environment (recommended):

   ```bash
   python -m venv venv
   venv\Scripts\activate   # on Windows
   ```
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```
4. Run the app:

   ```bash
   python -m app.main
   ```

---

## 🛠️ Build Your Own Executable

If you want to generate your own `.exe`:

1. Install [PyInstaller](https://pyinstaller.org/):

   ```bash
   pip install pyinstaller
   ```
2. Run:

   ```bash
   pyinstaller --onefile --windowed --icon=assets/icon.ico \
       --add-data "assets/icon.png;assets" \
       --add-data "ffmpeg/ffmpeg.exe;ffmpeg" \
       --add-data "ffmpeg/ffprobe.exe;ffmpeg" \
       --add-data "ffmpeg/ffplay.exe;ffmpeg" \
       app/main.py
   ```
3. Your executable will be in the `dist/` folder.

---

## 📜 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.
You are free to use, modify, and distribute it under the same license terms. See [LICENSE](LICENSE) for details.

---

## 🙌 Acknowledgements

* [PyQt5](https://pypi.org/project/PyQt5/) for GUI
* [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube downloading
* [FFmpeg](https://ffmpeg.org/) for audio/video processing


