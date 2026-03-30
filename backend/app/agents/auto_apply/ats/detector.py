from __future__ import annotations

from app.agents.auto_apply.ats.base import ATSStrategy
from app.agents.auto_apply.ats.direct import DirectApplyStrategy
from app.agents.auto_apply.ats.greenhouse import GreenhouseATSStrategy
from app.agents.auto_apply.ats.lever import LeverATSStrategy


def strategy_for_provider(ats_provider: str) -> ATSStrategy:
    normalized = ats_provider.strip().lower()
    if normalized == "greenhouse":
        return GreenhouseATSStrategy()
    if normalized == "lever":
        return LeverATSStrategy()
    return DirectApplyStrategy()

