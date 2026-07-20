# Controller Pod Cgroup HTTP Integration Design

## 1. Purpose

Extend WAAS Agent so that its existing sampling loop obtains Pod cgroup targets from `kunpeng-qos-controller` over HTTP instead of using a startup-time placeholder or fixed node target.

This first phase is limited to HTTP-driven sampling-target management. The existing `kperf.PmuAttr(cgroupNameList=...)` aggregation behavior is treated as an established capability and is not redesigned here.

## 2. Scope

### In scope

- Serve the Controller `v1` HTTP contract on `127.0.0.1:18080` by default.
- Accept complete online-Pod snapshots from `POST /v1/online-pods`.
- Store the latest snapshot safely across HTTP and sampling threads.
- Supply the snapshot's cgroup paths to the existing `PerfCount`-based sampling loop.
- Recreate the counter only when the effective sampling targets change.
- Pause sampling when the current snapshot contains no Pods.
- Return a valid `unknown` result from `GET /v1/interference` until interference analysis is implemented.
- Preserve the existing processing, IPMI/BMC communication, advice decoding, and handler pipeline after sampling.
- Add focused tests that do not require real Kunpeng hardware or the `kperf` Python module.

### Out of scope

- Implementing `l3`, `mb`, or `cpu` interference classification.
- Changing `kperf`'s aggregation of a cgroup across CPUs.
- Defining a new per-Pod metric output format.
- Changing the BMC binary protocol or register-tuning advice format.
- Adding authentication, TLS, historical persistence, result scoring, or TTL consumption semantics.
- Supporting multiple concurrently sampled Kubernetes nodes in one Agent process.

## 3. Dependencies and Defaults

The HTTP implementation uses:

- FastAPI for routing and dependency injection.
- Pydantic for request and response models.
- Uvicorn as the in-process ASGI server.

The service defaults are:

- Host: `127.0.0.1`
- Port: `18080`
- Protocol version: `v1`

The Agent adds `--http-host` and `--http-port` command-line options. The default remains loopback-only, matching the Controller security boundary.

## 4. Architecture

The Agent remains one process with two execution contexts:

1. The main thread runs Uvicorn and handles HTTP lifecycle and operating-system signals.
2. One sampling worker thread owns all `kperf`/`PerfCount` operations and runs the existing sampling-to-BMC loop.

The two contexts communicate only through a thread-safe `PodSnapshotStore` and a process-wide stop event.

```text
kunpeng-qos-controller
        |
        | POST /v1/online-pods
        v
FastAPI / Uvicorn (main thread)
        |
        | atomic snapshot replacement
        v
PodSnapshotStore
        |
        | target_revision + cgroup_paths
        v
Sampling worker (sole PerfCount owner)
        |
        v
kperf -> DataProcessor -> IPMI/BMC -> advice -> Handler
```

HTTP request handlers never create, close, enable, disable, or read a `PerfCount` object.

## 5. Components

### 5.1 `agent_http.models`

Defines the `v1` API models:

- `OnlinePod`
- `OnlinePodsRequest`
- `OnlinePodsResponse`
- `InterferenceReason`
- `InterferenceItem`
- `InterferenceResponse`

The request timestamp is parsed as an RFC 3339 datetime. Pod cgroup paths are passed to the sampling layer exactly as supplied by the Controller; the Agent does not reconstruct them from Pod names or UIDs.

### 5.2 `agent_http.store`

`PodSnapshotStore` stores one node's latest complete snapshot and provides:

- Atomic snapshot replacement under a lock.
- Immutable snapshot values for readers.
- A condition variable that wakes the sampling worker after a target change or shutdown.
- The most recently received Controller timestamp.
- A monotonically increasing `target_revision`.
- A wait operation that returns when targets change or shutdown is requested.

The process binds to the non-empty `node_name` in the first accepted request, including a request whose Pod list is empty. A later POST for another node is rejected with HTTP 409. An empty Pod list does not remove the node binding; process restart resets it.

Two normalized target sets are equivalent when they contain the same `(pod_uid, cgroup_path)` pairs regardless of array order. A repeated request may update metadata and the received timestamp without incrementing `target_revision`.

Changes to namespace or Pod name alone do not recreate the counter because they do not change the sampling target.

### 5.3 `agent_http.server`

Provides an application factory:

```python
create_app(store: PodSnapshotStore) -> FastAPI
```

It implements:

- `POST /v1/online-pods`
- `GET /v1/interference`
- `GET /healthz`

The application receives the store explicitly rather than using module-level mutable dictionaries. This keeps tests isolated and makes ownership clear.

### 5.4 `sampling_worker`

Contains the sampling-loop orchestration extracted from `main.py`. It receives dependencies explicitly, including a counter factory, so tests can substitute a fake counter.

The production counter factory creates `PerfCount` with the current snapshot's cgroup path list. Downstream processing remains the existing recorder, `DataProcessor`, Messenger, advice decoder, and Handler pipeline.

### 5.5 `main`

`main.py` becomes composition and lifecycle code:

1. Parse CLI arguments.
2. Create the snapshot store and stop event.
3. Construct existing processor, messenger, handlers, and optional recorder dependencies.
4. Start the sampling worker.
5. Run Uvicorn in the main thread.
6. On server exit, signal shutdown, wake the worker, release sampling resources, and join the worker.

