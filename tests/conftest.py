import pytest
import pytest_asyncio
import time
import asyncio
import aio_pika
from unittest.mock import AsyncMock
from uservice.settings import Settings

from yarl import URL


@pytest.fixture(scope="session", autouse=True)
def rabbitmq_server():
    import docker
    client = docker.from_env()
    container = client.containers.run(
        "rabbitmq:3.11",
        ports={"5672/tcp": 5672},
        name="rabbitmq-test",
        detach=True,
    )
    time.sleep(5)
    yield container
    container.kill()
    container.remove()


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    try:
        loop = policy.get_event_loop()
    except RuntimeError:
        loop = policy.new_event_loop()
    yield loop

    loop.close()

@pytest.fixture(scope="session")
def amqp_direct_url(request) -> URL:
    url = URL(
        "amqp://guest:guest@localhost:5672",
    ).update_query(name=request.node.nodeid)

    return url


@pytest.fixture(scope="session")
def amqp_url(request, amqp_direct_url) -> URL:
    query = dict(amqp_direct_url.query)
    query["name"] = request.node.nodeid
    return amqp_direct_url.with_query(**query)



@pytest_asyncio.fixture(scope="session")
async def connection(amqp_url):
    conn = await aio_pika.connect(amqp_url)
    async with conn:
        yield conn


@pytest_asyncio.fixture
async def channel(connection):
    async with connection.channel() as ch:
        yield ch
        await ch.close()


@pytest.fixture
def mock():
    yield AsyncMock()


@pytest.fixture(scope="session")
def settings():
    return Settings()
