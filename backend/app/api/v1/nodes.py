"""节点与任务路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import ok
from app.models.project import TrTemplate, TrTemplateNode
from app.schemas.project import (
    NodeOut,
    NodeUpdate,
    TaskCreate,
    TaskOut,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.services.audit_service import record_audit
from app.services.project_service import ProjectService

router = APIRouter()


def _node_out(n) -> dict:
    from datetime import date
    out = NodeOut.model_validate(n).model_dump()
    out["overdue"] = bool(n.status != "passed" and n.planned_end and n.planned_end < date.today())
    return out


def _task_out(t) -> dict:
    from datetime import date as _d
    d = TaskOut.model_validate(t).model_dump()
    d["overdue"] = bool(t.status != "done" and t.planned_end and t.planned_end < _d.today())
    return d


# ---------- TR 模板（建项时选择节点用） ----------
@router.get("/tr-templates")
def list_templates(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    tpls = db.execute(select(TrTemplate).where(TrTemplate.status == "active").order_by(TrTemplate.id)).scalars().all()
    out = []
    for t in tpls:
        nodes = db.execute(
            select(TrTemplateNode).where(TrTemplateNode.template_id == t.id).order_by(TrTemplateNode.sequence)
        ).scalars().all()
        out.append({
            "id": t.id, "name": t.name, "description": t.description, "is_builtin": t.is_builtin,
            "nodes": [{"id": n.id, "node_key": n.node_key, "name": n.name, "sequence": n.sequence, "review_focus": n.review_focus} for n in nodes],
        })
    return ok(out)


# ---------- 节点 ----------
@router.get("/projects/{project_id}/nodes")
def list_nodes(project_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    nodes = ProjectService(db).list_nodes(project_id)
    return ok([_node_out(n) for n in nodes])


@router.patch("/nodes/{node_id}")
def update_node(node_id: int, body: NodeUpdate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    n = ProjectService(db).update_node(node_id, body, user)
    record_audit(db, user["user_id"], "update", "node", str(node_id), body.model_dump(exclude_none=True))
    return ok(_node_out(n), message="已更新")


# ---------- 任务 ----------
@router.get("/projects/{project_id}/tasks")
def list_tasks(
    project_id: int,
    node_id: int | None = None,
    status: str | None = None,
    assignee_id: int | None = None,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = ProjectService(db).list_tasks(project_id, node_id, status, assignee_id)
    return ok([_task_out(t) for t in tasks])


@router.post("/nodes/{node_id}/tasks")
def create_task(node_id: int, body: TaskCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    t = ProjectService(db).create_task(node_id, body, user)
    record_audit(db, user["user_id"], "create", "task", str(t.id), {"title": t.title})
    return ok(_task_out(t), message="创建成功")


@router.put("/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    t = ProjectService(db).update_task(task_id, body, user)
    record_audit(db, user["user_id"], "update", "task", str(task_id), body.model_dump(exclude_none=True))
    return ok(_task_out(t), message="已更新")


@router.patch("/tasks/{task_id}/status")
def set_task_status(task_id: int, body: TaskStatusUpdate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    t = ProjectService(db).set_task_status(task_id, body.status, user)
    record_audit(db, user["user_id"], "update", "task", str(task_id), {"status": body.status})
    return ok(_task_out(t), message="已更新")


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    ProjectService(db).delete_task(task_id, user)
    record_audit(db, user["user_id"], "delete", "task", str(task_id))
    return ok(message="已删除")
