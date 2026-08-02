"""个人工作汇总服务：按月/季/年聚合某成员的工作。"""
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.misc import Progress
from app.models.project import Project, ProjectMember, Task
from app.models.user import User


def period_range(period_type: str, ref: date) -> tuple[date, date]:
    if period_type == "month":
        start = ref.replace(day=1)
        end = (start.replace(year=start.year + 1, month=1, day=1) if start.month == 12
               else start.replace(month=start.month + 1, day=1))
        return start, end - __import__("datetime").timedelta(days=1)
    if period_type == "quarter":
        q = (ref.month - 1) // 3
        start = date(ref.year, q * 3 + 1, 1)
        end_month = q * 3 + 3
        end = (date(ref.year + 1, 1, 1) if end_month == 12 else date(ref.year, end_month + 1, 1))
        return start, end - __import__("datetime").timedelta(days=1)
    if period_type == "year":
        return date(ref.year, 1, 1), date(ref.year, 12, 31)
    raise ValueError("period_type 须为 month/quarter/year")


class PersonalService:
    def __init__(self, db: Session):
        self.db = db

    def summary(self, user_id: int, period_type: str, ref: date) -> dict:
        start, end = period_range(period_type, ref)
        user = self.db.get(User, user_id)

        # 参与的项目（周期内有进展或任务的）
        mems = self.db.execute(
            select(ProjectMember, Project).join(Project, Project.id == ProjectMember.project_id).where(
                ProjectMember.user_id == user_id, ProjectMember.is_deleted.is_(False),
                Project.is_deleted.is_(False),
            )
        ).all()

        projects = []
        total_progress = 0
        for mem, proj in mems:
            progresses = self.db.execute(
                select(Progress).where(
                    Progress.project_id == proj.id, Progress.author_id == user_id,
                    Progress.progress_date >= start, Progress.progress_date <= end,
                    Progress.is_deleted.is_(False),
                ).order_by(Progress.progress_date)
            ).scalars().all()
            done_tasks = self.db.execute(
                select(Task).where(
                    Task.project_id == proj.id, Task.assignee_id == user_id,
                    Task.is_deleted.is_(False), Task.status == "done",
                    Task.actual_end >= start, Task.actual_end <= end,
                )
            ).scalars().all()
            total_progress += len(progresses)
            if not progresses and not done_tasks:
                continue
            projects.append({
                "project_id": proj.id, "name": proj.name, "code": proj.code,
                "project_role": mem.project_role, "is_invested": mem.is_invested,
                "progress_count": len(progresses),
                "done_task_count": len(done_tasks),
                "done_tasks": [{"id": t.id, "title": t.title, "actual_end": t.actual_end} for t in done_tasks],
                "progresses": [{"date": p.progress_date, "today_work": p.today_work, "risk": p.risk} for p in progresses],
            })

        return {
            "user": {"id": user.id, "display_name": user.display_name},
            "period_type": period_type, "period_start": start, "period_end": end,
            "total_progress": total_progress,
            "projects": projects,
        }
