from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.models import Principal


def _principal(*, subject: str) -> Principal:
    return Principal(
        subject=subject,
        scope_id="scope-1",
        tenant_id=None,
        scopes=(),
        permissions=(),
    )


def test_memory_activity_store_thread_safe_record_and_summary() -> None:
    store = MemoryActivityStore()
    writer_threads = 8
    reader_threads = 4
    events_per_writer = 500
    summary_reads_per_reader = 400
    start = threading.Barrier(writer_threads + reader_threads + 1)
    subjects = [
        _principal(subject=f"user-{index}") for index in range(writer_threads)
    ]

    def _writer(worker_index: int) -> None:
        principal = subjects[worker_index]
        start.wait()
        for iteration in range(events_per_writer):
            store.record(
                principal=principal,
                event_type=f"event-{iteration % 3}",
            )
            if iteration % 25 == 0:
                snapshot = store.summary()
                assert snapshot["events_total"] >= 0

    def _reader() -> None:
        start.wait()
        for _ in range(summary_reads_per_reader):
            snapshot = store.summary()
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
        start.wait()
        for future in futures:
            future.result()

    summary = store.summary()
    assert summary["events_total"] == writer_threads * events_per_writer
    assert summary["active_users_today"] == writer_threads
    assert summary["distinct_event_types"] == 3
