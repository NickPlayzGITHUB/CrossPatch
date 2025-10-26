import os
import ctypes
import threading
import platform
import requests
import subprocess
import sys
import json
import shutil

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QPushButton, QLineEdit, QLabel, QStyle,
    QFrame, QComboBox, QCheckBox, QMenu, QSplitter, QSpacerItem, QSizePolicy, QScrollArea,
    QGridLayout,
    QMessageBox, QFileDialog, QInputDialog
)
from PySide6.QtGui import QIcon, QAction, QFont, QDrag, QPixmap, QPainter, QColor, QDesktopServices, QImage, QDropEvent, QShortcut, QKeySequence
from PySide6.QtCore import Qt, QMimeData, QPoint, Signal, QObject, QUrl, QSize, QThread, QTimer, QRunnable, QThreadPool, QEvent

from Credits import CreditsWindow
from ModUpdatePrompt import ModUpdatePromptWindow
from DownloadManager import DownloadManager
from ConflictDialog import ConflictDialog
from FileSelectDialog import FileSelectDialog
from OneClickInstallDialog import OneClickInstallDialog
from EditMod import EditModWindow
from ProfileManager import ProfileManager
import Config
import Util
from Constants import APP_TITLE, APP_VERSION

class WorkerSignals(QObject):
    """Defines signals available from a running worker thread."""
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)

# --- Worker for background image loading ---
class ImageLoader(QRunnable):
    """Worker thread for loading an image from a URL."""

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = WorkerSignals()

    def run(self):
        """Downloads an image and emits it as a QPixmap."""
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            image = QImage()
            image.loadFromData(response.content)
            self.signals.result.emit(image)
        except Exception as e:
            self.signals.error.emit((e, f"Failed to load image from {self.url}: {e}"))
        finally:
            self.signals.finished.emit()

# --- Worker for fetching full mod details ---
class ModDetailsLoader(QRunnable):
    """Worker thread for fetching the full data for a single mod."""

    def __init__(self, mod_data):
        super().__init__()
        self.mod_data = mod_data
        self.signals = WorkerSignals()

    def run(self):
        """Fetches full mod data and emits it."""
        try:
            url = f"https://gamebanana.com/{self.mod_data.get('_sProfileUrl')}"
            full_mod_data = Util.get_gb_item_data_from_url(url)
            self.signals.result.emit(full_mod_data)
        except Exception as e:
            self.signals.error.emit((e, f"Failed to load details for {self.mod_data.get('_sName')}: {e}"))
        finally:
            self.signals.finished.emit()

