# WAAS介绍<a name="ZH-CN_TOPIC_0000002518588852"></a>











## 项目介绍<a name="ZH-CN_TOPIC_0000002549748607"></a>

在容器超分场景下，部分容器的CPU需求可能在某些时刻超出预设最大值（例如响应周期性或者瞬时的高并发请求），即使此时计算节点上仍有空闲CPU资源，也无法调度给该容器使用，导致其性能受限。针对该场景，对该计算节点历史性能数据以及容器历史性能特征进行建模，在整机CPU资源富余的情况下，根据负载模型动态调整容器的CPU配额，提升业务性能。

虚拟化负载感知加速系统容器场景负载动态调度工具（Workload Aware Acceleration System Booster，简称WAAS Booster），主要功能是实时检测分析容器负载水平，及时响应突发高负载导致的容器CPU资源不足问题，并且通过负载感知和预测，实现全局的资源调度最优化配置。

**应用场景<a name="section92245417444"></a>**

应用于云计算场景，部署开源微服务，在单节点超分场景下（request < 2/3物理机core，limit \> CPU物理机core）高并发时，典型业务场景性能实现CPU配额根据业务负载变化设置，实现容器的负载使用的CPU资源动态最优。

**原理描述<a name="section1211183294413"></a>**

- 负载感知：通过滑动窗口和负载预测模型感知业务容器CPU负载压力。
- 动态调优：根据PID（Proportion Integration Differentiation）算法和全局资源管理进行实时CPU资源调整和平衡。

## 目录结构<a name="ZH-CN_TOPIC_0000002518229278"></a>

WAAS Booster项目全量目录层级介绍如下：

```
├─ build.sh                                     # 构建脚本
├─ Dockerfile                                   # 容器镜像构建文件（定义运行环境、依赖与启动方式）
├─ LICENSE                                      # 开源许可证文本
├─ README.md                                    # 中文/主 README
├─ README.en.md                                 # 英文 README
├─ requirements.txt                             # Python 依赖清单（pip 安装用）
├─ waas_booster.spec                            # 打包脚本所依赖的规格文件
├─ deployment/                                  # 部署相关资源的目录（面向集群/平台的部署清单）
│  └─ waasbooster.yaml                           # 用于部署的 YAML文件
│
├─ docs/                                        # 文档目录（面向安装、快速开始、用户手册与发行说明）
│  ├─ installation_guide.md                      # 安装指南：依赖、安装步骤、环境要求
│  ├─ quick_start.md                             # 快速开始：最小可用步骤/示例
│  ├─ release_notes.md                           # 发行说明：版本变更记录、特性列表
│  └─ user_guide.md                              # 用户指南：配置说明、运行方式、常见问题等
│
├─ src/                                         # 源码目录
│  └─ waasbooster/                               # 主 Python 包目录（核心业务实现）
│     ├─ boost_log.py                            # 日志封装/日志工具
│     ├─ cpu_monitor.py                          # CPU负载监控模块（采集 CPU 使用率/负载等基础指标）
│     ├─ data_collector.py                       # 数据采集模块
│     ├─ load_predictor.py                       # 负载预测模块（基于历史/当前指标估计未来负载或趋势）
│     ├─ numa_cpu_monitor.py                     # NUMA 维度 CPU 监控（按 NUMA Node 统计/采集 CPU 指标）
│     ├─ quota_calculator.py                     # quota资源计算模块（将负载/策略转成目标 quota/调节量）
│     ├─ quota_manager.py                        # quota资源全局管理模块
│     ├─ quota_updater.py                        # quota资源更新模块
│     ├─ util.py                                 # 通用工具函数
│     ├─ waasbooster.service                     # systemd 服务单元文件
│     └─ waas_booster.py                         # 项目主入口/主流程（组装各模块，运行与调度）
│
└─ test/                                        # 测试目录
   ├─ cov.py                                     # 用于运行所有测试脚本，计算总体测试覆盖率的脚本
   └─ waasbooster/                               
      ├─ test_cpu_monitor.py                     # cpu_monitor.py 的单元测试
      ├─ test_data_collector.py                  # data_collector.py 的单元测试
      ├─ test_load_predictor.py                  # load_predictor.py 的单元测试
      ├─ test_numa_cpu_monitor.py                # numa_cpu_monitor.py 的单元测试
      ├─ test_quota_calculator.py                # quota_calculator.py 的单元测试
      ├─ test_quota_manager.py                   # quota_manager.py 的单元测试
      ├─ test_quota_updater.py                   # quota_updater.py 的单元测试
      ├─ test_util.py                            # util.py 的单元测试
      └─ test_waas_booster.py                    # waas_booster.py 主流程部分的单元测试
```

