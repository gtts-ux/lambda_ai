"""HTTPS trust that also works when frozen outside the Python build machine."""
from functools import lru_cache
import ssl
import certifi


@lru_cache(maxsize=1)
def https_context():
    # Keep OS/custom trust, then add the CA file distributed inside the app.
    # Frozen Python's compiled default CA path can refer to a CI-only location.
    context=ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context
