from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from radar.adapters.console import log
from radar.domain.ai.prompts import Prompt
from radar.domain.ports.ai.usage_log import Unparsed

T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class Reply:
    text: str
    tokens_in: int
    tokens_out: int
    prompt: str

    def read(self, shape: Callable[[Any], T]) -> T:
        try:
            return shape(json.loads(self.text))
        except (ValueError, LookupError, TypeError) as exc:
            raise Unparsed(f"{self.prompt}: the reply does not fit its shape: {type(exc).__name__}: {exc}",
                           self.tokens_in, self.tokens_out) from exc

def _tokens(usage: Any) -> tuple[int, int]:
    if not usage:
        return 0, 0
    return usage.prompt_token_count or 0, (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)

class AdkRunner:
    def __init__(self, model: str, project: str, location: str, token: str | None = None,
                 base_url: str | None = None) -> None:
        self.model, self._project, self._location, self._token, self._base_url = (
            model, project, location, token, base_url)

    def _agent(self, agent: str, prompt: Prompt, max_tokens: int) -> Any:
        try:
            from google.adk.agents import LlmAgent
            from google.adk.models.google_llm import Gemini
            from google.genai import Client, types
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise RuntimeError("google-adk is not installed: python3 -m pip install -r radar/requirements.txt") from exc

        credentials = Credentials(self._token, quota_project_id=self._project) if self._token else None
        client = Client(vertexai=True, project=self._project, location=self._location, credentials=credentials,
                        http_options=types.HttpOptions(base_url=self._base_url) if self._base_url else None)
        schema = json.loads(prompt.output_schema)
        return LlmAgent(name=agent, model=Gemini(model=self.model, client=client),
                        static_instruction=prompt.instruction, output_schema=schema,
                        generate_content_config=types.GenerateContentConfig(
                            temperature=0, max_output_tokens=max_tokens))

    async def _run(self, agent: str, prompt: Prompt, request: str, max_tokens: int,
                   file: tuple[bytes, str] | None) -> Reply:
        built = self._agent(agent, prompt, max_tokens)
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        runner = InMemoryRunner(agent=built, app_name="mvradar")
        session = await runner.session_service.create_session(app_name="mvradar", user_id=prompt.id)
        text, tokens_in, tokens_out = "", 0, 0
        parts = [types.Part(text=request), *([types.Part.from_bytes(data=file[0], mime_type=file[1])] if file else [])]
        async for event in runner.run_async(user_id=prompt.id, session_id=session.id,
                                            new_message=types.Content(role="user", parts=parts)):
            spent_in, spent_out = _tokens(event.usage_metadata)
            tokens_in, tokens_out = tokens_in + spent_in, tokens_out + spent_out
            if event.is_final_response() and event.content and event.content.parts:
                text = "".join(p.text or "" for p in event.content.parts)
        return Reply(text, tokens_in, tokens_out, prompt.id)

    def run(self, agent: str, prompt: Prompt, request: str, max_tokens: int,
            file: tuple[bytes, str] | None = None) -> Reply:
        if self._project.startswith("demo-"):
            raise RuntimeError("a model call needs Gemini on Vertex AI in the project: pass --project")
        log.debug("model request", prompt=prompt.id, model=self.model, request=request)
        return asyncio.run(self._run(agent, prompt, request, max_tokens, file))
