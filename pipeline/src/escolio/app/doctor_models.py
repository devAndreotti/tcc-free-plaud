from typing import Any, Literal

from pydantic import BaseModel, Field

DoctorStatus = Literal['ok', 'warning', 'error']


class DoctorCheck(BaseModel):
    code: str
    status: DoctorStatus
    message: str
    action: str | None = None
    latency_ms: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class DoctorReport(BaseModel):
    status: DoctorStatus
    checks: list[DoctorCheck]
    latency_ms: int
    ok_count: int
    warning_count: int
    error_count: int
