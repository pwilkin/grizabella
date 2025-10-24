# Grizabella Memory Leak Fix - Implementation Specification

## Implementation Overview

This document provides detailed implementation specifications for each component of the memory leak fix solution. Each section includes concrete code examples, file locations, and integration points.

## Phase 1: Core Infrastructure Implementation

### 1.1 Connection Pool Manager

**File Location**: `grizabella/core/connection_pool.py`

```python
import asyncio
import logging
import threading
import time
from collections import defaultdict
from queue import Queue, Empty
from typing import Any, Dict, Optional, Union
from contextlib import asynccontextmanager

from grizabella.db_layers.sqlite.sqlite_adapter import SQLiteAdapter
from grizabella.db_layers.lancedb.lancedb_adapter import LanceDBAdapter
from grizabella.db_layers.kuzu.kuzu_adapter import KuzuAdapter

logger = logging.getLogger(__name__)

class PooledConnection:
    """Wrapper for pooled connections with metadata"""
    
    def __init__(self, connection, created_at: float, last_used: float):
        self.connection = connection
        self.created_at = created_at
        self.last_used = last_used
        self.in_use = False
        self.usage_count = 0
        
    def mark_used(self):
        self.last_used = time.time()
        self.usage_count += 1
        self.in_use = True
        
    def mark_returned(self):
        self.in_use = False

class ConnectionPoolManager:
    """Thread-safe connection pool for database adapters"""
    
    def __init__(self, 
                 max_connections_per_type: int = 10,
                 max_idle_time: int = 300,  # 5 minutes
                 connection_timeout: int = 30):
        self._pools: Dict[str, Queue] = {
            'sqlite': Queue(maxsize=max_connections_per_type),
            'lancedb': Queue(maxsize=max_connections_per_type),
            'kuzu': Queue(maxsize=max_connections_per_type)
        }
        self._lock = threading.RLock()
        self._connection_count = defaultdict(int)
        self._max_idle_time = max_idle_time
        self._connection_timeout = connection_timeout
        self._cleanup_thread = None
        self._shutdown = False
        
        # Start cleanup thread
        self._start_cleanup_thread()
        
    def _start_cleanup_thread(self):
        """Start background thread for cleaning up idle connections"""
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_idle_connections,
            daemon=True,
            name="ConnectionPool-Cleanup"
        )
        self._cleanup_thread.start()
        
    async def get_connection(self, adapter_type: str, **kwargs) -> PooledConnection:
        """Get a connection from the pool or create a new one"""
        if adapter_type not in self._pools:
            raise ValueError(f"Unsupported adapter type: {adapter_type}")
            
        pool = self._pools[adapter_type]
        
        try:
            # Try to get existing connection from pool
            pooled_conn = pool.get(timeout=self._connection_timeout)
            
            # Validate connection is still alive
            if self._is_connection_alive(pooled_conn.connection, adapter_type):
                pooled_conn.mark_used()
                logger.debug(f"Reusing {adapter_type} connection (usage: {pooled_conn.usage_count})")
                return pooled_conn
            else:
                # Connection is dead, create new one
                logger.warning(f"Dead {adapter_type} connection found, creating new one")
                await self._close_connection(pooled_conn.connection, adapter_type)
                
        except Empty:
            # No available connections, create new one if under limit
            with self._lock:
                if self._connection_count[adapter_type] < pool.maxsize:
                    self._connection_count[adapter_type] += 1
                else:
                    raise Exception(f"Maximum connections reached for {adapter_type}")
        
        # Create new connection
        connection = await self._create_connection(adapter_type, **kwargs)
        pooled_conn = PooledConnection(
            connection=connection,
            created_at=time.time(),
            last_used=time.time()
        )
        pooled_conn.mark_used()
        
        logger.info(f"Created new {adapter_type} connection (total: {self._connection_count[adapter_type]})")
        return pooled_conn
        
    async def return_connection(self, adapter_type: str, pooled_conn: PooledConnection):
        """Return a connection to the pool"""
        if not pooled_conn or not pooled_conn.connection:
            return
            
        try:
            pooled_conn.mark_returned()
            self._pools[adapter_type].put(pooled_conn, timeout=5)
            logger.debug(f"Returned {adapter_type} connection to pool")
        except Exception as e:
            # Pool is full or other error, close the connection
            logger.warning(f"Failed to return {adapter_type} connection to pool: {e}")
            await self._close_connection(pooled_conn.connection, adapter_type)
            with self._lock:
                self._connection_count[adapter_type] -= 1
                
    async def _create_connection(self, adapter_type: str, **kwargs):
        """Create a new database connection"""
        if adapter_type == 'sqlite':
            return SQLiteAdapter(**kwargs)
        elif adapter_type == 'lancedb':
            return LanceDBAdapter(**kwargs)
        elif adapter_type == 'kuzu':
            return ThreadSafeKuzuAdapter(**kwargs)
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")
            
    async def _close_connection(self, connection, adapter_type: str):
        """Close a database connection"""
        try:
            if hasattr(connection, 'close'):
                if asyncio.iscoroutinefunction(connection.close):
                    await connection.close()
                else:
                    connection.close()
            logger.debug(f"Closed {adapter_type} connection")
        except Exception as e:
            logger.error(f"Error closing {adapter_type} connection: {e}")
            
    def _is_connection_alive(self, connection, adapter_type: str) -> bool:
        """Check if a connection is still alive"""
        try:
            if adapter_type == 'sqlite':
                return connection.conn is not None
            elif adapter_type == 'lancedb':
                return hasattr(connection, '_db') and connection._db is not None
            elif adapter_type == 'kuzu':
                return connection.conn is not None
            return False
        except Exception:
            return False
            
    def _cleanup_idle_connections(self):
        """Background thread to clean up idle connections"""
        while not self._shutdown:
            try:
                current_time = time.time()
                for adapter_type, pool in self._pools.items():
                    temp_connections = []
                    
                    # Drain pool and check each connection
                    while not pool.empty():
                        try:
                            pooled_conn = pool.get_nowait()
                            if (current_time - pooled_conn.last_used > self._max_idle_time and 
                                not pooled_conn.in_use):
                                # Connection is idle and not in use, close it
                                asyncio.create_task(
                                    self._close_connection(pooled_conn.connection, adapter_type)
                                )
                                with self._lock:
                                    self._connection_count[adapter_type] -= 1
                                logger.info(f"Cleaned up idle {adapter_type} connection")
                            else:
                                temp_connections.append(pooled_conn)
                        except Empty:
                            break
                            
                    # Put valid connections back in pool
                    for conn in temp_connections:
                        pool.put(conn)
                        
            except Exception as e:
                logger.error(f"Error in cleanup thread: {e}")
                
            # Sleep for 1 minute before next cleanup
            time.sleep(60)
            
    async def cleanup_all(self):
        """Clean up all connections in the pool"""
        self._shutdown = True
        
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
            
        for adapter_type, pool in self._pools.items():
            while not pool.empty():
                try:
                    pooled_conn = pool.get_nowait()
                    await self._close_connection(pooled_conn.connection, adapter_type)
                except Empty:
                    break
                    
        with self._lock:
            self._connection_count.clear()
            
        logger.info("All connection pools cleaned up")
        
    @asynccontextmanager
    async def get_connection_context(self, adapter_type: str, **kwargs):
        """Context manager for getting and returning connections"""
        pooled_conn = None
        try:
            pooled_conn = await self.get_connection(adapter_type, **kwargs)
            yield pooled_conn.connection
        finally:
            if pooled_conn:
                await self.return_connection(adapter_type, pooled_conn)

# Global singleton instance
_connection_pool_manager: Optional[ConnectionPoolManager] = None
_pool_lock = threading.Lock()

def get_connection_pool_manager() -> ConnectionPoolManager:
    """Get the global connection pool manager instance"""
    global _connection_pool_manager
    if _connection_pool_manager is None:
        with _pool_lock:
            if _connection_pool_manager is None:
                _connection_pool_manager = ConnectionPoolManager()
    return _connection_pool_manager
```

