from typing import Any, Type

from .etcdrpc import kv_pb2


class Event:
    """A watch event; key-value fields are read from the underlying protobuf.

    ``prev_<field>`` reads the field from the previous key-value pair (only
    set when the watch was created with ``prev_kv=True``).
    """

    # Forwarded to the event's KeyValue by __getattr__; declared for typing.
    value: bytes
    create_revision: int
    mod_revision: int
    version: int
    lease: int
    prev_value: bytes
    prev_create_revision: int
    prev_mod_revision: int
    prev_version: int
    prev_lease: int

    def __init__(self, event: kv_pb2.Event) -> None:
        self.key: bytes = event.kv.key
        self._event = event

    def __getattr__(self, name: str) -> Any:
        if name.startswith("prev_"):
            return getattr(self._event.prev_kv, name[5:])
        return getattr(self._event.kv, name)

    def __str__(self) -> str:
        return f"{self.__class__} key={self.key!r} value={self.value!r}"


class PutEvent(Event):
    pass


class DeleteEvent(Event):
    pass


def new_event(event: kv_pb2.Event) -> Event:
    """
    Wrap a raw gRPC event in a friendlier containing class.

    This picks the appropriate class from one of PutEvent or DeleteEvent and
    returns a new instance.
    """
    op_name = event.EventType.DESCRIPTOR.values_by_number[event.type].name
    cls: Type[Event]
    if op_name == "PUT":
        cls = PutEvent
    elif op_name == "DELETE":
        cls = DeleteEvent
    else:
        raise Exception("Invalid op_name")

    return cls(event)
