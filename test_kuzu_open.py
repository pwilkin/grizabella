import kuzu
import logging
import os

# Configure basic logging to see output from this script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("kuzu_test")

# Get the Kuzu database path from an environment variable or use default
kuzu_db_dir = os.getenv("GRIZABELLA_KUZU_TEST_PATH", "/home/ilintar/.grizabella/test/kuzu_data")

logger.info(f"Attempting to open Kuzu database at: {kuzu_db_dir}")

try:
    # Attempt to create/open the database
    db = kuzu.Database(kuzu_db_dir)
    logger.info(f"Successfully created/opened Kuzu database object: {db}")

    # Attempt to create a connection
    conn = kuzu.Connection(db)
    logger.info(f"Successfully created Kuzu connection object: {conn}")

    logger.info("Kuzu test script completed successfully.")

except Exception as e:
    logger.error(f"Error during Kuzu database/connection test: {e}", exc_info=True)


