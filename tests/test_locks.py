"""
Tests for lock functionality.
"""

import time
from unittest import mock

import etcd3
from tests.conftest import TestBase


class TestLocks(TestBase):
    def test_lock_acquire(self, etcd):
        lock = etcd.lock("lock-1", ttl=10)
        assert lock.acquire() is True
        assert etcd.get(lock.key)[0] is not None
        assert lock.acquire(timeout=0) is False
        assert lock.acquire(timeout=1) is False

    def test_lock_release(self, etcd):
        lock = etcd.lock("lock-2", ttl=10)
        assert lock.acquire() is True
        assert etcd.get(lock.key)[0] is not None
        assert lock.release() is True
        v, _ = etcd.get(lock.key)
        assert v is None
        assert lock.acquire() is True
        assert lock.release() is True
        assert lock.acquire(timeout=None) is True

    def test_lock_expire(self, etcd):
        lock = etcd.lock("lock-3", ttl=3)
        assert lock.acquire() is True
        assert etcd.get(lock.key)[0] is not None
        # wait for the lease to expire
        time.sleep(9)
        v, _ = etcd.get(lock.key)
        assert v is None

    def test_lock_refresh(self, etcd):
        lock = etcd.lock("lock-4", ttl=3)
        assert lock.acquire() is True
        assert etcd.get(lock.key)[0] is not None
        # sleep for the same total time as test_lock_expire, but refresh each
        # second
        for _ in range(9):
            time.sleep(1)
            lock.refresh()

        assert etcd.get(lock.key)[0] is not None

    def test_lock_is_acquired(self, etcd):
        lock1 = etcd.lock("lock-5", ttl=2)
        assert lock1.is_acquired() is False

        lock2 = etcd.lock("lock-5", ttl=2)
        lock2.acquire()
        assert lock2.is_acquired() is True
        lock2.release()

        lock3 = etcd.lock("lock-5", ttl=2)
        lock3.acquire()
        assert lock3.is_acquired() is True
        assert lock2.is_acquired() is False

    def test_lock_context_manager(self, etcd):
        with etcd.lock("lock-6", ttl=2) as lock:
            assert lock.is_acquired() is True
        assert lock.is_acquired() is False

    def test_lock_contended(self, etcd):
        lock1 = etcd.lock("lock-7", ttl=2)
        lock1.acquire()
        lock2 = etcd.lock("lock-7", ttl=2)
        lock2.acquire()
        assert lock1.is_acquired() is False
        assert lock2.is_acquired() is True

    def test_lock_double_acquire_release(self, etcd):
        lock = etcd.lock("lock-8", ttl=10)
        assert lock.acquire(0) is True
        assert lock.acquire(0) is False
        assert lock.release() is True

    def test_lock_acquire_none(self, etcd):
        lock = etcd.lock("lock-9", ttl=10)
        assert lock.acquire(None) is True
        # This will succeed after 10 seconds since the TTL will expire and the
        # lock is not refreshed
        assert lock.acquire(None) is True

    def test_lock_acquire_with_timeout(self, etcd):
        lock1 = etcd.lock("lock-10", ttl=10)
        lock2 = etcd.lock("lock-10", ttl=10)

        original_watch = etcd.watch
        watch_called = [0]

        def release_lock_before_watch(*args, **kwargs):
            watch_called[0] += 1
            # Simulates the case where key is expired before watch is called.
            # See https://github.com/kragniz/python-etcd3/issues/1107
            lock1.release()
            return original_watch(*args, **kwargs)

        original_transaction = etcd.transaction
        transaction_called = [0]

        def transaction_wrapper(*args, **kwargs):
            transaction_called[0] += 1
            return original_transaction(*args, **kwargs)

        assert lock1.acquire() is True
        with mock.patch.object(
            etcd3.Etcd3Client, "watch", wraps=release_lock_before_watch
        ):
            with mock.patch.object(
                etcd3.Etcd3Client, "transaction", wraps=transaction_wrapper
            ):
                assert lock2.acquire(timeout=5) is True

        # watch must be called only for lock2 once
        assert watch_called[0] == 1

        # transaction must be called once for lock1, twice for lock2
        assert transaction_called[0] == 3