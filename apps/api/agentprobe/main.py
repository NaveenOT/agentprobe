from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from agentprobe.browser_sessions import BrowserSessionManager
from agentprobe.config import get_settings
from agentprobe.demo import router as demo_router
from agentprobe.models import BrowserSessionRequest, CreateRunRequest, ScanRun
from agentprobe.objectives import attack_outcome_mode, normalize_attack_outcome
from agentprobe.pipeline import ScanPipeline
from agentprobe.repository import (
    MemoryRunRepository,
    MongoRunRepository,
    RunRepository,
    create_mongo_client,
)
from agentprobe.template_repository import (
    LocalAttackTemplateRepository,
    MongoAttackTemplateRepository,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    client = None
    database = None
    if settings.storage_backend == "mongodb" or settings.template_backend == "mongodb":
        client = create_mongo_client(settings.mongodb_uri)
        database = client[settings.mongodb_database]
    if settings.storage_backend == "mongodb" and database is not None:
        await database.runs.create_index("id", unique=True)
        await database.runs.create_index("created_at")
        app.state.repository = MongoRunRepository(database)
    else:
        app.state.repository = MemoryRunRepository()
    if settings.template_backend == "mongodb" and database is not None:
        template_repository = MongoAttackTemplateRepository(database, settings)
        await template_repository.ensure_indexes()
    else:
        template_repository = LocalAttackTemplateRepository(settings)
    app.state.browser_sessions = BrowserSessionManager(settings.browser_profile_dir)
    app.state.pipeline = ScanPipeline(
        app.state.repository, settings, template_repository=template_repository
    )
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
    template_repository = request.app.state.pipeline.template_repository
    return {
        "groq_configured": bool(settings.groq_api_key),
        "target_provider": settings.demo_provider,
        "agent_model": settings.groq_model,
        "target_model": settings.groq_target_model,
        "ai_dom_detection": settings.ai_dom_detection,
        "template_backend": settings.template_backend,
        "template_count": await template_repository.count(),
        "dataset": {
            "enabled": settings.dataset_enabled,
            "path": str(settings.dataset_path),
            "exists": settings.dataset_path.exists(),
            "loaded_templates": 0,
            "total_rows": 0,
            "successful_rows": 0,
            "error": None,
        },
    }


@app.post(f"{settings.api_prefix}/browser/session", status_code=status.HTTP_202_ACCEPTED)
async def open_browser_session(
    payload: BrowserSessionRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict[str, str]:
    manager = request.app.state.browser_sessions
    if manager.active:
        raise HTTPException(status_code=409, detail="A browser login session is already open")
    background_tasks.add_task(manager.open, str(payload.url))
    return {
        "status": "opening",
        "message": "Complete login in the browser window, then close it before starting a scan.",
    }


@app.get(f"{settings.api_prefix}/browser/session")
async def browser_session_status(request: Request) -> dict:
    return request.app.state.browser_sessions.status()


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
    run_data = payload.model_dump()
    requested_outcome = (run_data.pop("attack_outcome") or "").strip()
    effective_objective = normalize_attack_outcome(requested_outcome)
    run = ScanRun(
        **run_data,
        requested_outcome=requested_outcome,
        effective_objective=effective_objective,
        objective_mode=attack_outcome_mode(effective_objective),
    )
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
