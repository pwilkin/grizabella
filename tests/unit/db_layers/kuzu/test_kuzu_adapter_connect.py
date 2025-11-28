import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import logging

# Ensure kuzu is importable, or mock it if not available in the test environment
try:
    import real_ladybug as kuzu
except ImportError:
    kuzu = MagicMock()

from grizabella.db_layers.kuzu.kuzu_adapter import KuzuAdapter

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

    @patch('real_ladybug.Database')
    @patch('real_ladybug.Connection')
    def test_connect_with_existing_lockfile(self, mock_kuzu_connection, mock_kuzu_database):
        """Test that _connect removes an existing lockfile and connects."""
        logger.info("TestKuzuAdapterConnect: Running test_connect_with_existing_lockfile")
        # Arrange
        # Create a dummy lock file with correct pattern matching
        expected_db_path_with_ext = self.db_path + ".db"
        lock_file_path = expected_db_path_with_ext + ".lock"
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
        mock_kuzu_database.assert_called_once_with(expected_db_path_with_ext)
        mock_kuzu_connection.assert_called_once_with(mock_db_instance)
        self.assertIsNotNone(adapter.db, "Database object should be set.")
        self.assertIsNotNone(adapter.conn, "Connection object should be set.")
        logger.info("TestKuzuAdapterConnect: test_connect_with_existing_lockfile PASSED")

    @patch('real_ladybug.Database')
    @patch('real_ladybug.Connection')
    def test_connect_no_lockfile(self, mock_kuzu_connection, mock_kuzu_database):
        """Test that _connect works correctly when no lockfile is present."""
        logger.info("TestKuzuAdapterConnect: Running test_connect_no_lockfile")
        # Arrange
        expected_db_path_with_ext = self.db_path + ".db"
        lock_file_path = expected_db_path_with_ext + ".lock"
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
        mock_kuzu_database.assert_called_once_with(expected_db_path_with_ext)
        mock_kuzu_connection.assert_called_once_with(mock_db_instance)
        self.assertIsNotNone(adapter.db, "Database object should be set.")
        self.assertIsNotNone(adapter.conn, "Connection object should be set.")
        logger.info("TestKuzuAdapterConnect: test_connect_no_lockfile PASSED")

if __name__ == "__main__":
    unittest.main()
