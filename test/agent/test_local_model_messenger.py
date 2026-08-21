import importlib

import pytest


def local_messenger_class():
    module = importlib.import_module("messengers.local_model_messenger")
    return module.LocalModelMessenger


def test_local_messenger_runs_model_from_existing_messenger_calls():
    payload = {"all": {0: {"l3.mpi": 1.0}}}

    class FakeInferencer:
        def __init__(self):
            self.payloads = []

        def infer(self, current_payload):
            self.payloads.append(current_payload)
            return 4

    inferencer = FakeInferencer()
    messenger = local_messenger_class()(inferencer=inferencer)

    messenger.send_data(payload)
    assert messenger.get_advice() == {}

    assert messenger.get_interference_reason() == 4
    assert inferencer.payloads == [payload]


def test_local_messenger_rejects_get_advice_before_send_data():
    messenger = local_messenger_class()(inferencer=object())

    with pytest.raises(RuntimeError, match="no payload"):
        messenger.get_advice()


def test_local_messenger_loads_model_when_created(monkeypatch):
    module = importlib.import_module("messengers.local_model_messenger")
    inferencer = object()
    loaded_paths = []

    def fake_from_file(model_path):
        loaded_paths.append(model_path)
        return inferencer

    monkeypatch.setattr(module.ModelInfer, "from_file", fake_from_file)

    messenger = module.LocalModelMessenger("/tmp/model.pkl")

    assert messenger.inferencer is inferencer
    assert loaded_paths == ["/tmp/model.pkl"]


def test_local_messenger_propagates_model_load_failure(monkeypatch):
    module = importlib.import_module("messengers.local_model_messenger")

    def fail_to_load(model_path):
        raise FileNotFoundError(model_path)

    monkeypatch.setattr(module.ModelInfer, "from_file", fail_to_load)

    with pytest.raises(FileNotFoundError, match="missing.pkl"):
        module.LocalModelMessenger("/tmp/missing.pkl")
