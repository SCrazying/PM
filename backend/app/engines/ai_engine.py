"""AI 引擎：调用 OpenAI 兼容 API 生成个人绩效总结。失败降级为模板汇总。"""
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.misc import AiSummary
from app.services.personal_service import PersonalService, period_range

logger = get_logger("pm.ai")


class AiService:
    def __init__(self, db: Session):
        self.db = db
        self.personal = PersonalService(db)

    def _build_prompt(self, summary: dict) -> str:
        u = summary["user"]["display_name"]
        lines = [f"请为以下员工的工作数据生成一份{self._period_label(summary['period_type'])}工作总结，"
                 f"用于绩效考核参考。要求：分点、客观、突出完成的事项与项目贡献，200-400字，中文。\n",
                 f"员工：{u}", f"周期：{summary['period_start']} 至 {summary['period_end']}\n", "工作数据："]
        for p in summary["projects"]:
            lines.append(f"\n【项目】{p['name']}（角色：{p.get('project_role') or '成员'}）")
            lines.append(f"  完成任务 {p['done_task_count']} 项：")
            for t in p["done_tasks"][:20]:
                lines.append(f"    - {t['title']}（{t['actual_end']}）")
            lines.append(f"  进展记录 {p['progress_count']} 条，部分如下：")
            for pr in p["progresses"][:15]:
                risk = f"（风险：{pr['risk']}）" if pr.get("risk") else ""
                lines.append(f"    - [{pr['date']}] {pr['today_work']}{risk}")
        return "\n".join(lines)

    def _period_label(self, p: str) -> str:
        return {"month": "月度", "quarter": "季度", "year": "年度"}.get(p, "周期性")

    def _call_llm(self, prompt: str) -> str:
        url = settings.AI_BASE_URL.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {settings.AI_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": settings.AI_MODEL,
            "messages": [
                {"role": "system", "content": "你是一位专业的技术团队绩效考核助手，擅长把工作记录整理成客观的工作总结。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        last_err = None
        for _ in range(settings.AI_MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=settings.AI_TIMEOUT_SECONDS) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as e:  # noqa: BLE001
                last_err = e
                logger.warning("AI 调用失败，重试：%s", e)
        raise RuntimeError(f"AI 调用失败：{last_err}")

    def _template_summary(self, summary: dict) -> str:
        """降级：模板化汇总（不润色）。"""
        u = summary["user"]["display_name"]
        lines = [f"{u} {self._period_label(summary['period_type'])}工作汇总（{summary['period_start']} ~ {summary['period_end']}）\n"]
        for p in summary["projects"]:
            lines.append(f"■ {p['name']}（{p.get('project_role') or '成员'}）")
            lines.append(f"  完成任务 {p['done_task_count']} 项，进展记录 {p['progress_count']} 条")
            for t in p["done_tasks"]:
                lines.append(f"    ✓ {t['title']}")
        return "\n".join(lines)

    def generate(self, user_id: int, period_type: str, ref: date, operator_id: int) -> AiSummary:
        start, end = period_range(period_type, ref)
        # 唯一键占位（upsert）
        row = self.db.execute(
            select(AiSummary).where(
                AiSummary.user_id == user_id, AiSummary.period_type == period_type,
                AiSummary.period_start == start,
            )
        ).scalar_one_or_none()
        if not row:
            row = AiSummary(user_id=user_id, period_type=period_type, period_start=start, period_end=end)
            self.db.add(row)
        row.status = "generating"
        row.error = None
        row.generated_by = operator_id
        self.db.commit()
        self.db.refresh(row)

        summary = self.personal.summary(user_id, period_type, ref)

        if not settings.AI_BASE_URL or not settings.AI_API_KEY:
            # 无 AI 配置 → 模板汇总
            row.content = self._template_summary(summary)
            row.model = "template"
            row.status = "generated"
            row.source_snapshot = self._snapshot(summary, "template")
        else:
            try:
                prompt = self._build_prompt(summary)
                row.content = self._call_llm(prompt)
                row.model = settings.AI_MODEL
                row.status = "generated"
                row.source_snapshot = self._snapshot(summary, settings.AI_MODEL)
            except Exception as e:  # noqa: BLE001
                row.content = self._template_summary(summary)
                row.model = "template"
                row.status = "failed"
                row.error = str(e)[:255]
                row.source_snapshot = self._snapshot(summary, "template")
        self.db.commit()
        self.db.refresh(row)
        return row

    def _snapshot(self, summary: dict, model: str) -> dict:
        items = []
        for p in summary["projects"]:
            for t in p["done_tasks"]:
                items.append({"type": "task", "id": t["id"], "excerpt": t["title"]})
            for pr in p["progresses"]:
                items.append({"type": "progress", "excerpt": f"[{pr['date']}] {pr['today_work'][:60]}"})
        return {
            "period": {"start": str(summary["period_start"]), "end": str(summary["period_end"])},
            "model": model, "prompt_version": "v1", "item_count": len(items), "items": items[:100],
        }

    def get(self, user_id: int, period_type: str, ref: date) -> AiSummary | None:
        start, _ = period_range(period_type, ref)
        return self.db.execute(
            select(AiSummary).where(
                AiSummary.user_id == user_id, AiSummary.period_type == period_type,
                AiSummary.period_start == start,
            )
        ).scalar_one_or_none()

    def edit(self, summary_id: int, edited_content: str, user: dict) -> AiSummary:
        from app.core.responses import ForbiddenError, NotFoundError
        row = self.db.get(AiSummary, summary_id)
        if not row:
            raise NotFoundError("总结不存在")
        if user["role"] != "admin" and row.user_id != user["user_id"]:
            raise ForbiddenError("仅本人或管理员可编辑")
        row.edited_content = edited_content
        row.status = "edited"
        self.db.commit()
        self.db.refresh(row)
        return row