### 1.2 Thread-Safe KuzuAdapter

**File Location**: `grizabella/db_layers/kuzu/thread_safe_kuzu_adapter.py`

```python
import glob
import logging
import os
import threading
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import kuzu

from grizabella.core.exceptions import DatabaseError, InstanceError, SchemaError
from grizabella.core.models import (
    EmbeddingDefinition, EmbeddingInstance, ObjectInstance, PropertyDataType,
    RelationInstance, ObjectTypeDefinition as ObjectTypeDefinitionModel,
    RelationTypeDefinition as RelationTypeDefinitionModel
)
from grizabella.core.query_models import GraphTraversalClause
from grizabella.db_layers.common.base_adapter import BaseDBAdapter

logger = logging.getLogger(__name__)

class ThreadSafeKuzuAdapter(BaseDBAdapter):
    """Thread-safe Kuzu adapter with proper connection isolation"""
    
    def __init__(self, db_path: str, config: Optional[dict[str, Any]] = None):
        self._db_path = db_path
        self._config = config or {}
        self._lock = threading.RLock()
        
        # Thread-local storage for connections
        self._local = threading.local()
        
        # Shared database instance (thread-safe in Kuzu)
        self._db: Optional[kuzu.Database] = None
        self._db_lock = threading.Lock()
        
        logger.info(f"ThreadSafeKuzuAdapter: Initializing for db_path: {db_path}")
        
        # Initialize database (shared across threads)
        self._init_database()
        
    def _init_database(self):
        """Initialize the shared database instance"""
        with self._db_lock:
            if self._db is None:
                try:
                    # Clean up stale lock files
                    self._cleanup_stale_files()
                    
                    logger.info(f"ThreadSafeKuzuAdapter: Creating shared Database instance")
                    self._db = kuzu.Database(self._db_path)
                    logger.info(f"ThreadSafeKuzuAdapter: Shared Database instance created: {self._db}")
                except Exception as e:
                    logger.error(f"ThreadSafeKuzuAdapter: Error creating database: {e}")
                    raise DatabaseError(f"KuzuDB initialization error: {e}") from e
                    
    @property
    def conn(self) -> kuzu.Connection:
        """Get thread-local connection"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._create_connection()
        return self._local.conn
        
    def _create_connection(self) -> kuzu.Connection:
        """Create a new thread-local connection"""
        thread_id = threading.get_ident()
        logger.info(f"ThreadSafeKuzuAdapter: Creating connection for thread {thread_id}")
        
        try:
            if self._db is None:
                raise DatabaseError("Database not initialized")
                
            conn = kuzu.Connection(self._db)
            logger.info(f"ThreadSafeKuzuAdapter: Connection created for thread {thread_id}: {conn}")
            return conn
        except Exception as e:
            logger.error(f"ThreadSafeKuzuAdapter: Error creating connection for thread {thread_id}: {e}")
            raise DatabaseError(f"KuzuDB connection error: {e}") from e
            
    def _cleanup_stale_files(self):
        """Clean up stale lock and WAL files"""
        try:
            # Clean up lock files
            lock_files = glob.glob(os.path.join(self._db_path, "*.lock"), include_hidden=True)
            for lock_file in lock_files:
                try:
                    os.remove(lock_file)
                    logger.info(f"ThreadSafeKuzuAdapter: Removed stale lock file: {lock_file}")
                except OSError as e:
                    logger.warning(f"ThreadSafeKuzuAdapter: Could not remove lock file {lock_file}: {e}")
                    
            # Clean up WAL files
            wal_files = glob.glob(os.path.join(self._db_path, "*.wal"), include_hidden=True)
            for wal_file in wal_files:
                try:
                    os.remove(wal_file)
                    logger.info(f"ThreadSafeKuzuAdapter: Removed stale WAL file: {wal_file}")
                except OSError as e:
                    logger.warning(f"ThreadSafeKuzuAdapter: Could not remove WAL file {wal_file}: {e}")
                    
        except Exception as e:
            logger.warning(f"ThreadSafeKuzuAdapter: Error cleaning up stale files: {e}")
            
    def close(self):
        """Close thread-local connection"""
        thread_id = threading.get_ident()
        
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            try:
                # Kuzu connections are cleaned up by garbage collector
                # but we can explicitly dereference
                self._local.conn = None
                logger.info(f"ThreadSafeKuzuAdapter: Closed connection for thread {thread_id}")
            except Exception as e:
                logger.error(f"ThreadSafeKuzuAdapter: Error closing connection for thread {thread_id}: {e}")
                
    def close_all(self):
        """Close all connections and database"""
        with self._db_lock:
            if self._db is not None:
                try:
                    self._db = None
                    logger.info("ThreadSafeKuzuAdapter: Closed shared database instance")
                except Exception as e:
                    logger.error(f"ThreadSafeKuzuAdapter: Error closing database: {e}")
                    
    # Delegate all other methods to the original KuzuAdapter implementation
    # but use the thread-local connection
    def _map_grizabella_to_kuzu_type(self, prop_type: PropertyDataType) -> str:
        """Maps Grizabella PropertyDataType to Kuzu data type strings."""
        mapping = {
            PropertyDataType.TEXT: "STRING",
            PropertyDataType.INTEGER: "INT64",
            PropertyDataType.FLOAT: "DOUBLE",
            PropertyDataType.BOOLEAN: "BOOL",
            PropertyDataType.DATETIME: "TIMESTAMP",
            PropertyDataType.BLOB: "BLOB",
            PropertyDataType.JSON: "STRING",
            PropertyDataType.UUID: "UUID",
        }
        kuzu_type = mapping.get(prop_type)
        if not kuzu_type:
            msg = f"Unsupported Grizabella data type for Kuzu: {prop_type}"
            raise SchemaError(msg)
        return kuzu_type
        
    # Implement all other methods from original KuzuAdapter...
    # Each method should use self.conn (thread-local) instead of storing connection
```

