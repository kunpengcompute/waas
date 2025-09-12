#!/bin/bash
# *********************************************************************
# Copyright Huawei Technologies Co, Ltd. 2025-2025. All right reserved.
# File Name: build.sh
# Description: 编译构建脚本
# Usage: sh build.sh clean -> 环境清理
#        sh build.sh build_booster_package -> 打包
# *********************************************************************

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
    #cp -rf waasbooster_env ${BUILD_DIR}/rpmbuild/SOURCES
    build_waas_booster
}

function build_waas_booster() {
    mkdir -p ${CURRENT_DIR}/output
    cp waas_booster.spec ${BUILD_DIR}/rpmbuild/SPECS/
    find waasbooster -name '__pycache__' | xargs rm -rf
    zip -r ${BUILD_DIR}/rpmbuild/SOURCES/waasbooster.zip \
        src/waasbooster/*
    rpmbuild --define "_topdir ${BUILD_DIR}/rpmbuild" -v -ba ${BUILD_DIR}/rpmbuild/SPECS/waas_booster.spec --undefine=py_auto_byte_compile
    cp ${BUILD_DIR}/rpmbuild/RPMS/aarch64/waasbooster-1.0.0-1.aarch64.rpm ./output/waasbooster-1.0.0.aarch64.rpm

}
main() {
    item=$1
    eval ${item}
}
main "$@"
exit $?
