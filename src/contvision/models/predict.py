
from pathlib import Path
from ultralytics import YOLO


# ==========================================
# PROJECT PATHS
# ==========================================

ROOT = Path(__file__).resolve().parents[3]

MODEL_PATH = (
    ROOT
    / "runs"
    / "container_id"
    / "yolo26s_baseline"
    / "weights"
    / "best.pt"
)

DATASET_YAML = ROOT / "dataset_split" / "data.yaml"

OUTPUT_DIR = ROOT / "runs" / "evaluation"


def main():

    # ======================================
    # CHECK FILES
    # ======================================

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found: {MODEL_PATH}"
        )

    if not DATASET_YAML.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_YAML}"
        )

    # ======================================
    # LOAD MODEL
    # ======================================

    print("\n========== LOADING MODEL ==========")

    model = YOLO(str(MODEL_PATH))

    # ======================================
    # TEST EVALUATION
    # ======================================

    print("\n========== TEST EVALUATION ==========")

    metrics = model.val(

        data=str(DATASET_YAML),

        split="test",

        imgsz=640,

        batch=8,

        device=0,

        workers=0,

        plots=True,

        project=str(OUTPUT_DIR),

        name="yolo26s_test",

        exist_ok=True

    )

    # ======================================
    # RESULTS
    # ======================================

    print("\n========== RESULTS ==========")

    for key, value in metrics.results_dict.items():

        print(f"{key}: {value}")

    print("\nEvaluation completed!")

    print(
        "Results saved in:",
        OUTPUT_DIR / "yolo26s_test"
    )


if __name__ == "__main__":
    main()
