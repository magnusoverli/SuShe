# spotify_player/player_workers.py
import logging
from PyQt6.QtCore import QObject, pyqtSignal, QThread

class SpotifyPlayerWorker(QThread):
    """
    Worker thread for Spotify API operations.
    Handles all network operations asynchronously.
    """
    playback_state_updated = pyqtSignal(dict)
    devices_updated = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    operation_completed = pyqtSignal(bool)
    
    def __init__(self, spotify_player, operation=None, **kwargs):
        super().__init__()
        self.spotify_player = spotify_player
        self.operation = operation
        self.kwargs = kwargs
        self.running = True
        
    def run(self):
        """Execute the requested operation."""
        try:
            if self.operation == "get_playback_state":
                while self.running:
                    state = self.spotify_player.get_playback_state()
                    self.playback_state_updated.emit(state or {})
                    # Sleep for a bit to avoid too frequent requests
                    self.msleep(1000)
                    
            elif self.operation == "get_devices":
                devices = self.spotify_player.get_available_devices()
                self.devices_updated.emit(devices)
                self.operation_completed.emit(True)
                
            elif self.operation == "play":
                success = self.spotify_player.play(**self.kwargs)
                self.operation_completed.emit(success)
                
            elif self.operation == "pause":
                success = self.spotify_player.pause(**self.kwargs)
                self.operation_completed.emit(success)
                
            elif self.operation == "next_track":
                success = self.spotify_player.next_track(**self.kwargs)
                self.operation_completed.emit(success)
                
            elif self.operation == "previous_track":
                success = self.spotify_player.previous_track(**self.kwargs)
                self.operation_completed.emit(success)
                
            elif self.operation == "set_volume":
                success = self.spotify_player.set_volume(**self.kwargs)
                self.operation_completed.emit(success)
                
            elif self.operation == "seek":
                success = self.spotify_player.seek_to_position(**self.kwargs)
                self.operation_completed.emit(success)
                
            elif self.operation == "transfer_playback":
                success = self.spotify_player.transfer_playback(**self.kwargs)
                self.operation_completed.emit(success)
                
        except Exception as e:
            logging.error(f"Error in player worker: {e}")
            self.error_occurred.emit(str(e))
            
    def stop(self):
        """Stop the worker thread."""
        self.running = False