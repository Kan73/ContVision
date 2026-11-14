
import os

os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "False"

from reader.pipeline import extract_container_id


image_path = "/home/adri/Documents/UDC/hackatones/1hack/ContVision/dataset_split/train/images/1-122816001-OCR-AS-B01.jpg"

container_id = extract_container_id(image_path)

if container_id:

    print("Container ID:", container_id)

else:

    print("Container ID not detected")