"""Enhanced MCP server with proper resource cleanup and monitoring."""
import asyncio
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastmcp import MCP, tool
from pydantic import BaseModel

from grizabella.core.db_manager_factory import get_db_manager_factory, cleanup_all_managers
from grizabella.core.resource_monitor import start_global_monitoring, stop_global_monitoring
from grizabella.core.connection_pool import ConnectionPoolManager


logger = logging.getLogger(__name__)


class HealthCheckResult(BaseModel):
    """Result of health check."""
    status: str
    message: str
    details: Dict[str, Any]


class EnhancedMCPServer:
    """Enhanced MCP server with proper resource management and cleanup."""
    
    def __init__(self):
        self.mcp = MCP()
        self._shutdown_handlers: List[callable] = []
        self._cleanup_lock = threading.Lock()
        self._is_shutting_down = False
        self._pool_manager = ConnectionPoolManager()
        
        # Register shutdown signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Register core cleanup handlers
        self._register_cleanup_handlers()
        
        # Start global monitoring
        start_global_monitoring()
    
    def _register_cleanup_handlers(self):
        """Register core cleanup handlers."""
        self._shutdown_handlers.extend([
            self._cleanup_database_connections,
            self._cleanup_temporary_files,
            self._cleanup_memory_resources,
        ])
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(self.shutdown_server())
    
    def _cleanup_database_connections(self):
        """Clean up all database connections."""
        logger.info("Cleaning up database connections...")
        try:
            # Close all connection pools
            self._pool_manager.close_all_pools()
            
            # Cleanup all DB managers
            cleanup_all_managers()
            
            logger.info("Database connections cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during database connection cleanup: {e}")
    
    def _cleanup_temporary_files(self):
        """Clean up temporary files."""
        logger.info("Cleaning up temporary files...")
        try:
            # Clean up any temporary files created during operation
            temp_dirs = [Path.home() / ".grizabella" / "temp"]
            for temp_dir in temp_dirs:
                if temp_dir.exists():
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.info(f"Removed temporary directory: {temp_dir}")
            
            logger.info("Temporary files cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during temporary file cleanup: {e}")
    
    def _cleanup_memory_resources(self):
        """Clean up memory resources."""
        logger.info("Cleaning up memory resources...")
        try:
            import gc
            collected = gc.collect()
            logger.info(f"Garbage collector cleaned up {collected} objects")
        except Exception as e:
            logger.error(f"Error during memory cleanup: {e}")
    
    async def _run_shutdown_handlers(self):
        """Run all registered shutdown handlers."""
        logger.info(f"Running {len(self._shutdown_handlers)} shutdown handlers...")
        for handler in self._shutdown_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                logger.error(f"Error in shutdown handler {handler.__name__}: {e}")
    
    async def shutdown_server(self):
        """Gracefully shutdown the server."""
        with self._cleanup_lock:
            if self._is_shutting_down:
                return
            self._is_shutting_down = True
            
        logger.info("Initiating graceful server shutdown...")
        
        # Run shutdown handlers
        await self._run_shutdown_handlers()
        
        # Stop global monitoring
        stop_global_monitoring()
        
        logger.info("Server shutdown completed")
        
        # Exit the process
        sys.exit(0)
    
    @tool
    async def health_check(self) -> HealthCheckResult:
        """Perform a health check on the server."""
        try:
            # Check if server is in shutdown state
            if self._is_shutting_down:
                return HealthCheckResult(
                    status="unhealthy",
                    message="Server is shutting down",
                    details={"shutdown_in_progress": True}
                )
            
            # Check connection pools
            pool_status = self._pool_manager.get_pool_status()
            
            # Check DB manager factory
            factory = get_db_manager_factory()
            active_managers = len(factory._instances)
            
            return HealthCheckResult(
                status="healthy",
                message="Server is operational",
                details={
                    "connection_pools": pool_status,
                    "active_db_managers": active_managers,
                    "shutdown_in_progress": False
                }
            )
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthCheckResult(
                status="unhealthy",
                message=f"Health check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def run(self, host: str = "localhost", port: int = 3000):
        """Run the MCP server."""
        logger.info(f"Starting enhanced MCP server on {host}:{port}")
        
        try:
            self.mcp.run(
                host=host,
                port=port,
                shutdown_event=threading.Event()  # This will be handled by our signal handlers
            )
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, initiating shutdown...")
            asyncio.run(self.shutdown_server())
        except Exception as e:
            logger.error(f"Error running server: {e}")
            raise


def run_enhanced_server(host: str = "localhost", port: int = 3000):
    """Run the enhanced MCP server."""
    server = EnhancedMCPServer()
    server.run(host=host, port=port)


if __name__ == "__main__":
    run_enhanced_server()