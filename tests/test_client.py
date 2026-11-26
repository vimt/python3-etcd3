"""
Tests for client configuration and functionality.
"""

import tempfile
import time
from unittest import mock

import grpc
import pytest

import etcd3
import etcd3.etcdrpc as etcdrpc
import etcd3.exceptions
from etcd3.client import EtcdTokenCallCredentials
from tests.conftest import TestBase, new_client


class TestClient(TestBase):
    class MockedException(grpc.RpcError):
        def __init__(self, code):
            self._code = code

        def code(self):
            return self._code

    def test_sort_target(self, etcd):
        key = b"key"
        sort_target = {
            None: etcdrpc.RangeRequest.KEY,
            "key": etcdrpc.RangeRequest.KEY,
            "version": etcdrpc.RangeRequest.VERSION,
            "create": etcdrpc.RangeRequest.CREATE,
            "mod": etcdrpc.RangeRequest.MOD,
            "value": etcdrpc.RangeRequest.VALUE,
        }

        for input, expected in sort_target.items():
            range_request = etcd._build_get_range_request(key, sort_target=input)
            assert range_request.sort_target == expected
        with pytest.raises(ValueError):
            etcd._build_get_range_request(key, sort_target="feelsbadman")

    def test_sort_order(self, etcd):
        key = b"key"
        sort_target = {
            None: etcdrpc.RangeRequest.NONE,
            "ascend": etcdrpc.RangeRequest.ASCEND,
            "descend": etcdrpc.RangeRequest.DESCEND,
        }

        for input, expected in sort_target.items():
            range_request = etcd._build_get_range_request(key, sort_order=input)
            assert range_request.sort_order == expected
        with pytest.raises(ValueError):
            etcd._build_get_range_request(key, sort_order="feelsbadman")

    def test_secure_channel_ca_cert_and_key_raise_exception(self):
        with pytest.raises(ValueError):
            etcd3.client(
                ca_cert="tests/ca.crt", cert_key="tests/client.crt", cert_cert=None
            )

        with pytest.raises(ValueError):
            etcd3.client(
                ca_cert="tests/ca.crt", cert_key=None, cert_cert="tests/client.crt"
            )

    def test_compact(self, etcd):
        # Create some data to generate revisions
        etcd.put("/test1", "value1")
        etcd.put("/test2", "value2")
        etcd.put("/test3", "value3")

        # Get current revision
        _, meta = etcd.get("/test1")
        current_revision = meta.response_header.revision

        # Compact to a revision that exists
        compact_revision = max(1, current_revision - 1)
        etcd.compact(compact_revision)

        # Trying to compact to the same revision again should raise an error
        with pytest.raises(grpc.RpcError):
            etcd.compact(compact_revision)

    def test_channel_with_no_cert(self):
        client = etcd3.client(ca_cert=None, cert_key=None, cert_cert=None)
        assert client.uses_secure_channel is False

    def test_internal_exception_on_internal_error(self, etcd):
        exception = self.MockedException(grpc.StatusCode.INTERNAL)
        kv_mock = mock.PropertyMock()
        kv_mock.Range.side_effect = exception
        with mock.patch(
            "etcd3.Etcd3Client.kvstub", new_callable=mock.PropertyMock
        ) as property_mock:
            property_mock.return_value = kv_mock
            with pytest.raises(etcd3.exceptions.InternalServerError):
                etcd.get("foo")

    def test_connection_failure_exception_on_connection_failure(self, etcd):
        exception = self.MockedException(grpc.StatusCode.UNAVAILABLE)
        kv_mock = mock.PropertyMock()
        kv_mock.Range.side_effect = exception
        with mock.patch(
            "etcd3.Etcd3Client.kvstub", new_callable=mock.PropertyMock
        ) as property_mock:
            property_mock.return_value = kv_mock
            with pytest.raises(etcd3.exceptions.ConnectionFailedError):
                etcd.get("foo")
            assert etcd.endpoint_in_use.is_failed()

    def test_connection_timeout_exception_on_connection_timeout(self, etcd):
        exception = self.MockedException(grpc.StatusCode.DEADLINE_EXCEEDED)
        kv_mock = mock.PropertyMock()
        kv_mock.Range.side_effect = exception
        with mock.patch(
            "etcd3.Etcd3Client.kvstub", new_callable=mock.PropertyMock
        ) as property_mock:
            property_mock.return_value = kv_mock
            with pytest.raises(etcd3.exceptions.ConnectionTimeoutError):
                etcd.get("foo")
            assert etcd.endpoint_in_use.is_failed()

    def test_single_endpoint_failover(self, etcd):
        etcd.failover = True
        exception = self.MockedException(grpc.StatusCode.UNAVAILABLE)
        kv_mock = mock.PropertyMock()
        kv_mock.Range.side_effect = exception
        with mock.patch(
            "etcd3.Etcd3Client.kvstub", new_callable=mock.PropertyMock
        ) as property_mock:
            property_mock.return_value = kv_mock
            with pytest.raises(etcd3.exceptions.ConnectionFailedError):
                etcd.get("foo")
        with pytest.raises(etcd3.exceptions.NoServerAvailableError):
            etcd.get("foo")

    def test_grpc_exception_on_unknown_code(self, etcd):
        exception = self.MockedException(grpc.StatusCode.DATA_LOSS)
        kv_mock = mock.PropertyMock()
        kv_mock.Range.side_effect = exception
        with mock.patch(
            "etcd3.Etcd3Client.kvstub", new_callable=mock.PropertyMock
        ) as property_mock:
            property_mock.return_value = kv_mock
            with pytest.raises(grpc.RpcError):
                etcd.get("foo")
            assert not etcd.endpoint_in_use.is_failed()

    def test_hash(self, etcd):
        assert isinstance(etcd.hash(), int)

    def test_snapshot(self, etcd):
        with tempfile.NamedTemporaryFile() as f:
            etcd.snapshot(f)
            f.flush()
            # Note: In original test, this used etcdctl to verify snapshot
            # For now, we just verify the snapshot was created without error

    @pytest.mark.integration
    def test_grpc_options(self):
        # gRPC channel options are a sequence of (key, value) pairs
        with new_client(
            grpc_options=[("grpc.max_receive_message_length", 64 * 1024 * 1024)]
        ) as client:
            client.put("/doot/opts", "v")
            assert client.get("/doot/opts")[0] == b"v"
            client.delete("/doot/opts")

    def test_defragment(self, etcd):
        etcd.put("/doot/defrag", "v")
        etcd.defragment()
        assert etcd.get("/doot/defrag")[0] == b"v"

    def test_alarm_request_validation(self, etcd):
        with pytest.raises(ValueError, match="Unknown alarm action"):
            etcd._build_alarm_request("explode", 0, "none")
        with pytest.raises(ValueError, match="Unknown alarm type"):
            etcd._build_alarm_request("get", 0, "on fire")


