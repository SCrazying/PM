"""进展、周目标、附件 Schema。"""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------- 进展 ----------
class ProgressCreate(BaseModel):
    project_node_id: Optional[int] = None      # 可空=项目级
    progress_date: date
    today_work: str = Field(min_length=1)
    tomorrow_plan: Optional[str] = None
    risk: Optional[str] = None
    task_ids: List[int] = []                   # 关联任务


class ProgressUpdate(BaseModel):
    today_work: Optional[str] = None
    tomorrow_plan: Optional[str] = None
    risk: Optional[str] = None
    task_ids: Optional[List[int]] = None


class ProgressOut(BaseModel):
    id: int
    project_id: int
    project_node_id: Optional[int]
    node_name: Optional[str] = None
    author_id: int
    author_name: Optional[str] = None
    progress_date: date
    today_work: str
    tomorrow_plan: Optional[str]
    risk: Optional[str]
    task_ids: List[int] = []
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- 周目标 ----------
class WeeklyGoalIn(BaseModel):
    week_start: date
    goal: str = Field(min_length=1)


class WeeklyGoalOut(BaseModel):
    id: int
    project_id: int
    week_start: date
    goal: str

    class Config:
        from_attributes = True


# ---------- 附件 ----------
class AttachmentOut(BaseModel):
    id: int
    project_id: int
    project_node_id: Optional[int]
    task_id: Optional[int]
    review_id: Optional[int]
    file_name: str
    file_size: Optional[int]
    mime_type: Optional[str]
    uploaded_by: Optional[int]
    uploaded_at: datetime

    class Config:
        from_attributes = True
