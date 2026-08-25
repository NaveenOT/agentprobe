from collections import defaultdict

from agentprobe.models import AttackAttempt, Report, TokenUsage

CATEGORY_RECOMMENDATIONS = {
    "instruction_based": (
        "Reinforce instruction hierarchy and reject user attempts to redefine policy."
    ),
    "task_deflection": "Bind each request to the application's intended task before execution.",
    "repetition": "Normalize repeated directives and apply policy checks after normalization.",
    "context_switching": "Do not let conversational context alter immutable system constraints.",
    "variable_code_based": (
        "Treat code and variable content as data unless execution is explicitly required."
    ),
    "formatting": "Apply the same policy checks after parsing structured and formatted input.",
    "obfuscation": "Canonicalize encoded or obfuscated input before safety classification.",
    "cognitive_role_based": "Prevent role-play requests from granting additional privileges.",
    "indirect": "Label external content as untrusted and isolate it from system instructions.",
}


def build_report(
    attempts: list[AttackAttempt],
    duration_ms: int,
    profile_usage: TokenUsage | None = None,
) -> Report:
    successes = [attempt for attempt in attempts if attempt.evaluation.success]
    category_totals: dict[str, int] = defaultdict(int)
    category_successes: dict[str, int] = defaultdict(int)
    for attempt in attempts:
        category = attempt.category.value
        category_totals[category] += 1
        if attempt.evaluation.success:
            category_successes[category] += 1

    vulnerable_categories = sorted({attempt.category.value for attempt in successes})
    recommendations = [CATEGORY_RECOMMENDATIONS[category] for category in vulnerable_categories]
    if not recommendations:
        recommendations.append(
            "Retain layered input validation and rerun this suite after model changes."
        )

    token_usage: dict[str, TokenUsage] = {"profiler": profile_usage or TokenUsage()}
    for attempt in attempts:
        for role, usage in attempt.token_usage.items():
            token_usage[role] = token_usage.get(role, TokenUsage()).plus(usage)
    total_tokens = sum(usage.total_tokens for usage in token_usage.values())

    return Report(
        total_attacks=len(attempts),
        successful_attacks=len(successes),
        attack_success_rate=round(len(successes) / len(attempts), 3) if attempts else 0,
        average_severity=round(
            sum(attempt.evaluation.severity for attempt in attempts) / len(attempts), 2
        )
        if attempts
        else 0,
        category_vulnerability={
            category: round(category_successes[category] / total, 3)
            for category, total in category_totals.items()
        },
        duration_ms=duration_ms,
        recommendations=recommendations,
        token_usage=token_usage,
        total_tokens=total_tokens,
    )
