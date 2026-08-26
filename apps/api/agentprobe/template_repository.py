import asyncio
import math
from collections import defaultdict
from typing import Protocol

from motor.motor_asyncio import AsyncIOMotorDatabase

from agentprobe.config import Settings
from agentprobe.models import AttackCategory, AttackTemplate, TargetProfile
from agentprobe.templates import AttackCorpus


class AttackTemplateRepository(Protocol):
    async def select(
        self,
        categories: list[AttackCategory],
        limit: int,
        profile: TargetProfile | None = None,
    ) -> list[AttackTemplate]: ...

    async def count(self) -> int: ...


class LocalAttackTemplateRepository:
    def __init__(self, settings: Settings) -> None:
        self.corpus = AttackCorpus(settings)

    async def select(
        self,
        categories: list[AttackCategory],
        limit: int,
        profile: TargetProfile | None = None,
    ) -> list[AttackTemplate]:
        return await asyncio.to_thread(self.corpus.select, categories, limit, profile)

    async def count(self) -> int:
        return self.corpus.loaded_count


class MongoAttackTemplateRepository:
    def __init__(self, database: AsyncIOMotorDatabase, settings: Settings) -> None:
        self.collection = database.attack_templates
        self.fallback = LocalAttackTemplateRepository(settings)

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("id", unique=True)
        await self.collection.create_index("tags")
        await self.collection.create_index([("category", 1), ("source", 1)])

    async def select(
        self,
        categories: list[AttackCategory],
        limit: int,
        profile: TargetProfile | None = None,
    ) -> list[AttackTemplate]:
        if not categories or limit <= 0:
            return []

        per_category = math.ceil(limit / len(categories))
        sampled = await asyncio.gather(
            *(self._sample_category(category, per_category) for category in categories)
        )
        grouped = {
            category: templates for category, templates in zip(categories, sampled, strict=True)
        }
        selected: list[AttackTemplate] = []
        offsets: dict[AttackCategory, int] = defaultdict(int)
        while len(selected) < limit:
            added = False
            for category in categories:
                offset = offsets[category]
                candidates = grouped[category]
                if offset < len(candidates):
                    selected.append(candidates[offset])
                    offsets[category] += 1
                    added = True
                    if len(selected) == limit:
                        break
            if not added:
                break

        if len(selected) < limit:
            fallback = await self.fallback.select(categories, limit - len(selected), profile)
            existing_ids = {template.id for template in selected}
            selected.extend(template for template in fallback if template.id not in existing_ids)
        return selected[:limit]

    async def _sample_category(
        self, category: AttackCategory, limit: int
    ) -> list[AttackTemplate]:
        cursor = self.collection.aggregate(
            [
                {"$match": {"tags": category.value}},
                {"$sample": {"size": limit}},
                {"$project": {"_id": 0}},
            ]
        )
        return [AttackTemplate.model_validate(document) async for document in cursor]

    async def count(self) -> int:
        return await self.collection.count_documents({})