# --- Custom Mod Card Widget ---
class ModCard(QFrame):
    def __init__(self, mod_data, download_callback, parent=None):
        super().__init__(parent)
        self.mod_data = mod_data
        self.download_callback = download_callback
        self.worker = None # To hold a reference to the running worker

        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedWidth(220)
        self.setFixedHeight(280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Image Label
        self.image_label = QLabel("Loading...")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(210, 118) # 16:9 aspect ratio
        self.image_label.setStyleSheet("background-color: #2a2a2a; border-radius: 3px;")
        layout.addWidget(self.image_label)

        # Mod Name
        name = self.mod_data.get('_sName', 'N/A')
        name_label = QLabel(name)
        name_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        # Author
        author = self.mod_data.get('_aSubmitter', {}).get('_sName', 'N/A')
        author_label = QLabel(f"by {author}")
        layout.addWidget(author_label)

        layout.addStretch()

        # Stats (Likes/Downloads)
        stats_layout = QHBoxLayout()
        likes = self.mod_data.get('_nLikeCount', 0)
        downloads = self.mod_data.get('_nTotalDownloads', 0)
        stats_layout.addWidget(QLabel(f"👍 {likes}"))
        stats_layout.addWidget(QLabel(f"📥 {downloads}"))
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Download Button
        download_btn = QPushButton(self.style().standardIcon(QStyle.SP_ArrowDown), " Download")
        download_btn.clicked.connect(self.on_download_clicked)
        layout.addWidget(download_btn)

        self._load_image()

    def _update_with_full_data(self, full_mod_data):
        """Updates the card's internal data and then loads the image."""
        self.mod_data = full_mod_data
        self._load_image() # Now try loading the image again with the full data

    def _load_image(self):
        preview_media = self.mod_data.get('_aPreviewMedia', {})
        images = preview_media.get('_aImages', [])
        
        if not images:
            # If image data is missing, it's likely from a minimal API response.
            # Fetch the full details for this mod in the background.
            if '_aPreviewMedia' not in self.mod_data:
                print(f"[DEBUG] Missing preview media for '{self.mod_data.get('_sName')}'. Fetching full details.")
                details_worker = ModDetailsLoader(self.mod_data)
                details_worker.signals.result.connect(self._update_with_full_data)
                QThreadPool.globalInstance().start(details_worker)
                return # Stop here; the callback will re-trigger image loading.
            self.image_label.setText("No Image")
            return

        # Use the 220px wide thumbnail from the API
        image_url = f"{images[0].get('_sBaseUrl')}/{images[0].get('_sFile220')}"

        self.worker = ImageLoader(image_url)
        self.worker.signals.result.connect(self.on_image_loaded)
        self.worker.signals.error.connect(self.on_image_load_failed)
        # Use the global thread pool for efficiency
        QThreadPool.globalInstance().start(self.worker)

    def on_image_loaded(self, image):
        if not image.isNull():
            # Convert the thread-safe QImage to a QPixmap in the main thread
            pixmap = QPixmap.fromImage(image)
            self.image_label.setPixmap(pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
        else:
            self.image_label.setText("Load Failed")

    def on_image_load_failed(self, error_info):
        e, msg = error_info
        print(msg)
        self.image_label.setText("Load Failed")

    def on_download_clicked(self):
        # Pass the full mod_data to avoid a second API call
        self.download_callback(item_data=self.mod_data)

    def stop(self):
        """Safely stops any running background tasks."""
        # Disconnect signals to prevent the worker from calling slots on this widget
        # after it has been scheduled for deletion.
        if self.worker:
            try:
                self.worker.signals.result.disconnect(self.on_image_loaded)
                self.worker.signals.error.disconnect(self.on_image_load_failed)
            except (RuntimeError, TypeError):
                # This can happen if the signal is already disconnected or the worker finished.
                pass

class ModTreeWidget(QTreeWidget):
    """A custom QTreeWidget that forces all drops to be insertions, not parenting."""
    def dropEvent(self, event: QDropEvent):
        if not self.selectedItems():
            return

        # Get the item being dragged
        dragged_item = self.selectedItems()[0]
        # Get the item at the drop position
        target_item = self.itemAt(event.position().toPoint())

        if target_item:
            # Calculate the index to insert at (above the target)
            drop_index = self.indexOfTopLevelItem(target_item)
            # Take the dragged item out of the tree
            taken_item = self.takeTopLevelItem(self.indexOfTopLevelItem(dragged_item))
            # Insert it at the new position
            self.insertTopLevelItem(drop_index, taken_item)
            # Ensure the newly moved item is selected
            self.setCurrentItem(taken_item)

class CrossPatchWindow(QMainWindow):
    # Signal to handle protocol URL from a non-GUI thread
    protocol_url_received = Signal(str)
    # Signal to safely update UI after background mod update check
    mod_update_check_finished = Signal(dict, bool)

    def __init__(self, instance_socket=None):
        super().__init__()
        self.instance_socket = instance_socket

        # --- Core App Data ---
        self.cfg = Config.config
        self.profile_manager = ProfileManager(self.cfg)
        self.updatable_mods = {}
        self.active_download_manager = None # To hold a reference
        self._resize_timer = None
        self.assets_path = Util.find_assets_dir()

        # --- Drag & Drop Data ---
        self._drag_start_pos = None

        # --- Window Setup ---
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon(os.path.join(self.assets_path, 'CrossP.ico')))
        
        # Restore window size and position
        geometry = self.cfg.get("window_geometry")
        if geometry:
            self.restoreGeometry(bytes.fromhex(geometry))
        else:
            self.resize(620, 750)
            Util.center_window_pyside(self)

        # --- Main Widget and Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Tabbed Interface ---
        self.notebook = QTabWidget()
        main_layout.addWidget(self.notebook)

        self.mods_tab_frame = QWidget()
        self.browse_tab_frame = QWidget()
        self.settings_tab_frame = QWidget()

        self.notebook.addTab(self.mods_tab_frame, "Installed Mods")
        self.notebook.addTab(self.browse_tab_frame, "Browse Mods")
        self.notebook.addTab(self.settings_tab_frame, "Settings")

        # --- Build UI for each tab ---
        self._create_mods_tab_ui()
        self._create_browse_tab_ui()
        self._create_settings_tab_ui()

        # --- Bottom Buttons and Status Bar ---
        self._create_bottom_bar()

        # --- Hotkeys ---
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        # Only activate shortcut if the mods tab is visible
        search_shortcut.activated.connect(self.on_search_hotkey)

        # Connect signals after all relevant widgets have been created
        self.notebook.currentChanged.connect(self.on_tab_change)

        # --- Final Setup ---
        self.protocol_url_received.connect(self.handle_protocol_url)
        self.mod_update_check_finished.connect(self.on_mod_update_check_finished)
        if self.instance_socket:
            threading.Thread(target=self._socket_listener, daemon=True).start()

        # On startup, just populate the list from saved data without a full refresh.
        self._update_treeview()
        threading.Thread(target=lambda: self.check_all_mod_updates(), daemon=True).start()
        self.set_dark_title_bar()

    def _create_mods_tab_ui(self):
        mods_layout = QVBoxLayout(self.mods_tab_frame)

        # Search bar (hidden by default)
        self.search_frame = QFrame()
        search_layout = QHBoxLayout(self.search_frame)
        search_layout.setContentsMargins(0,0,0,0)
        search_layout.addWidget(QLabel("Search:"))
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Filter by name, author, etc.")
        self.search_entry.textChanged.connect(self._update_treeview)
        search_layout.addWidget(self.search_entry)
        mods_layout.addWidget(self.search_frame)
        self.search_frame.hide()

        # Mods List (Treeview)
        self.tree = ModTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(["", "", "Mod Name", "Version", "Author", "Type"])
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.setDragDropMode(QTreeWidget.InternalMove)
        self.tree.setDragEnabled(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setAllColumnsShowFocus(True)

        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Update Icon
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Enabled Checkbox
        header.setSectionResizeMode(2, QHeaderView.Stretch)          # Name
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Version
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents) # Author
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Type
        self.tree.setColumnHidden(0, True) # Hide update column by default

        # Set up drag and drop reordering
        self.tree.model().rowsMoved.connect(self.on_drag_end)
        self.tree.viewport().setAcceptDrops(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_right_click)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.itemChanged.connect(self.on_item_changed)
        self.tree.mousePressEvent = self._tree_mouse_press_event

        mods_layout.addWidget(self.tree)

    def _create_browse_tab_ui(self):
        browse_layout = QVBoxLayout(self.browse_tab_frame)

        # --- Filters and Search ---
        filter_bar = QHBoxLayout()
        
        filter_bar.addWidget(QLabel("Filter:"))
        self.browse_filter_combo = QComboBox()
        self.browse_filter_combo.addItems(["Top", "Featured", "Community Spotlight", "Newest", "Most Liked"])
        # Use a lambda to ensure fetch_browse_mods is called with page=1 when the filter changes.
        # The default signal would pass the combobox index (starting at 0) as the page number.
        self.browse_filter_combo.currentIndexChanged.connect(lambda: self.fetch_browse_mods(page=1))
        filter_bar.addWidget(self.browse_filter_combo)

        filter_bar.addWidget(QLabel("Section:"))
        self.browse_section_combo = QComboBox()
        self.sections = {
            "All Sections": None,
            "Skins": 39130,
            "HUD/GUI": 39825,
            "Others/Misc": 39830,
            "Animations": 40088,
            "Items": 39839,
            "Maps/Crossworlds": 39978,
            "Translations": 39844
        }
        self.browse_section_combo.addItems(self.sections.keys())
        self.browse_section_combo.currentIndexChanged.connect(lambda: self.fetch_browse_mods(page=1))
        filter_bar.addWidget(self.browse_section_combo)

        filter_bar.addStretch()

        filter_bar.addWidget(QLabel("Search:"))
        self.browse_search_entry = QLineEdit()
        self.browse_search_entry.setPlaceholderText("Search GameBanana...")
        self.browse_search_entry.returnPressed.connect(lambda: self.fetch_browse_mods(page=1))
        filter_bar.addWidget(self.browse_search_entry)

        self.browse_clear_search_btn = QPushButton("Clear")
        self.browse_clear_search_btn.clicked.connect(self.clear_browse_search)
        self.browse_clear_search_btn.setVisible(False)
        self.browse_search_entry.textChanged.connect(lambda text: self.browse_clear_search_btn.setVisible(bool(text)))
        filter_bar.addWidget(self.browse_clear_search_btn)

        browse_layout.addLayout(filter_bar)

        # --- Mod Browser Card Layout ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.card_container = QWidget()
        self.card_layout = QGridLayout(self.card_container)
        self.card_layout.setSpacing(10)
        self.card_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll_area.setWidget(self.card_container)
        browse_layout.addWidget(self.scroll_area)

        # --- Pagination and Download ---
        page_bar = QHBoxLayout()
        self.browse_prev_btn = QPushButton("<< Previous")
        self.browse_prev_btn.clicked.connect(self.browse_prev_page)
        self.browse_prev_btn.setEnabled(False)
        page_bar.addWidget(self.browse_prev_btn)

        self.browse_page_label = QLabel("Page 1")
        self.browse_page_label.setAlignment(Qt.AlignCenter)
        page_bar.addWidget(self.browse_page_label)

        self.browse_next_btn = QPushButton("Next >>")
        self.browse_next_btn.clicked.connect(self.browse_next_page)
        page_bar.addWidget(self.browse_next_btn)

        page_bar.addStretch()

        browse_layout.addLayout(page_bar)

        # --- Data for browsing ---
        self.browse_current_page = 1
        self.browse_mods_data = []
        # Fetch initial data when the tab is first shown
        self.notebook.currentChanged.connect(self._on_browse_tab_selected)


    def _create_settings_tab_ui(self):
        settings_layout = QVBoxLayout(self.settings_tab_frame)
        settings_layout.setAlignment(Qt.AlignTop)

        # --- Profile Management ---
        profile_frame = QFrame()
        profile_frame.setFrameShape(QFrame.StyledPanel)
        profile_layout = QHBoxLayout(profile_frame)
        profile_layout.addWidget(QLabel("<b>Profile:</b>"))

        self.profile_selector = QComboBox()
        self.profile_selector.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.profile_selector.activated.connect(self.on_profile_change)
        profile_layout.addWidget(self.profile_selector)

        add_profile_btn = QPushButton(self.style().standardIcon(QStyle.SP_FileDialogNewFolder), "")
        add_profile_btn.setToolTip("Add new profile")
        add_profile_btn.clicked.connect(self.add_profile)
        profile_layout.addWidget(add_profile_btn)

        rename_profile_btn = QPushButton(self.style().standardIcon(QStyle.SP_FileLinkIcon), "")
        rename_profile_btn.setToolTip("Rename current profile")
        rename_profile_btn.clicked.connect(self.rename_profile)
        profile_layout.addWidget(rename_profile_btn)

        delete_profile_btn = QPushButton(self.style().standardIcon(QStyle.SP_TrashIcon), "")
        delete_profile_btn.setToolTip("Delete current profile")
        delete_profile_btn.clicked.connect(self.delete_profile)
        profile_layout.addWidget(delete_profile_btn)

        settings_layout.addWidget(profile_frame)
        self.update_profile_selector()

        # --- Paths Settings ---
        paths_frame = QFrame()
        paths_frame.setFrameShape(QFrame.StyledPanel)
        paths_layout = QVBoxLayout(paths_frame)

        # Game Directory
        game_root_layout = QHBoxLayout()
        game_root_layout.addWidget(QLabel("Game Directory:"))
        self.game_root_var = QLineEdit(self.cfg["game_root"])
        self.game_root_var.setReadOnly(True)
        game_root_layout.addWidget(self.game_root_var)
        game_root_btn = QPushButton("...")
        game_root_btn.clicked.connect(self.on_change_game_root)
        game_root_layout.addWidget(game_root_btn)
        paths_layout.addLayout(game_root_layout)

        # Mods Folder
        mods_folder_layout = QHBoxLayout()
        mods_folder_layout.addWidget(QLabel("Mods Folder:"))
        self.mods_folder_var = QLineEdit(self.cfg["mods_folder"])
        self.mods_folder_var.setReadOnly(True)
        mods_folder_layout.addWidget(self.mods_folder_var)
        mods_folder_btn = QPushButton("...")
        mods_folder_btn.clicked.connect(self.on_change_mods_folder)
        mods_folder_layout.addWidget(mods_folder_btn)
        paths_layout.addLayout(mods_folder_layout)

        settings_layout.addWidget(paths_frame)

        # --- Other Settings ---
        other_frame = QFrame()
        other_frame.setFrameShape(QFrame.StyledPanel)
        other_layout = QVBoxLayout(other_frame)

        self.show_logs_var = QCheckBox("Show console logs")
        self.show_logs_var.setChecked(self.cfg.get("show_cmd_logs", False))
        self.show_logs_var.toggled.connect(self.on_toggle_logs)
        if platform.system() == "Windows":
            other_layout.addWidget(self.show_logs_var)

        settings_layout.addWidget(other_frame)

        # --- Action Buttons ---
        action_frame = QFrame()
        action_frame.setFrameShape(QFrame.StyledPanel)
        action_layout = QHBoxLayout(action_frame)
        action_layout.addStretch()
        credits_btn = QPushButton("Credits")
        credits_btn.clicked.connect(self.open_credits)
        action_layout.addWidget(credits_btn)
        action_layout.addStretch()
        settings_layout.addWidget(action_frame)

    def _create_bottom_bar(self):
        # --- Main Action Buttons (Refresh, Save, Add) ---
        self.bottom_button_frame = QWidget()
        bottom_button_layout = QHBoxLayout(self.bottom_button_frame)
        bottom_button_layout.setContentsMargins(0, 5, 0, 5)

        self.refresh_btn = QPushButton(self.style().standardIcon(QStyle.SP_BrowserReload), " Refresh")
        self.refresh_btn.setToolTip("Apply changes and refresh list")
        self.refresh_btn.clicked.connect(self.refresh)
        bottom_button_layout.addWidget(self.refresh_btn)

        self.save_btn = QPushButton(self.style().standardIcon(QStyle.SP_DialogSaveButton), " Save")
        self.save_btn.setToolTip("Save changes (mod order and enabled status)")
        self.save_btn.clicked.connect(self.save_and_refresh)
        bottom_button_layout.addWidget(self.save_btn)

        self.add_mod_btn = QPushButton(QIcon(os.path.join(self.assets_path, 'gb_icon.png')), " Add Mod from URL")
        # Use a lambda to ensure no arguments are passed when the button is clicked.
        self.add_mod_btn.clicked.connect(lambda: self.add_mod_from_url())
        bottom_button_layout.addWidget(self.add_mod_btn)

        bottom_button_layout.addStretch()

        self.search_btn = QPushButton(QIcon(os.path.join(self.assets_path, 'search.png')), "")
        self.search_btn.setToolTip("Search mods (Ctrl+F)")
        self.search_btn.setCheckable(True)
        self.search_btn.toggled.connect(self.toggle_search_bar)
        bottom_button_layout.addWidget(self.search_btn)

        self.centralWidget().layout().addWidget(self.bottom_button_frame)

        # --- Launch Button ---
        launch_btn = QPushButton("Launch Game")
        launch_btn.setToolTip("Apply changes and launch the game")
        launch_btn.clicked.connect(self.save_and_launch)
        font = launch_btn.font()
        font.setPointSize(12)
        launch_btn.setFont(font)
        self.centralWidget().layout().addWidget(launch_btn)

        # --- Status Bar ---
        self.statusBar().showMessage(f"CrossPatch {APP_VERSION}")

    def event(self, event):
        """Handles custom events posted to the main window."""
        if event.type() == Util.ModListFetchEvent.EVENT_TYPE:
            self._update_browse_cards(event.mods_data)
            return True
        return super().event(event)

    def resizeEvent(self, event):
        """Handle window resize to reflow mod cards with a debounce timer."""
        super().resizeEvent(event)
        if self._resize_timer:
            self._resize_timer.stop()
        
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._reflow_browse_cards)
        self._resize_timer.start(100) # 100ms delay
    # --- Event Handlers & Logic (High-Level) ---

    def closeEvent(self, event):
        """Saves window size and closes the application."""
        print("Saving configuration before exiting...")
        self.refresh()
        self.cfg["window_geometry"] = self.saveGeometry().toHex().data().decode()
        self.profile_manager.save()
        if self.instance_socket:
            self.instance_socket.close()
        event.accept()

    def on_tab_change(self, index):
        """Shows or hides mod-related buttons based on the selected tab."""
        tab_text = self.notebook.tabText(index)
        is_mods_tab = (tab_text == "Installed Mods")
        
        self.refresh_btn.setVisible(is_mods_tab)
        self.save_btn.setVisible(is_mods_tab)
        self.add_mod_btn.setVisible(is_mods_tab)
        self.search_btn.setVisible(is_mods_tab)

        if not is_mods_tab and self.search_frame.isVisible():
            self.search_btn.setChecked(False) # This will hide the search bar

    def toggle_search_bar(self, checked):
        self.search_frame.setVisible(checked)
        if checked:
            self.search_entry.setFocus()
        else:
            self.search_entry.clear()
            self.tree.setFocus()

    def on_search_hotkey(self):
        """Toggles the search bar only if the 'Installed Mods' tab is active."""
        if self.notebook.tabText(self.notebook.currentIndex()) == "Installed Mods":
            self.search_btn.toggle()

    def on_drag_end(self, parent, start, end, destination, row):
        """Finalizes the drag operation, saving the new order."""
        # The move is already visually done by QTreeWidget. We just need to save it.
        new_priority = [self.tree.topLevelItem(i).data(0, Qt.UserRole) for i in range(self.tree.topLevelItemCount())]
        if self.profile_manager.get_active_profile().get("mod_priority") != new_priority:
            self.profile_manager.set_mod_priority(new_priority)
            print("New mod order saved.")

    def on_item_clicked(self, item, column):
        """Handle clicks on specific columns, like the checkbox."""
        mod_folder_name = item.data(0, Qt.UserRole)
        if not mod_folder_name:
            return

        if column == 0: # 'Update' column
            self.on_update_column_click(mod_folder_name)

    def on_item_changed(self, item, column):
        """Handles changes to an item, specifically the checkbox state."""
        if column == 1: # 'Enabled' column
            mod_folder_name = item.data(0, Qt.UserRole)
            is_enabled = item.checkState(1) == Qt.Checked
            self.profile_manager.set_mod_enabled(mod_folder_name, is_enabled)

    def on_right_click(self, pos):
        """Handles right-clicks on the treeview to show the context menu."""
        item = self.tree.itemAt(pos)
        if not item:
            return

        # Set the item under the cursor as the current item
        self.tree.setCurrentItem(item)

        mod_folder_name = item.data(0, Qt.UserRole)

        menu = QMenu()
        menu.addAction("Open containing folder", self.open_selected_mod_folder)
        menu.addAction("Edit mod info", self.edit_selected_mod_info)
        menu.addSeparator()

        # Only show update option if mod has a page URL
        mod_info = Util.read_mod_info(os.path.join(self.cfg["mods_folder"], mod_folder_name))
        if mod_info.get("mod_page", "").startswith("https://gamebanana.com"):
            menu.addAction("Check for updates", self.check_mod_updates)

        menu.addSeparator()
        menu.addAction(self.style().standardIcon(QStyle.SP_TrashIcon), "Delete mod", self.delete_mod)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # --- Core Application Logic (Ported from Tkinter version) ---

    def refresh(self):
        all_mods = Util.list_mod_folders(self.cfg["mods_folder"])
        
        # Get the current visual order from the tree as the source of truth
        current_priority = [self.tree.topLevelItem(i).data(0, Qt.UserRole) for i in range(self.tree.topLevelItemCount())]
        
        # Synchronize with disk (add new mods, remove deleted ones)
        new_priority_list = Util.synchronize_priority_with_disk(current_priority, all_mods)
        self.profile_manager.set_mod_priority(new_priority_list)

        Util.clean_mods_folder(self.cfg)
        enabled_mods = self.profile_manager.get_active_profile().get("enabled_mods", {})
        Util.enable_mods_from_priority(new_priority_list, enabled_mods, self.cfg, self, self.profile_manager.get_active_profile())

        threading.Thread(target=lambda: self.check_all_mod_updates(), daemon=True).start()

        # A manual refresh should clear the selection for a clean state.
        self._update_treeview(preserve_selection=False)
        print("Saved and refreshed.")

        conflicts = self.detect_mod_conflicts()
        if conflicts:
            dialog = ConflictDialog(self, conflicts)
            dialog.exec()
    def _tree_mouse_press_event(self, event):
        """Clears selection when clicking on an empty area of the tree."""
        item = self.tree.itemAt(event.pos())
        if not item:
            self.tree.clearSelection()
        # Call the original event handler to maintain default behavior (like dragging)
        QTreeWidget.mousePressEvent(self.tree, event)

    def _update_treeview(self, preserve_selection=True):
        # --- Preserve Selection ---
        selected_mod_folder = None
        if preserve_selection:
            current_item = self.tree.currentItem()
            if current_item:
                selected_mod_folder = current_item.data(0, Qt.UserRole)

        search_text = self.search_entry.text().lower()
        active_profile = self.profile_manager.get_active_profile()
        enabled_mods = active_profile.get("enabled_mods", {})
        updatable_mod_names = {v['name'] for v in self.updatable_mods.values()}

        self.tree.setColumnHidden(0, not self.updatable_mods)
        
        self.tree.clear()
        for i, mod_folder_name in enumerate(active_profile.get("mod_priority", [])):
            info = Util.read_mod_info(os.path.join(self.cfg["mods_folder"], mod_folder_name))
            name = info.get("name", mod_folder_name)
            version = info.get("version", "1.0")
            author = info.get("author", "Unknown")
            mod_type = info.get("mod_type", "pak").upper()

            if search_text and not any(search_text in s.lower() for s in [name, version, author, mod_type]):
                continue

            is_enabled = enabled_mods.get(mod_folder_name, False)

            item = QTreeWidgetItem(["", "", name, version, author, mod_type])
            item.setData(0, Qt.UserRole, mod_folder_name) # Store folder name in item

            # Enabled Checkbox
            item.setCheckState(1, Qt.Checked if is_enabled else Qt.Unchecked)

            # Update Icon
            if name in updatable_mod_names:
                item.setText(0, "⬆️")
                font = item.font(2)
                font.setBold(True)
                item.setFont(2, font)
                item.setForeground(2, QColor("springgreen"))

            self.tree.addTopLevelItem(item)

            # --- Restore Selection ---
            if mod_folder_name == selected_mod_folder:
                self.tree.setCurrentItem(item)

        print("Treeview updated")

    def save_and_refresh(self):
        self.refresh()

    def save_and_launch(self):
        self.refresh()
        Util.launch_game()
    
    def add_mod_from_url(self, item_data=None):
        if not item_data:
            url, ok = QInputDialog.getText(self, "Add Mod from URL", "Enter the GameBanana Mod URL:")
            if not ok or not url:
                return
        else:
            # If item_data is from the browser, it might be incomplete.
            # We need to re-fetch it using the URL to guarantee we have the file list.
            url = f"https://gamebanana.com/{item_data.get('_sProfileUrl')}"

        if "gamebanana.com" not in url:
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid GameBanana mod URL.")
            return
        try:
            # Always fetch the full data to ensure _aFiles is present.
            item_data = Util.get_gb_item_data_from_url(url)
        except Exception as e:
            QMessageBox.critical(self, "Download Error", f"Could not get mod details.\n\n{e}")
            return

        try:
            mod_name = item_data.get('_sName', 'Unknown Mod')

            if not item_data.get('_aFiles'):
                QMessageBox.critical(self, "No Files Found", "Could not find any downloadable files for this mod.")
                return

            dialog = FileSelectDialog(self, item_data)
            if dialog.exec():
                self.start_download_from_selection(dialog.get_selection(), mod_name)
        except Exception as e:
            QMessageBox.critical(self, "Download Error", f"Could not start download.\n\n{e}")

    def start_download_from_selection(self, selected_file, mod_name):
        """Starts the download after the FileSelectDialog has closed."""
        if selected_file:
            self.active_download_manager = DownloadManager(self, self.cfg["mods_folder"], on_complete=self.refresh)
            self.active_download_manager.download_specific_file(selected_file, mod_name)

    def edit_selected_mod_info(self):
        selected = self.tree.currentItem()
        if not selected:
            return

        folder_name = selected.data(0, Qt.UserRole)
        display_name = selected.text(2)
        mod_folder = os.path.join(self.cfg["mods_folder"], folder_name)
        data = Util.read_mod_info(mod_folder) or {}

        dialog = EditModWindow(self, display_name, data)
        if dialog.exec():
            new_data = dialog.get_data()
            original_mod_type = dialog.original_mod_type
            try:
                with open(os.path.join(mod_folder, "info.json"), "w", encoding="utf-8") as f:
                    json.dump(new_data, f, indent=2)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Could not save info.json:\n{e}")
                return

            active_profile = self.profile_manager.get_active_profile()
            is_enabled = active_profile.get("enabled_mods", {}).get(folder_name, False)
            new_mod_type = new_data["mod_type"]

            if is_enabled and new_mod_type != original_mod_type:
                Util.remove_mod_from_game_folders(folder_name, self.cfg)
                self.refresh()
            else:
                selected.setText(2, new_data["name"])
                selected.setText(3, new_data["version"])
                selected.setText(4, new_data["author"])
                selected.setText(5, new_mod_type.upper())
        else:
            print("Edit mod info cancelled.")

    def on_update_column_click(self, mod_folder_name):
        mod_update_info = next((v for k, v in self.updatable_mods.items() if k == mod_folder_name), None)
        if mod_update_info:
            url = mod_update_info['url']
            print(f"Starting update for '{mod_folder_name}' from action column click.")
            self.update_mod_from_url(url, mod_folder_name)

    def update_mod_from_url(self, url, mod_folder_name):
        print(f"Starting update for '{mod_folder_name}' from URL: {url}")
        try:
            item_data = Util.get_gb_item_data_from_url(url)
            mod_name_from_gb = item_data.get('_sName', 'Unknown Mod')

            if not item_data.get('_aFiles'):
                QMessageBox.critical(self, "No Files Found", "Could not find any downloadable files for this mod.")
                return

            dialog = FileSelectDialog(self, item_data)
            if dialog.exec():
                selected_file = dialog.get_selection()
                if selected_file:
                    self.active_download_manager = DownloadManager(self, self.cfg["mods_folder"], on_complete=self.refresh)
                    active_profile = self.profile_manager.get_active_profile()
                    self.active_download_manager.update_specific_file(selected_file, mod_name_from_gb, mod_folder_name, active_profile)
            else:
                threading.Thread(target=lambda: self.check_all_mod_updates(), daemon=True).start()
                print("User cancelled file selection for update.")

        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Could not get mod details or start update.\n\n{e}")

    def check_all_mod_updates(self, manual_check=False):
        print("Checking all mods for updates...")
        updates = {}
        mod_folders = Util.list_mod_folders(self.cfg["mods_folder"])

        for mod_folder_name in mod_folders:
            mod_info = Util.read_mod_info(os.path.join(self.cfg["mods_folder"], mod_folder_name))
            mod_name = mod_info.get("name", mod_folder_name)
            mod_version = mod_info.get("version", "1.0")
            mod_page = mod_info.get("mod_page")

            if not mod_page or not mod_page.startswith("https://gamebanana.com"):
                continue

            try:
                gb_version = Util.get_gb_mod_version(mod_page)
                if not gb_version:
                    continue
                if Util.is_newer_version(mod_version, gb_version):
                    updates[mod_folder_name] = {
                        'name': mod_name,
                        'current': mod_version,
                        'new': gb_version,
                        'url': mod_page,
                        'folder_name': mod_folder_name
                    }
                    print(f"Update found for {mod_name}: {mod_version} -> {gb_version}")
            except Exception as e:
                print(f"Error checking {mod_name}: {str(e)}")

        # Emit signal to update UI on the main thread
        self.mod_update_check_finished.emit(updates, manual_check)

    def on_mod_update_check_finished(self, updates, manual_check):
        """Slot to handle the results of the background mod update check."""
        self.updatable_mods = updates
        self._update_treeview(preserve_selection=True)

        if manual_check:
            if updates:
                QMessageBox.information(self, "Updates Found", f"{len(updates)} mod(s) have updates available and are now highlighted.")
            else:
                QMessageBox.information(self, "Update Check", "No mod updates available.")
        print("Mod update check finished and UI updated.")

    def check_mod_updates(self):
        selected = self.tree.currentItem()
        if not selected: return

        mod_folder = selected.data(0, Qt.UserRole)
        display_name = selected.text(2)
        mod_info = Util.read_mod_info(os.path.join(self.cfg["mods_folder"], mod_folder))

        mod_page = mod_info.get("mod_page")
        if not mod_page or not mod_page.startswith("https://gamebanana.com"):
            QMessageBox.information(self, "Update Check", "This mod does not have a GameBanana page set in its info.json.")
            return

        try:
            gb_version = Util.get_gb_mod_version(mod_page)
            if not gb_version:
                QMessageBox.warning(self, "Update Check", "Could not find version information for this mod on GameBanana.")
                return

            local_version = mod_info.get("version", "1.0")

            if Util.is_newer_version(local_version, gb_version):
                dialog = ModUpdatePromptWindow(self, display_name, local_version, gb_version)
                if dialog.exec():
                    self.update_mod_from_url(mod_page, mod_folder)
            else:
                QMessageBox.information(self, "No Updates Found", f"'{display_name}' is already up to date (v{local_version}).")

        except Exception as e:
            QMessageBox.critical(self, "Update Check Error", f"Failed to check for updates: {str(e)}")

    def delete_mod(self):
        selected = self.tree.currentItem()
        if not selected: return

        mod_id = selected.data(0, Qt.UserRole)
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete '{selected.text(2)}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            print(f"Deleting mod {mod_id}")
            Util.remove_mod_from_game_folders(mod_id, self.cfg)
            shutil.rmtree(os.path.join(self.cfg["mods_folder"], mod_id))
            self.refresh()

    def open_selected_mod_folder(self):
        selected = self.tree.currentItem()
        if not selected: return

        folder = os.path.join(self.cfg["mods_folder"], selected.data(0, Qt.UserRole))
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def detect_mod_conflicts(self):
        mods_folder = self.cfg["mods_folder"]
        active_profile = self.profile_manager.get_active_profile()
        enabled_mods_dict = active_profile.get("enabled_mods", {})
        enabled_mods = [mod for mod in active_profile.get("mod_priority", []) if enabled_mods_dict.get(mod, False)]
        file_map = {}
        conflicts = {}
        conflict_blacklist = {"info.json", "config.ini", "readme.txt", "readme.md", "changelog.txt"}

        for mod in enabled_mods:
            mod_path = os.path.join(mods_folder, mod)
            mod_info = Util.read_mod_info(mod_path)
            if mod_info.get("mod_type", "pak").startswith("ue4ss"):
                continue

            for root, _, files in os.walk(mod_path):
                for f in files:
                    if f.lower() in conflict_blacklist:
                        continue
                    rel_path = os.path.relpath(os.path.join(root, f), mod_path)
                    if rel_path not in file_map:
                        file_map[rel_path] = [mod]
                    else:
                        file_map[rel_path].append(mod)
        for rel_path, mods in file_map.items():
            if len(mods) > 1:
                conflicts[rel_path] = mods
        return conflicts

    def handle_protocol_url(self, url):
        print(f"Received URL from protocol: {url}")
        self.activateWindow() # Bring window to front
        self.raise_()

        try:
            if url.startswith("crosspatch:") and "," in url:
                parts_str = url.replace("crosspatch:", "")
                parts = parts_str.split(',')
                download_url, item_type, item_id = parts[0], parts[1], parts[2]
                file_ext = parts[3] if len(parts) > 3 else 'zip'
                gb_page_url = f"https://gamebanana.com/{item_type.lower()}s/{item_id}"
                item_data = Util.get_gb_item_data_from_url(gb_page_url)

                dialog = OneClickInstallDialog(self, item_data)
                if dialog.exec():
                    self.active_download_manager = DownloadManager(self, self.cfg["mods_folder"], on_complete=self.refresh)
                    self.active_download_manager.download_from_schema(download_url, item_type, item_id, file_ext, page_url=gb_page_url)

            elif url.startswith("crosspatch://install?url="):
                gb_url = url.replace("crosspatch://install?url=", "")
                item_data = Util.get_gb_item_data_from_url(gb_url)
                dialog = OneClickInstallDialog(self, item_data)
                if dialog.exec():
                    self.active_download_manager = DownloadManager(self, self.cfg["mods_folder"], on_complete=self.refresh)
                    self.active_download_manager.download_from_schema(gb_url) # Should be schema download
        except Exception as e:
            QMessageBox.critical(self, "Download Error", f"Could not parse the received URL.\n\nDetails: {e}")

    def _socket_listener(self):
        self.instance_socket.listen(1)
        while True:
            try:
                conn, addr = self.instance_socket.accept()
                with conn:
                    data = conn.recv(1024)
                    if data:
                        url = data.decode('utf-8')
                        self.protocol_url_received.emit(url)
            except Exception as e:
                print(f"Socket listener error: {e}")
                break

    def set_dark_title_bar(self):
        if platform.system() == "Windows":
            try:
                hwnd = self.winId()
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value), ctypes.sizeof(value)
                )
            except Exception as e:
                print(f"Could not set dark title bar: {e}")

    # --- Settings Tab Methods ---

    def open_credits(self):
        dialog = CreditsWindow(self)
        dialog.exec()

    def on_toggle_logs(self, enabled):
        self.cfg["show_cmd_logs"] = enabled
        Config.save_config(self.cfg)
        if enabled:
            Config.show_console()
        else:
            Config.hide_console()

    def on_change_mods_folder(self):
        new_folder = QFileDialog.getExistingDirectory(self, "Select a folder to store your mods", self.cfg["mods_folder"])
        if new_folder:
            self.mods_folder_var.setText(new_folder)
            self.cfg["mods_folder"] = new_folder
            Config.save_config(self.cfg)
            self.refresh()

    def on_change_game_root(self):
        new_root = QFileDialog.getExistingDirectory(self, "Select Crossworlds Install Folder", self.cfg["game_root"])
        if new_root:
            self.game_root_var.setText(new_root)
            self.cfg["game_root"] = new_root
            self.cfg["game_mods_folder"] = os.path.join(new_root, "UNION", "Content", "Paks", "~mods")
            Config.save_config(self.cfg)
            print("Updated root folder")

    # --- Profile Management Methods ---

    def update_profile_selector(self):
        profiles = self.profile_manager.get_profile_names()
        active_profile = self.profile_manager.get_active_profile_name()
        self.profile_selector.clear()
        self.profile_selector.addItems(profiles)
        self.profile_selector.setCurrentText(active_profile)

    def on_profile_change(self):
        new_profile = self.profile_selector.currentText()
        if self.profile_manager.set_active_profile(new_profile):
            self.refresh()

    def add_profile(self):
        new_name, ok = QInputDialog.getText(self, "New Profile", "Enter a name for the new profile:")
        if ok and new_name:
            if self.profile_manager.create_profile(new_name):
                self.update_profile_selector()
                self.refresh()
            else:
                QMessageBox.critical(self, "Error", "A profile with this name already exists or the name is invalid.")

    def rename_profile(self):
        old_name = self.profile_manager.get_active_profile_name()
        if old_name == self.profile_manager.DEFAULT_PROFILE_NAME:
            QMessageBox.critical(self, "Error", "The 'Default' profile cannot be renamed.")
            return

        new_name, ok = QInputDialog.getText(self, "Rename Profile", f"Enter a new name for '{old_name}':", text=old_name)
        if ok and new_name and new_name != old_name:
            if self.profile_manager.rename_profile(old_name, new_name):
                self.update_profile_selector()
            else:
                QMessageBox.critical(self, "Error", "A profile with this name already exists or the name is invalid.")

    def delete_profile(self):
        profile_to_delete = self.profile_manager.get_active_profile_name()

        if profile_to_delete == self.profile_manager.DEFAULT_PROFILE_NAME:
            QMessageBox.critical(self, "Error", "The 'Default' profile cannot be deleted.")
            return
        if len(self.profile_manager.get_profile_names()) <= 1:
            QMessageBox.critical(self, "Error", "You cannot delete the last profile.")
            return

        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete the active profile '{profile_to_delete}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            if self.profile_manager.delete_profile(profile_to_delete):
                self.update_profile_selector()
                self.refresh()

    # --- Browse Mods Tab Methods ---

    def _on_browse_tab_selected(self, index):
        """Fetch initial mod data only when the 'Browse Mods' tab is selected for the first time."""
        if self.notebook.tabText(index) == "Browse Mods" and not self.browse_mods_data:
            self.fetch_browse_mods()

    def fetch_browse_mods(self, page=1):
        """Fetches and displays mods from GameBanana in a background thread."""
        print(f"[DEBUG] fetch_browse_mods called with page={page}")
        # Clear existing cards and show loading message
        self._clear_card_layout()
        loading_label = QLabel("<h2>Loading...</h2>")
        loading_label.setAlignment(Qt.AlignCenter)
        self.card_layout.addWidget(loading_label, 0, 0, 1, 4)

        self.browse_current_page = page
        self.browse_page_label.setText(f"Page {self.browse_current_page}")
        self.browse_prev_btn.setEnabled(page > 1)
        
        search_query = self.browse_search_entry.text()
        
        # Disable filters during search for better UX
        is_searching = bool(search_query)
        self.browse_filter_combo.setEnabled(not is_searching)
        self.browse_section_combo.setEnabled(not is_searching)

        sort_param = self.browse_filter_combo.currentText()
        section_id = self.sections.get(self.browse_section_combo.currentText())

        print(f"[DEBUG] Starting worker thread with sort='{sort_param}', page={self.browse_current_page}, search='{search_query}', section={section_id}")

        threading.Thread(
            target=self._fetch_browse_mods_worker,
            args=(sort_param, self.browse_current_page, search_query, section_id),
            daemon=True
        ).start()

    def _fetch_browse_mods_worker(self, sort, page, search, section_id):
        try:
            # Game ID for "Sonic Racing Crossworlds"
            game_id = 21640
            mods, metadata = [], {}

            # Search overrides all other filters and uses the Subfeed endpoint.
            if search:
                mods, metadata = Util.get_gb_mod_list(game_id, 'default', page, search, section_id)
            # If a section is selected, we must use the Subfeed endpoint as it supports category filtering.
            elif section_id:
                sort_map = { "Top": "default", "Newest": "new", "Most Liked": "popular", "Featured": "featured", "Community Spotlight": "spotlight" }
                subfeed_sort = sort_map.get(sort, "default")
                mods, metadata = Util.get_gb_mod_list(game_id, subfeed_sort, page, None, section_id)
            # Use specialized, more curated endpoints only when no section is selected.
            else:
                mods, metadata = Util.fetch_specialized_lists(game_id, sort, page)

            QApplication.instance().postEvent(self, Util.ModListFetchEvent((mods, metadata)))
        except Exception as e:
            error_message = f"Failed to fetch mods: {e}"
            print(error_message)
            QApplication.instance().postEvent(self, Util.ModListFetchEvent([error_message]))

    def _clear_card_layout(self):
        """Removes all widgets from the card layout, ensuring threads are stopped."""
        while self.card_layout.count():
            child = self.card_layout.takeAt(0)
            if child.widget():
                # Explicitly stop any background tasks before deleting
                if hasattr(child.widget(), 'stop'):
                    child.widget().stop()
                child.widget().deleteLater()

    def _update_browse_cards(self, mods):
        mods, metadata = mods
        self._clear_card_layout()
        print(f"[DEBUG] _update_browse_cards received: {mods}")
        self.browse_mods_data = []

        # Update pagination buttons based on metadata
        self.browse_next_btn.setEnabled(not metadata.get('_bIsComplete', True))

        if not mods or (isinstance(mods, list) and len(mods) > 0 and isinstance(mods[0], str)):
            error_message = mods[0] if mods else "No mods found."
            print(f"[DEBUG] No mods found or error received. Displaying: '{error_message}'")
            error_label = QLabel(f"<h2>{error_message}</h2>")
            error_label.setAlignment(Qt.AlignCenter)
            self.card_layout.addWidget(error_label, 0, 0, 1, 4)
            return

        print(f"[DEBUG] Populating browse tree with {len(mods)} mods.")
        self.browse_mods_data = mods
        
        # Determine number of columns based on window width
        cols = max(1, self.scroll_area.width() // 230)
        for i, mod_data in enumerate(mods):
            row, col = divmod(i, cols)
            card = ModCard(mod_data, self.add_mod_from_url)
            self.card_layout.addWidget(card, row, col)

    def _reflow_browse_cards(self):
        """Rearranges existing mod cards to fit the new window size without fetching new data."""
        # Only reflow if the browse tab is visible and has cards.
        if self.notebook.tabText(self.notebook.currentIndex()) != "Browse Mods" or self.card_layout.count() == 0:
            return

        # Check if the first item is a label (e.g., "Loading...", "No mods found.")
        first_item = self.card_layout.itemAt(0).widget()
        if isinstance(first_item, QLabel):
            return # Don't try to reflow a status message

        print("[DEBUG] Reflowing mod cards due to resize.")

        # Collect all existing card widgets
        cards = []
        while self.card_layout.count():
            child = self.card_layout.takeAt(0)
            if child.widget():
                cards.append(child.widget())

        # Recalculate columns and re-add the widgets
        cols = max(1, self.scroll_area.width() // 230)
        for i, card in enumerate(cards):
            row, col = divmod(i, cols)
            self.card_layout.addWidget(card, row, col)

    def browse_prev_page(self):
        if self.browse_current_page > 1:
            self.fetch_browse_mods(page=self.browse_current_page - 1)

    def browse_next_page(self):
        self.fetch_browse_mods(page=self.browse_current_page + 1)

    def clear_browse_search(self):
        """Clears the search bar and refreshes the view."""
        self.browse_search_entry.clear()
        self.fetch_browse_mods(page=1)

if __name__ == '__main__':
    # This is for testing purposes
    app = QApplication(sys.argv)
    # You would need to provide some sample item_data here to run this directly
    window = CrossPatchWindow()
    window.show()
    sys.exit(app.exec())