import pytest

from layers.cgroup_reduction import CgroupReduction


def test_cgroup_reduction_averages_active_cpu_features():
    data = {
        0: {"INST_RETIRED": 10, "l3.mpi": 2.0},
        1: {"INST_RETIRED": 0, "l3.mpi": 100.0},
        2: {"INST_RETIRED": 30, "l3.mpi": 4.0},
    }

    result = CgroupReduction().process(data)

    assert result == {
        0: {"INST_RETIRED": 20.0, "l3.mpi": 3.0},
    }


def test_cgroup_reduction_rejects_sample_without_active_cpu():
    data = {
        0: {"INST_RETIRED": 0, "l3.mpi": 0.0},
    }

    with pytest.raises(ValueError, match="no active CPU metrics"):
        CgroupReduction().process(data)
