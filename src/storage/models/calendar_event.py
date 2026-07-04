from dataclasses import dataclass
from datetime import datetime


@dataclass
class CalendarEvent:
    id: str
    summary: str
    start: datetime
    all_day: bool = False

    def format_line(self) -> str:
        if self.all_day:
            time_str = "All day"
        else:
            time_str = self.start.strftime("%I:%M %p").lstrip("0")
        return f"• {self.summary} — {time_str}"

    def days_until(self) -> int:
        now = datetime.now(self.start.tzinfo)
        event_day = self.start.replace(hour=0, minute=0, second=0, microsecond=0)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return (event_day - today).days

    def when_label(self) -> str:
        days = self.days_until()
        if days == 0:
            return "today"
        if days == 1:
            return "tomorrow"
        return f"in {days} days"
