from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from nova_file_api.activity import MemoryActivityStore
from nova_file_api.models import Principal


def _principal(*, subject: str) -> Principal:
    """
    Create a Principal used in tests for activity store operations.
    
    Parameters:
        subject (str): Identifier for the principal's subject.
    
    Returns:
        Principal: A Principal with the given subject, fixed scope_id "scope-1", no tenant, and empty scopes and permissions.
    """
    return Principal(
        subject=subject,
        scope_id="scope-1",
        tenant_id=None,
        scopes=(),
        permissions=(),
    )


class _BackgroundLoop:
    """Own a dedicated event loop thread for thread-safe coroutine execution."""

    def __init__(self) -> None:
        """Initialize loop thread state."""
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="activity-memory-loop",
            daemon=True,
        )

    def __enter__(self) -> _BackgroundLoop:
        """
        Start the background event loop thread and wait for it to become ready.
        
        Waits up to 5 seconds for the loop to signal readiness; if the loop does not become ready within that time an AssertionError is raised.
        
        Returns:
            self: The started _BackgroundLoop instance.
        
        Raises:
            AssertionError: If the background loop did not start within 5 seconds.
        """
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise AssertionError("background loop did not start")
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """
        Stop the background event loop, join its thread, and ensure it has terminated.
        
        Schedules the loop to stop in a thread-safe manner, waits up to 5 seconds for the background thread to finish, and raises AssertionError if the thread remains alive.
        """
        del exc_type, exc, tb
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            raise AssertionError("background loop thread did not stop")

    def run[T](self, coroutine: Coroutine[Any, Any, T]) -> T:
        """
        Execute a coroutine on the background event loop and wait for it to complete.
        
        Parameters:
            coroutine (Coroutine[Any, Any, T]): Coroutine to schedule on the loop.
        
        Returns:
            T: The value returned by the coroutine.
        
        Notes:
            Blocks up to 10 seconds waiting for the coroutine's result; a timeout will propagate if exceeded.
        """
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result(
            timeout=10
        )

    def _run(self) -> None:
        """
        Run the background asyncio event loop on the current thread until it is stopped.
        
        Performs loop lifecycle management: sets this loop as the current event loop, signals readiness, runs the loop until stop is invoked, shuts down asynchronous generators, closes the loop, and clears the current event loop reference.
        """
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        try:
            self._loop.run_forever()
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
        finally:
            self._loop.close()
            asyncio.set_event_loop(None)


def test_memory_activity_store_thread_safe_record_and_summary() -> None:
    """
    Verify that MemoryActivityStore produces consistent summaries under concurrent write/read load.
    
    Spawns multiple writer and reader threads synchronized with a barrier; each writer records a fixed number of events (cycling through three event types) and readers repeatedly fetch summaries. Assertions are performed during execution to ensure summary fields are non-negative, and final assertions verify that:
    - "events_total" equals writers * events_per_writer,
    - "active_users_today" equals the number of writers,
    - "distinct_event_types" equals 3.
    
    The test runs store coroutines on a dedicated background event loop provided by _BackgroundLoop and fails if thread coordination or worker completion times out.
    """
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
        """
        Runs a writer thread that records a sequence of events for the principal identified by worker_index and intermittently validates the activity store summary.
        
        The function waits for the coordinated test start, then records `events_per_writer` events for the corresponding principal, cycling event types ("event-0".."event-2"). Every 25th iteration it reads a summary and asserts that reported totals are non-negative.
        
        Parameters:
            worker_index (int): Index into the shared `subjects` list selecting which principal this writer will record events for.
        """
        principal = subjects[worker_index]
        _wait_for_start(context=f"writer-{worker_index}")
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
        """
        Performs repeated summary reads from the activity store and validates key metrics.
        
        Performs summary_reads_per_reader snapshot reads via the shared runtime and, for each snapshot, asserts that `events_total`, `active_users_today`, and `distinct_event_types` are greater than or equal to zero.
        """
        _wait_for_start(context="reader")
        for _ in range(summary_reads_per_reader):
            snapshot = runtime.run(store.summary())
            assert snapshot["events_total"] >= 0
            assert snapshot["active_users_today"] >= 0
            assert snapshot["distinct_event_types"] >= 0

    with _BackgroundLoop() as runtime:
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

        summary = runtime.run(store.summary())
    assert summary["events_total"] == writer_threads * events_per_writer
    assert summary["active_users_today"] == writer_threads
    assert summary["distinct_event_types"] == 3
