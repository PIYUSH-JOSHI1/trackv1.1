from flask import Flask, render_template, Response, jsonify, request
from flask_cors import CORS
import cv2
import numpy as np
from ultralytics import YOLO
import cvzone
import math
from sort import *
import threading
import queue
import time
import os
import tempfile
import requests
from werkzeug.utils import secure_filename
from intelligent_traffic_optimizer import IntelligentTrafficOptimizer, VehicleData, LaneMetrics, SignalPhase
import subprocess
import urllib.parse

# Load environment variables from .env file (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, using system env vars

# Import Supabase routes
try:
    from supabase_routes import register_supabase_routes
    SUPABASE_ROUTES_AVAILABLE = True
except ImportError:
    SUPABASE_ROUTES_AVAILABLE = False
    print("Warning: Supabase routes not available")


app = Flask(__name__)
CORS(app, resources={
    r"/video_feed/*": {"origins": "*", "methods": ["GET", "HEAD", "OPTIONS"]},
    r"/get_data/*": {"origins": "*"},
    r"/api/*": {"origins": "*"},
    r"/*": {"origins": "*"}
})  # Enable CORS with specific headers for video streaming

# Register Supabase API routes
if SUPABASE_ROUTES_AVAILABLE:
    register_supabase_routes(app)

# Upload folder configuration
UPLOAD_FOLDER = 'uploaded_videos'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Video quality settings
VIDEO_QUALITY = {
    'resolution': (480, 360),  # Width x Height - 480p for bandwidth efficiency
    'jpeg_quality': 70,  # 0-100, lower = smaller file
    'fps_limit': 15  # Limit FPS to reduce bandwidth
}

# Initialize queues for frame and data storage (4 feeds)
frame_queues = [queue.Queue(maxsize=2) for _ in range(4)]
data_queues = [queue.Queue(maxsize=5) for _ in range(4)]

# Global optimizer instance (shared across all detectors for phase management)
global_optimizer = None

