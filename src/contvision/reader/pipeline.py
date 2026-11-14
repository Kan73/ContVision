import cv2
import numpy as np

from .detector import ContainerDetector
from .image_processing import (
    crop_detection,
    preprocess_image
)
from .ocr import ContainerOCR
from .validation import (
    clean_text,
    validate_iso6346
)


class ContainerIDExtractor:

    def __init__(self):

        self.detector = ContainerDetector()

        self.ocr = ContainerOCR()

    def extract(self, image):

        # =====================================
        # 1. VALIDAR IMAGEN
        # =====================================

        if isinstance(image, str):

            image = cv2.imread(image)

        elif not isinstance(image, np.ndarray):

            raise TypeError(
                "Image must be a file path or numpy array"
            )

        if image is None or image.size == 0:

            raise ValueError(
                "Invalid image"
            )

        # =====================================
        # 2. DETECTAR REGIÓN CON YOLO
        # =====================================

        detection = self.detector.detect(image)

        if detection is None:
            return None

        bbox = detection["bbox"]

        # =====================================
        # 3. RECORTAR REGIÓN
        # =====================================

        crop = crop_detection(
            image,
            bbox
        )

        if crop is None:
            return None

        # =====================================
        # 4. PREPROCESAR
        # =====================================

        processed = preprocess_image(crop)

        if processed is None:
            return None

        # =====================================
        # 5. OCR
        # =====================================

        predictions = self.ocr.recognize(
            processed
        )

        # =====================================
        # 6. VALIDAR RESULTADOS
        # =====================================

        for prediction in predictions:

            text = clean_text(
                prediction["text"]
            )

            if validate_iso6346(text):

                return text

        return None


# =========================================
# PUBLIC API
# =========================================

_extractor = None


def extract_container_id(image):

    global _extractor

    if _extractor is None:

        _extractor = ContainerIDExtractor()

    return _extractor.extract(image)