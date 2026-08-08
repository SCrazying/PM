"""看板引擎：按项目状态分桶 + 年/月视图。（M7：健康度下线，看板列=手动状态）"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectNode


class BoardService:
    def __init__(self, db: Session):
        self.db = db

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
