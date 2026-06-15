"""
Infrastructure connectivity verification tests.
Ensures Redis and Supabase are reachable under active configurations.
Skips if environment variables are not loaded.
"""

import pytest
import redis
from config import settings, supabase

def test_redis_connection():
    """Verify that Redis is running and reachable."""
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        assert r.ping() is True
    except redis.ConnectionError as e:
        pytest.fail(f"Could not connect to Redis at {settings.REDIS_URL}: {e}")

def test_supabase_connection():
    """Verify that Supabase can be contacted if credentials are provided."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        pytest.skip("Supabase environment variables are missing; skipping connectivity test.")

    try:
        # Perform a cheap select on the customers table
        res = supabase.table("customers").select("id").limit(1).execute()
        assert hasattr(res, "data")
    except Exception as e:
        pytest.fail(f"Supabase connection test failed: {e}")
