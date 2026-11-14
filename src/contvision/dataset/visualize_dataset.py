
from pathlib import Path
import cv2
import random

ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "dataset_split"

images_dir = DATASET / "train" / "images"
labels_dir = DATASET / "train" / "labels"

images = list(images_dir.glob("*.jpg"))

random.seed(42)

selected = random.sample(images, min(10, len(images)))

output_dir = ROOT / "dataset_preview"
output_dir.mkdir(exist_ok=True)

for image_path in selected:

    image = cv2.imread(str(image_path))

    if image is None:
        continue

    h, w = image.shape[:2]

    label_path = labels_dir / f"{image_path.stem}.txt"

    if not label_path.exists():
        continue

    for line in label_path.read_text().splitlines():

        parts = line.split()

        if len(parts) != 5:
            continue

        cls, cx, cy, bw, bh = map(float, parts)

        x1 = int((cx - bw / 2) * w)
        y1 = int((cy - bh / 2) * h)

        x2 = int((cx + bw / 2) * w)
        y2 = int((cy + bh / 2) * h)

        cv2.rectangle(
            image,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            3
        )

    cv2.imwrite(
        str(output_dir / image_path.name),
        image
    )

print("Visualizaciones guardadas en:", output_dir)
