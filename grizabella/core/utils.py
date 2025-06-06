"""Grizabella Core Utility Functions."""

import uuid
from datetime import datetime, timezone


def generate_uuid() -> uuid.UUID:
    """Generates a new UUID."""
    return uuid.uuid4()

def get_current_utc_timestamp() -> datetime:
    """Returns the current UTC timestamp."""
    return datetime.now(timezone.utc)

# Add other general utility functions here as needed.
