"""Vision model abstraction.

Two providers ship with the MVP:

* ``openai_compatible`` — any OpenAI-compatible multimodal chat endpoint
  (OpenAI, Azure, local vLLM, etc.). Claude works too via an OpenAI-compatible
  gateway; swap VISION_BASE_URL/VISION_MODEL.
* ``stub`` — a deterministic, clearly-marked offline analyzer used when no
  VISION_API_KEY is configured, so the whole pipeline runs with zero
  credentials. It NEVER fabricates a diagnosis: it returns conservative,
  caption-aware, low-confidence output that always needs human review.

A future agave-specific YOLO/classifier can implement the same
``analyze(image_url, caption, ...)`` -> dict contract and drop in here.
"""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.agents.prompts import HERMES_SYSTEM_PROMPT, build_user_prompt
from app.config import settings

logger = logging.getLogger("agave.vision")


class VisionClient(ABC):
    @abstractmethod
    def analyze(
        self,
        image_url: str,
        caption: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> dict:
        """Return a raw dict that will be validated against HermesOutput."""

    @property
    def model_name(self) -> str:
        return "unknown"


def _extract_json(text: str) -> dict:
    """Best-effort extraction of a JSON object from an LLM response."""
    text = text.strip()
    # Strip code fences if present.
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


class OpenAICompatibleVisionClient(VisionClient):
    def __init__(self):
        self.base_url = settings.vision_base_url.rstrip("/")
        self.api_key = settings.vision_api_key
        self.model = settings.vision_model

    @property
    def model_name(self) -> str:
        return self.model

    def analyze(self, image_url, caption=None, latitude=None, longitude=None) -> dict:
        user_prompt = build_user_prompt(caption, latitude, longitude)
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": HERMES_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return _extract_json(content)


class StubVisionClient(VisionClient):
    """Offline analyzer. Conservative by design — always needs human review."""

    KEYWORDS = {
        "amarill": ("yellowing", "possible nutrient/water stress (suspected)"),
        "yellow": ("yellowing", "possible nutrient/water stress (suspected)"),
        "mancha": ("spots", "leaf spotting (suspected)"),
        "spot": ("spots", "leaf spotting (suspected)"),
        "plaga": ("pest_damage", "possible pest pressure (suspected)"),
        "pest": ("pest_damage", "possible pest pressure (suspected)"),
        "picudo": ("pest_damage", "possible agave weevil activity (suspected)"),
        "seca": ("drought_stress", "drought / water stress (suspected)"),
        "drought": ("drought_stress", "drought / water stress (suspected)"),
        "podrid": ("disease_suspected", "possible rot / disease (suspected)"),
        "rot": ("disease_suspected", "possible rot / disease (suspected)"),
        "maleza": ("weed_pressure", "weed pressure (suspected)"),
        "weed": ("weed_pressure", "weed pressure (suspected)"),
    }

    @property
    def model_name(self) -> str:
        return "stub-offline-analyzer-v1"

    def analyze(self, image_url, caption=None, latitude=None, longitude=None) -> dict:
        cap = (caption or "").lower()
        condition, issue = "unknown", None
        for kw, (cond, iss) in self.KEYWORDS.items():
            if kw in cap:
                condition, issue = cond, iss
                break

        urgent = any(
            t in cap
            for t in ["urgent", "urgente", "riesgo alto", "plaga fuerte", "se está extendiendo"]
        )
        severity = "high" if urgent else ("medium" if condition != "unknown" else "unknown")

        missing = []
        if latitude is None or longitude is None:
            missing.append("location")
        if not caption:
            missing.append("caption")

        tasks = []
        if condition != "unknown":
            tasks.append(
                {
                    "title": f"Validate possible {condition.replace('_', ' ')}",
                    "priority": "high" if urgent else "medium",
                    "due_in_days": 1 if urgent else 3,
                    "description": "Human agronomist to confirm the suspected condition in the field.",
                    "needs_approval": False,
                }
            )
        tasks.append(
            {
                "title": "Reinspect zone in 7 days",
                "priority": "medium",
                "due_in_days": 7,
                "description": "Follow-up inspection to track progression.",
                "needs_approval": False,
            }
        )

        return {
            "image_type": "unknown",
            "plant_condition": condition,
            "suspected_issue": issue,
            "diagnosis": issue or "Inconclusive — needs human review",
            "severity": severity,
            "confidence": 0.35 if condition != "unknown" else 0.2,
            "visible_symptoms": [issue] if issue else [],
            "agronomic_summary": (
                "[OFFLINE STUB ANALYSIS — no vision model configured] "
                + (
                    f"Caption suggests {condition.replace('_', ' ')}. "
                    if condition != "unknown"
                    else "Unable to assess without a vision model. "
                )
                + "Human agronomist review required."
            ),
            "recommended_next_step": (
                "Configure a vision model (VISION_API_KEY) and/or have an "
                "agronomist inspect the plant; take a close-up of affected tissue."
            ),
            "recommended_tasks": tasks,
            "needs_human_review": True,
            "escalation_recommended": urgent,
            "escalation_reason": "Caption contains urgent terms" if urgent else None,
            "missing_fields": missing,
        }


def get_vision_client() -> VisionClient:
    provider = settings.vision_provider.lower()
    if provider == "openai_compatible" and settings.vision_api_key:
        return OpenAICompatibleVisionClient()
    if provider == "openai_compatible" and not settings.vision_api_key:
        logger.warning("VISION_API_KEY not set; using offline stub vision client")
    return StubVisionClient()
