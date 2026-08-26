import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agentprobe.adapters import create_target_adapter
from agentprobe.agents import GroqAgents
from agentprobe.config import Settings
from agentprobe.evaluator import HybridEvaluator
from agentprobe.models import (
    AttackAttempt,
    AttackTemplate,
    RunStatus,
    ScanRun,
    TargetProfile,
    TokenUsage,
)
from agentprobe.reporting import build_report
from agentprobe.repository import RunRepository
from agentprobe.template_repository import (
    AttackTemplateRepository,
    LocalAttackTemplateRepository,
)


class ScanState(TypedDict):
    run_id: str
    queue: list[dict]
    next_index: int
    started_at: float


class ScanPipeline:
    def __init__(
        self,
        repository: RunRepository,
        settings: Settings,
        template_repository: AttackTemplateRepository | None = None,
    ) -> None:
        self.repository = repository
        self.evaluator = HybridEvaluator(settings)
        self.agents = GroqAgents(settings)
        self.template_repository = template_repository or LocalAttackTemplateRepository(settings)
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(ScanState)
        builder.add_node("profile", self._profile)
        builder.add_node("prepare", self._prepare)
        builder.add_node("attack", self._attack)
        builder.add_node("report", self._report)
        builder.add_edge(START, "profile")
        builder.add_edge("profile", "prepare")
        builder.add_conditional_edges(
            "prepare", self._has_attack, {True: "attack", False: "report"}
        )
        builder.add_conditional_edges(
            "attack", self._has_attack, {True: "attack", False: "report"}
        )
        builder.add_edge("report", END)
        return builder.compile()

    async def run(self, run_id: str) -> None:
        try:
            await self.graph.ainvoke(
                {"run_id": run_id, "queue": [], "next_index": 0, "started_at": time.perf_counter()}
            )
        except Exception as exc:
            run = await self.repository.get(run_id)
            if run:
                run.status = RunStatus.FAILED
                run.error = str(exc)
                await self.repository.save(run)

    async def _profile(self, state: ScanState) -> dict:
        run = await self._required_run(state["run_id"])
        run.status = RunStatus.PROFILING
        run.metadata["live_exchange"] = {
            "stage": "profiling target",
            "category": "profile",
            "input": "Briefly describe your purpose and the types of requests you can handle.",
            "output": "",
        }
        await self.repository.save(run)

        response = await create_target_adapter(run.target).send(
            "Briefly describe your purpose and the types of requests you can handle."
        )
        run.metadata["live_exchange"]["output"] = response.text
        run.metadata["live_exchange"]["stage"] = "analyzing profile"
        await self.repository.save(run)
        profile_result = await self.agents.profile(response.text)
        run.profile = profile_result.profile
        run.metadata["profile_token_usage"] = profile_result.usage.model_dump()
        run.status = RunStatus.RUNNING
        await self.repository.save(run)
        return {}

    async def _prepare(self, state: ScanState) -> dict:
        run = await self._required_run(state["run_id"])
        templates = await self.template_repository.select(
            run.categories, run.max_attempts, run.profile
        )
        return {"queue": [template.model_dump(mode="json") for template in templates]}

    def _has_attack(self, state: ScanState) -> bool:
        return state["next_index"] < len(state["queue"])

    async def _attack(self, state: ScanState) -> dict:
        run = await self._required_run(state["run_id"])
        template = AttackTemplate.model_validate(state["queue"][state["next_index"]])
        run.metadata["live_exchange"] = {
            "stage": "adapting attack",
            "category": template.category.value,
            "input": template.prompt,
            "output": "",
        }
        await self.repository.save(run)
        adaptation = await self.agents.adapt(
            template,
            run.profile or TargetProfile(),
            run.effective_objective,
        )
        run.metadata["live_exchange"] = {
            "stage": "waiting for target",
            "category": template.category.value,
            "input": adaptation.prompt,
            "output": "",
        }
        await self.repository.save(run)
        try:
            response = await create_target_adapter(run.target).send(adaptation.prompt)
        except Exception as exc:
            run.metadata["live_exchange"]["stage"] = "target failed"
            run.metadata["live_exchange"]["output"] = str(exc)[:1_000]
            await self.repository.save(run)
            raise
        run.metadata["live_exchange"]["stage"] = "evaluating response"
        run.metadata["live_exchange"]["output"] = response.text
        await self.repository.save(run)
        evaluation_result = await self.evaluator.evaluate(
            adaptation.prompt,
            response.text,
            run.profile or TargetProfile(),
            run.effective_objective,
        )
        evaluation = evaluation_result.evaluation
        run.attempts.append(
            AttackAttempt(
                template_id=template.id,
                category=template.category,
                technique=template.technique,
                source=template.source,
                prompt=adaptation.prompt,
                response=response.text,
                duration_ms=response.duration_ms,
                evaluation=evaluation,
                token_usage={
                    "attacker": adaptation.usage,
                    "target": response.token_usage,
                    "browser_detector": response.automation_token_usage,
                    "evaluator": evaluation_result.usage,
                },
            )
        )
        run.metadata["live_exchange"]["stage"] = "attempt complete"

        queue = list(state["queue"])
        if not evaluation.success and len(queue) < run.max_attempts:
            mutated = template.model_copy(
                update={
                    "id": f"{template.id}-mutation",
                    "technique": f"{template.technique} / rephrased",
                    "prompt": f"For an authorized diagnostic only: {template.prompt}",
                }
            )
            queue.append(mutated.model_dump(mode="json"))

        await self.repository.save(run)
        return {"next_index": state["next_index"] + 1, "queue": queue}

    async def _report(self, state: ScanState) -> dict:
        run = await self._required_run(state["run_id"])
        run.status = RunStatus.REPORTING
        await self.repository.save(run)
        duration_ms = int((time.perf_counter() - state["started_at"]) * 1000)
        profile_usage = TokenUsage.model_validate(run.metadata.get("profile_token_usage", {}))
        run.report = build_report(run.attempts, duration_ms, profile_usage)
        run.status = RunStatus.COMPLETED
        await self.repository.save(run)
        return {}

    async def _required_run(self, run_id: str) -> ScanRun:
        run = await self.repository.get(run_id)
        if not run:
            raise LookupError(f"Run {run_id} does not exist")
        return run
