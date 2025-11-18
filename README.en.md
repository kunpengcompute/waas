# 项目介绍
WAASAgent是鲲鹏自研的负载感知加速系统组件（Workload Aware Acceleration System Agent, 简称WAAS Agent），通过自动感知系统上运行的业务负载，匹配当前业务的最优化配置。
# 版本说明
|Kunpeng WAAS Agent | 特性 |
|---|---|
| v1.0.0 | 首发版本，支持微架构参数调优 |
# 软件部署
## 调优工具编译
1. 进入内核驱动目录
```
cd src\prf\ko
```
2. 编译内核驱动
```
make
```
* 注意，执行该步骤要求系统上存在目标内核的header文件，在openEuler系统上可以通过安装`kernel.src`完成。
```
yum install kernel.src
```
或者在Makefile中手动指定内核源码
```
KERNAL_DIR=Your/Kernel/Source
```
3. 编译调优工具
1. 进入工具目录
```
cd src\prf\regtool
```
2. 编译工具
```
mkdir build && cd build
cmake ..
make install
```

## 服务部署
1. 在安装节点启动WAAS Agent
```
systemctl start waasagent
```
2. 查看WAAS Agent服务状态
```
systemctl status waasagent
```
若回显中显示服务状态为`Active: active(running)`，则表示启动成功。

# 贡献指南
如果使用过程中有任何问题，或者需要反馈特性需求和bug报告，可以提交issue联系我们，具体贡献方法可参考[这里](https://gitcode.com/boostkit/community/blob/master/docs/contributor/contributing.md)。

# 许可证书
WAAS Agent主导开源，具体开源协议类型参考[LICENSE](https://gitcode.com/boostkit/waas/blob/waasagent/LICENSE)。