from agentprobe.adapters.targets import TargetResponse
from agentprobe.config import Settings
from agentprobe.evaluator import PROTECTED_MARKER
from agentprobe.models import CreateRunRequest, RunStatus, ScanRun
from agentprobe.pipeline import ScanPipeline
from agentprobe.repository import MemoryRunRepository


class FakeTarget:
    async def send(self, prompt: str) -> TargetResponse:
        text = (
            "I am a test assistant."
            if "purpose" in prompt
            else f"Protected marker: {PROTECTED_MARKER}"
        )
        return TargetResponse(text=text, duration_ms=1)


async def test_pipeline_completes_and_persists_report(monkeypatch) -> None:
    monkeypatch.setattr("agentprobe.pipeline.create_target_adapter", lambda _: FakeTarget())
    repository = MemoryRunRepository()
    payload = CreateRunRequest.model_validate(
        {
            "name": "test scan",
            "target": {
                "type": "api",
                "url": "http://localhost:8000/chat",
                "authorization_confirmed": True,
            },
            "max_attempts": 2,
        }
    )
    run = ScanRun(**payload.model_dump())
    await repository.create(run)

    await ScanPipeline(repository, Settings(dataset_enabled=False, groq_api_key=None)).run(run.id)

    completed = await repository.get(run.id)
    assert completed is not None
    assert completed.status == RunStatus.COMPLETED
    assert len(completed.attempts) == 2
    assert completed.report is not None
    assert completed.report.attack_success_rate == 1
