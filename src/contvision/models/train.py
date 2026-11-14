
import torch
from pathlib import Path
from ultralytics import YOLO


# ==========================================
# CONFIGURATION
# ==========================================

ROOT = Path(__file__).resolve().parents[3]

DATASET_DIR = ROOT / "dataset_split"
DATASET = str(DATASET_DIR / "data.yaml")
MODEL = "yolo26s.pt"

EPOCHS = 100
IMAGE_SIZE = 640
BATCH_SIZE = 8

DEVICE = 0 if torch.cuda.is_available() else "cpu"

PROJECT = "runs/container_id"
EXPERIMENT = "yolo26s_baseline"


# ==========================================
# HARDWARE CHECK
# ==========================================

print("\n========== HARDWARE ==========")

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

else:
    print("CUDA unavailable. Using CPU.")


# ==========================================
# DATASET CHECK
# ==========================================

print("\n========== DATASET ==========")

for split in ["train", "val", "test"]:

    images_dir = DATASET_DIR / split / "images"
    labels_dir = DATASET_DIR / split / "labels"

    if not images_dir.exists():
        raise FileNotFoundError(images_dir)

    if not labels_dir.exists():
        raise FileNotFoundError(labels_dir)

    images = [
        p for p in images_dir.iterdir()
        if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]
    ]

    labels = list(labels_dir.glob("*.txt"))

    print(f"\n{split.upper()}")
    print("Images:", len(images))
    print("Labels:", len(labels))

    if split in ["train", "val"] and len(images) == 0:
        raise RuntimeError(f"No images found in {split}")


# ==========================================
# LOAD MODEL
# ==========================================

print("\n========== LOADING MODEL ==========")

model = YOLO(MODEL)


# ==========================================
# TRAIN
# ==========================================

print("\n========== STARTING TRAINING ==========")

results = model.train(

    data=DATASET,

    epochs=EPOCHS,
    imgsz=IMAGE_SIZE,
    batch=BATCH_SIZE,

    device=DEVICE,
    workers=4,

    pretrained=True,
    optimizer="auto",

    patience=20,

    # Augmentation
    degrees=5.0,
    translate=0.05,
    scale=0.2,

    fliplr=0.0,
    flipud=0.0,

    hsv_h=0.015,
    hsv_s=0.5,
    hsv_v=0.3,

    mosaic=0.5,
    mixup=0.0,

    # Training stability
    amp=True,
    seed=42,
    deterministic=True,

    # Output
    project=PROJECT,
    name=EXPERIMENT,

    save=True,
    plots=True,
    verbose=True
)


# ==========================================
# FINISHED
# ==========================================

print("\n========== TRAINING FINISHED ==========")

print(
    "Best weights:",
    f"{PROJECT}/{EXPERIMENT}/weights/best.pt"
)
