import torch
from ultralytics import YOLO

assert torch.cuda.is_available()

model = YOLO("yolo26n.pt")

results = model.predict(
    source="data/raw",
    device=0,
    imgsz=640,
    save=True
)

print("Imágenes procesadas:", len(results))
print("GPU:", torch.cuda.get_device_name(0))