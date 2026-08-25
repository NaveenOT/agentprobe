import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from agentprobe.models import TargetConfig, TargetType, TokenUsage


@dataclass
class TargetResponse:
    text: str
    duration_ms: int
    token_usage: TokenUsage = field(default_factory=TokenUsage)


class TargetAdapter(Protocol):
    async def send(self, prompt: str) -> TargetResponse: ...


class ApiTargetAdapter:
    def __init__(self, config: TargetConfig) -> None:
        self.config = config

    async def send(self, prompt: str) -> TargetResponse:
        started = time.perf_counter()
        payload = {
            "model": self.config.model or "demo",
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(str(self.config.url), json=payload)
            if response.is_error:
                try:
                    detail = response.json().get("detail", response.text)
                except ValueError:
                    detail = response.text
                raise RuntimeError(f"Target returned HTTP {response.status_code}: {detail}")
            body = response.json()

        if "response" in body:
            text = body["response"]
        else:
            text = body["choices"][0]["message"]["content"]
        return TargetResponse(
            text=text,
            duration_ms=int((time.perf_counter() - started) * 1000),
            token_usage=TokenUsage.from_mapping(body.get("usage"), called=bool(body.get("usage"))),
        )


class BrowserTargetAdapter:
    def __init__(self, config: TargetConfig) -> None:
        self.config = config

    async def send(self, prompt: str) -> TargetResponse:
        from playwright.async_api import async_playwright

        if not self.config.selectors:
            raise ValueError("Browser selectors are required")

        started = time.perf_counter()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(str(self.config.url), wait_until="networkidle")
            await page.locator(self.config.selectors.input).fill(prompt)
            existing = await page.locator(self.config.selectors.messages).count()
            await page.locator(self.config.selectors.submit).click()
            messages = page.locator(self.config.selectors.messages)
            await messages.nth(existing).wait_for(state="visible", timeout=30_000)
            text = await messages.last.text_content()
            await browser.close()

        return TargetResponse(
            text=text or "",
            duration_ms=int((time.perf_counter() - started) * 1000),
            token_usage=TokenUsage(),
        )


def create_target_adapter(config: TargetConfig) -> TargetAdapter:
    if config.type == TargetType.API:
        return ApiTargetAdapter(config)
    return BrowserTargetAdapter(config)
