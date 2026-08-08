"""M3 路由：个人汇总/AI 总结、附件、配置、TR 模板管理、备份、导出。"""
import os
import subprocess
from datetime import date

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_self_or_admin
from app.core.responses import BizException, NotFoundError, ok, page_result
from app.engines.ai_engine import AiService
from app.models.misc import Attachment, Config
from app.models.project import TrTemplate, TrTemplateNode
from app.schemas.project import RecycleBatchIn
from app.services.audit_service import record_audit
from app.services.personal_service import PersonalService
from app.services.project_service import ProjectService

router = APIRouter()


# ---------- 个人汇总 / AI 总结 ----------
@router.get("/personal/{user_id}/summary")
def personal_summary(user_id: int, period: str = Query("month"), date_: date = Query(None, alias="date"),
                     user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_self_or_admin(user_id, user)
    ref = date_ or date.today()
    return ok(PersonalService(db).summary(user_id, period, ref))


@router.get("/personal/{user_id}/ai-summary")
def get_ai_summary(user_id: int, period: str = Query("month"), date_: date = Query(None, alias="date"),
                   user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_self_or_admin(user_id, user)
    ref = date_ or date.today()
    row = AiService(db).get(user_id, period, ref)
    if not row:
        return ok(None)
    return ok({"id": row.id, "content": row.edited_content or row.content, "raw_content": row.content,
               "status": row.status, "model": row.model, "error": row.error,
               "source_snapshot": row.source_snapshot,
               "period_start": row.period_start, "period_end": row.period_end})


@router.post("/personal/{user_id}/ai-summary")
def gen_ai_summary(user_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_self_or_admin(user_id, user)
    period = body.get("period", "month")
    ref = date.fromisoformat(body["date"]) if body.get("date") else date.today()
    row = AiService(db).generate(user_id, period, ref, user["user_id"])
    return ok({"id": row.id, "status": row.status, "model": row.model}, message="已生成")


@router.put("/ai-summaries/{sid}")
def edit_ai_summary(sid: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    row = AiService(db).edit(sid, body.get("edited_content", ""), user)
    return ok({"id": row.id, "status": row.status}, message="已保存")


# ---------- 附件 ----------
ALLOWED_EXT = set((os.environ.get("ATTACH_EXT") or
                   "pdf,doc,docx,xls,xlsx,ppt,pptx,txt,md,png,jpg,jpeg,zip").split(","))


@router.post("/attachments")
async def upload_attachment(project_id: int = Form(...), project_node_id: int = Form(None),
                            task_id: int = Form(None), review_id: int = Form(None),
                            file: UploadFile = File(...),
                            user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if not (project_node_id or task_id or review_id):
        raise BizException("附件须关联节点/任务/评审之一")
    ext = (file.filename.rsplit(".", 1)[-1] or "").lower()
    if ext not in ALLOWED_EXT:
        raise BizException(f"不支持的文件类型 .{ext}")
    content = await file.read()
    if len(content) > settings.ATTACHMENT_MAX_MB * 1024 * 1024:
        raise BizException(f"文件超过 {settings.ATTACHMENT_MAX_MB}MB")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    import uuid
    fname = f"{uuid.uuid4().hex}_{file.filename}"
    fpath = os.path.join(settings.UPLOAD_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(content)

    att = Attachment(project_id=project_id, project_node_id=project_node_id, task_id=task_id,
                     review_id=review_id, file_name=file.filename, file_path=fpath,
                     file_size=len(content), mime_type=file.content_type, uploaded_by=user["user_id"])
    db.add(att)
    db.commit()
    db.refresh(att)
    return ok({"id": att.id, "file_name": att.file_name}, message="上传成功")


@router.get("/attachments/{aid}/download")
def download_attachment(aid: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    att = db.get(Attachment, aid)
    if not att or att.is_deleted or not os.path.exists(att.file_path):
        raise NotFoundError("附件不存在")
    record_audit(db, user["user_id"], "export", "attachment", str(aid), {"file": att.file_name})
    return FileResponse(att.file_path, filename=att.file_name)


# ---------- 配置 ----------
SENSITIVE_KEYS = {"ai.api_key_ref"}


@router.get("/config")
def list_config(user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(Config)).scalars().all()
    out = []
    for c in rows:
        val = c.value
        if c.key in SENSITIVE_KEYS or "key" in c.key.lower():
            val = "***" if c.value else ""
        out.append({"key": c.key, "value": val, "description": c.description})
    return ok(out)


@router.put("/config/{key}")
def set_config(key: str, body: dict, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(Config, key)
    if not row:
        row = Config(key=key)
        db.add(row)
    row.value = body.get("value")
    db.commit()
    record_audit(db, user["user_id"], "config_change", "config", key)
    return ok(message="已保存")


# ---------- 机型管理（管理端维护，供新建/编辑项目下拉）----------
@router.get("/machine-models")
def list_machine_models(user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    from app.models.misc import MachineModel
    managed = db.execute(
        select(MachineModel).where(MachineModel.is_deleted.is_(False)).order_by(MachineModel.name)
    ).scalars().all()
    used = ProjectService(db).list_machine_options()
    registered = {m.name for m in managed}
    rows = [{"id": m.id, "name": m.name, "source": "registered"} for m in managed]
    rows += [{"id": None, "name": u, "source": "used"} for u in used if u not in registered]
    return ok(rows)


@router.post("/machine-models")
def create_machine_model(body: dict, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    from app.models.misc import MachineModel
    name = (body.get("name") or "").strip()
    if not name:
        raise BizException("机型名称不能为空", code=400, http_status=400)
    old = db.execute(select(MachineModel).where(MachineModel.name == name)).scalar_one_or_none()
    if old and not old.is_deleted:
        raise BizException("机型已存在", code=409, http_status=409)
    if old:
        old.is_deleted = False
        old.deleted_at = None
        m = old
    else:
        m = MachineModel(name=name)
        db.add(m)
    db.commit()
    db.refresh(m)
    record_audit(db, user["user_id"], "create", "machine_model", str(m.id), {"name": name})
    return ok({"id": m.id, "name": m.name}, message="已添加")


@router.delete("/machine-models/{mid}")
def delete_machine_model(mid: int, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    from app.models.misc import MachineModel
    m = db.get(MachineModel, mid)
    if not m or m.is_deleted:
        raise NotFoundError("机型不存在")
    m.is_deleted = True
    m.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(db, user["user_id"], "delete", "machine_model", str(mid), {"name": m.name})
    return ok(message="已删除")


# ---------- TR 模板管理 ----------
@router.post("/tr-templates")
def create_template(body: dict, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    from app.models.project import TrTemplateSubnode
    tpl = TrTemplate(name=body["name"], description=body.get("description"), is_builtin=False)
    db.add(tpl)
    db.flush()
    for i, n in enumerate(body.get("nodes", []), start=1):
        node = TrTemplateNode(template_id=tpl.id, node_key=n["node_key"], name=n["name"],
                              sequence=n.get("sequence", i), review_focus=n.get("review_focus"))
        db.add(node)
        db.flush()
        for j, sn in enumerate(n.get("subnodes", []), start=1):
            sn_name = (sn.get("name") if isinstance(sn, dict) else sn) or ""
            if sn_name.strip():
                db.add(TrTemplateSubnode(template_node_id=node.id, name=str(sn_name).strip(), sequence=j))
    db.commit()
    return ok({"id": tpl.id}, message="模板已创建")


@router.put("/tr-templates/{tid}")
def update_template(tid: int, body: dict, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    tpl = db.get(TrTemplate, tid)
    if not tpl:
        raise NotFoundError("模板不存在")
    if tpl.is_builtin and body.get("name") and body["name"] != tpl.name:
        raise BizException("内置模板不可改名")
    if body.get("status"):
        tpl.status = body["status"]
    if body.get("description") is not None:
        tpl.description = body["description"]
    db.commit()
    return ok(message="已更新")


# ---------- Excel 导入 ----------
@router.post("/import/excel/preview")
async def import_preview(file: UploadFile = File(...), user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.import_service import ImportService
    content = await file.read()
    result = ImportService(db).preview(content)
    return ok(result)


@router.post("/import/excel/confirm")
def import_confirm(body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.import_service import ImportService
    result = ImportService(db).confirm(body.get("projects", []), user["user_id"])
    record_audit(db, user["user_id"], "import", "project", None, {"created": result["created"], "failed": len(result["failed"])})
    return ok(result, message=f"导入完成：成功 {result['created']} 个")


# ---------- 备份 ----------
@router.post("/backup")
def trigger_backup(user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    os.makedirs(settings.BACKUP_DIR, exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = os.path.join(settings.BACKUP_DIR, f"db_{ts}.sql")
    url = settings.DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")
    try:
        subprocess.run(["pg_dump", url, "-f", outfile], check=True, capture_output=True, timeout=120)
    except FileNotFoundError:
        raise BizException("服务器未安装 pg_dump，无法在线备份")
    except subprocess.CalledProcessError as e:
        raise BizException(f"备份失败：{e.stderr.decode(errors='ignore')[:200]}")
    record_audit(db, user["user_id"], "backup", "system", ts)
    return ok({"file": os.path.basename(outfile)}, message="备份完成")


@router.get("/backups")
def list_backups(user: dict = Depends(require_admin)):
    if not os.path.isdir(settings.BACKUP_DIR):
        return ok([])
    files = sorted([f for f in os.listdir(settings.BACKUP_DIR) if f.startswith("db_")], reverse=True)
    return ok([{"file": f, "size": os.path.getsize(os.path.join(settings.BACKUP_DIR, f))} for f in files])


# ---------- 回收站（假删除项目：恢复 / 彻底删除）----------
@router.get("/admin/recycle-bin")
def recycle_bin(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    items, total = ProjectService(db).list_deleted_projects(page, size)
    return page_result(items, total, page, size)


@router.post("/admin/recycle-bin/restore")
def recycle_restore(body: RecycleBatchIn, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    n = ProjectService(db).restore_projects(body.project_ids)
    record_audit(db, user["user_id"], "restore", "project", ",".join(map(str, body.project_ids)), {"count": n})
    return ok(message=f"已恢复 {n} 个项目")


@router.post("/admin/recycle-bin/purge")
def recycle_purge(body: RecycleBatchIn, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    n = ProjectService(db).purge_projects(body.project_ids)
    record_audit(db, user["user_id"], "purge", "project", ",".join(map(str, body.project_ids)), {"count": n})
    return ok(message=f"已彻底删除 {n} 个项目")
