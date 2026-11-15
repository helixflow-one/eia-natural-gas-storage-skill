"""Stable error types used by the JSON CLI contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillError(Exception):
    code: str
    message: str
    exit_code: int = 1
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
        }


class InputError(SkillError):
    def __init__(self, message: str, **details: Any) -> None:
        super().__init__("invalid_input", message, 2, details)


class SchemaError(SkillError):
    def __init__(self, message: str, **details: Any) -> None:
        super().__init__("schema_validation_failed", message, 3, details)


class ConfigurationError(SkillError):
    def __init__(self, message: str, **details: Any) -> None:
        super().__init__("configuration_error", message, 4, details)


class RetrievalError(SkillError):
    def __init__(self, message: str, **details: Any) -> None:
        super().__init__("retrieval_error", message, 5, details)