### 1.3 DBManager Factory

**File Location**: `grizabella/core/db_manager_factory.py`

```python
import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Union
from weakref import WeakValueDictionary

from grizabella.core.db_manager import GrizabellaDBManager

logger = logging.getLogger(__name__)

class DBManagerFactory:
    """Factory for managing singleton GrizabellaDBManager instances"""
    
    _instances: Dict[str, GrizabellaDBManager] = {}
    _reference_counts: Dict[str, int] = {}
    _lock = threading.RLock()
    
    @classmethod
    def get_manager(cls, db_name_or_path: Union[str, Path], 
                   create_if_not_exists: bool = True,
                   **kwargs) -> GrizabellaDBManager:
        """Get or create a singleton DBManager for the given database path"""
        
        # Normalize path to ensure consistent keys
        db_path = str(Path(db_name_or_path).resolve())
        
        with cls._lock:
            if db_path not in cls._instances:
                logger.info(f"Creating new GrizabellaDBManager for: {db_path}")
                
                # Create new instance
                manager = GrizabellaDBManager(
                    db_name_or_path=db_path,
                    create_if_not_exists=create_if_not_exists,
                    **kwargs
                )
                
                cls._instances[db_path] = manager
                cls._reference_counts[db_path] = 1
                
                logger.info(f"Created GrizabellaDBManager for: {db_path} (ref count: 1)")
            else:
                # Increment reference count
                cls._reference_counts[db_path] += 1
                logger.debug(f"Reusing GrizabellaDBManager for: {db_path} (ref count: {cls._reference_counts[db_path]})")
                
            return cls._instances[db_path]
            
    @classmethod
    def release_manager(cls, db_name_or_path: Union[str, Path]) -> bool:
        """Release a reference to a DBManager instance"""
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
        """Force cleanup of a specific DBManager instance"""
        db_path = str(Path(db_name_or_path).resolve())
        
        with cls._lock:
            if db_path not in cls._instances:
                return False
                
            logger.info(f"Force cleaning up GrizabellaDBManager for: {db_path}")
            
            try:
                manager = cls._instances[db_path]
                manager.close()
            except Exception as e:
                logger.error(f"Error closing manager for {db_path}: {e}")
            finally:
                del cls._instances[db_path]
                del cls._reference_counts[db_path]
                
            return True
            
    @classmethod
    def cleanup_all(cls):
        """Clean up all DBManager instances"""
        with cls._lock:
            logger.info("Cleaning up all GrizabellaDBManager instances")
            
            for db_path in list(cls._instances.keys()):
                try:
                    manager = cls._instances[db_path]
                    manager.close()
                except Exception as e:
                    logger.error(f"Error closing manager for {db_path}: {e}")
                    
            cls._instances.clear()
            cls._reference_counts.clear()
            
            logger.info("All GrizabellaDBManager instances cleaned up")
            
    @classmethod
    def get_active_managers(cls) -> Dict[str, int]:
        """Get information about active managers"""
        with cls._lock:
            return cls._reference_counts.copy()
            
    @classmethod
    def is_manager_active(cls, db_name_or_path: Union[str, Path]) -> bool:
        """Check if a manager is active for the given database"""
        db_path = str(Path(db_name_or_path).resolve())
        return db_path in cls._instances
```