class VehicleDetector:
    def __init__(self):
        try:
            print("Loading YOLO model...")
            self.model = YOLO("yolov8n.pt")  # Use smaller model for faster processing
            self.tracker = Sort(max_age=10, min_hits=1, iou_threshold=0.1)
            self.total_count = []
            
            # Initialize intelligent optimizer (will be overridden by global optimizer)
            self.optimizer = IntelligentTrafficOptimizer()
            print("VehicleDetector initialized successfully")
        except Exception as e:
            print(f"Error initializing VehicleDetector: {e}")
            # Create minimal fallback
            self.model = None
            self.tracker = None
            self.total_count = []
            self.optimizer = None
        
        self.vehicles_data = []  # Store enhanced vehicle data
        self.bottleneck_strategies = {}
        self.lane_id = 0  # Will be set per detector instance
        
        # Traffic engineering standards
        self.MAX_SIGNAL_TIME = 120
        self.MIN_SIGNAL_TIME = 7
        self.YELLOW_TIME = 3
        self.ALL_RED_TIME = 2
        
        # Real-world vehicle classification
        self.class_names = ["person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck"]
        self.target_classes = ["car", "truck", "bus", "motorbike", "bicycle"]
        
        # Vehicle type mapping for optimization
        self.vehicle_type_map = {
            "car": "car",
            "truck": "truck", 
            "bus": "bus",
            "motorbike": "bike",
            "bicycle": "bike"
        }

        # Detection lines (will be initialized with frame dimensions)
        self.limit_lines = None
        self.vehicle_counts_history = []
        self.frame_analyzed = False
        self.frame_height = None
        self.frame_width = None
        
        # Signal timing tracking
        self.cycle_start_time = time.time()
        self.frame_count = 0
        self.fps = 15  # Expected FPS for timing calculations
        self.observation_start_time = None  # Track observation phase start
        self.observation_elapsed = 0  # Track observation time per lane
        
        # Performance tracking
        self.last_optimization_time = time.time()
        self.optimization_interval = 5  # Optimize every 5 seconds

    def analyze_video_frame(self, frame):
        """Analyze video frame dimensions and initialize detection lines"""
        if self.frame_analyzed:
            return  # Already analyzed
        
        self.frame_height, self.frame_width = frame.shape[:2]
        print(f"[Lane {self.lane_id}] Video analyzed - Resolution: {self.frame_width}x{self.frame_height}")
        
        # Initialize detection lines based on actual frame dimensions
        # Position lines at 60% height with proper margins
        y1 = int(self.frame_height * 0.60)  # Main detection line at 60% height
        y2 = int(self.frame_height * 0.65)  # Secondary line at 65% height
        
        # Horizontal span: 20% from left to 80% from left (60% of frame width centered)
        x_start = int(self.frame_width * 0.20)
        x_end = int(self.frame_width * 0.80)
        
        # Create detection lines with calculated positions
        self.limit_lines = [
            [x_start, y1, x_end, y1],  # Main horizontal line
            [x_start, y2, x_end, y2]   # Secondary horizontal line
        ]
        
        self.frame_analyzed = True
        print(f"[Lane {self.lane_id}] Detection lines marked:")
        print(f"  Line 1: ({x_start}, {y1}) to ({x_end}, {y1})")
        print(f"  Line 2: ({x_start}, {y2}) to ({x_end}, {y2})")

    def initialize_lines(self, frame):
        """Legacy method - calls analyze_video_frame"""
        if not self.frame_analyzed:
            self.analyze_video_frame(frame)

    def get_signal_state(self):
        """Get signal state from global optimizer based on phase logic"""
        global global_optimizer
        try:
            if global_optimizer is None:
                return "OBSERVATION"  # Fallback if optimizer not available
            
            # During observation phase, show OBSERVATION status
            if global_optimizer.observation_enabled:
                return "OBSERVATION"
            
            return global_optimizer.get_signal_state(self.lane_id)
        except Exception as e:
            print(f"Error getting signal state: {e}")
            return "OBSERVATION"  # Safe fallback
    
    def get_green_time(self):
        """Get remaining green time from global optimizer"""
        global global_optimizer
        try:
            if global_optimizer is None:
                return 30
            
            return global_optimizer.get_green_time(self.lane_id)
        except Exception as e:
            print(f"Error getting green time: {e}")
            return 30  # Safe fallback

    def get_next_green_time(self):
        """Calculate when this lane will get green light if currently RED"""
        global global_optimizer
        try:
            signal_state = self.get_signal_state()
            
            if signal_state == "GREEN" or signal_state == "YELLOW":
                return 0  # Already green or about to be green
            
            if signal_state == "RED" and global_optimizer:
                # Get opposite phase lanes
                # North/South: lanes 0, 2; East/West: lanes 1, 3
                if self.lane_id in [0, 2]:
                    # This is North/South - opposite is East/West
                    opposite_lanes = [1, 3]
                else:
                    # This is East/West - opposite is North/South
                    opposite_lanes = [0, 2]
                
                # Get the max green time from opposite lanes
                max_opposite_green = 0
                for lane_id in opposite_lanes:
                    opp_green = global_optimizer.get_green_time(lane_id)
                    if opp_green > max_opposite_green:
                        max_opposite_green = opp_green
                
                # Add yellow and all-red times
                next_green = max_opposite_green + self.YELLOW_TIME + self.ALL_RED_TIME
                return max(0, next_green)
            
            return 0
        except Exception as e:
            print(f"Error calculating next green time: {e}")
            return 0

    def calculate_lane_metrics(self, vehicle_count, vehicle_types=None):
        """Calculate lane metrics for this detector's lane"""
        
        if not vehicle_types:
            vehicle_types = ['car'] * vehicle_count
        
        # Create vehicle data for optimization
        vehicles = []
        for i, v_type in enumerate(vehicle_types[:vehicle_count]):
            vehicle = VehicleData(
                vehicle_id=i,
                vehicle_type=self.vehicle_type_map.get(v_type, 'car'),
                lane_id=self.lane_id,
                timestamp=time.time()
            )
            vehicles.append(vehicle)
        
        # Analyze lane conditions using the optimizer
        lane_metrics = self.optimizer.analyze_lane_conditions(vehicles)
        
        return lane_metrics

    def process_frame(self, frame):
        # Analyze video frame first (on first frame)
        if not self.frame_analyzed:
            self.analyze_video_frame(frame)
            if global_optimizer and self.observation_start_time is None:
                self.observation_start_time = time.time()
                self.cycle_start_time = time.time()  # Reset cycle timer
                self.frame_count = 0
                print(f"[Lane {self.lane_id}] Starting 30-second observation phase...")
        
        # Initialize lines if needed (legacy support)
        if self.limit_lines is None:
            self.initialize_lines(frame)
        
        # OBSERVATION PHASE: Track vehicle counts for first 30 seconds
        if global_optimizer and global_optimizer.observation_enabled and self.observation_start_time:
            self.observation_elapsed = time.time() - self.observation_start_time
            global_optimizer.update_observation_time(self.lane_id, self.observation_elapsed)
        elif global_optimizer and not global_optimizer.observation_enabled and self.observation_start_time:
            # Transition from observation to signal control
            # Only happens once per lane
            if self.lane_id == 0:  # Log once
                print(f"[Lane {self.lane_id}] Observation complete! Starting signal control...")
            # Reset timing for actual signal cycles
            self.cycle_start_time = time.time()
            self.frame_count = 0
            self.observation_start_time = None  # Mark transition as complete
        
        # Track elapsed time for signal control
        self.frame_count += 1
        elapsed_time = (self.frame_count / self.fps)
        
        # Update global optimizer with elapsed time for this lane
        if global_optimizer:
            global_optimizer.update_phase_elapsed_time(self.lane_id, elapsed_time)
            
            # Check if cycle should reset (after all phases complete)
            total_cycle_time = sum(global_optimizer.current_cycle_timings) + (self.YELLOW_TIME * 4)
            if elapsed_time >= total_cycle_time:
                # Cycle complete - prepare next cycle with predicted timings
                predicted_timings = global_optimizer.predict_next_cycle_timings({
                    0: len(self.total_count) // 30,  # Rough estimate based on cumulative count
                    1: len(self.total_count) // 30,
                    2: len(self.total_count) // 30,
                    3: len(self.total_count) // 30
                })
                # Only update once per feed (coordinator pattern)
                if self.lane_id == 0:
                    global_optimizer.set_cycle_timing(predicted_timings)
                self.cycle_start_time = time.time()
                self.frame_count = 0

        results = self.model(frame, stream=True)
        detections = np.empty((0, 5))

        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0]
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                conf = math.ceil((box.conf[0] * 100)) / 100
                cls = int(box.cls[0])
                
                # Safeguard against invalid class indices
                if cls < 0 or cls >= len(self.class_names):
                    continue
                
                current_class = self.class_names[cls]

                if current_class in self.target_classes and conf > 0.3:
                    current_array = np.array([x1, y1, x2, y2, conf])
                    detections = np.vstack((detections, current_array))

        tracked_objects = self.tracker.update(detections)
        
        # Count vehicles and record during observation phase
        vehicle_count = len(tracked_objects)
        if global_optimizer and global_optimizer.observation_enabled:
            global_optimizer.record_observation_vehicle_count(self.lane_id, vehicle_count)

        # Draw detection lines with proper styling
        for limit in self.limit_lines:
            # Primary line in teal color
            cv2.line(frame, (limit[0], limit[1]), (limit[2], limit[3]),
                     (250, 182, 122), 2)  # Orange: (B, G, R) = (122, 182, 250)
            # Add line markers at ends
            cv2.circle(frame, (limit[0], limit[1]), 4, (0, 255, 0), -1)
            cv2.circle(frame, (limit[2], limit[3]), 4, (0, 255, 0), -1)

        for result in tracked_objects:
            x1, y1, x2, y2, id = result
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            w, h = x2 - x1, y2 - y1

            cvzone.cornerRect(frame, (x1, y1, w, h), l=5, rt=1,
                              colorR=(111, 237, 235))
            cvzone.putTextRect(frame, f'#{int(id)}', (max(0, x1), max(25, y1)),
                               scale=0.8, thickness=1, offset=5,
                               colorR=(200, 200, 200), colorT=(0, 0, 0))

            cx, cy = x1 + w // 2, y1 + h // 2
            cv2.circle(frame, (cx, cy), 5, (22, 192, 240), cv2.FILLED)

            for limit in self.limit_lines:
                if (limit[0] < cx < limit[2] and
                        limit[1] - 15 < cy < limit[1] + 15 and
                        id not in self.total_count):
                    self.total_count.append(id)
                    cv2.line(frame, (limit[0], limit[1]), (limit[2], limit[3]),
                             (12, 202, 245), 3)

        # Get signal state from global phase-based optimizer
        signal_state = self.get_signal_state()
        green_time = self.get_green_time()

        # Display signal state and other information
        if signal_state == "OBSERVATION":
            signal_color = (0, 165, 255)  # Orange for observation/analysis
        else:
            signal_color = (0, 255, 0) if signal_state == "GREEN" else (0, 255, 255) if signal_state == "YELLOW" else (0, 0, 255)
        
        cv2.rectangle(frame, (20, 20), (200, 100), signal_color, -1)
        cvzone.putTextRect(frame, f'Signal: {signal_state}', (30, 40),
                           scale=1, thickness=2, offset=5,
                           colorR=signal_color, colorT=(0, 0, 0))
        cvzone.putTextRect(frame, f'Count: {len(self.total_count)}', (30, 70),
                           scale=1, thickness=2, offset=5,
                           colorR=signal_color, colorT=(0, 0, 0))
        
        if signal_state == "GREEN":
            cvzone.putTextRect(frame, f'Green Time: {green_time:.1f}s', (30, 100),
                               scale=1, thickness=2, offset=5,
                               colorR=signal_color, colorT=(0, 0, 0))
        elif signal_state == "OBSERVATION":
            if global_optimizer and self.observation_elapsed:
                obs_time = f'{self.observation_elapsed:.1f}s'
            else:
                obs_time = '0s'
            cvzone.putTextRect(frame, f'Analyzing: {obs_time}', (30, 100),
                               scale=1, thickness=2, offset=5,
                               colorR=signal_color, colorT=(0, 0, 0))

        return frame, len(self.total_count), green_time, signal_state

