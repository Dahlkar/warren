import logging
import json

from contextlib import AsyncExitStack

from aio_pika import (
    Connection,
    Queue,
    Exchange,
    ExchangeType,
    Channel,
    IncomingMessage,
)

from uservice.entrypoints import Entrypoint


logger = logging.getLogger('uservice')

EVENT_HANDLER_QUEUE = 'uservice-{}-{}-{}'
RPC_QUEUE = 'rpc-{}'
RPC_REPLY_QUEUE = 'rpc-reply-{}-{}'
RPC_ROUTING_KEY = '{}.{}'


class AmqpConsumer(Entrypoint):
    async def setup(self, connection: Connection) -> None:
        self.connection = connection
        self.channel: Channel = await self.connection.channel()
        self.exchange: Exchange = await self.channel.declare_exchange(
            **self.get_exchange_settings()
        )
        self.queue: Queue = await self.channel.declare_queue(
            **self.get_queue_settings(),
        )
        await self.queue.bind(self.exchange, self.get_routing_key())

    async def start(self) -> None:
        self.consumer_tag = await self.queue.consume(self.handle_message)

    async def stop(self) -> None:
        await self.queue.cancel(self.consumer_tag)
        await self.channel.close()

    async def handle_message(self, message: IncomingMessage) -> None:
        async with AsyncExitStack() as stack:
            body = json.loads(message.body)
            await self._handle_message(stack, body, message)

    async def _handle_message(self, stack, body, message) -> None:
        raise NotImplementedError

    def get_exchange_name(self):
        raise NotImplementedError

    def get_routing_key(self):
        raise NotImplementedError

    def get_queue_name(self):
        raise NotImplementedError

    def get_queue_settings(self):
        return {
            'name': self.get_queue_name(),
            'durable': True,
        }

    def get_exchange_settings(self):
        return {
            'name': self.get_exchange_name(),
            'type': ExchangeType.TOPIC,
            'durable': True,
            'auto_delete': False,
        }
