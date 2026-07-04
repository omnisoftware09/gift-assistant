from dataclasses import dataclass


@dataclass
class SlackContext:
    user_id: str
    channel_id: str
    thread_ts: str | None = None
    team_id: str | None = None


@dataclass
class AgentResponse:
    text: str
    blocks: list | None = None
