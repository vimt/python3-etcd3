from typing import Any, Iterable, Optional, Union

from . import etcdrpc, utils
from .utils import BytesOrStr, LeaseLike

_OPERATORS = {
    etcdrpc.Compare.EQUAL: "==",
    etcdrpc.Compare.NOT_EQUAL: "!=",
    etcdrpc.Compare.LESS: "<",
    etcdrpc.Compare.GREATER: ">",
}


class BaseCompare:
    """A comparison in a transaction, built with ==, !=, < or > on a target.

    For example ``etcd.transactions.version("/key") > 0``.
    """

    def __init__(self, key: BytesOrStr, range_end: Optional[BytesOrStr] = None):
        self.key = key
        self.range_end = range_end
        self.value: Any = None
        self.op: Optional[etcdrpc.Compare.CompareResult] = None

    # The comparison operators build the compare instead of returning a bool.
    # TODO check other is of correct type for compare
    # Version, Mod and Create can only be ints
    def __eq__(self, other: Any) -> "BaseCompare":  # type: ignore[override]
        self.value = other
        self.op = etcdrpc.Compare.EQUAL
        return self

    def __ne__(self, other: Any) -> "BaseCompare":  # type: ignore[override]
        self.value = other
        self.op = etcdrpc.Compare.NOT_EQUAL
        return self

    def __lt__(self, other: Any) -> "BaseCompare":
        self.value = other
        self.op = etcdrpc.Compare.LESS
        return self

    def __gt__(self, other: Any) -> "BaseCompare":
        self.value = other
        self.op = etcdrpc.Compare.GREATER
        return self

    def __repr__(self) -> str:
        if self.range_end is None:
            keys = str(self.key)
        else:
            keys = "[" + str(self.key) + ", " + str(self.range_end) + ")"
        op = _OPERATORS.get(self.op) if self.op is not None else None
        return f"{self.__class__}: {keys} {op} '{self.value}'"

    def build_message(self) -> etcdrpc.Compare:
        compare = etcdrpc.Compare()
        compare.key = utils.to_bytes(self.key)
        if self.range_end is not None:
            compare.range_end = utils.to_bytes(self.range_end)

        if self.op is None:
            raise ValueError("op must be one of =, !=, < or >")

        compare.result = self.op

        self.build_compare(compare)
        return compare

    def build_compare(self, compare: etcdrpc.Compare) -> None:
        raise NotImplementedError


class Value(BaseCompare):
    def build_compare(self, compare: etcdrpc.Compare) -> None:
        compare.target = etcdrpc.Compare.VALUE
        compare.value = utils.to_bytes(self.value)


class Version(BaseCompare):
    def build_compare(self, compare: etcdrpc.Compare) -> None:
        compare.target = etcdrpc.Compare.VERSION
        compare.version = int(self.value)


class Create(BaseCompare):
    def build_compare(self, compare: etcdrpc.Compare) -> None:
        compare.target = etcdrpc.Compare.CREATE
        compare.create_revision = int(self.value)


class Mod(BaseCompare):
    def build_compare(self, compare: etcdrpc.Compare) -> None:
        compare.target = etcdrpc.Compare.MOD
        compare.mod_revision = int(self.value)


class Put:
    def __init__(
        self,
        key: BytesOrStr,
        value: BytesOrStr,
        lease: LeaseLike = None,
        prev_kv: bool = False,
    ) -> None:
        self.key = key
        self.value = value
        self.lease = lease
        self.prev_kv = prev_kv


class Get:
    def __init__(self, key: BytesOrStr, range_end: Optional[BytesOrStr] = None):
        self.key = key
        self.range_end = range_end


class Delete:
    def __init__(
        self,
        key: BytesOrStr,
        range_end: Optional[BytesOrStr] = None,
        prev_kv: bool = False,
    ) -> None:
        self.key = key
        self.range_end = range_end
        self.prev_kv = prev_kv


class Txn:
    def __init__(
        self,
        compare: Iterable[BaseCompare],
        success: Optional[Iterable["Op"]] = None,
        failure: Optional[Iterable["Op"]] = None,
    ) -> None:
        self.compare = compare
        self.success = success
        self.failure = failure


#: An operation that can be run inside a transaction.
Op = Union[Put, Get, Delete, Txn]
