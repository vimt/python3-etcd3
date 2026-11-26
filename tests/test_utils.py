"""
Tests for utility functions.
"""

import etcd3.utils


class TestUtils:
    def test_prefix_range_end(self):
        assert etcd3.utils.prefix_range_end(b"foo") == b"fop"
        assert etcd3.utils.prefix_range_end(b"ab\xff") == b"ac\xff"
        assert (
            etcd3.utils.prefix_range_end(b"a\xff\xff\xff\xff\xff")
            == b"b\xff\xff\xff\xff\xff"
        )

    def test_to_bytes(self):
        assert isinstance(etcd3.utils.to_bytes(b"doot"), bytes) is True
        assert isinstance(etcd3.utils.to_bytes("doot"), bytes) is True
        assert etcd3.utils.to_bytes(b"doot") == b"doot"
        assert etcd3.utils.to_bytes("doot") == b"doot"
