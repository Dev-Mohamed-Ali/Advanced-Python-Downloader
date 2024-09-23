import sys
import os
import time
import logging
from urllib.parse import urlparse
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QListWidget, QProgressBar, QFileDialog,
                             QMessageBox, QComboBox, QSpinBox, QLineEdit, QDialog, QFormLayout,
                             QListWidgetItem, QInputDialog, QScrollArea, QGroupBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QIcon
from pypdl import Pypdl

class HeaderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Headers")
        layout = QFormLayout(self)

        self.referer = QLineEdit(self)
        self.user_agent = QLineEdit(self)

        layout.addRow("Referer:", self.referer)
        layout.addRow("User-Agent:", self.user_agent)

        buttons = QHBoxLayout()
        self.ok_button = QPushButton("OK", self)
        self.cancel_button = QPushButton("Cancel", self)
        buttons.addWidget(self.ok_button)
        buttons.addWidget(self.cancel_button)

        layout.addRow(buttons)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

class DownloadThread(QThread):
    progress_update = pyqtSignal(int, float, str)
    download_complete = pyqtSignal(bool, str)

    def __init__(self, url, download_path, headers, progress=0):
        super().__init__()
        self.url = url
        self.download_path = download_path
        self.headers = headers
        self.paused = False
        self.dl = None
        self.initial_progress = progress

    def run(self):
        self.dl = Pypdl(headers=self.headers)
        file_name = os.path.basename(urlparse(self.url).path)

        try:
            self.dl.start(
                url=self.url,
                display=True,
                block=False,
                multisegment=True,
                segments=10,
                file_path=self.download_path,
                retries=3,
            )

            while not self.dl.completed:
                if self.paused:
                    time.sleep(0.5)
                    continue
                if self.dl.failed:
                    raise Exception("An error occurred.")
                self.progress_update.emit(self.dl.progress, self.dl.speed, file_name)
                time.sleep(0.5)

            self.progress_update.emit(100, 0, file_name)
            self.download_complete.emit(True, file_name)
        except Exception as e:
            logging.error(f"Error downloading {file_name}: {e}")
            self.download_complete.emit(False, file_name)

    def pause(self):
        self.paused = True
        if self.dl:
            self.dl.stop()

    def resume(self):
        self.paused = False
        if self.dl:
            try:
                # Restart the download from the last progress point
                self.dl.start(
                    url=self.url,
                    display=True,
                    block=False,
                    multisegment=True,
                    segments=10,
                    file_path=self.download_path,
                    retries=5,
                )
            except Exception as e:
                logging.error(f"Error resuming download for {self.url}: {e}")


