from typing import Any


class ProcessingStep:
    def __init__(
        self, title: str, type: str, content: Any, description: str | None = None
    ):
        self.title = title
        self.description = description
        self.type = type
        self.content = content

    def to_dict(self):
        return {
            "title": self.title,
            "description": self.description,
            "type": self.type,
            "content": self.content,
        }
