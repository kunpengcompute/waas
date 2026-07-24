import csv

from data_recorder import DataRecorder


def cgroup_data(path, count):
    return {
        "start_time": "start",
        "stop_time": "stop",
        "cgroup_path": path,
        "all": {
            0: {
                "INST_RETIRED": {
                    "count": count,
                    "countPercent": 100.0,
                }
            }
        },
    }


def test_recorder_writes_each_cgroup_as_a_separate_row(tmp_path):
    output = tmp_path / "data.csv"
    recorder = DataRecorder(str(output))

    recorder.insert(cgroup_data("path-a", 10))
    recorder.insert(cgroup_data("path-b", 20))
    recorder.close()

    with output.open(newline="", encoding="utf-8") as file_obj:
        rows = list(csv.DictReader(file_obj))

    assert [row["cgroup_path"] for row in rows] == ["path-a", "path-b"]
    assert [row["0_INST_RETIRED_count"] for row in rows] == ["10", "20"]
