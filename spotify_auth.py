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
import socket
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QWaitCondition

class SpotifyAuth(QObject):
    """
    Handles Spotify OAuth authentication flow with PKCE.
    Includes a local HTTP server to receive the callback from Spotify.
    """
    auth_complete = pyqtSignal(bool)
    auth_timeout = pyqtSignal()
    
    def __init__(self, client_id, redirect_port=8888):
        super().__init__()
        self.client_id = client_id
        self.redirect_port = redirect_port
        self.redirect_uri = f"http://localhost:{redirect_port}/callback"
        self.access_token = None
        self.refresh_token = None
        self.code_verifier = None
        self.auth_code = None
        self.server = None
        self.server_thread = None
        
        # Thread synchronization
        self.mutex = QMutex()
        self.auth_result_available = QWaitCondition()
        self.server_should_shutdown = False
        self.auth_success = False
        self.callback_received = False
        
        # Find an available port if the default is in use
        self.find_available_port()
    
    def find_available_port(self):
        """Find an available port if the default port is in use."""
        original_port = self.redirect_port
        try:
            # Try to bind to the default port
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.bind(('localhost', self.redirect_port))
            s.close()
            logging.info(f"Default port {self.redirect_port} is available")
        except OSError:
            # Port is in use, try to find an available one
            for port in range(original_port + 1, original_port + 20):
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(1)
                    s.bind(('localhost', port))
                    s.close()
                    self.redirect_port = port
                    self.redirect_uri = f"http://localhost:{port}/callback"
                    logging.info(f"Found available port {port}")
                    return
                except OSError:
                    continue
            
            # If we get here, we couldn't find an available port
            logging.error("Could not find an available port for the callback server")
        
    def generate_code_verifier(self):
        """Generate a random code verifier string for PKCE."""
        code_verifier = ''.join(random.choice(string.ascii_letters + string.digits + "-._~") for _ in range(64))
        self.code_verifier = code_verifier
        return code_verifier
        
    def generate_code_challenge(self, code_verifier):
        """Generate a code challenge from the code verifier using SHA-256."""
        code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8').replace('=', '')
        return code_challenge
        
    def get_authorization_url(self):
        """Generate the Spotify authorization URL with PKCE parameters."""
        if not self.code_verifier:
            self.generate_code_verifier()
        code_challenge = self.generate_code_challenge(self.code_verifier)
        
        # Generate a unique state parameter for security
        state = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
        
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "state": state,
            "scope": "user-read-private user-library-read",
            # Add timestamp to prevent caching
            "_": int(time.time())
        }
        
        return f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"
        
    def start_auth_flow(self, timeout_seconds=120):
        """
        Start the OAuth flow by launching a local server and opening the browser.
        
        Args:
            timeout_seconds: Number of seconds to wait for authentication before timing out
        """
        # Ensure any previous auth flow is cleaned up
        self.cleanup_auth_resources()
        
        # Reset all state flags with mutex protection
        self.mutex.lock()
        self.server_should_shutdown = False
        self.callback_received = False
        self.auth_success = False
        self.auth_code = None
        self.mutex.unlock()
        
        # Generate fresh verifier and auth URL
        auth_url = self.get_authorization_url()
        logging.info(f"Starting auth flow with redirect to: {self.redirect_uri}")
        
        # Start the callback server
        if not self.start_callback_server():
            logging.error("Failed to start callback server")
            # Emit signals from main thread only
            self.auth_complete.emit(False)
            return
        
        # Open the browser for authentication
        try:
            webbrowser.open(auth_url)
            logging.info("Browser opened for authentication")
        except Exception as e:
            logging.error(f"Failed to open browser: {e}")
            self.mutex.lock()
            self.server_should_shutdown = True
            self.mutex.unlock()
            self.auth_complete.emit(False)
            return
        
        # Start a timeout monitor (as a non-Qt thread)
        timeout_thread = threading.Thread(
            target=self._timeout_monitor,
            args=(timeout_seconds,),
            daemon=True
        )
        timeout_thread.start()
    
    def _timeout_monitor(self, timeout_seconds):
        """
        Monitor for timeout during authentication.
        This runs in a separate thread.
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            # Check if callback was received
            self.mutex.lock()
            if self.callback_received:
                self.mutex.unlock()
                return
            self.mutex.unlock()
            
            # Sleep briefly to avoid busy waiting
            time.sleep(0.5)
        
        # If we get here, timeout occurred
        logging.warning(f"Authentication timed out after {timeout_seconds} seconds")
        
        # Signal server to shut down
        self.mutex.lock()
        self.server_should_shutdown = True
        self.mutex.unlock()
        
        # Emit timeout signal (safe because signals are thread-safe in PyQt)
        self.auth_timeout.emit()
    
    def start_callback_server(self):
        """
        Start the local HTTP server to receive the callback.
        Returns True if server started successfully, False otherwise.
        """
        # Create a reference to self for the handler class
        auth_instance = self
        
        class CallbackHandler(BaseHTTPRequestHandler):
            """Handle the OAuth callback request."""
            
            def do_GET(self):
                """Process GET requests."""
                try:
                    if '/callback' not in self.path:
                        self.send_error(404)
                        return
                    
                    # Parse the callback URL
                    parsed_url = urllib.parse.urlparse(self.path)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    
                    # Process the callback parameters
                    if "code" in query_params:
                        # Success case
                        auth_code = query_params["code"][0]
                        
                        # Update state atomically with mutex
                        auth_instance.mutex.lock()
                        auth_instance.auth_code = auth_code
                        auth_instance.auth_success = True
                        auth_instance.callback_received = True
                        # Signal server should shutdown
                        auth_instance.server_should_shutdown = True
                        auth_instance.mutex.unlock()
                        
                        # Send success response to browser
                        self.send_response(200)
                        self.send_header("Content-type", "text/html")
                        self.end_headers()
                        self.wfile.write(b"""
                        <html>
                        <head>
                            <title>Authentication Successful</title>
                            <style>
                                body { font-family: Arial, sans-serif; text-align: center; padding: 40px; }
                                h2 { color: #1DB954; }
                                p { margin: 20px 0; }
                            </style>
                        </head>
                        <body>
                            <h2>Authentication Successful</h2>
                            <p>You have successfully authenticated with Spotify.</p>
                            <p>You can close this window and return to the application.</p>
                        </body>
                        </html>
                        """)
                        
                        # Emit signal (safe because signals are thread-safe in PyQt)
                        auth_instance.auth_complete.emit(True)
                        
                    elif "error" in query_params:
                        # Error case
                        error_msg = query_params["error"][0]
                        logging.error(f"Authentication error: {error_msg}")
                        
                        # Update state atomically with mutex
                        auth_instance.mutex.lock()
                        auth_instance.auth_success = False
                        auth_instance.callback_received = True
                        # Signal server should shutdown
                        auth_instance.server_should_shutdown = True
                        auth_instance.mutex.unlock()
                        
                        # Send error response to browser
                        self.send_response(400)
                        self.send_header("Content-type", "text/html")
                        self.end_headers()
                        self.wfile.write(f"""
                        <html>
                        <head>
                            <title>Authentication Failed</title>
                            <style>
                                body {{ font-family: Arial, sans-serif; text-align: center; padding: 40px; }}
                                h2 {{ color: #FF0000; }}
                                p {{ margin: 20px 0; }}
                            </style>
                        </head>
                        <body>
                            <h2>Authentication Failed</h2>
                            <p>Error: {error_msg}</p>
                            <p>Please close this window and try again.</p>
                        </body>
                        </html>
                        """.encode('utf-8'))
                        
                        # Emit signal (safe because signals are thread-safe in PyQt)
                        auth_instance.auth_complete.emit(False)
                        
                    else:
                        # Missing code parameter
                        logging.error("No code or error in callback")
                        
                        # Update state atomically with mutex
                        auth_instance.mutex.lock()
                        auth_instance.auth_success = False
                        auth_instance.callback_received = True
                        # Signal server should shutdown
                        auth_instance.server_should_shutdown = True
                        auth_instance.mutex.unlock()
                        
                        # Send error response to browser
                        self.send_response(400)
                        self.send_header("Content-type", "text/html")
                        self.end_headers()
                        self.wfile.write(b"""
                        <html>
                        <head>
                            <title>Authentication Failed</title>
                            <style>
                                body { font-family: Arial, sans-serif; text-align: center; padding: 40px; }
                                h2 { color: #FF0000; }
                                p { margin: 20px 0; }
                            </style>
                        </head>
                        <body>
                            <h2>Authentication Failed</h2>
                            <p>No authorization code received.</p>
                            <p>Please close this window and try again.</p>
                        </body>
                        </html>
                        """)
                        
                        # Emit signal (safe because signals are thread-safe in PyQt)
                        auth_instance.auth_complete.emit(False)
                    
                except Exception as e:
                    logging.error(f"Error in callback handler: {e}")
                    
                    # Update state atomically with mutex
                    auth_instance.mutex.lock()
                    auth_instance.auth_success = False
                    auth_instance.callback_received = True
                    # Signal server should shutdown
                    auth_instance.server_should_shutdown = True
                    auth_instance.mutex.unlock()
                    
                    # Send error response
                    try:
                        self.send_response(500)
                        self.send_header("Content-type", "text/html")
                        self.end_headers()
                        self.wfile.write(f"""
                        <html>
                        <head>
                            <title>Server Error</title>
                            <style>
                                body {{ font-family: Arial, sans-serif; text-align: center; padding: 40px; }}
                                h2 {{ color: #FF0000; }}
                                p {{ margin: 20px 0; }}
                            </style>
                        </head>
                        <body>
                            <h2>Server Error</h2>
                            <p>{str(e)}</p>
                            <p>Please close this window and try again.</p>
                        </body>
                        </html>
                        """.encode('utf-8'))
                    except:
                        pass
                    
                    # Emit signal (safe because signals are thread-safe in PyQt)
                    auth_instance.auth_complete.emit(False)
            
            # Silence server logs
            def log_message(self, format, *args):
                return
        
        def server_thread_func():
            """Function to run the server in a separate thread."""
            try:
                # Set up a socket with REUSEADDR to allow immediate reuse
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.socket.bind(('localhost', self.redirect_port))
                
                # Create an HTTP server
                class ReuseAddrHTTPServer(HTTPServer):
                    def server_bind(self):
                        self.socket = auth_instance.socket
                
                # Create and start the server
                self.server = ReuseAddrHTTPServer(('localhost', self.redirect_port), CallbackHandler)
                logging.info(f"Callback server started on port {self.redirect_port}")
                
                # Set a short timeout to check shutdown flag frequently
                self.server.timeout = 0.5
                
                # Process requests until signaled to shut down
                while True:
                    # Check if we should shut down (with mutex protection)
                    self.mutex.lock()
                    should_shutdown = self.server_should_shutdown
                    self.mutex.unlock()
                    
                    if should_shutdown:
                        break
                    
                    # Handle a single request with timeout
                    self.server.handle_request()
                
                # Clean up server resources
                logging.info("Shutting down callback server")
                try:
                    self.server.server_close()
                    self.socket.close()
                    logging.info("Server closed successfully")
                except Exception as e:
                    logging.error(f"Error closing server: {e}")
                
                # Clear server references
                self.server = None
                self.socket = None
                
            except OSError as e:
                if "address already in use" in str(e).lower():
                    logging.error(f"Port {self.redirect_port} is already in use.")
                else:
                    logging.error(f"Server error: {e}")
                return False
            except Exception as e:
                logging.error(f"Unexpected server error: {e}")
                return False
            
            return True
        
        try:
            # Start the server thread as a standard Python thread (not QThread)
            self.server_thread = threading.Thread(target=server_thread_func, daemon=True)
            self.server_thread.start()
            
            # Give the server a moment to start
            time.sleep(0.2)
            
            # Check if server started successfully
            if self.server is None:
                logging.error("Failed to start server")
                return False
            
            logging.info("Server thread started successfully")
            return True
        except Exception as e:
            logging.error(f"Failed to start server thread: {e}")
            return False
    
    def cleanup_auth_resources(self):
        """
        Clean up authentication resources.
        This must be called when shutting down or when starting a new auth flow.
        """
        logging.info("Cleaning up authentication resources")
        
        # Signal the server to shut down if it exists
        self.mutex.lock()
        self.server_should_shutdown = True
        self.mutex.unlock()
        
        # Wait for server thread to terminate
        if hasattr(self, 'server_thread') and self.server_thread and self.server_thread.is_alive():
            try:
                self.server_thread.join(timeout=2.0)
                if self.server_thread.is_alive():
                    logging.warning("Server thread did not terminate within timeout")
            except Exception as e:
                logging.error(f"Error joining server thread: {e}")
        
        # Explicitly close socket if it exists
        if hasattr(self, 'socket') and self.socket:
            try:
                self.socket.close()
            except Exception as e:
                logging.warning(f"Error closing socket: {e}")
        
        # Clear server reference
        self.server = None
        self.server_thread = None

    def exchange_code_for_tokens(self):
        """
        Exchange the authorization code for access and refresh tokens.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.auth_code or not self.code_verifier:
            logging.error("Missing auth_code or code_verifier")
            return False
            
        token_url = "https://accounts.spotify.com/api/token"
        payload = {
            "client_id": self.client_id,
            "grant_type": "authorization_code",
            "code": self.auth_code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": self.code_verifier
        }
        
        try:
            # Use a longer timeout for token exchange
            response = requests.post(token_url, data=payload, timeout=15)
            
            if response.status_code == 200:
                tokens = response.json()
                self.access_token = tokens.get("access_token")
                self.refresh_token = tokens.get("refresh_token")
                
                # Log tokens (partially masked)
                access_token_masked = f"{self.access_token[:5]}...{self.access_token[-5:]}" if self.access_token else None
                refresh_token_masked = f"{self.refresh_token[:5]}...{self.refresh_token[-5:]}" if self.refresh_token else None
                logging.info(f"Received access token: {access_token_masked}")
                logging.info(f"Received refresh token: {refresh_token_masked}")
                
                return True
            else:
                logging.error(f"Token exchange failed: {response.status_code} - {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logging.error(f"Request exception during token exchange: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected exception during token exchange: {e}")
            return False
            
    def refresh_access_token(self):
        """
        Refresh the access token using the refresh token.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.refresh_token:
            logging.error("No refresh token available")
            return False
            
        token_url = "https://accounts.spotify.com/api/token"
        payload = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        try:
            # Use a longer timeout for token refresh
            response = requests.post(token_url, data=payload, timeout=15)
            
            if response.status_code == 200:
                tokens = response.json()
                self.access_token = tokens.get("access_token")
                
                # Some APIs return a new refresh token, save it if provided
                if "refresh_token" in tokens:
                    self.refresh_token = tokens.get("refresh_token")
                
                # Log refreshed token (partially masked)
                access_token_masked = f"{self.access_token[:5]}...{self.access_token[-5:]}" if self.access_token else None
                logging.info(f"Refreshed access token: {access_token_masked}")
                
                return True
            else:
                logging.error(f"Token refresh failed: {response.status_code} - {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logging.error(f"Request exception during token refresh: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected exception during token refresh: {e}")
            return False

    def save_tokens(self, path):
        """
        Save access and refresh tokens to a file.
        
        Args:
            path (str): Path to save the tokens
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.access_token or not self.refresh_token:
            logging.error("Missing tokens to save")
            return False
            
        # Create directory if it doesn't exist
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except Exception as e:
                logging.error(f"Failed to create directory for tokens: {e}")
                return False
        
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "created_at": int(time.time())  # Store creation time
        }
        
        try:
            # Write to a temporary file first, then rename for atomic write
            temp_path = f"{path}.tmp"
            with open(temp_path, 'w') as f:
                json.dump(data, f)
            
            # Rename to target path
            if os.path.exists(path):
                os.remove(path)
            os.rename(temp_path, path)
            
            logging.info(f"Tokens saved to {path}")
            return True
        except Exception as e:
            logging.error(f"Failed to save tokens: {e}")
            return False
            
    def load_tokens(self, path):
        """
        Load access and refresh tokens from a file.
        
        Args:
            path (str): Path to load the tokens from
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not os.path.exists(path):
            logging.warning(f"Token file not found: {path}")
            return False
            
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            
            # Check if tokens were loaded successfully
            if not self.access_token or not self.refresh_token:
                logging.error("Invalid token file format")
                return False
                
            # Check token age (optional)
            created_at = data.get("created_at", 0)
            token_age = int(time.time()) - created_at
            logging.info(f"Loaded tokens from {path} (age: {token_age} seconds)")
            
            return True
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON in token file: {path}")
            return False
        except Exception as e:
            logging.error(f"Failed to load tokens: {e}")
            return False