## Phase 2: MCP Server Enhancements

### 2.1 Enhanced MCP Server

**File Location**: `grizabella/mcp/enhanced_server.py`

```python
import argparse
import asyncio
import gc
import logging
import os
import psutil
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from fastmcp import FastMCP
from pydantic import BaseModel

from grizabella.api.client import Grizabella
from grizabella.core.db_manager_factory import DBManagerFactory
from grizabella.core.connection_pool import get_connection_pool_manager

logger = logging.getLogger(__name__)

class ResourceMonitor:
    """Monitor system resources and detect memory leaks"""
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.monitoring = False
        self.monitor_thread = None
        self.process = psutil.Process()
        self.baseline_memory = None
        self.baseline_threads = None
        
    def start_monitoring(self):
        """Start resource monitoring"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.baseline_memory = self.process.memory_info().rss
        self.baseline_threads = threading.active_count()
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="ResourceMonitor"
        )
        self.monitor_thread.start()
        
        logger.info(f"Resource monitoring started (baseline: {self.baseline_memory // 1024 // 1024}MB, {self.baseline_threads} threads)")
        
    def stop_monitoring(self):
        """Stop resource monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                self._check_resources()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                
    def _check_resources(self):
        """Check current resource usage"""
        current_memory = self.process.memory_info().rss
        current_threads = threading.active_count()
        
        memory_increase = current_memory - self.baseline_memory
        thread_increase = current_threads - self.baseline_threads
        
        # Log resource usage
        logger.debug(f"Memory: {current_memory // 1024 // 1024}MB (+{memory_increase // 1024 // 1024}MB), "
                    f"Threads: {current_threads} (+{thread_increase})")
        
        # Alert on significant increases
        if memory_increase > 100 * 1024 * 1024:  # 100MB increase
            logger.warning(f"High memory usage detected: +{memory_increase // 1024 // 1024}MB")
            
        if thread_increase > 10:  # 10 threads increase
            logger.warning(f"High thread count detected: {current_threads} threads (+{thread_increase})")
            
            # Log thread details for debugging
            for thread in threading.enumerate():
                logger.debug(f"Active thread: {thread.name} (ID: {thread.ident})")

class EnhancedMCPServer:
    """Enhanced MCP server with proper resource management"""
    
    def __init__(self):
        self.app = FastMCP(
            name="Grizabella", 
            instructions="A tri-layer memory management system with a relational database, an embedding database and a graph database layer."
        )
        self.grizabella_client: Optional[Grizabella] = None
        self.db_path: Optional[str] = None
        self.resource_monitor = ResourceMonitor()
        self.shutdown_handlers = []
        
    async def start_server(self, db_path: str):
        """Start server with proper initialization"""
        self.db_path = db_path
        
        try:
            logger.info(f"Starting enhanced MCP server for database: {db_path}")
            
            # Initialize Grizabella client using factory
            self.grizabella_client = Grizabella(
                db_name_or_path=db_path,
                create_if_not_exists=True
            )
            
            # Start resource monitoring
            self.resource_monitor.start_monitoring()
            
            # Register shutdown handlers
            self._register_shutdown_handlers()
            
            # Setup tools (reuse existing tool definitions)
            self._setup_tools()
            
            logger.info("Enhanced MCP server started successfully")
            
            # Run the FastMCP app
            await self.app.run_async(show_banner=False)
            
        except Exception as e:
            logger.error(f"Error starting MCP server: {e}")
            await self.shutdown_server()
            raise
            
    async def shutdown_server(self):
        """Graceful shutdown with resource cleanup"""
        logger.info("Shutting down enhanced MCP server")
        
        try:
            # Stop resource monitoring
            self.resource_monitor.stop_monitoring()
            
            # Close Grizabella client
            if self.grizabella_client:
                self.grizabella_client.close()
                self.grizabella_client = None
                
            # Cleanup connection pool
            connection_pool = get_connection_pool_manager()
            await connection_pool.cleanup_all()
            
            # Cleanup DBManager factory
            DBManagerFactory.cleanup_all()
            
            # Force garbage collection
            gc.collect()
            
            logger.info("Enhanced MCP server shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during server shutdown: {e}")
            
    def _register_shutdown_handlers(self):
        """Register signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown")
            asyncio.create_task(self.shutdown_server())
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
    def _setup_tools(self):
        """Setup MCP tools (reuse existing definitions)"""
        # Import and register all existing tools from the original server
        # This would be moved from the original server.py
        pass

# Global server instance
_server_instance: Optional[EnhancedMCPServer] = None

def get_server_instance() -> EnhancedMCPServer:
    """Get the global server instance"""
    global _server_instance
    if _server_instance is None:
        _server_instance = EnhancedMCPServer()
    return _server_instance

async def main():
    """Main entry point for enhanced MCP server"""
    parser = argparse.ArgumentParser(description="Enhanced Grizabella MCP Server")
    parser.add_argument("--db-path", help="Path to the Grizabella database.")
    args = parser.parse_args()
    
    db_path = args.db_path or os.getenv("GRIZABELLA_DB_PATH", "grizabella_mcp_db")
    
    server = get_server_instance()
    
    try:
        await server.start_server(db_path)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await server.shutdown_server()

if __name__ == "__main__":
    asyncio.run(main())
```

