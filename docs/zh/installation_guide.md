# 安装指南<a name="ZH-CN_TOPIC_0000002518384328"></a>

## 部署说明<a name="ZH-CN_TOPIC_0000002518384330"></a>

WAAS Booster是一个专为容器化环境设计的负载动态调度工具，根据不同的部署环境，WAAS Booster提供了两种主要的部署方式：RPM部署和K8s Pod部署。下面将详细介绍这两种部署方式的区别及其适用场景。

1. RPM部署
    1. 业务节点数量较少：适用于业务节点数量较少的环境，例如小型企业或初创公司，这些环境中通常不需要复杂的资源管理和调度。
    2. 未使用Kubernetes搭建集群：适用于尚未采用Kubernetes进行容器化管理的环境，这些环境可能使用传统的虚拟机或物理机部署应用。
    3. 不需要频繁人工维护调试：适用于对运维自动化要求不高，且不需要频繁进行人工维护和调试的场景。RPM物理机部署可以减少对自动化运维工具的依赖，简化运维流程。

2. K8s Pod部署
    1. 业务节点数量较多：适用于业务节点数量较多的环境，例如大型企业或互联网公司，这些环境中通常需要高效的资源管理和调度能力。
    2. 业务基于Kubernetes搭建集群：适用于已经使用Kubernetes进行容器化管理的环境，这些环境可以充分利用Kubernetes的自动化部署、扩展和管理功能。
    3. 需要高度自动化运维：适用于对运维自动化要求较高的场景，K8s Pod部署可以在Master节点实现WAAS Booster服务Pod的集中创建、管理和销毁，提高系统的可靠性和可用性。

用户在选择部署方式时，应根据自身的业务需求、技术栈和运维能力，综合考虑上述特点和适用场景，选择最适合的部署方式。

>![](public_sys-resources/icon-note.gif) **说明：** 
>Master节点为K8s集群中的管理节点，业务节点为K8s集群中部署具体业务的节点。

WAAS Booster是一个专为容器化环境设计的负载动态调度工具，根据不同的部署环境，WAAS Booster提供了两种主要的部署方式：RPM部署和K8s Pod部署。下面将详细介绍这两种部署方式的区别及其适用场景。
## 环境要求<a name="ZH-CN_TOPIC_0000002549864175"></a>

本文基于openEuler操作系统提供指导，在正式操作前请确保软硬件均满足要求。

**操作系统和软件要求<a name="section21485361307"></a>**

