"""M2 路由：进展、周目标、周报、看板、节点流转、通知。"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.responses import ok
from app.engines.board_engine import BoardService
from app.engines.node_flow_engine import NodeFlowService
from app.engines.report_engine import ReportService
from app.schemas.progress import ProgressCreate, ProgressUpdate, WeeklyGoalIn
from app.services.audit_service import record_audit
from app.services.progress_service import ProgressService

router = APIRouter()


# ---------- 进展 ----------
@router.get("/projects/{project_id}/progress")
def list_progress(project_id: int, date_from: date | None = None, date_to: date | None = None,
                  author_id: int | None = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(ProgressService(db).list_progress(project_id, date_from, date_to, author_id))


@router.post("/projects/{project_id}/progress")
def create_progress(project_id: int, body: ProgressCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    p = ProgressService(db).create_progress(project_id, body, user)
    db.commit()
    return ok({"id": p.id}, message="填报成功")


@router.put("/progress/{progress_id}")
def update_progress(progress_id: int, body: ProgressUpdate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    progress = ProgressService(db).update_progress(progress_id, body, user)
    db.commit()
    record_audit(db, user["user_id"], "update", "progress", str(progress_id), body.model_dump(exclude_none=True))
    return ok(message="已更新")


@router.delete("/progress/{progress_id}")
def delete_progress(progress_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    ProgressService(db).delete_progress(progress_id, user)
    return ok(message="已删除")


@router.patch("/progress/{progress_id}/risk-resolve")
def set_risk_resolved(progress_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    p = ProgressService(db).set_risk_resolved(progress_id, bool(body.get("resolved")), user)
    db.commit()
    return ok({"id": p.id, "resolved": p.risk_resolved}, message="已关闭风险" if p.risk_resolved else "已重新打开")


@router.get("/progress/mine/todo")
def my_todo(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(ProgressService(db).my_todo(user))


# ---------- 周目标 ----------
@router.get("/projects/{project_id}/weekly-goal")
def get_weekly_goal(project_id: int, week_start: date = Query(...), user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    row = ProgressService(db).get_weekly_goal(project_id, week_start)
    return ok({"goal": row.goal, "week_start": row.week_start} if row else {"goal": None, "week_start": ProgressService(db).week_start_of(week_start)})


@router.put("/projects/{project_id}/weekly-goal")
def set_weekly_goal(project_id: int, body: WeeklyGoalIn, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    row = ProgressService(db).set_weekly_goal(project_id, body.week_start, body.goal, user)
    return ok({"id": row.id, "week_start": row.week_start}, message="已保存")


# ---------- 周目标条目（M7） ----------
@router.get("/projects/{project_id}/weekly-goal/items")
def list_weekly_goal_items(project_id: int, week_start: date = Query(...), user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(ProgressService(db).list_weekly_goal_items(project_id, week_start))


@router.post("/projects/{project_id}/weekly-goal/items")
def add_weekly_goal_item(project_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    goal = (body.get("goal") or "").strip()
    if not goal:
        from app.core.responses import BizException
        raise BizException("目标内容不能为空")
    item = ProgressService(db).add_weekly_goal_item(
        project_id, body.get("week_start") or date.today(), goal, body.get("deadline"),
        body.get("user_id"), user)
    return ok({"id": item.id}, message="已添加")


@router.patch("/weekly-goal-items/{item_id}")
def update_weekly_goal_item(item_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    item = ProgressService(db).update_weekly_goal_item(
        item_id, body.get("goal"), body.get("deadline"), body.get("user_id"), user)
    return ok({"id": item.id}, message="已更新")


@router.patch("/weekly-goal-items/{item_id}/done")
def set_weekly_goal_item_done(item_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    item = ProgressService(db).set_weekly_goal_item_done(item_id, bool(body.get("done")), user)
    return ok({"id": item.id, "done": item.done, "done_at": item.done_at}, message="已更新")


@router.delete("/weekly-goal-items/{item_id}")
def delete_weekly_goal_item(item_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    ProgressService(db).delete_weekly_goal_item(item_id, user)
    return ok(message="已删除")


# ---------- 周报 ----------
@router.get("/reports/projects/{project_id}/weekly")
def project_weekly(project_id: int, week_start: date = Query(...), user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(ReportService(db).project_weekly(project_id, week_start))


@router.get("/reports/group/weekly")
def group_weekly(view: str = Query("project"), week_start: date = Query(...), user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = ReportService(db)
    if view == "person":
        return ok(svc.group_weekly_by_person(week_start))
    return ok(svc.group_weekly_by_project(week_start))


@router.get("/reports/group/ledger/export")
def export_ledger(week_start: date = Query(...), type: str = Query("weekly"),
                  columns: str = Query(None),
                  user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """导出台账：type=weekly 本周台账 / type=project 项目台账(每周任务合集) / type=completion 项目完成台账。
    columns：逗号分隔的启用列 key（仅 weekly 生效，空=全部列），与周会视图列设置一致。"""
    from urllib.parse import quote
    svc = ReportService(db)
    cols = [c.strip() for c in columns.split(",") if c.strip()] if columns else None
    if type == "completion":
        filename = "项目完成台账.xlsx"
        output = svc.export_completion_xlsx()
    elif type == "project":
        filename = "项目台账.xlsx"
        output = svc.export_ledger_xlsx(week_start, scope="all")
    else:
        filename = f"本周台账_{week_start.isocalendar().year}年第{week_start.isocalendar().week:02d}周.xlsx"
        output = svc.export_ledger_xlsx(week_start, scope="weekly", columns=cols)
    record_audit(db, user["user_id"], "export", "project_ledger", None, {"week_start": str(week_start), "type": type})
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# ---------- 看板 ----------
@router.get("/board")
def board(granularity: str = "month", year: int | None = None, month: int | None = None,
          machine_model: str | None = None, owner_id: int | None = None,
          user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(BoardService(db).board(granularity, year, month, machine_model, owner_id))


@router.get("/board/summary")
def board_summary(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """可视化看板统计：状态分布 / 风险 / 待关注项目 / 我的待办。"""
    return ok(BoardService(db).summary(user))


# ---------- 节点流转 ----------
@router.post("/nodes/{node_id}/transition")
def node_transition(node_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    target = body.get("target")
    n = NodeFlowService(db).transition(node_id, target, user)
    record_audit(db, user["user_id"], "update", "node", str(node_id), {"status": target})
    return ok({"id": n.id, "status": n.status}, message="已流转")


@router.post("/nodes/{node_id}/advance")
def node_advance(node_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    n = NodeFlowService(db).advance_to_next(node_id, user)
    return ok({"id": n.id, "status": n.status}, message="已进入下一节点")


@router.post("/nodes/{node_id}/force-transition")
def node_force_transition(node_id: int, body: dict, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    target = body.get("target")
    n = NodeFlowService(db).force_transition(node_id, target, user)
    record_audit(db, user["user_id"], "force_transition", "node", str(node_id), {"status": target})
    return ok({"id": n.id, "status": n.status}, message="已强制流转")


@router.post("/nodes/{node_id}/reviews")
def add_review(node_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    r = NodeFlowService(db).add_review(
        node_id, body.get("conclusion"), body.get("comment"),
        body.get("review_date") or date.today(), user)
    record_audit(db, user["user_id"], "review", "node", str(node_id), {"conclusion": r.conclusion})
    return ok({"id": r.id}, message="评审已记录")


@router.get("/nodes/{node_id}/reviews")
def list_reviews(node_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = NodeFlowService(db).list_reviews(node_id)
    return ok([{"id": r.id, "conclusion": r.conclusion, "comment": r.comment,
                "review_date": r.review_date, "reviewer_id": r.reviewer_id} for r in rows])


# ---------- M4：完成度 + 直接完成节点 ----------
@router.post("/nodes/{node_id}/complete")
def complete_node(node_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    n = NodeFlowService(db).complete_node(node_id, user)
    record_audit(db, user["user_id"], "update", "node", str(node_id), {"status": "passed"})
    return ok({"id": n.id, "status": n.status, "actual_end": n.actual_end}, message="节点已完成")


@router.get("/nodes/{node_id}/completion")
def node_completion(node_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(NodeFlowService(db).node_completion(node_id))


@router.get("/projects/{project_id}/completion")
def project_completion(project_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(NodeFlowService(db).project_completion(project_id))


# ---------- 通知 ----------
@router.get("/notifications")
def list_notifications(is_read: bool | None = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.misc import Notification
    from sqlalchemy import select
    q = select(Notification).where(Notification.user_id == user["user_id"])
    if is_read is not None:
        q = q.where(Notification.is_read == is_read)
    q = q.order_by(Notification.id.desc()).limit(100)
    rows = db.execute(q).scalars().all()
    return ok([{"id": n.id, "type": n.type, "title": n.title, "content": n.content,
                "link": n.link, "is_read": n.is_read, "created_at": n.created_at} for n in rows])


@router.patch("/notifications/{nid}/read")
def mark_read(nid: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.misc import Notification
    n = db.get(Notification, nid)
    if n and n.user_id == user["user_id"]:
        n.is_read = True
        db.commit()
    return ok(message="已读")


@router.post("/notifications/read-all")
def mark_all_read(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.misc import Notification
    db.query(Notification).filter(Notification.user_id == user["user_id"], Notification.is_read.is_(False)).update({"is_read": True})
    db.commit()
    return ok(message="全部已读")
