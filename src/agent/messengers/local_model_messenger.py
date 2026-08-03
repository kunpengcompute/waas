from messengers.messenger import Messenger
from model.model_infer import ModelInfer


class LocalModelMessenger(Messenger):
    def __init__(self, model_path=None, inferencer=None):
        super().__init__()
        if inferencer is not None:
            self.inferencer = inferencer
        elif model_path is None:
            self.inferencer = ModelInfer.from_file()
        else:
            self.inferencer = ModelInfer.from_file(model_path)
        self._payload = None
        self._reason_code = None

    def send_data(self, data):
        self._payload = data
        self._reason_code = None

    def get_advice(self):
        if self._payload is None:
            raise RuntimeError("no payload available for local inference")
        self._reason_code = self.inferencer.infer(self._payload)
        return {}

    def get_interference_reason(self) -> int:
        if self._reason_code is None:
            raise RuntimeError("local inference has not completed")
        return self._reason_code
