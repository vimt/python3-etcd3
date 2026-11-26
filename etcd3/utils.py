from typing import TYPE_CHECKING, Iterable, Iterator, Union

if TYPE_CHECKING:
    from .events import Event
    from .leases import Lease
    from .watch import WatchResponse

#: Keys and values may be given as ``str`` (encoded as UTF-8) or ``bytes``.
BytesOrStr = Union[str, bytes]
#: A lease may be given as a :class:`.Lease` or as its integer ID.
LeaseLike = Union["Lease", int, None]


def prefix_range_end(prefix: bytes) -> bytes:
    """Create a bytestring that can be used as a range_end for a prefix."""
    s = bytearray(prefix)
    for i in reversed(range(len(s))):
        if s[i] < 0xFF:
            s[i] = s[i] + 1
            break
    return bytes(s)


def to_bytes(maybe_bytestring: BytesOrStr) -> bytes:
    """
    Encode string to bytes.

    Convenience function to do a simple encode('utf-8') if the input is not
    already bytes. Returns the data unmodified if the input is bytes.
    """
    if isinstance(maybe_bytestring, bytes):
        return maybe_bytestring
    else:
        return maybe_bytestring.encode("utf-8")


def lease_to_id(lease: LeaseLike) -> int:
    """Figure out if the argument is a Lease object, or the lease ID."""
    lease_id = 0
    if hasattr(lease, "id"):
        lease_id = lease.id  # type: ignore[union-attr]
    else:
        try:
            lease_id = int(lease)  # type: ignore[arg-type]
        except TypeError:
            pass
    return lease_id


def response_to_event_iterator(
    response_iterator: Iterable["WatchResponse"],
) -> Iterator["Event"]:
    """Convert a watch response iterator to an event iterator."""
    for response in response_iterator:
        yield from response.events
