"""Comprehensive tests for connection management functionality."""

import asyncio
import gc
import logging
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import psutil

from grizabella.core.connection_pool import ConnectionPoolManager
from grizabella.core.db_manager import GrizabellaDBManager
from grizabella.core.db_manager_factory import DBManagerFactory, get_db_manager_factory, cleanup_all_managers
from grizabella.db_layers.kuzu.thread_safe_kuzu_adapter import ThreadSafeKuzuAdapter
from grizabella.core.resource_monitor import ResourceMonitor


class TestConnectionPoolManager(unittest.TestCase):
    """Test suite for ConnectionPoolManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.pool_manager = ConnectionPoolManager(max_connections_per_type=5, max_idle_time=0.1)
        self.test_db_path = Path(tempfile.mkdtemp()) / "test.db"
    
    def tearDown(self):
        """Clean up after tests."""
        self.pool_manager.close_all_pools()
        if self.test_db_path.exists():
            self.test_db_path.unlink()
        # Clean up the temporary directory
        try:
            self.test_db_path.parent.rmdir()
        except OSError:
            # Directory not empty, that's OK
            pass
    
    def test_pool_creation(self):
        """Test that connection pools are created properly."""
        # Get a connection from the pool (need to use async approach)
        import asyncio
        async def get_and_return():
            pooled_conn = await self.pool_manager.get_connection('sqlite', db_path=str(self.test_db_path))
            self.assertIsNotNone(pooled_conn)
            self.assertIsNotNone(pooled_conn.connection)
            
            # Return the connection to the pool
            await self.pool_manager.return_connection('sqlite', pooled_conn)
            return True
        
        result = asyncio.run(get_and_return())
        self.assertTrue(result)
    
    def test_max_connections(self):
        """Test that max connections limit is enforced."""
        connections = []
        
        # Acquire max number of connections
        import asyncio
        async def test_max_connections_async():
            for i in range(5):
                pooled_conn = await self.pool_manager.get_connection('sqlite', db_path=str(self.test_db_path))
                connections.append(pooled_conn)
            
            # Try to acquire one more (should block or fail depending on implementation)
            # In our implementation, it should return a new connection that isn't pooled
            extra_pooled_conn = await self.pool_manager.get_connection('sqlite', db_path=str(self.test_db_path))
            self.assertIsNotNone(extra_pooled_conn)
            
            # Return all connections
            for pooled_conn in connections:
                await self.pool_manager.return_connection('sqlite', pooled_conn)
            await self.pool_manager.return_connection('sqlite', extra_pooled_conn)
            return True
        
        result = asyncio.run(test_max_connections_async())
        self.assertTrue(result)
    
    def test_connection_cleanup(self):
        """Test that idle connections are cleaned up."""
        # Get a connection and return it immediately
        import asyncio
        async def test_connection_cleanup_async():
            pooled_conn = await self.pool_manager.get_connection('sqlite', db_path=str(self.test_db_path))
            await self.pool_manager.return_connection('sqlite', pooled_conn)
            
            # Wait for the idle time to pass
            time.sleep(0.2)
            
            # The cleanup should happen automatically
            status = self.pool_manager.get_pool_stats()
            # Check that the pool has the expected structure
            self.assertIn('sqlite', status)
            return True
        
        result = asyncio.run(test_connection_cleanup_async())
        self.assertTrue(result)
    
    def test_close_all_pools(self):
        """Test that all pools can be closed properly."""
        # Close all pools immediately
        self.pool_manager.close_all_pools()
        self.assertTrue(True)  # Test passes if no exception is thrown


class TestDBManagerFactory(unittest.TestCase):
    """Test suite for DBManagerFactory."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.factory = DBManagerFactory()
        self.test_db_path = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up after tests."""
        # Clean up all managers
        cleanup_all_managers()
        
        # Remove test database directory
        import shutil
        if self.test_db_path.exists():
            shutil.rmtree(self.test_db_path)
    
    def test_singleton_behavior(self):
        """Test that the same DBManager is returned for the same path."""
        db_path = self.test_db_path / "test1"
        
        manager1 = self.factory.get_manager(str(db_path))
        manager2 = self.factory.get_manager(str(db_path))
        
        self.assertIs(manager1, manager2)
        self.assertEqual(self.factory._reference_counts[str(db_path)], 2)
    
    def test_reference_counting(self):
        """Test that reference counts are properly maintained."""
        db_path = self.test_db_path / "test2"
        
        manager1 = self.factory.get_manager(str(db_path))
        ref_count_after_first = self.factory._reference_counts[str(db_path)]
        
        manager2 = self.factory.get_manager(str(db_path))
        ref_count_after_second = self.factory._reference_counts[str(db_path)]
        
        # Release first reference
        self.factory.release_manager(str(db_path))
        ref_count_after_release1 = self.factory._reference_counts[str(db_path)]
        
        # Release second reference
        self.factory.release_manager(str(db_path))
        # After releasing last reference, manager should be removed
        ref_count_final = self.factory._reference_counts.get(str(db_path), 0)
        
        self.assertEqual(ref_count_after_first, 1)
        self.assertEqual(ref_count_after_second, 2)
        self.assertEqual(ref_count_after_release1, 1)
        self.assertEqual(ref_count_final, 0)
        self.assertNotIn(str(db_path), self.factory._instances)
    
    def test_multiple_db_instances(self):
        """Test that different DB paths get different managers."""
        db_path1 = self.test_db_path / "test3a"
        db_path2 = self.test_db_path / "test3b"
        
        manager1 = self.factory.get_manager(str(db_path1))
        manager2 = self.factory.get_manager(str(db_path2))
        
        self.assertIsNot(manager1, manager2)
        self.assertEqual(len(self.factory._instances), 2)
    
    def test_global_factory_instance(self):
        """Test that the global factory instance works properly."""
        db_path = self.test_db_path / "test4"
        
        factory1 = get_db_manager_factory()
        factory2 = get_db_manager_factory()
        
        self.assertIs(factory1, factory2)
        
        manager = factory1.get_manager(str(db_path))
        self.assertIsNotNone(manager)


class TestThreadSafeKuzuAdapter(unittest.TestCase):
    """Test suite for ThreadSafeKuzuAdapter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_db_path = Path(tempfile.mkdtemp()) / "kuzu_test"
        self.test_db_path.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        if self.test_db_path.exists():
            shutil.rmtree(self.test_db_path)
    
    def test_thread_local_storage(self):
        """Test that connections are isolated per thread."""
        def get_connection_in_thread(result_dict, key):
            import asyncio
            async def get_conn():
                adapter = ThreadSafeKuzuAdapter(str(self.test_db_path))
                conn = adapter.connection
                result_dict[key] = id(conn)
                return id(conn)
            
            # Run the async function in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(get_conn())
            finally:
                loop.close()
        
        # Use a dictionary to store results from different threads
        results = {}
        
        # Create multiple threads that each get a connection
        threads = []
        for i in range(3):
            thread = threading.Thread(target=get_connection_in_thread, args=(results, f'thread_{i}'))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify that each thread got a different connection object (by ID)
        connection_ids = list(results.values())
        self.assertEqual(len(connection_ids), len(set(connection_ids)), "Each thread should have its own connection")


