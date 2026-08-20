"""
Camera Streaming Utilities
Handles video capture, streaming, and reconnection logic for IoT Cameras
"""

import cv2
import logging
import threading
import time

logger = logging.getLogger(__name__)


class CameraStream:
    """
    Manages video streaming from an IP camera with automatic reconnection
    """
    
    def __init__(self, camera_obj):
        """
        Initialize camera stream
        
        Args:
            camera_obj: IPCamera model instance
        """
        self.camera = camera_obj
        self.stream_url = camera_obj.get_stream_url()
        self.capture = None
        self.frame = None
        self.is_running = False
        self.lock = threading.Lock()
        self.thread = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3  # Reduced from 5 to 3
        self.reconnect_delay = 5  # Increased from 3 to 5 seconds
        self.last_frame_time = time.time()
        self.frame_timeout = 10  # Consider stream dead if no frame for 10 seconds
        self.frame_skip = 1  # No frame skipping for single camera (1 = no skip)
        self.frame_counter = 0
    
    def start(self):
        """Start the camera stream in a separate thread"""
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._update_frame, daemon=True)
            self.thread.start()
            return True
        return False
    
    def stop(self):
        """Stop the camera stream"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.capture:
            self.capture.release()
            self.capture = None
    
    def _connect(self):
        """
        Attempt to connect to the camera
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Release previous capture if exists
            if self.capture:
                self.capture.release()
                self.capture = None
            
            logger.debug("Attempting to connect to %s", self.camera.name)
            
            # Open camera stream with optimized settings for real-time streaming
            self.capture = cv2.VideoCapture(self.stream_url, cv2.CAP_FFMPEG)
            
            # Critical settings to reduce latency and enable real-time streaming
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffer - CRITICAL for real-time
            self.capture.set(cv2.CAP_PROP_FPS, 25)  # 25 FPS for high quality single camera
            
            # For RTSP streams, reduce buffering
            if 'rtsp' in self.camera.camera_type or self.camera.rtsp_url:
                self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
            
            # Check if opened
            if not self.capture.isOpened():
                logger.warning("Failed to open stream for %s", self.camera.name)
                return False
            
            # Try to read a test frame with timeout
            ret, frame = self.capture.read()
            if ret and frame is not None:
                self.reconnect_attempts = 0
                self.last_frame_time = time.time()
                self.camera.mark_online()
                logger.info("Successfully connected to %s", self.camera.name)
                return True
            
            logger.warning("Failed to read test frame from %s", self.camera.name)
            return False
            
        except Exception as e:
            logger.exception("Error connecting to camera %s: %s", self.camera.name, e)
            self.camera.mark_offline(str(e))
            return False
    
    def _update_frame(self):
        """
        Continuously update frames from the camera (runs in separate thread)
        Handles automatic reconnection on failure
        """
        while self.is_running:
            # Connect if not connected
            if not self.capture or not self.capture.isOpened():
                if self.reconnect_attempts < self.max_reconnect_attempts:
                    if self._connect():
                        continue
                    else:
                        self.reconnect_attempts += 1
                        logger.warning(
                            "Connection failed. Retry %s/%s",
                            self.reconnect_attempts,
                            self.max_reconnect_attempts,
                        )
                        time.sleep(self.reconnect_delay)
                        continue
                else:
                    logger.error("Max reconnection attempts reached for %s", self.camera.name)
                    self.camera.mark_offline("Max reconnection attempts reached")
                    time.sleep(30)  # Wait 30 seconds before resetting attempts
                    self.reconnect_attempts = 0
                    continue
            
            # Read frame from camera
            try:
                # Frame skipping to reduce CPU load with multiple cameras
                self.frame_counter += 1
                if self.frame_counter % self.frame_skip != 0:
                    self.capture.grab()  # Grab and discard frame
                    time.sleep(0.05)  # Small delay
                    continue
                
                # For real-time streaming: grab only 1 frame to clear buffer
                self.capture.grab()
                
                # Decode the latest frame
                ret, frame = self.capture.retrieve()
                
                if ret and frame is not None:
                    # Downscale large frames to reduce memory pressure
                    height, width = frame.shape[:2]
                    max_width = 1280
                    if width > max_width:
                        scale = max_width / float(width)
                        frame = cv2.resize(frame, (max_width, int(height * scale)))

                    # Update frame with thread lock
                    with self.lock:
                        self.frame = frame
                        self.last_frame_time = time.time()
                    
                    # Mark camera as online
                    if self.camera.status != 'active':
                        self.camera.mark_online()
                else:
                    # Check if we've timed out
                    if time.time() - self.last_frame_time > self.frame_timeout:
                        logger.warning("Frame timeout for %s", self.camera.name)
                        if self.capture:
                            self.capture.release()
                            self.capture = None
                        self.camera.mark_offline("Frame timeout")
                    
            except Exception as e:
                logger.exception("Error reading frame from %s: %s", self.camera.name, e)
                if self.capture:
                    self.capture.release()
                    self.capture = None
                time.sleep(1)
            
            # Minimal delay for real-time performance - optimized for single camera
            time.sleep(0.04)  # ~25 FPS max, smooth video for single camera
    
    def get_frame(self):
        """
        Get the latest frame from the camera
        
        Returns:
            numpy.ndarray or None: Current frame or None if unavailable
        """
        with self.lock:
            if self.frame is None:
                return None

            try:
                return self.frame.copy()
            except Exception as e:
                logger.exception("Error copying frame for %s: %s", self.camera.name, e)
                return None
    
    def get_jpeg_frame(self, quality=85):
        """
        Get the latest frame encoded as JPEG
        
        Args:
            quality: JPEG compression quality (0-100)
            Higher quality = better image, optimized for single camera
            
        Returns:
            bytes or None: JPEG encoded frame or None if unavailable
        """
        frame = self.get_frame()
        if frame is not None:
            try:
                # Resize to HD quality for single camera (better quality)
                height, width = frame.shape[:2]
                if width > 1280:
                    # Limit to 1280px for HD quality without excessive bandwidth
                    frame = cv2.resize(frame, (1280, int(height * 1280 / width)))
                elif width < 640:
                    # Upscale if too small
                    frame = cv2.resize(frame, (640, int(height * 640 / width)))
                
                # Encode frame as JPEG with optimized settings for streaming
                encode_param = [
                    int(cv2.IMWRITE_JPEG_QUALITY), quality,
                    int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,  # Optimize encoding
                    int(cv2.IMWRITE_JPEG_PROGRESSIVE), 0  # Disable progressive for speed
                ]
                ret, buffer = cv2.imencode('.jpg', frame, encode_param)
                if ret:
                    return buffer.tobytes()
            except Exception as e:
                logger.exception("Error encoding frame for %s: %s", self.camera.name, e)
                return None
        return None


