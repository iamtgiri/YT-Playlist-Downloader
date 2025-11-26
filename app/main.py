import sys
import os
import json
import socket
import subprocess
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton,
    QProgressBar, QTextEdit, QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QSpinBox, QSystemTrayIcon, QCheckBox
)
from PyQt5.QtGui import QFont, QIcon, QColor    
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QRunnable, QThreadPool, pyqtSlot

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError, GeoRestrictedError, UnsupportedError
from yt_dlp import YoutubeDL
from yt_dlp_gemini_tagger import GeminiID3PostProcessor

ffmpeg_dir = os.path.join(os.path.dirname(__file__), "..", "ffmpeg")
ydl_opts = {
    "ffmpeg_location": ffmpeg_dir,
    "outtmpl": "%(title).200s.%(ext)s"
}
# -----------------------------
# Signals
# -----------------------------
class SignalHandler(QObject):
    # message, level -> "info" | "success" | "warning" | "error"
    update_status = pyqtSignal(str, str)
    # percent, key (per-video progress)
    update_progress = pyqtSignal(int, str)
    # one-video finished, key, filename
    finished_one = pyqtSignal(str, str)
    # history event
    history_event = pyqtSignal(dict)


# -----------------------------
# Worker (one URL per worker)
# -----------------------------
class DownloadWorker(QRunnable):
    def __init__(self, url, key, folder, quality, tmpl, signals, flags):
        """
        flags: dict with keys:
            cancel (bool), pause (bool)
        """
        super().__init__()
        self.url = url
        self.key = key
        self.folder = folder
        self.quality = quality
        self.tmpl = tmpl
        self.signals = signals
        self.flags = flags

    @pyqtSlot()
    def run(self):
        self.process_download_one(self.url, self.key, self.folder, self.quality, self.tmpl, self.flags)

    # ---- yt-dlp per-video execution ----
    def process_download_one(self, url, key, folder, quality, tmpl, flags):
        format_map = {
            "Best_Video+Audio": "bestvideo+bestaudio/best",
            "1080p": "bestvideo[height=1080]+bestaudio/best",
            "720p": "bestvideo[height=720]+bestaudio/best",
            "480p": "bestvideo[height=480]+bestaudio/best",
            "only_mp3": "bestaudio"
        }

        # Hook bound to this specific key
        def hook(d):
            # pause support (soft pause: abort current request; resume will re-run with continuedl)
            if flags.get("pause", False) or flags.get("cancel", False):
                raise Exception("Paused/Cancelled")

            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    percent = int(downloaded / total * 100)
                    self.signals.update_progress.emit(percent, key)
            elif d['status'] == 'finished':
                filename = d.get('filename', '') or ''
                # Report 100% for cosmetic closure
                self.signals.update_progress.emit(100, key)
                self.signals.finished_one.emit(key, filename)

        outtmpl = tmpl.strip() if tmpl.strip() else '%(title).200s.%(ext)s'

        # SABR-safe fallback format
        sabr_safe_format = "bv*[protocol^=http]+ba*[protocol^=http]/best"

        # Use your format_map if present, otherwise fallback to SABR-safe
        selected_format = format_map.get(quality, sabr_safe_format)

        ydl_opts = {
            'format': selected_format,
            'paths': {'home': folder},
            'outtmpl': outtmpl,
            'windowsfilenames': True,
            'restrictfilenames': True,
            'progress_hooks': [hook],
            'socket_timeout': 30,
            'ignoreerrors': True,
            'noprogress': True,
            'continuedl': True,        # resume partial downloads
            'updatetime': False,
            'writethumbnail': quality == "only_mp3",
            'postprocessor_args': [],
            'cookies_from_browser': ('chrome',),
        }


        # MP3 post-processing with metadata + thumbnail embedding
        if quality == "only_mp3":
            ydl_opts['postprocessors'] = [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192'
                },
                {'key': 'FFmpegMetadata'},
                {'key': 'EmbedThumbnail'},
                # GeminiID3PostProcessor()
            ]

        start_ts = datetime.now().isoformat()
        ok = False
        err_msg = None

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if quality == "only_mp3":
                    ydl.add_post_processor(GeminiID3PostProcessor(ydl))
                ydl.download([url])
            ok = True
        except GeoRestrictedError:
            err_msg = "Geo-restricted; skipped."
            self.signals.update_status.emit(f"❌ {err_msg}", "warning")
        except ExtractorError as e:
            err_msg = f"Extractor error: {e}"
            self.signals.update_status.emit(f"❌ {err_msg}", "error")
        except DownloadError as e:
            err_msg = f"Download error: {e}"
            self.signals.update_status.emit(f"❌ {err_msg}", "error")
        except socket.timeout:
            err_msg = "Network timeout."
            self.signals.update_status.emit(f"❌ {err_msg}", "error")
        except Exception as e:
            # Determine whether this was a pause/cancel or actual error
            if flags.get("pause", False):
                err_msg = "Paused."
                self.signals.update_status.emit("⏸️ Download paused.", "warning")
            elif flags.get("cancel", False):
                err_msg = "Cancelled."
                self.signals.update_status.emit("⏹️ Download cancelled.", "warning")
            else:
                err_msg = f"Unexpected error: {e}"
                self.signals.update_status.emit(f"❌ {err_msg}", "error")

        # Emit history record
        self.signals.history_event.emit({
            "ts": start_ts,
            "url": url,
            "key": key,
            "folder": folder,
            "quality": quality,
            "template": outtmpl,
            "status": "ok" if ok else "error",
            "error": err_msg
        })


