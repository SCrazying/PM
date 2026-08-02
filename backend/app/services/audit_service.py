"""审计服务：记录关键操作（变更字段 diff）。"""
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.misc import AuditLog


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
        detail=detail,
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
