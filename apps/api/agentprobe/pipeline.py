import asyncio
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
from agentprobe.templates import AttackCorpus


class ScanState(TypedDict):
    run_id: str
    queue: list[dict]
    next_index: int
    started_at: float


class ScanPipeline:
    def __init__(self, repository: RunRepository, settings: Settings) -> None:
        self.repository = repository
        self.evaluator = HybridEvaluator(settings)
        self.agents = GroqAgents(settings)
        self.corpus = AttackCorpus(settings)
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
        await self.repository.save(run)

        response = await create_target_adapter(run.target).send(
            "Briefly describe your purpose and the types of requests you can handle."
        )
        profile_result = await self.agents.profile(response.text)
        run.profile = profile_result.profile
        run.metadata["profile_token_usage"] = profile_result.usage.model_dump()
        run.status = RunStatus.RUNNING
        await self.repository.save(run)
        return {}

    async def _prepare(self, state: ScanState) -> dict:
        run = await self._required_run(state["run_id"])
        templates = await asyncio.to_thread(
            self.corpus.select, run.categories, run.max_attempts, run.profile
        )
        return {"queue": [template.model_dump(mode="json") for template in templates]}

    def _has_attack(self, state: ScanState) -> bool:
        return state["next_index"] < len(state["queue"])

    async def _attack(self, state: ScanState) -> dict:
        run = await self._required_run(state["run_id"])
        template = AttackTemplate.model_validate(state["queue"][state["next_index"]])
        adaptation = await self.agents.adapt(template, run.profile or TargetProfile())
        response = await create_target_adapter(run.target).send(adaptation.prompt)
        evaluation_result = await self.evaluator.evaluate(
            adaptation.prompt, response.text, run.profile or TargetProfile()
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
                    "evaluator": evaluation_result.usage,
                },
            )
        )

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
