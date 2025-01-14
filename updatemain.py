import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                            QVBoxLayout, QHBoxLayout, QLineEdit, 
                            QPushButton, QLabel, QProgressBar,
                            QFileDialog, QComboBox, QGroupBox,
                            QListWidget, QTabWidget)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSettings
from PyQt6.QtGui import QKeySequence, QShortcut, QPalette, QColor
import yt_dlp
from datetime import datetime
import json

# Define quality presets
QUALITY_PRESETS = {
    'High Quality (320kbps)': '320',
    'Standard Quality (192kbps)': '192',
    'Medium Quality (128kbps)': '128',
    'Low Quality (96kbps)': '96',
}

# Define format presets
FORMAT_PRESETS = {
    'MP3': 'mp3',
    'M4A': 'm4a',
    'WAV': 'wav',
    'FLAC': 'flac',
    'OPUS': 'opus',
}

class DownloadWorker(QThread):
    finished = pyqtSignal()
    progress = pyqtSignal(str, float)
    error = pyqtSignal(str)

    def __init__(self, url, output_dir, quality, format_):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.quality = quality
        self.format = format_
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': self.format,
                'preferredquality': self.quality,
            }],
            'progress_hooks': [self.progress_hook],
            'retries': 5,
            'fragment_retries': 5,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.youtube.com/',
            },
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'skip_download': False,
            'verbose': True,
            'nocheckcertificate': True,
            'prefer_insecure': True,
            'geo_bypass': True,
            'cookiefile': 'cookies.txt',
            'buffersize': 1024 * 16,
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        }
        self.ydl = yt_dlp.YoutubeDL(self.ydl_opts)

    def run(self):
        try:
            self.ydl.download([self.url])
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            try:
                percent_float = float(percent.strip('%'))
            except:
                percent_float = 0
            self.progress.emit(f'Downloading... {percent} at {speed}', percent_float)
        elif d['status'] == 'finished':
            self.progress.emit(f'Download complete. Converting to {self.format.upper()}...', 100)
        elif d['status'] == 'error':
            self.progress.emit('Error occurred, retrying...', 0)

class DownloadHistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_history()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        self.clear_btn = QPushButton("Clear History")
        self.clear_btn.clicked.connect(self.clear_history)
        header.addWidget(QLabel("Download History"))
        header.addStretch()
        header.addWidget(self.clear_btn)
        
        # History list
        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        
        layout.addLayout(header)
        layout.addWidget(self.history_list)

    def add_to_history(self, url, format_, quality):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item = {
            'timestamp': timestamp,
            'url': url,
            'format': format_,
            'quality': quality
        }
        
        # Add to list widget
        self.history_list.insertItem(
            0, 
            f"{timestamp} - {format_} ({quality}kbps)\n{url}"
        )
        
        # Save to file
        history = self.load_history_from_file()
        history.append(item)
        self.save_history_to_file(history)

    def clear_history(self):
        self.history_list.clear()
        self.save_history_to_file([])

    def load_history(self):
        history = self.load_history_from_file()
        for item in reversed(history):
            self.history_list.addItem(
                f"{item['timestamp']} - {item['format']} ({item['quality']}kbps)\n{item['url']}"
            )

    def load_history_from_file(self):
        try:
            with open('download_history.json', 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_history_to_file(self, history):
        with open('download_history.json', 'w') as f:
            json.dump(history, f, indent=2)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Downloader & Converter")
        self.setMinimumSize(600, 300)
        
        # Create history widget first
        self.history_widget = DownloadHistoryWidget()
        
        # Setup the main UI (includes converter widget)
        self.setup_ui()
        
        # Setup tabs last
        self.setup_tabs()

    def setup_ui(self):
        # Create the main converter widget and its layout
        self.converter_widget = QWidget()
        self.main_layout = QVBoxLayout(self.converter_widget)

        # Create top toolbar for dark mode toggle
        toolbar_layout = QHBoxLayout()
        self.dark_mode_btn = QPushButton("🌙")  # Moon emoji for dark mode
        self.dark_mode_btn.setCheckable(True)
        self.dark_mode_btn.setFixedSize(30, 30)
        self.dark_mode_btn.clicked.connect(self.toggle_dark_mode)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.dark_mode_btn)
        
        # Load saved dark mode preference
        settings = QSettings('YourApp', 'AudioConverter')
        is_dark = settings.value('dark_mode', False, type=bool)
        self.dark_mode_btn.setChecked(is_dark)
        self.toggle_dark_mode(is_dark)

        # URL input section
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter YouTube URL")
        url_layout.addWidget(QLabel("URL:"))
        url_layout.addWidget(self.url_input)

        # Output directory section
        dir_layout = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("Output Directory")
        self.dir_input.setText(os.path.expanduser("~/Downloads"))
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_directory)
        dir_layout.addWidget(QLabel("Save to:"))
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.browse_btn)

        # Format and Quality Selection Group
        format_group = QGroupBox("Format & Quality Settings")
        format_layout = QHBoxLayout()
        
        # Format selection
        format_section = QVBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(FORMAT_PRESETS.keys())
        self.format_combo.setCurrentText("MP3")  # Default format
        format_section.addWidget(QLabel("Format:"))
        format_section.addWidget(self.format_combo)
        
        # Quality selection
        quality_section = QVBoxLayout()
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(QUALITY_PRESETS.keys())
        self.quality_combo.setCurrentText("High Quality (320kbps)")  # Default quality
        quality_section.addWidget(QLabel("Quality:"))
        quality_section.addWidget(self.quality_combo)
        
        format_layout.addLayout(format_section)
        format_layout.addLayout(quality_section)
        format_group.setLayout(format_layout)

        # Download button
        self.download_btn = QPushButton("Convert")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #E4E4E4;
                color: #000000;
                padding: 6px 12px;
                border: 1px solid #C4C4C4;
                border-radius: 6px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #EBEBEB;
            }
            QPushButton:pressed {
                background-color: #D4D4D4;
            }
            QPushButton:disabled {
                background-color: #F5F5F5;
                color: #A0A0A0;
                border-color: #E5E5E5;
            }
        """)
        
        # Progress section
        progress_layout = QVBoxLayout()
        self.status_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #C4C4C4;
                border-radius: 6px;
                background-color: #F5F5F5;
                text-align: center;
                height: 16px;
            }
            QProgressBar::chunk {
                background-color: #D4D4D4;
                border-radius: 5px;
            }
        """)
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)

        # Add toolbar at the top
        self.main_layout.addLayout(toolbar_layout)
        
        # Add all other layouts
        self.main_layout.addLayout(url_layout)
        self.main_layout.addLayout(dir_layout)
        self.main_layout.addWidget(format_group)
        self.main_layout.addWidget(self.download_btn)
        self.main_layout.addLayout(progress_layout)
        self.main_layout.addStretch()

        # Line edits styling
        line_edit_style = """
            QLineEdit {
                padding: 5px;
                border: 1px solid #C4C4C4;
                border-radius: 6px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #919191;
            }
        """
        self.url_input.setStyleSheet(line_edit_style)
        self.dir_input.setStyleSheet(line_edit_style)

        # Browse button
        self.browse_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 10px;
                border: 1px solid #C4C4C4;
                border-radius: 6px;
                background-color: #E4E4E4;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #EBEBEB;
            }
            QPushButton:pressed {
                background-color: #D4D4D4;
            }
        """)

        # Combo boxes styling
        combo_style = """
            QComboBox {
                padding: 5px;
                border: 1px solid #C4C4C4;
                border-radius: 6px;
                background-color: #E4E4E4;
                min-width: 200px;
            }
            QComboBox:hover {
                background-color: #EBEBEB;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #666;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #C4C4C4;
                border-radius: 6px;
                background-color: white;
                selection-background-color: #E4E4E4;
                selection-color: black;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 5px;
                min-height: 25px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #F5F5F5;
            }
        """
        self.format_combo.setStyleSheet(combo_style)
        self.quality_combo.setStyleSheet(combo_style)

        # Group box styling
        format_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #C4C4C4;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)

        # Dark mode button styling
        self.dark_mode_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #C4C4C4;
                border-radius: 15px;
                background-color: #E4E4E4;
            }
            QPushButton:checked {
                background-color: #2D2D2D;
                color: white;
            }
        """)

        self.setup_shortcuts()
        self.setup_dark_mode()

    def setup_shortcuts(self):
        # Enter key for converting
        self.url_input.returnPressed.connect(self.start_download)
        
        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.browse_directory)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self.url_input.setFocus)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self.close)
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.close)

    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "Select Output Directory",
            self.dir_input.text(),
            QFileDialog.Option.ShowDirsOnly
        )
        if dir_path:
            self.dir_input.setText(dir_path)

    def start_download(self):
        url = self.url_input.text().strip()
        output_dir = self.dir_input.text().strip()
        
        # Get selected format and quality
        format_name = self.format_combo.currentText()
        quality_name = self.quality_combo.currentText()
        
        format_ = FORMAT_PRESETS[format_name]
        quality = QUALITY_PRESETS[quality_name]

        if not url:
            self.status_label.setText("Please enter a URL")
            return

        if not output_dir or not os.path.isdir(output_dir):
            self.status_label.setText("Please select a valid output directory")
            return

        self.download_btn.setEnabled(False)
        self.status_label.setText("Starting download...")
        self.progress_bar.setValue(0)
        
        # Create and start download thread
        self.worker = DownloadWorker(url, output_dir, quality, format_)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.download_finished)
        self.worker.error.connect(self.download_error)
        self.worker.start()

        # Add to history after successful download
        self.history_widget.add_to_history(url, format_, quality)

    def update_progress(self, message, percent):
        self.status_label.setText(message)
        self.progress_bar.setValue(int(percent))

    def download_finished(self):
        self.status_label.setText("Conversion complete!")
        self.progress_bar.setValue(100)
        self.download_btn.setEnabled(True)
        
        # Add to history after successful download
        url = self.url_input.text().strip()
        format_name = self.format_combo.currentText()
        quality_name = self.quality_combo.currentText()
        format_ = FORMAT_PRESETS[format_name]
        quality = QUALITY_PRESETS[quality_name]
        self.history_widget.add_to_history(url, format_, quality)
        
        self.url_input.clear()

    def download_error(self, error_message):
        self.status_label.setText(f"Error: {error_message}")
        self.progress_bar.setValue(0)
        self.download_btn.setEnabled(True)

    def setup_tabs(self):
        tab_widget = QTabWidget()
        
        # Add the tab widget styling here
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border-top: 1px solid #CCCCCC;
                background: transparent;
                position: absolute;
                top: -1px;
            }
            
            QTabBar::tab {
                background-color: transparent;
                color: #666666;
                padding: 4px 16px;
                margin-right: 2px;
                border: none;
                font-size: 13px;
            }
            
            QTabBar::tab:hover {
                color: #007AFF;
            }
            
            QTabBar::tab:selected {
                color: #007AFF;
                border-bottom: 2px solid #007AFF;
            }
            
            QTabWidget {
                background: transparent;
            }
            
            QTabWidget::tab-bar {
                alignment: left;
                border: none;
            }
        """)
        
        # Add the tabs
        tab_widget.addTab(self.converter_widget, "Converter")
        tab_widget.addTab(self.history_widget, "History")
        
        self.setCentralWidget(tab_widget)

    def setup_dark_mode(self):
        # Add dark mode toggle button
        self.dark_mode_btn = QPushButton()
        self.dark_mode_btn.setCheckable(True)
        self.dark_mode_btn.setChecked(False)
        self.dark_mode_btn.clicked.connect(self.toggle_dark_mode)
        
        # Load saved dark mode preference
        settings = QSettings('YourApp', 'AudioConverter')
        is_dark = settings.value('dark_mode', False, type=bool)
        self.dark_mode_btn.setChecked(is_dark)
        self.toggle_dark_mode(is_dark)

    def toggle_dark_mode(self, enabled):
        settings = QSettings('YourApp', 'AudioConverter')
        settings.setValue('dark_mode', enabled)
        
        if enabled:
            self.dark_mode_btn.setText("☀️")  # Sun emoji for light mode
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #2D2D2D;
                    color: #FFFFFF;
                }
                QLineEdit, QComboBox {
                    background-color: #3D3D3D;
                    color: #FFFFFF;
                    border: 1px solid #555555;
                }
                QPushButton {
                    background-color: #3D3D3D;
                    color: #FFFFFF;
                    border: 1px solid #555555;
                }
                QPushButton:hover {
                    background-color: #4D4D4D;
                }
                QPushButton:pressed {
                    background-color: #2D2D2D;
                }
                QProgressBar {
                    border: 1px solid #555555;
                    background-color: #3D3D3D;
                }
                QProgressBar::chunk {
                    background-color: #555555;
                }
                QGroupBox {
                    border: 1px solid #555555;
                }
                QTabWidget::pane {
                    border: 1px solid #555555;
                }
                QTabBar::tab {
                    background-color: #3D3D3D;
                    color: #FFFFFF;
                    border: 1px solid #555555;
                }
                QTabBar::tab:selected {
                    background-color: #4D4D4D;
                }
                QListWidget {
                    background-color: #3D3D3D;
                    alternate-background-color: #353535;
                }
                QListWidget::item {
                    color: #FFFFFF;
                }
            """)
        else:
            self.dark_mode_btn.setText("🌙")  # Moon emoji for dark mode
            self.setStyleSheet("")  # Reset to default light theme

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 
