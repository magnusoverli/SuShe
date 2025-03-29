import base64
import hashlib
import random
import string
import webbrowser
import urllib.parse
import threading
import requests
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
from PyQt6.QtCore import QObject, pyqtSignal

class SpotifyAuth(QObject):
    auth_complete = pyqtSignal(bool)
    auth_timeout = pyqtSignal()
    
    def __init__(self, client_id, redirect_port=8888):
        QObject.__init__(self)
        self.client_id = client_id
        self.redirect_port = redirect_port
        self.redirect_uri = f"http://localhost:{redirect_port}/callback"
        self.access_token = None
        self.refresh_token = None
        self.code_verifier = None
        self.auth_code = None
        self.server = None
        self.server_should_shutdown = False
        self.server_thread = None
        
    def generate_code_verifier(self):
        code_verifier = ''.join(random.choice(string.ascii_letters + string.digits + "-._~") for _ in range(64))
        self.code_verifier = code_verifier
        return code_verifier
        
    def generate_code_challenge(self, code_verifier):
        code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8').replace('=', '')
        return code_challenge
        
    def get_authorization_url(self):
        if not self.code_verifier:
            self.generate_code_verifier()
        code_challenge = self.generate_code_challenge(self.code_verifier)
        
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "scope": "user-read-private user-library-read"  # Adjust scopes as needed
        }
        
        return f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"
        
    def start_auth_flow(self, timeout_seconds=120):
        auth_url = self.get_authorization_url()
        self.auth_code = None
        self.server_should_shutdown = False
        self.start_auth_server()
        webbrowser.open(auth_url)
        
        # Start a timer to emit timeout signal if needed
        def check_timeout():
            start_time = time.time()
            while time.time() - start_time < timeout_seconds:
                if self.auth_code or self.server_should_shutdown:
                    return
                time.sleep(0.5)
            
            if not self.auth_code:
                self.auth_timeout.emit()
                self.server_should_shutdown = True
        
        timeout_thread = threading.Thread(target=check_timeout)
        timeout_thread.daemon = True
        timeout_thread.start()
        
    def start_auth_server(self):
        auth_instance = self
        
        class AuthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    if '/callback' in self.path:
                        query = urllib.parse.urlparse(self.path).query
                        params = urllib.parse.parse_qs(query)
                        
                        if "code" in params:
                            auth_instance.auth_code = params["code"][0]
                            self.send_response(200)
                            self.send_header("Content-type", "text/html")
                            self.end_headers()
                            self.wfile.write(b"<html><body><h2>Authentication Successful</h2><p>You can close this window now.</p></body></html>")
                            auth_instance.auth_complete.emit(True)
                        else:
                            self.send_response(400)
                            self.send_header("Content-type", "text/html")
                            self.end_headers()
                            self.wfile.write(b"<html><body><h2>Authentication Failed</h2><p>No authorization code received.</p></body></html>")
                            auth_instance.auth_complete.emit(False)
                        
                        auth_instance.server_should_shutdown = True
                except Exception as e:
                    logging.error(f"Error in callback handler: {e}")
                    auth_instance.auth_complete.emit(False)
            
            # Silence server logs
            def log_message(self, format, *args):
                return
        
        def server_thread_func():
            try:
                self.server = HTTPServer(('localhost', self.redirect_port), AuthHandler)
                while not self.server_should_shutdown:
                    self.server.handle_request()
                self.server.server_close()
            except Exception as e:
                logging.error(f"Error in auth server: {e}")
                self.auth_complete.emit(False)
        
        self.server_thread = threading.Thread(target=server_thread_func)
        self.server_thread.daemon = True
        self.server_thread.start()

    def cleanup_auth_resources(self):
        """Clean up authentication resources"""
        if hasattr(self, 'server') and self.server:
            self.server_should_shutdown = True
            if hasattr(self, 'server_thread') and self.server_thread:
                self.server_thread.join(timeout=1.0)

    def exchange_code_for_tokens(self):
        if not self.auth_code or not self.code_verifier:
            return False
            
        token_url = "https://accounts.spotify.com/api/token"
        payload = {
            "client_id": self.client_id,
            "grant_type": "authorization_code",
            "code": self.auth_code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": self.code_verifier
        }
        
        response = requests.post(token_url, data=payload)
        
        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens.get("access_token")
            self.refresh_token = tokens.get("refresh_token")
            return True
        else:
            logging.error(f"Token exchange failed: {response.text}")
            return False
            
    def refresh_access_token(self):
        if not self.refresh_token:
            return False
            
        token_url = "https://accounts.spotify.com/api/token"
        payload = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        response = requests.post(token_url, data=payload)
        
        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens.get("access_token")
            if "refresh_token" in tokens:
                self.refresh_token = tokens.get("refresh_token")
            return True
        else:
            return False

    def save_tokens(self, path):
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token
        }
        
        with open(path, 'w') as f:
            json.dump(data, f)
            
    def load_tokens(self, path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
            return True
        except:
            return False