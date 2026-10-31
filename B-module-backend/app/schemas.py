from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class Module(BaseModel):
    name: str
    question_count: int = Field(ge=0)
    correct_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _correct_not_over_total(self):
        if self.correct_count is not None and self.correct_count > self.question_count:
            raise ValueError("correct_count 不能大于 question_count")
        return self


class RecordBody(BaseModel):
    source_app: str | None = None
    event_date: date | None = None
    event_time: str | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    modules: list[Module] = []
    total_questions: int | None = Field(default=None, ge=0)
    accuracy: float | None = Field(default=None, ge=0, le=1)


class RecordIn(BaseModel):
    """POST /api/records 请求体（A 侧定稿的契约）。"""
    record: RecordBody
    recognition_ref: dict | None = None
    edited_fields: list[str] = []
    confirmed_at: datetime | None = None
    user_id: str = "demo_zhang"
    manual: bool = False
