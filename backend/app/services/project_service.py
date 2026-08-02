"""项目服务：项目 CRUD、成员、TR 节点实例化、任务。含软删级联与 owner 强制入成员表。"""
from datetime import date
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.responses import BizException, ForbiddenError, NotFoundError
from app.models.project import Project, ProjectMember, ProjectNode, Task, TrTemplateNode
from app.models.user import User
from app.schemas.project import MemberIn, ProjectCreate, ProjectUpdate, TaskCreate, TaskUpdate


class ProjectService:
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
    def list_projects(self, status=None, owner_id=None, machine_model=None, keyword=None, page=1, size=20):
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
        q = q.order_by(Project.id.desc()).offset((page - 1) * size).limit(size)
        return list(self.db.execute(q).scalars().all()), total

    def create_project(self, body: ProjectCreate, operator_id: int) -> Project:
        # code 唯一（软删兼容由 DB 部分唯一索引兜底，这里先查）
        exists = self.db.execute(
            select(Project).where(Project.code == body.code, Project.is_deleted.is_(False))
        ).scalar_one_or_none()
        if exists:
            raise BizException("项目编号已存在", code=409, http_status=409)

        owner = self.db.get(User, body.owner_id)
        if not owner:
            raise NotFoundError("负责人用户不存在")

        project = Project(
            name=body.name, code=body.code, machine_model=body.machine_model,
            owner_id=body.owner_id, status="in_progress",
            start_date=body.start_date, end_date=body.end_date,
            description=body.description, created_by=operator_id,
        )
        self.db.add(project)
        self.db.flush()

        # 成员：负责人强制入成员表 + 其它成员
        self._upsert_member(project.id, body.owner_id, "负责人", True)
        seen = {body.owner_id}
        for m in body.members:
            if m.user_id in seen:
                continue
            seen.add(m.user_id)
            self._upsert_member(project.id, m.user_id, m.project_role, m.is_invested)

        # TR 节点实例化
        node_ids = body.node_ids or self._default_template_node_ids()
        self._instantiate_nodes(project, node_ids)

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

    def _instantiate_nodes(self, project: Project, template_node_ids: List[int]) -> None:
        if not template_node_ids:
            return
        nodes = self.db.execute(
            select(TrTemplateNode).where(TrTemplateNode.id.in_(template_node_ids)).order_by(TrTemplateNode.sequence)
        ).scalars().all()
        first_id = None
        for i, tn in enumerate(nodes):
            node = ProjectNode(
                project_id=project.id, template_node_id=tn.id, node_key=tn.node_key,
                name=tn.name, sequence=i + 1, status="not_started",
            )
            self.db.add(node)
            self.db.flush()
            if first_id is None:
                first_id = node.id
        project.current_node_id = first_id
        self.db.flush()

    def update_project(self, project_id: int, body: ProjectUpdate, user: dict) -> Project:
        project = self.get_project(project_id)
        self.check_owner(project, user)
        data = body.model_dump(exclude_none=True)
        # 负责人变更：同步成员表
        if "owner_id" in data and data["owner_id"] != project.owner_id:
            new_owner = self.db.get(User, data["owner_id"])
            if not new_owner:
                raise NotFoundError("新负责人不存在")
            self._upsert_member(project.id, data["owner_id"], "负责人", True)
        for f, v in data.items():
            setattr(project, f, v)
        self.db.commit()
        self.db.refresh(project)
        return project

    def archive_project(self, project_id: int, user: dict, archive: bool = True) -> Project:
        project = self.get_project(project_id)
        self.check_owner(project, user)
        project.status = "archived" if archive else "in_progress"
        if archive:
            from datetime import date as _d
            project.archived_at = _d.today()
        self.db.commit()
        self.db.refresh(project)
        return project

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

    def list_members(self, project_id: int) -> list:
        rows = self.db.execute(
            select(ProjectMember, User.display_name)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id, ProjectMember.is_deleted.is_(False))
        ).all()
        out = []
        for m, dname in rows:
            out.append({"id": m.id, "user_id": m.user_id, "project_role": m.project_role,
                        "is_invested": m.is_invested, "display_name": dname})
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
        self.get_project(project_id)
        return list(self.db.execute(
            select(ProjectNode).where(ProjectNode.project_id == project_id, ProjectNode.is_deleted.is_(False)).order_by(ProjectNode.sequence)
        ).scalars().all())

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
            select(ProjectNode).where(ProjectNode.project_id == project.id, ProjectNode.is_deleted.is_(False)).order_by(ProjectNode.sequence)
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
