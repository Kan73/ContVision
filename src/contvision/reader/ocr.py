from paddleocr import PaddleOCR

from .config import (
    OCR_LANGUAGE,
    OCR_USE_GPU
)


class ContainerOCR:

    def __init__(self):

        self.ocr = PaddleOCR(
            lang=OCR_LANGUAGE,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False
        )

    def recognize(self, image):

        if image is None:
            return []

        results = self.ocr.predict(image)

        detected_texts = []

        for result in results:

            data = result.json

            if isinstance(data, dict):
                data = data.get("res", data)

            texts = data.get("rec_texts", [])
            scores = data.get("rec_scores", [])

            for text, score in zip(texts, scores):

                detected_texts.append({
                    "text": text,
                    "confidence": float(score)
                })

        return detected_texts