## 版本说明<a name="ZH-CN_TOPIC_0000002549749037"></a>

WAAS Booster的版本说明包含WAAS Booster的软件版本配套关系和软件包下载以及每个版本的特性变更说明，具体请参见[版本说明书](docs/zh/release_notes.md)。

## 约束与限制<a name="ZH-CN_TOPIC_0000002549869041"></a>

- 规格要求

    WAAS Booster目前仅针对使用鲲鹏920系列处理器的服务器上的容器进行调优，不支持对其他场景进行调优。

- 对系统的影响

    系统参数的设置仅对部署在容器中的在线应用服务生效，对其他应用的影响不在WAAS Booster的负责范围内，WAAS Booster调优任务停止后，容器相关参数将恢复到WAAS Booster调优前状态。

- 容器限制

    WAAS Booster依赖容器cgroup底层cpu.cfs\_quota\_us等接口实现调整，需要确保被调优容器能够访问cgroup底层接口、被调优容器未单独指定CPU（允许绑定NUMA），并且cpu.cfs\_quota\_us数值非-1。

## 环境部署<a name="ZH-CN_TOPIC_0000002518389190"></a>

WAAS Booster是一个专为容器化环境设计的负载动态调度工具，根据不同的部署环境，WAAS Booster提供了两种主要的部署方式：RPM部署和K8s Pod部署。安装指南提供兼容性信息的内容，包括支持的模型清单、支持的框架等，具体请参见[安装指南](docs/zh/installation_guide.md)。

## 快速入门<a name="ZH-CN_TOPIC_0000002518229280"></a>

WAAS Booster的快速入门，包括快速安装、工具使用等，具体请参见[快速入门](docs/zh/quick_start.md)。

## 用户指南<a name="ZH-CN_TOPIC_0000002549749039"></a>

WAAS Booster的用户指南，包括详细的工具使用教程等，具体请参见[用户指南](docs/zh/user_guide.md)。

## 贡献声明<a name="ZH-CN_TOPIC_0000002549869043"></a>

如果使用过程中有任何问题，或者需要反馈特性需求和bug报告，可以提交issue联系我们，具体贡献方法可参考[这里](https://gitcode.com/boostkit/community/blob/master/docs/contributor/contributing.md)。

## 免责声明<a name="ZH-CN_TOPIC_0000002518389192"></a>

**致WAAS Booster使用者**

- 本工具仅供调试和开发之用，使用者需自行承担使用风险，并理解以下内容：
    - 数据处理及删除：用户在使用本工具过程中产生的数据属于用户责任范畴。建议用户在使用完毕后及时删除相关数据，以防信息泄露。
    - 数据保密与传播：使用者了解并同意不得将通过本工具产生的数据随意外发或传播。对于由此产生的信息泄露、数据泄露或其他不良后果，本工具及其开发者概不负责。
    - 用户输入安全性：用户需自行保证输入的命令行的安全性，并承担因输入不当而导致的任何安全风险或损失。对于输入命令行不当所导致的问题，本工具及其开发者概不负责。

- 免责声明范围：本免责声明适用于所有使用本工具的个人或实体。使用本工具即表示您同意并接受本声明的内容，并愿意承担因使用该功能而产生的风险和责任，如有异议请停止使用本工具。
- 在使用本工具之前，请**谨慎阅读并理解以上免责声明的内容**。对于使用本工具所产生的任何问题或疑问，请及时联系开发者。

**致数据所有者**

如果您不希望您的模型或数据集等信息在WAAS Booster中被提及，或希望更新WAAS Booster中有关的描述，请在GitCode提交issue，我们将根据您的issue要求删除或更新您相关描述。衷心感谢您对WAAS Booster的理解和贡献。

## License<a name="ZH-CN_TOPIC_0000002518229282"></a>

WAAS Booster采用Apache License 2.0许可证，具体开源协议请参见[LICENSE](https://gitcode.com/BoostKit/waas/blob/waasbooster/LICENSE)。

本项目的文档适用于CC-BY 4.0许可证，具体请参见[LICENSE](docs/zh/LICENSE)。