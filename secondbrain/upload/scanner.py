import io
from abc import ABC, abstractmethod


class IngestionScanner(ABC):
    @abstractmethod
    async def scan(self, raw: bytes) -> bool:
        """Return True if the content is clean."""


class NoOpScanner(IngestionScanner):
    """Dev-only placeholder. TODO: swap for ClamdScanner before any non-local deploy."""

    async def scan(self, raw: bytes) -> bool:
        return True


class ClamdScanner(IngestionScanner):
    def __init__(self, host: str = "localhost", port: int = 3310):
        import clamd

        self._cd = clamd.ClamdNetworkSocket(host=host, port=port)

    async def scan(self, raw: bytes) -> bool:
        result = self._cd.instream(io.BytesIO(raw))
        return result["stream"][0] == "OK"


_scanner: IngestionScanner = NoOpScanner()


def get_scanner() -> IngestionScanner:
    return _scanner
