from __future__ import annotations

import json

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.pipeline_run import PipelineRun
from app.models.user import User
from app.pipeline.checkpointer import PipelineCheckpointer
from app.pipeline.nodes import approval_gate_node, auto_apply_node, fetch_jobs_node, rank_jobs_node, track_applications_node
from app.pipeline.state import ApplyIQState
from app.services.auto_apply_service import AutoApplyService
from app.services.cover_letter_service import CoverLetterService
from app.services.match_rank_service import MatchRankService
from app.services.scrape_service import ScrapeService
from app.services.vault_service import VaultService


class PipelineGraphRunner:
    def __init__(
        self,
        *,
        scrape_service: ScrapeService,
        match_service: MatchRankService,
        checkpointer: PipelineCheckpointer,
        encryption_service,
        cover_letter_service: CoverLetterService,
        auto_apply_service: AutoApplyService,
        vault_service: VaultService,
    ) -> None:
        self._scrape_service = scrape_service
        self._match_service = match_service
        self._checkpointer = checkpointer
        self._encryption_service = encryption_service
        self._cover_letter_service = cover_letter_service
        self._auto_apply_service = auto_apply_service
        self._vault_service = vault_service

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

        async def auto_apply_node_wrapper(state: ApplyIQState) -> ApplyIQState:
            return await auto_apply_node(
                state,
                session=session,
                pipeline_run=pipeline_run,
                user=user,
                auto_apply_service=self._auto_apply_service,
                vault_service=self._vault_service,
                encryption_service=self._encryption_service,
            )

        async def track_applications_wrapper(state: ApplyIQState) -> ApplyIQState:
            return await track_applications_node(
                state,
                session=session,
                pipeline_run=pipeline_run,
            )

        graph = StateGraph(ApplyIQState)
        graph.add_node("fetch_jobs_node", fetch_node)
        graph.add_node("rank_jobs_node", rank_node)
        graph.add_node("approval_gate_node", approval_node)
        graph.add_node("auto_apply_node", auto_apply_node_wrapper)
        graph.add_node("track_applications_node", track_applications_wrapper)

        graph.add_edge(START, "fetch_jobs_node")
        graph.add_edge("fetch_jobs_node", "rank_jobs_node")
        graph.add_edge("rank_jobs_node", "approval_gate_node")
        graph.add_edge("approval_gate_node", "auto_apply_node")
        graph.add_edge("auto_apply_node", "track_applications_node")
        graph.add_edge("track_applications_node", END)

        from langgraph.checkpoint.memory import MemorySaver

        # Compiling the single topology as designated by Audit Remediation Plan (Workstream A)
        # We use a MemorySaver locally to satisfy LangGraph's requirement for interrupt_before
        compiled_graph = graph.compile(checkpointer=MemorySaver(), interrupt_before=["auto_apply_node"])
        
        # run the graph, which will pause before auto_apply_node
        return await compiled_graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": pipeline_run.id}}
        )

    async def resume_after_approval(
        self,
        *,
        session: AsyncSession,
        pipeline_run: PipelineRun,
        user: User,
        run_id: str,
    ) -> ApplyIQState:
        checkpoint_state = await self._checkpointer.load(run_id)
        if checkpoint_state is None:
            if not pipeline_run.state_snapshot:
                raise ValueError("Pipeline checkpoint not found")
            decrypted_snapshot = self._encryption_service.decrypt_for_user(user.id, pipeline_run.state_snapshot)
            checkpoint_state = json.loads(decrypted_snapshot)

        approved_rows = list(
            await session.scalars(
                select(Application).where(
                    Application.pipeline_run_id == run_id,
                    Application.status == "approved",
                )
            )
        )
        checkpoint_state["approved_applications"] = [{"id": application.id, "status": application.status} for application in approved_rows]

        # Use the exact same node setup as above
        async def auto_apply(state: ApplyIQState) -> ApplyIQState:
            return await auto_apply_node(
                state,
                session=session,
                pipeline_run=pipeline_run,
                user=user,
                auto_apply_service=self._auto_apply_service,
                vault_service=self._vault_service,
                encryption_service=self._encryption_service,
            )

        async def track_applications(state: ApplyIQState) -> ApplyIQState:
            return await track_applications_node(
                state,
                session=session,
                pipeline_run=pipeline_run,
            )

        # But we only step the remaining part during resume.
        graph = StateGraph(ApplyIQState)
        graph.add_node("auto_apply_node", auto_apply)
        graph.add_node("track_applications_node", track_applications)
        graph.add_edge(START, "auto_apply_node")
        graph.add_edge("auto_apply_node", "track_applications_node")
        graph.add_edge("track_applications_node", END)
        state = await graph.compile().ainvoke(checkpoint_state)
        await self._checkpointer.delete(run_id)
        return state
