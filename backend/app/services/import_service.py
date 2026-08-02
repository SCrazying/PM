"""Excel 台账导入服务：preview（解析+映射）/ confirm（入库+幂等）。
依据 doc/Excel导入映射.md。默认迁"项目/节点/任务骨架 + 当前周目标"。"""
import re
from datetime import date
from typing import Optional

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectMember, ProjectNode, Task, TrTemplate, TrTemplateNode
from app.models.user import User
from app.services.progress_service import ProgressService

# 节点关键词映射（可配置化）
NODE_KEYWORDS = {
    "TR1": ["tr1", "概念", "需求"],
    "TR2": ["tr2", "方案", "计划"],
    "TR3": ["tr3", "设计", "开发前"],
    "TR4": ["tr4", "开发", "编码", "测试"],
    "TR5": ["tr5", "发布", "验证"],
    "TR6": ["tr6", "收尾", "量产"],
}
OWNER_KEYWORDS = ["负责人", "pm", "owner", "项目经理"]


def _match_node_key(text: str) -> Optional[str]:
    if not text:
        return None
    t = str(text).strip().lower()
    for key, kws in NODE_KEYWORDS.items():
        if any(k in t for k in kws):
            return key
    return None


def _split_tasks(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"[\n；;、]|(?:\d+[.、\)])", str(text))
    return [p.strip() for p in parts if p and p.strip()]


