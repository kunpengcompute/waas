# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import unittest
from unittest.mock import patch, mock_open
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../../src/waasbooster"))
import boost_log as logging
from util import get_cpu_cgroup_mount_point, get_numa_cpu_mapping, file_check, get_cgroup_path_for_pid, is_container_path,\
                 check_container_cpuset_cpus, legal_cgroup_path, get_container_cgroups, get_boosted_container_cgroups,\
                 get_container_info, weighted_queue_sum, read_cpu_stats, read_file, get_cpu_usage, parse_cpu_affinity, \
                 map_cores_to_numa, is_numa_multiple

logging.set_log_instance("INFO")


class TestGetCpuCgroupMountPoint(unittest.TestCase):
    
    @patch("builtins.open", mock_open(read_data="cgroup /sys/fs/cgroup/cpu,cpuacct cgroup rw,relatime,cpu 0 0\n"
                                               "cgroup /sys/fs/cgroup/cpuset cgroup rw,relatime,cpuset 0 0"))
    def test_get_cpu_cgroup_mount_point_success(self):
        cpu_path, cpuset_path = get_cpu_cgroup_mount_point()
        self.assertEqual(cpu_path, '/sys/fs/cgroup/cpu,cpuacct')
        self.assertEqual(cpuset_path, '/sys/fs/cgroup/cpuset')

    @patch("builtins.open", mock_open(read_data="cgroup /sys/fs/cgroup/cpu cgroup rw,relatime,cpu 0 0\n"
                                               "cgroup /sys/fs/cgroup/cpuset cgroup rw,relatime,cpuset 0 0"))
    def test_get_cpu_cgroup_mount_point_partial_info(self):
        cpu_path, cpuset_path = get_cpu_cgroup_mount_point()
        self.assertEqual(cpu_path, '/sys/fs/cgroup/cpu')
        self.assertEqual(cpuset_path, '/sys/fs/cgroup/cpuset')

    @patch("builtins.open", mock_open(read_data="cgroup /sys/fs/cgroup/cpu cgroup rw,relatime,cpu 0 0"))
    def test_get_cpu_cgroup_mount_point_no_cpuset(self):
        cpu_path, cpuset_path = get_cpu_cgroup_mount_point()
        self.assertEqual(cpu_path, '/sys/fs/cgroup/cpu')
        self.assertIsNone(cpuset_path)

    @patch("builtins.open", mock_open(read_data="cgroup /sys/fs/cgroup/cpuset cgroup rw,relatime,cpuset 0 0"))
    def test_get_cpu_cgroup_mount_point_no_cpu(self):
        cpu_path, cpuset_path = get_cpu_cgroup_mount_point()
        self.assertIsNone(cpu_path)
        self.assertEqual(cpuset_path, '/sys/fs/cgroup/cpuset')

    @patch("builtins.open", mock_open(read_data=""))
    def test_get_cpu_cgroup_mount_point_empty_file(self):
        cpu_path, cpuset_path = get_cpu_cgroup_mount_point()
        self.assertIsNone(cpu_path)
        self.assertIsNone(cpuset_path)


