from __future__ import annotations

import asyncio
import uuid
import json

from typing import Callable, Any, Optional, AsyncGenerator
from contextlib import AsyncExitStack

from aio_pika import IncomingMessage, Connection, Message, Exchange, Channel

from uservice.contexts import ServiceContext
from uservice.utils import serialize_payload
from .consumer import AmqpConsumer


RPC_QUEUE = 'rpc-{}'
RPC_REPLY_QUEUE = 'rpc-reply-{}-{}'
RPC_ROUTING_KEY = '{}.{}'


class AmqpRpc(AmqpConsumer):
    def __init__(
            self,
            *,
            context: ServiceContext,
            call: Callable,
            response_model: Optional[Any],
    ):
        super().__init__(context=context, call=call)
        self.response_model = response_model

    def get_exchange_name(self) -> str:
        return self.context.settings.amqp.rpc_exchange

    def get_routing_key(self) -> str:
        return RPC_ROUTING_KEY.format(self.context.name, self.dependant.name)

    def get_queue_name(self) -> str:
        return RPC_QUEUE.format(self.context.name)

    async def _handle_message(
            self,
            stack: AsyncExitStack,
            body: Any,
            message: IncomingMessage,
    ) -> None:
        reply_to = message.reply_to
        correlation_id = message.correlation_id
        params = await self.dependant.prepare_params(
            stack,
            {
                'connection': self.connection,
                'context': self.context,
                **body['kwargs'],
            })
        result = await self.dependant.call(**params)
        body = serialize_payload(
            field=None,
            payload_content=result,
        )
        response = Message(
            body=body,
            correlation_id=correlation_id,
        )
        await self.exchange.publish(response, reply_to)
        await message.ack()


class AmqpRpcProxy:
    def __init__(
            self,
            *,
            target_service: str,
    ):
        self.target_service = target_service

    async def __call__(
            self,
            connection: Connection,
            context: ServiceContext,
    ) -> AsyncGenerator[ServiceProxy, None]:
        proxy: ServiceProxy
        try:
            channel = await connection.channel()
            exchange = await channel.get_exchange(context.settings.amqp.rpc_exchange)
            proxy = ServiceProxy(
                channel=channel,
                exchange=exchange,
                service_name=context.name,
                target_service=self.target_service,
            )
            yield proxy
        finally:
            await proxy.stop()
            await channel.close()


class ServiceProxy:
    def __init__(
            self,
            *,
            channel: Channel,
            exchange: Exchange,
            service_name: str,
            target_service: str,
    ):

        self.channel = channel
        self.exchange = exchange
        self.service_name = service_name
        self.target_service = target_service

    def __getattr__(self, name) -> MethodProxy:
        self.proxy = MethodProxy(
            channel=self.channel,
            exchange=self.exchange,
            service_name=self.service_name,
            target_service=self.target_service,
            method_name=name,
        )
        return self.proxy

    async def stop(self) -> None:
        await self.proxy.stop()


class MethodProxy:
    def __init__(
            self,
            *,
            channel: Channel,
            exchange: Exchange,
            service_name: str,
            target_service: str,
            method_name: str,
    ):
        self.channel = channel
        self.exchange = exchange
        self.service_name = service_name
        self.target_service = target_service
        self.method_name = method_name

    async def __call__(self, **kwargs) -> Any:
        reply_routing_key = await self.setup_reply_queue()
        body = serialize_payload(
            field=None,
            payload_content={'kwargs': kwargs},
        )
        self.correlation_id = str(uuid.uuid4())
        message = Message(
            body=body,
            reply_to=reply_routing_key,
            correlation_id=self.correlation_id,
        )
        self.response: asyncio.Future = asyncio.Future()
        await self.exchange.publish(message, RPC_ROUTING_KEY.format(self.target_service, self.method_name))

        await self.response
        return self.response.result()

    async def setup_reply_queue(self) -> str:
        reply_routing_key = str(uuid.uuid4())
        reply_queue_name = RPC_REPLY_QUEUE.format(self.service_name, reply_routing_key)
        self.reply_queue = await self.channel.declare_queue(
            reply_queue_name,
            auto_delete=True,
        )
        await self.reply_queue.bind(self.exchange, reply_routing_key)
        self.consumer_tag = await self.reply_queue.consume(self.handle_message)
        return reply_routing_key

    async def handle_message(self, message: IncomingMessage) -> None:
        body = json.loads(message.body)
        if message.correlation_id == self.correlation_id:
            self.response.set_result(body)

        await message.ack()

    async def stop(self) -> None:
        await self.reply_queue.cancel(self.consumer_tag)
        await self.reply_queue.delete()
