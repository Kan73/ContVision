
from src.contvision.models.YOLO.model import ContainerIDDetector


WEIGHTS = (
    "runs/container_id/"
    "yolo26s_baseline/weights/best.pt"
)

DATASET = "dataset/data.yaml"

IMAGE_SIZE = 640


# Cargar modelo
detector = ContainerIDDetector(WEIGHTS)


# Evaluar
metrics = detector.validate(

    data=DATASET,

    split="test",

    imgsz=IMAGE_SIZE,

    batch=8,

    device=0,

    plots=True,

    verbose=True
)


# Mostrar resultados
print("\n========== RESULTADOS ==========")

print("Precision:", metrics.box.mp)

print("Recall:", metrics.box.mr)

print("mAP50:", metrics.box.map50)

print("mAP50-95:", metrics.box.map)