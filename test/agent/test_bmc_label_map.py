import util


def test_bmc_label_map_matches_protocol_definition():
    assert list(util.LABEL_MAP.items()) == [
        ("base", 0),
        ("compute", 1),
        ("l2", 2),
        ("l3", 3),
        ("membw", 4),
        ("tlb", 5),
        ("frontend", 6),
    ]
