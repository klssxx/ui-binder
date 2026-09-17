"""AutoVisionProvider — local first, escalate to remote if confidence is low.

Mode AUTO:
1. Run local heuristic
2. Calculate average confidence
3. If confidence < threshold, escalate to remote provider
4. Track usage and provenance
"""
from __future__ import annotations

import os
import time
from typing import Any

from PIL import Image

from backend import config
from backend.schema.ui_schema import UIDocument
from backend.vision.contract import (
    DetectedComponent, VisionProvenance, VisionResult, VisionUsage,
)


class AutoVisionProvider:
    name = "auto"

    def __init__(self, threshold: float = 0.6, remote_provider_name: str = "remote"):
        self.threshold = threshold
        self.remote_provider_name = remote_provider_name

    def analyze(self, image: Image.Image) -> tuple[UIDocument, dict[str, Any]]:
        from backend.vision.provider import get_provider

        t_start = time.time()

        # Step 1: Local heuristic
        local_provider = get_provider("heuristic")
        doc, notes = local_provider.analyze(image)

        # Step 2: Calculate confidence
        confidences = [c.metadata.get("confidence", 0.5) for c in doc.components]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        # Step 3: Escalate if needed
        fallback_used = False
        if avg_conf < self.threshold:
            try:
                remote = get_provider(self.remote_provider_name)
                doc_remote, notes_remote = remote.analyze(image)
                # Use remote result if it has more components or higher confidence
                remote_confidences = [c.metadata.get("confidence", 0.5) for c in doc_remote.components]
                avg_remote = sum(remote_confidences) / len(remote_confidences) if remote_confidences else 0.0
                if avg_remote > avg_conf or len(doc_remote.components) > len(doc.components):
                    doc = doc_remote
                    notes = notes_remote
                    avg_conf = avg_remote
                    fallback_used = True
            except Exception as e:
                # Remote failed, keep local result
                notes["remote_error"] = str(e)

        latency = (time.time() - t_start) * 1000
        notes["latency_ms"] = latency
        notes["fallback_used"] = fallback_used
        notes["confidence_avg"] = avg_conf

        return doc, notes

    def analyze_rich(self, image: Image.Image) -> VisionResult:
        doc, notes = self.analyze(image)
        components = []
        for c in doc.components:
            dc = DetectedComponent(
                type=c.type,
                bbox={"x": c.bbox.x, "y": c.bbox.y, "width": c.bbox.width, "height": c.bbox.height},
                text=c.text,
                confidence=c.metadata.get("confidence", 0.5),
                role=c.metadata.get("role"),
                parent_hint=c.metadata.get("parent_hint"),
                group_hint=c.metadata.get("group_hint"),
                styles=c.metadata.get("styles", {}),
                state=c.metadata.get("state", {}),
                visual_semantic=c.metadata.get("visual_semantic"),
            )
            components.append(dc)

        usage = VisionUsage(
            provider=notes.get("provider", "auto"),
            model=notes.get("model", "heuristic+remote"),
            latency_ms=notes.get("latency_ms", 0),
            success=True,
            fallback=notes.get("fallback_used", False),
        )
        provenance = VisionProvenance(
            provider=notes.get("provider", "auto"),
            model=notes.get("model", "heuristic+remote"),
            mode="AUTO",
            privacy="local first, remote only if low confidence",
            confidence_avg=notes.get("confidence_avg", 0.0),
            fallback_used=notes.get("fallback_used", False),
        )

        return VisionResult(components=components, usage=usage, provenance=provenance)
