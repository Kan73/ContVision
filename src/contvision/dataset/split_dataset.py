
import os
import random
import shutil
from pathlib import Path

# ==============================
# CONFIGURACIÓN
# ==============================

IMAGE_DIR = Path("dataset/images")
LABEL_DIR = Path("dataset/labels")
OUTPUT_DIR = Path("dataset_split")

# Porcentajes de división
TRAIN_RATIO = 0.80
VAL_RATIO = 0.10
TEST_RATIO = 0.10

# Semilla para que la división sea reproducible
RANDOM_SEED = 9424

# Extensiones de imagen permitidas
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp",
    ".tif", ".tiff", ".webp"
}


# ==============================
# DIVISIÓN DEL DATASET
# ==============================

def split_dataset():

    # Comprobar porcentajes
    total_ratio = TRAIN_RATIO + VAL_RATIO + TEST_RATIO

    if abs(total_ratio - 1.0) > 0.0001:
        raise ValueError("Los porcentajes deben sumar 1.0")

    # Obtener imágenes
    images = [
        f for f in IMAGE_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]

    if not images:
        print("No se han encontrado imágenes.")
        return

    # Mezclar imágenes aleatoriamente
    random.seed(RANDOM_SEED)
    random.shuffle(images)

    # Calcular cantidades
    total = len(images)

    train_end = int(total * TRAIN_RATIO)
    val_end = train_end + int(total * VAL_RATIO)

    datasets = {
        "train": images[:train_end],
        "val": images[train_end:val_end],
        "test": images[val_end:]
    }

    # Crear carpetas
    for split in datasets:
        (OUTPUT_DIR / split / "images").mkdir(
            parents=True, exist_ok=True
        )
        (OUTPUT_DIR / split / "labels").mkdir(
            parents=True, exist_ok=True
        )

    # Copiar imágenes y anotaciones
    for split, split_images in datasets.items():

        for image_path in split_images:

            # Copiar imagen
            destination_image = (
                OUTPUT_DIR / split / "images" / image_path.name
            )

            shutil.copy2(image_path, destination_image)

            # Buscar archivo TXT con el mismo nombre
            label_path = LABEL_DIR / (image_path.stem + ".txt")

            if label_path.exists():

                destination_label = (
                    OUTPUT_DIR / split / "labels" / label_path.name
                )

                shutil.copy2(label_path, destination_label)

            else:
                print(
                    f"AVISO: No existe anotación para "
                    f"{image_path.name}"
                )

    # Mostrar resumen
    print("\nDataset dividido correctamente:\n")

    for split, split_images in datasets.items():
        print(f"{split}: {len(split_images)} imágenes")

    print(f"\nResultado guardado en: {OUTPUT_DIR}")


if __name__ == "__main__":
    split_dataset()
