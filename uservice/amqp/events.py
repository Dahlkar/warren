from inspect import isclass
from contextlib import AsyncExitStack
from typing import Callable, Any, AsyncGenerator

from aio_pika import IncomingMessage, Connection, Message
from pydantic import BaseModel, ValidationError

from uservice.contexts import ServiceContext
from uservice.utils import create_field, serialize_payload
from .consumer import AmqpConsumer


EVENT_HANDLER_QUEUE = 'uservice-{}-{}-{}'


class AmqpEventHandler(AmqpConsumer):
    def __init__(
            self,
            *,
            context: ServiceContext,
            call: Callable,
            exchange_name: str,
            routing_key: str,
    ):
        super().__init__(context=context, call=call)
        self.exchange_name = exchange_name
        self.routing_key = routing_key
        self
        try:
            self.payload_type = self.dependant.required_params['payload'].annotation
        except KeyError:
            raise ValueError('Event handler function is missing required arugment "payload"')

    def get_exchange_name(self) -> str:
        return self.exchange_name

    def get_routing_key(self) -> str:
        return self.routing_key

    def get_queue_name(self) -> str:
        return EVENT_HANDLER_QUEUE.format(
            self.get_exchange_name(),
            self.get_routing_key(),
            self.dependant.name,
        )

    async def _handle_message(
            self,
            stack: AsyncExitStack,
            payload: Any,
            message: IncomingMessage,
    ) -> None:
        if isclass(self.payload_type) and issubclass(self.payload_type, BaseModel):
            try:
                payload = self.payload_type(**payload)
            except ValidationError as e:
                await message.ack()
                raise e

        params = await self.dependant.prepare_params(
            stack, {
                'payload': payload,
                'connection': self.connection,
                'context': self.context,
        })
        await self.dependant.call(**params)
        await message.ack()


class AmqpEventPublisher:
    def __init__(
            self,
            *,
            publish_model: Any = None,
    ):
        self.field = None
        if publish_model:
            self.field = create_field(
                name='publish_model',
                type_=publish_model,
            )

    async def __call__(
            self,
            connection: Connection,
            context: ServiceContext,
    ) -> AsyncGenerator[Callable, None]:
        channel = await connection.channel()
        exchange = await channel.get_exchange(context.name)

        async def publish(routing_key: str, payload: Any):
            body = serialize_payload(
                field=self.field,
                payload_content=payload,
            )
            await exchange.publish(Message(body), routing_key)

        try:
            yield publish
        finally:
            await channel.close()
