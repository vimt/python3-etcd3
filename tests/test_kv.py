"""
Tests for basic KV operations (get, put, delete).
"""

import pytest
from hypothesis import given
from hypothesis.strategies import characters

from tests.conftest import TestBase, _out_quorum

# hypothesis tests get a clean etcd per example instead of the `etcd` fixture
pytestmark = pytest.mark.integration


class TestKVOperations(TestBase):
    def test_get_unknown_key(self, etcd):
        value, meta = etcd.get("probably-invalid-key")
        assert value is None
        assert meta is None

    @given(characters(blacklist_categories=["Cs", "Cc"]))
    def test_get_key(self, string):
        with self.get_clean_etcd() as etcd:
            etcd.put("/doot/a_key", string)
            returned, _ = etcd.get("/doot/a_key")
            assert returned == string.encode("utf-8")

    @given(characters(blacklist_categories=["Cs", "Cc"]))
    def test_get_random_key(self, string):
        with self.get_clean_etcd() as etcd:
            etcd.put("/doot/" + string, "dootdoot")
            returned, _ = etcd.get("/doot/" + string)
            assert returned == b"dootdoot"

    @given(
        characters(blacklist_categories=["Cs", "Cc"]),
        characters(blacklist_categories=["Cs", "Cc"]),
    )
    def test_get_key_serializable(self, key, string):
        with self.get_clean_etcd() as etcd:
            etcd.put("/doot/" + key, string)
            with _out_quorum():
                returned, _ = etcd.get("/doot/" + key, serializable=True)
            assert returned == string.encode("utf-8")

    @given(characters(blacklist_categories=["Cs", "Cc"]))
    def test_get_have_cluster_revision(self, string):
        with self.get_clean_etcd() as etcd:
            etcd.put("/doot/" + string, "dootdoot")
            _, md = etcd.get("/doot/" + string)
            assert md.response_header.revision > 0

    @given(characters(blacklist_categories=["Cs", "Cc"]))
    def test_put_key(self, string):
        with self.get_clean_etcd() as etcd:
            etcd.put("/doot/put_1", string)
            value, _ = etcd.get("/doot/put_1")
            assert value == string.encode("utf-8")

    @given(characters(blacklist_categories=["Cs", "Cc"]))
    def test_put_has_cluster_revision(self, string):
        with self.get_clean_etcd() as etcd:
            response = etcd.put("/doot/put_1", string)
            assert response.header.revision > 0

    @given(characters(blacklist_categories=["Cs", "Cc"]))
    def test_put_has_prev_kv(self, string):
        with self.get_clean_etcd() as etcd:
            etcd.put("/doot/put_1", "old_value")
            response = etcd.put("/doot/put_1", string, prev_kv=True)
            assert response.prev_kv.value == b"old_value"

    @given(characters(blacklist_categories=["Cs", "Cc"]))
    def test_put_if_not_exists(self, string):
        with self.get_clean_etcd() as etcd:
            txn_status = etcd.put_if_not_exists("/doot/put_1", string)
            assert txn_status is True

            txn_status = etcd.put_if_not_exists("/doot/put_1", string)
            assert txn_status is False

    def test_delete_key(self, etcd):
        etcd.put("/doot/delete_this", "delete pls")

        v, _ = etcd.get("/doot/delete_this")
        assert v == b"delete pls"

        deleted = etcd.delete("/doot/delete_this")
        assert deleted is True

        deleted = etcd.delete("/doot/delete_this")
        assert deleted is False

        deleted = etcd.delete("/doot/not_here_dude")
        assert deleted is False

        v, _ = etcd.get("/doot/delete_this")
        assert v is None

    def test_delete_has_cluster_revision(self, etcd):
        response = etcd.delete("/doot/delete_this", return_response=True)
        assert response.header.revision > 0

    def test_delete_has_prev_kv(self, etcd):
        etcd.put("/doot/delete_this", "old_value")
        response = etcd.delete("/doot/delete_this", prev_kv=True, return_response=True)
        assert response.prev_kvs[0].value == b"old_value"

    def test_delete_keys_with_prefix(self, etcd):
        etcd.put("/foo/1", "bar")
        etcd.put("/foo/2", "baz")

        v, _ = etcd.get("/foo/1")
        assert v == b"bar"

        v, _ = etcd.get("/foo/2")
        assert v == b"baz"

        response = etcd.delete_prefix("/foo")
        assert response.deleted == 2

        v, _ = etcd.get("/foo/1")
        assert v is None

        v, _ = etcd.get("/foo/2")
        assert v is None

    def test_replace_success(self, etcd):
        etcd.put("/doot/thing", "toot")
        status = etcd.replace("/doot/thing", "toot", "doot")
        v, _ = etcd.get("/doot/thing")
        assert v == b"doot"
        assert status is True

    def test_replace_fail(self, etcd):
        etcd.put("/doot/thing", "boot")
        status = etcd.replace("/doot/thing", "toot", "doot")
        v, _ = etcd.get("/doot/thing")
        assert v == b"boot"
        assert status is False
