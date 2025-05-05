# spotify_player/compact_player.py
import logging
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton, 
                             QLabel, QSlider, QComboBox, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QEvent
from PyQt6.QtGui import QPixmap, QImage, QIcon
import requests

class CompactPlayer(QWidget):
    """
    Compact Spotify Connect player widget.
    Designed to fit between album list and status bar.
    """
    play_pause_requested = pyqtSignal()
    next_track_requested = pyqtSignal()
    previous_track_requested = pyqtSignal()
    device_change_requested = pyqtSignal(str)
    volume_change_requested = pyqtSignal(int)
    seek_requested = pyqtSignal(int)
    album_click_requested = pyqtSignal(str)  # When user clicks album art
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_playing = False
        self.current_track = None
        self.current_device_id = None
        self.devices = []
        self.seeking = False
        self.current_album_id = None
        
        self.initUI()
        self.setup_timers()
        
        # Instead, disable only the controls that require connection
        self.prev_btn.setEnabled(False)
        self.play_pause_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.progress_slider.setEnabled(False)
        self.volume_slider.setEnabled(False)
        self.device_combo.setEnabled(False)
        
        # Keep the connect button enabled so user can click it
        self.connect_btn.setEnabled(True)
        
    def initUI(self):
        """Initialize the compact player UI."""
        # Set fixed height for compact player
        self.setFixedHeight(72)
        
        # Main layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(16, 8, 16, 8)
        main_layout.setSpacing(16)
        
        # Album art (smaller for compact player)
        self.album_art = QLabel()
        self.album_art.setFixedSize(56, 56)
        self.album_art.setStyleSheet("""
            QLabel {
                border-radius: 4px;
                background-color: #282828;
            }
        """)
        self.album_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.album_art.setCursor(Qt.CursorShape.PointingHandCursor)
        self.album_art.mousePressEvent = self.on_album_art_click
        main_layout.addWidget(self.album_art)
        
        # Track info and progress bar container
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        # Track details
        track_details = QHBoxLayout()
        track_details.setSpacing(4)
        
        self.track_name = QLabel("No track")
        self.track_name.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 11pt;")
        self.track_name.setFixedHeight(20)
        track_details.addWidget(self.track_name)
        
        self.artist_name = QLabel("Select a device to start")
        self.artist_name.setStyleSheet("color: #B3B3B3; font-size: 10pt;")
        self.artist_name.setFixedHeight(18)
        track_details.addWidget(self.artist_name)
        
        info_layout.addLayout(track_details)
        
        # Progress bar with time labels
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(8)
        
        self.progress_label = QLabel("0:00")
        self.progress_label.setStyleSheet("color: #B3B3B3; font-size: 9pt;")
        self.progress_label.setFixedWidth(35)
        progress_layout.addWidget(self.progress_label)
        
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setObjectName("progress_slider")
        self.progress_slider.setMinimum(0)
        self.progress_slider.setMaximum(0)
        self.progress_slider.setValue(0)
        self.progress_slider.sliderPressed.connect(self.on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self.on_slider_released)
        self.progress_slider.sliderMoved.connect(self.on_slider_moved)
        progress_layout.addWidget(self.progress_slider)
        
        self.duration_label = QLabel("0:00")
        self.duration_label.setStyleSheet("color: #B3B3B3; font-size: 9pt;")
        self.duration_label.setFixedWidth(35)
        progress_layout.addWidget(self.duration_label)
        
        info_layout.addLayout(progress_layout)
        main_layout.addLayout(info_layout)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(4)
        
        # Previous button
        self.prev_btn = QPushButton()
        self.prev_btn.setObjectName("compact_prev_btn")
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.setText("⏮")
        self.prev_btn.clicked.connect(self.previous_track_requested.emit)
        controls_layout.addWidget(self.prev_btn)
        
        # Play/Pause button
        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setObjectName("compact_play_pause_btn")
        self.play_pause_btn.setFixedSize(40, 40)
        self.play_pause_btn.setText("▶")
        self.play_pause_btn.clicked.connect(self.play_pause_requested.emit)
        controls_layout.addWidget(self.play_pause_btn)
        
        # Next button
        self.next_btn = QPushButton()
        self.next_btn.setObjectName("compact_next_btn")
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.setText("⏭")
        self.next_btn.clicked.connect(self.next_track_requested.emit)
        controls_layout.addWidget(self.next_btn)
        
        main_layout.addLayout(controls_layout)
        
        # Volume control
        volume_layout = QHBoxLayout()
        volume_layout.setSpacing(4)
        
        self.volume_icon = QLabel("🔊")
        self.volume_icon.setFixedWidth(20)
        volume_layout.addWidget(self.volume_icon)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setObjectName("volume_slider")
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        volume_layout.addWidget(self.volume_slider)
        
        main_layout.addLayout(volume_layout)
        
        # Device selector
        self.device_combo = QComboBox()
        self.device_combo.setObjectName("compact_device_combo")
        self.device_combo.setMinimumWidth(140)
        self.device_combo.setMaximumWidth(200)
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        main_layout.addWidget(self.device_combo)
        
        # Connect/Disconnect button
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("compact_connect_btn")
        self.connect_btn.setFixedSize(80, 32)
        main_layout.addWidget(self.connect_btn)
        
        self.setLayout(main_layout)
        
        # Initial state
        self.setEnabled(False)
        
    def setup_timers(self):
        """Set up timers for updating playback progress."""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_progress)
        self.update_timer.setInterval(1000)  # Update every second
        
    def update_playback_state(self, state: dict):
        """Update the UI based on current playback state."""
        if not state:
            self.reset_ui()
            return
            
        # Update play/pause button
        self.is_playing = state.get('is_playing', False)
        self.play_pause_btn.setText("⏸" if self.is_playing else "▶")
        
        # Start/stop update timer
        if self.is_playing:
            self.update_timer.start()
        else:
            self.update_timer.stop()
            
        # Update track info
        item = state.get('item', {})
        if item:
            track_name = item.get('name', 'Unknown')
            self.track_name.setText(track_name)
            
            artists = ', '.join([artist['name'] for artist in item.get('artists', [])])
            self.artist_name.setText(artists)
            
            # Update album art and store album ID
            album = item.get('album', {})
            images = album.get('images', [])
            self.current_album_id = album.get('id', None)
            
            if images:
                self.load_album_art(images[0]['url'])
            else:
                self.album_art.setText("🎵")
                self.album_art.setPixmap(QPixmap())
            
        # Update progress
        progress_ms = state.get('progress_ms', 0)
        duration_ms = item.get('duration_ms', 0) if item else 0
        
        if not self.seeking:
            self.progress_slider.setMaximum(duration_ms)
            self.progress_slider.setValue(progress_ms)
            self.update_progress_labels(progress_ms, duration_ms)
            
        # Update volume
        device = state.get('device', {})
        volume = device.get('volume_percent', 0)
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(volume)
        self.volume_slider.blockSignals(False)
        
    def update_device_list(self, devices: list):
        """Update the device combo box with available devices."""
        self.devices = devices
        current_device = self.current_device_id
        
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        
        if not devices:
            self.device_combo.addItem("No devices available")
            self.device_combo.setEnabled(False)
        else:
            active_device_found = False
            for idx, device in enumerate(devices):
                device_name = device.get('name', 'Unknown Device')
                device_id = device.get('id', '')
                device_type = device.get('type', '')
                
                display_text = f"{device_name}"
                if device.get('is_active', False):
                    display_text += " - Active"
                    active_device_found = True
                    
                self.device_combo.addItem(display_text, device_id)
                
                if device_id == current_device:
                    self.device_combo.setCurrentIndex(idx)
                    
            self.device_combo.setEnabled(True)
        
        self.device_combo.blockSignals(False)
        
    def load_album_art(self, url: str):
        """Load album art from URL."""
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                image = QImage()
                image.loadFromData(response.content)
                pixmap = QPixmap.fromImage(image)
                scaled_pixmap = pixmap.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio, 
                                            Qt.TransformationMode.SmoothTransformation)
                self.album_art.setPixmap(scaled_pixmap)
        except Exception as e:
            logging.error(f"Failed to load album art: {e}")
            self.album_art.setText("🎵")
            
    def update_progress(self):
        """Update progress bar position."""
        if not self.seeking and not self.progress_slider.isSliderDown():
            current_value = self.progress_slider.value()
            if current_value < self.progress_slider.maximum():
                new_value = current_value + 1000  # Add 1 second
                self.progress_slider.setValue(new_value)
                self.update_progress_labels(new_value, self.progress_slider.maximum())
                
    def update_progress_labels(self, current_ms: int, duration_ms: int):
        """Update progress time labels."""
        self.progress_label.setText(self.format_time(current_ms))
        self.duration_label.setText(self.format_time(duration_ms))
        
    def format_time(self, ms: int) -> str:
        """Format milliseconds to MM:SS."""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
        
    def on_slider_pressed(self):
        """Handle slider press event."""
        self.seeking = True
        self.update_timer.stop()
        
    def on_slider_released(self):
        """Handle slider release event."""
        self.seeking = False
        position_ms = self.progress_slider.value()
        self.seek_requested.emit(position_ms)
        if self.is_playing:
            self.update_timer.start()
            
    def on_slider_moved(self, value: int):
        """Handle slider movement."""
        self.update_progress_labels(value, self.progress_slider.maximum())
        
    def on_volume_changed(self, value: int):
        """Handle volume slider change."""
        # Update volume icon based on level
        if value == 0:
            self.volume_icon.setText("🔇")
        elif value < 30:
            self.volume_icon.setText("🔉")
        else:
            self.volume_icon.setText("🔊")
            
        self.volume_change_requested.emit(value)
        
    def on_device_changed(self, index: int):
        """Handle device selection change."""
        if index >= 0 and self.devices:
            device_id = self.device_combo.itemData(index)
            if device_id:
                self.current_device_id = device_id
                self.device_change_requested.emit(device_id)
                
    def on_album_art_click(self, event):
        """Handle clicks on album art."""
        if self.current_album_id:
            self.album_click_requested.emit(self.current_album_id)
            
    def reset_ui(self):
        """Reset UI to inactive state."""
        self.track_name.setText("No track")
        self.artist_name.setText("Select a device to start")
        self.album_art.setText("🎵")
        self.album_art.setPixmap(QPixmap())