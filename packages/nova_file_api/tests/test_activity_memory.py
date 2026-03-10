from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, TypeVar

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.models import Principal

_T = TypeVar("_T")


def _principal(*, subject: str) -> Principal:
    """Build a test principal for activity store operations."""
    return Principal(
        subject=subject,
        scope_id="scope-1",
        tenant_id=None,
        scopes=(),
        permissions=(),
    )


class _BackgroundLoop:
    """Run coroutines on a dedicated background event loop thread."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="activity-memory-loop",
            daemon=True,
        )

    def __enter__(self) -> _BackgroundLoop:
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise AssertionError("background loop did not start")
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            raise AssertionError("background loop thread did not stop")

    def run(self, coroutine: Coroutine[Any, Any, _T]) -> _T:
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result(
            timeout=10
        )

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        try:
            self._loop.run_forever()
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
        finally:
            self._loop.close()
            asyncio.set_event_loop(None)


def test_memory_activity_store_thread_safe_record_and_summary() -> None:
    """Verify concurrent readers and writers observe consistent memory state."""
    store = MemoryActivityStore()
    writer_threads = 8
    reader_threads = 4
    events_per_writer = 500
    summary_reads_per_reader = 400
    start = threading.Barrier(writer_threads + reader_threads + 1)
    subjects = [
        _principal(subject=f"user-{index}") for index in range(writer_threads)
    ]

    def _wait_for_start(*, context: str) -> None:
        try:
            start.wait(timeout=10)
        except threading.BrokenBarrierError as exc:
            raise AssertionError(
                f"thread coordination timed out in {context}"
            ) from exc

    def _writer(worker_index: int) -> None:
        principal = subjects[worker_index]
        _wait_for_start(context=f"writer-{worker_index}")
        with _BackgroundLoop() as runtime:
            for iteration in range(events_per_writer):
                runtime.run(
                    store.record(
                        principal=principal,
                        event_type=f"event-{iteration % 3}",
                    )
                )
                if iteration % 25 == 0:
                    snapshot = runtime.run(store.summary())
                    assert snapshot["events_total"] >= 0

    def _reader() -> None:
        _wait_for_start(context="reader")
        with _BackgroundLoop() as runtime:
            for _ in range(summary_reads_per_reader):
                snapshot = runtime.run(store.summary())
                assert snapshot["events_total"] >= 0
                assert snapshot["active_users_today"] >= 0
                assert snapshot["distinct_event_types"] >= 0

    with ThreadPoolExecutor(
        max_workers=writer_threads + reader_threads
    ) as pool:
        futures = [
            pool.submit(_writer, index) for index in range(writer_threads)
        ]
        futures.extend(pool.submit(_reader) for _ in range(reader_threads))
        _wait_for_start(context="main")
        for future in futures:
            try:
                future.result(timeout=30)
            except FutureTimeout as exc:
                raise AssertionError("worker thread timed out") from exc

    with _BackgroundLoop() as runtime:
        summary = runtime.run(store.summary())
    assert summary["events_total"] == writer_threads * events_per_writer
    assert summary["active_users_today"] == writer_threads
    assert summary["distinct_event_types"] == 3
