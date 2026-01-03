
# 🎬 YT Playlist Downloader

A simple **desktop app** to download full YouTube playlists or single videos with a clean PyQt5-based GUI.  
This project bundles **FFmpeg** internally, so you don’t need to install Python or extra dependencies when using the `.exe` release.

---

## 📦 Project Structure

```

youtube-downloader-gui/
├── app/
│   ├── __init__.py
│   ├── yt_dlp_gemini_tagger.py # yt-dlp wrapper with Gemini tagging
│   └── main.py         # main application code
├── requirements.txt     # dependencies for running from source
├── README.md            # this file
├── LICENSE              # GPL-3.0 License
├── .gitignore
├── ffmpeg/              # bundled FFmpeg binaries
└── assets/

```

---

## 🚀 How to Use

### Run from Source

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