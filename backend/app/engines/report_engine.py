"""汇总引擎：项目周报 / 组内周报（按项目、按人）。"""
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.misc import Progress, ProjectWeeklyGoal
from app.models.project import Project, ProjectMember, ProjectNode, Task
from app.models.user import User
from app.services.progress_service import ProgressService


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.ps = ProgressService(db)

    def _week_range(self, week_start: date) -> tuple[date, date]:
        ws = self.ps.week_start_of(week_start)
        return ws, ws + timedelta(days=6)

    # ---------- 项目周报 ----------
    def project_weekly(self, project_id: int, week_start: date) -> dict:
        ws, we = self._week_range(week_start)
        project = self.db.get(Project, project_id)

        # 周目标
        goal_row = self.db.execute(
            select(ProjectWeeklyGoal).where(
                ProjectWeeklyGoal.project_id == project_id,
                ProjectWeeklyGoal.week_start == ws,
                ProjectWeeklyGoal.is_deleted.is_(False),
            )
        ).scalar_one_or_none()

        # 本周任务（计划区间与本周相交 OR 本周内完成）
        tasks = self.db.execute(
            select(Task).where(Task.project_id == project_id, Task.is_deleted.is_(False))
        ).scalars().all()
        week_tasks = []
        for t in tasks:
            in_plan = t.planned_start and t.planned_end and (t.planned_start <= we and t.planned_end >= ws)
            done_this_week = t.actual_end and (ws <= t.actual_end <= we)
            if in_plan or done_this_week or (t.status != "done" and t.planned_end is None):
                week_tasks.append({
                    "id": t.id, "title": t.title, "status": t.status,
                    "planned_start": t.planned_start, "planned_end": t.planned_end,
                    "actual_end": t.actual_end,
                    "overdue": bool(t.status != "done" and t.planned_end and t.planned_end < date.today()),
                    "assignee_id": t.assignee_id,
                })

        # 每日明细（按日期→人）
        progresses = self.db.execute(
            select(Progress, User.display_name).join(User, User.id == Progress.author_id).where(
                Progress.project_id == project_id,
                Progress.progress_date >= ws, Progress.progress_date <= we,
                Progress.is_deleted.is_(False),
            ).order_by(Progress.progress_date, Progress.id)
        ).all()
        daily = {}
        risks = []
        for p, uname in progresses:
            d = p.progress_date.isoformat()
            daily.setdefault(d, []).append({
                "author": uname, "today_work": p.today_work,
                "tomorrow_plan": p.tomorrow_plan, "risk": p.risk,
            })
            if p.risk:
                risks.append({"date": d, "author": uname, "risk": p.risk})

        # 当前节点
        current_node = None
        if project.current_node_id:
            node = self.db.get(ProjectNode, project.current_node_id)
            if node:
                current_node = {"id": node.id, "node_key": node.node_key, "name": node.name}

        return {
            "project": {"id": project.id, "name": project.name, "code": project.code,
                        "machine_model": project.machine_model, "health": project.health,
                        "status": project.status, "current_node": current_node},
            "week_start": ws, "week_end": we,
            "weekly_goal": goal_row.goal if goal_row else None,
            "tasks": week_tasks,
            "daily": daily,
            "risks": risks,
        }

    # ---------- 组内周报：按项目 ----------
    def group_weekly_by_project(self, week_start: date) -> list[dict]:
        projects = self.db.execute(
            select(Project).where(Project.is_deleted.is_(False), Project.status == "in_progress")
            .order_by(Project.id)
        ).scalars().all()
        return [self.project_weekly(p.id, week_start)["project"] | {"week_start": self._week_range(week_start)[0],
                "weekly_goal": self.project_weekly(p.id, week_start)["weekly_goal"]} for p in projects]

    # ---------- 组内周报：按人 ----------
    def group_weekly_by_person(self, week_start: date) -> list[dict]:
        ws, we = self._week_range(week_start)
        users = self.db.execute(select(User).where(User.status == "active").order_by(User.id)).scalars().all()
        out = []
        for u in users:
            # 参与的项目（含角色/投入）
            mems = self.db.execute(
                select(ProjectMember, Project).join(Project, Project.id == ProjectMember.project_id).where(
                    ProjectMember.user_id == u.id, ProjectMember.is_deleted.is_(False),
                    Project.is_deleted.is_(False), Project.status == "in_progress",
                )
            ).all()
            if not mems:
                continue
            projects = []
            for mem, proj in mems:
                # 本周此人在此项目的进展条数
                cnt = self.db.execute(
                    select(Progress).where(
                        Progress.project_id == proj.id, Progress.author_id == u.id,
                        Progress.progress_date >= ws, Progress.progress_date <= we,
                        Progress.is_deleted.is_(False),
                    )
                ).scalars().all()
                projects.append({
                    "project_id": proj.id, "name": proj.name, "code": proj.code,
                    "project_role": mem.project_role, "is_invested": mem.is_invested,
                    "progress_count": len(cnt),
                })
            # 本周进展明细
            progresses = self.db.execute(
                select(Progress, Project.name).join(Project, Project.id == Progress.project_id).where(
                    Progress.author_id == u.id, Progress.progress_date >= ws, Progress.progress_date <= we,
                    Progress.is_deleted.is_(False),
                ).order_by(Progress.progress_date)
            ).all()
            daily = {}
            for p, pname in progresses:
                daily.setdefault(p.progress_date.isoformat(), []).append(
                    {"project": pname, "today_work": p.today_work, "risk": p.risk})
            out.append({"user_id": u.id, "display_name": u.display_name,
                        "projects": projects, "daily": daily})
        return out
