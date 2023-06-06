__version__ = "0.1.2"


from uservice.main import main
from uservice.service import Service
from uservice.amqp.events import AmqpEventPublisher as EventPublisher
from uservice.amqp.rpc import AmqpRpcProxy as RpcProxy
from uservice.dependencies import Depends

__all__ = [
    "main",
    "Service",
    "EventPublisher",
    "RpcProxy",
    "Depends",
]
