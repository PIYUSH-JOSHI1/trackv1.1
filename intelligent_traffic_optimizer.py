"""
Intelligent Traffic Optimizer for 4-way Junction Phase Management
Handles traffic signal timing based on vehicle detection and lane analysis
"""

class VehicleData:
    """Data class for vehicle information"""
    def __init__(self, vehicle_id, vehicle_type, lane_id, timestamp=None):
        self.vehicle_id = vehicle_id
        self.vehicle_type = vehicle_type  # car, truck, bus, bike
        self.lane_id = lane_id
        self.timestamp = timestamp
        
    def __repr__(self):
        return f"Vehicle(id={self.vehicle_id}, type={self.vehicle_type}, lane={self.lane_id})"


class LaneMetrics:
    """Metrics for a specific lane/direction"""
    def __init__(self, lane_id, vehicle_count=0, congestion_level='low'):
        self.lane_id = lane_id
        self.vehicle_count = vehicle_count
        self.congestion_level = congestion_level  # low, medium, high, severe
        self.average_wait_time = 0
        self.vehicles = []
        
    def update_congestion(self, vehicle_count):
        self.vehicle_count = vehicle_count
        if vehicle_count < 5:
            self.congestion_level = 'low'
        elif vehicle_count < 10:
            self.congestion_level = 'medium'
        elif vehicle_count < 15:
            self.congestion_level = 'high'
        else:
            self.congestion_level = 'severe'
        return self.congestion_level
    
    def __repr__(self):
        return f"LaneMetrics(lane={self.lane_id}, count={self.vehicle_count}, level={self.congestion_level})"


class SignalPhase:
    """Traffic signal phase timing"""
    def __init__(self, phase_id, duration=30, yellow_time=3):
        self.phase_id = phase_id  # 0-3 for 4-way junction
        self.duration = duration  # Green light duration in seconds
        self.yellow_time = yellow_time  # Yellow light duration
        self.red_time = 0  # Calculated as sum of other phases
        self.is_active = False
        self.elapsed_time = 0
        
    def get_state(self, elapsed_time):
        """Get current signal state based on elapsed time"""
        if elapsed_time < self.duration:
            return 'GREEN'
        elif elapsed_time < self.duration + self.yellow_time:
            return 'YELLOW'
        else:
            return 'RED'
    
    def get_remaining_green_time(self, elapsed_time):
        """Get remaining green light time"""
        if elapsed_time < self.duration:
            return self.duration - elapsed_time
        return 0
    
    def __repr__(self):
        return f"SignalPhase(id={self.phase_id}, duration={self.duration}s, yellow={self.yellow_time}s)"