## Integration Points

### 1. Update Existing DBManager

**File**: `grizabella/core/db_manager.py`

```python
# Add to imports
from grizabella.core.connection_pool import get_connection_pool_manager

# Update _ConnectionHelper to use connection pool
class _ConnectionHelper:
    def __init__(self, ...):
        # ... existing code ...
        self._connection_pool = get_connection_pool_manager()
        
    async def connect_all_adapters(self) -> None:
        """Connect all managed database adapters using connection pool"""
        if self._adapters_are_connected:
            return
            
        try:
            # Use connection pool for each adapter
            self._sqlite_adapter_instance = await self._connection_pool.get_connection(
                'sqlite', db_path=self.sqlite_db_file_path
            )
            
            self._lancedb_adapter_instance = await self._connection_pool.get_connection(
                'lancedb', db_uri=self.lancedb_uri
            )
            
            self._kuzu_adapter_instance = await self._connection_pool.get_connection(
                'kuzu', db_path=self.kuzu_path
            )
            
            self._adapters_are_connected = True
            
        except Exception as e:
            await self.close_all_adapters()
            raise
```

### 2. Update Grizabella Client

**File**: `grizabella/api/client.py`

```python
# Add to imports
from grizabella.core.db_manager_factory import DBManagerFactory

class Grizabella:
    def __init__(self, db_name_or_path: Union[str, Path] = "default", create_if_not_exists: bool = True):
        # ... existing code ...
        
        # Use factory for DBManager
        self._db_manager = DBManagerFactory.get_manager(
            db_name_or_path=db_name_or_path,
            create_if_not_exists=create_if_not_exists
        )
        
    def close(self) -> None:
        """Close the connection using factory"""
        self._logger.info(f"Grizabella client close() called for db: {self.db_name_or_path}")
        
        if self._is_connected:
            try:
                self._db_manager.close()
                self._logger.info(f"Grizabella client: self._db_manager.close() completed for {self.db_name_or_path}.")
            except Exception as e:
                self._logger.error(f"Grizabella client: Error during self._db_manager.close() for {self.db_name_or_path}: {e}", exc_info=True)
            finally:
                # Release reference to factory
                DBManagerFactory.release_manager(self.db_name_or_path)
                self._is_connected = False
                self._logger.info(f"Grizabella client: _is_connected set to False for {self.db_name_or_path}.")
```