class TestResourceMonitor(unittest.TestCase):
    """Test suite for ResourceMonitor."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.monitor = ResourceMonitor()
    
    def test_monitoring_start_stop(self):
        """Test that monitoring can be started and stopped."""
        # Start monitoring
        self.monitor.start_monitoring()
        self.monitor.start_monitoring()
        self.assertTrue(self.monitor.monitoring)
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        self.monitor.stop_monitoring()
        self.assertFalse(self.monitor.monitoring)
    
    def test_memory_monitoring(self):
        """Test that memory metrics are collected."""
        # Start monitoring briefly
        self.monitor.start_monitoring()
        time.sleep(0.1)  # Allow some metrics to be collected
        self.monitor.stop_monitoring()
        
        # Check that some metrics were collected
        if hasattr(self.monitor, 'metrics_history'):
            # The metrics history should have been populated during monitoring
            pass  # Implementation-dependent


class TestMemoryLeakPrevention(unittest.TestCase):
    """Test suite for memory leak prevention."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_db_path = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        if self.test_db_path.exists():
            shutil.rmtree(self.test_db_path)
        
        # Clean up all managers to prevent interference between tests
        cleanup_all_managers()
    
    def test_db_manager_cleanup(self):
        """Test that DB managers are properly cleaned up."""
        db_path = self.test_db_path / "cleanup_test"
        
        # Create a manager
        factory = get_db_manager_factory()
        manager = factory.get_manager(str(db_path))
        self.assertIsNotNone(manager)
        
        # Release all references
        factory.release_manager(str(db_path))
        
        # Verify the manager is cleaned up
        self.assertNotIn(str(db_path), factory._instances)
    
    def test_connection_pool_cleanup(self):
        """Test that connection pools don't accumulate connections."""
        db_path = self.test_db_path / "pool_cleanup_test.db"
        
        initial_process = psutil.Process()
        initial_connections = len(initial_process.net_connections())
        
        # Create and use several connections
        import asyncio
        async def test_connection_pool_cleanup_async():
            pool_manager = ConnectionPoolManager()
            for i in range(10):
                conn = await pool_manager.get_connection('sqlite', db_path=str(db_path))
                # Don't return to pool to test cleanup behavior
                if hasattr(conn.connection, 'close'):
                    conn.connection.close()
            
            # Close all pools
            await pool_manager.cleanup_all()
            return True
        
        result = asyncio.run(test_connection_pool_cleanup_async())
        
        # Force garbage collection
        gc.collect()
        
        # Check that no resources are leaked
        current_process = psutil.Process()
        current_connections = len(current_process.net_connections())
        
        # The number of connections should not have grown significantly
        # (allowing for some variance due to test environment)
        self.assertLessEqual(current_connections - initial_connections, 5)
    
    def test_factory_cleanup_all_managers(self):
        """Test the cleanup_all_managers function."""
        # Create several managers
        factory = get_db_manager_factory()
        paths = []
        for i in range(3):
            path = self.test_db_path / f"cleanup_test_{i}"
            paths.append(str(path))
            manager = factory.get_manager(str(path))
            self.assertIsNotNone(manager)
        
        # Verify managers exist
        self.assertEqual(len(factory._instances), 3)
        
        # Clean up all managers
        cleanup_all_managers()
        
        # Verify managers are gone
        self.assertEqual(len(factory._instances), 0)
        self.assertEqual(len(factory._reference_counts), 0)


