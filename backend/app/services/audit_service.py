"""审计服务：记录关键操作（变更字段 diff）。"""
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.misc import AuditLog


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