class DownloadWindow(QWidget):
    def __init__(self, url, download_path, headers, progress=0):
        super().__init__()
        self.url = url
        self.download_path = download_path
        self.headers = headers
        self.progress = progress
        self.thread = None
        self.setWindowTitle(f"Downloading: {os.path.basename(urlparse(url).path)}")
        self.setGeometry(100, 100, 400, 150)

        layout = QVBoxLayout(self)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(progress)
        layout.addWidget(self.progress_bar)

        self.speed_label = QLabel("Download Speed: 0 MB/s")
        layout.addWidget(self.speed_label)

        self.pause_resume_button = QPushButton("Pause")
        self.pause_resume_button.clicked.connect(self.toggle_pause_resume)
        layout.addWidget(self.pause_resume_button)

        self.cooldown_timer = QTimer(self)
        self.cooldown_timer.timeout.connect(self.enable_pause_resume_button)
        self.cooldown_duration = 1500  # 1 second cooldown

        self.thread = DownloadThread(url, download_path, headers, progress)
        self.thread.progress_update.connect(self.update_progress)
        self.thread.download_complete.connect(self.download_finished)
        self.thread.start()

    def update_progress(self, progress, speed, file_name):
        self.progress_bar.setValue(progress)
        self.speed_label.setText(f"Download Speed: {speed:.2f} MB/s")
        self.progress = progress

    def toggle_pause_resume(self):
        if self.thread.paused:
            self.thread.resume()
            self.pause_resume_button.setText("Pause")
        else:
            self.thread.pause()
            self.pause_resume_button.setText("Resume")
        # Disable the button and start the cooldown timer
        self.pause_resume_button.setEnabled(False)
        self.cooldown_timer.start(self.cooldown_duration)

    def enable_pause_resume_button(self):
        self.pause_resume_button.setEnabled(True)
        self.cooldown_timer.stop()

    def download_finished(self, success, file_name):
        if success:
            self.close_and_clear_window()
            QMessageBox.information(self, "Complete", f"Download of {file_name} completed.")
        else:
            self.close_and_clear_window()
            QMessageBox.warning(self, "Error", f"Download of {file_name} failed.")
    def close_and_clear_window(self):
        current_active_windows = show_current_active_windows()
        if self.window() in current_active_windows:
            self.window().close()
            current_active_windows.remove(self.window())
            # current_active_windows.remove(self.window())
    def pause_download(self):
        if self.thread.paused:
            pass
        else:
            self.thread.pause()
            self.pause_resume_button.setText("Resume")

    def resume_download(self):
        if self.thread.paused:
            self.thread.resume()
            self.pause_resume_button.setText("Pause")

        else:
            pass

    def stop_download(self):
        """Safely stop the download process and close the window."""
        if self.thread.isRunning():
            # Somewhere else in your code
            self.thread.pause()
            self.thread.terminate()
            self.thread.wait()
            self.close_and_clear_window()

    def closeEvent(self, event):
        if self.thread.isRunning():
            reply = QMessageBox.question(self, 'Exit',
                                         'Download is still in progress. Are you sure you want to quit?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                # Somewhere else in your code
                inner_active_window = self.window()
                active_windows = show_current_active_windows()
                if inner_active_window in active_windows:
                    active_windows.remove(inner_active_window)
                self.thread.pause()
                self.thread.terminate()
                self.thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
# Global variable to store the reference to the DownloaderApp instance
global_downloader_app = None


class DownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.custom_headers = {}
        self.setWindowTitle("Advanced File Downloader")
        self.setGeometry(100, 100, 900, 700)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.setup_ui()
        self.links_dict = {}
        self.current_theme = "light"
        self.download_path = ""
        self.download_queue = []
        self.active_windows = set()
        self.load_settings()
        self.change_theme(self.current_theme)
        global global_downloader_app
        global_downloader_app = self

    def get_active_windows(self):
        # Ensure self.active_windows exists before returning it
        if not hasattr(self, 'active_windows'):
            self.active_windows = set()
        return self.active_windows

    def get_download_path(self):
        if not hasattr(self, 'download_path'):
            self.download_path = ""
        return self.download_path
    def setup_ui(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # File selection group
        file_group = QGroupBox("File Selection")
        file_layout = QHBoxLayout()
        self.select_files_button = QPushButton("Select Files")
        self.select_files_button.setIcon(QIcon.fromTheme("document-open"))
        self.select_files_button.clicked.connect(self.select_files)
        file_layout.addWidget(self.select_files_button)

        self.select_save_location_button = QPushButton("Select Save Location")
        self.select_save_location_button.setIcon(QIcon.fromTheme("folder"))
        self.select_save_location_button.clicked.connect(self.select_save_location)
        file_layout.addWidget(self.select_save_location_button)

        self.add_link_button = QPushButton("Add Link")
        self.add_link_button.setIcon(QIcon.fromTheme("list-add"))
        self.add_link_button.clicked.connect(self.add_link)
        file_layout.addWidget(self.add_link_button)
        file_group.setLayout(file_layout)
        scroll_layout.addWidget(file_group)

        # List of files
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        scroll_layout.addWidget(self.file_list)

        # Download options group
        options_group = QGroupBox("Download Options")
        options_layout = QHBoxLayout()
        self.concurrent_downloads_label = QLabel("Concurrent Downloads:")
        self.concurrent_downloads_spinner = QSpinBox()
        self.concurrent_downloads_spinner.setRange(1, 10)
        self.concurrent_downloads_spinner.setValue(3)
        options_layout.addWidget(self.concurrent_downloads_label)
        options_layout.addWidget(self.concurrent_downloads_spinner)

        self.custom_headers_button = QPushButton("Custom Headers")
        self.custom_headers_button.setIcon(QIcon.fromTheme("preferences-system-network"))
        self.custom_headers_button.clicked.connect(self.set_custom_headers)
        options_layout.addWidget(self.custom_headers_button)
        options_group.setLayout(options_layout)
        scroll_layout.addWidget(options_group)

        # Download buttons
        download_group = QGroupBox("Download Control")
        download_layout = QHBoxLayout()
        self.download_button = QPushButton("Start Download")
        self.download_button.setIcon(QIcon.fromTheme("go-down"))
        self.download_button.clicked.connect(self.start_download)
        download_layout.addWidget(self.download_button)

        self.pause_all_button = QPushButton("Pause All")
        self.pause_all_button.setIcon(QIcon.fromTheme("media-playback-pause"))
        self.pause_all_button.clicked.connect(self.pause_all_downloads)
        download_layout.addWidget(self.pause_all_button)

        self.resume_all_button = QPushButton("Resume All")
        self.resume_all_button.setIcon(QIcon.fromTheme("media-playback-start"))
        self.resume_all_button.clicked.connect(self.resume_all_downloads)
        download_layout.addWidget(self.resume_all_button)
        self.stop_all_button = QPushButton("Stop All")
        self.stop_all_button.setIcon(QIcon.fromTheme("media-playback-stop"))
        self.stop_all_button.clicked.connect(self.stop_all_downloads)
        download_layout.addWidget(self.stop_all_button)

        download_group.setLayout(download_layout)
        scroll_layout.addWidget(download_group)

        # Theme selection
        theme_group = QGroupBox("Appearance")
        theme_layout = QHBoxLayout()
        self.theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark", "Blue"])
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        theme_layout.addWidget(self.theme_label)
        theme_layout.addWidget(self.theme_combo)
        theme_group.setLayout(theme_layout)
        scroll_layout.addWidget(theme_group)

        # Download progress overview
        self.progress_overview = QListWidget()
        self.progress_overview.setMaximumHeight(150)
        scroll_layout.addWidget(QLabel("Download Progress Overview:"))
        scroll_layout.addWidget(self.progress_overview)

        scroll_area.setWidget(scroll_content)
        self.layout.addWidget(scroll_area)

        # Status bar
        self.statusBar().showMessage("Ready")
        self.update_status_bar()

    def update_status_bar(self):
        active_downloads = len(self.get_active_windows())
        total_files = self.file_list.count()
        status_message = f"Download path: {self.get_download_path() or 'Not set'} | Active downloads: {active_downloads} | Total files: {total_files}"
        self.statusBar().showMessage(status_message)
    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "Text Files (*.txt)")
        if files:
            self.file_list.clear()
            self.links_dict.clear()
            for file in files:
                self.load_links(file)
        self.update_status_bar()


    def load_links(self, file):
        try:
            with open(file, 'r') as f:
                links = [link.strip() for link in f if link.strip()]
                for link in links:
                    self.add_link_to_list(link)
        except IOError as e:
            QMessageBox.critical(self, "File Error", f"Error reading file {file}: {e}")

    def select_save_location(self):
        self.download_path = QFileDialog.getExistingDirectory(self, "Select Download Directory")
        if self.download_path:
            self.update_status_bar()

    def set_custom_headers(self):
        dialog = HeaderDialog(self)
        if dialog.exec():
            self.custom_headers['referer'] = dialog.referer.text() or self.custom_headers.get('referer', '')
            self.custom_headers['user-agent'] = dialog.user_agent.text() or self.custom_headers.get('user-agent', '')
            self.statusBar().showMessage("Custom headers set", 3000)

    def add_link(self):
        link, ok = QInputDialog.getText(self, "Add Link", "Enter download link:")
        if ok and link:
            self.add_link_to_list(link)

    def add_link_to_list(self, link):
        file_name = os.path.basename(urlparse(link).path)
        file_path = os.path.join(self.download_path, file_name)

        item = QListWidgetItem(file_name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

        if os.path.exists(file_path):
            item.setIcon(QIcon.fromTheme("emblem-default"))
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(f"{file_name} already downloaded")
            self.update_progress_overview(file_name, 100)

        else:
            item.setCheckState(Qt.CheckState.Checked)

        self.file_list.addItem(item)
        self.links_dict[file_name] = {"url": link, "progress": 0}

    def start_download(self):
        if not hasattr(self, 'download_queue'):
            self.download_queue = []  # Initialize download queue if not present

        if not self.download_path:
            QMessageBox.warning(self, "No Save Location", "Please select a save location first.")
            return

        selected_items = [self.file_list.item(i) for i in range(self.file_list.count())
                          if self.file_list.item(i).checkState() == Qt.CheckState.Checked]

        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select at least one file.")
            return

        max_concurrent = self.concurrent_downloads_spinner.value()
        active_count = len(self.active_windows)
        if len(selected_items) > max_concurrent:
            QMessageBox.information(self, "Max Concurrent Downloads",
                                    f"Maximum concurrent downloads ({max_concurrent}) reached. Remaining files will be queued.")

        for item in selected_items:
            file_name = item.text()
            url = self.links_dict[file_name]["url"]
            progress = self.links_dict[file_name]["progress"]
            file_path = os.path.join(self.download_path, file_name)

            if os.path.exists(file_path):
                item.setIcon(QIcon.fromTheme("emblem-default"))
                reply = QMessageBox.question(self, 'File Exists',
                                             f"The file '{file_name}' already exists. Do you want to download it again?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                             QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    continue

            if any(win.url == url for win in self.active_windows):
                QMessageBox.warning(self, "Duplicate Download",
                                    f"A download for '{file_name}' is already in progress.")
                continue

            if active_count >= max_concurrent:
                self.download_queue.append((url, file_name, progress))  # Add to queue
            else:
                self.start_download_window(url, file_name, progress)
                active_count += 1

        self.update_status_bar()

    def start_download_window(self, url, file_name, progress):
        """Helper function to start a download."""
        download_window = DownloadWindow(url, self.download_path, self.custom_headers, progress)
        download_window.show()
        self.active_windows.add(download_window)

        download_window.thread.download_complete.connect(lambda: self.on_download_complete(download_window))
        download_window.thread.progress_update.connect(lambda p, s, fn: self.update_progress_overview(fn, p))

    def on_download_complete(self, download_window):
        """Handle logic when a download completes, start queued downloads if any."""
        self.remove_active_window(download_window)

        # Check if there are items in the queue
        if self.download_queue:
            next_url, next_file_name, next_progress = self.download_queue.pop(0)
            self.start_download_window(next_url, next_file_name, next_progress)

        self.update_status_bar()

    def update_progress_overview(self, file_name, progress):
        for i in range(self.progress_overview.count()):
            item = self.progress_overview.item(i)
            if item.text().startswith(file_name):
                item.setText(f"{file_name}: {progress}%")
                return

        self.progress_overview.addItem(f"{file_name}: {progress}%")

    def pause_all_downloads(self):
        if len(self.active_windows) > 0:
            for window in list(self.active_windows):
                window.pause_download()
            QMessageBox.information(self, "Downloads Paused", "All active downloads have been paused.")
        else:
            QMessageBox.warning(self, "No active windows", "Please start at least one download window.")

    def resume_all_downloads(self):
        if len(self.active_windows) > 0:
            for window in list(self.active_windows):
                window.resume_download()
            QMessageBox.information(self, "Downloads Resumed", "All paused downloads have been resumed.")
        else:
            QMessageBox.information(self, "No active windows", "No active windows are being downloaded.")

    def stop_all_downloads(self):
        if len(self.active_windows) > 0:
            windows_to_stop = list(self.active_windows)  # Copy to avoid modifying during iteration
            for inner_window in windows_to_stop:
                inner_window.stop_download()  # This might modify self.active_windows
            QMessageBox.information(self, "Downloads Stopped", "All paused downloads have been stopped.")
        else:
            QMessageBox.information(self, "No active windows", "No files are being downloaded.")

    def remove_active_window(self, window):
        self.active_windows.discard(window)
        self.update_status_bar()

    def change_theme(self, theme):
        if theme == "Light":
            self.setStyleSheet("""
                QWidget { background-color: #f0f0f0; color: #000000; }
                QPushButton { background-color: #e0e0e0; border: 1px solid #b0b0b0; padding: 5px; }
                QPushButton:hover { background-color: #d0d0d0; }
                QListWidget { background-color: #ffffff; border: 1px solid #b0b0b0; }
                QProgressBar { border: 1px solid #b0b0b0; }
                QComboBox, QSpinBox { background-color: #ffffff; border: 1px solid #b0b0b0; }
            """)
        elif theme == "Dark":
            self.setStyleSheet("""
                QWidget { background-color: #2c2c2c; color: #ffffff; }
                QPushButton { background-color: #3c3c3c; border: 1px solid #5c5c5c; padding: 5px; }
                QPushButton:hover { background-color: #4c4c4c; }
                QListWidget { background-color: #3c3c3c; border: 1px solid #5c5c5c; }
                QProgressBar { border: 1px solid #5c5c5c; }
                QComboBox, QSpinBox { background-color: #3c3c3c; border: 1px solid #5c5c5c; color: #ffffff; }
            """)
        elif theme == "Blue":
            self.setStyleSheet("""
                QWidget { background-color: #e6f3ff; color: #000000; }
                QPushButton { background-color: #b3d9ff; border: 1px solid #80bfff; padding: 5px; }
                QPushButton:hover { background-color: #99ccff; }
                QListWidget { background-color: #ffffff; border: 1px solid #80bfff; }
                QProgressBar { border: 1px solid #80bfff; }
                QComboBox, QSpinBox { background-color: #ffffff; border: 1px solid #80bfff; }
            """)
        self.current_theme = theme

    def closeEvent(self, event):
        self.save_settings()
        if self.active_windows:
            reply = QMessageBox.question(self, 'Exit',
                                         'Downloads are still in progress. Are you sure you want to quit?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                for window in self.active_windows:
                    window.close()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def load_settings(self):
        settings = QSettings("AdvancedDownloader", "Settings")
        self.download_path = settings.value("download_path", "")
        self.current_theme = settings.value("theme", "Light")
        self.custom_headers = settings.value("custom_headers", {'referer': 'https://vidtube.pro/'})
        print(self.custom_headers)
        self.concurrent_downloads_spinner.setValue(int(settings.value("concurrent_downloads", 3)))

        saved_links = settings.value("saved_links", {})
        for file_name, data in saved_links.items():
            self.add_link_to_list(data["url"])
            self.links_dict[file_name]["progress"] = data["progress"]
            self.update_progress_overview(file_name, data["progress"])

        self.theme_combo.setCurrentText(self.current_theme)

    def save_settings(self):
        settings = QSettings("AdvancedDownloader", "Settings")
        settings.setValue("download_path", self.download_path)
        settings.setValue("theme", self.current_theme)
        settings.setValue("custom_headers", self.custom_headers)
        print("custom headers: ", self.custom_headers)
        settings.setValue("concurrent_downloads", self.concurrent_downloads_spinner.value())

        saved_links = {file_name: {"url": data["url"], "progress": data["progress"]}
                       for file_name, data in self.links_dict.items()}
        settings.setValue("saved_links", saved_links)

    def update_link_progress(self, file_name, progress):
        if file_name in self.links_dict:
            self.links_dict[file_name]["progress"] = progress
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                if item.text() == file_name:
                    item.setData(Qt.ItemDataRole.UserRole, progress)
                    self.file_list.update()
                    break
def show_current_active_windows():
    if global_downloader_app is not None:
        return global_downloader_app.get_active_windows()
    else:
        return set()  # Return an empty set if the app instance doesn't exis

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DownloaderApp()
    window.show()
    sys.exit(app.exec())