"""Generación de imágenes (F6): proveedor opcional tipo OpenAI + avisos de privacidad.

Sin configurar, la app sigue 100% funcional (las herramientas LOCALES de fondo
no dependen de esto). La clave vive solo en variables de entorno.
"""
from __future__ import annotations

import base64
import io
import os
from typing import Any

from backend import config


def status() -> dict[str, Any]:
    configured = bool(config.IMAGEGEN_BASE_URL and config.IMAGEGEN_MODEL
                      and config.IMAGEGEN_API_KEY)
    return {
        "configured": configured,
        "provider": "openai-compatible",
        "base_url": config.IMAGEGEN_BASE_URL or None,
        "model": config.IMAGEGEN_MODEL or None,
        "privacy": "Al generar se envía el prompt al proveedor externo configurado. "
                   "Las herramientas de fondo locales no envían nada.",
    }


def generate_hero(prompt: str, width: int = 1024, height: int = 576) -> bytes:
    """Genera una imagen vía /images/generations (b64_json). Devuelve bytes PNG."""
    if not (config.IMAGEGEN_BASE_URL and config.IMAGEGEN_MODEL and config.IMAGEGEN_API_KEY):
        raise RuntimeError(
            "La generación con IA no está configurada. Define UIBINDER_IMAGEGEN_BASE_URL, "
            "UIBINDER_IMAGEGEN_MODEL y UIBINDER_IMAGEGEN_API_KEY (ver .env.example), o usa "
            "las herramientas de fondo locales.")
    import httpx

    payload = {
        "model": config.IMAGEGEN_MODEL,
        "prompt": prompt,
        "size": _nearest_size(width, height),
        "n": 1,
        "response_format": "b64_json",
    }
    with httpx.Client(timeout=120) as client:
        resp = client.post(
            f"{config.IMAGEGEN_BASE_URL.rstrip('/')}/images/generations",
            json=payload,
            headers={"Authorization": f"Bearer {config.IMAGEGEN_API_KEY}"},
        )
        resp.raise_for_status()
    data = resp.json()["data"][0]
    if "b64_json" in data:
        raw = base64.b64decode(data["b64_json"])
    else:  # algunas APIs devuelven url
        url = data["url"]
        with httpx.Client(timeout=120) as client:
            raw = client.get(url).content
    # normalizar a PNG re-codificando (acepta jpeg/webp del proveedor)
    from PIL import Image

    img = Image.open(io.BytesIO(raw))
    img.load()
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _nearest_size(w: int, h: int) -> str:
    """Las APIs suelen aceptar solo tamaños fijos; elige el más cercano horizontal."""
    ratios = {"1024x1024": 1.0, "1536x1024": 1.5, "1024x1536": 0.667, "1792x1024": 1.75}
    target = w / max(h, 1)
    return min(ratios, key=lambda k: abs(ratios[k] - target))


def apply_background_op(image_bytes: bytes, op: str, params: dict[str, Any]) -> bytes:
    """Herramientas LOCALES de fondo (sin nube, deterministas).

    ops: blur(sigma) · darken(factor) · lighten(factor) · color(hex) · gradient(hex1,hex2)
    """
    import cv2
    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    img.load()
    rgb = np.asarray(img.convert("RGB"))

    if op == "blur":
        sigma = max(1.0, float(params.get("sigma", 12)))
        k = int(sigma * 3) | 1
        out = cv2.GaussianBlur(rgb, (k, k), sigma)
    elif op in ("darken", "lighten"):
        factor = float(np.clip(params.get("factor", 0.5), 0.05, 0.95))
        out = (rgb * factor).astype(np.uint8) if op == "darken" \
            else np.clip(rgb + (255 - rgb) * factor, 0, 255).astype(np.uint8)
    elif op == "color":
        out = np.full_like(rgb, _hex_to_rgb(params.get("hex", "#101216")))
    elif op == "gradient":
        c1 = np.array(_hex_to_rgb(params.get("from", "#0c0e13")), dtype=float)
        c2 = np.array(_hex_to_rgb(params.get("to", "#1b2436")), dtype=float)
        grad = np.linspace(0, 1, rgb.shape[0])[:, None, None]
        out = (c1[None, None, :] * (1 - grad) + c2[None, None, :] * grad).astype(np.uint8)
        out = np.broadcast_to(out, rgb.shape).copy()
    else:
        raise ValueError(f"Operación de fondo desconocida: '{op}' "
                         "(blur, darken, lighten, color, gradient).")

    buf = io.BytesIO()
    Image.fromarray(out).save(buf, format="PNG")
    return buf.getvalue()


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"Color hexadecimal inválido: {hex_str}")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
