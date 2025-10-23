cmake_minimum_required(VERSION 3.15.0)

project(waas_regtool)

set(EXCUTABLE_NAME regtool)

add_executable(${EXCUTABLE_NAME} regtool.cpp)

target_compile_options(${EXCUTABLE_NAME} PRIVATE -Wall -Werror -std=c++14 -D_FORTIFY_SOURCE=2 -O2 -fPIE -fstack-protector-all -ftrapv -fvisibility=hidden)

target_link_options(${EXCUTABLE_NAME} PRIVATE -Wl,-z,now -s -pie)

install(TARGETS ${EXCUTABLE_NAME} DESTINATION /usr/local/bin)