# Create detector instances for each feed (lazy initialization)
detectors = [None for _ in range(4)]

def get_detector(feed_id):
    """Lazy initialization of detector for specific feed"""
    global detectors, global_optimizer
    if detectors[feed_id] is None:
        print(f"Initializing detector for feed {feed_id}...")
        detector = VehicleDetector()
        detector.lane_id = feed_id  # Set lane ID for phase-based signal management
        detector.optimizer = global_optimizer  # Use shared optimizer
        detectors[feed_id] = detector
    return detectors[feed_id]

def initialize_global_optimizer():
    """Initialize the global optimizer for 4-way junction phase management"""
    global global_optimizer
    if global_optimizer is None:
        print("Initializing global phase-based optimizer...")
        global_optimizer = IntelligentTrafficOptimizer()
    return global_optimizer

# Global variables for video sources
current_video_sources = [None, None, None, None]
last_frame_time = [0] * 4  # Track frame timing for FPS limiting

def compress_frame(frame, target_resolution=None, jpeg_quality=70):
    """
    Compress frame for efficient streaming
    
    Args:
        frame: OpenCV frame
        target_resolution: (width, height) tuple, defaults to VIDEO_QUALITY
        jpeg_quality: JPEG quality 0-100
    
    Returns:
        JPEG bytes
    """
    if target_resolution is None:
        target_resolution = VIDEO_QUALITY['resolution']
    
    # Resize frame
    height, width = frame.shape[:2]
    if (width, height) != target_resolution:
        frame = cv2.resize(frame, target_resolution, interpolation=cv2.INTER_LINEAR)
    
    # Encode to JPEG
    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    if ret:
        return buffer.tobytes()
    return None

