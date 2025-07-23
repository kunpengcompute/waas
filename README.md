# boostkit-waas

#### 介绍
WAAS容器场景负载动态调度


#### 镜像构建
该镜像基于python:3.9.9-slim构建，请确保构建环境中docker能够访问dockerhub拉取该基础镜像，或者手动下载导入。
1.  clone本仓库并选择waasbooster分支
```
git clone -b waasbooster https://gitee.com/kunpeng_compute/boostkit-waas.git
```
2.  使用docker构建镜像
```
docker build -t waasbooster:1.0.0 .
```
构建中需要使用PIP安装python依赖，如果需要使用PIP代理，可以使用以下命令指定代理服务器
注意：如果用户名或密码中存在特殊字符，按照docker标准需要使用'%%'进行转义而不是常用的'%'，例如'#'应被转义为'%%23'。
```
docker build --build-arg PIP_PROXY=http://username:password@http.example.com:8080 -t waasbooster:1.0.0 .
```
也可以指定PIP镜像源
```
docker build \
    --build-arg PIP_MIRROR=http://mirror.example.com/pypi/simple \
    --build-arg PIP_TRUST_HOST=http://mirror.example.com \
    -t waasbooster:1.0.0 .
```

#### 使用K8s部署
1.  将构建好的镜像导入工作节点可以访问的镜像仓库，或者手动导入各工作节点。
2.  使能waasbooster
```
cd boostkit-waas
kubectl apply -f deployment/waasbooster.yaml
```
