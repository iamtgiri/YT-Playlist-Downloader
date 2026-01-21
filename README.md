# YouTube Playlist Downloader (Desktop GUI)

A lightweight **desktop application** for downloading **YouTube playlists or individual videos** using a clean **PyQt5-based GUI**.

The application is built on top of `yt-dlp` and bundles **FFmpeg binaries**, allowing end users to run the application without manually installing Python or external dependencies when using the prebuilt executable.

---

## Features

- Download full playlists or single videos
- Simple, responsive desktop UI (PyQt5)
- Built on `yt-dlp` for reliable downloads
- Bundled FFmpeg for post-processing
- Optional executable build for non-Python users

---

##  Project Structure

```

YT-Playlist-Downloader/
├── app/
│   ├── **init**.py
│   ├── yt_dlp_gemini_tagger.py   # yt-dlp wrapper (metadata/tagging)
│   └── main.py                  # application entry point
├── ffmpeg/                      # bundled FFmpeg binaries
├── assets/                      # icons and UI assets
├── requirements.txt             # runtime dependencies
├── LICENSE                      # GPL-3.0
├── README.md
└── .gitignore
````

---

##  Running from Source

### Prerequisites
- Python 3.9+
- Windows (tested)

### Steps

````bash
git clone https://github.com/iamtgiri/YT-Playlist-Downloader.git
cd YT-Playlist-Downloader
````

Create and activate a virtual environment:

````bash
python -m venv venv
venv\Scripts\activate
````

Install dependencies:

````bash
pip install -r requirements.txt
````

Run the application:

````bash
python -m app.main
````

---

##  Building a Standalone Executable

You can generate a self-contained Windows executable using **PyInstaller**.

### Install PyInstaller

````bash
pip install pyinstaller
````

### Build

````bash
pyinstaller --onefile --windowed --icon=assets/icon.ico \
  --add-data "assets/icon.png;assets" \
  --add-data "ffmpeg/ffmpeg.exe;ffmpeg" \
  --add-data "ffmpeg/ffprobe.exe;ffmpeg" \
  --add-data "ffmpeg/ffplay.exe;ffmpeg" \
  app/main.py
````

The generated executable will be available in the `dist/` directory.

---

##  License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.
See the [LICENSE](LICENSE) file for details.

---

##  Acknowledgements

* **PyQt5** — GUI framework
* **yt-dlp** — YouTube download backend
* **FFmpeg** — audio/video processing

*Inspired by the need for a simple YouTube playlist downloader with a user-friendly interface.*