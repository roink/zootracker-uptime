"""Custom logging handlers used by the application."""

from __future__ import annotations

import os
from contextlib import suppress
from io import TextIOWrapper
from logging.handlers import WatchedFileHandler


class SecureWatchedFileHandler(WatchedFileHandler):
    """File handler enforcing restrictive file permissions."""

    def _open(self) -> TextIOWrapper:  # noqa: D401
        stream = super()._open()
        with suppress(OSError):
            os.chmod(self.baseFilename, 0o600)
        return stream
