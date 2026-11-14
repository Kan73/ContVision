
from ultralytics import YOLO


class ContainerIDDetector:

    def __init__(self, weights="yolo26s.pt"):

        """
        Detector de identificadores de contenedores.

        Args:
            weights: pesos preentrenados o checkpoint entrenado.
        """

        self.model = YOLO(weights)

    def train(self, **kwargs):

        """
        Entrena el detector mediante fine-tuning.
        """

        return self.model.train(**kwargs)

    def predict(self, image, conf=0.25, imgsz=640):

        """
        Detecta identificadores en una imagen.
        """

        return self.model.predict(
            source=image,
            conf=conf,
            imgsz=imgsz,
            verbose=False
        )

    def validate(self, **kwargs):

        """
        Evalúa el modelo.
        """

        return self.model.val(**kwargs)

    def export(self, format="onnx"):

        """
        Exporta el modelo.
        """

        return self.model.export(format=format)

#containe number-ocr
#roboflow universe container id