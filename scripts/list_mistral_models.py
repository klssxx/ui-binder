"""List available Mistral models."""
import os
import httpx
from pathlib import Path

def main():
    api_key = os.environ.get("HERMES_CUSTOM_API_MISTRAL_AI_API_KEY", "")
    base_url = "https://api.mistral.ai/v1"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    resp = httpx.get(f"{base_url}/models", headers=headers, timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        for m in data.get("data", []):
            if "pixtral" in m.get("id", "").lower() or "ministral" in m.get("id", "").lower() or "multimodal" in m.get("id", "").lower():
                print(f"  {m['id']}")
    else:
        print(resp.text[:500])

if __name__ == "__main__":
    main()