class TestGetNumaCpuMapping(unittest.TestCase):
    
    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("builtins.open", mock_open(read_data="0-31"))
    def test_get_numa_cpu_mapping_success(self, mock_listdir, mock_exists):
        # 模拟 NUMA 路径存在
        mock_exists.return_value = True
        
        # 模拟列出 NUMA 节点目录
        mock_listdir.return_value = ['node0', 'node1', 'node2', 'node3']
        
        # 调用被测试的函数
        result = get_numa_cpu_mapping()
        
        # 预期的结果
        expected = {
            0: '0-31',
            1: '0-31',
            2: '0-31',
            3: '0-31'
        }
        
        self.assertEqual(result, expected)

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("builtins.open", mock_open(read_data="0-15"))
    def test_get_numa_cpu_mapping_partial_nodes(self, mock_listdir, mock_exists):
        # 模拟 NUMA 路径存在
        mock_exists.return_value = True
        
        # 模拟列出部分 NUMA 节点目录
        mock_listdir.return_value = ['node0', 'node1']
        
        # 调用被测试的函数
        result = get_numa_cpu_mapping()
        
        # 预期的结果
        expected = {
            0: '0-15',
            1: '0-15'
        }
        
        self.assertEqual(result, expected)
        
    @patch("os.path.exists")
    @patch("os.listdir")
    def test_get_numa_cpu_mapping_no_numa(self, mock_listdir, mock_exists):
        # 模拟 NUMA 路径不存在
        mock_exists.return_value = False
        
        # 调用被测试的函数，确保会抛出 OSError
        with self.assertRaises(OSError):
            get_numa_cpu_mapping()

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("builtins.open", mock_open(read_data="0-7"))
    def test_get_numa_cpu_mapping_empty_cpulist(self, mock_listdir, mock_exists):
        # 模拟 NUMA 路径存在
        mock_exists.return_value = True
        
        # 模拟列出 NUMA 节点目录
        mock_listdir.return_value = ['node0']
        
        # 调用被测试的函数
        result = get_numa_cpu_mapping()
        
        # 预期的结果
        expected = {0: '0-7'}
        
        self.assertEqual(result, expected)
    
    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("builtins.open", mock_open(read_data=""))
    def test_get_numa_cpu_mapping_empty_cpulist_file(self, mock_listdir, mock_exists):
        # 模拟 NUMA 路径存在
        mock_exists.return_value = True
        
        # 模拟列出 NUMA 节点目录
        mock_listdir.return_value = ['node0']
        
        # 测试 cpu_list 文件为空的情况
        result = get_numa_cpu_mapping()
        
        expected = {0: ''}
        
        self.assertEqual(result, expected)


class TestFileCheck(unittest.TestCase):
    
    @patch("builtins.open", mock_open(read_data="0:cpu:/docker/abc\n1:cpu,cpuacct:/sys/fs/cgroup"))
    def test_file_check_success(self):
        pid = 1234
        cpu_mount = "/sys/fs/cgroup"
        cgroup_key = "cpu"

        # 测试正常的cgroup文件
        result = file_check(pid, cpu_mount, cgroup_key)
        expected = "/sys/fs/cgroup/docker/abc"
        self.assertEqual(result, expected)

    @patch("builtins.open", mock_open(read_data="0:cpu:/docker/abc\n1:cpu,cpuacct:/sys/fs/cgroup"))
    def test_file_check_multiple_controllers(self):
        pid = 1234
        cpu_mount = "/sys/fs/cgroup"
        cgroup_key = "cpuacct"

        # 测试多个控制器匹配
        result = file_check(pid, cpu_mount, cgroup_key)
        expected = "/sys/fs/cgroup/sys/fs/cgroup"
        self.assertEqual(result, expected)

    @patch("builtins.open", mock_open(read_data="0:cpu:/docker/abc\n1:memory:/sys/fs/cgroup"))
    def test_file_check_no_match(self):
        pid = 1234
        cpu_mount = "/sys/fs/cgroup"
        cgroup_key = "cpuacct"

        # 测试没有匹配的控制器
        result = file_check(pid, cpu_mount, cgroup_key)
        self.assertIsNone(result)

    @patch("builtins.open", mock_open(read_data="0:cpu:/\n1:cpu:/sys/fs/cgroup"))
    def test_file_check_invalid_path(self):
        pid = 1234
        cpu_mount = "/sys/fs/cgroup"
        cgroup_key = "cpu"

        # 测试路径为"/"的情况
        result = file_check(pid, cpu_mount, cgroup_key)
        expected = '/sys/fs/cgroup/sys/fs/cgroup'
        self.assertEqual(result, expected)

    @patch("builtins.open", mock_open(read_data=""))
    def test_file_check_empty_file(self):
        pid = 1234
        cpu_mount = "/sys/fs/cgroup"
        cgroup_key = "cpu"

        # 测试空文件
        result = file_check(pid, cpu_mount, cgroup_key)
        self.assertIsNone(result)

    @patch("builtins.open", mock_open(read_data="0:cpu:/docker/abc\n"))
    def test_file_check_invalid_format(self):
        pid = 1234
        cpu_mount = "/sys/fs/cgroup"
        cgroup_key = "cpu"

        # 测试格式不对的cgroup文件
        result = file_check(pid, cpu_mount, cgroup_key)
        expected = "/sys/fs/cgroup/docker/abc"
        self.assertEqual(result, expected)


