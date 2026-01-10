"""
Queue module for async entity extraction via Redis workers.
"""

from .redis_client import RedisClient
from .models import ExtractionJob, ExtractionResult

__all__ = ['RedisClient', 'ExtractionJob', 'ExtractionResult']
