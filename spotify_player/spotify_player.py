# spotify_player/spotify_player.py
import logging
import requests
from typing import Dict, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal

class SpotifyPlayer(QObject):
    """
    Handles all Spotify Web API interactions for playback control.
    Thread-safe by design - use worker threads for API calls.
    """
    playback_state_changed = pyqtSignal(dict)
    device_list_changed = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, auth_manager):
        super().__init__()
        self.auth_manager = auth_manager
        self.current_device_id = None
        self.current_state = {}
        
    def get_playback_state(self) -> Optional[Dict]:
        """
        Get current playback state from Spotify API.
        Returns None if no active device or error occurs.
        """
        access_token = self.auth_manager.get_access_token()
        if not access_token:
            logging.error("No access token available")
            return None
            
        url = "https://api.spotify.com/v1/me/player"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 204:  # No active device
                return None
            elif response.status_code == 200:
                data = response.json()
                self.current_state = data
                return data
            else:
                logging.error(f"Get playback state failed: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error getting playback state: {e}")
            return None
    
    def get_available_devices(self) -> List[Dict]:
        """Get list of available Spotify Connect devices."""
        access_token = self.auth_manager.get_access_token()
        if not access_token:
            return []
            
        url = "https://api.spotify.com/v1/me/player/devices"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                devices = data.get('devices', [])
                self.device_list_changed.emit(devices)
                return devices
            else:
                logging.error(f"Get devices failed: {response.status_code} - {response.text}")
                return []
        except requests.exceptions.RequestException as e:
            logging.error(f"Error getting devices: {e}")
            return []
    
    def transfer_playback(self, device_id: str) -> bool:
        """Transfer playback to specified device."""
        access_token = self.auth_manager.get_access_token()
        if not access_token:
            return False
            
        url = "https://api.spotify.com/v1/me/player"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        data = {
            "device_ids": [device_id],
            "play": False  # Don't start playing automatically
        }
        
        try:
            response = requests.put(url, headers=headers, json=data, timeout=10)
            if response.status_code == 204:
                self.current_device_id = device_id
                return True
            else:
                logging.error(f"Transfer playback failed: {response.status_code} - {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logging.error(f"Error transferring playback: {e}")
            return False
    
    def play(self, device_id: Optional[str] = None, context_uri: Optional[str] = None, 
             uris: Optional[List[str]] = None, position_ms: Optional[int] = None) -> bool:
        """Start or resume playback."""
        access_token = self.auth_manager.get_access_token()
        if not access_token:
            return False
            
        device_param = f"?device_id={device_id}" if device_id else ""
        url = f"https://api.spotify.com/v1/me/player/play{device_param}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        data = {}
        if context_uri:
            data["context_uri"] = context_uri
        if uris:
            data["uris"] = uris
        if position_ms is not None:
            data["position_ms"] = position_ms
        
        try:
            response = requests.put(url, headers=headers, json=data if data else None, timeout=10)
            return response.status_code == 204
        except requests.exceptions.RequestException as e:
            logging.error(f"Error playing: {e}")
            return False
    
    def pause(self, device_id: Optional[str] = None) -> bool:
        """Pause playback."""
        access_token = self.auth_manager.get_access_token()
        if not access_token:
            return False
            
        device_param = f"?device_id={device_id}" if device_id else ""
        url = f"https://api.spotify.com/v1/me/player/pause{device_param}"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = requests.put(url, headers=headers, timeout=10)
            return response.status_code == 204
        except requests.exceptions.RequestException as e:
            logging.error(f"Error pausing: {e}")
            return False
    
    def next_track(self, device_id: Optional[str] = None) -> bool:
        """Skip to next track."""
        access_token = self.auth_manager.get_access_token()
        if not access_token:
            return False
            
        device_param = f"?device_id={device_id}" if device_id else ""
        url = f"https://api.spotify.com/v1/me/player/next{device_param}"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = requests.post(url, headers=headers, timeout=10)
            return response.status_code == 204
        except requests.exceptions.RequestException as e:
            logging.error(f"Error skipping to next: {e}")
            return False
    
    def previous_track(self, device_id: Optional[str] = None) -> bool:
        """Skip to previous track."""
        access_token = self.auth_manager.get_access_token()
        if not access_token:
            return False
            
        device_param = f"?device_id={device_id}" if device_id else ""
        url = f"https://api.spotify.com/v1/me/player/previous{device_param}"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = requests.post(url, headers=headers, timeout=10)
            return response.status_code == 204
        except requests.exceptions.RequestException as e:
            logging.error(f"Error skipping to previous: {e}")
            return False
    
    def set_volume(self, volume_percent: int, device_id: Optional[str] = None) -> bool:
        """Set volume level (0-100)."""
        access_token = self.auth_manager.get_access_token()
        if not access_token:
            return False
            
        params = {"volume_percent": min(max(volume_percent, 0), 100)}
        if device_id:
            params["device_id"] = device_id
            
        url = "https://api.spotify.com/v1/me/player/volume"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = requests.put(url, headers=headers, params=params, timeout=10)
            return response.status_code == 204
        except requests.exceptions.RequestException as e:
            logging.error(f"Error setting volume: {e}")
            return False
    
    def seek_to_position(self, position_ms: int, device_id: Optional[str] = None) -> bool:
        """Seek to specific position in track."""
        access_token = self.auth_manager.get_access_token()
        if not access_token:
            return False
            
        params = {"position_ms": max(position_ms, 0)}
        if device_id:
            params["device_id"] = device_id
            
        url = "https://api.spotify.com/v1/me/player/seek"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = requests.put(url, headers=headers, params=params, timeout=10)
            return response.status_code == 204
        except requests.exceptions.RequestException as e:
            logging.error(f"Error seeking: {e}")
            return False
    
    def play_album(self, album_id: str, device_id: Optional[str] = None) -> bool:
        """Play a specific album by ID."""
        context_uri = f"spotify:album:{album_id}"
        return self.play(device_id=device_id, context_uri=context_uri)