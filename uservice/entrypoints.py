from typing import Callable
from .dependencies import Dependant
from .contexts import ServiceContext


class Entrypoint:
    def __init__(
            self,
            *,
            context: ServiceContext,
            call: Callable,
    ):
        self.context = context
        self.dependant = Dependant(call=call)

    async def setup(self, *args, **kwargs) -> None:
        raise NotImplementedError

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError
