"""汇总引擎：项目周报 / 组内周报（按项目、按人）。"""
from datetime import date, timedelta
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.project_roles import PROJECT_ROLE_NAMES, canonical_project_role
from app.models.misc import Progress, ProjectWeeklyGoal
from app.models.project import Project, ProjectMember, ProjectNode, ProjectRoleAssignment, Task
from app.models.user import User
from app.services.progress_service import ProgressService


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.ps = ProgressService(db)

    def _week_range(self, week_start: date) -> tuple[date, date]:
        ws = self.ps.week_start_of(week_start)
        return ws, ws + timedelta(days=6)

    def _project_role_summary(self, project: Project, members: list[tuple[ProjectMember | None, str]]) -> str:
        """生成可直接放入 Excel 单元格的项目角色摘要。"""
        role_names = {role: [] for role in PROJECT_ROLE_NAMES}
        assignments = self.db.execute(
            select(ProjectRoleAssignment, User.display_name)
            .join(User, User.id == ProjectRoleAssignment.user_id)
            .where(ProjectRoleAssignment.project_id == project.id)
        ).all()
        for assignment, display_name in assignments:
            if display_name and display_name not in role_names[assignment.role]:
                role_names[assignment.role].append(display_name)

        # 兼容尚未迁移角色分配记录的历史项目。
        for member, display_name in members:
            if not member:
                continue
            role = canonical_project_role(member.project_role)
            if role and display_name not in role_names[role]:
                role_names[role].append(display_name)

        lines = []
        owner = self.db.get(User, project.owner_id)
        if owner and owner.display_name:
            lines.append(f"负责人: {owner.display_name}")
        for role in PROJECT_ROLE_NAMES:
            if role_names[role]:
                lines.append(f"{role}: {'、'.join(role_names[role])}")
        return "\n".join(lines)

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

    # ---------- 项目台账 Excel 导出（M5） ----------
    def export_ledger_xlsx(self, week_start: date) -> BytesIO:
        """按成员一行导出固定 7 列项目台账。"""
        ws_start, ws_end = self._week_range(week_start)
        wb = Workbook()
        ws = wb.active
        ws.title = "项目台账"
        headers = ["机型", "项目", "是否投入", "项目角色", "关键节点", "周目标", "本周任务"]
        widths = [14, 24, 12, 16, 18, 30, 52]
        header_fill = PatternFill("solid", fgColor="4F6EF7")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        thin = Side(style="thin", color="D9E0EA")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        for col, (header, width) in enumerate(zip(headers, widths), start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border
            ws.column_dimensions[get_column_letter(col)].width = width
        ws.row_dimensions[1].height = 28
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = "A1:G1"

        projects = self.db.execute(
            select(Project).where(Project.is_deleted.is_(False), Project.status != "archived").order_by(Project.name)
        ).scalars().all()
        row_no = 2
        for project in projects:
            current = self.db.get(ProjectNode, project.current_node_id) if project.current_node_id else None
            goal = self.db.execute(select(ProjectWeeklyGoal).where(
                ProjectWeeklyGoal.project_id == project.id,
                ProjectWeeklyGoal.week_start == ws_start,
                ProjectWeeklyGoal.is_deleted.is_(False),
            )).scalar_one_or_none()
            members = self.db.execute(
                select(ProjectMember, User.display_name).join(User, User.id == ProjectMember.user_id).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.is_deleted.is_(False),
                ).order_by(ProjectMember.id)
            ).all()
            # 没有成员时仍保留项目一行，方便发现数据缺口
            if not members:
                members = [(None, "未分配")]
            role_text = self._project_role_summary(project, members)
            for member, display_name in members:
                member_tasks = []
                member_progress = []
                if member:
                    tasks = self.db.execute(select(Task).where(
                        Task.project_id == project.id, Task.assignee_id == member.user_id,
                        Task.is_deleted.is_(False),
                    )).scalars().all()
                    member_tasks = [f"{'✓' if t.status == 'done' else '○'} {t.title}" for t in tasks]
                    progresses = self.db.execute(select(Progress).where(
                        Progress.project_id == project.id, Progress.author_id == member.user_id,
                        Progress.progress_date >= ws_start, Progress.progress_date <= ws_end,
                        Progress.is_deleted.is_(False),
                    ).order_by(Progress.progress_date)).scalars().all()
                    member_progress = [f"[{p.progress_date}] {p.today_work}" for p in progresses]
                task_text = "\n".join(member_tasks + member_progress)
                values = [
                    project.machine_model or "",
                    project.name,
                    "是" if member and member.is_invested else "否",
                    role_text,
                    f"{current.node_key} {current.name}" if current else "",
                    goal.goal if goal else "",
                    task_text,
                ]
                for col, value in enumerate(values, start=1):
                    cell = ws.cell(row=row_no, column=col, value=value)
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                    cell.border = border
                role_lines = role_text.count("\n") + 1 if role_text else 1
                task_lines = task_text.count("\n") + 1 if task_text else 1
                ws.row_dimensions[row_no].height = min(180, max(42, 18 * max(role_lines, task_lines)))
                row_no += 1
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

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
