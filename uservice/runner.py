import asyncio
import signal


from .importer import import_from_string
from .service import Service

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)

class ServiceRunner:
    def __init__(
            self,
            *,
            service_str,
    ):
        self.service_str = service_str


    def load(self):
        self.loaded_service: Service = import_from_string(self.service_str)

    def run(self):
        self.load()
        return asyncio.run(self.loaded_service.run())
