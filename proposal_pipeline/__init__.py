"""Proposal generation pipeline using direct OpenAI SDK calls."""

from .pipeline import ProposalPipeline
from .models import ProposalPackage

__all__ = ["ProposalPipeline", "ProposalPackage"]
