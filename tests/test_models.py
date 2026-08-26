import pytest
from agentprobe.models import (
    AttackCategory,
    AttackTemplate,
    BrowserSessionRequest,
    TargetConfig,
    TargetType,
)
from pydantic import ValidationError


def test_target_requires_explicit_authorization() -> None:
    with pytest.raises(ValidationError):
        TargetConfig(type=TargetType.API, url="http://localhost:8000/chat")


def test_browser_target_uses_auto_detection_without_selectors() -> None:
    target = TargetConfig(
        type=TargetType.BROWSER,
        url="http://localhost:8000/demo",
        authorization_confirmed=True,
    )
    assert target.selectors is None


def test_browser_login_session_requires_authorization() -> None:
    with pytest.raises(ValidationError):
        BrowserSessionRequest(url="https://example.com")


def test_attack_template_uses_category_as_tag() -> None:
    template = AttackTemplate(
        id="test",
        category=AttackCategory.OBFUSCATION,
        technique="test",
        prompt="test prompt",
    )
    assert template.tags == ["obfuscation"]
