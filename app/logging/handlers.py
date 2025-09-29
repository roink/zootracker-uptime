"""Custom logging handlers used by the application."""

from __future__ import annotations

import os
from logging.handlers import WatchedFileHandler


class SecureWatchedFileHandler(WatchedFileHandler):
    """File handler enforcing restrictive file permissions."""

    def _open(self):  # noqa: D401
        stream = super()._open()
        try:
            os.chmod(self.baseFilename, 0o600)
        except OSError:
            pass
        return stream
