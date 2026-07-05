from dataclasses import dataclass, field


@dataclass
class SlackContext:
    user_id: str
    channel_id: str
    thread_ts: str | None = None
    team_id: str | None = None


@dataclass
class SlackFile:
    data: bytes
    filename: str
    title: str = ""
    initial_comment: str | None = None


@dataclass
class AgentResponse:
    text: str
    blocks: list | None = None
    files: list[SlackFile] = field(default_factory=list)
    unfurl_links: bool = True
    unfurl_media: bool = True
