# 用户指南<a name="ZH-CN_TOPIC_0000002550231305"></a>

## 工具使用<a name="ZH-CN_TOPIC_0000002518228422"></a>

### RPM使用<a name="ZH-CN_TOPIC_0000002549868179"></a>

用户通过WAAS Booster支持的命令行与WAAS Booster进行交互。

WAAS Booster支持的命令行如下所示。

- 启动WAAS Booster。

    ```
    systemctl start waasbooster
    ```

- 关闭WAAS Booster。

    ```
    systemctl stop waasbooster
    ```

- 查看WAAS Booster对容器的调整动作。

    ```
    tail -f /var/log/waasbooster.log
    ```

>![](public_sys-resources/icon-note.gif) **说明：** 
>本工具启动后可全自动实现容器场景负载动态调度功能，无须进行额外操作，用户若想查看调整过程可通过日志内容查看。

用户通过WAAS Booster支持的命令行与WAAS Booster进行交互。
### K8s Pod使用<a name="ZH-CN_TOPIC_0000002518228420"></a>

用户通过kubectl进行WAAS Booster Pod的创建与销毁。Pod创建后自动启动WAAS Booster服务，Pod销毁后自动关闭WAAS Booster服务。

假设WAAS Booster Pod配置文件名为waasbooster.yaml，以此为例介绍K8s Pod的常用操作。

>![](public_sys-resources/icon-note.gif) **说明：** 
>以下所有操作均在Master节点进行。

- 创建WAAS Booster Pod。

    ```
    kubectl apply -f waasbooster.yaml
    ```

- 销毁WAAS Booster Pod。

    ```
    kubectl delete -f waasbooster.yaml
    ```

- 查看WAAS Booster对容器的调整动作。

    假设目标Pod名为waasbooster-daemon-rhwdz。

    1. 若持续监控，可以进入容器查看日志。
        1. 进入容器。

            ```
            kubectl exec -it waasbooster-daemon-rhwdz bash
            ```

        2. 查看日志。

            ```
            tail -f /var/log/waasbooster.log
            ```

    2. 若临时查看，则可以通过K8s日志查看。

        ```
        kubectl logs waasbooster-daemon-rhwdz
        ```



## 安全管理<a name="ZH-CN_TOPIC_0000002518228414"></a>

### 目录和文件权限<a name="ZH-CN_TOPIC_0000002549748175"></a>

针对RPM部署方式，WAAS Booster目录和文件的权限说明如[**表 1** WAAS Booster目录和文件的权限说明](#WAAS Booster目录和文件的权限说明)所示。

**表 1** WAAS Booster目录和文件的权限说明<a id="WAAS Booster目录和文件的权限说明"></a>

|目录或文件名|位置|用户权限|文件权限|说明|
|--|--|--|--|--|
|/usr/local/waasbooster|/usr/local/waasbooster|waas:waas|644|WAAS Booster安装目录|
|/var/log/waasbooster.log|/var/log/waasbooster.log|root:root|640|WAAS Booster产生的日志|
|/var/waasbooster/|/var/waasbooster|root:root|750|WAAS Booster的数据存储路径|
|/var/run/waasbooster_manager/|/var/run/waasbooster_manager/|root:root|644|WAAS Booster的临时文件存储路径|


针对K8s Pod部署方式，WAAS Booster目录和文件的权限说明如[**表 2** K8s WAAS Booster Pod目录和文件的权限说明](#K8s WAAS Booster Pod目录和文件的权限说明)所示。

**表 2** K8s WAAS Booster Pod目录和文件的权限说明<a id="K8s WAAS Booster Pod目录和文件的权限说明"></a>

|目录或文件名|位置|用户权限|文件权限|说明|
|--|--|--|--|--|
|/app/|/app/|root:root|644|WAAS Booster安装目录|
|/var/log/waasbooster.log|/var/log/waasbooster.log|root:root|640|WAAS Booster产生的日志|
|/var/run/waasbooster_manager/|/var/run/waasbooster_manager/|root:root|644|WAAS Booster的临时文件存储路径|



### 日志管理<a name="ZH-CN_TOPIC_0000002549868175"></a>

>![](public_sys-resources/icon-notice.gif) **须知：** 
>请不要误删除WAAS Booster产生的所有日志文件。

- 运行日志输出到操作系统日志文件中。
- WAAS Booster的日志输出文件为“/var/log/waasbooster.log“。



