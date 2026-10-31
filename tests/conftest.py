import os

# Tests use their own JWT key so the "insecure dev key" warning stays quiet.
os.environ.setdefault("BIKECHECK_SECRET", "test-secret-key-for-pytest-only-0123456789")
