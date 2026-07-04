from dataclasses import dataclass


@dataclass
class GiftRequest:
    recipient: str
    occasion: str | None = None
    raw_message: str = ""

    def summary(self) -> str:
        if self.occasion:
            return f"{self.recipient}'s {self.occasion}"
        return self.recipient
