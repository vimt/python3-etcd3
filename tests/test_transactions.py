"""
Tests for transaction functionality.
"""

import pytest

import etcd3
import etcd3.etcdrpc as etcdrpc
import etcd3.utils as utils
from tests.conftest import TestBase


etcd_version = "v3.5"  # Assume recent version for now


class TestTransactions(TestBase):
    def test_transaction_success(self, etcd):
        etcd.put("/doot/txn", "dootdoot")
        etcd.transaction(
            compare=[etcd.transactions.value("/doot/txn") == "dootdoot"],
            success=[etcd.transactions.put("/doot/txn", "success")],
            failure=[etcd.transactions.put("/doot/txn", "failure")],
        )
        value, _ = etcd.get("/doot/txn")
        assert value == b"success"

    def test_transaction_failure(self, etcd):
        etcd.put("/doot/txn", "notdootdoot")
        etcd.transaction(
            compare=[etcd.transactions.value("/doot/txn") == "dootdoot"],
            success=[etcd.transactions.put("/doot/txn", "success")],
            failure=[etcd.transactions.put("/doot/txn", "failure")],
        )
        value, _ = etcd.get("/doot/txn")
        assert value == b"failure"

    def test_ops_to_requests(self, etcd):
        with pytest.raises(Exception):
            etcd._ops_to_requests(["not_transaction_type"])
        with pytest.raises(TypeError):
            etcd._ops_to_requests(0)

    @pytest.mark.skipif(etcd_version < "v3.3", reason="requires etcd v3.3 or higher")
    def test_nested_transactions(self, etcd):
        etcd.transaction(
            compare=[],
            success=[
                etcd.transactions.put("/doot/txn1", "1"),
                etcd.transactions.txn(
                    compare=[],
                    success=[etcd.transactions.put("/doot/txn2", "2")],
                    failure=[],
                ),
            ],
            failure=[],
        )
        value, _ = etcd.get("/doot/txn1")
        assert value == b"1"
        value, _ = etcd.get("/doot/txn2")
        assert value == b"2"

    @pytest.mark.skipif(etcd_version < "v3.3", reason="requires etcd v3.3 or higher")
    def test_transaction_range_conditions(self, etcd):
        etcd.put("/doot/key1", "dootdoot")
        etcd.put("/doot/key2", "notdootdoot")
        range_end = utils.prefix_range_end(utils.to_bytes("/doot/"))
        compare = [etcd.transactions.value("/doot/", range_end) == "dootdoot"]
        status, _ = etcd.transaction(compare=compare, success=[], failure=[])
        assert not status
        etcd.put("/doot/key2", "dootdoot")
        status, _ = etcd.transaction(compare=compare, success=[], failure=[])
        assert status


class TestCompares:
    def test_compare_version(self):
        key = "key"
        tx = etcd3.Transactions()

        version_compare = tx.version(key) == 1
        assert version_compare.op == etcdrpc.Compare.EQUAL

        version_compare = tx.version(key) != 2
        assert version_compare.op == etcdrpc.Compare.NOT_EQUAL

        version_compare = tx.version(key) < 91
        assert version_compare.op == etcdrpc.Compare.LESS

        version_compare = tx.version(key) > 92
        assert version_compare.op == etcdrpc.Compare.GREATER
        assert version_compare.build_message().target == etcdrpc.Compare.VERSION

    def test_compare_value(self):
        key = "key"
        tx = etcd3.Transactions()

        value_compare = tx.value(key) == "b"
        assert value_compare.op == etcdrpc.Compare.EQUAL

        value_compare = tx.value(key) != "b"
        assert value_compare.op == etcdrpc.Compare.NOT_EQUAL

        value_compare = tx.value(key) < "b"
        assert value_compare.op == etcdrpc.Compare.LESS

        value_compare = tx.value(key) > "b"
        assert value_compare.op == etcdrpc.Compare.GREATER
        assert value_compare.build_message().target == etcdrpc.Compare.VALUE

    def test_compare_mod(self):
        key = "key"
        tx = etcd3.Transactions()

        mod_compare = tx.mod(key) == -100
        assert mod_compare.op == etcdrpc.Compare.EQUAL

        mod_compare = tx.mod(key) != -100
        assert mod_compare.op == etcdrpc.Compare.NOT_EQUAL

        mod_compare = tx.mod(key) < 19
        assert mod_compare.op == etcdrpc.Compare.LESS

        mod_compare = tx.mod(key) > 21
        assert mod_compare.op == etcdrpc.Compare.GREATER
        assert mod_compare.build_message().target == etcdrpc.Compare.MOD

    def test_compare_create(self):
        key = "key"
        tx = etcd3.Transactions()

        create_compare = tx.create(key) == 10
        assert create_compare.op == etcdrpc.Compare.EQUAL

        create_compare = tx.create(key) != 10
        assert create_compare.op == etcdrpc.Compare.NOT_EQUAL

        create_compare = tx.create(key) < 155
        assert create_compare.op == etcdrpc.Compare.LESS

        create_compare = tx.create(key) > -12
        assert create_compare.op == etcdrpc.Compare.GREATER
        assert create_compare.build_message().target == etcdrpc.Compare.CREATE