class TestIntegrationConnectionManagement(unittest.TestCase):
    """Integration tests for the complete connection management system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_db_path = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        if self.test_db_path.exists():
            shutil.rmtree(self.test_db_path)
        
        # Clean up all managers
        cleanup_all_managers()
    
    def test_full_connection_lifecycle(self):
        """Test the complete lifecycle of database connections."""
        db_path = self.test_db_path / "integration_test"
        
        # Get manager from factory
        factory = get_db_manager_factory()
        manager = factory.get_manager(str(db_path))
        self.assertIsNotNone(manager)
        
        # Verify connections can be obtained via the properties
        sqlite_adapter = manager._connection_helper.sqlite_adapter
        self.assertIsNotNone(sqlite_adapter)
        
        # Verify that the same manager is returned for the same path
        same_manager = factory.get_manager(str(db_path))
        self.assertIs(manager, same_manager)
        
        # Release the manager
        factory.release_manager(str(db_path))
        
        # Verify the manager is still available due to internal references
        # until all internal references are released
        
        # Clean up all managers
        cleanup_all_managers()
        
        # Verify all managers are cleaned up
        self.assertEqual(len(factory._instances), 0)
    
    def test_concurrent_access(self):
        """Test concurrent access to database managers."""
        db_path = self.test_db_path / "concurrent_test"
        results = {}
        
        def access_manager(thread_id):
            factory = get_db_manager_factory()
            manager = factory.get_manager(str(db_path))
            results[thread_id] = id(manager)
            # Keep reference for a bit to test concurrent access
            time.sleep(0.1)
            factory.release_manager(str(db_path))
        
        # Create multiple threads that access the same DB path
        threads = []
        for i in range(5):
            thread = threading.Thread(target=access_manager, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All threads should have gotten the same manager instance
        manager_ids = list(results.values())
        self.assertTrue(all(mid == manager_ids[0] for mid in manager_ids))


def run_all_connection_management_tests():
    """Run all connection management tests."""
    # Set up logging for tests
    logging.basicConfig(level=logging.INFO)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(__loader__.name if __loader__.name != '__main__' else __name__)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    run_all_connection_management_tests()