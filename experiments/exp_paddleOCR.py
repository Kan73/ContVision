from paddleocr import PaddleOCR

ocr = PaddleOCR(
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False
)

results = ocr.predict("data/raw/test1.jpg")

for result in results:
    result.print()