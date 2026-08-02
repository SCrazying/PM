"""看板状态引擎：health 派生 + 看板列口径 + 年/月视图。"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.misc import Config, Progress
from app.models.project import Project, ProjectNode, Task


class BoardService:
    def __init__(self, db: Session):
        self.db = db

    def _risk_window_days(self) -> int:
        row = self.db.get(Config, "reminder.risk_window_days")
        try:
            return int(row.value) if row and row.value else 7
        except ValueError:
            return 7

    # ---------- health 计算 ----------
    def compute_health(self, project: Project) -> str:
        """仅对在研项目计算；终态冻结。"""
        if project.status in ("completed", "archived"):
            return project.health  # 冻结
        today = date.today()

        # delayed：存在延期节点或延期任务
        delayed_node = self.db.execute(
            select(ProjectNode).where(
                ProjectNode.project_id == project.id, ProjectNode.is_deleted.is_(False),
                ProjectNode.status != "passed", ProjectNode.planned_end.isnot(None),
                ProjectNode.planned_end < today,
            )
        ).scalars().first()
        delayed_task = self.db.execute(
            select(Task).where(
                Task.project_id == project.id, Task.is_deleted.is_(False),
                Task.status != "done", Task.planned_end.isnot(None), Task.planned_end < today,
            )
        ).scalars().first()
        if delayed_node or delayed_task:
            return "delayed"

        # at_risk：近期（N 天内）有风险进展
        since = today - timedelta(days=self._risk_window_days())
        risk = self.db.execute(
            select(Progress).where(
                Progress.project_id == project.id, Progress.is_deleted.is_(False),
                Progress.risk.isnot(None), Progress.risk != "",
                Progress.progress_date >= since,
            )
        ).scalars().first()
        if risk:
            return "at_risk"
        return "on_track"

    def refresh_health(self, project: Project) -> Project:
        project.health = self.compute_health(project)
        self.db.flush()
        return project

    def refresh_all_health(self) -> int:
        """每日兜底：重算所有在研项目 health。"""
        projects = self.db.execute(
            select(Project).where(Project.is_deleted.is_(False), Project.status.in_(["not_started", "in_progress", "suspended"]))
        ).scalars().all()
        for p in projects:
            p.health = self.compute_health(p)
        self.db.commit()
        return len(projects)

    # ---------- 看板列 ----------
    def board_column(self, project: Project) -> str:
        """看板列判定（唯一规则，见架构 §5.2）。"""
        if project.status == "not_started":
            return "not_started"
        if project.status == "completed":
            return "completed"
        if project.status == "suspended":
            return "suspended"
        if project.status == "in_progress":
            return "delayed" if project.health == "delayed" else "in_progress"
        return "archived"  # archived 默认不显示

    def board(self, granularity="month", year=None, month=None, machine_model=None, owner_id=None) -> dict:
        q = select(Project).where(Project.is_deleted.is_(False), Project.status != "archived")
        if machine_model:
            q = q.where(Project.machine_model == machine_model)
        if owner_id:
            q = q.where(Project.owner_id == owner_id)
        projects = list(self.db.execute(q).scalars().all())

        # 当前节点名
        def node_name(p):
            if not p.current_node_id:
                return None
            n = self.db.get(ProjectNode, p.current_node_id)
            return f"{n.node_key} {n.name}" if n else None

        columns = {"not_started": [], "in_progress": [], "delayed": [], "completed": [], "suspended": []}
        for p in projects:
            col = self.board_column(p)
            if col not in columns:
                continue
            columns[col].append({
                "id": p.id, "name": p.name, "code": p.code, "machine_model": p.machine_model,
                "health": p.health, "status": p.status, "current_node": node_name(p),
                "start_date": p.start_date, "end_date": p.end_date,
            })
        return {"columns": columns, "granularity": granularity, "year": year, "month": month}
