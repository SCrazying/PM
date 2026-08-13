"""审计服务：记录关键操作（变更字段 diff）。"""
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, cast, func, or_, select, String
from sqlalchemy.orm import Session

from app.models.misc import AuditLog
from app.models.project import ProjectNode, Task
from app.models.user import User


def _jsonable(value: Any) -> Any:
    """把 date/datetime 等转成可 JSON 序列化的值，避免 JSONB 写入失败。"""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return value


def record_audit(
    db: Session,
    actor_id: Optional[int],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[dict] = None,
    ip: Optional[str] = None,
    commit: bool = True,
) -> AuditLog:
    log = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=_jsonable(detail),
        ip=ip,
    )
    db.add(log)
    if commit:
        db.commit()
    else:
        db.flush()
    return log


def diff_dict(before: dict, after: dict, fields: list[str]) -> dict:
    """计算指定字段的前后变化（仅变化字段）。"""
    changes = {}
    for f in fields:
        b, a = before.get(f), after.get(f)
        if b != a:
            changes[f] = {"before": b, "after": a}
    return changes


def model_to_dict(obj: Any, fields: list[str]) -> dict:
    return {f: getattr(obj, f, None) for f in fields}


def cleanup_expired(db: Session, days: Optional[int] = None) -> int:
    """清理过期审计日志（默认按 config audit.retention_months，按月*30天）。返回删除条数。
    分批删除（每批 5000），避免单条大 DELETE 长锁表/膨胀。"""
    if days is None:
        from app.models.misc import Config
        row = db.get(Config, "audit.retention_months")
        months = int(row.value) if row and row.value and str(row.value).isdigit() else 24
        days = months * 30
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    total = 0
    while True:
        batch = db.query(AuditLog.id).filter(AuditLog.created_at < cutoff).limit(5000).all()
        if not batch:
            break
        ids = [b[0] for b in batch]
        db.query(AuditLog).filter(AuditLog.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        total += len(ids)
    return total


# ---------- 项目操作流水线（V1.0.5，复用 audit_log，项目视角聚合） ----------

# target_id 即 project_id 的操作类型（直系）
# 注意：weekly_goal 仅指 set_weekly_goal（target_id=project_id）；
# 周目标条目类（增/改/完成/删）单独用 target_type="weekly_goal_item"，靠 detail.project_id 归属，
# 避免 target_id=item_id 与项目 id 撞号导致跨项目误归属（见 query_project_activity）。
_PROJECT_DIRECT_TYPES = ("project", "member", "project_risk", "weekly_goal")

ACTION_LABELS = {
    "create": "新增", "update": "修改", "delete": "删除", "review": "评审",
    "restore": "恢复", "purge": "彻底删除", "force_transition": "强制流转",
    "transition": "流转", "export": "导出", "import": "导入", "config_change": "配置变更",
    "account_locked": "账号锁定", "login_failed": "登录失败", "backup": "备份",
    "reset_password": "重置密码", "login": "登录", "logout": "登出",
}
TARGET_LABELS = {
    "project": "项目", "node": "节点", "task": "任务", "member": "成员",
    "project_risk": "项目风险", "weekly_goal": "周目标", "weekly_goal_item": "周目标条目",
    "attachment": "附件", "progress": "进展", "subnode": "子节点",
}

# detail 字段 → 中文（summary 渲染用）
_FIELD_LABELS = {
    "name": "名称", "code": "编号", "status": "状态", "machine_model": "机型",
    "owner_id": "负责人", "description": "描述", "start_date": "开始日期", "end_date": "结束日期",
    "planned_start": "计划开始时间", "planned_end": "计划完成时间", "actual_end": "实际完成时间",
    "goal": "目标", "deadline": "截止时间", "done": "完成状态", "risk": "风险",
    "is_invested": "投入状态", "project_role": "角色", "title": "任务", "conclusion": "评审结论",
    "node_deadlines": "节点计划完成时间",
}
_SUMMARY_VERBS = {"create": "添加了", "update": "更新了", "delete": "删除了", "review": "评审了",
                  "restore": "恢复了", "purge": "彻底删除了", "force_transition": "强制流转了",
                  "transition": "流转了", "export": "导出了", "config_change": "变更了"}


def render_activity_summary(log: AuditLog) -> str:
    """把一条审计记录渲染成一句中文摘要（项目流水线展示用）。"""
    verb = _SUMMARY_VERBS.get(log.action, "操作了")
    target = TARGET_LABELS.get(log.target_type, log.target_type or "")
    detail = log.detail or {}
    parts = []
    for key, val in detail.items():
        # 归属/上下文字段不展示
        if key in ("project_id", "user_id", "action"):
            continue
        label = _FIELD_LABELS.get(key, key)
        if isinstance(val, dict) and "before" in val and "after" in val:
            b, a = val["before"], val["after"]
            if b == a or (b is None and a is None):
                continue
            parts.append(f"{label}：{b or '未设置'} → {a or '未设置'}")
        elif isinstance(val, list) and key == "node_deadlines":
            parts.append(f"{label}：共 {len(val)} 个节点")
        elif val is None or val == "":
            continue
        else:
            parts.append(f"{label}：{val}")
    body = "；".join(parts) if parts else ""
    return f"{verb}{target}" + (f"（{body}）" if body else "")


def query_project_activity(db: Session, project_id: int, page: int = 1, size: int = 20,
                           action: Optional[str] = None, date_from: Optional[date] = None,
                           date_to: Optional[date] = None) -> tuple[list, int]:
    """项目操作流水线：聚合该项目相关的审计记录（项目直系 + 节点/任务/附件/进展/周目标条目归属）。

    权限由路由层校验（成员/负责人/admin）。"""
    from app.models.misc import Attachment, Progress
    pid = str(project_id)
    node_ids = select(cast(ProjectNode.id, String)).where(ProjectNode.project_id == project_id)
    task_ids = select(cast(Task.id, String)).where(Task.project_id == project_id)
    att_ids = select(cast(Attachment.id, String)).where(Attachment.project_id == project_id)
    prog_ids = select(cast(Progress.id, String)).where(Progress.project_id == project_id)

    cond = or_(
        and_(AuditLog.target_type.in_(_PROJECT_DIRECT_TYPES), AuditLog.target_id == pid),
        # 周目标条目 target_id=item_id（可能与其他项目 id 撞号），改用 detail.project_id JSONB 归属
        and_(AuditLog.target_type == "weekly_goal_item", AuditLog.detail["project_id"].as_string() == pid),
        and_(AuditLog.target_type == "node", AuditLog.target_id.in_(node_ids)),
        and_(AuditLog.target_type == "task", AuditLog.target_id.in_(task_ids)),
        and_(AuditLog.target_type == "attachment", AuditLog.target_id.in_(att_ids)),
        and_(AuditLog.target_type == "progress", AuditLog.target_id.in_(prog_ids)),
    )
    q = select(AuditLog, User.display_name).join(User, User.id == AuditLog.actor_id, isouter=True).where(cond)
    if action:
        q = q.where(AuditLog.action == action)
    if date_from:
        q = q.where(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        q = q.where(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), time.min))

    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = db.execute(q.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size)).all()
    items = [{
        "id": log.id, "time": log.created_at.isoformat() if log.created_at else None,
        "actor_id": log.actor_id, "actor_name": uname,
        "action": log.action, "action_label": ACTION_LABELS.get(log.action, log.action),
        "target_type": log.target_type, "target_label": TARGET_LABELS.get(log.target_type, log.target_type),
        "detail": log.detail, "summary": render_activity_summary(log),
    } for log, uname in rows]
    return items, total
