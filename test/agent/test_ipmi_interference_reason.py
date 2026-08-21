from messengers.ipmi_messenger import IpmiMessenger


def test_get_interference_reason_uses_bmc_label_range(monkeypatch):
    calls = []

    def fake_randint(start, end):
        calls.append((start, end))
        return 4

    monkeypatch.setattr("messengers.ipmi_messenger.random.randint", fake_randint)

    assert IpmiMessenger().get_interference_reason() == 4
    assert calls == [(0, 6)]
