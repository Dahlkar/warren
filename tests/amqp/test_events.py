import asyncio
import pytest
import json

from contextlib import asynccontextmanager
from contextlib import nullcontext as does_not_raise
from typing import Any

from aio_pika import ExchangeType, Message
from pydantic import BaseModel, ValidationError

from uservice.amqp.events import AmqpEventHandler, AmqpEventPublisher
from uservice.contexts import ServiceContext


class Payload(BaseModel):
    foo: int


def handle(payload):
    print(payload)


@pytest.fixture(scope="module")
def service_name():
    return "test_events"


@pytest.fixture(scope="module")
def exchange_name():
    return "source_events"


@pytest.fixture(scope="module")
def routing_key():
    return "test_event"


@pytest.fixture(scope="module")
def event_handler(service_name, settings, exchange_name, routing_key):
    context = ServiceContext(
        name=service_name,
        settings=settings
    )
    return AmqpEventHandler(
        context=context,
        call=handle,
        exchange_name=exchange_name,
        routing_key=routing_key,
    )


@pytest.mark.asyncio
async def test_event_handler_setup(
        connection,
        event_handler,
        exchange_name,
        routing_key,
):
    await event_handler.setup(connection)

    assert event_handler.queue.name == f'uservice-{exchange_name}-{routing_key}-handle'
    assert event_handler.exchange.name == exchange_name
    assert event_handler.exchange._type == ExchangeType.TOPIC
    assert event_handler.exchange.durable
    assert not event_handler.exchange.auto_delete


@pytest.mark.asyncio
async def test_event_handler_start(event_handler):
    await event_handler.start()
    assert "ctag" in event_handler.consumer_tag


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'dispatch_payload,type_,expects', [
        ({'foo': 1}, Payload, 1),
        ({'foo': 1}, Any, 1),
        ({'test': 1}, Payload, 0)
    ]
)
async def test_event_handler_consume(
        mock,
        channel,
        event_handler,
        exchange_name,
        routing_key,
        dispatch_payload,
        type_,
        expects,
):
    event_handler.dependant.call = mock
    event_handler.payload_type = type_

    exchange = await channel.get_exchange(exchange_name)
    message = Message(json.dumps(dispatch_payload).encode())
    await exchange.publish(message, routing_key)

    await asyncio.sleep(0.1)
    assert mock.await_count == expects


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'publish_model,payload,expects,count', [
        (None, {'foo': 1}, does_not_raise(), 1),
        (Payload, {'foo': 1}, does_not_raise(), 1),
        (Payload, {'bar': 1}, pytest.raises(ValidationError), 0),
    ]
)
async def test_event_publisher(
        mock,
        connection,
        settings,
        event_handler,
        exchange_name,
        routing_key,
        publish_model,
        payload,
        expects,
        count,
):
    context = ServiceContext(
        name=exchange_name,
        settings=settings,
    )
    event_handler.dependant.call = mock
    event_publisher = AmqpEventPublisher(publish_model=publish_model)
    cm = asynccontextmanager(event_publisher)(connection, context)
    async with cm as publish:
        with expects:
            await publish(routing_key, payload)
            await asyncio.sleep(0.1)

    assert mock.await_count == count


@pytest.mark.asyncio
async def test_event_handler_stop(
        event_handler,
):
    await event_handler.stop()
    assert event_handler.channel.is_closed
