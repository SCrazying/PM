"""项目路由。"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import ok, page_result
from app.models.project import ProjectNode
from app.schemas.project import MemberIn, ProjectCreate, ProjectOut, ProjectUpdate
from app.services.audit_service import record_audit
from app.services.project_service import ProjectService

router = APIRouter()


@router.get("")
def list_projects(
    status: str | None = None,
    owner_id: int | None = None,
    machine_model: str | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort_field: str = Query("id"),
    sort_order: str = Query("desc"),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = ProjectService(db)
    items, total = svc.list_projects(status, owner_id, machine_model, keyword, page, size, sort_field, sort_order)
    return page_result([ProjectOut.model_validate(p).model_dump() for p in items], total, page, size)


@router.get("/machine-options")
def list_machine_options(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(ProjectService(db).list_machine_options())


@router.post("")
def create_project(body: ProjectCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = ProjectService(db)
    p = svc.create_project(body, user["user_id"])
    record_audit(db, user["user_id"], "create", "project", str(p.id), {"name": p.name})
    return ok(ProjectOut.model_validate(p).model_dump(), message="创建成功")


@router.get("/{project_id}")
def get_project(project_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = ProjectService(db)
    p = svc.get_project(project_id)
    out = ProjectOut.model_validate(p).model_dump()
    out["members"] = svc.list_members(project_id)
    out["role_assignments"] = svc.list_role_assignments(project_id)
    subs = svc.subnodes_map(project_id)
    # 全部顶层节点（含停用，供编辑勾选/重新启用；前端展示时过滤 is_deleted）
    all_nodes = db.execute(
        select(ProjectNode).where(
            ProjectNode.project_id == project_id, ProjectNode.parent_id.is_(None),
        ).order_by(ProjectNode.sequence)
    ).scalars().all()
    out["nodes"] = [
        {"id": n.id, "node_key": n.node_key, "name": n.name, "sequence": n.sequence, "status": n.status,
         "planned_start": n.planned_start, "planned_end": n.planned_end,
         "actual_start": n.actual_start, "actual_end": n.actual_end,
         "is_deleted": n.is_deleted,
         "overdue": bool(n.status != "passed" and n.planned_end and n.planned_end < date.today()),
         "subnodes": [
             {"id": s.id, "name": s.name, "status": s.status, "planned_end": s.planned_end,
              "actual_end": s.actual_end,
              "overdue": bool(s.status != "done" and s.planned_end and s.planned_end < date.today())}
             for s in subs.get(n.id, [])
         ]}
        for n in all_nodes
    ]
    return ok(out)


@router.put("/{project_id}")
def update_project(project_id: int, body: ProjectUpdate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = ProjectService(db)
    p = svc.update_project(project_id, body, user)
    record_audit(db, user["user_id"], "update", "project", str(project_id), body.model_dump(exclude_none=True))
    return ok(ProjectOut.model_validate(p).model_dump(), message="更新成功")


@router.post("/{project_id}/archive")
def archive_project(project_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    p = ProjectService(db).archive_project(project_id, user, archive=True)
    record_audit(db, user["user_id"], "update", "project", str(project_id), {"status": "archived"})
    return ok(ProjectOut.model_validate(p).model_dump(), message="已归档")


@router.post("/{project_id}/unarchive")
def unarchive_project(project_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    p = ProjectService(db).archive_project(project_id, user, archive=False)
    record_audit(db, user["user_id"], "update", "project", str(project_id), {"status": "in_progress"})
    return ok(ProjectOut.model_validate(p).model_dump(), message="已恢复")


@router.delete("/{project_id}")
def delete_project(project_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    ProjectService(db).delete_project(project_id, user)
    record_audit(db, user["user_id"], "delete", "project", str(project_id))
    return ok(message="已删除")


@router.post("/{project_id}/restore")
def restore_project(project_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = ProjectService(db)
    p = svc.get_project(project_id, include_deleted=True)
    svc.check_owner(p, user)
    svc.restore_projects([project_id])  # 含编号唯一校验与软删级联恢复
    return ok(message="已恢复")


# ---------- 成员 ----------
@router.get("/{project_id}/members")
def list_members(project_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(ProjectService(db).list_members(project_id))


@router.post("/{project_id}/members")
def add_member(project_id: int, body: MemberIn, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    ProjectService(db).add_member(project_id, body, user)
    return ok(message="已添加")


@router.delete("/{project_id}/members/{member_id}")
def remove_member(project_id: int, member_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    ProjectService(db).remove_member(project_id, member_id, user)
    return ok(message="已移除")