## Testing Strategy

### 1. Unit Tests

**File**: `tests/unit/core/test_connection_pool.py`

```python
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from grizabella.core.connection_pool import ConnectionPoolManager, PooledConnection

class TestConnectionPoolManager:
    
    @pytest.fixture
    def pool_manager(self):
        return ConnectionPoolManager(max_connections_per_type=2)
        
    @pytest.mark.asyncio
    async def test_get_and_return_connection(self, pool_manager):
        # Test getting and returning connections
        conn = await pool_manager.get_connection('sqlite', db_path=':memory:')
        assert conn is not None
        assert conn.in_use is True
        
        await pool_manager.return_connection('sqlite', conn)
        # Connection should be back in pool
        
    @pytest.mark.asyncio
    async def test_connection_reuse(self, pool_manager):
        # Test that connections are reused
        conn1 = await pool_manager.get_connection('sqlite', db_path=':memory:')
        await pool_manager.return_connection('sqlite', conn1)
        
        conn2 = await pool_manager.get_connection('sqlite', db_path=':memory:')
        assert conn1 is conn2  # Should be the same connection
        
    @pytest.mark.asyncio
    async def test_max_connections_limit(self, pool_manager):
        # Test that max connections limit is enforced
        conn1 = await pool_manager.get_connection('sqlite', db_path=':memory:')
        conn2 = await pool_manager.get_connection('sqlite', db_path=':memory:')
        
        # Third connection should raise an exception
        with pytest.raises(Exception):
            await pool_manager.get_connection('sqlite', db_path=':memory:')
            
        await pool_manager.return_connection('sqlite', conn1)
        await pool_manager.return_connection('sqlite', conn2)
```

