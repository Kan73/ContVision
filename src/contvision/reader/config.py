from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

MODEL_PATH = (
    ROOT
    / "runs"
    / "container_id"
    / "yolo26s_baseline"
    / "weights"
    / "best.pt"
)


# YOLO
YOLO_IMAGE_SIZE = 640
YOLO_CONFIDENCE = 0.25
YOLO_IOU = 0.45
YOLO_DEVICE = 0


# OCR
OCR_LANGUAGE = "en"
OCR_USE_GPU = False

# Preprocesamiento
OCR_TARGET_HEIGHT = 128
OCR_UPSCALE_FACTOR = 2