class IntelligentTrafficOptimizer:
    """
    Main traffic optimization engine for 4-way junction
    Manages phase timing based on traffic density
    """
    
    def __init__(self):
        self.num_lanes = 4
        self.lanes = {i: LaneMetrics(i) for i in range(4)}
        
        # Initial signal timings as per user configuration
        # cam1: 30s green, cam2: 22s green, cam3: red, cam4: red
        self.phases = [
            SignalPhase(0, duration=30, yellow_time=3),  # cam1: 30s
            SignalPhase(1, duration=22, yellow_time=3),  # cam2: 22s
            SignalPhase(2, duration=0, yellow_time=0),   # cam3: red (no green time)
            SignalPhase(3, duration=0, yellow_time=0)    # cam4: red (no green time)
        ]
        
        self.current_phase = 0
        self.phase_start_time = 0
        self.cycle_number = 0  # Track which cycle we're in
        self.phase_elapsed_times = [0, 0, 0, 0]  # Track elapsed time for each phase
        
        # OBSERVATION PHASE: Initial 30 second analysis per lane
        self.observation_enabled = True  # Enable observation phase
        self.observation_duration = 30  # 30 seconds per lane for initial analysis
        self.lane_observation_times = [0, 0, 0, 0]  # Track observation time for each lane
        self.observation_vehicle_counts = [0, 0, 0, 0]  # Store vehicle counts during observation
        self.lanes_ready = [False, False, False, False]  # Track which lanes completed observation
        
        # Adaptive timings for cycles after first (predicted vehicle counts)
        # Cycle 1: [30, 22, 0, 0] (user provided)
        # Cycle 2+: Dynamically calculated based on vehicle analysis
        self.adaptive_timings = [
            [30, 22, 0, 0],      # Cycle 1: Initial user-defined
            [22, 19, 24, 55],    # Cycle 2: Example predicted timings
        ]
        self.current_cycle_timings = self.adaptive_timings[0]
        
        # Traffic engineering standards
        self.min_phase_duration = 7
        self.max_phase_duration = 120
        self.yellow_time = 3
        self.all_red_time = 2
        
        # Adaptive timing
        self.base_phase_duration = 30
        self.congestion_multiplier = {
            'low': 1.0,
            'medium': 1.2,
            'high': 1.5,
            'severe': 2.0
        }
        
    def analyze_lane_conditions(self, vehicles):
        """
        Analyze lane conditions based on vehicle data
        
        Args:
            vehicles: List of VehicleData objects
            
        Returns:
            LaneMetrics for the lane
        """
        if not vehicles:
            return LaneMetrics(0, vehicle_count=0, congestion_level='low')
        
        lane_id = vehicles[0].lane_id if vehicles else 0
        lane_metrics = self.lanes.get(lane_id, LaneMetrics(lane_id))
        
        # Update vehicle count and congestion
        vehicle_count = len(vehicles)
        lane_metrics.update_congestion(vehicle_count)
        lane_metrics.vehicles = vehicles
        
        return lane_metrics
    
    def optimize_phase_timing(self, lane_metrics_dict):
        """
        Optimize signal phase timing based on lane metrics
        
        Args:
            lane_metrics_dict: Dict mapping lane_id to LaneMetrics
            
        Returns:
            Updated phase durations
        """
        for lane_id, metrics in lane_metrics_dict.items():
            if lane_id < len(self.phases):
                # Calculate adaptive duration based on congestion
                congestion_factor = self.congestion_multiplier.get(metrics.congestion_level, 1.0)
                new_duration = int(self.base_phase_duration * congestion_factor)
                
                # Enforce limits
                new_duration = max(self.min_phase_duration, min(new_duration, self.max_phase_duration))
                
                self.phases[lane_id].duration = new_duration
                self.lanes[lane_id] = metrics
        
        return [p.duration for p in self.phases]
    
    def update_phase(self, elapsed_times=None):
        """
        Update current phase and cycle through lanes
        
        Args:
            elapsed_times: Dict mapping phase_id to elapsed time (optional)
        """
        if elapsed_times and isinstance(elapsed_times, dict):
            # Update specific phases
            for phase_id, elapsed_time in elapsed_times.items():
                if phase_id < len(self.phases):
                    self.phases[phase_id].elapsed_time = elapsed_time
        
        # Simple round-robin: cycle through phases
        # In production, this would be more sophisticated
        pass
    
    def update_phase_elapsed_time(self, phase_id, elapsed_time):
        """Update elapsed time for a specific phase"""
        if phase_id < len(self.phase_elapsed_times):
            self.phase_elapsed_times[phase_id] = elapsed_time
    
    def get_signal_state(self, lane_id=0):
        """
        Get current signal state for a lane based on cycle timing
        
        Args:
            lane_id: The lane to get state for
            
        Returns:
            Signal state: 'GREEN', 'YELLOW', or 'RED'
        """
        if lane_id >= len(self.phases):
            return 'RED'
        
        # Get current cycle timing for this lane
        green_duration = self.current_cycle_timings[lane_id] if lane_id < len(self.current_cycle_timings) else 0
        elapsed_time = self.phase_elapsed_times[lane_id]
        
        # State logic:
        # GREEN: 0 to green_duration seconds
        # YELLOW: green_duration to green_duration + yellow_time seconds
        # RED: beyond that
        
        if green_duration == 0:
            # No green time allocated (e.g., cam3, cam4 in cycle 1)
            return 'RED'
        
        if elapsed_time < green_duration:
            return 'GREEN'
        elif elapsed_time < green_duration + self.yellow_time:
            return 'YELLOW'
        else:
            return 'RED'
    
    def get_green_time(self, lane_id=0):
        """
        Get remaining green light time for a lane
        
        Args:
            lane_id: The lane to get time for
            
        Returns:
            Remaining green time in seconds
        """
        if lane_id >= len(self.current_cycle_timings):
            return 0
        
        green_duration = self.current_cycle_timings[lane_id]
        elapsed_time = self.phase_elapsed_times[lane_id]
        
        if elapsed_time < green_duration:
            return max(0, green_duration - elapsed_time)
        return 0
    
    def set_cycle_timing(self, cycle_timings):
        """
        Set the signal timings for the current cycle
        
        Args:
            cycle_timings: List of 4 integers [cam1_green, cam2_green, cam3_green, cam4_green]
        """
        if len(cycle_timings) == 4:
            self.current_cycle_timings = cycle_timings
            # Reset elapsed times for new cycle
            self.phase_elapsed_times = [0, 0, 0, 0]
            self.cycle_number += 1
            print(f"[Traffic Control] New cycle #{self.cycle_number}: Timings = {self.current_cycle_timings}")
    
    def predict_next_cycle_timings(self, lane_metrics_dict):
        """
        Predict next cycle timings based on vehicle count analysis
        
        Args:
            lane_metrics_dict: Dict of lane_id -> vehicle_count
            
        Returns:
            List of predicted timings [cam1, cam2, cam3, cam4]
        """
        predicted = []
        for lane_id in range(4):
            vehicle_count = lane_metrics_dict.get(lane_id, 0)
            
            # Simple prediction: allocate time based on vehicle count
            # More vehicles = longer green time (up to max 120s)
            if vehicle_count == 0:
                duration = 0  # No vehicles, keep red
            elif vehicle_count < 5:
                duration = 15
            elif vehicle_count < 10:
                duration = 25
            elif vehicle_count < 15:
                duration = 35
            else:
                duration = 55  # Max for heavy traffic
            
            predicted.append(duration)
        
        return predicted
    
    def update_observation_time(self, lane_id, elapsed_seconds):
        """
        Update observation time for a lane during initial analysis phase
        
        Args:
            lane_id: Lane to update (0-3)
            elapsed_seconds: How many seconds elapsed for this lane
        """
        if lane_id < 4:
            # Cap at 30 seconds - don't keep increasing
            self.lane_observation_times[lane_id] = min(elapsed_seconds, self.observation_duration)
            
            # Mark lane as ready when observation period is complete
            if elapsed_seconds >= self.observation_duration and not self.lanes_ready[lane_id]:
                self.lanes_ready[lane_id] = True
                print(f"[Traffic Control] Lane {lane_id} observation complete! Max vehicles: {self.observation_vehicle_counts[lane_id]}")
                
                # Check if ALL lanes are ready
                if all(self.lanes_ready):
                    print(f"[Traffic Control] ALL LANES OBSERVATION COMPLETE - Starting signal control!")
                    self.observation_enabled = False
    
    def record_observation_vehicle_count(self, lane_id, vehicle_count):
        """
        Record vehicle count during observation phase
        
        Args:
            lane_id: Lane being observed
            vehicle_count: Number of vehicles detected
        """
        if lane_id < 4:
            self.observation_vehicle_counts[lane_id] = max(self.observation_vehicle_counts[lane_id], vehicle_count)
    
    def is_observation_complete(self):
        """Check if all lanes have completed their 30-second observation period"""
        return all(self.lanes_ready)
    
    def get_observation_status(self):
        """Get current observation status for all lanes"""
        return {
            'lane_0': {'time': self.lane_observation_times[0], 'max_vehicles': self.observation_vehicle_counts[0], 'ready': self.lanes_ready[0]},
            'lane_1': {'time': self.lane_observation_times[1], 'max_vehicles': self.observation_vehicle_counts[1], 'ready': self.lanes_ready[1]},
            'lane_2': {'time': self.lane_observation_times[2], 'max_vehicles': self.observation_vehicle_counts[2], 'ready': self.lanes_ready[2]},
            'lane_3': {'time': self.lane_observation_times[3], 'max_vehicles': self.observation_vehicle_counts[3], 'ready': self.lanes_ready[3]},
        }
    
    def finalize_observation_phase(self):
        """
        Called after observation phase completes
        Uses observed vehicle counts to predict next cycle timings
        """
        if self.is_observation_complete():
            print("[Traffic Control] Observation phase complete!")
            print(f"[Traffic Control] Observed vehicle counts: cam1={self.observation_vehicle_counts[0]}, cam2={self.observation_vehicle_counts[1]}, cam3={self.observation_vehicle_counts[2]}, cam4={self.observation_vehicle_counts[3]}")
            
            # Reset elapsed times for fresh signal control cycle
            self.phase_elapsed_times = [0, 0, 0, 0]
            
            # Apply initial cycle timings [30, 22, 0, 0]
            print(f"[Traffic Control] Starting signal control with initial timings: {self.current_cycle_timings}")
            
            # Predict next cycle based on observations
            lane_metrics = {i: self.observation_vehicle_counts[i] for i in range(4)}
            next_timings = self.predict_next_cycle_timings(lane_metrics)
            print(f"[Traffic Control] Predicted cycle 2 timings (for after cycle 1): {next_timings}")
            
            self.observation_enabled = False
            return next_timings
        return None
        
    def emergency_override(self, emergency_type):
        """
        Check if emergency override is needed
        
        Args:
            emergency_type: Type of emergency ('ambulance', 'fire', 'police')
            
        Returns:
            Boolean indicating if override should activate
        """
        return False  # Override handled at application level
    
    def get_phase_info(self):
        """Get information about all phases"""
        return {
            'current_phase': self.current_phase,
            'phases': [
                {
                    'phase_id': p.phase_id,
                    'duration': p.duration,
                    'yellow_time': p.yellow_time,
                    'congestion': self.lanes[i].congestion_level
                }
                for i, p in enumerate(self.phases)
            ],
            'total_cycle_time': sum(p.duration + p.yellow_time for p in self.phases)
        }
    
    def __repr__(self):
        return f"IntelligentTrafficOptimizer(lanes={self.num_lanes}, current_phase={self.current_phase})"
