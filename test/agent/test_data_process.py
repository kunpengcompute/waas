from data_process import DataProcessor


def test_aggregate_accepts_single_cgroup_cpu_metrics():
    processor = DataProcessor()
    processor.features = {
        "INST_RETIRED": lambda metrics: metrics["INST_RETIRED"],
    }
    raw_metrics = {
        0: {
            "INST_RETIRED": {
                "count": 10,
                "countPercent": 100.0,
            }
        },
        1: {
            "INST_RETIRED": {
                "count": 20,
                "countPercent": 100.0,
            }
        },
    }

    result = processor.aggregate(raw_metrics)

    assert result == {
        0: {"INST_RETIRED": 10},
        1: {"INST_RETIRED": 20},
    }
