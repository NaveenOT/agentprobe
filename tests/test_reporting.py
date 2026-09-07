from agentprobe.models import AttackAttempt, AttackCategory, Evaluation, TokenUsage
from agentprobe.pipeline import build_report


def attempt(category: AttackCategory, success: bool, severity: int) -> AttackAttempt:
    return AttackAttempt(
        template_id="test",
        category=category,
        technique="test",
        prompt="test",
        response="test",
        duration_ms=10,
        evaluation=Evaluation(
            success=success,
            severity=severity,
            confidence=1,
            rationale="test",
        ),
        token_usage={
            "target": TokenUsage(input_tokens=4, output_tokens=2, total_tokens=6, calls=1)
        },
    )


def test_report_aggregates_success_and_categories() -> None:
    report = build_report(
        [
            attempt(AttackCategory.INSTRUCTION, True, 4),
            attempt(AttackCategory.INSTRUCTION, False, 1),
        ],
        duration_ms=120,
    )
    assert report.attack_success_rate == 0.5
    assert report.average_severity == 2.5
    assert report.category_vulnerability["instruction_based"] == 0.5
    assert report.total_tokens == 12
    assert report.token_usage["target"].calls == 2
    assert report.recommendations
