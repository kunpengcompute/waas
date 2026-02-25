# Installation Guide<a name="EN-US_TOPIC_0000002518384328"></a>

## Deployment Description<a name="EN-US_TOPIC_0000002518384330"></a>

WAAS Booster is a dynamic load-based scheduling tool designed for containerized environments. Depending on deployment environments, WAAS Booster can be deployed using either RPM or Kubernetes pods. The following describes the differences between the two deployment modes and their application scenarios.

1. Using RPM
    1. Applies to environments with a small number of service nodes, such as small enterprises or startups. In these environments, complex resource management and scheduling are usually not required.
    2. Applies to environments where Kubernetes is not adopted for containerized management. These environments may use traditional VMs or physical machines to deploy applications.
    3. Applies to scenarios where the O&M automation requirements are not high and manual maintenance and debugging are not frequent. RPM physical machine deployment reduces the dependency on automatic O&M tools and simplifies O&M.

2. Using Kubernetes pods
    1. Applies to environments with many service nodes, such as large enterprises or Internet companies. These environments usually require efficient resource management and scheduling capabilities.
    2. Applies to environments where Kubernetes is adopted for containerized management. In these environments, Kubernetes' automatic deployment, expansion, and management functions can be utilized.
    3. Applies to scenarios where high O&M automation is required. This deployment mode allows for centrally creating, managing, and deleting WAAS Booster service pods on primary nodes, improving system reliability and availability.

When selecting a deployment mode, you should consider the preceding features and application scenarios based on your service requirements, technology stack, and O&M capabilities.

>![](public_sys-resources/icon-note.gif) **NOTE:** 
>Primary nodes refer to the management nodes in a Kubernetes cluster, and service nodes refer to the nodes deployed with specific services in a Kubernetes cluster.

WAAS Booster is a dynamic load-based scheduling tool designed for containerized environments. Depending on deployment environments, WAAS Booster can be deployed using either RPM or Kubernetes pods. The following describes the differences between the two deployment modes and their application scenarios.
## Environment Requirements<a name="EN-US_TOPIC_0000002549864175"></a>

This document provides guidance based on the openEuler OS. Before performing operations, ensure that your hardware and software meet the requirements.

**OS and Software Requirements<a name="section21485361307"></a>**

