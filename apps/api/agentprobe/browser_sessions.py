import asyncio
from pathlib import Path


class BrowserSessionManager:
    def __init__(self, profile_dir: Path) -> None:
        self.profile_dir = profile_dir
        self.active = False
        self.error: str | None = None

    async def open(self, url: str) -> None:
        if self.active:
            return

        from playwright.async_api import async_playwright

        self.active = True
        self.error = None
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            async with async_playwright() as playwright:
                context = await playwright.chromium.launch_persistent_context(
                    str(self.profile_dir), headless=False
                )
                closed = asyncio.Event()
                context.on("close", lambda _: closed.set())
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                await closed.wait()
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.active = False

    def status(self) -> dict[str, str | bool | None]:
        return {
            "active": self.active,
            "profile_exists": self.profile_dir.exists(),
            "error": self.error,
        }