def should_process_frame(feed_id, fps_limit=None):
    """Check if enough time has passed to process next frame"""
    if fps_limit is None:
        fps_limit = VIDEO_QUALITY['fps_limit']
    
    current_time = time.time()
    min_interval = 1.0 / fps_limit
    
    if current_time - last_frame_time[feed_id] >= min_interval:
        last_frame_time[feed_id] = current_time
        return True
    return False

def video_processing_thread(feed_id):
    global current_video_sources
    
    while True:
        cap = None
        
        try:
            # Map feed IDs to specific video files
            video_files = {
                0: "track-v-frontend-main/video/cam1.mp4",
                1: "track-v-frontend-main/video/cam2.mp4",
                2: "track-v-frontend-main/video/cam3.mp4",
                3: "track-v-frontend-main/video/cam4.mp4"
            }
            
            # Try loading the mapped video file
            if feed_id in video_files:
                video_path = video_files[feed_id]
                try:
                    cap = cv2.VideoCapture(video_path)
                    if not cap.isOpened():
                        print(f"Could not open video at {video_path}, trying fallback...")
                        cap = None
                    else:
                        print(f"Loaded {video_path.split('/')[-1]} for feed {feed_id}")
                except Exception as e:
                    print(f"Error loading video for feed {feed_id}: {e}")
                    cap = None
            
            # Try YouTube or uploaded video if source is set
            elif current_video_sources[feed_id]:
                source = current_video_sources[feed_id]
                
                # Check if it's a YouTube URL
                if 'youtube.com' in source or 'youtu.be' in source:
                    try:
                        cap = YouTubeVideoHandler.get_video_stream(source)
                        if cap and cap.isOpened():
                            print(f"Loaded YouTube video for feed {feed_id}: {source}")
                        else:
                            cap = None
                    except Exception as e:
                        print(f"Error loading YouTube video for feed {feed_id}: {e}")
                        cap = None
                else:
                    # Try as file path
                    try:
                        cap = VideoUploadHandler.get_video_stream(source)
                        if cap and cap.isOpened():
                            print(f"Loaded video file for feed {feed_id}: {source}")
                        else:
                            cap = None
                    except Exception as e:
                        print(f"Error loading video file for feed {feed_id}: {e}")
                        cap = None
            
            # Fallback to camera or demo
            if cap is None or not cap.isOpened():
                try:
                    # Try to use webcam
                    cap = cv2.VideoCapture(feed_id if feed_id < 4 else 0)
                    if cap.isOpened():
                        print(f"Using camera for feed {feed_id}")
                except Exception as e:
                    print(f"Could not open camera for feed {feed_id}: {e}")
                    cap = None
            
            # If no camera available, generate demo frames
            if cap is None or not cap.isOpened():
                print(f"Generating demo frames for feed {feed_id}")
                frame_count = 0
                while True:
                    # Create animated dummy frame
                    dummy_frame = np.zeros((360, 480, 3), dtype=np.uint8)
                    
                    # Create some basic animation
                    time_text = f"Demo Feed {feed_id+1}"
                    frame_text = f"Frame: {frame_count}"
                    status_text = "LIVE DEMO"
                    
                    cv2.putText(dummy_frame, time_text, (120, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.putText(dummy_frame, frame_text, (150, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(dummy_frame, status_text, (150, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    
                    # Add some simple animation (moving rectangle)
                    x_pos = int((frame_count % 100) * 4.8)
                    cv2.rectangle(dummy_frame, (x_pos, 300), (x_pos + 30, 320), (255, 0, 0), -1)
                    
                    frame_bytes = compress_frame(dummy_frame)
                    if frame_bytes:
                        try:
                            frame_queues[feed_id].put(frame_bytes, block=False)
                        except queue.Full:
                            try:
                                frame_queues[feed_id].get_nowait()
                                frame_queues[feed_id].put(frame_bytes, block=False)
                            except queue.Empty:
                                pass
                    
                    frame_count += 1
                    time.sleep(0.1)  # 10 FPS for demo
                    
                    # Simple break condition
                    if frame_count > 1000000:
                        frame_count = 0
            
            # Set buffer size to prevent lag
            if cap:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            while True:
                if cap is None or not cap.isOpened():
                    break
                    
                success, frame = cap.read()
                if not success:
                    if hasattr(cap, 'set'):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Loop video
                    break

                # Limit FPS to reduce bandwidth
                if not should_process_frame(feed_id):
                    continue

                # Resize and compress for transmission
                frame = cv2.resize(frame, VIDEO_QUALITY['resolution'], interpolation=cv2.INTER_LINEAR)
                
                try:
                    detector = get_detector(feed_id)
                    processed_frame, count, green_time, signal_state = detector.process_frame(frame)
                except IndexError as e:
                    import traceback
                    print(f"IndexError in detector for feed {feed_id}: {e}")
                    traceback.print_exc()
                    # Use unprocessed frame as fallback
                    processed_frame = frame
                    count = 0
                    green_time = 30
                    signal_state = "GREEN"
                except Exception as e:
                    print(f"Error processing frame in detector for feed {feed_id}: {e}")
                    # Use unprocessed frame as fallback
                    processed_frame = frame
                    count = 0
                    green_time = 30
                    signal_state = "GREEN"
                
                # Update global optimizer phases to rotate traffic signals properly
                try:
                    global_optimizer.update_phase({})
                except Exception as e:
                    pass  # Silent fail for phase update

                data = {
                    "count": count,
                    "green_time": green_time,
                    "signal_state": signal_state
                }

                try:
                    data_queues[feed_id].put(data, block=False)
                except queue.Full:
                    try:
                        data_queues[feed_id].get_nowait()
                        data_queues[feed_id].put(data, block=False)
                    except queue.Empty:
                        pass

                # Compress frame for streaming
                frame_bytes = compress_frame(processed_frame, jpeg_quality=VIDEO_QUALITY['jpeg_quality'])
                if frame_bytes:
                    try:
                        frame_queues[feed_id].put(frame_bytes, block=False)
                    except queue.Full:
                        try:
                            frame_queues[feed_id].get_nowait()
                            frame_queues[feed_id].put(frame_bytes, block=False)
                        except queue.Empty:
                            pass
        
        except Exception as e:
            print(f"Error in video processing thread {feed_id}: {e}")
            time.sleep(1)
            continue
        finally:
            if cap:
                cap.release()

@app.route('/')
def index():
    """Root endpoint for quick health check"""
    try:
        return jsonify({
            "message": "Traffic Monitor Backend API", 
            "status": "running",
            "port": os.environ.get("PORT", 5000),
            "threads_active": threading.active_count(),
            "environment": "production" if os.environ.get("RENDER") else "development"
        })
    except Exception as e:
        return jsonify({
            "message": "Traffic Monitor Backend API",
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/health')
def health_check():
    """Detailed health check with thread and queue status"""
    queue_sizes = [frame_queues[i].qsize() for i in range(4)]
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "threads_active": threading.active_count(),
        "frame_queue_sizes": queue_sizes,
        "detectors_initialized": [detectors[i] is not None for i in range(4)],
        "upload_folder": UPLOAD_FOLDER,
        "max_file_size": "500MB"
    })

def generate_frames(feed_id):
    while True:
        try:
            # Use timeout to prevent indefinite blocking
            frame_bytes = frame_queues[feed_id].get(timeout=5)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except queue.Empty:
            # Timeout occurred - stream has stalled
            # Send a dummy frame or break to let client reconnect
            print(f"Feed {feed_id} timeout: no frames in queue for 5 seconds")
            break

@app.route('/video_feed/<int:feed_id>')
def video_feed(feed_id):
    if 0 <= feed_id < 4:
        return Response(generate_frames(feed_id),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    return "Invalid feed ID", 404

@app.route('/get_data/<int:feed_id>')
def get_data(feed_id):
    """Get real-time traffic data for a specific lane"""
    if 0 <= feed_id < 4:
        try:
            # Initialize global optimizer if needed
            initialize_global_optimizer()
            
            data = data_queues[feed_id].get_nowait()
            
            # Get detector for next green time calculation
            detector = get_detector(feed_id)
            next_green_time = detector.get_next_green_time()
            
            # Check observation phase status
            observation_status = None
            if global_optimizer:
                if global_optimizer.observation_enabled:
                    obs_info = global_optimizer.get_observation_status()
                    lane_obs = obs_info.get(f'lane_{feed_id}', {})
                    observation_status = {
                        'in_progress': not lane_obs.get('ready', False),
                        'time_elapsed': lane_obs.get('time', 0),
                        'max_vehicles': lane_obs.get('max_vehicles', 0)
                    }
                    # During observation, show vehicles but not final signal control yet
                    data['signal_state'] = 'OBSERVATION'
                    data['green_time'] = 0
                    next_green_time = 0
                else:
                    # Check if observation just completed
                    if feed_id == 0:  # Only log once
                        pass
            
            # Add phase information from global optimizer
            lane_phase = "NORTH_SOUTH" if feed_id in [0, 2] else "EAST_WEST"
            
            response_data = {
                **data,
                "lane_id": feed_id,
                "lane_name": ["North", "East", "South", "West"][feed_id],
                "current_phase": lane_phase,
                "next_green_time": next_green_time,
                "observation": observation_status,
                "phase_info": "Analyzing traffic..." if data["signal_state"] == "OBSERVATION" else ("Opposite lanes GREEN" if data["signal_state"] == "RED" else "This lane GREEN")
            }
            
            return jsonify(response_data)
        except queue.Empty:
            # Return default observation status during initial period
            return jsonify({
                "count": 0, 
                "green_time": 0, 
                "signal_state": "OBSERVATION",
                "lane_id": feed_id,
                "lane_name": ["North", "East", "South", "West"][feed_id],
                "next_green_time": 0,
                "observation": {"in_progress": True, "time_elapsed": 0, "max_vehicles": 0},
                "phase_info": "Analyzing traffic..."
            })
    return jsonify({"error": "Invalid feed ID"}), 404

@app.route('/set_video_source', methods=['POST'])
def set_video_source():
    global current_video_sources
    
    data = request.get_json()
    sources = data.get('sources', [])
    
    current_video_sources = sources + [None] * (4 - len(sources))
    
    return jsonify({"message": "Video sources updated", "sources": current_video_sources})

@app.route('/set_youtube_feed', methods=['POST'])
def set_youtube_feed():
    """Set a YouTube video URL for a specific feed"""
    global current_video_sources
    
    data = request.get_json()
    feed_id = data.get('feed_id', 0)
    youtube_url = data.get('url', '')
    
    if not youtube_url:
        return jsonify({"error": "YouTube URL required"}), 400
    
    if not (0 <= feed_id < 4):
        return jsonify({"error": "Invalid feed ID"}), 400
    
    try:
        # Validate it's a YouTube URL
        if 'youtube.com' not in youtube_url and 'youtu.be' not in youtube_url:
            return jsonify({"error": "Invalid YouTube URL"}), 400
        
        current_video_sources[feed_id] = youtube_url
        
        return jsonify({
            "message": f"YouTube video set for feed {feed_id}",
            "feed_id": feed_id,
            "url": youtube_url,
            "status": "active"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload_video', methods=['POST'])
def upload_video():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    feed_id = request.form.get('feed_id', '0')
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    try:
        feed_id = int(feed_id)
        if not (0 <= feed_id < 4):
            return jsonify({"error": "Invalid feed ID"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid feed ID"}), 400
    
    if file and allowed_file(file.filename):
        # Save the uploaded file
        file_path = VideoUploadHandler.save_uploaded_file(file)
        
        if file_path:
            # Update video source
            global current_video_sources
            current_video_sources[feed_id] = file_path
            
            return jsonify({
                "message": "Video uploaded successfully",
                "feed_id": feed_id,
                "file_path": file_path,
                "status": "active"
            })
        else:
            return jsonify({"error": "Failed to save file"}), 500
    else:
        return jsonify({"error": f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

@app.route('/get_all_signal_states')
def get_all_signal_states():
    """Get signal state for all 4 lanes (4-way junction phase control)"""
    global global_optimizer
    
    # Initialize optimizer if needed
    initialize_global_optimizer()
    
    # Collect lane metrics from all detectors
    lane_metrics_dict = {}
    for lane_id in range(4):
        detector = get_detector(lane_id)
        try:
            data = data_queues[lane_id].get_nowait()
        except queue.Empty:
            data = {"count": 0, "green_time": 30, "signal_state": "GREEN"}
        
        # Create lane metrics (simplified for phase management)
        lane_metrics_dict[lane_id] = LaneMetrics(
            vehicle_count=data.get("count", 0),
            queue_length=data.get("count", 0) * 5,  # Assume 5m per vehicle
            average_speed=0,
            saturation_level=min(data.get("count", 0) / 30.0, 1.0),
            discharge_rate=2.1,
            arrival_rate=0,
            wait_time_avg=0,
            bottleneck_severity=0
        )
    
    # Get all signal states from global optimizer
    signal_states = global_optimizer.get_all_signal_states(lane_metrics_dict)
    
    # Format response with lane information
    response = {
        "timestamp": time.time(),
        "current_phase": "NORTH_SOUTH" if global_optimizer.current_phase == "NORTH_SOUTH" else "EAST_WEST",
        "lanes": {}
    }
    
    for lane_id in range(4):
        lane_names = ["North", "East", "South", "West"]
        response["lanes"][lane_id] = {
            "lane_name": lane_names[lane_id],
            "signal_state": signal_states[lane_id]["state"],
            "remaining_green_time": signal_states[lane_id]["duration"],
            "phase": signal_states[lane_id]["phase"],
            "vehicle_count": lane_metrics_dict[lane_id].vehicle_count
        }
    
    return jsonify(response)

@app.route('/get_bottleneck_analysis/<int:feed_id>')
def get_bottleneck_analysis(feed_id):
    """Get detailed bottleneck analysis for a specific feed"""
    if 0 <= feed_id < 4:
        detector = detectors[feed_id]
        
        # Get current bottleneck strategies
        strategies = detector.bottleneck_strategies.copy()
        
        # Analyze current traffic conditions
        vehicle_types = [v.vehicle_type for v in detector.vehicles_data[-20:]]  # Last 20 vehicles
        
        analysis = {
            "feed_id": feed_id,
            "current_strategies": strategies,
            "traffic_intensity": len(detector.total_count),
            "signal_optimization": {
                "current_green_time": detector.current_green_time,
                "signal_state": detector.signal_state,
                "vehicles_in_queue": len(detector.vehicles_data),
                "optimization_active": bool(strategies)
            },
            "bottleneck_alerts": []
        }
        
        # Generate bottleneck alerts
        if len(detector.total_count) > 20:
            analysis["bottleneck_alerts"].append({
                "type": "HIGH_CONGESTION",
                "severity": "HIGH",
                "message": f"High vehicle density detected: {len(detector.total_count)} vehicles"
            })
        
        if detector.signal_state == "RED" and (time.time() - detector.signal_start_time) > 60:
            analysis["bottleneck_alerts"].append({
                "type": "LONG_RED_CYCLE", 
                "severity": "MEDIUM",
                "message": "Extended red light may cause spillback"
            })
        
        return jsonify(analysis)
    
    return jsonify({"error": "Invalid feed ID"}), 404

@app.route('/optimize_signal/<int:feed_id>', methods=['POST'])
def optimize_signal(feed_id):
    """Manually trigger signal optimization for a specific feed"""
    if 0 <= feed_id < 4:
        detector = detectors[feed_id]
        
        # Force optimization
        vehicle_types = [v.vehicle_type for v in detector.vehicles_data[-15:]]
        new_green_time = detector.calculate_green_time(len(detector.total_count), vehicle_types)
        
        # Apply optimization
        detector.current_green_time = new_green_time
        detector.signal_start_time = time.time()
        
        return jsonify({
            "message": f"Signal optimized for feed {feed_id}",
            "new_green_time": new_green_time,
            "vehicles_detected": len(detector.total_count),
            "optimization_applied": True
        })
    
    return jsonify({"error": "Invalid feed ID"}), 404

# ==== NEW API ENDPOINTS FOR FRONTEND ====

@app.route('/api/health')
def api_health():
    """Health check for frontend"""
    return jsonify({"status": "ok", "message": "Backend is running"}), 200

@app.route('/api/video/start', methods=['POST'])
def api_start_video():
    """Start video processing"""
    return jsonify({"status": "started", "message": "Video processing started"}), 200

@app.route('/api/video/stop', methods=['POST'])
def api_stop_video():
    """Stop video processing"""
    return jsonify({"status": "stopped", "message": "Video processing stopped"}), 200

@app.route('/api/video/frame')
def api_video_frame():
    """Get single frame from feed 0 (CAM1) as base64 JPEG"""
    try:
        frame_bytes = frame_queues[0].get_nowait()
        import base64
        frame_b64 = base64.b64encode(frame_bytes).decode('utf-8')
        return jsonify({"frame": frame_b64, "status": "ok"}), 200
    except queue.Empty:
        # Return a dummy frame if queue is empty
        dummy = np.zeros((360, 480, 3), dtype=np.uint8)
        ret, buf = cv2.imencode('.jpg', dummy)
        import base64
        b64 = base64.b64encode(buf.tobytes()).decode('utf-8')
        return jsonify({"frame": b64, "status": "ok"}), 200

@app.route('/api/traffic/data')
def api_traffic_data():
    """Get traffic data for feed 0 (CAM1)"""
    try:
        data = data_queues[0].get_nowait()
        return jsonify({
            "vehicle_counts": [data.get("count", 0), 0, 0, 0],
            "signal_state": data.get("signal_state", "GREEN"),
            "green_time": data.get("green_time", 30),
            "status": "ok"
        }), 200
    except queue.Empty:
        return jsonify({
            "vehicle_counts": [0, 0, 0, 0],
            "signal_state": "GREEN",
            "green_time": 30,
            "status": "ok"
        }), 200

# Simple Video Handler Classes
class YouTubeVideoHandler:
    """Handle YouTube video streaming"""
    
    @staticmethod
    def get_video_stream(youtube_url, resolution='480p'):
        """
        Get video stream from YouTube URL using yt-dlp
        
        Args:
            youtube_url: YouTube URL
            resolution: Desired resolution (default 480p)
            
        Returns:
            cv2.VideoCapture object or None
        """
        try:
            # Use yt-dlp to get the best format
            import yt_dlp
            
            ydl_opts = {
                'format': 'best[height<=480]/best',
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                video_url = info['url']
                
            cap = cv2.VideoCapture(video_url)
            if cap.isOpened():
                return cap
            return None
            
        except Exception as e:
            print(f"Error getting YouTube stream: {e}")
            return None


class VideoUploadHandler:
    """Handle uploaded video files"""
    
    @staticmethod
    def is_allowed_file(filename):
        """Check if file extension is allowed"""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
    @staticmethod
    def save_uploaded_file(file):
        """Save uploaded file to disk"""
        try:
            if file and VideoUploadHandler.is_allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Add timestamp to avoid conflicts
                filename = f"{int(time.time())}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                return filepath
        except Exception as e:
            print(f"Error saving file: {e}")
        return None
    
    @staticmethod
    def get_video_stream(filepath):
        """Get video stream from file"""
        try:
            if os.path.exists(filepath):
                cap = cv2.VideoCapture(filepath)
                if cap.isOpened():
                    return cap
        except Exception as e:
            print(f"Error opening video file: {e}")
        return None


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


if __name__ == '__main__':
    # Initialize global optimizer for 4-way junction phase management
    initialize_global_optimizer()
    
    # Start video processing threads for each feed AFTER Flask starts
    # This allows the health check endpoint to respond immediately
    import atexit
    
    def start_video_threads():
        """Start video threads after a short delay"""
        time.sleep(1)
        for i in range(4):
            threading.Thread(target=video_processing_thread, args=(i,), daemon=True).start()
        print("Video processing threads started")
    
    # Start threads in background after Flask boots
    threading.Thread(target=start_video_threads, daemon=True).start()

    # Render deployment configuration
    port = int(os.environ.get("PORT", 5000))
    # Force debug OFF for faster startup
    debug_mode = False  # os.environ.get("FLASK_ENV") != "production"
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode, threaded=True, use_reloader=False)

# Initialize video threads for production deployment (Render/Heroku)
def initialize_threads():
    """Initialize video processing threads for production"""
    try:
        print("Starting video processing threads...")
        # Initialize global optimizer first
        initialize_global_optimizer()
        
        for i in range(4):
            thread = threading.Thread(target=video_processing_thread, args=(i,), daemon=True)
            thread.start()
            print(f"Started thread for camera {i+1}")
        print("All video threads started successfully")
        print("4-way junction phase-based signal control ACTIVE")
    except Exception as e:
        print(f"Error starting threads: {e}")
        # Continue without threads for basic API functionality

# Start threads when module is imported (for gunicorn)
# Disabled automatic thread startup to allow faster app initialization
# Threads will start on first video request
try:
    print("Flask app module loaded successfully")
    print(f"Environment: {'production' if os.environ.get('RENDER') else 'development'}")
    print(f"Port: {os.environ.get('PORT', 5000)}")
    print("Signal Control: 4-Way Junction Phase-Based Management")
except Exception as e:
    print(f"Error in production initialization: {e}")

