# WAAS Introduction











## Project Overview<a name="EN-US_TOPIC_0000002549748607"></a>

In container overcommitment scenarios, some containers may require CPU resources beyond the preset maximum value \(for example, when responding to periodic or instantaneous high-concurrency requests\). Despite idle CPU resources on the compute node, the resources cannot be scheduled to the containers, resulting in limited performance. In this scenario, the historical performance data of the compute node and the historical performance features of containers can be modeled. If the node-wide CPU resources are sufficient, the CPU quota of containers can be dynamically adjusted based on the load model to improve service performance.

Workload Aware Acceleration System Booster \(WAAS Booster\) is a dynamic scheduling tool for containers in virtualization scenarios. It can detect and analyze container loads in real time, respond to CPU resource insufficiency caused by burst loads, and optimize global resource scheduling through load awareness and prediction.

**Application Scenarios<a name="section92245417444"></a>**

This tool is used to deploy open source microservices in cloud computing scenarios. In single-node overcommitment scenarios \(**request**  < two-thirds of physical CPU cores;  **limit**  \> physical CPU cores\), when high concurrency is required, the CPU quota of typical services is dynamically adjusted based on service loads to ensure optimal CPU resource usage of containers.

**Principles<a name="section1211183294413"></a>**

- Load awareness: The system senses the CPU load pressure of service containers through the sliding window and load prediction model.
- Dynamic tuning: The Proportion Integration Differentiation \(PID\) algorithm and global resource management are used to adjust and balance CPU resources in real time.

## Directory Structure<a name="EN-US_TOPIC_0000002518229278"></a>

The full project directory structure for WAAS Booster is as follows:

```
├─ build.sh                                     # Build script
├─ Dockerfile                                   # Container image build file (defining the operating environment, dependencies, and startup mode)
├─ LICENSE                                      # Open source license text
├─ README.md                                    # Main README (Chinese)
├─ README.en.md                                 # README (English)
├─ requirements.txt                             # Python dependency list (for installation using pip)
├─ waas_booster.spec                            # Specification file on which the packaging script depends
├─ deployment/                                  # Directory of deployment-related resources (deployment list for clusters/platforms)
│  └─ waasbooster.yaml                           # YAML file for deployment
│
├─ docs/                                        # Document directory (installation guide, quick start, user guide, and release notes)
│  ├─ installation_guide.md                      # Installation guide: dependencies, installation procedure, and environment requirements
│  ├─ quick_start.md                             # Quick start: minimum steps for project running/examples
│  ├─ release_notes.md                           # Release notes: version change history and feature list
│  └─ user_guide.md                              # User guide: configuration description, operating mode, and FAQs
│
├─ src/                                         # Source code directory
│  └─ waasbooster/                               # Main Python package directory (core service implementation)
│     ├─ boost_log.py                            # Log encapsulation/log tool
│     ├─ cpu_monitor.py                          # CPU load monitoring module (collecting basic metrics such as CPU usage and load)
│     ├─ data_collector.py                       # Data collection module
│     ├─ load_predictor.py                       # Load prediction module (estimating the future load or trend based on historical/current metrics)
│     ├─ numa_cpu_monitor.py                     # NUMA-based CPU monitoring (collecting CPU metrics by NUMA node)
│     ├─ quota_calculator.py                     # Quota calculation module (converting the load/policy into the target quota/adjustment value)
│     ├─ quota_manager.py                        # Global quota management module
│     ├─ quota_updater.py                        # Quota update module
│     ├─ util.py                                 # Common utility functions
│     ├─ waasbooster.service                     # systemd service unit file
│     └─ waas_booster.py                         # Main entry/process of the project (module integration, running, and scheduling)
│
└─ test/                                        # Test directory
   ├─ cov.py                                     # Script for running all test scripts and calculating the overall test coverage
   └─ waasbooster/                               
      ├─ test_cpu_monitor.py                     # Unit test for cpu_monitor.py
      ├─ test_data_collector.py                  # Unit test for data_collector.py
      ├─ test_load_predictor.py                  # Unit test for load_predictor.py
      ├─ test_numa_cpu_monitor.py                # Unit test for numa_cpu_monitor.py
      ├─ test_quota_calculator.py                # Unit test for quota_calculator.py
      ├─ test_quota_manager.py                   # Unit test for quota_manager.py
      ├─ test_quota_updater.py                   # Unit test for quota_updater.py
      ├─ test_util.py                            # Unit test for util.py
      └─ test_waas_booster.py                    # Unit test for the main process of waas_booster.py
```