class TestGetCgroupPathForPid(unittest.TestCase):
    
    @patch("util.file_check")  # 修改为实际文件模块路径
    def test_get_cgroup_path_for_pid_success(self, mock_file_check):
        pid = 1234
        cpu_mount = "/sys/fs/cgroup"
        cgroup_key = "cpu"
        
        # 模拟 file_check 返回有效路径
        mock_file_check.return_value = "/sys/fs/cgroup/docker/abc"
        
        # 调用被测试的函数
        result = get_cgroup_path_for_pid(pid, cpu_mount, cgroup_key)
        
        # 断言返回的路径是否正确
        self.assertEqual(result, "/sys/fs/cgroup/docker/abc")
        mock_file_check.assert_called_once_with(pid, cpu_mount, cgroup_key)
    
    @patch("util.file_check")  # 修改为实际文件模块路径
    def test_get_cgroup_path_for_pid_no_path(self, mock_file_check):
        pid = 1234
        cpu_mount = "/sys/fs/cgroup"
        cgroup_key = "cpu"
        
        # 模拟 file_check 返回 None
        mock_file_check.return_value = None
        
        # 调用被测试的函数
        result = get_cgroup_path_for_pid(pid, cpu_mount, cgroup_key)
        
        # 断言返回的结果为 None
        self.assertIsNone(result)
        mock_file_check.assert_called_once_with(pid, cpu_mount, cgroup_key)

    @patch("util.file_check")  # 修改为实际文件模块路径
    def test_get_cgroup_path_for_pid_exception(self, mock_file_check):
        pid = 1234
        cpu_mount = "/sys/fs/cgroup"
        cgroup_key = "cpu"
        
        # 模拟 file_check 抛出异常
        mock_file_check.side_effect = Exception("Test Exception")
        
        # 调用被测试的函数，验证异常是否被捕获
        result = get_cgroup_path_for_pid(pid, cpu_mount, cgroup_key)
        
        # 断言返回结果为 None
        self.assertIsNone(result)


class TestIsContainerPath(unittest.TestCase):
    
    def test_is_container_path_docker(self):
        path = "/var/lib/docker/containers/abcd1234"
        # 测试匹配 "docker"
        result = is_container_path(path)
        self.assertTrue(result)
    
    def test_is_container_path_kubepods(self):
        path = "/var/lib/kubepods/xyz1234"
        # 测试匹配 "kubepods"
        result = is_container_path(path)
        self.assertTrue(result)

    def test_is_container_path_containerd(self):
        path = "/var/lib/containerd/io.containerd.runtime.v2.task/k8s.io/abc1234"
        # 测试匹配 "containerd"
        result = is_container_path(path)
        self.assertTrue(result)

    def test_is_container_path_not_a_container(self):
        path = "/home/user/data"
        # 测试不匹配任何容器路径
        result = is_container_path(path)
        self.assertFalse(result)

    def test_is_container_path_multiple_matches(self):
        path = "/var/lib/docker/containers/abcd1234/kubepods"
        # 测试多个匹配 "docker" 和 "kubepods"
        result = is_container_path(path)
        self.assertTrue(result)

    def test_is_container_path_empty(self):
        path = ""
        # 测试空路径
        result = is_container_path(path)
        self.assertFalse(result)


