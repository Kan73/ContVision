
from pathlib import Path
import torch
from ultralytics import YOLO


# ==========================================
# PROJECT PATHS
# ==========================================

ROOT = Path(__file__).resolve().parents[3]

DATASET_DIR = ROOT / "dataset_split"
DATA_YAML = DATASET_DIR / "data.yaml"

# ==========================================
# CONFIGURATION
# ==========================================

MODEL = "yolo26s.pt"

EPOCHS = 100
IMAGE_SIZE = 640
BATCH_SIZE = 8

WORKERS = 0

DEVICE = 0 if torch.cuda.is_available() else "cpu"

PROJECT = str(ROOT / "runs" / "container_id")
EXPERIMENT = "yolo26s_baseline"


def main():

    # ======================================
    # HARDWARE
    # ======================================

    print("\n========== HARDWARE ==========")

    print("CUDA:", torch.cuda.is_available())

    if torch.cuda.is_available():

        print("GPU:", torch.cuda.get_device_name(0))

        print(
            "VRAM:",
            round(
                torch.cuda.get_device_properties(0).total_memory
                / 1024**3,
                2
            ),
            "GB"
        )

    # ======================================
    # DATASET CHECK
    # ======================================

    print("\n========== DATASET ==========")

    if not DATA_YAML.exists():
        raise FileNotFoundError(DATA_YAML)

    for split in ["train", "val", "test"]:

        images_dir = DATASET_DIR / split / "images"
        labels_dir = DATASET_DIR / split / "labels"

        if not images_dir.exists():
            raise FileNotFoundError(images_dir)

        if not labels_dir.exists():
            raise FileNotFoundError(labels_dir)

        images = [
            p for p in images_dir.iterdir()
            if p.suffix.lower() in [
                ".jpg", ".jpeg", ".png", ".bmp"
            ]
        ]

        labels = list(labels_dir.glob("*.txt"))

        print(f"{split}: {len(images)} images")
        print(f"{split}: {len(labels)} labels")

    # ======================================
    # LOAD MODEL
    # ======================================

    print("\n========== LOADING MODEL ==========")

    model = YOLO(MODEL)

    # ======================================
    # TRAIN
    # ======================================

    print("\n========== STARTING TRAINING ==========")

    model.train(

        data=str(DATA_YAML),

        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,

        device=DEVICE,
        workers=WORKERS,

        pretrained=True,
        optimizer="auto",
        patience=20,

        # Augmentations
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

        # Stability
        amp=True,
        seed=42,
        deterministic=True,

        # Saving
        project=PROJECT,
        name=EXPERIMENT,

        save=True,
        plots=True,
        verbose=True
    )

    print("\n========== TRAINING FINISHED ==========")

    print(
        "Best weights:",
        Path(PROJECT) / EXPERIMENT / "weights" / "best.pt"
    )


if __name__ == "__main__":
    main()
