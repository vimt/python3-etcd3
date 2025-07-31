"""
Tests for watch functionality.
"""

import threading
import time
from unittest import mock

import grpc
import pytest

import etcd3
import etcd3.etcdrpc as etcdrpc
import etcd3.exceptions
import etcd3.utils as utils
from tests.conftest import TestBase


class TestWatch(TestBase):
    class MockedException(grpc.RpcError):
        def __init__(self, code):
            self._code = code

        def code(self):
            return self._code

    def test_new_watch_error(self, etcd):
        # Trigger a failure while waiting on the new watch condition
        with mock.patch.object(
            etcd.watcher._new_watch_cond, "wait", side_effect=ValueError
        ):
            with pytest.raises(ValueError):
                etcd.watch("/foo")

        # Ensure a new watch can be created
        events, cancel = etcd.watch("/foo")
        etcd.put("/foo", "42")
        next(events)
        cancel()

    def test_watch_key(self, etcd):
        def update_etcd(v):
            etcd.put("/doot/watch", v)
            value, _ = etcd.get("/doot/watch")
            assert value == utils.to_bytes(v)

        def update_key():
            # sleep to make watch can get the event
            time.sleep(3)
            update_etcd("0")
            time.sleep(1)
            update_etcd("1")
            time.sleep(1)
            update_etcd("2")
            time.sleep(1)
            update_etcd("3")
            time.sleep(1)

        t = threading.Thread(name="update_key", target=update_key)
        t.start()

        change_count = 0
        events_iterator, cancel = etcd.watch(b"/doot/watch")
        for event in events_iterator:
            assert event.key == b"/doot/watch"
            assert event.value == utils.to_bytes(str(change_count))

            # if cancel worked, we should not receive event 3
            assert event.value != utils.to_bytes("3")

            change_count += 1
            if change_count > 2:
                # if cancel not work, we will block in this for-loop forever
                cancel()

        t.join()

    def test_watch_key_with_revision_compacted(self, etcd):
        etcd.put("/random", "1")  # Some data to compact

        def update_etcd(v):
            etcd.put("/watchcompation", v)
            value, _ = etcd.get("/watchcompation")
            assert value == utils.to_bytes(v)

        def update_key():
            # sleep to make watch can get the event
            time.sleep(3)
            update_etcd("0")
            time.sleep(1)
            update_etcd("1")
            time.sleep(1)
            update_etcd("2")
            time.sleep(1)
            update_etcd("3")
            time.sleep(1)

        t = threading.Thread(name="update_key", target=update_key)
        t.start()

        def watch_compacted_revision_test():
            events_iterator, cancel = etcd.watch(b"/watchcompation", start_revision=1)

            error_raised = False
            compacted_revision = 0
            try:
                next(events_iterator)
            except Exception as err:
                error_raised = True
                assert isinstance(err, etcd3.exceptions.RevisionCompactedError)
                compacted_revision = err.compacted_revision

            assert error_raised is True
            assert compacted_revision == 2

            change_count = 0
            events_iterator, cancel = etcd.watch(
                b"/watchcompation", start_revision=compacted_revision
            )
            for event in events_iterator:
                assert event.key == b"/watchcompation"
                assert event.value == utils.to_bytes(str(change_count))

                # if cancel worked, we should not receive event 3
                assert event.value != utils.to_bytes("3")

                change_count += 1
                if change_count > 2:
                    cancel()

        # Compact etcd and test watcher
        etcd.compact(2)

        watch_compacted_revision_test()

        t.join()

    def test_watch_exception_during_watch(self, etcd):
        def pass_exception_to_callback(callback):
            time.sleep(1)
            callback(self.MockedException(grpc.StatusCode.UNAVAILABLE))

        def add_callback_mock(*args, **kwargs):
            callback = args[1]
            t = threading.Thread(
                name="pass_exception_to_callback",
                target=pass_exception_to_callback,
                args=[callback],
            )
            t.start()
            return 1

        watcher_mock = mock.MagicMock()
        watcher_mock.add_callback = add_callback_mock
        etcd.watcher = watcher_mock

        events_iterator, cancel = etcd.watch("foo")

        with pytest.raises(etcd3.exceptions.ConnectionFailedError):
            for _ in events_iterator:
                pass

    def test_watch_timeout_on_establishment(self, etcd):
        foo_etcd = etcd3.client(timeout=3)

        def slow_watch_mock(*args, **kwargs):
            time.sleep(4)
            return []

        foo_etcd.watcher._watch_stub.Watch = slow_watch_mock  # noqa

        with pytest.raises(etcd3.exceptions.WatchTimedOut):
            foo_etcd.watch("foo")

    def test_watch_prefix(self, etcd):
        def update_etcd(v):
            etcd.put("/doot/watch/prefix/" + v, v)
            value, _ = etcd.get("/doot/watch/prefix/" + v)
            assert value == utils.to_bytes(v)

        def update_key():
            # sleep to make watch can get the event
            time.sleep(3)
            update_etcd("0")
            time.sleep(1)
            update_etcd("1")
            time.sleep(1)
            update_etcd("2")
            time.sleep(1)
            update_etcd("3")
            time.sleep(1)

        t = threading.Thread(name="update_key_prefix", target=update_key)
        t.start()

        change_count = 0
        events_iterator, cancel = etcd.watch_prefix("/doot/watch/prefix/")
        for event in events_iterator:
            assert event.key == utils.to_bytes(f"/doot/watch/prefix/{change_count}")
            assert event.value == utils.to_bytes(str(change_count))

            # if cancel worked, we should not receive event 3
            assert event.value != utils.to_bytes("3")

            change_count += 1
            if change_count > 2:
                # if cancel not work, we will block in this for-loop forever
                cancel()

        t.join()

    def test_watch_prefix_callback(self, etcd):
        def update_etcd(v):
            etcd.put("/doot/watch/prefix/callback/" + v, v)
            value, _ = etcd.get("/doot/watch/prefix/callback/" + v)
            assert value == utils.to_bytes(v)

        def update_key():
            # sleep to make watch can get the event
            time.sleep(3)
            update_etcd("0")
            time.sleep(1)
            update_etcd("1")
            time.sleep(1)

        events = []

        def callback(event):
            events.extend(event.events)

        t = threading.Thread(name="update_key_prefix", target=update_key)
        t.start()

        watch_id = etcd.add_watch_prefix_callback(
            "/doot/watch/prefix/callback/", callback
        )

        t.join()
        etcd.cancel_watch(watch_id)

        assert len(events) == 2
        assert events[0].key.decode() == "/doot/watch/prefix/callback/0"
        assert events[0].value.decode() == "0"
        assert events[1].key.decode() == "/doot/watch/prefix/callback/1"
        assert events[1].value.decode() == "1"

    def test_watch_prefix_callback_with_filter(self, etcd):
        def update_etcd(v):
            etcd.put("/doot/watch/prefix/callback/" + v, v)
            value, _ = etcd.get("/doot/watch/prefix/callback/" + v)
            assert value == utils.to_bytes(v)

        def delete_etcd(v):
            etcd.delete("/doot/watch/prefix/callback/" + v)

        def update_key():
            time.sleep(3)
            update_etcd("0")
            time.sleep(1)
            update_etcd("1")
            time.sleep(1)
            delete_etcd("1")
            time.sleep(1)

        events = []

        def callback(event):
            events.extend(event.events)

        t = threading.Thread(name="update_key_prefix", target=update_key)
        t.start()

        watch_id = etcd.add_watch_prefix_callback(
            "/doot/watch/prefix/callback/",
            callback,
            filters=[etcdrpc.WatchCreateRequest.FilterType.Value("NODELETE")],
        )

        t.join()
        etcd.cancel_watch(watch_id)

        assert len(events) == 2
        assert events[0].key.decode() == "/doot/watch/prefix/callback/0"
        assert events[0].value.decode() == "0"
        assert events[1].key.decode() == "/doot/watch/prefix/callback/1"
        assert events[1].value.decode() == "1"

    def test_sequential_watch_prefix_once(self, etcd):
        try:
            etcd.watch_prefix_once("/doot/", 1)
        except etcd3.exceptions.WatchTimedOut:
            pass
        try:
            etcd.watch_prefix_once("/doot/", 1)
        except etcd3.exceptions.WatchTimedOut:
            pass
        try:
            etcd.watch_prefix_once("/doot/", 1)
        except etcd3.exceptions.WatchTimedOut:
            pass

    def test_watch_responses(self, etcd):
        # Test watch_response & watch_once_response
        revision = etcd.put("/doot/watch", "0").header.revision
        etcd.put("/doot/watch", "1")
        responses_iterator, cancel = etcd.watch_response(
            "/doot/watch", start_revision=revision
        )

        response_1 = next(responses_iterator)
        cancel()
        response_2 = etcd.watch_once_response("/doot/watch", start_revision=revision)

        for response in [response_1, response_2]:
            count = 0
            # check that the response contains the etcd revision
            assert response.header.revision > 0
            assert len(response.events) == 2
            for event in response.events:
                assert event.key == b"/doot/watch"
                assert event.value == utils.to_bytes(str(count))
                count += 1

        # Test watch_prefix_response & watch_prefix_once_response
        success_ops = [
            etcd.transactions.put("/doot/watch/prefix/0", "0"),
            etcd.transactions.put("/doot/watch/prefix/1", "1"),
        ]
        revision = etcd.transaction([], success_ops, [])[1][
            0
        ].response_put.header.revision

        responses_iterator, cancel = etcd.watch_prefix_response(
            "/doot/watch/prefix/", start_revision=revision
        )

        response_1 = next(responses_iterator)
        cancel()
        response_2 = etcd.watch_prefix_once_response(
            "/doot/watch/prefix/", start_revision=revision
        )

        for response in [response_1, response_2]:
            count = 0
            assert response.header.revision == revision
            assert len(response.events) == 2
            for event in response.events:
                assert event.key == utils.to_bytes(f"/doot/watch/prefix/{count}")
                assert event.value == utils.to_bytes(str(count))
                count += 1