class TestCheckContainerCpusetCpus(unittest.TestCase):

    @patch("os.path.exists", return_value=True)  # 模拟文件存在
    @patch("builtins.open", mock_open(read_data="0-31"))  # 模拟cpuset.cpus文件内容
    @patch("util.get_numa_cpu_mapping", return_value={0: "0-15", 1: "16-31"})  # 模拟NUMA节点
    @patch("util.is_numa_multiple", return_value=(True, [0, 1]))  # 模拟NUMA亲和性检查
    def test_check_container_cpuset_cpus_success(self, mock_is_numa_multiple, mock_get_numa_cpu_mapping, mock_open):
        cpu_set_path = "/sys/fs/cgroup"
        
        # 调用被测试的函数
        result, pod_nodes = check_container_cpuset_cpus(cpu_set_path)

        # 断言返回结果正确
        self.assertTrue(result)
        self.assertEqual(pod_nodes, [0, 1])
        mock_is_numa_multiple.assert_called_once_with("0-31", {0: "0-15", 1: "16-31"})

    @patch("os.path.exists", return_value=True)  # 模拟文件存在
    @patch("builtins.open", mock_open(read_data="0-31"))  # 模拟cpuset.cpus文件内容
    @patch("util.get_numa_cpu_mapping", return_value={0: "0-15", 1: "16-31"})  # 模拟NUMA节点
    @patch("util.is_numa_multiple", return_value=(False, None))  # 模拟NUMA亲和性检查
    def test_check_container_cpuset_cpus_no_numa_affinity(self, mock_is_numa_multiple, mock_get_numa_cpu_mapping, mock_open):
        cpu_set_path = "/sys/fs/cgroup"
        
        # 调用被测试的函数
        result, pod_nodes = check_container_cpuset_cpus(cpu_set_path)

        # 断言返回结果为False
        self.assertFalse(result)
        self.assertIsNone(pod_nodes)

    @patch("os.path.exists", return_value=False)  # 模拟文件不存在
    @patch("builtins.open", mock_open(read_data="0-31"))  # 模拟cpuset.cpus文件内容
    @patch("util.get_numa_cpu_mapping", return_value={0: "0-15", 1: "16-31"})  # 模拟NUMA节点
    def test_check_container_cpuset_cpus_file_not_found(self, mock_get_numa_cpu_mapping, mock_open):
        cpu_set_path = "/sys/fs/cgroup"
        
        # 调用被测试的函数
        result, pod_nodes = check_container_cpuset_cpus(cpu_set_path)

        # 断言文件不存在时返回False
        self.assertFalse(result)
        self.assertIsNone(pod_nodes)

    @patch("os.path.exists", return_value=True)  # 模拟文件存在
    @patch("builtins.open", mock_open(read_data=""))  # 模拟cpuset.cpus文件为空
    @patch("util.get_numa_cpu_mapping", return_value={0: "0-15", 1: "16-31"})  # 模拟NUMA节点
    @patch("util.is_numa_multiple", return_value=(False, None))  # 模拟NUMA亲和性检查
    def test_check_container_cpuset_cpus_empty_file(self, mock_is_numa_multiple, mock_get_numa_cpu_mapping, mock_open):
        cpu_set_path = "/sys/fs/cgroup"
        
        # 调用被测试的函数
        result, pod_nodes = check_container_cpuset_cpus(cpu_set_path)

        # 断言cpuset.cpus为空时返回False
        self.assertFalse(result)
        self.assertIsNone(pod_nodes)

    @patch("util.get_numa_cpu_mapping", side_effect=Exception("NUMA error"))  # 模拟异常
    def test_check_container_cpuset_cpus_exception(self, mock_get_numa_cpu_mapping):
        cpu_set_path = "/sys/fs/cgroup"
        
        # 调用被测试的函数，验证异常被抛出
        with self.assertRaises(Exception) as context:
            check_container_cpuset_cpus(cpu_set_path)

        self.assertTrue("check container cpuset.cpus error for:" in str(context.exception))