class CameraStreamManager:
    """
    Manages multiple camera streams globally
    """
    
    def __init__(self):
        self.streams = {}
        self.lock = threading.Lock()
        self.startup_delay = 0  # No delay needed for single camera system
    
    def get_stream(self, camera_id):
        """
        Get or create a camera stream
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            CameraStream or None: Stream instance or None if camera not found
        """
        from .goat_models import IPCamera
        
        with self.lock:
            # Return existing stream if available
            if camera_id in self.streams:
                return self.streams[camera_id]
            
            # Create new stream
            try:
                camera = IPCamera.objects.get(id=camera_id, is_active=True)
                
                # Add delay between camera starts to prevent system overload
                if len(self.streams) > 0:
                    time.sleep(self.startup_delay)
                
                stream = CameraStream(camera)
                stream.start()
                self.streams[camera_id] = stream
                return stream
            except IPCamera.DoesNotExist:
                logger.warning("Camera with ID %s not found", camera_id)
                return None
            except Exception as e:
                logger.exception("Error creating stream for camera %s: %s", camera_id, e)
                return None
    
    def stop_stream(self, camera_id):
        """Stop a specific camera stream"""
        with self.lock:
            if camera_id in self.streams:
                self.streams[camera_id].stop()
                del self.streams[camera_id]
                return True
        return False
    
    def stop_all_streams(self):
        """Stop all camera streams"""
        with self.lock:
            for stream in self.streams.values():
                stream.stop()
            self.streams.clear()


# Global camera stream manager instance
camera_manager = CameraStreamManager()
