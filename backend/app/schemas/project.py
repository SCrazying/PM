"""项目、节点、任务相关 Schema。"""
from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class NodePlanIn(BaseModel):
    template_node_id: int
    # 旧客户端兼容字段；新建页面只提交 planned_end。
    planned_start: Optional[date] = None
    planned_end: Optional[date] = None


class NodeDeadlineIn(BaseModel):
    project_node_id: int
    planned_end: Optional[date] = None


# ---------- 项目成员 ----------
class MemberIn(BaseModel):
    user_id: int
    project_role: Optional[str] = None
    is_invested: bool = True


class MemberOut(BaseModel):
    id: int
    user_id: int
    project_role: Optional[str]
    is_invested: bool
    display_name: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- 固定项目角色 ----------
RoleAssignments = Dict[str, List[int]]


# ---------- 项目 ----------
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=1, max_length=64)
    machine_model: Optional[str] = None
    owner_id: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None
    node_ids: List[int] = []          # 立项自选的模板节点 id（tr_template_node.id）
    members: List[MemberIn] = []      # 初始成员
    role_assignments: RoleAssignments = Field(default_factory=dict)
    node_plans: List[NodePlanIn] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    machine_model: Optional[str] = None
    owner_id: Optional[int] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = None
    role_assignments: Optional[RoleAssignments] = None
    node_deadlines: Optional[List[NodeDeadlineIn]] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    code: str
    machine_model: Optional[str]
    owner_id: int
    status: str
    health: str
    current_node_id: Optional[int]
    start_date: Optional[date]
    end_date: Optional[date]
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- 节点 ----------
class NodeOut(BaseModel):
    id: int
    project_id: int
    node_key: str
    name: str
    sequence: int
    status: str
    planned_start: Optional[date]
    planned_end: Optional[date]
    actual_start: Optional[date]
    actual_end: Optional[date]
    overdue: bool = False

    class Config:
        from_attributes = True


class NodeUpdate(BaseModel):
    status: Optional[str] = None
    planned_start: Optional[date] = None
    planned_end: Optional[date] = None
    actual_start: Optional[date] = None
    actual_end: Optional[date] = None


# ---------- 任务 ----------
class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    planned_start: Optional[date] = None
    planned_end: Optional[date] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    planned_start: Optional[date] = None
    planned_end: Optional[date] = None


class TaskStatusUpdate(BaseModel):
    status: str  # todo / in_progress / done


class TaskOut(BaseModel):
    id: int
    project_node_id: int
    project_id: int
    title: str
    description: Optional[str]
    assignee_id: Optional[int]
    status: str
    overdue: bool = False
    planned_start: Optional[date]
    planned_end: Optional[date]
    actual_end: Optional[date]
    created_at: datetime

    class Config:
        from_attributes = True
