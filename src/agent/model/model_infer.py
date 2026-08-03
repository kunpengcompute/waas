import pickle
import warnings
from pathlib import Path


LABEL_MAP = {
    0: "base",
    1: "compute",
    2: "l2",
    3: "l3",
    4: "membw",
    5: "tlb",
    6: "frontend",
}

SELECTED_FEATURES = (
    "l3.mpi",
    "cpu.ipc",
    "sve.ratio",
    "l3.mr",
    "l1d.refer/l1i.refer",
)

DEFAULT_MODEL_PATH = Path(__file__).with_name("rf_spec.pkl")


def load_model(model_file):
    with Path(model_file).open("rb") as model_stream:
        return pickle.load(model_stream)


def payload_to_input(payload, feature_order):
    feature_groups = payload.get("all", {})
    if len(feature_groups) != 1:
        raise ValueError("local inference requires exactly one feature group")

    features = next(iter(feature_groups.values()))
    missing_features = [
        feature_name
        for feature_name in feature_order
        if feature_name not in features
    ]
    if missing_features:
        raise ValueError(
            f"missing model features: {missing_features}"
        )

    return [features[feature_name] for feature_name in feature_order]


class ModelInfer:
    def __init__(self, model):
        self.model = model

    @classmethod
    def from_file(cls, model_file=DEFAULT_MODEL_PATH):
        return cls(load_model(model_file))

    def infer(self, payload):
        feature_values = payload_to_input(payload, SELECTED_FEATURES)
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=UserWarning,
                message=(
                    "X does not have valid feature names, "
                    "but .* was fitted with feature names"
                ),
            )
            reason_code = int(self.model.predict([feature_values])[0])

        if reason_code not in LABEL_MAP:
            raise ValueError(
                f"model returned unknown reason code: {reason_code}"
            )
        return reason_code


def infer(payload, model_file=DEFAULT_MODEL_PATH):
    return ModelInfer.from_file(model_file).infer(payload)
