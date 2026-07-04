import ssl

import certifi


def get_ssl_context() -> ssl.SSLContext:
    """Use certifi CA bundle (fixes macOS Python SSL verify errors)."""
    return ssl.create_default_context(cafile=certifi.where())