class TestLegalCgroupPath(unittest.TestCase):

    def test_legal_cgroup_path_valid(self):
        path = "/sys/fs/cgroup/docker/abc"
        cpu_set_path = "/sys/fs/cgroup/cpuset"
        cpu_mount = "/sys/fs/cgroup"
        container_paths = ["/sys/fs/cgroup/docker/xyz", "/sys/fs/cgroup/k8s/abc"]

        # 验证路径合法
        result = legal_cgroup_path(path, cpu_set_path, cpu_mount, container_paths)
        self.assertTrue(result)

    def test_legal_cgroup_path_cpu_set_path_none(self):
        path = "/sys/fs/cgroup/docker/abc"
        cpu_set_path = None  # cpu_set_path 为 None
        cpu_mount = "/sys/fs/cgroup"
        container_paths = ["/sys/fs/cgroup/docker/xyz", "/sys/fs/cgroup/k8s/abc"]

        # 验证路径合法，但由于 cpu_set_path 为 None，返回 False
        result = legal_cgroup_path(path, cpu_set_path, cpu_mount, container_paths)
        self.assertFalse(result)

    def test_legal_cgroup_path_same_as_cpu_mount(self):
        path = "/sys/fs/cgroup"
        cpu_set_path = "/sys/fs/cgroup/cpuset"
        cpu_mount = "/sys/fs/cgroup"
        container_paths = ["/sys/fs/cgroup/docker/xyz", "/sys/fs/cgroup/k8s/abc"]

        # 验证路径与 cpu_mount 相同，不合法
        result = legal_cgroup_path(path, cpu_set_path, cpu_mount, container_paths)
        self.assertFalse(result)

    def test_legal_cgroup_path_in_container_paths(self):
        path = "/sys/fs/cgroup/docker/xyz"
        cpu_set_path = "/sys/fs/cgroup/cpuset"
        cpu_mount = "/sys/fs/cgroup"
        container_paths = ["/sys/fs/cgroup/docker/xyz", "/sys/fs/cgroup/k8s/abc"]

        # 验证路径已在 container_paths 中，不合法
        result = legal_cgroup_path(path, cpu_set_path, cpu_mount, container_paths)
        self.assertFalse(result)

    def test_legal_cgroup_path_empty_path(self):
        path = ""
        cpu_set_path = "/sys/fs/cgroup/cpuset"
        cpu_mount = "/sys/fs/cgroup"
        container_paths = ["/sys/fs/cgroup/docker/xyz", "/sys/fs/cgroup/k8s/abc"]

        # 验证空路径不合法
        result = legal_cgroup_path(path, cpu_set_path, cpu_mount, container_paths)
        self.assertFalse(result)

    def test_legal_cgroup_path_no_cpu_set_path(self):
        path = "/sys/fs/cgroup/docker/abc"
        cpu_set_path = None  # 模拟没有 cpu_set_path
        cpu_mount = "/sys/fs/cgroup"
        container_paths = ["/sys/fs/cgroup/docker/xyz", "/sys/fs/cgroup/k8s/abc"]

        # 验证没有 cpu_set_path 时返回 False
        result = legal_cgroup_path(path, cpu_set_path, cpu_mount, container_paths)
        self.assertFalse(result)


class TestGetContainerCgroups(unittest.TestCase):

    @patch('util.get_cpu_cgroup_mount_point')
    @patch('util.get_all_pids')
    @patch('util.get_cgroup_path_for_pid')
    @patch('util.check_container_cpuset_cpus')
    @patch('util.is_container_path')
    @patch('os.path.exists')
    def test_get_container_cgroups(self, mock_exists, mock_is_container_path, mock_check_container_cpuset_cpus, mock_get_cgroup_path_for_pid, mock_get_all_pids, mock_get_cpu_cgroup_mount_point):
        # 设置mock函数的返回值
        
        # Mock get_cpu_cgroup_mount_point 返回路径
        mock_get_cpu_cgroup_mount_point.return_value = ('/sys/fs/cgroup/cpu', '/sys/fs/cgroup/cpuset')
        
        # Mock get_all_pids 返回PID列表
        mock_get_all_pids.return_value = ['1234', '5678']
        
        # Mock get_cgroup_path_for_pid 返回特定路径
        mock_get_cgroup_path_for_pid.side_effect = lambda pid, mount, cgroup_key: f'{mount}/{pid}/{cgroup_key}'
        
        # Mock check_container_cpuset_cpus 返回容器是NUMA亲和
        mock_check_container_cpuset_cpus.return_value = (True, [0, 1])
        
        # Mock is_container_path 返回容器路径合法
        mock_is_container_path.return_value = True
        
        # Mock os.path.exists 返回True（表示路径存在）
        mock_exists.return_value = True
        
        # 调用待测试的函数
        container_paths, container_nodes = get_container_cgroups()

        # 断言返回的容器路径列表不为空
        self.assertEqual(len(container_paths), 2)
        self.assertEqual(len(container_nodes), 2)
        
        # 断言路径是否正确
        self.assertTrue('/sys/fs/cgroup/cpu/1234/cpu' in container_paths)
        self.assertFalse('/sys/fs/cgroup/cpuset/5678/cpuset' in container_paths)

        # 断言容器路径是否正确对应NUMA节点
        self.assertEqual(container_nodes.get('/sys/fs/cgroup/cpu/1234/cpu'), [0, 1])
        self.assertEqual(container_nodes.get('/sys/fs/cgroup/cpuset/5678/cpuset'), None)

    @patch('util.get_cpu_cgroup_mount_point')
    @patch('util.get_all_pids')
    @patch('util.get_cgroup_path_for_pid')
    @patch('util.check_container_cpuset_cpus')
    @patch('util.is_container_path')
    @patch('os.path.exists')
    def test_get_container_cgroups_no_cpu_mount(self, mock_exists, mock_is_container_path, mock_check_container_cpuset_cpus, mock_get_cgroup_path_for_pid, mock_get_all_pids, mock_get_cpu_cgroup_mount_point):
        # 测试没有CPU挂载点的情况
        mock_get_cpu_cgroup_mount_point.return_value = (None, None)
        
        container_paths, container_nodes = get_container_cgroups()
        
        # 断言返回的容器路径列表为空
        self.assertEqual(container_paths, [])
        self.assertEqual(container_nodes, [])

    @patch('util.get_cpu_cgroup_mount_point')
    @patch('util.get_all_pids')
    @patch('util.get_cgroup_path_for_pid')
    @patch('util.check_container_cpuset_cpus')
    @patch('util.is_container_path')
    @patch('os.path.exists')
    def test_get_container_cgroups_no_valid_cgroup(self, mock_exists, mock_is_container_path, mock_check_container_cpuset_cpus, mock_get_cgroup_path_for_pid, mock_get_all_pids, mock_get_cpu_cgroup_mount_point):
        # 测试路径无效的情况
        mock_get_cpu_cgroup_mount_point.return_value = ('/sys/fs/cgroup/cpu', '/sys/fs/cgroup/cpuset')
        mock_get_all_pids.return_value = ['1234', '5678']
        
        # Mock get_cgroup_path_for_pid 返回特定路径
        mock_get_cgroup_path_for_pid.side_effect = lambda pid, mount, cgroup_key: f'{mount}/{pid}/{cgroup_key}'
        
        # Mock check_container_cpuset_cpus 返回容器不是NUMA亲和
        mock_check_container_cpuset_cpus.return_value = (False, [])
        
        # Mock is_container_path 返回容器路径合法
        mock_is_container_path.return_value = True
        
        # Mock os.path.exists 返回True（表示路径存在）
        mock_exists.return_value = True
        
        container_paths, container_nodes = get_container_cgroups()
        
        # 断言返回的容器路径列表为空
        self.assertEqual(container_paths, [])
        self.assertEqual(container_nodes, {})


    @patch("util.get_cpu_cgroup_mount_point", return_value=(None, None))  # 模拟没有cgroup路径
    def test_get_container_cgroups_no_cgroup(self, mock_get_cpu_cgroup_mount_point):
        container_paths, container_nodes = get_container_cgroups()
        self.assertEqual(container_paths, [])
        self.assertEqual(container_nodes, [])


