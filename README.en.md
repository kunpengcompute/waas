# boostkit-waas

#### Description
WAAS container quota dynamic optimization

#### Build image
build is based on python:3.9.9-slim.
1.  clone waasbooster
```
git clone -b waasbooster https://gitee.com/kunpeng_compute/boostkit-waas.git
```
2.  build images by docker
```
docker build -t waasbooster:1.0.0 .
```
proxy can be used by giving build-arg PIP_PROXY.
PS: if URL encodeing is needed, using '%%' for encoding instead if '%', eg: '%%23' for '#'.
```
docker build --build-arg PIP_PROXY=http://username:password@http.example.com:8080 -t waasbooster:1.0.0 .
```
PIP mirror is also supported
```
docker build \
    --build-arg PIP_MIRROR=http://mirror.example.com/pypi/simple \
    --build-arg PIP_TRUST_HOST=http://mirror.example.com \
    -t waasbooster:1.0.0 .
```

#### K8s deployment
1.  import waasbooster image in all work nodes
2.  enable waasbooster in master node
```
cd boostkit-waas
kubectl apply -f deployment/waasbooster.yaml
```
