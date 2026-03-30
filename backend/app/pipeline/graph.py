from __future__ import annotations

import hashlib
import json
from time import perf_counter
from typing import Any, Awaitable, Callable

from cryptography.fernet import InvalidToken
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun
from app.models.application import Application
from app.models.job import Job
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

    async def _execute_with_agent_run(
        self,
        *,
        session: AsyncSession,
        pipeline_run_id: str,
        node_name: str,
        state: ApplyIQState,
        node_runner: Callable[[ApplyIQState], Awaitable[ApplyIQState]],
    ) -> ApplyIQState:
        started_at = perf_counter()
        input_hash = self._hash_payload(state)
        output_hash = input_hash
        token_count = 0
        execution_status = "success"
        execution_error: str | None = None

        try:
            next_state = await node_runner(state)
            output_hash = self._hash_payload(next_state)
            token_count = self._estimate_tokens(state, next_state)
            return next_state
        except Exception as error:
            execution_status = "failed"
            execution_error = str(error)
            output_hash = self._hash_payload({"error": str(error), "node": node_name})
            raise
        finally:
            latency_seconds = perf_counter() - started_at
            await self._persist_agent_run(
                session=session,
                pipeline_run_id=pipeline_run_id,
                node_name=node_name,
                input_hash=input_hash,
                output_hash=output_hash,
                token_count=token_count,
                latency_seconds=latency_seconds,
                execution_status=execution_status,
                execution_error=execution_error,
            )

    async def _persist_agent_run(
        self,
        *,
        session: AsyncSession,
        pipeline_run_id: str,
        node_name: str,
        input_hash: str,
        output_hash: str,
        token_count: int,
        latency_seconds: float,
        execution_status: str,
        execution_error: str | None,
    ) -> None:
        record = AgentRun(
            pipeline_run_id=pipeline_run_id,
            agent_name="pipeline_graph_agent",
            node=node_name,
            input_summary_hash=input_hash,
            output_summary_hash=output_hash,
            token_count=token_count,
            latency=latency_seconds,
            status=execution_status,
            error=execution_error,
        )
        try:
            session.add(record)
            await session.commit()
        except Exception:
            await session.rollback()

    def _hash_payload(self, payload: Any) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _estimate_tokens(self, input_payload: Any, output_payload: Any) -> int:
        input_len = len(json.dumps(input_payload, sort_keys=True, default=str, ensure_ascii=True))
        output_len = len(json.dumps(output_payload, sort_keys=True, default=str, ensure_ascii=True))
        return max(1, (input_len + output_len) // 4)

    def _build_graph(
        self,
        *,
        session: AsyncSession,
        pipeline_run: PipelineRun,
        user: User,
    ):
        pipeline_run_id = pipeline_run.id

        async def fetch_node(state: ApplyIQState) -> ApplyIQState:
            return await self._execute_with_agent_run(
                session=session,
                pipeline_run_id=pipeline_run_id,
                node_name="fetch_jobs_node",
                state=state,
                node_runner=lambda current_state: fetch_jobs_node(
                    current_state,
                    session=session,
                    scrape_service=self._scrape_service,
                    pipeline_run=pipeline_run,
                ),
            )

        async def rank_node(state: ApplyIQState) -> ApplyIQState:
            return await self._execute_with_agent_run(
                session=session,
                pipeline_run_id=pipeline_run_id,
                node_name="rank_jobs_node",
                state=state,
                node_runner=lambda current_state: rank_jobs_node(
                    current_state,
                    session=session,
                    match_service=self._match_service,
                    pipeline_run=pipeline_run,
                    user=user,
                ),
            )

        async def approval_node(state: ApplyIQState) -> ApplyIQState:
            return await self._execute_with_agent_run(
                session=session,
                pipeline_run_id=pipeline_run_id,
                node_name="approval_gate_node",
                state=state,
                node_runner=lambda current_state: approval_gate_node(
                    current_state,
                    session=session,
                    pipeline_run=pipeline_run,
                    user=user,
                    checkpointer=self._checkpointer,
                    encryption_service=self._encryption_service,
                    cover_letter_service=self._cover_letter_service,
                ),
            )

        async def auto_apply_node_wrapper(state: ApplyIQState) -> ApplyIQState:
            return await self._execute_with_agent_run(
                session=session,
                pipeline_run_id=pipeline_run_id,
                node_name="auto_apply_node",
                state=state,
                node_runner=lambda current_state: auto_apply_node(
                    current_state,
                    session=session,
                    pipeline_run=pipeline_run,
                    user=user,
                    auto_apply_service=self._auto_apply_service,
                    vault_service=self._vault_service,
                    encryption_service=self._encryption_service,
                ),
            )

        async def track_applications_wrapper(state: ApplyIQState) -> ApplyIQState:
            return await self._execute_with_agent_run(
                session=session,
                pipeline_run_id=pipeline_run_id,
                node_name="track_applications_node",
                state=state,
                node_runner=lambda current_state: track_applications_node(
                    current_state,
                    session=session,
                    pipeline_run=pipeline_run,
                ),
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

        return graph.compile(checkpointer=self._checkpointer, interrupt_before=["auto_apply_node"])

    async def run_until_approval(
        self,
        *,
        session: AsyncSession,
        pipeline_run: PipelineRun,
        user: User,
        initial_state: ApplyIQState,
    ) -> ApplyIQState:
        pipeline_run_id = pipeline_run.id
        compiled_graph = self._build_graph(session=session, pipeline_run=pipeline_run, user=user)
        result = await compiled_graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": pipeline_run_id}},
        )
        return _strip_interrupt(result)

    async def resume_after_approval(
        self,
        *,
        session: AsyncSession,
        pipeline_run: PipelineRun,
        user: User,
        run_id: str,
    ) -> ApplyIQState:
        pipeline_run_id = pipeline_run.id
        compiled_graph = self._build_graph(session=session, pipeline_run=pipeline_run, user=user)
        try:
            result = await compiled_graph.ainvoke(
                Command(resume=True),
                config={"configurable": {"thread_id": run_id}},
            )
            await self._checkpointer.delete(run_id)
            return _strip_interrupt(result)
        except Exception:
            checkpoint_state = await self._checkpointer.load(run_id)
            if checkpoint_state is None:
                checkpoint_state = await self._rebuild_resume_state(
                    session=session,
                    pipeline_run=pipeline_run,
                    user=user,
                )
            else:
                try:
                    if pipeline_run.state_snapshot:
                        decrypted_snapshot = self._encryption_service.decrypt_for_user(user.id, pipeline_run.state_snapshot)
                        snapshot_state = json.loads(decrypted_snapshot)
                        if isinstance(snapshot_state, dict):
                            checkpoint_state = {**checkpoint_state, **snapshot_state}
                except InvalidToken:
                    checkpoint_state = await self._rebuild_resume_state(
                        session=session,
                        pipeline_run=pipeline_run,
                        user=user,
                    )

            approved_rows = list(
                await session.scalars(
                    select(Application).where(
                        Application.pipeline_run_id == run_id,
                        Application.status == "approved",
                    )
                )
            )
            checkpoint_state["approved_applications"] = [
                {"id": application.id, "status": application.status}
                for application in approved_rows
            ]

            async def auto_apply(state: ApplyIQState) -> ApplyIQState:
                return await self._execute_with_agent_run(
                    session=session,
                    pipeline_run_id=pipeline_run_id,
                    node_name="auto_apply_node",
                    state=state,
                    node_runner=lambda current_state: auto_apply_node(
                        current_state,
                        session=session,
                        pipeline_run=pipeline_run,
                        user=user,
                        auto_apply_service=self._auto_apply_service,
                        vault_service=self._vault_service,
                        encryption_service=self._encryption_service,
                    ),
                )

            async def track_applications(state: ApplyIQState) -> ApplyIQState:
                return await self._execute_with_agent_run(
                    session=session,
                    pipeline_run_id=pipeline_run_id,
                    node_name="track_applications_node",
                    state=state,
                    node_runner=lambda current_state: track_applications_node(
                        current_state,
                        session=session,
                        pipeline_run=pipeline_run,
                    ),
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

    async def _rebuild_resume_state(
        self,
        *,
        session: AsyncSession,
        pipeline_run: PipelineRun,
        user: User,
    ) -> ApplyIQState:
        applications = list(
            await session.scalars(
                select(Application).where(
                    Application.pipeline_run_id == pipeline_run.id,
                    Application.user_id == user.id,
                )
            )
        )
        approved_applications = [
            {"id": application.id, "status": application.status}
            for application in applications
            if application.status == "approved"
        ]
        pending_approvals: list[dict[str, Any]] = []
        for application in applications:
            if application.status != "pending_approval":
                continue
            job = await session.scalar(select(Job).where(Job.id == application.job_id))
            pending_approvals.append(
                {
                    "id": application.id,
                    "job_id": application.job_id,
                    "title": job.title if job else "Unknown Job",
                    "company_name": job.company_name if job else "Unknown Company",
                    "match_score": float(application.match_score),
                    "cover_letter_text": application.cover_letter_text,
                    "tone": application.cover_letter_tone,
                    "word_count": application.cover_letter_word_count,
                    "cover_letter_version": application.cover_letter_version,
                    "status": application.status,
                }
            )
        search_preferences = None
        if user.search_preferences is not None:
            search_preferences = {
                "target_roles": user.search_preferences.target_roles,
                "preferred_locations": user.search_preferences.preferred_locations,
                "remote_preference": user.search_preferences.remote_preference,
                "salary_min": user.search_preferences.salary_min,
                "salary_max": user.search_preferences.salary_max,
                "currency": user.search_preferences.currency,
                "excluded_companies": user.search_preferences.excluded_companies,
                "seniority_level": user.search_preferences.seniority_level,
                "is_active": user.search_preferences.is_active,
            }

        resume = None
        if user.resume_profile is not None:
            resume = user.resume_profile.parsed_profile

        return {
            "run_id": pipeline_run.id,
            "user_id": user.id,
            "target_role": search_preferences["target_roles"][0] if search_preferences and search_preferences["target_roles"] else "",
            "location": search_preferences["preferred_locations"][0] if search_preferences and search_preferences["preferred_locations"] else None,
            "limit_per_source": 10,
            "sources": ["linkedin", "indeed", "remotive"],
            "raw_jobs_count": 0,
            "deduplicated_jobs_count": 0,
            "ranked_jobs": [],
            "pending_approvals": pending_approvals,
            "approved_applications": approved_applications,
            "applied_applications": [
                {"id": application.id, "status": application.status}
                for application in applications
                if application.status == "applied"
            ],
            "current_node": "approval_gate_node",
            "resume": resume,
            "search_preferences": search_preferences,
            "raw_jobs": [],
            "deduplicated_jobs": [],
            "errors": [],
        }


def _strip_interrupt(result):
    if isinstance(result, dict) and "__interrupt__" in result:
        return {key: value for key, value in result.items() if key != "__interrupt__"}
    return result
