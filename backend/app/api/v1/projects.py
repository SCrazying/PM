"""项目路由。"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.responses import BizException, ForbiddenError, NotFoundError, ok, page_result
from app.models.misc import Progress, ProjectRisk
from app.models.project import Project, ProjectMember, ProjectNode
from app.models.user import User
from app.schemas.project import MemberIn, ProjectCreate, ProjectOut, ProjectUpdate
from app.services.audit_service import record_audit
from app.services.project_service import ProjectService

router = APIRouter()


def _check_risk_perm(db: Session, project_id: int, user: dict) -> Project:
    """校验项目存在 + 成员/负责人/admin 可操作风险管理。"""
    project = db.get(Project, project_id)
    if not project or project.is_deleted:
        raise NotFoundError("项目不存在")
    if user["role"] == "admin" or project.owner_id == user["user_id"]:
        return project
    is_member = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user["user_id"],
            ProjectMember.is_deleted.is_(False))
    ).scalar_one_or_none()
    if not is_member:
        raise ForbiddenError("仅项目成员/负责人可管理风险")
    return project


@router.get("/{project_id}/risks")
def list_project_risks(project_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """项目风险管理：合并独立风险(project_risk) + 进展填报风险(progress.risk)。"""
    name_map = {u.id: u.display_name for u in db.execute(select(User)).scalars().all()}
    merged = []
    for pr in db.execute(
        select(ProjectRisk).where(ProjectRisk.project_id == project_id).order_by(ProjectRisk.id)
    ).scalars().all():
        merged.append({
            "key": f"risk:{pr.id}", "id": pr.id, "source": "risk", "risk": pr.risk,
            "resolved": pr.resolved, "date": (pr.created_at.date().isoformat() if pr.created_at else None),
            "author": name_map.get(pr.created_by), "can_delete": True,
        })
    for p, uname in db.execute(
        select(Progress, User.display_name).join(User, User.id == Progress.author_id).where(
            Progress.project_id == project_id,
            Progress.is_deleted.is_(False),
            Progress.risk.isnot(None), Progress.risk != "",
        ).order_by(Progress.progress_date.desc(), Progress.id.desc())
    ).all():
        merged.append({
            "key": f"progress:{p.id}", "id": p.id, "source": "progress", "risk": p.risk,
            "resolved": p.risk_resolved, "date": p.progress_date.isoformat(),
            "author": uname, "can_delete": False,
        })
    return ok(merged)


@router.post("/{project_id}/risks")
def add_project_risk(project_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """项目详情单独添加风险。"""
    _check_risk_perm(db, project_id, user)
    risk = (body.get("risk") or "").strip()
    if not risk:
        raise BizException("风险内容不能为空")
    pr = ProjectRisk(project_id=project_id, risk=risk, created_by=user["user_id"])
    db.add(pr)
    db.commit()
    db.refresh(pr)
    record_audit(db, user["user_id"], "create", "project_risk", str(pr.id), {"project_id": project_id})
    return ok({"id": pr.id}, message="已添加")


@router.patch("/risks/{rid}")
def set_project_risk_resolved(rid: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """关闭/重新打开独立风险。"""
    pr = db.get(ProjectRisk, rid)
    if not pr:
        raise NotFoundError("风险不存在")
    _check_risk_perm(db, pr.project_id, user)
    from datetime import datetime, timezone
    pr.resolved = bool(body.get("resolved"))
    pr.resolved_at = datetime.now(timezone.utc) if pr.resolved else None
    db.commit()
    record_audit(db, user["user_id"], "update", "project_risk", str(rid),
                 {"resolved": bool(body.get("resolved")), "risk": pr.risk})
    return ok({"id": pr.id, "resolved": pr.resolved}, message="已更新")


@router.delete("/risks/{rid}")
def delete_project_risk(rid: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除独立风险。"""
    pr = db.get(ProjectRisk, rid)
    if not pr:
        raise NotFoundError("风险不存在")
    _check_risk_perm(db, pr.project_id, user)
    db.delete(pr)
    db.commit()
    record_audit(db, user["user_id"], "delete", "project_risk", str(rid))
    return ok(message="已删除")


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
    db.commit()  # 修复：restore_projects 不 commit，缺此步恢复会被 session 关闭时回滚
    record_audit(db, user["user_id"], "restore", "project", str(project_id))
    return ok(message="已恢复")


# ---------- 成员 ----------
@router.get("/{project_id}/members")
def list_members(project_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(ProjectService(db).list_members(project_id))


@router.post("/{project_id}/members")
def add_member(project_id: int, body: MemberIn, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    ProjectService(db).add_member(project_id, body, user)
    record_audit(db, user["user_id"], "create", "member", str(project_id),
                 {"user_id": body.user_id, "role": body.project_role, "is_invested": body.is_invested})
    return ok(message="已添加")


@router.delete("/{project_id}/members/{member_id}")
def remove_member(project_id: int, member_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    ProjectService(db).remove_member(project_id, member_id, user)
    record_audit(db, user["user_id"], "delete", "member", str(project_id), {"member_id": member_id})
    return ok(message="已移除")