操作系统和软件要求如[**表 1** 操作系统和软件要求](#操作系统和软件要求)所示。

**表 1** 操作系统和软件要求<a id="操作系统和软件要求"></a>

|项目|版本|获取方式|
|--|--|--|
|OS|openEuler 20.03 LTS SP3|[获取链接](https://www.openeuler.org/zh/download/archive/detail/?version=openEuler%2020.03%20LTS%20SP3)|
|OS|openEuler 22.03 LTS SP4|[获取链接](https://www.openeuler.org/zh/download/archive/detail/?version=openEuler%2022.03%20LTS%20SP4)|
|Python|3.9.9或以上版本|[获取链接](https://www.python.org/downloads/release/python-399/)|
|Miniconda3|py310_25.1.1-2-Linux-aarch64|[获取链接](https://repo.anaconda.com/miniconda/Miniconda3-py310_25.1.1-2-Lniux-aarch64.sh)|
|WAAS Booster所需依赖包|安装手册中的指定版本|通过配置Yum源和pip源方式安装|
|WAAS Booster开源代码包|1.0.0|[获取链接](https://gitcode.com/boostkit/waas)|


>![](public_sys-resources/icon-note.gif) **说明：** 
>WAAS Booster仅支持部署于业务节点。

## RPM部署WAAS Booster<a name="ZH-CN_TOPIC_0000002518224408"></a>

### 安装运行环境<a name="ZH-CN_TOPIC_0000002518384324"></a>

为后续部署WAAS Booster提供必要的依赖和环境，需要安装其所需的依赖包。

>![](public_sys-resources/icon-note.gif) **说明：** 
>root用户可直接执行下述命令；普通用户执行本小节的操作时，需要在下述命令前加**sudo**提高权限。

1. 安装软件运行必要依赖。

    ```bash
    yum install -y python rpm-build cpio
    ```

2. 下载[Miniconda3安装脚本](https://repo.anaconda.com/miniconda/Miniconda3-py310_25.1.1-2-Linux-aarch64.sh)。
3. 按默认安装Miniconda3。

    ```
    sh Miniconda3-py310_25.1.1-2-Linux-aarch64.sh
    ```

4. 在“/etc/profile“里配置安装好的Miniconda3的二进制路径。
    1. 打开文件。

        ```
        vim /etc/profile
        ```

    2. 按“i“进入编辑模式，在文件末尾添加如下内容。

        ```
        export PATH=$PATH:/root/miniconda3/bin/
        ```

    3. 按“Esc“键退出编辑模式，输入 **:wq!**，按“Enter“键保存退出文件。
    4. 使文件生效。

        ```
        source /etc/profile
        ```

5. 初始化conda环境。

    ```
    conda init
    ```

6. 退出当前SSH窗口，再重新连接SSH窗口，确保conda生效。

    >![](public_sys-resources/icon-note.gif) **说明：** 
    >如果重新进入SSH窗口显示为在base环境中，则需要使用命令**conda deactivate**退出base环境，如果不在则无需操作。

7. 使用conda创建Python环境，例如环境命名为waasbooster\_env。
    1. 添加conda-forge channel。

        ```
        conda config --add channels conda-forge
        ```

    2. 使用conda-forge创建python环境。

        ```
        conda create -n waasbooster_env python=3.9.9 -c conda-forge
        ```

8. <a name="li3962559112"></a>查看waasbooster\_env环境路径。

    ```
    conda env list
    ```

    回显如下图所示：

    ![](figures/zh-cn_image_0000002518384334.png)

    >![](public_sys-resources/icon-note.gif) **说明：** 
    >-   如果步骤[8](#li3962559112)返回内容中waasbooster\_env对应路径不是“/usr/local/waasbooster/bin/python3“，请拷贝其内容，用于后续部署WAAS Booster后修改其配置文件内容；
    >-   如果返回内容是“/usr/local/waasbooster/bin/python3“，则忽略修改步骤。

9. 执行命令进入指定虚拟环境。

    ```
    conda activate waasbooster_env
    ```

10. 获取WAAS Booster开源代码包waas-waasbooster.zip，获取链接请参见[操作系统和软件要求](#操作系统和软件要求)，将waas-waasbooster.zip上传至服务器自定义路径并解压。

    ```
    unzip waas-waasbooster.zip
    ```

11. 执行命令安装依赖。

    ```
    pip3 install -r waas-waasbooster/requirements.txt
    ```

### 制作WAAS Booster RPM包<a name="ZH-CN_TOPIC_0000002549744183"></a>

制作WAAS Booster RPM包。

1. 编译构建WAAS Booster RPM。

    ```
    sh waas-waasbooster/build.sh build_booster_package
    ```

2. 编译结束后，进入“waas-waasbooster/output“确认RPM包是否构建成功。若存在waasbooster-1.0.0.aarch64.rpm的文件则表示RPM包构建成功。

### 部署WAAS Booster<a name="ZH-CN_TOPIC_0000002549864177"></a>

部署WAAS Booster，包括安装WAAS Booster的安装包和设置环境变量。

1. 安装WAAS Booster。

    >![](public_sys-resources/icon-note.gif) **说明：** 
    >root用户可直接执行下述命令；普通用户执行本步骤的操作时，需要在下述命令前加**sudo**提高权限。

    ```
    rpm -ivh waasbooster-1.0.0.aarch64.rpm
    ```

    安装成功后回显如下图所示。

    ![](figures/zh-cn_image_0000002518224418.png)

2. 修改WAAS Booster的service文件。
    1. 查看waasbooster\_env环境路径。

        ```
        conda env list
        ```

        例如waasbooster\_env对应的返回值为“/root/miniconda3/envs/waasbooster\_env“。

    2. 打开“/usr/lib/systemd/system/waasbooster.service“文件。

        ```
        vim /usr/lib/systemd/system/waasbooster.service
        ```

    3. 按“i“进入编辑模式，修改启动脚本。

        将

        ```
        ExecStart=/usr/local/waasbooster/bin/python3 /usr/local/waasbooster/cpu_booster.py
        ```

        修改为

        ```
        ExecStart=/root/miniconda3/envs/waasbooster_env/bin/python3 /usr/local/waasbooster/waas_booster.py
        ```

        即将“/usr/local/waasbooster/bin/python3“中的“/usr/local/waasbooster“修改为**conda env list**中waasbooster\_env对应的回显路径。

    4. 按“Esc“键退出编辑模式，输入 **:wq!**，按“Enter“键保存退出文件。

3. 重新加载systemctl的daemon。

    ```
    systemctl daemon-reload
    ```

### 运行WAAS Booster<a name="ZH-CN_TOPIC_0000002549744189"></a>

安装WAAS Booster完成后，需要先启动WAAS Booster，才能使用WAAS Booster服务的功能。

>![](public_sys-resources/icon-note.gif) **说明：** 
>root用户可直接执行下述操作步骤中的命令；普通用户执行本章节的操作时，需要在下述每个命令前加**sudo**提高权限。

**启动WAAS Booster<a name="section0388141123110"></a>**

1. 使用管理员账号登录WAAS Booster安装节点。
2. 在安装节点启动WAAS Booster。

    ```
    systemctl start waasbooster
    ```

3. 查看WAAS Booster状态。

    ```
    systemctl status waasbooster
    ```

    出现类似如下回显信息，状态为**Active: active（running）**，即表示启动成功。

    ![](figures/zh-cn_image_0000002549864187.png)

**停止WAAS Booster<a name="section31589018432"></a>**

>![](public_sys-resources/icon-notice.gif) **须知：** 
>停止WAAS Booster之前，需要保证所有正在运行的调优任务都已经停止。

1. 使用管理员账号登录WAAS Booster节点。
2. 在安装节点停止WAAS Booster。

    ```
    systemctl stop waasbooster
    ```

3. 查看WAAS Booster是否停止。

    ```
    systemctl status waasbooster
    ```

    出现类似如下回显状态，状态为**Active: inactive \(dead\)**，即表示停止成功。

    ![](figures/zh-cn_image_0000002549744195.png)

### （可选）卸载WAAS Booster<a name="ZH-CN_TOPIC_0000002518224414"></a>

当不再需要使用WAAS Booster时，可以卸载WAAS Booster。

>![](public_sys-resources/icon-notice.gif) **须知：** 
>-   当前步骤仅供需要卸载WAAS Booster时参考，不属于部署WAAS Booster的必要操作步骤。
>-   WAAS Booster默认安装路径在“/usr/local/waasbooster/“下，卸载后该路径中所有文件会被删除。
>-   卸载结束后，建议用户手动删除安装包与安装日志，日志位于“/var/log/waasbooster.log“。

1. 停止WAAS Booster。

    ```
    systemctl stop waasbooster
    ```

2. 卸载WAAS Booster。

    ```
    rpm -e waasbooster
    ```

### （可选）制作独立WAAS Booster RPM<a name="ZH-CN_TOPIC_0000002518224412"></a>

由于某些部署环境不支持网络连接操作，无法安装WAAS Booster所需依赖，因此本节给出不依赖环境的独立RPM包制作过程。

>![](public_sys-resources/icon-note.gif) **说明：** 
>-   制作该RPM包的机器环境需能访问外部网络。
>-   root用户可直接执行下述命令；普通用户执行本小节的操作时，需要在下述命令前加**sudo**提高权限。

1. 安装软件运行必要依赖。

    ```
    yum install -y python rpm-build cpio
    ```

2. 下载[Miniconda3安装脚本](https://repo.anaconda.com/miniconda/Miniconda3-py310_25.1.1-2-Linux-aarch64.sh)。
3. 按默认安装Miniconda3。

    ```
    sh Miniconda3-py310_25.1.1-2-Linux-aarch64.sh
    ```

4. 在“/etc/profile“里配置安装好的Miniconda3的二进制路径。
    1. 打开文件。

        ```
        vim /etc/profile
        ```

    2. 在文件末尾添加如下内容。

        ```
        export PATH=$PATH:/root/miniconda3/bin/
        ```

    3. 按“Esc“键退出编辑模式，输入 **:wq!**，按“Enter“键保存退出文件。
    4. 使文件生效。

        ```
        source /etc/profile
        ```

5. 初始化创建好的conda环境。

    ```
    conda init
    ```

6. 退出当前SSH窗口，再重新连接SSH窗口，确保conda生效。

    >![](public_sys-resources/icon-note.gif) **说明：** 
    >如果重新进入SSH窗口显示为在base环境中，则需要使用**conda deactivate**退出base环境，如果不在则无需操作。

7. 使用conda创建Python环境，例如环境命名为waasbooster\_env。
    1. 添加conda-forge channel。

        ```
        conda config --add channels conda-forge
        ```

    2. 使用conda-forge创建python环境。

        ```
        conda create -n waasbooster_env python=3.9.9 -c conda-forge
        ```

8. 查看waasbooster\_env环境路径。

    ```
    conda env list
    ```

    回显如下图所示：

    ![](figures/zh-cn_image_0000002549864189.png)

9. 执行命令进入指定虚拟环境。

    ```
    conda activate waasbooster_env
    ```

10. 创建并进入waasbooster rpm编译路径，例如此处路径为“/home/waasbooster\_rpm\_build“。
    1. 创建路径。

        ```
        mkdir /home/waasbooster_rpm_build
        ```

    2. 进入路径。

        ```
        cd /home/waasbooster_rpm_build
        ```

11. 拷贝conda环境文件到RPM编译路径。

    ```
    cp -r /root/miniconda3/envs/waasbooster_env/ /home/waasbooster_rpm_build/
    ```

12. 获取并解压WAAS软件安装包waas-waasbooster.zip。

    获取链接请参见[操作系统和软件要求](#操作系统和软件要求)。

    ```
    unzip waas-waasbooster.zip
    ```

13. 执行命令安装依赖。

    ```
    pip3 install -r waas-waasbooster/requirements.txt
    ```

14. 拷贝主程序文件夹waasbooster。

    ```
    cp -r waas-waasbooster/src/waasbooster/ /home/waasbooster_rpm_build/
    ```

15. 修改waasbooster.service文件。
    1. 打开waasbooster.service文件。

        ```
        vim /home/waasbooster_rpm_build/waasbooster/waasbooster.service
        ```

    2. 按“i“进入编辑模式，

        将

        ```
        ExecStart=/usr/local/waasbooster/bin/python3 /usr/local/waasbooster/waas_booster.py
        ```

        修改为

        ```
        ExecStart=/usr/local/waasbooster/waasbooster_env/bin/python3 /usr/local/waasbooster/waas_booster.py
        ```

    3. 按“Esc“键退出编辑模式，输入 **:wq!**，按“Enter“键保存退出文件。

16. 新增文件，保存指定内容。

    >![](public_sys-resources/icon-note.gif) **说明：** 
    >root用户可直接执行下述命令；普通用户执行本小节的操作时，需要在下述命令前加**sudo**提高权限。

    1. 新增文件build.sh，添加如下内容。

        ``` bash
        #!/bin/bash
        # ******************************************************************************** #
        # Copyright Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
        # File Name: build.sh
        # Description: 编译构建总调用脚本
        # Usage: sh build.sh clean --> 环境清理
        #        sh build.sh build_debug --> 部署调试环境（需要先安装server并配置WAAS_HOME环境变量）
        #        sh build.sh build_package --> 打包
        # ******************************************************************************** #
        CURRENT_DIR=$(dirname $(readlink -f "$0"))
        BUILD_DIR=${CURRENT_DIR}/build
        mkdir -p ${BUILD_DIR}
        mkdir -p ${CURRENT_DIR}/output
        function clean() {
            rm -rf ${BUILD_DIR}/rpmbuild/*
            rm -rf ${CURRENT_DIR}/build
            rm -rf ${CURRENT_DIR}/output
            rm -rf ${CURRENT_DIR}/debug
        }
        function build_booster_package() {
            clean
            cd ${CURRENT_DIR}/
            mkdir -p ${BUILD_DIR}/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
            rm -rf build/rpmbuild/BUILDROOT/*
            cp -rf waasbooster_env ${BUILD_DIR}/rpmbuild/SOURCES
            build_waas_booster
        }
        function build_waas_booster() {
            mkdir -p ${CURRENT_DIR}/output
            cp waas_booster.spec ${BUILD_DIR}/rpmbuild/SPECS/
            find waasbooster -name '__pycache__' | xargs rm -rf
            zip -r ${BUILD_DIR}/rpmbuild/SOURCES/waasbooster.zip \
                waasbooster/* \
                waasbooster_env/*
            rpmbuild --define "_topdir ${BUILD_DIR}/rpmbuild" -v -ba ${BUILD_DIR}/rpmbuild/SPECS/waas_booster.spec --undefine=py_auto_byte_compile
            cp ${BUILD_DIR}/rpmbuild/RPMS/aarch64/waasbooster-1.0.0-1.aarch64.rpm ./output/waasbooster-1.0.0-1.aarch64.rpm
        }
        main() {
            item=$1
            eval ${item}
        }
        main "$@"
        exit $?
        ```

    2. 新增文件waas\_booster.spec，添加如下内容。

        ``` bash
        %define projectdir /usr/local/waasbooster
        
        Name:     waasbooster
        Version:  1.0.0
        Release:  1%{?dist}
        Summary:    负载感知
        License:    FIXME
        BuildArch: %{_build_arch}
        Vendor:     Huawei
        
        Provides: waasbooster = 1.0.0
        
        %description
        WaaS Booster是一款在线版容器quota调优工具
        
        %prep
        unzip %{_sourcedir}/waasbooster.zip
        
        %build
        
        
        %install
        mkdir -p %{buildroot}/usr/lib/systemd/system/
        mkdir -p %{buildroot}/usr/bin/
        mkdir -p %{buildroot}/%{projectdir}
        cp %{_builddir}/waasbooster/* %{buildroot}/%{projectdir}
        
        install -m 444 waasbooster/waasbooster.service %{buildroot}/usr/lib/systemd/system/waasbooster.service
        cp -r %{_sourcedir}/waasbooster_env %{buildroot}/usr/local/waasbooster
        
        
        %files
        %dir %attr(644, waas, waas) %{projectdir}
        %defattr (0440, waas, waas)
        %{projectdir}/*
        %dir %attr(644, waas, waas) %{projectdir}
        %attr(644, root, root) /usr/lib/systemd/system/waasbooster.service
        %dir %attr(750, waas, waas) /usr/local/waasbooster/waasbooster_env
        %{projectdir}/waasbooster_env/*
        
        #=======以上是打包过程执行脚本========
        #=======以下是安装卸载时执行脚本========
        
        %pre -p /bin/sh
        getent group waas &> /dev/null || \
        groupadd -r waas &> /dev/null
        getent passwd waas &> /dev/null || \
        useradd -r -g waas -d /usr/local/waasbooster -s /sbin/nologin \
        -c 'Waas booster' waas &> /dev/null
        if [ $SUDO_USER ]; then
            usermod -a -G waas $SUDO_USER
        elif [ $USER ]; then
            usermod -a -G waas $USER
        else
            usermod -a -G waas `whoami`
        fi
        exit 0
        
        %post -p /bin/sh
        mkdir -p /var/waasbooster
        chown waas:waas /var/waasbooster
        chmod 750 /var/waasbooster
        mkdir -p /var/run/waasbooster_manager
        systemctl enable waasbooster.service
        chmod +x /usr/local/waasbooster/waasbooster_env/bin/python3
        exit 0
        
        %preun -p /bin/sh
        exit 0
        
        %postun -p /bin/sh
        rm -rf /usr/local/waasbooster
        rm -rf /var/waasbooster
        rm -rf /var/run/waasbooster_manager
        exit 0
        
        ```

17. 编译RPM包。

    ```
    sh build.sh build_booster_package
    ```

    编译结果输出至编译路径的output文件夹下，此处为“/home/waasbooster\_rpm\_build/output/“。

18. 安装独立RPM包。

    >![](public_sys-resources/icon-note.gif) **说明：** 
    >-   无需安装WAAS Booster运行环境即可部署运行此安装包。
    >-   安装此RPM包时请添加 **--nodeps**命令，否则将无法安装运行。

    ```
    rpm -ivh --nodeps /home/waasbooster_rpm_build/output/waasbooster-1.0.0-1.aarch64.rpm
    ```

19. （可选）卸载独立RPM包。

    ```
    rpm -e --nodeps waasbooster
    ```



## K8s Pod部署WAAS Booster<a name="ZH-CN_TOPIC_0000002549744187"></a>

### 构建镜像<a name="ZH-CN_TOPIC_0000002518224406"></a>

1. 拉取导入基础Python镜像。

    >![](public_sys-resources/icon-note.gif) **说明：** 
    >此处需要能够访问Docker Hub拉取镜像，并且能够使用pip拉取依赖。

    1. 拉取python:3.9.9-slim镜像。

        ```
        docker pull python:3.9.9-slim
        ```

    2. 查看镜像列表。

        ```
        docker images
        ```

        若拉取成功，则应该有如下回显：

        ![](figures/zh-cn_image_0000002549864185.png)

2. 下载WAAS Booster开源代码包，下载链接请参见[操作系统和软件要求](#操作系统和软件要求)。

    如选择拉取，则执行以下命令。

    ```
    git clone -b waasbooster https://gitcode.com/boostkit/waas.git
    ```

3. 构建镜像。
    1. 进入waas文件夹。

        ```
        cd waas
        ```

    2. 构建编译镜像。

        ```
        docker build -t waasbooster:1.0.0 .
        ```

        命令中的“waasbooster”为构建后的镜像名，“1.0.0”为镜像TAG。

        注意此处需要使用pip拉取依赖，如果需要使用pip代理，则可以使用以下命令指定代理服务器。

        ```
        docker build --build-arg PIP_PROXY=http://username:password@http.example.com:8080 -t waasbooster:1.0.0 .
        ```

        若有特定pip镜像源，则可使用以下命令指定pip镜像源。

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

        若回显中有如下类似镜像，则构建成功。

        ![](figures/zh-cn_image_0000002518224420.png)

        >![](public_sys-resources/icon-note.gif) **说明：** 
        >将构建好的镜像导入业务节点可以访问的镜像仓库，或者手动导入各业务节点。

4. （可选）containerd导入镜像。

    若目标集群底层基于containerd实现，则需要将Docker构建的waasbooster镜像导出后，以containerd的方式导入。

    1. 执行以下命令导出容器镜像并命名为waasbooster.tar。

        ```
        docker save -o waasbooster.tar waasbooster:1.0.0
        ```

    2. 执行以下命令导入waasbooster.tar。

        ```
        ctr -n k8s.io image import waasbooster.tar
        ```

    3. 执行以下命令查看是否导入成功。

        ```
        ctr -n k8s.io images list
        ```

        若回显中有如下类似镜像，则导入成功。

        ![](figures/zh-cn_image_0000002518384336.png)


### 部署Pod<a name="ZH-CN_TOPIC_0000002518224410"></a>

部署前需要确保部署节点上存在构建好的WAAS Booster镜像，或者能够拉取到WAAS Booster镜像。

1. 拷贝部署文件。

    将“waas-waasbooster/deployment“路径下的**waasbooster.yaml**文件拷贝至K8s的Master节点。

2. 创建waasbooster Pod。

    ```
    kubectl apply -f waasbooster.yaml
    ```

    若回显如下，则创建成功。

    ![](figures/zh-cn_image_0000002518224422.png)

    >![](public_sys-resources/icon-note.gif) **说明：** 
    >Pod创建后，WAAS Booster服务自动启动。

### （可选）销毁Pod<a name="ZH-CN_TOPIC_0000002518224404"></a>

当需要把整个集群中的WAAS Booster服务停掉时，需要销毁Pod。Pod销毁后，WAAS Booster服务自动停止，所有业务Pod的Quota恢复初始设置。

1. 查看Pod。

    ```
    kubectl get pods
    ```

    若回显如下，则存在运行的waasbooster Pod。

    ![](figures/zh-cn_image_0000002549864183.png)

2. 销毁Pod。

    ```
    kubectl delete -f waasbooster.yaml
    ```

    若回显如下，则销毁成功。

    ![](figures/zh-cn_image_0000002549744193.png)



