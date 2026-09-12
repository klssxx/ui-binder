"""OCR + borrado de texto (F3): motor real sobre imágenes sintéticas."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from backend.vision import ocr


def make_text_image() -> Image.Image:
    img = Image.new("RGB", (640, 180), "#101216")
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 44)
    d.text((40, 60), "GENERAR INFORME", font=font, fill="#ffffff")
    return img


def test_ocr_available_and_reads():
    ok, detail = ocr.ocr_available()
    assert ok, f"OCR debe estar disponible: {detail}"
    lines = ocr.read_lines(make_text_image())
    assert lines, "debe encontrar al menos una línea"
    joined = " ".join(l["text"].upper() for l in lines)
    assert "GENERAR" in joined
    top = max(lines, key=lambda l: l["confidence"])
    assert top["confidence"] > 0.8
    assert top["color"].lower() in ("#ffffff", "#fefefe", "#f7f7f7") or \
        top["color"].upper().startswith("#F") or top["color"].upper().startswith("#E"), \
        f"color de tinta clara esperado, no el fondo: {top['color']}"
    assert 20 <= top["fontSize"] <= 60


def test_ocr_bbox_crop_restricts_results():
    img = make_text_image()
    full = ocr.read_lines(img)
    assert full
    # caja fuera del texto → sin líneas
    empty = ocr.read_lines(img, {"x": 0, "y": 0, "width": 30, "height": 20})
    assert empty == []


def test_erase_regions_leaves_clean_background():
    img = make_text_image()
    line = ocr.read_lines(img)[0]
    cleaned = ocr.erase_regions(img, [line["bbox"]])
    arr = np.asarray(cleaned.convert("RGB"))
    region = arr[int(line["bbox"]["y"]):int(line["bbox"]["y"] + line["bbox"]["height"]),
                 int(line["bbox"]["x"]):int(line["bbox"]["x"] + line["bbox"]["width"])]
    # la zona del texto debe volver a ~fondo (varianza muy baja, sin píxeles blancos)
    assert float(region.mean()) < 60  # fondo #101216 ≈ 21
    assert float((region > 180).mean()) < 0.01  # casi sin tinta blanca restante
    # fuera de la caja no se toca (compara con original en una esquina)
    orig = np.asarray(img.convert("RGB"))
    assert np.array_equal(arr[150:, :40], orig[150:, :40])


def test_erase_noop_without_boxes():
    img = make_text_image()
    out = ocr.erase_regions(img, [])
    assert np.array_equal(np.asarray(out), np.asarray(img))


def test_api_ocr_endpoints(client, golden_png, sample_app_dir):
    ws = client.post("/api/workspaces", json={"name": "ocr"}).json()
    with open(golden_png, "rb") as fh:
        client.post(f"/api/workspaces/{ws['id']}/images",
                    files={"file": ("reference.png", fh, "image/png")})
    status = client.get("/api/ocr/status").json()
    assert status["available"] is True

    r = client.post(f"/api/workspaces/{ws['id']}/ocr",
                    json={"bbox": {"x": 280, "y": 120, "width": 660, "height": 120}})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert "confidence" in body["lines"][0]

    # borrar una caja pequeña y recuperar la imagen limpia
    line = body["lines"][0]["bbox"]
    r2 = client.post(f"/api/workspaces/{ws['id']}/ocr/erase", json={"bboxes": [line]})
    assert r2.status_code == 200
    rec = r2.json()["image"]
    assert rec["role"] == "cleaned" and rec["format"] == "PNG"
    served = client.get(f"/api/images/{rec['id']}/file")
    assert served.status_code == 200
    assert served.content[:4] == b"\x89PNG"

    # sin imagen → 409 honesto
    ws2 = client.post("/api/workspaces", json={"name": "ocr2"}).json()
    assert client.post(f"/api/workspaces/{ws2['id']}/ocr",
                       json={"bbox": None}).status_code == 409
    # sin cajas → 422
    assert client.post(f"/api/workspaces/{ws['id']}/ocr/erase",
                       json={"bboxes": []}).status_code == 422
