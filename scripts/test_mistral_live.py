"""Test real Mistral vision provider against test image."""
import os
import sys
import time
from pathlib import Path

# Configure Mistral with working model
os.environ["UIBINDER_VISION_BASE_URL"] = "https://api.mistral.ai/v1"
os.environ["UIBINDER_VISION_MODEL"] = "ministral-8b-latest"
os.environ["UIBINDER_VISION_API_KEY"] = os.environ.get("HERMES_CUSTOM_API_MISTRAL_AI_API_KEY", "")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image
from backend.schema.ui_schema import UIDocument

def validate_uidocument(doc):
    """Validate UIDocument structure."""
    errors = []
    if not doc.components:
        errors.append("No components")
    for c in doc.components:
        if c.type not in {"container", "panel", "card", "text", "heading", "button", "input", "textarea", "select", "checkbox", "radio", "image", "icon", "table", "chart", "tabs", "sidebar", "navbar", "modal", "divider", "custom"}:
            errors.append(f"Unknown type: {c.type}")
        if c.bbox.width <= 0 or c.bbox.height <= 0:
            errors.append(f"Invalid bbox for {c.id}")
    return errors

def run_provider(name, image_path):
    """Run a single provider and collect results."""
    from backend.vision.provider import get_provider
    
    img = Image.open(image_path)
    provider = get_provider(name)
    
    t0 = time.time()
    try:
        doc, notes = provider.analyze(img)
        latency = (time.time() - t0) * 1000
        errors = validate_uidocument(doc)
        
        components = []
        for c in doc.components:
            comp = {
                "id": c.id,
                "type": c.type,
                "parent": c.parent_id,
                "text": c.text,
                "bbox": {"x": c.bbox.x, "y": c.bbox.y, "w": c.bbox.width, "h": c.bbox.height},
                "confidence": c.metadata.get("confidence", 0),
                "role": c.metadata.get("role"),
                "styles": c.metadata.get("styles", {}),
            }
            components.append(comp)
        
        # Calculate hierarchy depth
        hierarchy = {}
        for c in doc.components:
            if c.parent_id not in hierarchy:
                hierarchy[c.parent_id] = []
            hierarchy[c.parent_id].append(c.id)
        
        return {
            "provider": name,
            "components": components,
            "component_count": len(doc.components),
            "types": list(set(c.type for c in doc.components)),
            "avg_confidence": sum(c.metadata.get("confidence", 0.5) for c in doc.components) / max(1, len(doc.components)),
            "latency_ms": round(latency, 1),
            "hierarchy": {k: len(v) for k, v in hierarchy.items()},
            "errors": errors,
            "success": True,
        }
    except Exception as e:
        latency = (time.time() - t0) * 1000
        return {
            "provider": name,
            "error": str(e),
            "latency_ms": round(latency, 1),
            "success": False,
        }

def main():
    image_path = PROJECT_ROOT / "tests" / "fixtures" / "test_ui.png"
    if not image_path.exists():
        print(f"ERROR: Test image not found: {image_path}")
        return
    
    print(f"Test image: {image_path}")
    print(f"Image size: {Image.open(image_path).size}")
    print()
    
    # Run each provider
    for name in ["heuristic", "mistral", "auto"]:
        print(f"{'='*60}")
        print(f"Provider: {name.upper()}")
        print(f"{'='*60}")
        result = run_provider(name, str(image_path))
        
        if result["success"]:
            print(f"  Components: {result['component_count']}")
            print(f"  Types: {result['types']}")
            print(f"  Avg Confidence: {result['avg_confidence']:.3f}")
            print(f"  Latency: {result['latency_ms']}ms")
            print(f"  Hierarchy: {result['hierarchy']}")
            if result["errors"]:
                print(f"  ERRORS: {result['errors']}")
            for c in result["components"][:5]:
                print(f"    - {c['type']:12s} {c['id']:20s} conf={c['confidence']:.2f} text={c['text']}")
        else:
            print(f"  FAILED: {result['error']}")
            print(f"  Latency: {result['latency_ms']}ms")
        print()

if __name__ == "__main__":
    main()
