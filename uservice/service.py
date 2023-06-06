import logging
import asyncio
import signal
import threading
from typing import Optional, NoReturn, Callable, Any, List
from aio_pika import Connection, connect
from .amqp.events import AmqpEventHandler
from .amqp.rpc import AmqpRpc
from .settings import get_settings, Settings
from .contexts import ServiceContext
from .entrypoints import Entrypoint


HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)

logger = logging.getLogger('uservice')


class Service:
    def __init__(
            self,
            *,
            name: str,
            settings: Optional[Settings] = None,
    ):
        if settings is None:
            _settings = get_settings()

        self.entrypoints: List[Entrypoint] = []
        self.init_context(name, settings or _settings)

    def init_context(self, name: str, settings: Settings) -> None:
        self.context = ServiceContext(
            name=name,
            settings=settings,
        )

    def handle_exit(self, sig, frame) -> None:
        self.is_running = False

    async def run(self) -> None:
        connection = await connect(self.context.settings.amqp.get_url())
        async with connection:
            await self.setup(connection)
            await self.start()
            await self.loop()
            await self.stop()

    async def loop(self) -> None:
        while self.is_running:
            await asyncio.sleep(0.1)

    async def setup(self, connection: Connection) -> None:
        self.install_signal_handlers()
        for entrypoint in self.entrypoints:
            await entrypoint.setup(connection)

    async def start(self) -> None:
        for entrypoint in self.entrypoints:
            await entrypoint.start()

        self.is_running = True

    async def stop(self) -> None:
        for entrypoint in self.entrypoints:
            await entrypoint.stop()

    def event_handler(
            self,
            exchange: str,
            queue: str,
    ) -> Callable:
        def decorator(func: Callable) -> None:
            self.entrypoints.append(
                AmqpEventHandler(
                    context=self.context,
                    call=func,
                    exchange_name=exchange,
                    routing_key=queue,
                )
            )
            return func

        return decorator

    def rpc(
            self,
            *,
            response_model: Optional[Any] = None,
    ) -> Callable:
        def decorator(func: Callable, *args, **kwargs) -> None:
            self.entrypoints.append(
                AmqpRpc(
                    context=self.context,
                    call=func,
                    response_model=response_model,
                )
            )

        return decorator

    def install_signal_handlers(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            # Signals can only be listened to from the main thread.
            return

        loop = asyncio.get_event_loop()

        try:
            for sig in HANDLED_SIGNALS:
                loop.add_signal_handler(sig, self.handle_exit, sig, None)
        except NotImplementedError:  # pragma: no cover
            # Windows
            for sig in HANDLED_SIGNALS:
                signal.signal(sig, self.handle_exit)
