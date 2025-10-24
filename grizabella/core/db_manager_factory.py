"""Factory for managing singleton GrizabellaDBManager instances.

This module provides a factory pattern implementation that ensures singleton
behavior for GrizabellaDBManager instances while properly managing their
lifecycle through reference counting and graceful cleanup.
"""

import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Union
from weakref import WeakValueDictionary

from grizabella.core.db_manager import GrizabellaDBManager

logger = logging.getLogger(__name__)

class DBManagerFactory:
    """Factory for managing singleton GrizabellaDBManager instances.
    
    This class ensures that:
    - Only one GrizabellaDBManager instance exists per database path
    - Proper reference counting tracks active usage
    - Graceful cleanup occurs when no more references exist
    - Thread-safe operations prevent race conditions
    """
    
    _instances: Dict[str, GrizabellaDBManager] = {}
    _reference_counts: Dict[str, int] = {}
    _lock = threading.RLock()
    
    @classmethod
    def get_manager(cls, db_name_or_path: Union[str, Path], 
                   create_if_not_exists: bool = True,
                   **kwargs) -> GrizabellaDBManager:
        """Get or create a singleton DBManager for the given database path.
        
        Args:
            db_name_or_path: The database name or file path
            create_if_not_exists: Whether to create the database if it doesn't exist
            **kwargs: Additional arguments for GrizabellaDBManager
            
        Returns:
            GrizabellaDBManager: The singleton instance for the database
        """
        # Normalize path to ensure consistent keys
        db_path = str(Path(db_name_or_path).resolve())
        
        with cls._lock:
            if db_path not in cls._instances:
                logger.info(f"Creating new GrizabellaDBManager for: {db_path}")
                
                try:
                    # Create new instance
                    manager = GrizabellaDBManager(
                        db_name_or_path=db_path,
                        create_if_not_exists=create_if_not_exists,
                        **kwargs
                    )
                    
                    cls._instances[db_path] = manager
                    cls._reference_counts[db_path] = 1
                    
                    logger.info(f"Created GrizabellaDBManager for: {db_path} (ref count: 1)")
                    
                except Exception as e:
                    logger.error(f"Failed to create GrizabellaDBManager for {db_path}: {e}")
                    raise
                    
            else:
                # Increment reference count
                cls._reference_counts[db_path] += 1
                logger.debug(f"Reusing GrizabellaDBManager for: {db_path} (ref count: {cls._reference_counts[db_path]})")
                
            return cls._instances[db_path]
            
    @classmethod
    def release_manager(cls, db_name_or_path: Union[str, Path]) -> bool:
        """Release a reference to a DBManager instance.
        
        Args:
            db_name_or_path: The database name or file path
            
        Returns:
            bool: True if the manager was cleaned up, False if still has references
        """
        db_path = str(Path(db_name_or_path).resolve())
        
        with cls._lock:
            if db_path not in cls._instances:
                logger.warning(f"Attempting to release non-existent manager: {db_path}")
                return False
                
            # Decrement reference count
            cls._reference_counts[db_path] -= 1
            logger.debug(f"Released reference for: {db_path} (ref count: {cls._reference_counts[db_path]})")
            
            # Clean up if no more references
            if cls._reference_counts[db_path] <= 0:
                logger.info(f"Cleaning up GrizabellaDBManager for: {db_path}")
                
                try:
                    manager = cls._instances[db_path]
                    manager.close()
                    logger.info(f"Successfully closed GrizabellaDBManager for: {db_path}")
                except Exception as e:
                    logger.error(f"Error closing manager for {db_path}: {e}")
                finally:
                    del cls._instances[db_path]
                    del cls._reference_counts[db_path]
                    
                logger.info(f"Cleaned up GrizabellaDBManager for: {db_path}")
                return True
                
            return False
            
    @classmethod
    def cleanup_manager(cls, db_name_or_path: Union[str, Path]) -> bool:
        """Force cleanup of a specific DBManager instance.
        
        This method forcefully cleans up a manager regardless of reference count.
        Use with caution as it may affect other code using the manager.
        
        Args:
            db_name_or_path: The database name or file path
            
        Returns:
            bool: True if the manager was cleaned up, False if not found
        """
        db_path = str(Path(db_name_or_path).resolve())
        
        with cls._lock:
            if db_path not in cls._instances:
                logger.debug(f"No manager to cleanup for: {db_path}")
                return False
                
            logger.warning(f"Force cleaning up GrizabellaDBManager for: {db_path}")
            
            try:
                manager = cls._instances[db_path]
                manager.close()
                logger.info(f"Successfully closed GrizabellaDBManager for: {db_path}")
            except Exception as e:
                logger.error(f"Error closing manager for {db_path}: {e}")
            finally:
                del cls._instances[db_path]
                del cls._reference_counts[db_path]
                
            return True
            
    @classmethod
    def cleanup_all(cls):
        """Clean up all DBManager instances.
        
        This method forcefully cleans up all managers regardless of reference count.
        Use with caution as it may affect other code using the managers.
        """
        with cls._lock:
            logger.info("Cleaning up all GrizabellaDBManager instances")
            
            # Store current instances to avoid modifying dict during iteration
            instances_to_cleanup = list(cls._instances.items())
            
            for db_path, manager in instances_to_cleanup:
                try:
                    logger.debug(f"Cleaning up manager for: {db_path}")
                    manager.close()
                except Exception as e:
                    logger.error(f"Error closing manager for {db_path}: {e}")
                    
            cls._instances.clear()
            cls._reference_counts.clear()
            
            logger.info("All GrizabellaDBManager instances cleaned up")
            
    @classmethod
    def get_active_managers(cls) -> Dict[str, int]:
        """Get information about active managers.
        
        Returns:
            Dict[str, int]: Dictionary mapping database paths to reference counts
        """
        with cls._lock:
            return cls._reference_counts.copy()
            
    @classmethod
    def is_manager_active(cls, db_name_or_path: Union[str, Path]) -> bool:
        """Check if a manager is active for the given database.
        
        Args:
            db_name_or_path: The database name or file path
            
        Returns:
            bool: True if manager is active, False otherwise
        """
        db_path = str(Path(db_name_or_path).resolve())
        return db_path in cls._instances
        
    @classmethod
    def get_manager_info(cls, db_name_or_path: Union[str, Path]) -> Optional[Dict[str, any]]:
        """Get detailed information about a specific manager.
        
        Args:
            db_name_or_path: The database name or file path
            
        Returns:
            Optional[Dict[str, any]]: Manager information or None if not found
        """
        db_path = str(Path(db_name_or_path).resolve())
        
        with cls._lock:
            if db_path not in cls._instances:
                return None
                
            manager = cls._instances[db_path]
            
            return {
                'db_path': db_path,
                'reference_count': cls._reference_counts[db_path],
                'is_connected': manager.is_connected,
                'db_name': manager.db_name,
                'db_instance_root': str(manager.db_instance_root),
            }
            
    @classmethod
    def get_all_manager_info(cls) -> Dict[str, Dict[str, any]]:
        """Get detailed information about all active managers.
        
        Returns:
            Dict[str, Dict[str, any]]: Dictionary mapping database paths to manager info
        """
        with cls._lock:
            info = {}
            for db_path in cls._instances:
                manager_info = cls.get_manager_info(db_path)
                if manager_info:
                    info[db_path] = manager_info
            return info
            
    @classmethod
    def validate_manager_state(cls) -> Dict[str, any]:
        """Validate the state of all managers and report issues.
        
        Returns:
            Dict[str, any]: Validation results including any issues found
        """
        with cls._lock:
            issues = []
            stats = {
                'total_managers': len(cls._instances),
                'total_references': sum(cls._reference_counts.values()),
                'managers_with_issues': 0,
                'issues': []
            }
            
            for db_path, manager in cls._instances.items():
                manager_issues = []
                
                # Check if manager is connected
                if not manager.is_connected:
                    manager_issues.append("Manager is not connected")
                    
                # Check reference count consistency
                ref_count = cls._reference_counts.get(db_path, 0)
                if ref_count <= 0:
                    manager_issues.append(f"Invalid reference count: {ref_count}")
                    
                # Check database path accessibility
                try:
                    if not manager.db_instance_root.exists():
                        manager_issues.append("Database instance root does not exist")
                except Exception as e:
                    manager_issues.append(f"Error accessing database path: {e}")
                    
                if manager_issues:
                    stats['managers_with_issues'] += 1
                    issues.append({
                        'db_path': db_path,
                        'issues': manager_issues,
                        'reference_count': ref_count,
                        'is_connected': manager.is_connected
                    })
                    
            stats['issues'] = issues
            return stats

