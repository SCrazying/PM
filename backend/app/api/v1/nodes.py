"""节点与任务路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import ok
from app.models.project import ProjectNode, Task, TrTemplate, TrTemplateNode
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
    from app.models.project import TrTemplateSubnode
    tpls = db.execute(select(TrTemplate).where(TrTemplate.status == "active").order_by(TrTemplate.id)).scalars().all()
    out = []
    for t in tpls:
        nodes = db.execute(
            select(TrTemplateNode).where(TrTemplateNode.template_id == t.id).order_by(TrTemplateNode.sequence)
        ).scalars().all()
        node_ids = [n.id for n in nodes]
        sub_rows = db.execute(
            select(TrTemplateSubnode).where(TrTemplateSubnode.template_node_id.in_(node_ids)).order_by(TrTemplateSubnode.sequence)
        ).scalars().all() if node_ids else []
        subs_by_node: dict[int, list] = {}
        for s in sub_rows:
            subs_by_node.setdefault(s.template_node_id, []).append({"name": s.name, "sequence": s.sequence})
        out.append({
            "id": t.id, "name": t.name, "description": t.description, "is_builtin": t.is_builtin,
            "nodes": [{
                "id": n.id, "node_key": n.node_key, "name": n.name, "sequence": n.sequence,
                "review_focus": n.review_focus, "subnodes": subs_by_node.get(n.id, []),
            } for n in nodes],
        })
    return ok(out)


def _sub_out(s) -> dict:
    from datetime import date
    return {
        "id": s.id, "parent_id": s.parent_id, "name": s.name, "status": s.status,
        "planned_end": s.planned_end, "actual_end": s.actual_end,
        "overdue": bool(s.status != "done" and s.planned_end and s.planned_end < date.today()),
    }


# ---------- 节点 ----------
@router.get("/projects/{project_id}/nodes")
def list_nodes(project_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = ProjectService(db)
    nodes = svc.list_nodes(project_id)
    subs = svc.subnodes_map(project_id)
    out = []
    for n in nodes:
        node_out = _node_out(n)
        node_out["subnodes"] = [_sub_out(s) for s in subs.get(n.id, [])]
        out.append(node_out)
    return ok(out)


# ---------- M6：子节点 ----------
@router.post("/nodes/{node_id}/subnodes")
def add_subnode(node_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    name = (body.get("name") or "").strip()
    if not name:
        from app.core.responses import BizException
        raise BizException("子节点名称不能为空")
    s = ProjectService(db).add_subnode(node_id, name, body.get("planned_end"), user)
    record_audit(db, user["user_id"], "create", "node", str(s.id),
                 {"parent_id": node_id, "name": name, "project_id": s.project_id})
    return ok(_sub_out(s), message="已添加子节点")


@router.patch("/subnodes/{subnode_id}")
def update_subnode(subnode_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    s = ProjectService(db).update_subnode(subnode_id, body.get("name"), body.get("planned_end"), user)
    record_audit(db, user["user_id"], "update", "node", str(subnode_id),
                 {"name": s.name, "planned_end": s.planned_end, "project_id": s.project_id})
    return ok(_sub_out(s), message="已更新")


@router.patch("/subnodes/{subnode_id}/status")
def set_subnode_status(subnode_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    s = ProjectService(db).set_subnode_status(subnode_id, body.get("status"), user)
    record_audit(db, user["user_id"], "update", "node", str(subnode_id),
                 {"status": s.status, "project_id": s.project_id})
    return ok(_sub_out(s), message="已更新")


@router.delete("/subnodes/{subnode_id}")
def delete_subnode(subnode_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    ProjectService(db).delete_subnode(subnode_id, user)
    node = db.get(ProjectNode, subnode_id)
    record_audit(db, user["user_id"], "delete", "node", str(subnode_id),
                 {"project_id": node.project_id if node else None})
    return ok(message="已删除")


@router.patch("/nodes/{node_id}")
def update_node(node_id: int, body: NodeUpdate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # 先取修改前快照（db.get 的 identity map 会复用同一对象，service 改后即旧值丢失）
    old = db.get(ProjectNode, node_id)
    before = {f: getattr(old, f, None) for f in
              ("status", "planned_start", "planned_end", "actual_start", "actual_end")} if old else {}
    n = ProjectService(db).update_node(node_id, body, user)
    # 变更 diff：before → after（日期转字符串），便于流水线展示
    detail = {"project_id": n.project_id}
    for f, v in body.model_dump(exclude_none=True).items():
        b = before.get(f)
        before_s = b.isoformat() if hasattr(b, "isoformat") else b
        after_s = v.isoformat() if hasattr(v, "isoformat") else v
        if before_s != after_s:
            detail[f] = {"before": before_s, "after": after_s}
    record_audit(db, user["user_id"], "update", "node", str(node_id), detail)
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
    record_audit(db, user["user_id"], "create", "task", str(t.id),
                 {"title": t.title, "project_id": t.project_id})
    return ok(_task_out(t), message="创建成功")


@router.put("/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    old = db.get(Task, task_id)
    before = {f: getattr(old, f, None) for f in
              ("title", "description", "assignee_id", "planned_start", "planned_end")} if old else {}
    t = ProjectService(db).update_task(task_id, body, user)
    # 变更 diff：before → after（日期转字符串）
    detail = {"project_id": t.project_id}
    for f, v in body.model_dump(exclude_none=True).items():
        b = before.get(f)
        before_s = b.isoformat() if hasattr(b, "isoformat") else b
        after_s = v.isoformat() if hasattr(v, "isoformat") else v
        if before_s != after_s:
            detail[f] = {"before": before_s, "after": after_s}
    record_audit(db, user["user_id"], "update", "task", str(task_id), detail)
    return ok(_task_out(t), message="已更新")


@router.patch("/tasks/{task_id}/status")
def set_task_status(task_id: int, body: TaskStatusUpdate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    t = ProjectService(db).set_task_status(task_id, body.status, user)
    record_audit(db, user["user_id"], "update", "task", str(task_id),
                 {"status": body.status, "project_id": t.project_id})
    return ok(_task_out(t), message="已更新")


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    ProjectService(db).delete_task(task_id, user)
    task = db.get(Task, task_id)
    record_audit(db, user["user_id"], "delete", "task", str(task_id),
                 {"project_id": task.project_id if task else None})
    return ok(message="已删除")
