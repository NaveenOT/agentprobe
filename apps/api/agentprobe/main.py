from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from agentprobe.config import get_settings
from agentprobe.demo import router as demo_router
from agentprobe.models import CreateRunRequest, ScanRun
from agentprobe.pipeline import ScanPipeline
from agentprobe.repository import (
    MemoryRunRepository,
    MongoRunRepository,
    RunRepository,
    create_mongo_client,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    client = None
    if settings.storage_backend == "mongodb":
        client = create_mongo_client(settings.mongodb_uri)
        database = client[settings.mongodb_database]
        await database.runs.create_index("id", unique=True)
        await database.runs.create_index("created_at")
        app.state.repository = MongoRunRepository(database)
    else:
        app.state.repository = MemoryRunRepository()
    app.state.pipeline = ScanPipeline(app.state.repository, settings)
    yield
    if client:
        client.close()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(demo_router)


def get_repository(request: Request) -> RunRepository:
    return request.app.state.repository


def get_pipeline(request: Request) -> ScanPipeline:
    return request.app.state.pipeline


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "storage": settings.storage_backend,
        "groq_configured": bool(settings.groq_api_key),
    }


@app.get(f"{settings.api_prefix}/system/status")
async def system_status(request: Request) -> dict:
    corpus = request.app.state.pipeline.corpus
    return {
        "groq_configured": bool(settings.groq_api_key),
        "target_provider": settings.demo_provider,
        "agent_model": settings.groq_model,
        "target_model": settings.groq_target_model,
        "dataset": {
            "enabled": settings.dataset_enabled,
            "path": str(settings.dataset_path),
            "exists": settings.dataset_path.exists(),
            "loaded_templates": corpus.loaded_count,
            "total_rows": corpus.total_rows,
            "successful_rows": corpus.successful_rows,
            "error": corpus.error,
        },
    }


@app.post(
    f"{settings.api_prefix}/runs",
    response_model=ScanRun,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_run(
    payload: CreateRunRequest,
    background_tasks: BackgroundTasks,
    repository: RunRepository = Depends(get_repository),
    pipeline: ScanPipeline = Depends(get_pipeline),
) -> ScanRun:
    run = ScanRun(**payload.model_dump())
    await repository.create(run)
    background_tasks.add_task(pipeline.run, run.id)
    return run


@app.get(f"{settings.api_prefix}/runs", response_model=list[ScanRun])
async def list_runs(repository: RunRepository = Depends(get_repository)) -> list[ScanRun]:
    return await repository.list()


@app.get(f"{settings.api_prefix}/runs/{{run_id}}", response_model=ScanRun)
async def get_run(run_id: str, repository: RunRepository = Depends(get_repository)) -> ScanRun:
    run = await repository.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