## 6. HTTP Contract

### 6.1 Publish online Pods

`POST /v1/online-pods` validates and stores a complete snapshot. It must not wait for a sampling interval or call `kperf`.

A successful request returns HTTP 200:

```json
{
  "accepted": true,
  "message": "online pod snapshot accepted"
}
```

Validation rules:

- `version` must equal `v1`.
- `node_name` must be non-empty.
- Pod UID and cgroup path must be non-empty.
- Pod UIDs must be unique within a snapshot.
- The request is a complete replacement, not an incremental update.
- An empty `pods` array is valid and means that sampling must pause.

Error behavior:

- Pydantic request-shape errors use FastAPI HTTP 422 responses.
- Unsupported protocol versions and snapshot-content errors return HTTP 400.
- A conflicting node name returns HTTP 409.
- Failed requests do not modify the last accepted snapshot.

### 6.2 Get interference

In this phase, `GET /v1/interference?node_name=...` always returns HTTP 200 with a safe result:

```json
{
  "version": "v1",
  "node_name": "node-a",
  "reason": "unknown",
  "ttl_seconds": 0,
  "items": []
}
```

This response is also used before the first snapshot and when the queried node does not match the active node. The endpoint remains stable for a later analyzer implementation.

### 6.3 Health

`GET /healthz` returns HTTP 200 when the HTTP process is alive. It does not claim that PMU collection, BMC communication, or interference analysis is ready.

## 7. Sampling State Machine

The worker behaves as follows:

```text
No accepted snapshot
    -> wait without creating PerfCount

Non-empty targets received
    -> create PerfCount(cgroup_paths)
    -> run existing sampling and downstream loop

Equivalent snapshot received
    -> keep current PerfCount

Changed target set received
    -> finish current sample
    -> discard it if its revision is stale
    -> close old PerfCount
    -> create PerfCount with new cgroup paths

Empty target set received
    -> close current PerfCount
    -> wait for a later non-empty target set

Shutdown requested
    -> wake from any wait
    -> close resources
    -> exit worker
```

The worker captures `target_revision` at the start of sampling. Before forwarding sampled data to the existing downstream pipeline, it checks the current revision. If the revision changed during sampling, the stale sample is discarded.

## 8. Failure Handling

- HTTP validation failure leaves the active sampling target unchanged.
- Counter creation failure is logged and retried after a bounded delay while the same snapshot remains active.
- Sampling failure is logged, the counter is released, and the worker retries with the current snapshot.
- IPMI/BMC or advice-processing failures are logged without terminating the HTTP server.
- An empty target list is a normal idle state, not an error.
- Shutdown signals interrupt snapshot waits through the condition variable.
- The worker closes the current counter and optional recorder on exit.

Retry waits must observe the stop event so shutdown is not delayed unnecessarily.

## 9. Planned File Changes

Add:

```text
src/agent/agent_http/__init__.py
src/agent/agent_http/models.py
src/agent/agent_http/store.py
src/agent/agent_http/server.py
src/agent/sampling_worker.py
test/agent/test_http_server.py
test/agent/test_pod_store.py
test/agent/test_sampling_worker.py
requirements.txt
```

Modify:

```text
src/agent/main.py
src/agent/sample.py
README.en.md
```

Changes to `sample.py` are limited to accepting the current cgroup path list and releasing the counter resource. PMU aggregation semantics are unchanged.

## 10. Testing Strategy

HTTP tests use FastAPI's test client and cover:

- Valid single-Pod, multi-Pod, and empty snapshots.
- Controller-compatible request and response JSON.
- Unsupported version, missing fields, duplicate UIDs, and conflicting node names.
- `GET /v1/interference` before and after snapshot publication.
- `/healthz`.

Store tests cover:

- Complete snapshot replacement.
- Array-order-independent target comparison.
- Timestamp-only and metadata-only updates without revision changes.
- Pod addition, deletion, and cgroup-path replacement with one revision increment.
- Empty snapshots and shutdown wake-up.
- Concurrent reads and updates without partial state exposure.

Sampling worker tests inject fake counters and cover:

- Waiting before the first snapshot.
- Passing Controller cgroup paths to the counter factory unchanged.
- Avoiding recreation for equivalent targets.
- Recreating once for changed targets.
- Closing and pausing for an empty snapshot.
- Discarding a sample whose revision became stale.
- Counter creation and sampling retry behavior.
- Clean worker shutdown.

Unit tests must not import or require the real `kperf` module. A Kunpeng integration test separately verifies that the `cgroupNameList` passed to `kperf.PmuAttr` exactly matches the latest accepted Controller snapshot.

## 11. Acceptance Criteria

- The Agent listens on the configured loopback HTTP endpoint.
- Controller-compatible POST requests receive HTTP 200 and `accepted: true` without waiting for sampling.
- The existing loop does not create a counter before a sampling target exists.
- The counter receives exactly the latest accepted cgroup path list.
- Repeated equivalent snapshots do not recreate the counter.
- Changed and empty snapshots take effect without restarting the Agent.
- HTTP remains responsive while sampling or IPMI/BMC work is running.
- GET interference remains protocol-compatible and safely returns `unknown`.
- The process releases worker and counter resources during shutdown.
- Focused tests pass without Kunpeng hardware or a real `kperf` installation.
