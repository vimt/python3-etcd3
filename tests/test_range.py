"""
Tests for range operations (get_prefix, get_range, get_all).
"""

import string

import pytest

from tests.conftest import TestBase


class TestRangeOperations(TestBase):
    def test_get_prefix(self, etcd):
        for i in range(20):
            etcd.put(f"/doot/range{i}", "i am a range")

        for i in range(5):
            etcd.put(f"/doot/notrange{i}", "i am a not range")

        values = list(etcd.get_prefix("/doot/range"))
        assert len(values) == 20
        for value, _ in values:
            assert value == b"i am a range"

    def test_get_prefix_keys_only(self, etcd):
        for i in range(20):
            etcd.put(f"/doot/range{i}", "i am a range")

        for i in range(5):
            etcd.put(f"/doot/notrange{i}", "i am a not range")

        values = list(etcd.get_prefix("/doot/range", keys_only=True))
        assert len(values) == 20
        for value, meta in values:
            assert meta.key.startswith(b"/doot/range")
            assert not value

    def test_get_prefix_serializable(self, etcd):
        for i in range(20):
            etcd.put(f"/doot/range{i}", "i am a range")

        from tests.conftest import _out_quorum

        with _out_quorum():
            values = list(
                etcd.get_prefix("/doot/range", keys_only=True, serializable=True)
            )

        assert len(values) == 20

    def test_get_prefix_error_handling(self, etcd):
        with pytest.raises(TypeError, match="Don't use "):
            etcd.get_prefix("a_prefix", range_end="end")

    def test_get_range(self, etcd):
        for char in string.ascii_lowercase:
            if char < "p":
                etcd.put("/doot/" + char, "i am in range")
            else:
                etcd.put("/doot/" + char, "i am not in range")

        values = list(etcd.get_range("/doot/a", "/doot/p"))
        assert len(values) == 15
        for value, _ in values:
            assert value == b"i am in range"

    def test_all_not_found_error(self, etcd):
        result = list(etcd.get_all())
        assert not result

    def test_range_not_found_error(self, etcd):
        for i in range(5):
            etcd.put(f"/doot/notrange{i}", "i am a not range")

        result = list(etcd.get_prefix("/doot/range"))
        assert not result

    def test_get_all(self, etcd):
        for i in range(20):
            etcd.put(f"/doot/range{i}", "i am in all")

        for i in range(5):
            etcd.put(f"/doot/notrange{i}", "i am in all")
        values = list(etcd.get_all())
        assert len(values) == 25
        for value, _ in values:
            assert value == b"i am in all"

    def test_get_all_keys_only(self, etcd):
        for i in range(20):
            etcd.put(f"/doot/range{i}", "i am in all")

        for i in range(5):
            etcd.put(f"/doot/notrange{i}", "i am in all")
        values = list(etcd.get_all(keys_only=True))
        assert len(values) == 25
        for value, meta in values:
            assert meta.key.startswith(b"/doot/")
            assert not value

    def test_get_count_only(self, etcd):
        for i in range(20):
            etcd.put(f"/doot/count{i}", "i am in all")
        resp = etcd.get_prefix_response(key_prefix="/doot/count", count_only=True)
        assert len(resp.kvs) == 0
        assert resp.count == 20

    def test_get_limit(self, etcd):
        for i in range(20):
            etcd.put(f"/doot/limit{i}", "i am in all")
        for i in range(20):
            resp = etcd.get_prefix_response(key_prefix="/doot/limit", limit=i)
            assert resp.count == 20
            if i == 0 or i == 20:
                assert len(resp.kvs) == 20
                assert resp.more is False
            else:
                assert len(resp.kvs) == i
                assert resp.more is True

    def test_get_revision(self, etcd):
        revisions = []
        for i in range(20):
            resp = etcd.put(f"/doot/revision{i}", "i am in all")
            revisions.append(resp.header.revision)
        for i, revision in enumerate(revisions):
            resp = etcd.get_prefix_response(
                key_prefix="/doot/revision", revision=revision
            )
            assert resp.count == min(len(revisions), i + 1)

    def test_get_min_mod_revision(self, etcd):
        revisions = []
        for i in range(5):
            resp = etcd.put("/doot/revision", str(i))
            revisions.append(resp.header.revision)
        for revision in revisions:
            resp = etcd.get_response(key="/doot/revision", min_mod_revision=revision)
            assert len(resp.kvs) == 1

    def test_get_max_mod_revision(self, etcd):
        revisions = []
        for i in range(5):
            resp = etcd.put("/doot/revision", str(i))
            revisions.append(resp.header.revision)
        for revision in revisions:
            resp = etcd.get_response(key="/doot/revision", max_mod_revision=revision)
            if revision == revisions[-1]:
                assert len(resp.kvs) == 1
            else:
                assert len(resp.kvs) == 0

    def test_get_min_max_create_revision(self, etcd):
        create_a = etcd.put("/doot/a", "1").header.revision
        create_b = etcd.put("/doot/b", "2").header.revision
        # Modifying "a" bumps its mod_revision past create_b; its
        # create_revision stays create_a. A filter that wrongly uses
        # mod_revision would therefore match both keys.
        etcd.put("/doot/a", "3")

        def keys(**kwargs):
            return sorted(meta.key for _, meta in etcd.get_prefix("/doot", **kwargs))

        assert keys(min_create_revision=create_b) == [b"/doot/b"]
        assert keys(max_create_revision=create_a) == [b"/doot/a"]
        assert keys(min_create_revision=create_a, max_create_revision=create_b) == [
            b"/doot/a",
            b"/doot/b",
        ]

    def test_sort_order(self, etcd):
        def remove_prefix(string, prefix):
            return string[len(prefix) :]

        initial_keys = "abcde"
        initial_values = "qwert"

        for k, v in zip(initial_keys, initial_values):
            etcd.put(f"/doot/{k}", v)

        keys = ""
        for _value, meta in etcd.get_prefix("/doot", sort_order="ascend"):
            keys += remove_prefix(meta.key.decode("utf-8"), "/doot/")

        assert keys == initial_keys

        reverse_keys = ""
        for _value, meta in etcd.get_prefix("/doot", sort_order="descend"):
            reverse_keys += remove_prefix(meta.key.decode("utf-8"), "/doot/")

        assert reverse_keys == "".join(reversed(initial_keys))

    def test_get_response(self, etcd):
        etcd.put("/foo/key1", "value1")
        etcd.put("/foo/key2", "value2")
        response = etcd.get_response("/foo/key1")
        assert response.header.revision > 0
        assert response.count == 1
        assert response.kvs[0].key == b"/foo/key1"
        assert response.kvs[0].value == b"value1"
        response = etcd.get_prefix_response("/foo/", sort_order="ascend")
        assert response.header.revision > 0
        assert response.count == 2
        assert response.kvs[0].key == b"/foo/key1"
        assert response.kvs[0].value == b"value1"
        assert response.kvs[1].key == b"/foo/key2"
        assert response.kvs[1].value == b"value2"
        # Test that the response header is accessible even when the
        # requested key or range of keys does not exist
        etcd.delete_prefix("/foo/")
        response = etcd.get_response("/foo/key1")
        assert response.count == 0
        assert response.header.revision > 0
        response = etcd.get_prefix_response("/foo/")
        assert response.count == 0
        assert response.header.revision > 0
        response = etcd.get_range_response("/foo/key1", "/foo/key3")
        assert response.count == 0
        assert response.header.revision > 0
        response = etcd.get_all_response()
        assert response.count == 0
        assert response.header.revision > 0