### 2. Integration Tests

**File**: `tests/integration/test_memory_leak_fix.py`

```python
import pytest
import threading
import time
import psutil
from grizabella.api.client import Grizabella
from grizabella.core.db_manager_factory import DBManagerFactory

class TestMemoryLeakFix:
    
    def test_singleton_db_manager(self):
        """Test that DBManager factory returns singletons"""
        db_path = "test_singleton_db"
        
        # Clean up any existing instances
        DBManagerFactory.cleanup_manager(db_path)
        
        # Create multiple clients
        client1 = Grizabella(db_path)
        client2 = Grizabella(db_path)
        
        # Should get the same DBManager instance
        assert id(client1._db_manager) == id(client2._db_manager)
        
        # Clean up
        client1.close()
        client2.close()
        DBManagerFactory.cleanup_manager(db_path)
        
    def test_thread_safety(self):
        """Test thread safety of connection management"""
        db_path = "test_thread_safety_db"
        results = []
        
        def create_client():
            try:
                client = Grizabella(db_path)
                # Perform some operations
                client.list_object_types()
                results.append(True)
                client.close()
            except Exception as e:
                results.append(False)
                
        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_client)
            threads.append(thread)
            thread.start()
            
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            
        # All operations should succeed
        assert all(results)
        
        # Clean up
        DBManagerFactory.cleanup_manager(db_path)
        
    def test_memory_usage_stability(self):
        """Test that memory usage remains stable over multiple operations"""
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        db_path = "test_memory_stability_db"
        
        # Perform multiple create/close cycles
        for _ in range(10):
            client = Grizabella(db_path)
            client.list_object_types()
            client.close()
            
        # Force garbage collection
        import gc
        gc.collect()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be minimal (less than 50MB)
        assert memory_increase < 50 * 1024 * 1024, f"Memory increased by {memory_increase // 1024 // 1024}MB"
        
        # Clean up
        DBManagerFactory.cleanup_manager(db_path)
```

This implementation specification provides concrete, actionable steps for implementing the comprehensive connection management solution. Each component is designed to be testable, maintainable, and backward-compatible while addressing the core memory leak and threading issues.