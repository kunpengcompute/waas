import importlib

import pytest


def model_infer_module():
    return importlib.import_module("model.model_infer")


def payload(features):
    return {
        "all": {
            0: features,
        }
    }


def test_payload_to_input_uses_training_feature_order():
    model_infer = model_infer_module()
    data = payload(
        {
            "cpu.ipc": 2.0,
            "l3.mpi": 1.0,
            "l3.mr": 4.0,
            "sve.ratio": 3.0,
            "l1d.refer/l1i.refer": 5.0,
        }
    )

    result = model_infer.payload_to_input(
        data,
        model_infer.SELECTED_FEATURES,
    )

    assert result == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_payload_to_input_rejects_missing_model_feature():
    model_infer = model_infer_module()

    with pytest.raises(ValueError, match="missing model features"):
        model_infer.payload_to_input(
            payload({"l3.mpi": 1.0}),
            model_infer.SELECTED_FEATURES,
        )


def test_model_infer_returns_builtin_integer_reason_code():
    model_infer = model_infer_module()

    class IntegerLike:
        def __int__(self):
            return 4

    class FakeModel:
        def predict(self, samples):
            assert samples == [[1.0, 2.0, 3.0, 4.0, 5.0]]
            return [IntegerLike()]

    inferencer = model_infer.ModelInfer(FakeModel())

    reason_code = inferencer.infer(
        payload(
            dict(zip(model_infer.SELECTED_FEATURES, range(1, 6)))
        )
    )

    assert reason_code == 4
    assert type(reason_code) is int


def test_model_infer_rejects_unknown_reason_code():
    model_infer = model_infer_module()

    class FakeModel:
        def predict(self, samples):
            return [7]

    inferencer = model_infer.ModelInfer(FakeModel())

    with pytest.raises(ValueError, match="unknown reason code: 7"):
        inferencer.infer(
            payload(
                dict(zip(model_infer.SELECTED_FEATURES, range(1, 6)))
            )
        )