## Release Notes<a name="EN-US_TOPIC_0000002549749037"></a>

The release notes of WAAS Booster describe the software version mapping, software package download, and feature changes of each version. For details, see [Release Notes](docs/en/release_notes.md).

## Constraints<a name="EN-US_TOPIC_0000002549869041"></a>

- Specifications

    WAAS Booster is only available for tuning containers on servers equipped with Kunpeng 920 series processors.

- Impact on the system

    The system parameter configuration applies to only online application services deployed in containers. WAAS Booster is not responsible for any impact on other applications. After the tuning task of WAAS Booster is stopped, the container parameters are restored to the status before tuning.

- Container constraints

    WAAS Booster depends on the cgroup underlying interfaces such as  **cpu.cfs\_quota\_us**  to implement adjustment. Ensure that the container to be tuned can access the cgroup underlying interfaces, no CPU is separately specified \(NUMA node binding is allowed\) for the container to be tuned, and the value of  **cpu.cfs\_quota\_us**  is not  **–1**.

## Environment Deployment<a name="EN-US_TOPIC_0000002518389190"></a>

WAAS Booster is a dynamic load-based scheduling tool designed for containerized environments. Depending on deployment environments, WAAS Booster can be deployed using either RPM or Kubernetes pods. The installation guide provides compatibility information, including the list of supported models and frameworks. For details, see  [Installation Guide](docs/en/installation_guide.md).

## Quick Start<a name="EN-US_TOPIC_0000002518229280"></a>

The quick start guide of WAAS Booster provides instructions for quick installation and usage. For details, see  [Tool Overview](docs/en/quick_start.md).

## User Guide<a name="EN-US_TOPIC_0000002549749039"></a>

The user guide of WAAS Booster provides a detailed tool usage tutorial. For details, see  [Tool Usage](docs/en/user_guide.md).

## Contribution Statement<a name="EN-US_TOPIC_0000002549869043"></a>

If you have any questions or want to provide feedback on feature requirements and bug reports, you can submit an issue. For details, see the  [contribution guideline](https://gitcode.com/boostkit/community/blob/master/docs/contributor/contributing.md).

## Disclaimer<a name="EN-US_TOPIC_0000002518389192"></a>

**To WAAS Booster users**

- This tool is intended solely for debugging and development. You are responsible for any risks and should carefully review the following information:
    - Data processing and deletion: Users are responsible for managing and deleting any data generated while using this tool. You are advised to promptly delete any related data after use to prevent information leaks.
    - Data confidentiality and transmission: Users understand and agree not to share or transmit any data generated by this tool. Neither the tool nor its developers are responsible for any information leaks, data breaches, or other negative consequences.
    - User input security: Users are responsible for the security of any commands they enter and for any risks or losses resulting from improper input. The tool and its developers are not liable for issues caused by incorrect command usage.

- Disclaimer scope: This disclaimer applies to all individuals and entities using this tool. By using the tool, you acknowledge and accept this statement and assume all risks and responsibilities arising from its use. If you do not agree, please stop using the tool immediately.
- Before using this tool,  **please read and understand the preceding disclaimer**. If you have any questions, contact the developer.

**To data owners**

If you do not want your model or dataset to be mentioned in WAAS Booster, or if you wish to update its description, please submit an issue on GitCode. We will delete or update your description according to your request. Thank you for your understanding and contribution to WAAS Booster.

## License<a name="EN-US_TOPIC_0000002518229282"></a>

WAAS Booster is licensed under the Apache License 2.0. For the full license text, see  [LICENSE](https://gitcode.com/BoostKit/waas/blob/waasbooster/LICENSE).

