"""节点流转引擎：状态迁移、评审、conditional_pass 整改闭环。"""
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.responses import BizException, ForbiddenError, NotFoundError
from app.models.project import NodeReview, Project, ProjectNode, Task

# 状态迁移表（from -> set(to)）
TRANSITIONS = {
    "not_started": {"in_progress"},
    "in_progress": {"pending_review"},
    "pending_review": {"passed", "failed", "in_progress"},  # in_progress=撤回送审
    "failed": {"in_progress", "pending_review"},            # 打回重做/重新送审
    "passed": {"in_progress"},                              # reopen（仅 admin）
}


class NodeFlowService:
    def __init__(self, db: Session):
        self.db = db

    def _get(self, node_id: int) -> ProjectNode:
        node = self.db.get(ProjectNode, node_id)
        if not node or node.is_deleted:
            raise NotFoundError("节点不存在")
        return node

    def _check_perm(self, project: Project, user: dict, admin_only: bool = False) -> None:
        if admin_only:
            if user["role"] != "admin":
                raise ForbiddenError("仅管理员可执行")
        else:
            if user["role"] != "admin" and project.owner_id != user["user_id"]:
                raise ForbiddenError("仅项目负责人或管理员可操作")

    def _refresh_current_node(self, project: Project) -> None:
        # 仅顶层节点参与 current_node_id 判定，子节点不作为当前节点
        nodes = list(self.db.execute(
            select(ProjectNode).where(
                ProjectNode.project_id == project.id,
                ProjectNode.parent_id.is_(None),
                ProjectNode.is_deleted.is_(False),
            ).order_by(ProjectNode.sequence)
        ).scalars().all())
        current = next((n for n in nodes if n.status != "passed"), nodes[-1] if nodes else None)
        project.current_node_id = current.id if current else None
        self.db.flush()

    def _has_unfinished_rectify_tasks(self, node: ProjectNode) -> bool:
        """是否存在未完成的整改任务（源自该节点评审）。"""
        review_ids = [r.id for r in self.db.execute(
            select(NodeReview).where(NodeReview.project_node_id == node.id)).scalars().all()]
        if not review_ids:
            return False
        t = self.db.execute(
            select(Task).where(
                Task.source_review_id.in_(review_ids), Task.is_deleted.is_(False), Task.status != "done")
        ).scalars().first()
        return t is not None

    def node_rectifying(self, node: ProjectNode) -> bool:
        """整改中：最新评审为 conditional_pass 且有未关闭整改任务。"""
        latest = self.db.execute(
            select(NodeReview).where(NodeReview.project_node_id == node.id)
            .order_by(NodeReview.review_date.desc(), NodeReview.id.desc())
        ).scalars().first()
        if not latest or latest.conclusion != "conditional_pass":
            return False
        return self._has_unfinished_rectify_tasks(node)

    def _can_enter_next(self, node: ProjectNode) -> tuple[bool, str]:
        """流转门控（适配无评审环境）：本节点已通过(passed)即可进入下一节点。
        评审为可选增强：若存在评审结论为 conditional_pass 且整改未关闭，仍拦截提示。
        未评审也可推进（组内无正式评审流程时，负责人完成节点即放行）。"""
        if node.status != "passed":
            return False, "节点尚未完成"
        latest = self.db.execute(
            select(NodeReview).where(NodeReview.project_node_id == node.id)
            .order_by(NodeReview.review_date.desc(), NodeReview.id.desc())
        ).scalars().first()
        if latest and latest.conclusion == "conditional_pass" and self._has_unfinished_rectify_tasks(node):
            return False, "存在未关闭的整改任务，不能进入下一节点"
        if latest and latest.conclusion == "fail":
            return False, "评审未通过"
        return True, ""

    def transition(self, node_id: int, target: str, user: dict) -> ProjectNode:
        node = self._get(node_id)
        project = self.db.get(Project, node.project_id)
        self._check_perm(project, user)

        # reopen（passed -> in_progress）仅 admin
        if node.status == "passed" and target == "in_progress":
            self._check_perm(project, user, admin_only=True)

        allowed = TRANSITIONS.get(node.status, set())
        if target not in allowed:
            raise BizException(f"不允许从 {node.status} 流转到 {target}")

        # 进入 passed 前，若序列上有后续节点想推进，由 transition 到下一节点时校验（此处不阻断 passed）
        node.status = target
        now_date = date.today()
        if target == "in_progress" and not node.actual_start:
            node.actual_start = now_date
        if target == "passed":
            node.actual_end = now_date

        self._refresh_current_node(project)
        self.db.commit()
        self.db.refresh(node)
        return node

    def advance_to_next(self, node_id: int, user: dict) -> ProjectNode:
        """推进到下一节点（带门控校验）。"""
        node = self._get(node_id)
        project = self.db.get(Project, node.project_id)
        self._check_perm(project, user)

        ok, reason = self._can_enter_next(node)
        if not ok:
            raise BizException(f"不能进入下一节点：{reason}")

        nxt = self.db.execute(
            select(ProjectNode).where(
                ProjectNode.project_id == node.project_id, ProjectNode.is_deleted.is_(False),
                ProjectNode.sequence > node.sequence,
            ).order_by(ProjectNode.sequence)
        ).scalars().first()
        if not nxt:
            raise BizException("已是最后一个节点")
        # 当前节点确保 passed
        node.status = "passed"
        if not node.actual_end:
            node.actual_end = date.today()
        nxt.status = "in_progress"
        if not nxt.actual_start:
            nxt.actual_start = date.today()
        self._refresh_current_node(project)
        self.db.commit()
        self.db.refresh(nxt)
        return nxt

    def force_transition(self, node_id: int, target: str, user: dict) -> ProjectNode:
        """强制流转（仅 admin，记审计由路由层负责）。"""
        node = self._get(node_id)
        project = self.db.get(Project, node.project_id)
        if user["role"] != "admin":
            raise ForbiddenError("仅管理员可强制流转")
        node.status = target
        self._refresh_current_node(project)
        self.db.commit()
        self.db.refresh(node)
        return node

    def add_review(self, node_id: int, conclusion: str, comment: str, review_date: date, user: dict) -> NodeReview:
        node = self._get(node_id)
        project = self.db.get(Project, node.project_id)
        self._check_perm(project, user)
        if conclusion not in ("pass", "conditional_pass", "fail"):
            raise BizException("评审结论不合法")
        review = NodeReview(
            project_node_id=node.id, conclusion=conclusion, comment=comment,
            review_date=review_date, reviewer_id=user["user_id"],
        )
        self.db.add(review)
        # 同步节点状态
        if conclusion in ("pass", "conditional_pass"):
            node.status = "passed"
            if not node.actual_end:
                node.actual_end = review_date
        else:
            node.status = "failed"
        self.db.flush()
        self._refresh_current_node(project)
        self.db.commit()
        self.db.refresh(review)
        return review

    def list_reviews(self, node_id: int) -> list[NodeReview]:
        self._get(node_id)
        return list(self.db.execute(
            select(NodeReview).where(NodeReview.project_node_id == node_id)
            .order_by(NodeReview.review_date.desc(), NodeReview.id.desc())
        ).scalars().all())

    # ---------- M4：完成度 + 直接完成节点 ----------
    def node_completion(self, node_id: int) -> dict:
        """节点完成度：已完成任务 / 总任务。"""
        node = self._get(node_id)
        tasks = list(self.db.execute(
            select(Task).where(Task.project_node_id == node.id, Task.is_deleted.is_(False))
        ).scalars().all())
        total = len(tasks)
        done = sum(1 for t in tasks if t.status == "done")
        return {"node_id": node.id, "total": total, "done": done,
                "percent": round(done / total * 100) if total else 100}

    def project_completion(self, project_id: int) -> dict:
        """项目完成度：已通过一级节点 / 一级节点总数（不含子节点；子节点状态为 done 不是 passed，计入会拉低）。无节点给 100%。"""
        nodes = list(self.db.execute(
            select(ProjectNode).where(
                ProjectNode.project_id == project_id,
                ProjectNode.parent_id.is_(None),
                ProjectNode.is_deleted.is_(False),
            )
        ).scalars().all())
        total = len(nodes)
        passed = sum(1 for n in nodes if n.status == "passed")
        return {"project_id": project_id, "total": total, "passed": passed,
                "percent": round(passed / total * 100) if total else 100}

    def complete_node(self, node_id: int, user: dict) -> ProjectNode:
        """负责人/管理员直接完成节点（置 passed + actual_end + 维护 current_node_id）。
        灵活优先：不强制任务全完成；完成后若存在下一节点，自动将其置 in_progress（无评审环境一步推进）。"""
        node = self._get(node_id)
        project = self.db.get(Project, node.project_id)
        self._check_perm(project, user)
        if node.status == "passed":
            return node  # 幂等
        node.status = "passed"
        if not node.actual_end:
            node.actual_end = date.today()
        # 自动激活下一节点（若存在）
        nxt = self.db.execute(
            select(ProjectNode).where(
                ProjectNode.project_id == node.project_id, ProjectNode.parent_id.is_(None),
                ProjectNode.is_deleted.is_(False), ProjectNode.sequence > node.sequence,
            ).order_by(ProjectNode.sequence)
        ).scalars().first()
        if nxt and nxt.status != "passed":
            nxt.status = "in_progress"
            if not nxt.actual_start:
                nxt.actual_start = date.today()
        self._refresh_current_node(project)
        self.db.commit()
        self.db.refresh(node)
        return node
