"""进展与周目标服务。"""
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.responses import BizException, NotFoundError
from app.models.misc import Progress, ProgressTaskLink, ProjectWeeklyGoal, WeeklyGoalItem
from app.models.project import Project, ProjectNode, Task
from app.models.user import User
from app.schemas.progress import ProgressCreate, ProgressUpdate
from app.services.project_service import ProjectService


class ProgressService:
    def __init__(self, db: Session):
        self.db = db
        self.ps = ProjectService(db)

    # ---------- 周界 ----------
    def week_start_of(self, d: date) -> date:
        """按周界配置（默认周一）求某日期所在周的起始日。"""
        dow = self._week_start_dow()  # 1=周一
        # python weekday(): 周一=0
        delta = (d.weekday() - (dow - 1)) % 7
        return d - timedelta(days=delta)

    def _week_start_dow(self) -> int:
        from app.models.misc import Config
        row = self.db.get(Config, "report.week_start_dow")
        try:
            return int(row.value) if row and row.value else 1
        except ValueError:
            return 1

    # ---------- 进展 ----------
    def list_progress(self, project_id: int, date_from=None, date_to=None, author_id=None) -> List[dict]:
        self.ps.get_project(project_id)
        q = select(Progress, ProjectNode.name, User.display_name).\
            join(User, User.id == Progress.author_id).\
            outerjoin(ProjectNode, ProjectNode.id == Progress.project_node_id).\
            where(Progress.project_id == project_id, Progress.is_deleted.is_(False))
        if date_from:
            q = q.where(Progress.progress_date >= date_from)
        if date_to:
            q = q.where(Progress.progress_date <= date_to)
        if author_id:
            q = q.where(Progress.author_id == author_id)
        q = q.order_by(Progress.progress_date.desc(), Progress.id.desc())
        out = []
        for p, node_name, author_name in self.db.execute(q).all():
            task_ids = [l.task_id for l in self.db.execute(
                select(ProgressTaskLink).where(ProgressTaskLink.progress_id == p.id)).scalars().all()]
            out.append({
                "id": p.id, "project_id": p.project_id, "project_node_id": p.project_node_id,
                "node_name": node_name, "author_id": p.author_id, "author_name": author_name,
                "progress_date": p.progress_date, "today_work": p.today_work,
                "tomorrow_plan": p.tomorrow_plan, "risk": p.risk, "task_ids": task_ids,
                "created_at": p.created_at,
            })
        return out

    def create_progress(self, project_id: int, body: ProgressCreate, user: dict) -> Progress:
        project = self.ps.get_project(project_id)
        self.ps.check_member(project, user)
        # 校验 node 属于本项目
        if body.project_node_id:
            node = self.db.get(ProjectNode, body.project_node_id)
            if not node or node.is_deleted or node.project_id != project_id:
                raise BizException("节点不属于该项目")
        # 唯一约束：一人一天一项目/节点一条（DB 表达式索引兜底，这里先查给友好提示）
        existing = self.db.execute(
            select(Progress).where(
                Progress.project_id == project_id,
                Progress.author_id == user["user_id"],
                Progress.progress_date == body.progress_date,
                Progress.is_deleted.is_(False),
                (Progress.project_node_id == body.project_node_id) if body.project_node_id
                else Progress.project_node_id.is_(None),
            )
        ).scalar_one_or_none()
        if existing:
            raise BizException("当日该" + ("节点" if body.project_node_id else "项目") + "已填报，可编辑原记录", code=409, http_status=409)

        p = Progress(
            project_id=project_id, project_node_id=body.project_node_id, author_id=user["user_id"],
            progress_date=body.progress_date, today_work=body.today_work,
            tomorrow_plan=body.tomorrow_plan, risk=body.risk,
        )
        self.db.add(p)
        self.db.flush()
        self._link_tasks(p, body.task_ids, project_id)
        self.db.commit()
        self.db.refresh(p)
        return p

    def _link_tasks(self, progress: Progress, task_ids: List[int], project_id: int) -> None:
        for tid in task_ids or []:
            t = self.db.get(Task, tid)
            if t and not t.is_deleted and t.project_id == project_id:
                self.db.add(ProgressTaskLink(progress_id=progress.id, task_id=tid))

    def update_progress(self, progress_id: int, body: ProgressUpdate, user: dict) -> Progress:
        p = self.db.get(Progress, progress_id)
        if not p or p.is_deleted:
            raise NotFoundError("进展不存在")
        if user["role"] != "admin" and p.author_id != user["user_id"]:
            from app.core.responses import ForbiddenError
            raise ForbiddenError("仅本人或管理员可编辑")
        for f in ("today_work", "tomorrow_plan", "risk"):
            v = getattr(body, f, None)
            if v is not None:
                setattr(p, f, v)
        if body.task_ids is not None:
            self.db.query(ProgressTaskLink).filter(ProgressTaskLink.progress_id == p.id).delete()
            self._link_tasks(p, body.task_ids, p.project_id)
        self.db.commit()
        self.db.refresh(p)
        return p

    def delete_progress(self, progress_id: int, user: dict) -> None:
        p = self.db.get(Progress, progress_id)
        if not p or p.is_deleted:
            raise NotFoundError("进展不存在")
        if user["role"] != "admin" and p.author_id != user["user_id"]:
            from app.core.responses import ForbiddenError
            raise ForbiddenError("仅本人或管理员可删除")
        p.is_deleted = True
        p.deleted_at = datetime.now(timezone.utc)
        self.db.commit()

    def set_risk_resolved(self, progress_id: int, resolved: bool, user: dict) -> Progress:
        """关闭/重新打开进展中的风险（本人或管理员）。"""
        p = self.db.get(Progress, progress_id)
        if not p or p.is_deleted:
            raise NotFoundError("进展不存在")
        if user["role"] != "admin" and p.author_id != user["user_id"]:
            from app.core.responses import ForbiddenError
            raise ForbiddenError("仅本人或管理员可操作")
        p.risk_resolved = resolved
        self.db.commit()
        self.db.refresh(p)
        return p

    def my_todo(self, user: dict) -> dict:
        """我的待办：我参与且投入的项目（今天是否已填报）+ 指派给我的未完成任务。"""
        from app.models.project import ProjectMember
        today = date.today()
        # 我参与的项目
        rows = self.db.execute(
            select(Project, ProjectMember).join(ProjectMember, ProjectMember.project_id == Project.id).where(
                ProjectMember.user_id == user["user_id"],
                ProjectMember.is_deleted.is_(False),
                Project.is_deleted.is_(False),
                Project.status == "in_progress",
            )
        ).all()
        projects = []
        for proj, mem in rows:
            filled = self.db.execute(
                select(Progress).where(
                    Progress.project_id == proj.id, Progress.author_id == user["user_id"],
                    Progress.progress_date == today, Progress.is_deleted.is_(False),
                )
            ).scalars().first() is not None
            current_node = self.db.get(ProjectNode, proj.current_node_id) if proj.current_node_id else None
            projects.append({
                "id": proj.id, "name": proj.name, "code": proj.code,
                "is_invested": mem.is_invested, "filled_today": filled,
                "current_node_id": proj.current_node_id,
                "current_node_key": current_node.node_key if current_node else None,
                "current_node_name": current_node.name if current_node else None,
                "node_planned_end": current_node.planned_end if current_node else None,
                "node_overdue": bool(current_node and current_node.status != "passed" and current_node.planned_end and current_node.planned_end < today),
                "project_role": mem.project_role,
            })
        # 我的未完成任务
        tasks = self.db.execute(
            select(Task).where(Task.assignee_id == user["user_id"], Task.is_deleted.is_(False), Task.status != "done")
            .order_by(Task.planned_end)
        ).scalars().all()
        my_tasks = [{
            "id": t.id, "title": t.title, "project_id": t.project_id, "status": t.status,
            "planned_end": t.planned_end,
            "overdue": bool(t.planned_end and t.planned_end < today),
        } for t in tasks]
        recent_rows = self.db.execute(
            select(Progress, Project.name, Project.code, ProjectNode.name)
            .join(Project, Project.id == Progress.project_id)
            .outerjoin(ProjectNode, ProjectNode.id == Progress.project_node_id)
            .where(
                Progress.author_id == user["user_id"],
                Progress.is_deleted.is_(False),
                Project.is_deleted.is_(False),
            )
            .order_by(Progress.progress_date.desc(), Progress.id.desc())
            .limit(20)
        ).all()
        recent_progress = [{
            "id": p.id, "project_id": p.project_id, "project_name": project_name,
            "project_code": project_code, "progress_date": p.progress_date,
            "project_node_id": p.project_node_id, "node_name": node_name,
            "today_work": p.today_work, "tomorrow_plan": p.tomorrow_plan, "risk": p.risk,
        } for p, project_name, project_code, node_name in recent_rows]
        return {"date": today, "projects": projects, "tasks": my_tasks, "recent_progress": recent_progress}

    # ---------- 周目标 ----------
    def get_weekly_goal(self, project_id: int, week_start: date) -> Optional[ProjectWeeklyGoal]:
        self.ps.get_project(project_id)
        ws = self.week_start_of(week_start)
        return self.db.execute(
            select(ProjectWeeklyGoal).where(
                ProjectWeeklyGoal.project_id == project_id,
                ProjectWeeklyGoal.week_start == ws,
                ProjectWeeklyGoal.is_deleted.is_(False),
            )
        ).scalar_one_or_none()

    def set_weekly_goal(self, project_id: int, week_start: date, goal: str, user: dict) -> ProjectWeeklyGoal:
        project = self.ps.get_project(project_id)
        self.ps.check_owner(project, user)
        ws = self.week_start_of(week_start)
        row = self.db.execute(
            select(ProjectWeeklyGoal).where(
                ProjectWeeklyGoal.project_id == project_id, ProjectWeeklyGoal.week_start == ws,
            )
        ).scalar_one_or_none()
        if row:
            row.goal = goal
            row.is_deleted = False
            row.deleted_at = None
            row.set_by = user["user_id"]
        else:
            row = ProjectWeeklyGoal(project_id=project_id, week_start=ws, goal=goal, set_by=user["user_id"])
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    # ---------- 周目标条目（M7） ----------
    def list_weekly_goal_items(self, project_id: int, week_start: date) -> List[dict]:
        self.ps.get_project(project_id)
        ws = self.week_start_of(week_start)
        rows = self.db.execute(
            select(WeeklyGoalItem).where(
                WeeklyGoalItem.project_id == project_id, WeeklyGoalItem.week_start == ws,
            ).order_by(WeeklyGoalItem.sequence, WeeklyGoalItem.id)
        ).scalars().all()
        return [{
            "id": r.id, "goal": r.goal, "deadline": r.deadline,
            "done": r.done, "done_at": r.done_at, "sequence": r.sequence,
            "overdue": bool(not r.done and r.deadline and r.deadline < date.today()),
        } for r in rows]

    def add_weekly_goal_item(self, project_id: int, week_start, goal: str, deadline, user: dict) -> WeeklyGoalItem:
        project = self.ps.get_project(project_id)
        self.ps.check_owner(project, user)
        if isinstance(week_start, str):
            week_start = date.fromisoformat(week_start)
        ws = self.week_start_of(week_start)
        seq = self.db.execute(
            select(func.count()).select_from(WeeklyGoalItem).where(
                WeeklyGoalItem.project_id == project_id, WeeklyGoalItem.week_start == ws)
        ).scalar_one() + 1
        item = WeeklyGoalItem(project_id=project_id, week_start=ws, goal=goal, deadline=deadline, sequence=seq)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_weekly_goal_item(self, item_id: int, goal, deadline, user: dict) -> WeeklyGoalItem:
        item = self.db.get(WeeklyGoalItem, item_id)
        if not item:
            raise NotFoundError("周目标条目不存在")
        project = self.ps.get_project(item.project_id)
        self.ps.check_owner(project, user)
        if goal is not None:
            item.goal = goal
        item.deadline = deadline
        self.db.commit()
        self.db.refresh(item)
        return item

    def set_weekly_goal_item_done(self, item_id: int, done: bool, user: dict) -> WeeklyGoalItem:
        """完成/取消完成周目标条目（周会视图点击；成员可操作）。"""
        item = self.db.get(WeeklyGoalItem, item_id)
        if not item:
            raise NotFoundError("周目标条目不存在")
        project = self.ps.get_project(item.project_id)
        self.ps.check_member(project, user)
        item.done = done
        item.done_at = date.today() if done else None
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_weekly_goal_item(self, item_id: int, user: dict) -> None:
        item = self.db.get(WeeklyGoalItem, item_id)
        if not item:
            raise NotFoundError("周目标条目不存在")
        project = self.ps.get_project(item.project_id)
        self.ps.check_owner(project, user)
        self.db.delete(item)
        self.db.commit()
