from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.pipeline_run import PipelineRun
from app.models.user import User
from app.pipeline.checkpointer import PipelineCheckpointer
from app.pipeline.nodes import approval_gate_node, auto_apply_node, fetch_jobs_node, rank_jobs_node, track_applications_node
from app.pipeline.state import ApplyIQState
from app.services.cover_letter_service import CoverLetterService
from app.services.match_rank_service import MatchRankService
from app.services.scrape_service import ScrapeService


class PipelineGraphRunner:
    def __init__(
        self,
        *,
        scrape_service: ScrapeService,
        match_service: MatchRankService,
        checkpointer: PipelineCheckpointer,
        encryption_service,
        cover_letter_service: CoverLetterService,
    ) -> None:
        self._scrape_service = scrape_service
        self._match_service = match_service
        self._checkpointer = checkpointer
        self._encryption_service = encryption_service
        self._cover_letter_service = cover_letter_service

    async def run_until_approval(
        self,
        *,
        session: AsyncSession,
        pipeline_run: PipelineRun,
        user: User,
        initial_state: ApplyIQState,
    ) -> ApplyIQState:
        async def fetch_node(state: ApplyIQState) -> ApplyIQState:
            return await fetch_jobs_node(
                state,
                session=session,
                scrape_service=self._scrape_service,
                pipeline_run=pipeline_run,
            )

        async def rank_node(state: ApplyIQState) -> ApplyIQState:
            return await rank_jobs_node(
                state,
                session=session,
                match_service=self._match_service,
                pipeline_run=pipeline_run,
                user=user,
            )

        async def approval_node(state: ApplyIQState) -> ApplyIQState:
            return await approval_gate_node(
                state,
                session=session,
                pipeline_run=pipeline_run,
                user=user,
                checkpointer=self._checkpointer,
                encryption_service=self._encryption_service,
                cover_letter_service=self._cover_letter_service,
            )

        graph = StateGraph(ApplyIQState)
        graph.add_node("fetch_jobs_node", fetch_node)
        graph.add_node("rank_jobs_node", rank_node)
        graph.add_node("approval_gate_node", approval_node)
        graph.add_edge(START, "fetch_jobs_node")
        graph.add_edge("fetch_jobs_node", "rank_jobs_node")
        graph.add_edge("rank_jobs_node", "approval_gate_node")
        graph.add_edge("approval_gate_node", END)
        return await graph.compile().ainvoke(initial_state)

    async def resume_after_approval(
        self,
        *,
        session: AsyncSession,
        pipeline_run: PipelineRun,
        run_id: str,
    ) -> ApplyIQState:
        checkpoint_state = await self._checkpointer.load(run_id)
        if checkpoint_state is None:
            raise ValueError("Pipeline checkpoint not found")

        approved_rows = list(
            await session.scalars(
                select(Application).where(
                    Application.pipeline_run_id == run_id,
                    Application.status == "approved",
                )
            )
        )
        checkpoint_state["approved_applications"] = [{"id": application.id, "status": application.status} for application in approved_rows]

        async def auto_apply(state: ApplyIQState) -> ApplyIQState:
            return await auto_apply_node(
                state,
                session=session,
                pipeline_run=pipeline_run,
            )

        async def track_applications(state: ApplyIQState) -> ApplyIQState:
            return await track_applications_node(
                state,
                session=session,
                pipeline_run=pipeline_run,
            )

        graph = StateGraph(ApplyIQState)
        graph.add_node("auto_apply_node", auto_apply)
        graph.add_node("track_applications_node", track_applications)
        graph.add_edge(START, "auto_apply_node")
        graph.add_edge("auto_apply_node", "track_applications_node")
        graph.add_edge("track_applications_node", END)
        state = await graph.compile().ainvoke(checkpoint_state)
        await self._checkpointer.delete(run_id)
        return state
