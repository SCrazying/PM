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

    def _last_workday(self, d: date) -> date:
        """上一个工作日（跳过周六日）：早会看板检查的是上一工作日的日报。"""
        d = d - timedelta(days=1)
        while d.weekday() >= 5:  # 5=周六, 6=周日
            d -= timedelta(days=1)
        return d

    # ---------- 可视化看板统计（首页） ----------
    def summary(self, user: dict) -> dict:
        """聚合统计：状态分布 / 未关闭风险 / 待关注项目（当前节点超期）/ 我的待办。"""
        today = date.today()
        projects = list(self.db.execute(
            select(Project).where(Project.is_deleted.is_(False))
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

        # 昨日进展 / 今日计划缺报（早会提醒）：上一工作日，在研项目成员+负责人中
        # 未填今日进展(today_work) 的人 → missing_progress；未填明日计划(tomorrow_plan) 的人 → missing_plan
        target = self._last_workday(today)
        active_projects = [p for p in projects if p.status in ACTIVE_PROJECT_STATUSES]
        active_ids = [p.id for p in active_projects]
        proj_map = {p.id: p for p in projects}
        user_projects = {}
        for p in active_projects:
            user_projects.setdefault(p.owner_id, {})[p.id] = p
        if active_ids:
            for m in self.db.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id.in_(active_ids), ProjectMember.is_deleted.is_(False))
            ).scalars().all():
                if m.project_id in proj_map:
                    user_projects.setdefault(m.user_id, {})[m.project_id] = proj_map[m.project_id]

        report_rows = self.db.execute(
            select(Progress).where(
                Progress.progress_date == target, Progress.is_deleted.is_(False))
        ).scalars().all()
        filled_progress, filled_plan = set(), set()
        for pr in report_rows:
            if pr.today_work and pr.today_work.strip():
                filled_progress.add(pr.author_id)
            if pr.tomorrow_plan and pr.tomorrow_plan.strip():
                filled_plan.add(pr.author_id)

        uid_list = list(user_projects)
        name_map = {}
        if uid_list:
            name_map = {u.id: u.display_name for u in self.db.execute(
                select(User).where(User.id.in_(uid_list))).scalars().all()}

        def _mk(uid, projs):
            return {"user_id": uid, "display_name": name_map.get(uid), "projects": [
                {"id": p.id, "name": p.name} for p in projs.values()]}

        missing_progress = sorted(
            (_mk(uid, projs) for uid, projs in user_projects.items() if uid not in filled_progress),
            key=lambda x: (x["display_name"] or ""))
        missing_plan = sorted(
            (_mk(uid, projs) for uid, projs in user_projects.items() if uid not in filled_plan),
            key=lambda x: (x["display_name"] or ""))

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
            "report_target_date": target,
            "missing_progress": missing_progress,
            "missing_plan": missing_plan,
            "missing_count": len(missing_progress) + len(missing_plan),
        }

    # ---------- 看板列 ----------
    def board(self, granularity="month", year=None, month=None, machine_model=None, owner_id=None) -> dict:
        """看板按项目状态分桶（列=status，唯一规则见架构 §5.2）。"""
        q = select(Project).where(Project.is_deleted.is_(False))
        if machine_model:
            q = q.where(Project.machine_model == machine_model)
        if owner_id:
            q = q.where(Project.owner_id == owner_id)
        projects = list(self.db.execute(q).scalars().all())

        # 负责人姓名（批量取，避免 N+1）
        owner_ids = {p.owner_id for p in projects if p.owner_id}
        owner_map = {}
        if owner_ids:
            owner_map = {u.id: u.display_name for u in self.db.execute(
                select(User).where(User.id.in_(owner_ids))).scalars().all()}

        # 当前节点（批量取，避免 N+1），用于节点名 + 超期判断
        today = date.today()
        cur_node_ids = [p.current_node_id for p in projects if p.current_node_id]
        node_map = {}
        if cur_node_ids:
            node_map = {n.id: n for n in self.db.execute(
                select(ProjectNode).where(ProjectNode.id.in_(cur_node_ids))).scalars().all()}

        def node_name(n):
            return f"{n.node_key} {n.name}" if n else None

        def node_overdue(n):
            return bool(n and n.status != "passed" and n.planned_end and n.planned_end < today)

        columns = {"not_started": [], "in_progress": [], "delayed": [], "completed": [], "suspended": []}
        for p in projects:
            col = p.status  # archived 已被过滤，其余直接进对应列
            if col not in columns:
                continue
            cur = node_map.get(p.current_node_id) if p.current_node_id else None
            columns[col].append({
                "id": p.id, "name": p.name, "code": p.code, "machine_model": p.machine_model,
                "status": p.status, "current_node": node_name(cur), "node_overdue": node_overdue(cur),
                "owner_id": p.owner_id, "owner_name": owner_map.get(p.owner_id),
                "start_date": p.start_date, "end_date": p.end_date,
            })
        return {"columns": columns, "granularity": granularity, "year": year, "month": month}
