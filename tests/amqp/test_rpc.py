import pytest
import asyncio
import json
import uuid

from contextlib import asynccontextmanager

from pydantic import BaseModel
from aio_pika import ExchangeType, Message
from uservice.amqp.rpc import AmqpRpc, AmqpRpcProxy, RPC_QUEUE, RPC_REPLY_QUEUE, RPC_ROUTING_KEY
from uservice.contexts import ServiceContext


class Response(BaseModel):
    foo: int


async def handle(x, y):
    return x * y


@pytest.fixture(scope="module")
def service_name():
    return "test_rpcs"


@pytest.fixture(scope="module")
def routing_key():
    return "test_event"


@pytest.fixture(scope="module")
def rpc(service_name, settings):
    context = ServiceContext(
        name=service_name,
        settings=settings
    )
    return AmqpRpc(
        context=context,
        call=handle,
        response_model=Response,
    )


@pytest.mark.asyncio
async def test_rcp_setup(connection, rpc, service_name, settings):
    await rpc.setup(connection)

    assert rpc.queue.name == f'rpc-{service_name}'

    assert rpc.exchange.name == settings.amqp.rpc_exchange
    assert rpc.exchange._type == ExchangeType.TOPIC
    assert rpc.exchange.durable
    assert not rpc.exchange.auto_delete


@pytest.mark.asyncio
async def test_rpc_start(rpc):
    await rpc.start()
    assert "ctag" in rpc.consumer_tag


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'input,expects', [
        ({'x': 1, 'y': 2}, 1),
        ({'x': 1}, 0),
        ({'y': 2}, 0),
    ]
)
async def test_rcp_consume_reply(mock, channel, service_name, settings, rpc, input, expects):
    async def handle_message(message):
        await mock()
        await message.ack()

    exchange = await channel.get_exchange(settings.amqp.rpc_exchange)
    reply_routing_key = str(uuid.uuid4())
    reply_queue_name = RPC_REPLY_QUEUE.format('test_rpc_consume', reply_routing_key)
    reply_queue = await channel.declare_queue(
        reply_queue_name,
        auto_delete=True,
    )


    await reply_queue.bind(exchange, reply_routing_key)
    consumer_tag = await reply_queue.consume(handle_message)

    routing_key = RPC_ROUTING_KEY.format(service_name, 'handle')
    message = Message(json.dumps({'kwargs': input}).encode(), reply_to=reply_routing_key, correlation_id='1')
    await exchange.publish(message, routing_key)

    await asyncio.sleep(0.1)
    assert mock.await_count == expects

    await reply_queue.cancel(consumer_tag)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'input,expects', [
        ({'x': 1, 'y': 2}, 2),
        ({'x': 3, 'y': 2}, 6),
    ]
)
async def test_rpc_proxy(
        mock,
        connection,
        service_name,
        settings,
        input,
        expects,
):
    context = ServiceContext(
        name='source',
        settings=settings,
    )
    rpc_proxy = AmqpRpcProxy(target_service=service_name)
    cm = asynccontextmanager(rpc_proxy)(connection, context)
    async with cm as proxy:
        result = await proxy.handle(**input)
        assert result == expects