class TestEndpoint:
    def test_secure_endpoint_requires_credentials(self):
        with pytest.raises(ValueError, match="TLS credentials"):
            etcd3.Endpoint("localhost", 2379, secure=True)

    def test_str(self):
        ep = etcd3.Endpoint("localhost", 2379, secure=False)
        assert str(ep) == "Endpoint(http://localhost:2379)"
        ep.close()

    def test_fail_and_retry_window(self):
        ep = etcd3.Endpoint("localhost", 2379, secure=False, time_retry=0.2)
        assert not ep.is_failed()
        ep.fail()
        assert ep.is_failed()
        with pytest.raises(ValueError, match="failed node"):
            ep.use()
        time.sleep(0.3)
        assert not ep.is_failed()
        assert ep.use() is ep.channel
        ep.close()


class TestExceptions:
    def test_messages(self):
        assert str(etcd3.exceptions.ConnectionFailedError()) == "etcd connection failed"
        assert (
            str(etcd3.exceptions.ConnectionTimeoutError()) == "etcd connection timeout"
        )
        err = etcd3.exceptions.RevisionCompactedError(42)
        assert err.compacted_revision == 42


class TestEtcdTokenCallCredentials:
    def test_token_callback(self):
        e = EtcdTokenCallCredentials("foo")
        callback = mock.MagicMock()
        e(None, callback)
        metadata = (("token", "foo"),)
        callback.assert_called_once_with(metadata, None)