[Table 1](#Table1)  lists the OS and software requirements.

**Table  1**  OS and software requirements <a id="Table1"></a>

|Item|Version|How to Obtain|
|--|--|--|
|OS|openEuler 20.03 LTS SP3|[Link](https://www.openeuler.org/zh/download/archive/detail/?version=openEuler%2020.03%20LTS%20SP3)|
|OS|openEuler 22.03 LTS SP4|[Link](https://www.openeuler.org/zh/download/archive/detail/?version=openEuler%2022.03%20LTS%20SP4)|
|Python|3.9.9 or later|[Link](https://www.python.org/downloads/release/python-399/)|
|Miniconda3|py310_25.1.1-2-Linux-aarch64|[Link](https://repo.anaconda.com/miniconda/Miniconda3-py310_25.1.1-2-Lniux-aarch64.sh)|
|Dependencies required by WAAS Booster|Versions specified in the installation guide|Install them using a Yum repository and pip source.|
|WAAS Booster open source package|1.0.0|[Link](https://gitcode.com/boostkit/waas)|


>![](public_sys-resources/icon-note.gif) **NOTE:** 
>WAAS Booster can be deployed only on service nodes.

This document provides guidance based on the openEuler OS. Before performing operations, ensure that your hardware and software meet the requirements.
## Deploying WAAS Booster Using RPM<a name="EN-US_TOPIC_0000002518224408"></a>

### Installing the Operating Environment<a name="EN-US_TOPIC_0000002518384324"></a>

Install the required dependencies to provide the environment for deploying WAAS Booster.

>![](public_sys-resources/icon-note.gif) **NOTE:** 
>For the  **root**  user, directly run the following commands. For a common user, add  **sudo**  before the following commands to elevate the permission.

1. Install the dependencies required for running the software.

    ```
    yum install -y python rpm-build cpio
    ```

2. Download the  [Miniconda3 installation script](https://repo.anaconda.com/miniconda/Miniconda3-py310_25.1.1-2-Linux-aarch64.sh).
3. Install Miniconda3 with default configuration.

    ```
    sh Miniconda3-py310_25.1.1-2-Linux-aarch64.sh
    ```

4. Configure the path to the Miniconda3 binary in  **/etc/profile**.
    1. Open the file.

        ```
        vim /etc/profile
        ```

    2. Press  **i**  to enter the insert mode and add the following content to the end of the file:

        ```
        export PATH=$PATH:/root/miniconda3/bin/
        ```

    3. Press  **Esc**  to exit the insert mode. Type  **:wq!**  and press  **Enter**  to save the file and exit.
    4. Make the file take effect.

        ```
        source /etc/profile
        ```

5. Initialize the conda environment.

    ```
    conda init
    ```

6. Exit the current SSH window and reconnect to the SSH window to ensure that conda takes effect.

    >![](public_sys-resources/icon-note.gif) **NOTE:** 
    >If the base environment is displayed after you re-enter the SSH window, run the  **conda deactivate**  command to exit the base environment. If the base environment is not displayed, no operation is required.

7. Use conda to create a Python environment, for example,  **waasbooster\_env**.
    1. Add the  **conda-forge**  channel.

        ```
        conda config --add channels conda-forge
        ```

    2. Use  **conda-forge**  to create a Python environment.

        ```
        conda create -n waasbooster_env python=3.9.9 -c conda-forge
        ```

8. <a name="li3962559112"></a>Check the  **waasbooster\_env**  environment path.

    ```
    conda env list
    ```

    The command output is as follows:

    ![](figures/en-us_image_0000002518384334.png)

    >![](public_sys-resources/icon-note.gif) **NOTE:** 
    >-   If the  **waasbooster\_env**  path in the command output in step  [8](#li3962559112)  is not  **/usr/local/waasbooster/bin/python3**, copy the path and use it to modify the configuration file after WAAS Booster is deployed.
    >-   If the returned content is  **/usr/local/waasbooster/bin/python3**, skip this modification.

9. Run the following command to go to the specified virtual environment:

    ```
    conda activate waasbooster_env
    ```

10. Obtain the WAAS Booster open source package  **waas-waasbooster.zip**. For details about how to obtain the package, see  [OS and Software Requirements](#Table1). Upload  **waas-waasbooster.zip**  to a custom directory on the server and decompress the package.

    ```
    unzip waas-waasbooster.zip
    ```

11. Run the following command to install the dependencies:

    ```
    pip3 install -r waas-waasbooster/requirements.txt
    ```

Install the required dependencies to provide the environment for deploying WAAS Booster.
### Creating a WAAS Booster RPM Package<a name="EN-US_TOPIC_0000002549744183"></a>

Create a WAAS Booster RPM package.

1. Compile and build the WAAS Booster RPM package.

    ```
    sh waas-waasbooster/build.sh build_booster_package
    ```

2. After the compilation is complete, go to the  **waas-waasbooster/output**  directory to check whether the RPM package is successfully built. If the  **waasbooster-1.0.0.aarch64.rpm**  file exists, the RPM package is successfully built.

Create a WAAS Booster RPM package.
### Deploying WAAS Booster<a name="EN-US_TOPIC_0000002549864177"></a>

This operation includes installing the WAAS Booster installation package and setting environment variables.

1. Install WAAS Booster.

    >![](public_sys-resources/icon-note.gif) **NOTE:** 
    >For the  **root**  user, directly run the following commands. For a common user, add  **sudo**  before the following commands to elevate the permission.

    ```
    rpm -ivh waasbooster-1.0.0.aarch64.rpm
    ```

    If the installation is successful, the following information will be displayed.

    ![](figures/en-us_image_0000002518224418.png)

2. Modify the service file of WAAS Booster.
    1. Check the  **waasbooster\_env**  environment path.

        ```
        conda env list
        ```

        For example, the returned value of  **waasbooster\_env**  is  **/root/miniconda3/envs/waasbooster\_env**.

    2. Open the  **/usr/lib/systemd/system/waasbooster.service**  file.

        ```
        vim /usr/lib/systemd/system/waasbooster.service
        ```

    3. Press  **i**  to enter the insert mode and modify the startup script.

        Change

        ```
        ExecStart=/usr/local/waasbooster/bin/python3 /usr/local/waasbooster/cpu_booster.py
        ```

        to

        ```
        ExecStart=/root/miniconda3/envs/waasbooster_env/bin/python3 /usr/local/waasbooster/waas_booster.py
        ```

        That is, change  **/usr/local/waasbooster**  in  **/usr/local/waasbooster/bin/python3**  to the  **waasbooster\_env**  path in the  **conda env list**  command output.

    4. Press  **Esc**  to exit the insert mode. Type  **:wq!**  and press  **Enter**  to save the file and exit.

3. Reload the daemon of systemctl.

    ```
    systemctl daemon-reload
    ```

This operation includes installing the WAAS Booster installation package and setting environment variables.
### Running WAAS Booster<a name="EN-US_TOPIC_0000002549744189"></a>

After WAAS Booster is installed, you need to start WAAS Booster before using the WAAS Booster functions.

>![](public_sys-resources/icon-note.gif) **NOTE:** 
>For the  **root**  user, directly run the following commands. For a common user, add  **sudo**  before the following commands to elevate the permission.

**Starting WAAS Booster<a name="section0388141123110"></a>**

1. Log in to the WAAS Booster installation node using an administrator account.
2. Start WAAS Booster on the installation node.

    ```
    systemctl start waasbooster
    ```

3. Check the status of WAAS Booster.

    ```
    systemctl status waasbooster
    ```

    If information similar to the following \(**Active: active \(running\)**\) is displayed, WAAS Booster is started successfully.

    ![](figures/en-us_image_0000002549864187.png)

**Stopping WAAS Booster<a name="section31589018432"></a>**

>![](public_sys-resources/icon-notice.gif) **NOTICE:** 
>Before stopping WAAS Booster, ensure that all running tuning tasks have been stopped.

1. Log in to the WAAS Booster node using an administrator account.
2. Stop WAAS Booster on the installation node.

    ```
    systemctl stop waasbooster
    ```

3. Check whether WAAS Booster is stopped.

    ```
    systemctl status waasbooster
    ```

    If information similar to the following \(**Active: inactive \(dead\)**\) is displayed, WAAS Booster is stopped successfully.

    ![](figures/en-us_image_0000002549744195.png)

After WAAS Booster is installed, you need to start WAAS Booster before using the WAAS Booster functions.
### \(Optional\) Uninstalling WAAS Booster<a name="EN-US_TOPIC_0000002518224414"></a>

You can uninstall WAAS Booster when it is not required.

>![](public_sys-resources/icon-notice.gif) **NOTICE:** 
>-   This operation is not mandatory for the deployment.
>-   The default installation path of WAAS Booster is  **/usr/local/waasbooster/**. After WAAS Booster is uninstalled, all files in this path are deleted.
>-   After the uninstallation is complete, you are advised to manually delete the installation packages and logs located in  **/var/log/waasbooster.log**.

1. Stop WAAS Booster.

    ```
    systemctl stop waasbooster
    ```

2. Uninstall WAAS Booster.

    ```
    rpm -e waasbooster
    ```

You can uninstall WAAS Booster when it is not required.
### \(Optional\) Creating an Independent WAAS Booster RPM Package<a name="EN-US_TOPIC_0000002518224412"></a>

Some deployment environments do not support network connections. As a result, the dependencies required by WAAS Booster cannot be installed. This section describes how to create an environment-independent RPM package.

>![](public_sys-resources/icon-note.gif) **NOTE:** 
>-   The host where the RPM package is created must be able to access the external network.
>-   For the  **root**  user, directly run the following commands. For a common user, add  **sudo**  before the following commands to elevate the permission.

1. Install the dependencies required for running the software.

    ```
    yum install -y python rpm-build cpio
    ```

2. Download the  [Miniconda3 installation script](https://repo.anaconda.com/miniconda/Miniconda3-py310_25.1.1-2-Linux-aarch64.sh).
3. Install Miniconda3 with default configuration.

    ```
    sh Miniconda3-py310_25.1.1-2-Linux-aarch64.sh
    ```

4. Configure the path to the Miniconda3 binary in  **/etc/profile**.
    1. Open the file.

        ```
        vim /etc/profile
        ```

    2. Add the following content to the end of the file:

        ```
        export PATH=$PATH:/root/miniconda3/bin/
        ```

    3. Press  **Esc**  to exit the insert mode. Type  **:wq!**  and press  **Enter**  to save the file and exit.
    4. Make the file take effect.

        ```
        source /etc/profile
        ```

5. Initialize the created conda environment.

    ```
    conda init
    ```

6. Exit the current SSH window and reconnect to the SSH window to ensure that conda takes effect.

    >![](public_sys-resources/icon-note.gif) **NOTE:** 
    >If the base environment is displayed after you re-enter the SSH window, run the  **conda deactivate**  command to exit the base environment. If the base environment is not displayed, no operation is required.

7. Use conda to create a Python environment, for example,  **waasbooster\_env**.
    1. Add the  **conda-forge**  channel.

        ```
        conda config --add channels conda-forge
        ```

    2. Use  **conda-forge**  to create a Python environment.

        ```
        conda create -n waasbooster_env python=3.9.9 -c conda-forge
        ```

8. Check the  **waasbooster\_env**  environment path.

    ```
    conda env list
    ```

    The command output is as follows:

    ![](figures/en-us_image_0000002549864189.png)

9. Run the following command to go to the specified virtual environment:

    ```
    conda activate waasbooster_env
    ```

10. Create and go to the WAAS Booster RPM compilation path, for example,  **/home/waasbooster\_rpm\_build**.
    1. Create a path.

        ```
        mkdir /home/waasbooster_rpm_build
        ```

    2. Access the path.

        ```
        cd /home/waasbooster_rpm_build
        ```

11. Copy the conda environment file to the RPM compilation path.

    ```
    cp -r /root/miniconda3/envs/waasbooster_env/ /home/waasbooster_rpm_build/
    ```

12. Obtain and decompress the WAAS software installation package  **waas-waasbooster.zip**.

    For details about how to obtain the package, see  [OS and Software Requirements](#Table1).

    ```
    unzip waas-waasbooster.zip
    ```

13. Run the following command to install the dependencies:

    ```
    pip3 install -r waas-waasbooster/requirements.txt
    ```

14. Copy the main program folder  **waasbooster**.

    ```
    cp -r waas-waasbooster/src/waasbooster/ /home/waasbooster_rpm_build/
    ```

15. Modify the  **waasbooster.service**  file.
    1. Open the  **waasbooster.service**  file.

        ```
        vim /home/waasbooster_rpm_build/waasbooster/waasbooster.service
        ```

    2. Press  **i**  to enter the insert mode.

        Change

        ```
        ExecStart=/usr/local/waasbooster/bin/python3 /usr/local/waasbooster/waas_booster.py
        ```

        to

        ```
        ExecStart=/usr/local/waasbooster/waasbooster_env/bin/python3 /usr/local/waasbooster/waas_booster.py
        ```

    3. Press  **Esc**  to exit the insert mode. Type  **:wq!**  and press  **Enter**  to save the file and exit.

16. Create files and save the specified content.

    >![](public_sys-resources/icon-note.gif) **NOTE:** 
    >For the  **root**  user, directly run the following commands. For a common user, add  **sudo**  before the following commands to elevate the permission.

    1. Create a  **build.sh**  file and add the following content to the file:

        ```
        #!/bin/bash
        # ******************************************************************************** #
        # Copyright Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
        # File Name: build.sh
        # Description: main script to be called for compilation and building
        # Usage: sh build.sh clean --> Clean the environment.
        #        sh build.sh build_debug --> Deploy the debugging environment. (You need to install the server and configure the WAAS_HOME environment variable first.)
        #        sh build.sh build_package --> Perform packaging.
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

    2. Create a  **waas\_booster.spec**  file and add the following content to the file:

        ```
        %define projectdir /usr/local/waasbooster
        
        Name:     waasbooster
        Version:  1.0.0
        Release:  1%{?dist}
        Summary: Load awareness
        License:    FIXME
        BuildArch: %{_build_arch}
        Vendor:     Huawei
        
        Provides: waasbooster = 1.0.0
        
        %description
        WAAS Booster is an online container quota tuning tool.
        
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
        
        #=======The preceding script is executed during packaging.========
        #=======The following script is executed during installation and uninstallation.========
        
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

17. Compile the RPM package.

    ```
    sh build.sh build_booster_package
    ```

    The compilation result is output to the  **output**  folder in the compilation path, for example,  **/home/waasbooster\_rpm\_build/output/**.

18. Install the independent RPM package.

    >![](public_sys-resources/icon-note.gif) **NOTE:** 
    >-   You can deploy and run the installation package without installing the WAAS Booster operating environment.
    >-   Add the  **--nodeps**  command when installing the RPM package. Otherwise, the RPM package cannot be installed.

    ```
    rpm -ivh --nodeps /home/waasbooster_rpm_build/output/waasbooster-1.0.0-1.aarch64.rpm
    ```

19. \(Optional\) Uninstall the independent RPM package.

    ```
    rpm -e --nodeps waasbooster
    ```

Some deployment environments do not support network connections. As a result, the dependencies required by WAAS Booster cannot be installed. This section describes how to create an environment-independent RPM package.


## Deploying WAAS Booster Using Kubernetes Pods<a name="EN-US_TOPIC_0000002549744187"></a>

### Building an Image<a name="EN-US_TOPIC_0000002518224406"></a>

1. Pull and import the base Python image.

    >![](public_sys-resources/icon-note.gif) **NOTE:** 
    >You need to be able to access Docker Hub to pull images and use pip to pull dependencies.

    1. Pull the  **python:3.9.9-slim**  image.

        ```
        docker pull python:3.9.9-slim
        ```

    2. View the image list.

        ```
        docker images
        ```

        If the pull is successful, the following information is displayed:

        ![](figures/en-us_image_0000002549864185.png)

2. Download the WAAS Booster open source package. For details, see  [OS and Software Requirements](#Table1).

    If you choose to pull the image, run the following command:

    ```
    git clone -b waasbooster https://gitcode.com/boostkit/waas.git
    ```

3. Build the image.
    1. Go to the  **waas**  folder.

        ```
        cd waas
        ```

    2. Build the image.

        ```
        docker build -t waasbooster:1.0.0 .
        ```

        In the command,  **waasbooster**  is the name of the built image, and  **1.0.0**  is the image tag.

        Note that you need to use pip to pull dependencies. If you need to use the pip proxy, run the following command to specify a proxy server:

        ```
        docker build --build-arg PIP_PROXY=http://username:password@http.example.com:8080 -t waasbooster:1.0.0 .
        ```

        If a specific pip image source is available, run the following command to specify the pip image source:

        ```
        docker build \     
          --build-arg PIP_MIRROR=http://mirror.example.com/pypi/simple \     
          --build-arg PIP_TRUST_HOST=http://mirror.example.com \     
          -t waasbooster:1.0.0 .
        ```

    3. View the image list.

        ```
        docker images
        ```

        If the information similar to the following is displayed, the image is successfully built.

        ![](figures/en-us_image_0000002518224420.png)

        >![](public_sys-resources/icon-note.gif) **NOTE:** 
        >Import the built image to the image repository that can be accessed by service nodes, or manually import the image to each service node.

4. \(Optional\) Import the image into the containerd environment.

    If the target cluster is implemented based on containerd, you need to export the  **waasbooster**  image built by Docker and import the image into the containerd environment.

    1. Run the following command to export the container image and name it  **waasbooster.tar**:

        ```
        docker save -o waasbooster.tar waasbooster:1.0.0
        ```

    2. Run the following command to import  **waasbooster.tar**:

        ```
        ctr -n k8s.io image import waasbooster.tar
        ```

    3. Run the following command to check whether the image is successfully imported:

        ```
        ctr -n k8s.io images list
        ```

        If the information similar to the following is displayed, the image is successfully imported.

        ![](figures/en-us_image_0000002518384336.png)


### Deploying Pods<a name="EN-US_TOPIC_0000002518224410"></a>

Before the deployment, ensure that the deployment node has or can pull the built WAAS Booster image.

1. Copy the deployment file.

    Copy the  **waasbooster.yaml**  file in the  **waas-waasbooster/deployment**  directory to the primary node of Kubernetes.

2. Create the  **waasbooster**  pod.

    ```
    kubectl apply -f waasbooster.yaml
    ```

    If the following information is displayed, the pod is created successfully.

    ![](figures/en-us_image_0000002518224422.png)

    >![](public_sys-resources/icon-note.gif) **NOTE:** 
    >After a pod is created, the WAAS Booster service is automatically started.

Before the deployment, ensure that the deployment node has or can pull the built WAAS Booster image.
### \(Optional\) Deleting Pods<a name="EN-US_TOPIC_0000002518224404"></a>

To stop the WAAS Booster service in a cluster, you need to delete the pods. After the pods are deleted, the WAAS Booster service automatically stops, and the quota of all service pods is restored to the initial setting.

1. View pods.

    ```
    kubectl get pods
    ```

    If the following information is displayed, the  **waasbooster**  pods are running:

    ![](figures/en-us_image_0000002549864183.png)

2. Delete the pods.

    ```
    kubectl delete -f waasbooster.yaml
    ```

    If the following information is displayed, the pods are deleted successfully.

    ![](figures/en-us_image_0000002549744193.png)

To stop the WAAS Booster service in a cluster, you need to delete the pods. After the pods are deleted, the WAAS Booster service automatically stops, and the quota of all service pods is restored to the initial setting.


