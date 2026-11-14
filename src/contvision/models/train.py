
import torch
from pathlib import Path

from src.contvision.models.YOLO.model import ContainerIDDetector


# ==========================================
# CONFIGURACION
# ==========================================

DATASET = "dataset/data.yaml"

MODEL = "yolo26s.pt"

EPOCHS = 100

IMAGE_SIZE = 640

BATCH_SIZE = 8

WORKERS = 4

DEVICE = 0 if torch.cuda.is_available() else "cpu"

PROJECT = "runs/container_id"

EXPERIMENT_NAME = "yolo26s_baseline"


# ==========================================
# COMPROBAR GPU
# ==========================================

print("\n========== HARDWARE ==========")

print("CUDA disponible:", torch.cuda.is_available())

if torch.cuda.is_available():

    print("GPU:", torch.cuda.get_device_name(0))

    print(
        "VRAM:",
        round(
            torch.cuda.get_device_properties(0).total_memory / 1024**3,
            2
        ),
        "GB"
    )


# ==========================================
# CARGAR MODELO
# ==========================================

print("\n========== CARGANDO MODELO ==========")

detector = ContainerIDDetector(MODEL)


# ==========================================
# ENTRENAMIENTO
# ==========================================

print("\n========== INICIANDO ENTRENAMIENTO ==========")

results = detector.train(

    data=DATASET,

    # Training
    epochs=EPOCHS,
    imgsz=IMAGE_SIZE,
    batch=BATCH_SIZE,
    device=DEVICE,
    workers=WORKERS,

    # Fine tuning
    pretrained=True,
    optimizer="auto",
    patience=20,

    # Augmentations
    degrees=5.0,
    translate=0.05,
    scale=0.2,

    fliplr=0.0,
    flipud=0.0,

    perspective=0.0001,

    hsv_h=0.015,
    hsv_s=0.5,
    hsv_v=0.3,

    mosaic=0.5,
    mixup=0.0,

    # Training stability
    amp=True,
    seed=42,
    deterministic=True,

    # Saving
    project=PROJECT,
    name=EXPERIMENT_NAME,

    save=True,
    plots=True,

    # Logging
    verbose=True
)


# RESULTADOS


print("\n========== ENTRENAMIENTO FINALIZADO ==========")

print("Mejores pesos guardados en:")

print(
    Path(PROJECT)
    / EXPERIMENT_NAME
    / "weights"
    / "best.pt"
)