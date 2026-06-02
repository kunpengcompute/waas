# Quick Start

## Tool Overview<a name="EN-US_TOPIC_0000002549747753"></a>

Workload Aware Acceleration System Booster (WAAS Booster) is a dynamic scheduling tool for containers in virtualization scenarios. It can detect and analyze container loads in real time, respond to CPU resource insufficiency caused by burst loads, and optimize global resource scheduling through load awareness and prediction.


## Tool Installation<a name="EN-US_TOPIC_0000002550143105"></a>

The following uses Kubernetes-based deployment as an example, where the service deployed in the form of DaemonSet pods is distributed from the master node to each compute node. The deployment involves two steps: image building and pod deployment.

1. Pull and import the base Python image.
    1. You need to be able to access Docker Hub to pull images and use pip to pull dependencies.

        Pull the `python:3.9.9-slim` image.

        ```
        docker pull python:3.9.9-slim 
        ```

    2. Check the image list.

        ```
        docker images 
        ```

        If the image whose name is `python` and tag is `3.9.9-slim` is displayed in the command output, the image is successfully pulled.

2. Download the WAAS Booster open-source package.

    ```
    git clone -b waasbooster https://gitcode.com/BoostKit/waas.git 
    ```

3. Build the image.

    1. Go to the `waas` folder.

        ```
        cd waas-waasbooster 
        ```

    2. Build the image.

        ```
        docker build -t waasbooster:1.0.0 . 
        ```

        In the command, `waasbooster` is the name of the built image, and `1.0.0` is the image tag. Note that you need to use pip to pull dependencies. If you need to use the pip proxy, run the following command to specify a proxy server:

        ```
        docker build --build-arg PIP_PROXY=http://username:password@http.example.com:8080 -t waasbooster:1.0.0 . 
        ```

        If a specific pip image source is available, you can also specify the pip image source.

        ```
        docker build \     
        --build-arg PIP_MIRROR=http://mirror.example.com/pypi/simple \     
        --build-arg PIP_TRUST_HOST=http://mirror.example.com \     
        -t waasbooster:1.0.0 .
        ```

    3. Check the image list.

        ```
        docker images 
        ```

        If the image whose name is `waasbooster` and tag is `1.0.0` is displayed in the command output, the image is successfully built.


## Tool Usage<a name="EN-US_TOPIC_0000002550183111"></a>

The following uses Kubernetes-based deployment as an example. Before the deployment, ensure that the deployment node has or can pull the built WAAS Booster image.

1. Copy the deployment file.

    Copy the `waasbooster.yaml` file in the `waas-waasbooster/deployment` directory to the master node of Kubernetes.

2. Create a WAAS Booster pod.

    ```
    kubectl apply -f waasbooster.yaml 
    ```

    If the command output contains the following information, the pod is created successfully.

    ```
    daemonset.apps/waasbooster-daemon created
    ```
