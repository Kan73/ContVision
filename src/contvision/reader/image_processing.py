import cv2

from .config import (
    OCR_UPSCALE_FACTOR
)


def crop_detection(image, bbox):

    x1, y1, x2, y2 = bbox

    height, width = image.shape[:2]

    # Evitar coordenadas fuera de la imagen
    x1 = max(0, x1)
    y1 = max(0, y1)

    x2 = min(width, x2)
    y2 = min(height, y2)

    if x2 <= x1 or y2 <= y1:
        return None

    crop = image[y1:y2, x1:x2]

    return crop.copy()


def preprocess_image(image):

    if image is None or image.size == 0:
        return None

    # Escala de grises
    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    # Aumentar resolución
    enlarged = cv2.resize(
        gray,
        None,
        fx=OCR_UPSCALE_FACTOR,
        fy=OCR_UPSCALE_FACTOR,
        interpolation=cv2.INTER_CUBIC
    )

    # Mejorar contraste local
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )

    enhanced = clahe.apply(enlarged)

    # Convertir a BGR para mantener compatibilidad
    # con la entrada de PaddleOCR.
    processed = cv2.cvtColor(
        enhanced,
        cv2.COLOR_GRAY2BGR
    )

    return processed