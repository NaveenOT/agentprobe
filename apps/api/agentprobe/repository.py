from typing import Protocol

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from agentprobe.models import ScanRun, utc_now


class RunRepository(Protocol):
    async def create(self, run: ScanRun) -> ScanRun: ...
    async def get(self, run_id: str) -> ScanRun | None: ...
    async def list(self, limit: int = 50) -> list[ScanRun]: ...
    async def save(self, run: ScanRun) -> ScanRun: ...


class MongoRunRepository:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database.runs

    async def create(self, run: ScanRun) -> ScanRun:
        await self.collection.insert_one(run.model_dump(mode="json"))
        return run

    async def get(self, run_id: str) -> ScanRun | None:
        document = await self.collection.find_one({"id": run_id}, {"_id": 0})
        return ScanRun.model_validate(document) if document else None

    async def list(self, limit: int = 50) -> list[ScanRun]:
        cursor = self.collection.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
        return [ScanRun.model_validate(document) async for document in cursor]

    async def save(self, run: ScanRun) -> ScanRun:
        run.updated_at = utc_now()
        await self.collection.replace_one({"id": run.id}, run.model_dump(mode="json"), upsert=True)
        return run


class MemoryRunRepository:
    def __init__(self) -> None:
        self.runs: dict[str, ScanRun] = {}

    async def create(self, run: ScanRun) -> ScanRun:
        self.runs[run.id] = run.model_copy(deep=True)
        return run

    async def get(self, run_id: str) -> ScanRun | None:
        run = self.runs.get(run_id)
        return run.model_copy(deep=True) if run else None

    async def list(self, limit: int = 50) -> list[ScanRun]:
        runs = sorted(self.runs.values(), key=lambda run: run.created_at, reverse=True)
        return [run.model_copy(deep=True) for run in runs[:limit]]

    async def save(self, run: ScanRun) -> ScanRun:
        run.updated_at = utc_now()
        self.runs[run.id] = run.model_copy(deep=True)
        return run


def create_mongo_client(uri: str) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(uri)