class TestGetBoostedContainerCgroups(unittest.TestCase):

    @patch('util.get_container_cgroups')
    @patch("builtins.open", mock_open(read_data="100000"))
    @patch('os.path.exists')
    def test_get_boosted_container_cgroups(self, mock_exists, mock_get_container_cgroups):
        # 设置mock函数的返回值
        mock_get_container_cgroups.return_value = (['/sys/fs/cgroup/cpu/1234', '/sys/fs/cgroup/cpu/5678'],
                                                   {'/sys/fs/cgroup/cpu/1234': [0, 1], '/sys/fs/cgroup/cpu/5678': [1, 2]})
        
        # Mock os.path.exists 返回True（表示路径存在）
        mock_exists.return_value = True
        
        # 调用待测试的函数
        boosted_container_paths, boosted_container_nodes = get_boosted_container_cgroups()

        # 断言返回的容器路径
        self.assertEqual(boosted_container_paths, ['/sys/fs/cgroup/cpu/1234', '/sys/fs/cgroup/cpu/5678'])
        
        # 断言容器节点是否正确
        self.assertEqual(boosted_container_nodes, {'/sys/fs/cgroup/cpu/1234': [0, 1], '/sys/fs/cgroup/cpu/5678': [1, 2]})

    @patch('util.get_container_cgroups')
    @patch("builtins.open", mock_open(read_data="-1"))
    @patch('os.path.exists')
    def test_get_boosted_container_cgroups_invalid_path(self, mock_exists, mock_get_container_cgroups):
        # 测试无效路径（模拟路径不存在）
        mock_get_container_cgroups.return_value = (['/sys/fs/cgroup/cpu/1234'],
                                                   {'/sys/fs/cgroup/cpu/1234': [0, 1]})
        
        # Mock os.path.exists 返回False，模拟路径不存在
        mock_exists.return_value = False
        
        # 调用待测试的函数
        boosted_container_paths, boosted_container_nodes = get_boosted_container_cgroups()

        # 断言返回的容器路径为空，因为路径不存在
        self.assertEqual(boosted_container_paths, [])
        
        # 断言容器节点为空
        self.assertEqual(boosted_container_nodes, {})


