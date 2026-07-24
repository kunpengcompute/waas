import logging

from fastapi import FastAPI, HTTPException, Query

from agent_http.interference_store import InterferenceResultStore
from agent_http.models import (
    InterferenceReason,
    InterferenceResponse,
    OnlinePodsRequest,
    OnlinePodsResponse,
    controller_reason_from_code,
)
from agent_http.store import NodeConflictError, PodSnapshotStore


_ACTIVE_INTERFERENCE_REASON_ORDER = (
    InterferenceReason.CPU,
    InterferenceReason.MB,
    InterferenceReason.L3,
)


def create_app(
    store: PodSnapshotStore,
    interference_store: InterferenceResultStore | None = None,
) -> FastAPI:
    app = FastAPI(title="WAAS Agent", version="v1")

    @app.post("/v1/online-pods", response_model=OnlinePodsResponse)
    async def update_online_pods(request: OnlinePodsRequest) -> OnlinePodsResponse:
        if request.version != "v1":
            raise HTTPException(
                status_code=400,
                detail=f"unsupported version: {request.version}",
            )
        try:
            snapshot = store.replace(request)
        except NodeConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        logging.info(
            "received online pod snapshot: node=%s timestamp=%s "
            "pod_count=%d revision=%d",
            snapshot.node_name,
            snapshot.timestamp.isoformat(),
            len(snapshot.pods),
            snapshot.target_revision,
        )
        for pod in snapshot.pods:
            logging.info(
                "online pod: namespace=%s name=%s uid=%s cgroup_path=%s",
                pod.namespace,
                pod.name,
                pod.uid,
                pod.cgroup_path,
            )
        return OnlinePodsResponse(
            accepted=True,
            message="online pod snapshot accepted",
        )

    @app.get("/v1/interference", response_model=InterferenceResponse)
    async def get_interference(
        node_name: str = Query(min_length=1),
    ) -> InterferenceResponse:
        normalized_node_name = node_name.strip()
        if not normalized_node_name:
            raise HTTPException(status_code=422, detail="node name must not be empty")
        result = (
            interference_store.current(normalized_node_name)
            if interference_store is not None
            else None
        )
        if result is None:
            response = InterferenceResponse.empty(normalized_node_name)
            logging.info(
                "return interference result: node=%s reasons=[] source=no_result",
                normalized_node_name,
            )
            return response
        mapped_reasons = {
            reason
            for reason_code in result.reason_codes
            if (reason := controller_reason_from_code(reason_code)) is not None
        }
        reasons = tuple(
            reason
            for reason in _ACTIVE_INTERFERENCE_REASON_ORDER
            if reason in mapped_reasons
        )
        if not reasons and InterferenceReason.NONE in mapped_reasons:
            reasons = (InterferenceReason.NONE,)
        response = InterferenceResponse(
            node_name=normalized_node_name,
            reasons=reasons,
        )
        logging.info(
            "return interference result: node=%s reason_codes=%s reasons=%s "
            "timestamp=%s",
            normalized_node_name,
            result.reason_codes,
            [reason.value for reason in response.reasons],
            result.timestamp.isoformat(),
        )
        return response

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
