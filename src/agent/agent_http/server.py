from fastapi import FastAPI, HTTPException, Query

from agent_http.interference_store import InterferenceResultStore
from agent_http.models import (
    InterferenceResponse,
    OnlinePodsRequest,
    OnlinePodsResponse,
    controller_reason_from_code,
)
from agent_http.store import NodeConflictError, PodSnapshotStore


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
            store.replace(request)
        except NodeConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
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
        if interference_store is None:
            return InterferenceResponse.unknown(normalized_node_name)
        result = interference_store.current(normalized_node_name)
        if result is None:
            return InterferenceResponse.unknown(normalized_node_name)
        return InterferenceResponse(
            node_name=normalized_node_name,
            reason=controller_reason_from_code(result.reason_code),
            ttl_seconds=0,
            items=(),
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
