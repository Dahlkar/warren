from uservice import Service
from pydantic import BaseModel


service = Service(name="example")


class Payload(BaseModel):
    foo: int
    bar: float


@service.event_handler(
    "source",
    "event",
)
def handle_event(payload: Payload):
    print(payload)
