"""项目服务：项目 CRUD、成员、TR 节点实例化、任务。含软删级联与 owner 强制入成员表。"""
from datetime import date
import re
from typing import List, Optional

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.responses import BizException, ForbiddenError, NotFoundError
from app.core.project_roles import (
    PROJECT_ROLE_NAMES,
    SINGLE_PROJECT_ROLES,
    canonical_project_role,
    empty_role_assignments,
)
from app.models.misc import (
    Attachment,
    Notification,
    Progress,
    ProgressTaskLink,
    ProjectWeeklyGoal,
    WeeklyGoalItem,
)
from app.models.project import (
    ACTIVE_PROJECT_STATUSES,
    PROJECT_STATUSES,
    NodeReview,
    Project,
    ProjectMember,
    ProjectNode,
    ProjectRoleAssignment,
    Task,
    TrTemplateNode,
)
from app.models.user import User
from app.schemas.project import MemberIn, ProjectCreate, ProjectUpdate, TaskCreate, TaskUpdate


class ProjectService:
    # 项目列表可排序字段白名单
    _SORTABLE_FIELDS = frozenset({"id", "name", "code", "machine_model", "status", "created_at", "updated_at"})

    def __init__(self, db: Session):
        self.db = db

    # ---------- 权限辅助 ----------
    def get_project(self, project_id: int, include_deleted: bool = False) -> Project:
        q = select(Project).where(Project.id == project_id)
        if not include_deleted:
            q = q.where(Project.is_deleted.is_(False))
        p = self.db.execute(q).scalar_one_or_none()
        if not p:
            raise NotFoundError("项目不存在")
        # 数据兜底修复：current_node_id 误指向子节点时，按顶层节点规则纠正（历史脏数据）
        if p.current_node_id:
            cur = self.db.get(ProjectNode, p.current_node_id)
            if cur and cur.parent_id is not None:
                self._refresh_current_node(p)
                self.db.commit()
        return p

    def check_owner(self, project: Project, user: dict) -> None:
        if user["role"] != "admin" and project.owner_id != user["user_id"]:
            raise ForbiddenError("仅项目负责人或管理员可操作")

    def check_member(self, project: Project, user: dict) -> None:
        if user["role"] == "admin" or project.owner_id == user["user_id"]:
            return
        m = self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == user["user_id"],
                ProjectMember.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if not m:
            raise ForbiddenError("仅项目成员可操作")

    # ---------- 项目 ----------
    def list_projects(self, status=None, owner_id=None, machine_model=None, keyword=None, page=1, size=20,
                      sort_field="id", sort_order="desc"):
        q = select(Project).where(Project.is_deleted.is_(False))
        if status:
            q = q.where(Project.status == status)
        if owner_id:
            q = q.where(Project.owner_id == owner_id)
        if machine_model:
            q = q.where(Project.machine_model == machine_model)
        if keyword:
            q = q.where(Project.name.contains(keyword) | Project.code.contains(keyword))
        total = self.db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
        # 排序字段白名单，防注入
        if sort_field not in self._SORTABLE_FIELDS:
            sort_field = "id"
        col = getattr(Project, sort_field)
        q = q.order_by(col.asc() if sort_order == "asc" else col.desc())
        q = q.offset((page - 1) * size).limit(size)
        return list(self.db.execute(q).scalars().all()), total

    def list_machine_options(self) -> list[str]:
        """返回全部机型：管理端登记的机型 ∪ 项目表中现存机型（避免历史数据丢失）。"""
        from app.models.misc import MachineModel
        managed = self.db.execute(
            select(MachineModel.name).where(MachineModel.is_deleted.is_(False)).order_by(MachineModel.name)
        ).scalars().all()
        used = self.db.execute(
            select(Project.machine_model)
            .where(
                Project.is_deleted.is_(False),
                Project.machine_model.isnot(None),
                Project.machine_model != "",
            )
            .distinct()
            .order_by(Project.machine_model)
        ).scalars().all()
        seen = set(managed)
        return list(managed) + [u for u in used if u not in seen]

    def create_project(self, body: ProjectCreate, operator_id: int) -> Project:
        # 项目名称唯一（软删兼容，DB 部分唯一索引 ux_project_name 兜底）
        name_exists = self.db.execute(
            select(Project).where(Project.name == body.name, Project.is_deleted.is_(False))
        ).scalar_one_or_none()
        if name_exists:
            raise BizException("项目名称已存在", code=409, http_status=409)

        code = (body.code or "").strip()
        # code 唯一（软删兼容由 DB 部分唯一索引兜底，这里先查；留空则插入后自动生成）
        if code:
            exists = self.db.execute(
                select(Project).where(Project.code == code, Project.is_deleted.is_(False))
            ).scalar_one_or_none()
            if exists:
                raise BizException("项目编号已存在", code=409, http_status=409)

        owner = self.db.get(User, body.owner_id)
        if not owner:
            raise NotFoundError("负责人用户不存在")

        status = body.status or "in_progress"
        if status not in PROJECT_STATUSES:
            raise BizException("项目状态不合法", code=400, http_status=400)

        project = Project(
            name=body.name, code=code, machine_model=body.machine_model,
            owner_id=body.owner_id, status=status,
            start_date=body.start_date, end_date=body.end_date,
            description=body.description, created_by=operator_id,
        )
        self.db.add(project)
        self.db.flush()
        if not project.code:
            project.code = f"P{project.id}"

        # 成员：负责人强制入成员表 + 其它成员
        self._upsert_member(project.id, body.owner_id, "负责人", True)
        seen = {body.owner_id}
        for m in body.members:
            if m.user_id in seen:
                continue
            seen.add(m.user_id)
            self._upsert_member(project.id, m.user_id, m.project_role, m.is_invested)

        self.replace_role_assignments(project.id, body.role_assignments)

        # TR 节点实例化
        node_ids = body.node_ids or self._default_template_node_ids()
        if body.node_ids:
            plans = {plan.template_node_id: plan for plan in body.node_plans}
            missing = [node_id for node_id in body.node_ids if node_id not in plans]
            if missing:
                raise BizException("请补齐所选节点的计划日期")
            invalid = [
                plan for plan in plans.values()
                if plan.template_node_id in body.node_ids
                and (not plan.planned_end or (plan.planned_start and plan.planned_end < plan.planned_start))
            ]
            if invalid:
                raise BizException("节点计划完成日期不能为空")
        self._instantiate_nodes(project, node_ids, body.node_plans)

        self.db.commit()
        self.db.refresh(project)
        return project

    def _default_template_node_ids(self) -> List[int]:
        """默认取第一个 active 模板的全部节点。"""
        from app.models.project import TrTemplate
        tpl = self.db.execute(select(TrTemplate).where(TrTemplate.status == "active").order_by(TrTemplate.id)).scalars().first()
        if not tpl:
            return []
        return [n.id for n in self.db.execute(
            select(TrTemplateNode).where(TrTemplateNode.template_id == tpl.id).order_by(TrTemplateNode.sequence)
        ).scalars().all()]

    def _instantiate_nodes(self, project: Project, template_node_ids: List[int], node_plans=None) -> None:
        if not template_node_ids:
            return
        from app.models.project import TrTemplateSubnode
        plan_map = {plan.template_node_id: plan for plan in (node_plans or [])}
        nodes = self.db.execute(
            select(TrTemplateNode).where(TrTemplateNode.id.in_(template_node_ids)).order_by(TrTemplateNode.sequence)
        ).scalars().all()
        # 模板节点默认子节点（批量取，避免 N+1）
        tpl_sub_map: dict[int, list[TrTemplateSubnode]] = {}
        if nodes:
            tpl_subs = self.db.execute(
                select(TrTemplateSubnode).where(TrTemplateSubnode.template_node_id.in_([n.id for n in nodes]))
                .order_by(TrTemplateSubnode.sequence)
            ).scalars().all()
            for s in tpl_subs:
                tpl_sub_map.setdefault(s.template_node_id, []).append(s)
        first_id = None
        for i, tn in enumerate(nodes):
            plan = plan_map.get(tn.id)
            node = ProjectNode(
                project_id=project.id, template_node_id=tn.id, node_key=tn.node_key,
                name=tn.name, sequence=i + 1, status="not_started",
                planned_start=plan.planned_start if plan else None,
                planned_end=plan.planned_end if plan else None,
            )
            self.db.add(node)
            self.db.flush()
            if first_id is None:
                first_id = node.id
            # 模板默认子节点 → 实例化为项目子节点（截止时间默认取节点计划完成）
            for j, ts in enumerate(tpl_sub_map.get(tn.id, []), start=1):
                self.db.add(ProjectNode(
                    project_id=project.id, parent_id=node.id, node_key="SUB",
                    name=ts.name, sequence=j, status="not_started",
                    planned_end=plan.planned_end if plan else None,
                ))
        project.current_node_id = first_id
        self.db.flush()

    def update_project(self, project_id: int, body: ProjectUpdate, user: dict) -> Project:
        project = self.get_project(project_id)
        self.check_owner(project, user)
        data = body.model_dump(exclude_none=True)
        role_assignments = data.pop("role_assignments", None)
        node_deadlines = data.pop("node_deadlines", None)
        node_enabled_ids = data.pop("node_enabled_ids", None)
        # 负责人变更：同步成员表
        if "owner_id" in data and data["owner_id"] != project.owner_id:
            new_owner = self.db.get(User, data["owner_id"])
            if not new_owner:
                raise NotFoundError("新负责人不存在")
            self._upsert_member(project.id, data["owner_id"], "负责人", True)
        # 项目名称变更：唯一性校验（软删兼容）
        if "name" in data:
            name_exists = self.db.execute(
                select(Project).where(
                    Project.name == data["name"], Project.is_deleted.is_(False), Project.id != project_id
                )
            ).scalar_one_or_none()
            if name_exists:
                raise BizException("项目名称已存在", code=409, http_status=409)
        # 项目编号变更：唯一性校验（软删兼容）；留空则自动生成
        if "code" in data:
            data["code"] = (data["code"] or "").strip()
            if not data["code"]:
                data["code"] = f"P{project.id}"
            elif data["code"] != project.code:
                exists = self.db.execute(
                    select(Project).where(
                        Project.code == data["code"], Project.is_deleted.is_(False), Project.id != project_id
                    )
                ).scalar_one_or_none()
                if exists:
                    raise BizException("项目编号已存在", code=409, http_status=409)
        # 项目状态手动配置：白名单校验
        if "status" in data:
            if data["status"] not in PROJECT_STATUSES:
                raise BizException("项目状态不合法", code=400, http_status=400)
        for f, v in data.items():
            setattr(project, f, v)
        if role_assignments is not None:
            self.replace_role_assignments(project.id, role_assignments)
        if node_enabled_ids is not None:
            self.apply_node_enabled(project, node_enabled_ids)
        if node_deadlines is not None:
            self.replace_node_deadlines(project.id, node_deadlines)
        self.db.commit()
        self.db.refresh(project)
        return project

    def apply_node_enabled(self, project: Project, enabled_ids: list[int]) -> None:
        """编辑项目时启用/停用节点：未列出的顶层节点停用，列出的启用/恢复；子节点跟随父节点。"""
        from datetime import datetime, timezone
        enabled_set = set(enabled_ids)
        nodes = list(self.db.execute(
            select(ProjectNode).where(ProjectNode.project_id == project.id)
        ).scalars().all())
        now = datetime.now(timezone.utc)
        top = {n.id: n for n in nodes if n.parent_id is None}
        for node in nodes:
            if node.parent_id is None:
                active = node.id in enabled_set
                node.is_deleted = not active
                node.deleted_at = None if active else now
            else:
                parent = top.get(node.parent_id)
                parent_active = parent is not None and not parent.is_deleted
                node.is_deleted = not parent_active
                node.deleted_at = None if parent_active else now
        self._refresh_current_node(project)
        self.db.flush()

    def replace_node_deadlines(self, project_id: int, deadlines: list[dict]) -> None:
        """只替换项目节点的计划完成日期，不改动旧的计划开始日期。"""
        nodes = {
            node.id: node for node in self.db.execute(
                select(ProjectNode).where(
                    ProjectNode.project_id == project_id,
                    ProjectNode.is_deleted.is_(False),
                )
            ).scalars().all()
        }
        seen = set()
        for item in deadlines or []:
            node_id = item["project_node_id"]
            if node_id in seen:
                raise BizException("节点截止日期不能重复提交")
            seen.add(node_id)
            node = nodes.get(node_id)
            if not node:
                raise BizException("节点不属于当前项目")
            node.planned_end = item.get("planned_end")
        self.db.flush()

    def delete_project(self, project_id: int, user: dict) -> None:
        project = self.get_project(project_id)
        self.check_owner(project, user)
        # 软删级联
        project.is_deleted = True
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        project.deleted_at = now
        for model, field in [
            (ProjectNode, ProjectNode.project_id),
            (Task, Task.project_id),
            (ProjectMember, ProjectMember.project_id),
        ]:
            for row in self.db.execute(select(model).where(field == project_id, model.is_deleted.is_(False))).scalars().all():
                row.is_deleted = True
                row.deleted_at = now
        self.db.commit()

    # ---------- 回收站（软删项目列表 / 恢复 / 彻底删除）----------
    def list_deleted_projects(self, page: int = 1, size: int = 20) -> tuple[list[dict], int]:
        """回收站列表：软删项目，按删除时间倒序，附带负责人姓名。"""
        q = select(Project).where(Project.is_deleted.is_(True))
        total = self.db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
        rows = self.db.execute(
            q.order_by(Project.deleted_at.desc(), Project.id.desc())
            .offset((page - 1) * size).limit(size)
        ).scalars().all()
        owner_ids = {r.owner_id for r in rows}
        names = dict(self.db.execute(
            select(User.id, User.display_name).where(User.id.in_(owner_ids or [0]))
        ).all())
        items = []
        for r in rows:
            d = {
                "id": r.id, "name": r.name, "code": r.code, "machine_model": r.machine_model,
                "owner_id": r.owner_id, "owner_name": names.get(r.owner_id),
                "status": r.status, "health": r.health,
                "start_date": r.start_date, "end_date": r.end_date,
                "created_at": r.created_at, "deleted_at": r.deleted_at,
            }
            items.append(d)
        return items, total

    def restore_projects(self, project_ids: list[int]) -> int:
        """回收站恢复：恢复项目及其软删级联的节点/任务/成员。

        数据库兼容：编号唯一由部分唯一索引 ux_project_code（WHERE NOT is_deleted）兜底，
        这里先整体查重，命中冲突则整体失败返回 409，避免抛 UniqueViolation 导致 500。
        """
        ids = list(dict.fromkeys(project_ids or []))
        if not ids:
            raise BizException("请选择要恢复的项目")
        projects = list(self.db.execute(select(Project).where(Project.id.in_(ids))).scalars().all())
        if len(projects) != len(ids):
            raise NotFoundError("部分项目不存在")
        for p in projects:
            if not p.is_deleted:
                raise BizException(f"项目「{p.name}」不在回收站中", code=409, http_status=409)
        conflicts = list(self.db.execute(
            select(Project).where(
                Project.code.in_({p.code for p in projects}),
                Project.is_deleted.is_(False),
                Project.id.not_in(ids),
            )
        ).scalars().all())
        if conflicts:
            codes = "、".join(f"「{c.code}」" for c in conflicts)
            raise BizException(f"项目编号 {codes} 已被其他项目占用，无法恢复", code=409, http_status=409)
        for p in projects:
            p.is_deleted = False
            p.deleted_at = None
            # 反向级联：恢复删除时一并软删的节点/任务/成员
            for model, fk in [
                (ProjectNode, ProjectNode.project_id),
                (Task, Task.project_id),
                (ProjectMember, ProjectMember.project_id),
            ]:
                for row in self.db.execute(
                    select(model).where(fk == p.id, model.is_deleted.is_(True))
                ).scalars().all():
                    row.is_deleted = False
                    row.deleted_at = None
        return len(projects)

    def purge_projects(self, project_ids: list[int]) -> int:
        """回收站彻底删除：物理删除项目及全部关联数据（不可恢复）。

        数据库兼容：按外键 RESTRICT 约束的依赖顺序删除（先子表后父表），
        自引用 project_node.parent_id CASCADE 由一次性全删本项目的节点解决；
        空 in_ 列表用 [0] 兜底，PG 与 SQLite 均可用。
        """
        ids = list(dict.fromkeys(project_ids or []))
        if not ids:
            raise BizException("请选择要删除的项目")
        projects = list(self.db.execute(select(Project).where(Project.id.in_(ids))).scalars().all())
        if len(projects) != len(ids):
            raise NotFoundError("部分项目不存在")
        node_ids = list(self.db.execute(
            select(ProjectNode.id).where(ProjectNode.project_id.in_(ids))
        ).scalars().all())
        task_ids = list(self.db.execute(
            select(Task.id).where(Task.project_id.in_(ids))
        ).scalars().all())
        review_ids = list(self.db.execute(
            select(NodeReview.id).where(NodeReview.project_node_id.in_(node_ids or [0]))
        ).scalars().all())
        progress_ids = list(self.db.execute(
            select(Progress.id).where(Progress.project_id.in_(ids))
        ).scalars().all())

        # 通知指向项目/节点（无外键约束），一并清理避免残留失效链接
        self.db.execute(delete(Notification).where(or_(
            and_(Notification.ref_type == "project", Notification.ref_id.in_(ids)),
            and_(Notification.ref_type == "node", Notification.ref_id.in_(node_ids or [0])),
        )))
        self.db.execute(delete(ProgressTaskLink).where(or_(
            ProgressTaskLink.progress_id.in_(progress_ids or [0]),
            ProgressTaskLink.task_id.in_(task_ids or [0]),
        )))
        self.db.execute(delete(Attachment).where(or_(
            Attachment.project_id.in_(ids),
            Attachment.project_node_id.in_(node_ids or [0]),
            Attachment.task_id.in_(task_ids or [0]),
            Attachment.review_id.in_(review_ids or [0]),
        )))
        self.db.execute(delete(Progress).where(Progress.project_id.in_(ids)))
        self.db.execute(delete(Task).where(Task.project_id.in_(ids)))
        self.db.execute(delete(NodeReview).where(NodeReview.project_node_id.in_(node_ids or [0])))
        self.db.execute(delete(WeeklyGoalItem).where(WeeklyGoalItem.project_id.in_(ids)))
        self.db.execute(delete(ProjectWeeklyGoal).where(ProjectWeeklyGoal.project_id.in_(ids)))
        self.db.execute(delete(ProjectNode).where(ProjectNode.project_id.in_(ids)))
        self.db.execute(delete(ProjectRoleAssignment).where(ProjectRoleAssignment.project_id.in_(ids)))
        self.db.execute(delete(ProjectMember).where(ProjectMember.project_id.in_(ids)))
        self.db.execute(delete(Project).where(Project.id.in_(ids)))
        return len(projects)

    # ---------- 成员 ----------
    def _upsert_member(self, project_id: int, user_id: int, role: Optional[str], invested: bool) -> ProjectMember:
        m = self.db.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        ).scalar_one_or_none()
        if m:
            m.is_deleted = False
            m.deleted_at = None
            if role is not None:
                m.project_role = role
            m.is_invested = invested
        else:
            m = ProjectMember(project_id=project_id, user_id=user_id, project_role=role, is_invested=invested, joined_at=date.today())
            self.db.add(m)
        self.db.flush()
        return m

    def _normalize_role_assignments(self, assignments: Optional[dict]) -> dict[str, list[int]]:
        normalized = empty_role_assignments()
        if not assignments:
            return normalized
        if not isinstance(assignments, dict):
            raise BizException("项目角色格式不正确")

        for raw_role, raw_user_ids in assignments.items():
            role = canonical_project_role(raw_role)
            if role not in PROJECT_ROLE_NAMES:
                raise BizException(f"不支持的项目角色：{raw_role}")
            if raw_user_ids is None:
                user_ids = []
            elif isinstance(raw_user_ids, (list, tuple, set)):
                user_ids = list(raw_user_ids)
            else:
                user_ids = [raw_user_ids]

            for raw_user_id in user_ids:
                try:
                    user_id = int(raw_user_id)
                except (TypeError, ValueError) as exc:
                    raise BizException(f"{role} 用户格式不正确") from exc
                if user_id not in normalized[role]:
                    normalized[role].append(user_id)

            if role in SINGLE_PROJECT_ROLES and len(normalized[role]) > 1:
                raise BizException(f"{role} 只能选择 1 名用户")

        user_ids = {user_id for ids in normalized.values() for user_id in ids}
        if user_ids:
            existing_ids = set(self.db.execute(select(User.id).where(User.id.in_(user_ids))).scalars().all())
            missing_ids = sorted(user_ids - existing_ids)
            if missing_ids:
                raise NotFoundError(f"角色用户不存在：{','.join(map(str, missing_ids))}")
        return normalized

    def replace_role_assignments(self, project_id: int, assignments: Optional[dict]) -> dict[str, list[int]]:
        """以完整角色集合替换项目角色，并确保角色用户属于项目成员。
        只增删有变化的分配；不变的保留原行，避免 DELETE+INSERT 同一角色触发唯一键冲突。"""
        normalized = self._normalize_role_assignments(assignments)
        current = self.db.execute(
            select(ProjectRoleAssignment).where(ProjectRoleAssignment.project_id == project_id)
        ).scalars().all()
        current_keys = {(row.role, row.user_id) for row in current}
        desired_keys = {
            (role, user_id)
            for role, user_ids in normalized.items()
            for user_id in user_ids
        }
        for row in current:
            if (row.role, row.user_id) not in desired_keys:
                self.db.delete(row)
        for role, user_id in desired_keys - current_keys:
            self.db.add(ProjectRoleAssignment(project_id=project_id, role=role, user_id=user_id))

        roles_by_user: dict[int, list[str]] = {}
        for role, user_ids in normalized.items():
            for user_id in user_ids:
                roles_by_user.setdefault(user_id, []).append(role)

        # 清理旧的兼容字段，避免编辑时清空角色后又被旧字段兜底恢复。
        members = self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.is_deleted.is_(False),
            )
        ).scalars().all()
        for member in members:
            if member.user_id in roles_by_user or not member.project_role:
                continue
            legacy_parts = re.split(r"[、,，;；]+", member.project_role)
            kept_parts = [part.strip() for part in legacy_parts if part.strip() and not canonical_project_role(part)]
            member.project_role = "、".join(kept_parts) or None

        # 角色用户自动成为项目成员，保留已有成员的投入状态。
        for user_id, roles in roles_by_user.items():
            member = self.db.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id == user_id,
                )
            ).scalar_one_or_none()
            invested = member.is_invested if member else True
            self._upsert_member(project_id, user_id, "、".join(roles), invested)
        self.db.flush()
        return normalized

    def list_role_assignments(self, project_id: int) -> dict[str, list[int]]:
        result = empty_role_assignments()
        rows = self.db.execute(
            select(ProjectRoleAssignment).where(ProjectRoleAssignment.project_id == project_id)
        ).scalars().all()
        for row in rows:
            if row.user_id not in result[row.role]:
                result[row.role].append(row.user_id)

        # 兼容旧数据：迁移前使用 project_member.project_role 的固定角色。
        members = self.db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.is_deleted.is_(False),
            )
        ).scalars().all()
        for member in members:
            role = canonical_project_role(member.project_role)
            if role and member.user_id not in result[role]:
                result[role].append(member.user_id)
        return result

    def list_members(self, project_id: int) -> list:
        role_assignments = self.list_role_assignments(project_id)
        roles_by_user = {}
        for role, user_ids in role_assignments.items():
            for user_id in user_ids:
                roles_by_user.setdefault(user_id, []).append(role)
        rows = self.db.execute(
            select(ProjectMember, User.display_name)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id, ProjectMember.is_deleted.is_(False))
        ).all()
        out = []
        for m, dname in rows:
            roles = roles_by_user.get(m.user_id, [])
            out.append({"id": m.id, "user_id": m.user_id, "project_role": m.project_role,
                        "roles": roles, "is_invested": m.is_invested, "display_name": dname})
            if roles:
                out[-1]["project_role"] = "、".join(roles)
        return out

    def add_member(self, project_id: int, body: MemberIn, user: dict) -> None:
        project = self.get_project(project_id)
        self.check_owner(project, user)
        if not self.db.get(User, body.user_id):
            raise NotFoundError("用户不存在")
        self._upsert_member(project_id, body.user_id, body.project_role, body.is_invested)
        self.db.commit()

    def remove_member(self, project_id: int, member_id: int, user: dict) -> None:
        project = self.get_project(project_id)
        self.check_owner(project, user)
        m = self.db.get(ProjectMember, member_id)
        if not m or m.project_id != project_id:
            raise NotFoundError("成员不存在")
        if m.user_id == project.owner_id:
            raise BizException("不能移除项目负责人", code=400)
        m.is_deleted = True
        from datetime import datetime, timezone
        m.deleted_at = datetime.now(timezone.utc)
        self.db.commit()

    # ---------- 节点 ----------
    def list_nodes(self, project_id: int) -> List[ProjectNode]:
        """顶层 TR 节点列表（不含子节点）。"""
        self.get_project(project_id)
        return list(self.db.execute(
            select(ProjectNode).where(
                ProjectNode.project_id == project_id,
                ProjectNode.parent_id.is_(None),
                ProjectNode.is_deleted.is_(False),
            ).order_by(ProjectNode.sequence)
        ).scalars().all())

    def list_subnodes(self, node_id: int) -> List[ProjectNode]:
        """某节点下的子节点列表。"""
        return list(self.db.execute(
            select(ProjectNode).where(
                ProjectNode.parent_id == node_id, ProjectNode.is_deleted.is_(False),
            ).order_by(ProjectNode.sequence)
        ).scalars().all())

    def subnodes_map(self, project_id: int) -> dict[int, List[ProjectNode]]:
        """项目全部顶层节点 → 子节点映射（供详情/周报返回）。"""
        top_ids = [n.id for n in self.list_nodes(project_id)]
        if not top_ids:
            return {}
        rows = self.db.execute(
            select(ProjectNode).where(
                ProjectNode.parent_id.in_(top_ids), ProjectNode.is_deleted.is_(False),
            ).order_by(ProjectNode.sequence)
        ).scalars().all()
        result: dict[int, List[ProjectNode]] = {tid: [] for tid in top_ids}
        for sub in rows:
            result.setdefault(sub.parent_id, []).append(sub)
        return result

    def add_subnode(self, parent_node_id: int, name: str, planned_end, user: dict) -> ProjectNode:
        """在节点下添加子节点（owner/admin）。"""
        parent = self.db.get(ProjectNode, parent_node_id)
        if not parent or parent.is_deleted or parent.parent_id is not None:
            raise BizException("父节点不存在或不是顶层节点")
        project = self.get_project(parent.project_id)
        self.check_owner(project, user)
        seq = self.db.execute(
            select(func.count()).select_from(ProjectNode).where(
                ProjectNode.parent_id == parent.id, ProjectNode.is_deleted.is_(False))
        ).scalar_one() + 1
        sub = ProjectNode(
            project_id=parent.project_id, parent_id=parent.id,
            node_key="SUB", name=name, sequence=seq, status="not_started",
            planned_end=planned_end,
        )
        self.db.add(sub)
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def update_subnode(self, subnode_id: int, name, planned_end, user: dict) -> ProjectNode:
        sub = self.db.get(ProjectNode, subnode_id)
        if not sub or sub.is_deleted or sub.parent_id is None:
            raise NotFoundError("子节点不存在")
        project = self.get_project(sub.project_id)
        self.check_owner(project, user)
        if name:
            sub.name = name
        sub.planned_end = planned_end
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def set_subnode_status(self, subnode_id: int, status: str, user: dict) -> ProjectNode:
        """更新子节点完成状态（member 可操作）。"""
        sub = self.db.get(ProjectNode, subnode_id)
        if not sub or sub.is_deleted or sub.parent_id is None:
            raise NotFoundError("子节点不存在")
        project = self.get_project(sub.project_id)
        self.check_member(project, user)
        if status not in ("done", "in_progress", "not_started"):
            raise BizException("子节点状态不合法")
        sub.status = status
        sub.actual_end = date.today() if status == "done" else None
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def delete_subnode(self, subnode_id: int, user: dict) -> None:
        sub = self.db.get(ProjectNode, subnode_id)
        if not sub or sub.is_deleted or sub.parent_id is None:
            raise NotFoundError("子节点不存在")
        project = self.get_project(sub.project_id)
        self.check_owner(project, user)
        sub.is_deleted = True
        from datetime import datetime, timezone
        sub.deleted_at = datetime.now(timezone.utc)
        self.db.commit()

    def update_node(self, node_id: int, body, user: dict) -> ProjectNode:
        node = self.db.get(ProjectNode, node_id)
        if not node or node.is_deleted:
            raise NotFoundError("节点不存在")
        project = self.get_project(node.project_id)
        self.check_owner(project, user)
        data = body.model_dump(exclude_none=True)
        old_status = node.status
        for f, v in data.items():
            setattr(node, f, v)
        # 维护 current_node_id：取第一个未 passed 的节点
        self._refresh_current_node(project)
        self.db.commit()
        self.db.refresh(node)
        return node

    def _refresh_current_node(self, project: Project) -> None:
        nodes = list(self.db.execute(
            select(ProjectNode).where(
                ProjectNode.project_id == project.id,
                ProjectNode.parent_id.is_(None),
                ProjectNode.is_deleted.is_(False),
            ).order_by(ProjectNode.sequence)
        ).scalars().all())
        current = None
        for n in nodes:
            if n.status != "passed":
                current = n
                break
        if current is None and nodes:
            current = nodes[-1]
        project.current_node_id = current.id if current else None
        self.db.flush()

    # ---------- 任务 ----------
    def list_tasks(self, project_id: int, node_id=None, status=None, assignee_id=None) -> List[Task]:
        self.get_project(project_id)
        q = select(Task).where(Task.project_id == project_id, Task.is_deleted.is_(False))
        if node_id:
            q = q.where(Task.project_node_id == node_id)
        if status:
            q = q.where(Task.status == status)
        if assignee_id:
            q = q.where(Task.assignee_id == assignee_id)
        return list(self.db.execute(q.order_by(Task.id)).scalars().all())

    def create_task(self, node_id: int, body: TaskCreate, user: dict) -> Task:
        node = self.db.get(ProjectNode, node_id)
        if not node or node.is_deleted:
            raise NotFoundError("节点不存在")
        project = self.get_project(node.project_id)
        self.check_member(project, user)
        task = Task(
            project_node_id=node_id, project_id=node.project_id, title=body.title,
            description=body.description, assignee_id=body.assignee_id,
            planned_start=body.planned_start, planned_end=body.planned_end,
            created_by=user["user_id"],
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_task(self, task_id: int, body: TaskUpdate, user: dict) -> Task:
        task = self.db.get(Task, task_id)
        if not task or task.is_deleted:
            raise NotFoundError("任务不存在")
        project = self.get_project(task.project_id)
        self.check_member(project, user)
        for f, v in body.model_dump(exclude_none=True).items():
            setattr(task, f, v)
        self.db.commit()
        self.db.refresh(task)
        return task

    def set_task_status(self, task_id: int, status: str, user: dict) -> Task:
        task = self.db.get(Task, task_id)
        if not task or task.is_deleted:
            raise NotFoundError("任务不存在")
        project = self.get_project(task.project_id)
        self.check_member(project, user)
        task.status = status
        if status == "done":
            task.actual_end = date.today()
        else:
            task.actual_end = None
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete_task(self, task_id: int, user: dict) -> None:
        task = self.db.get(Task, task_id)
        if not task or task.is_deleted:
            raise NotFoundError("任务不存在")
        project = self.get_project(task.project_id)
        self.check_member(project, user)
        task.is_deleted = True
        from datetime import datetime, timezone
        task.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
