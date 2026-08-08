"""看板引擎：可视化看板统计 + 状态分桶。（M7：健康度下线，看板列=手动状态）"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.misc import Progress
from app.models.project import ACTIVE_PROJECT_STATUSES, Project, ProjectMember, ProjectNode, Task
from app.models.user import User


class BoardService:
    def __init__(self, db: Session):
        self.db = db

    # ---------- 可视化看板统计（首页） ----------
    def summary(self, user: dict) -> dict:
        """聚合统计：状态分布 / 未关闭风险 / 待关注项目（当前节点超期）/ 我的待办。"""
        today = date.today()
        projects = list(self.db.execute(
            select(Project).where(Project.is_deleted.is_(False), Project.status != "archived")
        ).scalars().all())

        # 状态分布
        counts = {s: 0 for s in ("not_started", "in_progress", "delayed", "completed", "suspended")}
        for p in projects:
            if p.status in counts:
                counts[p.status] += 1

        # 未关闭风险（最近 30 天）
        since = today - timedelta(days=30)
        risk_rows = self.db.execute(
            select(Progress, Project.name, User.display_name)
            .join(Project, Project.id == Progress.project_id)
            .join(User, User.id == Progress.author_id)
            .where(
                Progress.is_deleted.is_(False), Project.is_deleted.is_(False),
                Progress.risk.isnot(None), Progress.risk != "",
                Progress.risk_resolved.is_(False),
                Progress.progress_date >= since,
            )
            .order_by(Progress.progress_date.desc())
            .limit(50)
        ).all()
        risks = [{"progress_id": p.id, "project_id": p.project_id, "project_name": pname,
                  "date": p.progress_date, "author": uname, "risk": p.risk}
                 for p, pname, uname in risk_rows]

        # 待关注项目：当前节点（未通过）计划完成已逾期（批量取节点，避免 N+1）
        node_map = {}
        node_ids = [p.current_node_id for p in projects if p.current_node_id]
        if node_ids:
            node_map = {n.id: n for n in self.db.execute(
                select(ProjectNode).where(ProjectNode.id.in_(node_ids))).scalars().all()}
        overdue_projects = []
        for p in projects:
            if p.status in ("completed", "suspended"):
                continue
            n = node_map.get(p.current_node_id) if p.current_node_id else None
            if n and n.status != "passed" and n.planned_end and n.planned_end < today:
                overdue_projects.append({
                    "id": p.id, "name": p.name, "status": p.status, "machine_model": p.machine_model,
                    "node_key": n.node_key, "node_name": n.name, "planned_end": n.planned_end,
                })
        overdue_projects.sort(key=lambda x: x["planned_end"])

        # 我的待办：指派未完成任务数 + 今天未填报的参与项目（在研）
        my_open_tasks = self.db.execute(
            select(Task).where(Task.assignee_id == user["user_id"], Task.is_deleted.is_(False), Task.status != "done")
        ).scalars().all()
        my_project_ids = {m.project_id for m in self.db.execute(
            select(ProjectMember).where(
                ProjectMember.user_id == user["user_id"], ProjectMember.is_deleted.is_(False))
        ).scalars().all()}
        filled_today = set(self.db.execute(
            select(Progress.project_id).where(
                Progress.author_id == user["user_id"], Progress.progress_date == today,
                Progress.is_deleted.is_(False))
        ).scalars().all())
        todo_projects = [
            {"id": p.id, "name": p.name, "status": p.status}
            for p in projects if p.id in my_project_ids and p.status in ACTIVE_PROJECT_STATUSES and p.id not in filled_today
        ]

        return {
            "status_counts": counts,
            "active": sum(counts[s] for s in ("not_started", "in_progress", "delayed", "suspended")),
            "completed": counts["completed"],
            "risk_count": len(risks),
            "risks": risks,
            "overdue_count": len(overdue_projects),
            "overdue_projects": overdue_projects,
            "my_task_count": len(my_open_tasks),
            "todo_projects": todo_projects,
        }

    # ---------- 看板列 ----------
    def board(self, granularity="month", year=None, month=None, machine_model=None, owner_id=None) -> dict:
        """看板按项目状态分桶（列=status，唯一规则见架构 §5.2）。"""
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
            col = p.status  # archived 已被过滤，其余直接进对应列
            if col not in columns:
                continue
            columns[col].append({
                "id": p.id, "name": p.name, "code": p.code, "machine_model": p.machine_model,
                "status": p.status, "current_node": node_name(p),
                "start_date": p.start_date, "end_date": p.end_date,
            })
        return {"columns": columns, "granularity": granularity, "year": year, "month": month}
