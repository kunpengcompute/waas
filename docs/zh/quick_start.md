# 快速入门<a name="ZH-CN_TOPIC_0000002550231069"></a>

## 工具简介<a name="ZH-CN_TOPIC_0000002549747753"></a>

虚拟化负载感知加速系统容器场景负载动态调度工具（Workload Aware Acceleration System Booster，简称WAAS Booster），主要功能是实时检测分析容器负载水平，及时响应突发高负载导致的容器CPU资源不足问题，并且通过负载感知和预测，实现全局的资源调度最优化配置。


## 工具安装<a name="ZH-CN_TOPIC_0000002550143105"></a>

此处以K8s部署为例，服务以daemonset pod的形式，从主节点分发到各计算节点上，部署起来共分为两步：镜像构建和pod部署。

1. 拉取导入基础Python镜像。
    1. 此处要求能够访问Docker Hub拉取镜像，并且能够使用pip拉取依赖。

        拉取python:3.9.9-slim镜像。

        ```
        docker pull python:3.9.9-slim 
        ```

    2. 查看镜像列表。

        ```
        docker images 
        ```

        若回显中有名为python，TAG为3.9.9-slim镜像出现，则拉取成功。

2. 下载WAAS Booster开源代码包。

    ```
    git clone -b waasbooster https://gitcode.com/BoostKit/waas.git 
    ```

3. 构建镜像。

    1. 进入waas文件夹。

        ```
        cd waas-waasbooster 
        ```

    2. 构建编译镜像。

        ```
        docker build -t waasbooster:1.0.0 . 
        ```

        命令中的“waasbooster”为构建后的镜像名，“1.0.0”为镜像TAG。 注意此处需要pip拉取依赖，如果需要使用pip代理，可使用以下命令指定代理服务器。

        ```
        docker build --build-arg PIP_PROXY=http://username:password@http.example.com:8080 -t waasbooster:1.0.0 . 
        ```

        若有特定pip镜像源，也可以指定pip镜像源。

        ```
        docker build \     
        --build-arg PIP_MIRROR=http://mirror.example.com/pypi/simple \     
        --build-arg PIP_TRUST_HOST=http://mirror.example.com \     
        -t waasbooster:1.0.0 .
        ```

    3. 查看镜像列表。

        ```
        docker images 
        ```

        回显中若有名为waasbooster，TAG为1.0.0的镜像出现，则构建成功。


## 工具使用<a name="ZH-CN_TOPIC_0000002550183111"></a>

此处以K8s部署为例，部署前需要确保部署节点上存在构建好的WAAS Booster镜像，或者能够拉取到WAAS Booster镜像。

1. 拷贝部署文件

    将waas-waasbooster/deployment目录下的waasbooster.yaml文件拷贝至K8s的Master节点。

2. 创建WAAS Booster Pod。

    ```
    kubectl apply -f waasbooster.yaml 
    ```

    若回显中有如下内容，则创建成功。

    ```
    daemonset.apps/waasbooster-daemon created
    ```