class ImportService:
    def __init__(self, db: Session):
        self.db = db
        self.ps = ProgressService(db)

    # ---------- preview ----------
    def preview(self, file_bytes: bytes) -> dict:
        wb = load_workbook(filename=__import__("io").BytesIO(file_bytes), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return {"projects": [], "warnings": ["空表格"], "errors": []}
        header = [str(c).strip() if c else "" for c in rows[0]]
        col = {name: idx for idx, name in enumerate(header)}

        def gv(row, *names):
            for n in names:
                if n in col and col[n] < len(row) and row[col[n]] is not None:
                    return str(row[col[n]]).strip()
            return ""

        users_by_name = {u.display_name: u for u in self.db.execute(select(User)).scalars().all()}

        projects = {}
        warnings, errors = [], []
        for r in rows[1:]:
            if not any(r):
                continue
            machine = gv(r, "机型")
            pname = gv(r, "项目", "项目名称")
            if not pname:
                warnings.append("存在项目名为空的行，已跳过")
                continue
            key = f"{machine}|{pname}"
            person = gv(r, "项目角色", "成员", "姓名", "人员")
            invested = gv(r, "是否投入该项目", "是否投入")
            role = gv(r, "项目角色")
            node_text = gv(r, "关键节点", "节点", "当前节点")
            week_goal = gv(r, "项目周目标", "周目标")
            week_task = gv(r, "本周任务", "本周工作")

            p = projects.setdefault(key, {
                "name": pname, "machine_model": machine, "code": "",
                "members": [], "node_text": node_text, "weekly_goal": week_goal,
                "tasks": [], "warnings": [],
            })
            if week_goal and not p["weekly_goal"]:
                p["weekly_goal"] = week_goal
            if person:
                u = users_by_name.get(person)
                is_owner = any(k in (role or "").lower() for k in OWNER_KEYWORDS)
                p["members"].append({
                    "name": person, "user_id": u.id if u else None, "matched": bool(u),
                    "project_role": role or ("负责人" if is_owner else "成员"),
                    "is_owner": is_owner,
                    "is_invested": invested not in ("否", "N", "n", "0", ""),
                })
            for t in _split_tasks(week_task):
                if t not in p["tasks"]:
                    p["tasks"].append(t)

        out = []
        for p in projects.values():
            node_key = _match_node_key(p["node_text"])
            owners = [m for m in p["members"] if m["is_owner"]]
            unmatched = [m["name"] for m in p["members"] if not m["matched"]]
            warns = []
            if not node_key:
                warns.append(f"关键节点「{p['node_text']}」无法识别，需人工指定")
            if len(owners) > 1:
                warns.append("识别到多个负责人，请确认")
            if unmatched:
                warns.append(f"成员未匹配到用户：{','.join(unmatched)}")
            out.append({**p, "current_node_key": node_key, "warnings": warns})
        return {"projects": out, "warnings": warnings, "errors": errors,
                "week_start": self.ps.week_start_of(date.today())}

    # ---------- confirm ----------
    def confirm(self, projects: list[dict], operator_id: int) -> dict:
        # 默认模板节点
        tpl = self.db.execute(select(TrTemplate).where(TrTemplate.status == "active").order_by(TrTemplate.id)).scalars().first()
        tpl_nodes = {n.node_key: n for n in self.db.execute(
            select(TrTemplateNode).where(TrTemplateNode.template_id == tpl.id).order_by(TrTemplateNode.sequence)).scalars().all()} if tpl else {}

        created, updated, failed = 0, 0, []
        for p in projects:
            try:
                self._import_one(p, tpl_nodes, operator_id)
                created += 1
            except Exception as e:  # noqa: BLE001
                failed.append({"project": p.get("name"), "error": str(e)[:200]})
        return {"created": created, "failed": failed}

    def _import_one(self, p: dict, tpl_nodes: dict, operator_id: int) -> None:
        # 找负责人
        owner = next((m for m in p["members"] if m.get("is_owner") and m.get("user_id")), None)
        if not owner:
            owner = next((m for m in p["members"] if m.get("user_id")), None)
        owner_id = owner["user_id"] if owner else operator_id

        # 项目（存在则更新）
        code = p.get("code") or f"P{date.today().year}{abs(hash(p['name'])) % 10000:04d}"
        proj = self.db.execute(select(Project).where(Project.code == code, Project.is_deleted.is_(False))).scalar_one_or_none()
        if not proj:
            proj = Project(name=p["name"], code=code, machine_model=p.get("machine_model"),
                           owner_id=owner_id, status="in_progress", created_by=operator_id)
            self.db.add(proj)
            self.db.flush()
        else:
            proj.name = p["name"]
            proj.machine_model = p.get("machine_model")

        # 成员
        for m in p["members"]:
            if not m.get("user_id"):
                continue
            mem = self.db.execute(select(ProjectMember).where(
                ProjectMember.project_id == proj.id, ProjectMember.user_id == m["user_id"])).scalar_one_or_none()
            role = "负责人" if (m.get("is_owner") or m["user_id"] == owner_id) else (m.get("project_role") or "成员")
            if mem:
                mem.is_deleted = False
                mem.project_role = role
                mem.is_invested = m.get("is_invested", True)
            else:
                self.db.add(ProjectMember(project_id=proj.id, user_id=m["user_id"], project_role=role,
                                          is_invested=m.get("is_invested", True), joined_at=date.today()))
        proj.owner_id = owner_id

        # 节点：按模板全量实例化，当前节点置为匹配到的
        current_key = p.get("current_node_key")
        if tpl_nodes and not self.db.execute(select(ProjectNode).where(ProjectNode.project_id == proj.id)).scalars().first():
            seqs = sorted(tpl_nodes.values(), key=lambda n: n.sequence)
            current_id = None
            reached = False
            for tn in seqs:
                is_current = (tn.node_key == current_key)
                status = "in_progress" if is_current else ("passed" if (current_key and not reached and tn.node_key != current_key and list(seqs).index(tn) < [x.node_key for x in seqs].index(current_key)) else "not_started")
                node = ProjectNode(project_id=proj.id, template_node_id=tn.id, node_key=tn.node_key,
                                   name=tn.name, sequence=tn.sequence, status=status)
                self.db.add(node)
                self.db.flush()
                if is_current:
                    current_id = node.id
                    reached = True
            proj.current_node_id = current_id or (seqs[0] and self.db.execute(
                select(ProjectNode).where(ProjectNode.project_id == proj.id).order_by(ProjectNode.sequence)).scalars().first().id)

        # 周目标（当周）
        if p.get("weekly_goal"):
            self.ps.set_weekly_goal(proj.id, date.today(), p["weekly_goal"], {"user_id": operator_id, "role": "admin"})

        # 任务（挂当前节点）
        if proj.current_node_id:
            for title in p.get("tasks", []):
                self.db.add(Task(project_node_id=proj.current_node_id, project_id=proj.id,
                                 title=title, status="in_progress", created_by=operator_id))
        self.db.commit()
