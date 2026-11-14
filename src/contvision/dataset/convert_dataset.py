
from pathlib import Path
import cv2


# ==========================================
# PATHS
# ==========================================

ROOT = Path(__file__).resolve().parents[3]

DATASET = ROOT / "dataset_split"

SPLITS = ["train", "val", "test"]


# ==========================================
# CONVERSION
# ==========================================

def convert_label(label_path, img_w, img_h):

    yolo_annotations = []

    with open(label_path, "r", encoding="utf-8") as f:

        lines = f.readlines()

    for line in lines:

        parts = line.strip().split(",")

        if len(parts) != 5:
            print("Invalid annotation:", line.strip())
            continue

        try:

            x1, y1, x2, y2 = map(
                float,
                parts[:4]
            )

            text = parts[4].strip().upper()

        except ValueError:
            print("Invalid coordinates:", line.strip())
            continue

        # Solo identificadores completos ISO 6346
        if len(text) != 11:
            continue

        if not (
            text[:4].isalpha()
            and text[:4].isascii()
            and text[4:].isdigit()
        ):
            continue

        # Validar coordenadas
        if not (
            0 <= x1 < x2 <= img_w
            and 0 <= y1 < y2 <= img_h
        ):
            print("Invalid bounding box:", line.strip())
            continue

        # Normalizar
        cx = ((x1 + x2) / 2) / img_w
        cy = ((y1 + y2) / 2) / img_h

        w = (x2 - x1) / img_w
        h = (y2 - y1) / img_h

        yolo_annotations.append(
            f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"
        )

    return yolo_annotations


# ==========================================
# PROCESS DATASET
# ==========================================

total_images = 0
total_boxes = 0
missing_labels = 0

for split in SPLITS:

    images_dir = DATASET / split / "images"
    labels_dir = DATASET / split / "labels"

    print(f"\n========== {split.upper()} ==========")

    for image_path in images_dir.iterdir():

        if image_path.suffix.lower() not in [
            ".jpg", ".jpeg", ".png", ".bmp"
        ]:
            continue

        label_path = labels_dir / (
            image_path.stem + ".txt"
        )

        if not label_path.exists():
            missing_labels += 1
            continue

        image = cv2.imread(str(image_path))

        if image is None:
            print("Corrupt image:", image_path.name)
            continue

        img_h, img_w = image.shape[:2]

        annotations = convert_label(
            label_path,
            img_w,
            img_h
        )

        # Sobrescribir etiqueta original
        with open(
            label_path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write("\n".join(annotations))

            if annotations:
                f.write("\n")

        total_images += 1
        total_boxes += len(annotations)

    print("Processed split:", split)


# ==========================================
# SUMMARY
# ==========================================

print("\n========== SUMMARY ==========")

print("Processed images:", total_images)
print("Valid boxes:", total_boxes)
print("Missing labels:", missing_labels)

print("\nConversion completed.")
