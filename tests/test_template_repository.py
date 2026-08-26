from agentprobe.config import Settings
from agentprobe.models import AttackCategory
from agentprobe.template_repository import MongoAttackTemplateRepository


class AsyncDocuments:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = documents

    def __aiter__(self):
        self.iterator = iter(self.documents)
        return self

    async def __anext__(self):
        try:
            return next(self.iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeCollection:
    def __init__(self) -> None:
        self.pipelines: list[list[dict]] = []

    def aggregate(self, pipeline: list[dict]) -> AsyncDocuments:
        self.pipelines.append(pipeline)
        category = pipeline[0]["$match"]["tags"]
        size = pipeline[1]["$sample"]["size"]
        documents = [
            {
                "id": f"{category}-{index}",
                "category": category,
                "technique": "test",
                "prompt": f"test prompt {index}",
                "source": "MongoTest",
                "tags": [category],
            }
            for index in range(size)
        ]
        return AsyncDocuments(documents)


class FakeDatabase:
    def __init__(self) -> None:
        self.attack_templates = FakeCollection()


async def test_mongodb_repository_samples_each_category() -> None:
    database = FakeDatabase()
    repository = MongoAttackTemplateRepository(
        database, Settings(dataset_enabled=False, groq_api_key=None)
    )
    categories = [AttackCategory.OBFUSCATION, AttackCategory.REPETITION]

    templates = await repository.select(categories, limit=4)

    assert len(templates) == 4
    assert [template.category for template in templates] == categories * 2
    assert all(
        pipeline[1] == {"$sample": {"size": 2}}
        for pipeline in database.attack_templates.pipelines
    )
