import concurrent.futures
import time
from app.schemas import ContextPush
from app.store import ContextStore


def test_version_deduplication():
    store = ContextStore()

    push_v1 = ContextPush(
        scope="merchant",
        context_id="m_001",
        version=1,
        payload={"identity": {"name": "Test Dental Clinic"}},
    )
    ack1 = store.upsert(push_v1)
    assert ack1.accepted is True
    assert ack1.status == "stored"
    assert ack1.stored_version == 1
    assert store.get_version("merchant", "m_001") == 1

    ack1_dup = store.upsert(push_v1)
    assert ack1_dup.accepted is True
    assert ack1_dup.status == "noop"
    assert ack1_dup.stored_version == 1
    assert store.get_version("merchant", "m_001") == 1

    push_v0 = ContextPush(
        scope="merchant",
        context_id="m_001",
        version=0,
        payload={"identity": {"name": "Old Dental Clinic"}},
    )
    ack0 = store.upsert(push_v0)
    assert ack0.status == "noop"
    assert ack0.stored_version == 1
    assert store.get("merchant", "m_001")["identity"]["name"] == "Test Dental Clinic"

    push_v2 = ContextPush(
        scope="merchant",
        context_id="m_001",
        version=2,
        payload={"identity": {"name": "Updated Dental Clinic"}},
    )
    ack2 = store.upsert(push_v2)
    assert ack2.accepted is True
    assert ack2.status == "stored"
    assert ack2.stored_version == 2
    assert store.get("merchant", "m_001")["identity"]["name"] == "Updated Dental Clinic"


def test_payload_size_ceiling_rejection():
    store = ContextStore(max_context_bytes=512000)

    normal_push = ContextPush(
        scope="category",
        context_id="dentists",
        version=1,
        payload={"slug": "dentists", "data": "x" * 1000},
    )
    ack_normal = store.upsert(normal_push)
    assert ack_normal.accepted is True
    assert ack_normal.status == "stored"

    huge_data = "a" * (520 * 1024)
    huge_push = ContextPush(
        scope="category",
        context_id="salons",
        version=1,
        payload={"slug": "salons", "blob": huge_data},
    )
    ack_huge = store.upsert(huge_push)
    assert ack_huge.accepted is False
    assert ack_huge.status == "rejected"
    assert "exceeds" in (ack_huge.reason or "")
    assert store.get("category", "salons") is None


def test_multithreaded_upsert_integrity():
    store = ContextStore()
    num_threads = 50

    def worker(i: int):
        push = ContextPush(
            scope="customer",
            context_id=f"c_{i:03d}",
            version=1,
            payload={"customer_id": f"c_{i:03d}", "merchant_id": "m_shared", "idx": i},
        )
        return store.upsert(push)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        results = [f.result() for f in futures]

    assert all(r.accepted is True and r.status == "stored" for r in results)
    counts = store.get_counts()
    assert counts["customer"] == num_threads

    custs = store.get_customers_for_merchant("m_shared")
    assert len(custs) == num_threads


def test_secondary_indexes():
    store = ContextStore()

    store.upsert(
        ContextPush(
            scope="category",
            context_id="dentists",
            version=1,
            payload={"slug": "dentists"},
        )
    )
    store.upsert(
        ContextPush(
            scope="merchant",
            context_id="m_1",
            version=1,
            payload={"merchant_id": "m_1", "category_slug": "dentists"},
        )
    )
    store.upsert(
        ContextPush(
            scope="merchant",
            context_id="m_2",
            version=1,
            payload={"merchant_id": "m_2", "category_slug": "dentists"},
        )
    )
    store.upsert(
        ContextPush(
            scope="customer",
            context_id="c_1",
            version=1,
            payload={"customer_id": "c_1", "merchant_id": "m_1"},
        )
    )
    store.upsert(
        ContextPush(
            scope="trigger",
            context_id="t_1",
            version=1,
            payload={"id": "t_1", "merchant_id": "m_1"},
        )
    )

    merchants = store.get_merchants_for_category("dentists")
    assert len(merchants) == 2
    assert {m["merchant_id"] for m in merchants} == {"m_1", "m_2"}

    customers = store.get_customers_for_merchant("m_1")
    assert len(customers) == 1
    assert customers[0]["customer_id"] == "c_1"

    triggers = store.get_triggers_for_merchant("m_1")
    assert len(triggers) == 1
    assert triggers[0]["id"] == "t_1"


def test_store_read_latency_benchmark():
    store = ContextStore()
    store.upsert(
        ContextPush(
            scope="merchant",
            context_id="m_bench",
            version=1,
            payload={"identity": {"name": "Speedy Clinic"}},
        )
    )

    for _ in range(100):
        store.get("merchant", "m_bench")

    n_reads = 10000
    start = time.perf_counter()
    for _ in range(n_reads):
        val = store.get("merchant", "m_bench")
        assert val is not None
    duration_s = time.perf_counter() - start

    avg_latency_us = (duration_s / n_reads) * 1_000_000
    print(f"\n[BENCHMARK] store.get() average latency: {avg_latency_us:.3f} µs over {n_reads} iterations")

    assert avg_latency_us < 50.0, f"Average read latency {avg_latency_us:.2f} µs exceeded 50 µs target!"
