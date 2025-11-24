# 项目介绍
WAAS Booster是鲲鹏自研的虚拟化负载感知加速系统容器场景负载感知动态调度工具（Workload Aware Acceleration System Booster, 简称WAAS Booster），通过实时监测分析容器负载水平，及时响应突发高负载导致的容器CPU资源不足问题，并且通过负载感知和预测，实现全局的资源调度最优化配置。
# 版本说明
|Kunpeng WAAS Booster | 特性 |
|---|---|
| v1.0.0 | 首发版本，支持容器实时负载感知和CPU资源动态调度 |
# 环境部署
本项目支持两种部署方式：K8s部署和RPM部署。
## K8s部署
K8s部署时，服务以daemonset pod的形式，从主节点分发到各计算节点上，部署起来共分为两步：镜像构建和pod部署。
### 镜像构建
#### 步骤1 拉取导入基础Python镜像。

此处要求能够访问Docker Hub拉取镜像，并且能够使用pip拉取依赖。

1.   拉取python:3.9.9-slim镜像。
```
docker pull python:3.9.9-slim
```
2.  查看镜像列表。
```
docker images
```
若回显中有名为python，TAG为3.9.9-slim镜像出现，则拉取成功。

#### 步骤2 下载WAAS Booster开源代码包。
```
git clone -b waasbooster https://gitcode.com/BoostKit/waas.git
```
#### 步骤3 构建镜像
1. 进入waas文件夹。
```
cd waas-waasbooster
```
2. 构建编译镜像。
```
docker build -t waasbooster:1.0.0 .
```
命令中的"waasbooster"为构建后的镜像名，"1.0.0"为镜像TAG。
注意此处需要pip拉取依赖，如果需要使用pip代理，可使用以下命令指定代理服务器。
```
docker build --build-arg PIP_PROXY=http://username:password@http.example.com:8080 -t waasbooster:1.0.0 .
```
若有特定pip镜像源，也可以指定PIP镜像源。
```
docker build \
    --build-arg PIP_MIRROR=http://mirror.example.com/pypi/simple \
    --build-arg PIP_TRUST_HOST=http://mirror.example.com \
    -t waasbooster:1.0.0 .
```
3. 查看镜像列表
```
docker images
```
回显中若有名为waasbooster，TAG为1.0.0的镜像出现，则构建成功。

## RPM部署
具体安装指南可参考[链接](https://www.hikunpeng.com/document/detail/zh/kunpengcpfs/appAccelFeatures/waas/kunpeng_waasbooster_zn_28_009.html)。

# 快速上手
## pod部署
部署前需要确保部署节点上存在构建好的WAAS Booster镜像，或者能够拉取到WAAS Booster镜像。
#### 步骤1 拷贝部署文件
将`waas-waasbooster/deployment`目录下的`waasbooster.yaml`文件拷贝至K8s的Master节点。
#### 步骤2 创建WAAS Booster Pod。
```
kubectl apply -f waasbooster.yaml
```
若回显中由于如下内容，则创建成功。
```
daemonset.apps/waasbooster-daemon created
```
## RPM部署
#### 步骤1 在安装节点启动WAAS Booster
```
systemctl start waasbooster
```
#### 步骤2 查看WAAS Booster服务状态
```
systemctl status waasbooster
```
若回显中显示服务状态为`Active: active(running)`，则表示启动成功。

# 贡献指南
如果使用过程中有任何问题，或者需要反馈特性需求和bug报告，可以提交issue联系我们，具体贡献方法可参考[这里](https://gitcode.com/boostkit/community/blob/master/docs/contributor/contributing.md)。

# 许可证书
WAAS Booster主导开源，具体开源协议类型参考[LICENSE](https://gitcode.com/BoostKit/waas/blob/waasbooster/LICENSE)。
# 参考文档
[安装指南](https://www.hikunpeng.com/document/detail/zh/kunpengcpfs/appAccelFeatures/waas/kunpeng_waasbooster_zn_28_002.html)