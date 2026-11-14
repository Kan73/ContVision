from ultralytics import YOLO

from .config import (
    MODEL_PATH,
    YOLO_IMAGE_SIZE,
    YOLO_CONFIDENCE,
    YOLO_IOU,
    YOLO_DEVICE
)


class ContainerDetector:

    def __init__(self, model_path=MODEL_PATH):

        if not model_path.exists():
            raise FileNotFoundError(
                f"YOLO model not found: {model_path}"
            )

        self.model = YOLO(str(model_path))

    def detect(self, image):

        results = self.model.predict(
            source=image,
            imgsz=YOLO_IMAGE_SIZE,
            conf=YOLO_CONFIDENCE,
            iou=YOLO_IOU,
            device=YOLO_DEVICE,
            verbose=False
        )

        if not results:
            return None

        result = results[0]

        if result.boxes is None or len(result.boxes) == 0:
            return None

        # Seleccionar la detección con mayor confianza
        best_index = result.boxes.conf.argmax().item()

        box = result.boxes.xyxy[best_index].cpu().numpy()

        confidence = float(
            result.boxes.conf[best_index].item()
        )

        x1, y1, x2, y2 = map(int, box)

        return {
            "bbox": (x1, y1, x2, y2),
            "confidence": confidence
        }