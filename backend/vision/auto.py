"""AutoVisionProvider — local first, escalate to remote if confidence is low.

Mode AUTO:
1. Run local heuristic
2. Calculate average confidence
3. If confidence < threshold, ATTEMPT remote provider
4. If remote improves result (more components or higher confidence), SELECT remote
5. Track usage and provenance
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
        doc_local, notes_local = local_provider.analyze(image)

        # Step 2: Calculate confidence
        confidences = [c.metadata.get("confidence", 0.5) for c in doc_local.components]
        avg_local_conf = sum(confidences) / len(confidences) if confidences else 0.0

        # Step 3: Attempt remote if needed
        remote_attempted = False
        remote_selected = False
        doc_remote = None
        notes_remote = {}
        avg_remote_conf = 0.0
        
        if avg_local_conf < self.threshold:
            remote_attempted = True
            try:
                remote = get_provider(self.remote_provider_name)
                doc_remote, notes_remote = remote.analyze(image)
                
                # Calculate remote confidence
                remote_confidences = [c.metadata.get("confidence", 0.5) for c in doc_remote.components]
                avg_remote_conf = sum(remote_confidences) / len(remote_confidences) if remote_confidences else 0.0
                
                # Step 4: Select remote only if it improves the result
                if avg_remote_conf > avg_local_conf or len(doc_remote.components) > len(doc_local.components):
                    remote_selected = True
                    doc = doc_remote
                    notes = notes_remote
                    avg_conf = avg_remote_conf
                else:
                    doc = doc_local
                    notes = notes_local
                    avg_conf = avg_local_conf
            except Exception as e:
                # Remote failed, keep local result
                notes = notes_local
                notes["remote_error"] = str(e)
                doc = doc_local
                avg_conf = avg_local_conf
        else:
            doc = doc_local
            notes = notes_local
            avg_conf = avg_local_conf

        latency = (time.time() - t_start) * 1000
        notes["latency_ms"] = latency
        notes["remote_attempted"] = remote_attempted
        notes["remote_selected"] = remote_selected
        notes["local_confidence"] = avg_local_conf
        notes["remote_confidence"] = avg_remote_conf if remote_attempted else 0.0
        notes["confidence_defaulted"] = False
        
        # Check if confidence was defaulted (no confidence in remote result)
        if remote_attempted and avg_remote_conf == 0.5:
            notes["confidence_defaulted"] = True

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
            fallback=notes.get("remote_selected", False),
        )
        provenance = VisionProvenance(
            provider=notes.get("provider", "auto"),
            model=notes.get("model", "heuristic+remote"),
            mode="AUTO",
            privacy="local first, remote only if low confidence",
            confidence_avg=notes.get("confidence_avg", 0.0),
            fallback_used=notes.get("remote_selected", False),
            warnings=["Remote confidence defaulted" if notes.get("confidence_defaulted", False) else ""]
        )

        return VisionResult(components=components, usage=usage, provenance=provenance)