class TestGetContainerInfo(unittest.TestCase):

    @patch("builtins.open", new_callable=mock_open)
    @patch('os.path.exists')
    def test_get_container_info_success(self, mock_exists, mock_open):
        # 假设容器路径和文件名
        container_path = "/sys/fs/cgroup/cpu/1234"
        info_name = "cpu.cfs_quota_us"
        
        # 模拟文件路径存在
        mock_exists.return_value = True
        
        # 模拟打开文件并返回内容
        mock_open.return_value.read.return_value = "1000"  # 模拟文件内容为 "1000"
        
        # 调用函数并断言
        result = get_container_info(container_path, info_name)
        
        # 断言返回的值应该是文件内容 "1000"
        self.assertEqual(result, "1000")
        
        # 确保文件被正确打开
        mock_open.assert_called_once_with(os.path.join(container_path, info_name), 'r')

    @patch("builtins.open", new_callable=mock_open)
    @patch('os.path.exists')
    def test_get_container_info_file_not_found(self, mock_exists, mock_open):
        # 假设容器路径和文件名
        container_path = "/sys/fs/cgroup/cpu/1234"
        info_name = "cpu.cfs_quota_us"
        
        # 模拟文件路径存在
        mock_exists.return_value = True
        
        # 模拟文件打开时抛出 FileNotFoundError
        mock_open.side_effect = FileNotFoundError("File not found")
        
        # 调用函数并断言
        result = get_container_info(container_path, info_name)
        
        # 断言返回的值应该是 None，因为文件打开失败
        self.assertIsNone(result)
        
        # 确保日志记录了警告
        with self.assertLogs(level='WARNING') as log:
            get_container_info(container_path, info_name)
            self.assertTrue("Fail to get container info" in log.output[0])

    @patch("builtins.open", new_callable=mock_open)
    @patch('os.path.exists')
    def test_get_container_info_permission_error(self, mock_exists, mock_open):
        # 假设容器路径和文件名
        container_path = "/sys/fs/cgroup/cpu/1234"
        info_name = "cpu.cfs_quota_us"
        
        # 模拟文件路径存在
        mock_exists.return_value = True
        
        # 模拟文件打开时抛出 PermissionError
        mock_open.side_effect = PermissionError("Permission denied")
        
        # 调用函数并断言
        result = get_container_info(container_path, info_name)
        
        # 断言返回的值应该是 None，因为权限错误
        self.assertIsNone(result)
        
        # 确保日志记录了警告
        with self.assertLogs(level='WARNING') as log:
            get_container_info(container_path, info_name)
            self.assertTrue("Fail to get container info" in log.output[0])

    @patch("builtins.open", new_callable=mock_open)
    @patch('os.path.exists')
    def test_get_container_info_empty_content(self, mock_exists, mock_open):
        # 假设容器路径和文件名
        container_path = "/sys/fs/cgroup/cpu/1234"
        info_name = "cpu.cfs_quota_us"
        
        # 模拟文件路径存在
        mock_exists.return_value = True
        
        # 模拟打开文件并返回空内容
        mock_open.return_value.read.return_value = ""  # 文件为空
        
        # 调用函数并断言
        result = get_container_info(container_path, info_name)
        
        # 断言返回的值应该是空字符串
        self.assertEqual(result, "")
        
        # 确保文件被正确打开
        mock_open.assert_called_once_with(os.path.join(container_path, info_name), 'r')

    @patch("builtins.open", new_callable=mock_open)
    @patch('os.path.exists')
    def test_get_container_info_file_not_exists(self, mock_exists, mock_open):
        # 假设容器路径和文件名
        container_path = "/sys/fs/cgroup/cpu/1234"
        info_name = "cpu.cfs_quota_us"
        
        # 模拟文件路径不存在
        mock_exists.return_value = False
        
        # 调用函数并断言
        result = get_container_info(container_path, info_name)
        
        # 断言返回的值应该是 None，因为文件路径不存在
        self.assertEqual(result, '')