# Global instance for easy access
_db_manager_factory = DBManagerFactory()

def get_db_manager_factory() -> DBManagerFactory:
    """Get the global DBManager factory instance.
    
    Returns:
        DBManagerFactory: The singleton factory instance
    """
    return _db_manager_factory

# Convenience functions for common operations
def get_manager(db_name_or_path: Union[str, Path], 
               create_if_not_exists: bool = True,
               **kwargs) -> GrizabellaDBManager:
    """Get a GrizabellaDBManager instance using the factory.
    
    Args:
        db_name_or_path: The database name or file path
        create_if_not_exists: Whether to create the database if it doesn't exist
        **kwargs: Additional arguments for GrizabellaDBManager
        
    Returns:
        GrizabellaDBManager: The manager instance
    """
    return _db_manager_factory.get_manager(db_name_or_path, create_if_not_exists, **kwargs)

def release_manager(db_name_or_path: Union[str, Path]) -> bool:
    """Release a GrizabellaDBManager instance using the factory.
    
    Args:
        db_name_or_path: The database name or file path
        
    Returns:
        bool: True if the manager was cleaned up, False if still has references
    """
    return _db_manager_factory.release_manager(db_name_or_path)

def cleanup_all_managers():
    """Clean up all GrizabellaDBManager instances using the factory."""
    _db_manager_factory.cleanup_all()

def get_active_managers_info() -> Dict[str, Dict[str, any]]:
    """Get information about all active managers.
    
    Returns:
        Dict[str, Dict[str, any]]: Dictionary mapping database paths to manager info
    """
    return _db_manager_factory.get_all_manager_info()