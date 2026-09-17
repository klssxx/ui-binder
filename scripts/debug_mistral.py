"""Debug Mistral API response."""
import os
import sys
import httpx
import base64
import io
from pathlib import Path
from PIL import Image

os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def main():
    api_key = os.environ.get("HERMES_CUSTOM_API_MISTRAL_AI_API_KEY", "")
    base_url = "https://api.mistral.ai/v1"
    model = "ministral-8b-latest"
    
    img_path = PROJECT_ROOT / "tests" / "fixtures" / "test_ui.png"
    img = Image.open(img_path)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": "Describe briefly"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]},
        ],
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        resp = httpx.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=30)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text[:1000]}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    main()
