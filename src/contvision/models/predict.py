from ultralytics import YOLO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

model = YOLO(
    ROOT / "runs/container_id/yolo26s_baseline/weights/best.pt"
)

metrics = model.val(
    data=str(ROOT / "dataset_split/data.yaml"),
    split="test",
    imgsz=640,
    device=0
)

print(metrics.results_dict)