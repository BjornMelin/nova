from __future__ import annotations

import asyncio
import threading
from concurrent.futures import (
    ThreadPoolExecutor,
)
from concurrent.futures import (
    TimeoutError as FutureTimeout,
)

import pytest
from nova_file_api.activity import MemoryActivityStore
from nova_file_api.models import Principal


def _principal(*, subject: str) -> Principal:
    """Build a test principal for activity store operations."""
    return Principal(
        subject=subject,
        scope_id="scope-1",
        tenant_id=None,
        scopes=(),
        permissions=(),
    )


@pytest.mark.asyncio
async def test_memory_activity_store_thread_safe_record_and_summary() -> None:
    """Verify concurrent readers and writers observe consistent memory state."""
    store = MemoryActivityStore()
    writer_threads = 4
    reader_threads = 2
    events_per_writer = 100
    summary_reads_per_reader = 80
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
        with asyncio.Runner() as runner:
            for iteration in range(events_per_writer):
                runner.run(
                    store.record(
                        principal=principal,
                        event_type=f"event-{iteration % 3}",
                    )
                )
                if iteration % 25 == 0:
                    snapshot = runner.run(store.summary())
                    assert snapshot["events_total"] >= 0

    def _reader() -> None:
        _wait_for_start(context="reader")
        with asyncio.Runner() as runner:
            for _ in range(summary_reads_per_reader):
                snapshot = runner.run(store.summary())
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

    summary = await store.summary()
    assert summary["events_total"] == writer_threads * events_per_writer
    assert summary["active_users_today"] == writer_threads
    assert summary["distinct_event_types"] == 3
