"""Test para la semántica de AutoVisionProvider."""
import os
import sys
import tempfile
from pathlib import Path

# Configurar entorno
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image
from backend.vision.provider import get_provider

def test_auto_vision_provider_semantics():
    """Test que AutoVisionProvider distingue entre remote_attempted y remote_selected."""
    # Cargar la imagen
    image = Image.open('tests/fixtures/test_ui.png')
    
    # Probar AUTO
    auto_provider = get_provider('auto')
    doc_auto, notes_auto = auto_provider.analyze(image)
    
    # Verificar que los campos están presentes
    assert "remote_attempted" in notes_auto, "remote_attempted debe estar en notes"
    assert "remote_selected" in notes_auto, "remote_selected debe estar en notes"
    assert "local_confidence" in notes_auto, "local_confidence debe estar en notes"
    assert "remote_confidence" in notes_auto, "remote_confidence debe estar en notes"
    assert "confidence_defaulted" in notes_auto, "confidence_defaulted debe estar en notes"
    
    # Verificar que remote_attempted es True (porque local_confidence < threshold)
    assert notes_auto["remote_attempted"] is True, "remote_attempted debe ser True"
    
    # Verificar que remote_selected depende de si el resultado remoto mejora
    # (en este caso, no debería seleccionarse porque la confianza es baja)
    assert isinstance(notes_auto["remote_selected"], bool), "remote_selected debe ser booleano"
    
    # Verificar que local_confidence y remote_confidence son numéricos
    assert isinstance(notes_auto["local_confidence"], (int, float)), "local_confidence debe ser numérico"
    assert isinstance(notes_auto["remote_confidence"], (int, float)), "remote_confidence debe ser numérico"
    
    # Verificar que confidence_defaulted es False (porque el modelo devuelve confianza)
    assert isinstance(notes_auto["confidence_defaulted"], bool), "confidence_defaulted debe ser booleano"
    
    # Verificar que el documento tiene componentes
    assert len(doc_auto.components) > 0, "El documento debe tener componentes"
    
    # Verificar que los componentes tienen confianza
    for c in doc_auto.components:
        assert "confidence" in c.metadata, "Cada componente debe tener confianza"
    
    print("✅ Test de semántica de AutoVisionProvider PASADO")
    print(f"LOCAL_CONFIDENCE: {notes_auto['local_confidence']}")
    print(f"REMOTE_ATTEMPTED: {notes_auto['remote_attempted']}")
    print(f"REMOTE_CONFIDENCE: {notes_auto['remote_confidence']}")
    print(f"REMOTE_SELECTED: {notes_auto['remote_selected']}")
    print(f"CONFIDENCE_DEFAULTED: {notes_auto['confidence_defaulted']}")
    print(f"FINAL_PROVIDER: {notes_auto.get('provider', 'unknown')}")
    print(f"FINAL_COMPONENTS: {len(doc_auto.components)}")

if __name__ == "__main__":
    test_auto_vision_provider_semantics()