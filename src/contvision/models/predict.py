
import cv2
from pathlib import Path

from src.contvision.models.YOLO.model import ContainerIDDetector


# ==========================================
# CONFIGURACION
# ==========================================

WEIGHTS = (
    "runs/container_id/"
    "yolo26s_baseline/weights/best.pt"
)

IMAGE_PATH = "test_container.jpg"

OUTPUT_DIR = Path("outputs")

OUTPUT_DIR.mkdir(exist_ok=True)


# ==========================================
# CARGAR MODELO
# ==========================================

detector = ContainerIDDetector(WEIGHTS)


# ==========================================
# CARGAR IMAGEN
# ==========================================

image = cv2.imread(IMAGE_PATH)

if image is None:
    raise FileNotFoundError(IMAGE_PATH)


# ==========================================
# DETECCION
# ==========================================

results = detector.predict(

    image,

    conf=0.25,

    imgsz=640
)


# ==========================================
# EXTRAER IDENTIFICADORES
# ==========================================

for result_idx, result in enumerate(results):

    for box_idx, box in enumerate(result.boxes):

        x1, y1, x2, y2 = map(
            int,
            box.xyxy[0].tolist()
        )

        confidence = float(box.conf[0])

        # Recorte
        roi = image[y1:y2, x1:x2]

        # Guardar recorte
        crop_path = (
            OUTPUT_DIR /
            f"container_id_{result_idx}_{box_idx}.jpg"
        )

        cv2.imwrite(str(crop_path), roi)

        # Dibujar deteccion
        cv2.rectangle(
            image,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2
        )

        print(
            f"ID detectado: "
            f"confidence={confidence:.3f}"
        )

# Guardar imagen completa
cv2.imwrite(
    str(OUTPUT_DIR / "detection_result.jpg"),
    image
)

print("\nInferencia finalizada.")
