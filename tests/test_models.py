import pytest
from agentprobe.models import TargetConfig, TargetType
from pydantic import ValidationError


def test_target_requires_explicit_authorization() -> None:
    with pytest.raises(ValidationError):
        TargetConfig(type=TargetType.API, url="http://localhost:8000/chat")


def test_browser_target_receives_default_selectors() -> None:
    target = TargetConfig(
        type=TargetType.BROWSER,
        url="http://localhost:8000/demo",
        authorization_confirmed=True,
    )
    assert target.selectors is not None
    assert target.selectors.input == "#message-input"
