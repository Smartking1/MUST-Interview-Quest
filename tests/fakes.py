"""A scripted chat model for keyless tests. It ignores its input and replays responses."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedModel(BaseChatModel):
    responses: list[AIMessage]

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        msg = self.responses.pop(0) if self.responses else AIMessage(content="(script finished)")
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kwargs):
        return self

    @property
    def _llm_type(self) -> str:
        return "scripted"


def call(name: str, args: dict, n: int = 0) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{name}_{n}"}])


def say(text: str) -> AIMessage:
    return AIMessage(content=text)
