import pytest

from messengers.messenger import Messenger


def test_messenger_exposes_interference_reason_interface():
    class MessengerWithoutReasonImplementation(Messenger):
        def send_data(self, data):
            pass

        def get_advice(self):
            pass

    messenger = MessengerWithoutReasonImplementation()

    with pytest.raises(NotImplementedError):
        messenger.get_interference_reason()