# -----------------------------
# Main Window
# -----------------------------
class YouTubeDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # self.setWindowTitle("YT Playlist Downloader")
        QApplication.setFont(QFont("Arial", 14))
        self.signals = SignalHandler()
        self.playlist_items = []    # entries with at least {title, url/id}
        self.threadpool = QThreadPool()
        self.flags = {"cancel": False, "pause": False}
        self.item_widgets = {}      # key -> {"item": QListWidgetItem, "bar": QProgressBar, "label": QLabel}
        self.tray = None            # QSystemTrayIcon
        self.history_path = None    # set when folder chosen

        self.init_ui()
        self.connect_signals()

    # ---------- UI ----------
    def init_ui(self):
        self.setWindowTitle("YT Playlist Downloader")
        self.setGeometry(350, 30, 1300, 1000)
        self.setStyleSheet("background-color: #2E3440; color: #D8DEE9;")

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        root = QVBoxLayout()
        main_widget.setLayout(root)

        # Title
        title_label = QLabel("YouTube Playlist / Single Video Downloader")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #88C0D0; margin: 10px;")
        root.addWidget(title_label)

        # URL row
        url_row = QHBoxLayout()
        url_label = QLabel("Enter URL:")
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Playlist or single video URL (YouTube)")
        self.url_entry.setStyleSheet("font: 16px; background-color: #4C566A; color: #D8DEE9; padding: 8px; border-radius: 5px;")
        url_row.addWidget(url_label)
        url_row.addWidget(self.url_entry)

        fetch_button = QPushButton("Fetch Info")
        fetch_button.setStyleSheet("background-color: #5E81AC; color: #D8DEE9; padding: 8px; border-radius: 5px;")
        fetch_button.clicked.connect(self.fetch_info)
        url_row.addWidget(fetch_button)

        update_button = QPushButton("Update yt-dlp")
        update_button.setStyleSheet("background-color: #434C5E; color: #D8DEE9; padding: 8px; border-radius: 5px;")
        update_button.clicked.connect(self.update_ytdlp)
        url_row.addWidget(update_button)

        root.addLayout(url_row)

        # Info label
        self.playlist_info_label = QLabel()
        self.playlist_info_label.setWordWrap(True)
        root.addWidget(self.playlist_info_label)

        # Search/filter
        filter_row = QHBoxLayout()
        filter_label = QLabel("Filter:")
        self.filter_entry = QLineEdit()
        self.filter_entry.setPlaceholderText("Type to filter listed videos…")
        self.filter_entry.setStyleSheet("font: 14px; background-color: #4C566A; color: #D8DEE9; padding: 6px; border-radius: 5px;")
        self.filter_entry.textChanged.connect(self.apply_filter)
        filter_row.addWidget(filter_label)
        filter_row.addWidget(self.filter_entry)
        root.addLayout(filter_row)

        # Video list with per-item progressbars
        self.video_list = QListWidget()
        self.video_list.setStyleSheet("font: 22px; background-color: #3B4252; color: #ECEFF4; padding: 1px; border-radius: 1px;")
        root.addWidget(self.video_list)

        # Select all / none
        select_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All / Deselect All")
        select_all_btn.setStyleSheet("background-color: #81A1C1; color: #2E3440; padding: 6px; border-radius: 5px;")
        select_all_btn.clicked.connect(self.toggle_select_all)
        select_row.addWidget(select_all_btn)

        # Concurrency control
        conc_label = QLabel("Parallel downloads:")
        self.conc_spin = QSpinBox()
        self.conc_spin.setRange(1, 8)
        self.conc_spin.setValue(min(4, self.threadpool.maxThreadCount()))
        self.conc_spin.setStyleSheet("background-color: #4C566A; color: #D8DEE9; padding: 6px; border-radius: 5px;")
        select_row.addWidget(conc_label)
        select_row.addWidget(self.conc_spin)

        root.addLayout(select_row)

        # Quality + Folder selection in one row
        q_row = QHBoxLayout()

        # Quality dropdown
        quality_label = QLabel("Quality:")
        self.quality_combobox = QComboBox()
        self.quality_combobox.addItems(["Best_Video+Audio", "1080p", "720p", "480p", "only_mp3"])
        self.quality_combobox.setStyleSheet("font: 16px; background-color: #4C566A; color: #D8DEE9; padding: 8px; border-radius: 5px;")

        # Folder selection
        folder_label = QLabel("Download Folder:")
        self.folder_path = QLineEdit()
        self.folder_path.setPlaceholderText("Select download folder…")
        self.folder_path.setStyleSheet("font: 16px; background-color: #4C566A; color: #D8DEE9; padding: 8px; border-radius: 5px;")

        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.select_folder)

        # Add to row
        q_row.addWidget(quality_label)
        q_row.addWidget(self.quality_combobox)
        q_row.addWidget(folder_label)
        q_row.addWidget(self.folder_path)
        q_row.addWidget(browse_button)

        root.addLayout(q_row)


        # Overall progress (kept for backwards compatibility as "active task" indicator)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #4C566A; color: #D8DEE9; padding: 5px; border-radius: 5px; }"
            "QProgressBar::chunk { background-color: #88C0D0; border-radius: 5px; }"
        )
        root.addWidget(self.progress_bar)

        # Status log (timestamped + colored)
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setFont(QFont("Courier New", 11))
        self.status_text.setStyleSheet("background-color: #2E3440; color: #D8DEE9; padding: 8px; border-radius: 5px;")
        self.status_text.setMinimumHeight(130) 
        self.status_text.setMaximumHeight(190)
        root.addWidget(self.status_text, stretch=2)

        # Log controls + Pause/Resume/Cancel
        control_row = QHBoxLayout()

        dl_button = QPushButton("▶ Download Selected")
        dl_button.setStyleSheet("background-color: #5E81AC; color: #D8DEE9; padding: 10px; border-radius: 5px;")
        dl_button.clicked.connect(self.download_selected_videos)
        control_row.addWidget(dl_button)

        pause_button = QPushButton("⏸ Pause")
        pause_button.setStyleSheet("background-color: #A3BE8C; color: #2E3440; padding: 10px; border-radius: 5px;")
        pause_button.clicked.connect(self.pause_downloads)
        control_row.addWidget(pause_button)

        resume_button = QPushButton("⏵ Resume")
        resume_button.setStyleSheet("background-color: #8FBCBB; color: #2E3440; padding: 10px; border-radius: 5px;")
        resume_button.clicked.connect(self.resume_downloads)
        control_row.addWidget(resume_button)

        cancel_button = QPushButton("⏹ Cancel")
        cancel_button.setStyleSheet("background-color: #BF616A; color: #ECEFF4; padding: 10px; border-radius: 5px;")
        cancel_button.clicked.connect(self.cancel_downloads)
        control_row.addWidget(cancel_button)

        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.setStyleSheet("background-color: #D08770; color: #2E3440; padding: 10px; border-radius: 5px;")
        clear_log_btn.clicked.connect(self.status_text.clear)
        control_row.addWidget(clear_log_btn)

        root.addLayout(control_row)

        # System tray (for notifications)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self)
            # If you have an icon file, set it here. Fallback to default if not.
            self.tray.setIcon(QIcon("icon.png"))
            self.tray.setVisible(True)

    # ---------- Signals/Slots ----------
    def connect_signals(self):
        self.signals.update_status.connect(self.append_status)
        self.signals.update_progress.connect(self.set_item_progress)
        self.signals.finished_one.connect(self.one_finished)
        self.signals.history_event.connect(self.append_history)

    def append_status(self, text, level="info"):
        ts = datetime.now().strftime("[%H:%M:%S] ")
        # Colorize
        if level == "error":
            self.status_text.setTextColor(QColor("red"))
        elif level == "success":
            self.status_text.setTextColor(QColor("green"))
        elif level == "warning":
            self.status_text.setTextColor(QColor("yellow"))
        else:
            self.status_text.setTextColor(QColor("white"))
        self.status_text.append(ts + text)
        self.status_text.verticalScrollBar().setValue(self.status_text.verticalScrollBar().maximum())

    def set_item_progress(self, percent, key):
        w = self.item_widgets.get(key)
        if not w:
            # fallback to global progress if unknown
            self.progress_bar.setValue(percent)
            return
        w["bar"].setValue(percent)

    def one_finished(self, key, filename):
        self.append_status(f"Finished: {os.path.basename(filename)}", "success")
        if self.tray:
            self.tray.showMessage("Download finished", os.path.basename(filename), QSystemTrayIcon.Information, 3000)

    def append_history(self, record: dict):
        try:
            if not self.history_path:
                return
            with open(self.history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            # non-fatal
            self.append_status(f"History write failed: {e}", "warning")

    # ---------- Helpers ----------
    def key_for_entry(self, entry):
        """
        Prefer video ID when available; otherwise fallback to URL text.
        """
        vid = entry.get("id")
        if vid:
            return vid
        # some extract_flat entries have URL as id-like
        return entry.get("url") or entry.get("webpage_url") or entry.get("title") or str(id(entry))

    def set_item_widget(self, entry, idx):
        """
        Create a QWidget per list item: [checkbox label] [progressbar]
        """

        entry["_original_index"] = idx 

        title = entry.get("title", f"Video {idx}")
        key = self.key_for_entry(entry)

        item = QListWidgetItem()

        # container widget
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(6, 4, 6, 4)

        checkbox = QCheckBox(f"{idx}. {title}")
        checkbox.setChecked(True)
        checkbox.setStyleSheet("color: #ECEFF4;")

        bar = QProgressBar()
        bar.setMinimum(0)
        bar.setMaximum(100)
        bar.setValue(0)
        bar.setStyleSheet(
            "QProgressBar { background-color: #4C566A; color: #D8DEE9; padding: 2px; border-radius: 4px; }"
            "QProgressBar::chunk { background-color: #88C0D0; border-radius: 4px; }"
        )

        h.addWidget(checkbox, stretch=5)
        h.addWidget(bar, stretch=2)

        self.video_list.addItem(item)
        self.video_list.setItemWidget(item, container)
        self.item_widgets[key] = {
            "item": item,
            "bar": bar,
            "checkbox": checkbox,
            "entry": entry
        }


    def visible_text(self, item):
        w = self.video_list.itemWidget(item)
        if not w:
            return item.text()
        lbl = w.findChild(QLabel)
        return lbl.text() if lbl else item.text()

    # ---------- Actions ----------
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.folder_path.setText(folder)
            self.history_path = os.path.join(folder, "download_history.jsonl")
            if not os.path.exists(self.history_path):
                with open(self.history_path, "w", encoding="utf-8") as f:
                    pass
                
    def fetch_info(self):
        url = self.url_entry.text().strip()
        if not url:
            QMessageBox.warning(self, "Input Error", "Please enter a URL.")
            return

        self.append_status("Fetching information…", "info")
        # ydl_opts = {'extract_flat': True, 'quiet': True}
        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            # 'cookies': r"E:\myWorkPlace\PROJECTS\youtube-downloader\temp_files\yt-cookies.txt",
            # 'cookiesfrombrowser': ('chrome',),  # or use 'cookies': r"C:\path\to\cookies.txt"
            'cookies_from_browser': ('chrome',),
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    QMessageBox.warning(self, "Error", "Unable to fetch info. The URL may be empty or unavailable.")
                    return

                # Normalize to list of entries (playlist or single)
                entries = []
                if "entries" in info and isinstance(info["entries"], list):
                    # playlist
                    entries = info["entries"]
                    title = info.get('title', 'N/A')
                    uploader = info.get('uploader', 'N/A')
                    count = info.get('playlist_count', len(entries))
                    summary = f"Type: Playlist\nTitle: {title}\nVideos: {count}\nUploader: {uploader}"
                else:
                    # single video
                    entries = [info]
                    summary = f"Type: Single Video\nTitle: {info.get('title','N/A')}\nUploader: {info.get('uploader','N/A')}"

                self.playlist_items = entries
                self.playlist_info_label.setText(summary)

                # Populate list with widgets
                self.video_list.clear()
                self.item_widgets.clear()
                for idx, entry in enumerate(self.playlist_items, start=1):
                    # For extract_flat playlist, entry['url'] may be video ID; construct a full URL
                    if entry.get("url") and "http" not in entry["url"]:
                        entry["webpage_url"] = f"https://www.youtube.com/watch?v={entry['url']}"
                    elif entry.get("webpage_url") is None and entry.get("url"):
                        entry["webpage_url"] = entry["url"]
                    self.set_item_widget(entry, idx)

                self.append_status("Info fetched successfully.", "success")

        except GeoRestrictedError:
            QMessageBox.critical(self, "Geo-Restricted", "This content is not available in your region.")
            self.signals.update_status.emit("Error: Geo-restricted content.", "error")
        except ExtractorError as e:
            QMessageBox.critical(self, "Extractor Error", f"Could not extract info: {e}")
            self.signals.update_status.emit(f"Extractor error: {e}", "error")
        except UnsupportedError:
            QMessageBox.critical(self, "Unsupported URL", "Unsupported link. Provide a valid YouTube URL.")
            self.signals.update_status.emit("Unsupported URL.", "error")
        except socket.timeout:
            QMessageBox.critical(self, "Network Timeout", "Request to YouTube timed out. Check your connection.")
            self.signals.update_status.emit("Network timeout.", "error")
        except DownloadError as e:
            QMessageBox.critical(self, "Download Error", f"yt-dlp failed to fetch info: {e}")
            self.signals.update_status.emit(f"Download error: {e}", "error")
        except Exception as e:
            QMessageBox.critical(self, "Unknown Error", f"An unexpected error occurred: {str(e)}")
            self.signals.update_status.emit(f"Unexpected error: {str(e)}", "error")

    def apply_filter(self, text):
        text = text.lower().strip()
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            w = self.video_list.itemWidget(item)
            lbl = w.findChild(QLabel) if w else None
            s = (lbl.text() if lbl else item.text()).lower()
            item.setHidden(text not in s)

    def toggle_select_all(self):
        all_checked = all(meta["checkbox"].isChecked() for meta in self.item_widgets.values())
        new_state = not all_checked
        for meta in self.item_widgets.values():
            meta["checkbox"].setChecked(new_state)


    def gather_selected_urls(self):
        selected = []
        for key, meta in self.item_widgets.items():
            if meta["checkbox"].isChecked():
                entry = meta["entry"]
                url = entry.get("webpage_url") or entry.get("url")
                if url:
                    selected.append((key, url))
        return selected


    def download_selected_videos(self):
        folder = self.folder_path.text().strip()
        quality = self.quality_combobox.currentText()
        tmpl = "%(title).200s.%(ext)s"


        if not self.playlist_items:
            QMessageBox.warning(self, "Error", "No playlist/video loaded. Fetch info first.")
            return
        if not folder:
            QMessageBox.warning(self, "Input Error", "Please select a download folder.")
            return

        sel = self.gather_selected_urls()
        if not sel:
            QMessageBox.warning(self, "Selection Error", "No videos selected.")
            return

        # reset flags
        self.flags["cancel"] = False
        self.flags["pause"] = False

        # prepare history path if not set
        if not self.history_path:
            self.history_path = os.path.join(folder, "download_history.jsonl")

        # set threadpool concurrency
        self.threadpool.setMaxThreadCount(self.conc_spin.value())
        self.append_status(f"Starting downloads ({len(sel)} item(s)) with concurrency = {self.conc_spin.value()}…", "info")

        # launch one worker per selected url
        for key, url in sel:
            meta = self.item_widgets.get(key)
            entry = meta["entry"] if meta else {}
            orig_index = entry.get("_original_index", 0)
            zindex = str(orig_index).zfill(3)   # fixed 3 digits
            per_tmpl = f"{zindex} - %(title).200s.%(ext)s"

            # reset per-item progress if available
            if meta:
                meta["bar"].setValue(0)

            worker = DownloadWorker(
                url=url,
                key=key,
                folder=folder,
                quality=quality,
                tmpl=per_tmpl,
                signals=self.signals,
                flags=self.flags
            )
            self.threadpool.start(worker)




    def pause_downloads(self):
        self.flags["pause"] = True
        self.append_status("Pause requested. Current tasks will stop safely; resume will continue.", "warning")

    def resume_downloads(self):
        # "resume" is simply clearing pause and re-issuing downloads for anything not at 100%.
        if not self.playlist_items:
            return
        self.flags["pause"] = False
        # collect not-complete items among checked ones
        pending = []
        for key, meta in self.item_widgets.items():
            if meta["item"].checkState() == Qt.Checked and meta["bar"].value() < 100:
                entry = meta["entry"]
                url = entry.get("webpage_url") or entry.get("url")
                if url:
                    pending.append((key, url))
        if not pending:
            self.append_status("Nothing to resume; all selected items appear complete.", "info")
            return
        self.append_status(f"Resuming {len(pending)} item(s)…", "info")
        self.download_specific(pending)

    def cancel_downloads(self):
        self.flags["cancel"] = True
        self.append_status("Cancellation requested. Active tasks will terminate shortly.", "warning")

    def download_specific(self, pairs):
        folder = self.folder_path.text().strip()
        quality = self.quality_combobox.currentText()
        tmpl = "%(title).200s.%(ext)s"


        self.threadpool.setMaxThreadCount(self.conc_spin.value())
        for key, url in pairs:
            worker = DownloadWorker(
                url=url,
                key=key,
                folder=folder,
                quality=quality,
                tmpl=tmpl,
                signals=self.signals,
                flags=self.flags
            )
            self.threadpool.start(worker)

    def update_ytdlp(self):
        try:
            self.append_status("Updating yt-dlp via pip…", "info")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"])
            self.append_status("yt-dlp updated successfully. Please restart the app to use the new version.", "success")
        except subprocess.CalledProcessError as e:
            self.append_status(f"yt-dlp update failed: {e}", "error")

    # ---------- Entry point ----------
    def closeEvent(self, event):
        # best-effort to stop workers
        self.flags["cancel"] = True
        super().closeEvent(event)

def main():
    import sys
    from PyQt5.QtWidgets import QApplication
    # from app.main import YouTubeDownloaderApp  # adjust if your class is elsewhere

    app = QApplication(sys.argv)
    window = YouTubeDownloaderApp()
    window.show()
    sys.exit(app.exec_())

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    main()

