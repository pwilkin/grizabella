"""Resource monitoring for detecting memory leaks and threading issues.

This module provides monitoring capabilities to track system resources,
detect memory leaks, and identify threading problems in the Grizabella system.
"""

import gc
import logging
import threading
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available, resource monitoring will be limited")

logger = logging.getLogger(__name__)

@dataclass
class ResourceSnapshot:
    """Snapshot of system resources at a point in time."""
    timestamp: float
    memory_rss: int  # Resident Set Size in bytes
    memory_vms: int  # Virtual Memory Size in bytes
    thread_count: int
    open_files: int
    cpu_percent: float
    gc_objects: int

@dataclass
class ResourceAlert:
    """Alert for resource usage anomalies."""
    timestamp: float
    alert_type: str
    message: str
    severity: str  # 'warning', 'error', 'critical'
    current_value: float
    threshold_value: float
    details: Dict[str, any]

class ResourceMonitor:
    """Monitor system resources and detect memory leaks."""
    
    def __init__(self, check_interval: int = 60, 
                 memory_threshold_mb: int = 100,
                 thread_threshold: int = 20,
                 enable_gc_monitoring: bool = True):
        """Initialize the resource monitor.
        
        Args:
            check_interval: Interval between checks in seconds
            memory_threshold_mb: Memory increase threshold in MB for alerts
            thread_threshold: Thread count threshold for alerts
            enable_gc_monitoring: Whether to monitor garbage collection objects
        """
        self.check_interval = check_interval
        self.memory_threshold_bytes = memory_threshold_mb * 1024 * 1024
        self.thread_threshold = thread_threshold
        self.enable_gc_monitoring = enable_gc_monitoring
        
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Baseline measurements
        self.baseline_snapshot: Optional[ResourceSnapshot] = None
        self.previous_snapshot: Optional[ResourceSnapshot] = None
        
        # History for trend analysis
        self.snapshot_history: List[ResourceSnapshot] = []
        self.max_history_size = 100
        
        # Alerts
        self.alerts: List[ResourceAlert] = []
        self.max_alerts = 50
        
        # Process handle
        if PSUTIL_AVAILABLE:
            self.process = psutil.Process()
        else:
            self.process = None
            
        # Lock for thread safety
        self.lock = threading.RLock()
        
    def start_monitoring(self):
        """Start resource monitoring."""
        if self.monitoring:
            logger.warning("Resource monitoring is already active")
            return
            
        self.monitoring = True
        
        # Take baseline snapshot
        self.baseline_snapshot = self._take_snapshot()
        self.previous_snapshot = self.baseline_snapshot
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="ResourceMonitor"
        )
        self.monitor_thread.start()
        
        baseline_mb = self.baseline_snapshot.memory_rss // 1024 // 1024
        logger.info(f"Resource monitoring started (baseline: {baseline_mb}MB, "
                   f"{self.baseline_snapshot.thread_count} threads)")
        
    def stop_monitoring(self):
        """Stop resource monitoring."""
        if not self.monitoring:
            return
            
        self.monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
            
        logger.info("Resource monitoring stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                snapshot = self._take_snapshot()
                self._analyze_snapshot(snapshot)
                
                with self.lock:
                    self.previous_snapshot = snapshot
                    self.snapshot_history.append(snapshot)
                    
                    # Limit history size
                    if len(self.snapshot_history) > self.max_history_size:
                        self.snapshot_history = self.snapshot_history[-self.max_history_size:]
                        
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in resource monitoring loop: {e}")
                time.sleep(self.check_interval)
                
    def _take_snapshot(self) -> ResourceSnapshot:
        """Take a snapshot of current resource usage."""
        timestamp = time.time()
        
        if PSUTIL_AVAILABLE and self.process:
            try:
                memory_info = self.process.memory_info()
                memory_rss = memory_info.rss
                memory_vms = memory_info.vms
                open_files = len(self.process.open_files())
                cpu_percent = self.process.cpu_percent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                memory_rss = memory_vms = open_files = cpu_percent = 0
        else:
            memory_rss = memory_vms = open_files = cpu_percent = 0
            
        thread_count = threading.active_count()
        gc_objects = len(gc.get_objects()) if self.enable_gc_monitoring else 0
        
        return ResourceSnapshot(
            timestamp=timestamp,
            memory_rss=memory_rss,
            memory_vms=memory_vms,
            thread_count=thread_count,
            open_files=open_files,
            cpu_percent=cpu_percent,
            gc_objects=gc_objects
        )
        
    def _analyze_snapshot(self, snapshot: ResourceSnapshot):
        """Analyze a snapshot for anomalies and generate alerts."""
        if not self.baseline_snapshot:
            return
            
        # Check memory usage
        memory_increase = snapshot.memory_rss - self.baseline_snapshot.memory_rss
        if memory_increase > self.memory_threshold_bytes:
            self._create_alert(
                alert_type="memory_increase",
                message=f"High memory usage detected: +{memory_increase // 1024 // 1024}MB",
                severity="warning",
                current_value=memory_increase,
                threshold_value=self.memory_threshold_bytes,
                details={
                    "current_mb": snapshot.memory_rss // 1024 // 1024,
                    "baseline_mb": self.baseline_snapshot.memory_rss // 1024 // 1024,
                    "increase_mb": memory_increase // 1024 // 1024
                }
            )
            
        # Check thread count
        thread_increase = snapshot.thread_count - self.baseline_snapshot.thread_count
        if snapshot.thread_count > self.thread_threshold:
            self._create_alert(
                alert_type="high_thread_count",
                message=f"High thread count detected: {snapshot.thread_count} threads",
                severity="warning",
                current_value=snapshot.thread_count,
                threshold_value=self.thread_threshold,
                details={
                    "current_threads": snapshot.thread_count,
                    "baseline_threads": self.baseline_snapshot.thread_count,
                    "thread_increase": thread_increase
                }
            )
            
        # Check for rapid memory growth (if we have previous snapshot)
        if self.previous_snapshot and self.previous_snapshot != self.baseline_snapshot:
            time_diff = snapshot.timestamp - self.previous_snapshot.timestamp
            if time_diff > 0:
                memory_growth_rate = (snapshot.memory_rss - self.previous_snapshot.memory_rss) / time_diff
                if memory_growth_rate > 10 * 1024 * 1024:  # 10MB per second
                    self._create_alert(
                        alert_type="rapid_memory_growth",
                        message=f"Rapid memory growth: {memory_growth_rate // 1024 // 1024}MB/s",
                        severity="error",
                        current_value=memory_growth_rate,
                        threshold_value=10 * 1024 * 1024,
                        details={
                            "growth_rate_mb_per_sec": memory_growth_rate // 1024 // 1024,
                            "time_interval_seconds": time_diff
                        }
                    )
                    
        # Check GC objects if enabled
        if self.enable_gc_monitoring and self.baseline_snapshot.gc_objects > 0:
            gc_increase = snapshot.gc_objects - self.baseline_snapshot.gc_objects
            if gc_increase > 10000:  # 10k objects increase
                self._create_alert(
                    alert_type="high_gc_objects",
                    message=f"High GC object count: +{gc_increase} objects",
                    severity="warning",
                    current_value=snapshot.gc_objects,
                    threshold_value=self.baseline_snapshot.gc_objects + 10000,
                    details={
                        "current_objects": snapshot.gc_objects,
                        "baseline_objects": self.baseline_snapshot.gc_objects,
                        "object_increase": gc_increase
                    }
                )
                
    def _create_alert(self, alert_type: str, message: str, severity: str,
                     current_value: float, threshold_value: float, details: Dict[str, any]):
        """Create and store a resource alert."""
        alert = ResourceAlert(
            timestamp=time.time(),
            alert_type=alert_type,
            message=message,
            severity=severity,
            current_value=current_value,
            threshold_value=threshold_value,
            details=details
        )
        
        with self.lock:
            self.alerts.append(alert)
            
            # Limit alerts history
            if len(self.alerts) > self.max_alerts:
                self.alerts = self.alerts[-self.max_alerts:]
                
        # Log the alert
        log_method = {
            'warning': logger.warning,
            'error': logger.error,
            'critical': logger.critical
        }.get(severity, logger.info)
        
        log_method(f"Resource Alert [{alert_type}]: {message}")
        
        # Log thread details for high thread count
        if alert_type == "high_thread_count":
            self._log_thread_details()
            
    def _log_thread_details(self):
        """Log details of all active threads for debugging."""
        try:
            threads = []
            for thread in threading.enumerate():
                threads.append({
                    'name': thread.name,
                    'id': thread.ident,
                    'daemon': thread.daemon,
                    'alive': thread.is_alive()
                })
                
            logger.debug(f"Active threads ({len(threads)}):")
            for thread_info in threads:
                logger.debug(f"  - {thread_info['name']} (ID: {thread_info['id']}, "
                           f"daemon: {thread_info['daemon']}, alive: {thread_info['alive']})")
                           
        except Exception as e:
            logger.error(f"Error logging thread details: {e}")
            
    def get_current_stats(self) -> Dict[str, any]:
        """Get current resource statistics."""
        snapshot = self._take_snapshot()
        
        stats = {
            'timestamp': snapshot.timestamp,
            'memory_rss_mb': snapshot.memory_rss // 1024 // 1024,
            'memory_vms_mb': snapshot.memory_vms // 1024 // 1024,
            'thread_count': snapshot.thread_count,
            'open_files': snapshot.open_files,
            'cpu_percent': snapshot.cpu_percent,
            'gc_objects': snapshot.gc_objects
        }
        
        if self.baseline_snapshot:
            stats['baseline_memory_rss_mb'] = self.baseline_snapshot.memory_rss // 1024 // 1024
            stats['baseline_thread_count'] = self.baseline_snapshot.thread_count
            stats['memory_increase_mb'] = (snapshot.memory_rss - self.baseline_snapshot.memory_rss) // 1024 // 1024
            stats['thread_increase'] = snapshot.thread_count - self.baseline_snapshot.thread_count
            
        return stats
        
    def get_recent_alerts(self, count: int = 10) -> List[ResourceAlert]:
        """Get recent resource alerts.
        
        Args:
            count: Maximum number of alerts to return
            
        Returns:
            List of recent alerts
        """
        with self.lock:
            return self.alerts[-count:] if self.alerts else []
            
    def get_alert_summary(self) -> Dict[str, any]:
        """Get a summary of all alerts.
        
        Returns:
            Dictionary with alert statistics
        """
        with self.lock:
            if not self.alerts:
                return {
                    'total_alerts': 0,
                    'by_type': {},
                    'by_severity': {},
                    'recent_alerts': []
                }
                
            by_type = {}
            by_severity = {}
            
            for alert in self.alerts:
                by_type[alert.alert_type] = by_type.get(alert.alert_type, 0) + 1
                by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
                
            return {
                'total_alerts': len(self.alerts),
                'by_type': by_type,
                'by_severity': by_severity,
                'recent_alerts': self.get_recent_alerts(5)
            }
            
    def force_garbage_collection(self) -> Dict[str, any]:
        """Force garbage collection and report results.
        
        Returns:
            Dictionary with GC results
        """
        if not self.enable_gc_monitoring:
            return {'error': 'GC monitoring is not enabled'}
            
        try:
            # Get object count before GC
            objects_before = len(gc.get_objects())
            
            # Force garbage collection
            collected = gc.collect()
            
            # Get object count after GC
            objects_after = len(gc.get_objects())
            
            result = {
                'objects_collected': objects_before - objects_after,
                'objects_before': objects_before,
                'objects_after': objects_after,
                'gc_cycles_run': collected
            }
            
            logger.info(f"Garbage collection completed: {result['objects_collected']} objects collected")
            return result
            
        except Exception as e:
            error_msg = f"Error during garbage collection: {e}"
            logger.error(error_msg)
            return {'error': error_msg}
            
    def reset_baseline(self):
        """Reset the baseline to current resource usage."""
        self.baseline_snapshot = self._take_snapshot()
        logger.info(f"Resource baseline reset: {self.baseline_snapshot.memory_rss // 1024 // 1024}MB, "
                   f"{self.baseline_snapshot.thread_count} threads")

# Global monitor instance
_global_monitor: Optional[ResourceMonitor] = None
_monitor_lock = threading.Lock()

def get_global_monitor() -> ResourceMonitor:
    """Get the global resource monitor instance.
    
    Returns:
        ResourceMonitor: The global monitor instance
    """
    global _global_monitor
    if _global_monitor is None:
        with _monitor_lock:
            if _global_monitor is None:
                _global_monitor = ResourceMonitor()
    return _global_monitor

def start_global_monitoring(**kwargs):
    """Start global resource monitoring.
    
    Args:
        **kwargs: Arguments to pass to ResourceMonitor constructor
    """
    monitor = get_global_monitor()
    monitor.start_monitoring()

def stop_global_monitoring():
    """Stop global resource monitoring."""
    monitor = get_global_monitor()
    monitor.stop_monitoring()

def get_resource_stats() -> Dict[str, any]:
    """Get current resource statistics from global monitor.
    
    Returns:
        Dictionary with current resource statistics
    """
    monitor = get_global_monitor()
    return monitor.get_current_stats()