class TestWeightedQueueSum(unittest.TestCase):

    def test_weighted_queue_sum_valid(self):
        # 正常情况：队列数据和权重一致
        queue_data = [10, 20, 30]
        queue_weight_list = [1, 2, 3]
        
        result = weighted_queue_sum(queue_data, queue_weight_list)
        
        # 计算加权平均： (10*1 + 20*2 + 30*3) / (1 + 2 + 3) = (10 + 40 + 90) / 6 = 140 / 6 = 23.3333
        self.assertEqual(result, 23.333333333333332)

    def test_weighted_queue_sum_length_mismatch(self):
        # 数据和权重长度不一致
        queue_data = [10, 20, 30]
        queue_weight_list = [1, 2]
        
        result = weighted_queue_sum(queue_data, queue_weight_list)
        
        # 应该返回 None，因为长度不一致
        self.assertIsNone(result)

    def test_weighted_queue_sum_empty_data(self):
        # 数据为空
        queue_data = []
        queue_weight_list = [1, 2, 3]
        
        result = weighted_queue_sum(queue_data, queue_weight_list)
        
        # 数据为空，应该返回 None
        self.assertIsNone(result)

    def test_weighted_queue_sum_none_in_data(self):
        # 数据中包含 None
        queue_data = [10, None, 30]
        queue_weight_list = [1, 2, 3]
        
        result = weighted_queue_sum(queue_data, queue_weight_list)
        
        # 数据中包含 None，应该返回 None
        self.assertIsNone(result)

    def test_weighted_queue_sum_zero_weight(self):
        # 总权重为 0
        queue_data = [10, 20, 30]
        queue_weight_list = [0, 0, 0]
        
        result = weighted_queue_sum(queue_data, queue_weight_list)
        
        # 总权重为 0，应该返回 0.0
        self.assertEqual(result, 0.0)

    def test_weighted_queue_sum_zero_weight_valid_data(self):
        # 数据有效，但权重为 0，不能出现除法
        queue_data = [10, 20, 30]
        queue_weight_list = [0, 0, 0]
        
        result = weighted_queue_sum(queue_data, queue_weight_list)
        
        # 总权重为 0，应该返回 0.0
        self.assertEqual(result, 0.0)


class TestReadCpuStats(unittest.TestCase):

    @patch("util.read_file")
    def test_read_cpu_stats_success(self, mock_read_file):
        # 模拟 read_file 函数返回的有效数据
        mock_read_file.return_value = {'idle': 100, 'total': 2000}
        
        # 调用函数并断言
        result = read_cpu_stats()
        
        # 断言返回的值与模拟数据一致
        self.assertEqual(result, {'idle': 100, 'total': 2000})
        
        # 确保调用了 read_file 函数
        mock_read_file.assert_called_once()

    @patch("util.read_file")
    @patch('logging.warning')
    def test_read_cpu_stats_ioerror(self, mock_warning, mock_read_file):
        # 模拟 read_file 函数抛出 IOError
        mock_read_file.side_effect = IOError("Fail to read /proc/stat")
        
        # 调用函数并断言返回 None
        result = read_cpu_stats()
        
        # 断言返回值应该是 None
        self.assertIsNone(result)
        

class TestReadFile(unittest.TestCase):

    @patch("builtins.open", mock_open(read_data="cpu  100 50 200 300 10 5 5 0 0 0 0\n"))
    def test_read_file_success(self, ):
        
        # 调用函数并断言
        result = read_file()
        
        # 计算结果：idle = 300, total = 100 + 50 + 200 + 300 + 10 + 5 + 5 + 0 + 0 + 0 = 670
        expected_result = {'idle': 300, 'total': 670}
        self.assertEqual(result, expected_result)


    @patch("builtins.open", new_callable=mock_open)
    def test_read_file_invalid_format(self, mock_file):
        # 模拟文件内容，格式不正确
        mock_file.return_value.read.return_value = "invalid data\nanother invalid line\n"
        
        # 调用函数并断言
        result = read_file()
        
        # 无符合要求的 'cpu ' 行，应该返回 None
        self.assertIsNone(result)

        # 确保文件被打开
        mock_file.assert_called_once_with('/proc/stat', 'r')


if __name__ == "__main__":
    unittest.main()
