import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import logging

# Ensure kuzu is importable, or mock it if not available in the test environment
try:
    import kuzu
except ImportError:
    kuzu = MagicMock()

from grizabella.db_layers.kuzu.kuzu_adapter import KuzuAdapter
from grizabella.core.exceptions import DatabaseError

# Configure logging for tests (optional, but can be helpful for debugging)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestKuzuAdapterConnect(unittest.TestCase):
    """Tests for KuzuAdapter connection logic, specifically lockfile handling."""

    def setUp(self):
        """Set up a temporary directory for the Kuzu database for each test."""
        self.test_dir = tempfile.mkdtemp()
        # It's good practice to ensure the path Kuzu will use actually exists
        # even if Kuzu itself creates subdirectories.
        self.db_path = os.path.join(self.test_dir, "test_kuzu_db")
        os.makedirs(self.db_path, exist_ok=True)
        logger.info(f"TestKuzuAdapterConnect: setUp created db_path: {self.db_path}")


    def tearDown(self):
        """Clean up the temporary directory after each test."""
        # First, ensure any adapter instances are closed if they were created
        # This is a bit tricky as the adapter might not be stored on self directly in all tests
        # For now, we rely on shutil.rmtree to clean up.
        # If tests start failing due to open file handles on Windows, we might need explicit close calls.
        shutil.rmtree(self.test_dir)
        logger.info(f"TestKuzuAdapterConnect: tearDown removed test_dir: {self.test_dir}")

    @patch('kuzu.Database')
    @patch('kuzu.Connection')
    def test_connect_with_existing_lockfile(self, mock_kuzu_connection, mock_kuzu_database):
        """Test that _connect removes an existing lockfile and connects."""
        logger.info("TestKuzuAdapterConnect: Running test_connect_with_existing_lockfile")
        # Arrange
        # Create a dummy lock file
        lock_file_path = os.path.join(self.db_path, ".lock") # Corrected lock file name
        with open(lock_file_path, "w", encoding="utf-8") as f:
            f.write("dummy lock content")
        self.assertTrue(os.path.exists(lock_file_path))
        logger.info(f"TestKuzuAdapterConnect: Created dummy lock file at {lock_file_path}")

        mock_db_instance = MagicMock()
        mock_kuzu_database.return_value = mock_db_instance
        mock_kuzu_connection.return_value = MagicMock()

        adapter = KuzuAdapter(db_path=self.db_path)

        # Act
        # _connect is called during KuzuAdapter instantiation via super().__init__()
        # No explicit call to adapter._connect() needed here.

        # Assert
        self.assertFalse(os.path.exists(lock_file_path), "Lockfile should have been removed.")
        logger.info(f"TestKuzuAdapterConnect: Verified lock file was removed from {lock_file_path}")
        mock_kuzu_database.assert_called_once_with(self.db_path)
        mock_kuzu_connection.assert_called_once_with(mock_db_instance)
        self.assertIsNotNone(adapter.db, "Database object should be set.")
        self.assertIsNotNone(adapter.conn, "Connection object should be set.")
        logger.info("TestKuzuAdapterConnect: test_connect_with_existing_lockfile PASSED")

    @patch('kuzu.Database')
    @patch('kuzu.Connection')
    def test_connect_no_lockfile(self, mock_kuzu_connection, mock_kuzu_database):
        """Test that _connect works correctly when no lockfile is present."""
        logger.info("TestKuzuAdapterConnect: Running test_connect_no_lockfile")
        # Arrange
        lock_file_path = os.path.join(self.db_path, ".lock") # Corrected lock file name
        self.assertFalse(os.path.exists(lock_file_path)) # Ensure no lock file exists
        logger.info(f"TestKuzuAdapterConnect: Verified no lock file at {lock_file_path}")

        mock_db_instance = MagicMock()
        mock_kuzu_database.return_value = mock_db_instance
        mock_kuzu_connection.return_value = MagicMock()

        adapter = KuzuAdapter(db_path=self.db_path)

        # Act
        # _connect is called during KuzuAdapter instantiation.

        # Assert
        self.assertFalse(os.path.exists(lock_file_path), "Lockfile should still not exist.")
        logger.info(f"TestKuzuAdapterConnect: Verified lock file still does not exist at {lock_file_path}")
        mock_kuzu_database.assert_called_once_with(self.db_path)
        mock_kuzu_connection.assert_called_once_with(mock_db_instance)
        self.assertIsNotNone(adapter.db, "Database object should be set.")
        self.assertIsNotNone(adapter.conn, "Connection object should be set.")
        logger.info("TestKuzuAdapterConnect: test_connect_no_lockfile PASSED")

    @patch('kuzu.Database')
    @patch('kuzu.Connection')
    @patch('os.remove')
    def test_connect_lockfile_removal_fails(self, mock_os_remove, mock_kuzu_connection, mock_kuzu_database):
        """Test connection proceeds if lockfile removal fails, but logs a warning."""
        logger.info("TestKuzuAdapterConnect: Running test_connect_lockfile_removal_fails")
        # Arrange
        lock_file_path = os.path.join(self.db_path, ".lock") # Corrected lock file name
        with open(lock_file_path, "w", encoding="utf-8") as f:
            f.write("dummy lock content")
        self.assertTrue(os.path.exists(lock_file_path))
        logger.info(f"TestKuzuAdapterConnect: Created dummy lock file at {lock_file_path}")

        mock_os_remove.side_effect = OSError("Permission denied")
        mock_db_instance = MagicMock()
        mock_kuzu_database.return_value = mock_db_instance
        mock_kuzu_connection.return_value = MagicMock()

        # adapter = KuzuAdapter(db_path=self.db_path) # Removed: Instantiation will happen in assertLogs

        # Act & Assert
        adapter = None # Ensure adapter is defined in the outer scope
        with self.assertLogs(logger='grizabella.db_layers.kuzu.kuzu_adapter', level='WARNING') as cm:
            # _connect is called during KuzuAdapter instantiation.
            adapter = KuzuAdapter(db_path=self.db_path) # This is the call we are testing
            # Check that the warning message was logged
            self.assertTrue(any(f"Could not remove lock file: {lock_file_path}" in message for message in cm.output))
            logger.info(f"TestKuzuAdapterConnect: Verified warning log for failed lock file removal from {lock_file_path}")

        # Assertions after instantiation
        self.assertIsNotNone(adapter, "Adapter should have been instantiated.")
        mock_kuzu_database.assert_called_once_with(self.db_path) # kuzu.Database is called by _connect
        mock_kuzu_connection.assert_called_once_with(mock_db_instance) # kuzu.Connection is called by _connect
        self.assertTrue(os.path.exists(lock_file_path), "Lockfile should still exist as removal failed.")
        logger.info(f"TestKuzuAdapterConnect: Verified lock file still exists at {lock_file_path}")
        logger.info("TestKuzuAdapterConnect: test_connect_lockfile_removal_fails PASSED")

    @patch('kuzu.Database')
    def test_connect_kuzu_database_creation_fails(self, mock_kuzu_database):
        """Test that DatabaseError is raised if kuzu.Database fails."""
        logger.info("TestKuzuAdapterConnect: Running test_connect_kuzu_database_creation_fails")
        # Arrange
        mock_kuzu_database.side_effect = Exception("Kuzu internal error")
        # adapter = KuzuAdapter(db_path=self.db_path) # Removed: Instantiation will happen in assertRaises

        # Act & Assert
        with self.assertRaises(DatabaseError) as context:
            # _connect is called during KuzuAdapter instantiation.
            adapter = KuzuAdapter(db_path=self.db_path)
        self.assertIn("KuzuDB connection error", str(context.exception))
        self.assertIn("Kuzu internal error", str(context.exception))
        logger.info(f"TestKuzuAdapterConnect: Verified DatabaseError on kuzu.Database failure: {context.exception}")
        logger.info("TestKuzuAdapterConnect: test_connect_kuzu_database_creation_fails PASSED")

    @patch('kuzu.Database') # Mock Database to control its return value
    @patch('kuzu.Connection') # Mock Connection
    def test_connect_with_wal_directory(self, mock_kuzu_connection, mock_kuzu_database):
        """Test connection proceeds when a WAL directory exists, and logs its presence."""
        logger.info("TestKuzuAdapterConnect: Running test_connect_with_wal_directory")
        # Arrange
        wal_dir_path = os.path.join(self.db_path, "wal")
        os.makedirs(wal_dir_path, exist_ok=True)
        # Optionally, create a dummy file inside WAL to simulate actual WAL files
        with open(os.path.join(wal_dir_path, "dummy.walfile"), "w", encoding="utf-8") as f:
            f.write("dummy wal content")
        self.assertTrue(os.path.isdir(wal_dir_path))
        logger.info(f"TestKuzuAdapterConnect: Created dummy WAL directory at {wal_dir_path}")

        mock_db_instance = MagicMock()
        mock_kuzu_database.return_value = mock_db_instance
        mock_kuzu_connection.return_value = MagicMock()

        # adapter = KuzuAdapter(db_path=self.db_path) # Moved into assertLogs

        # Act & Assert
        adapter = None # Ensure adapter is defined in the outer scope
        with self.assertLogs(logger='grizabella.db_layers.kuzu.kuzu_adapter', level='INFO') as cm:
            adapter = KuzuAdapter(db_path=self.db_path) # Instantiation calls _connect
            # Check that the WAL directory detection was logged
            self.assertTrue(any(f"Found WAL directory: {wal_dir_path}" in message for message in cm.output))
            logger.info(f"TestKuzuAdapterConnect: Verified log for WAL directory presence at {wal_dir_path}")

        # Assertions after instantiation
        self.assertIsNotNone(adapter, "Adapter should have been instantiated.")
        mock_kuzu_database.assert_called_once_with(self.db_path)
        mock_kuzu_connection.assert_called_once_with(mock_db_instance)
        self.assertIsNotNone(adapter.db)
        self.assertIsNotNone(adapter.conn)
        logger.info("TestKuzuAdapterConnect: test_connect_with_wal_directory PASSED")


if __name__ == "__main__":
    unittest.main()
