/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved
*/


#include <cstdlib>
#include <thread>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#include <sys/ioctl.h>

#include <map>
#include <string>
#include <cstdint>
#include <iostream>

namespace RegTool {
struct Entry {
    int id;
    long long unsigned int value;
};

struct Request {
    int startCore;
    int endCore; // 仅在set时生效
    struct Entry *entries;
    size_t count;
};

constexpr char IOCTL_MAGIC = 'K';
constexpr unsigned long IOCTL_SET = _IOWR(IOCTL_MAGIC, 0, struct Request);
constexpr unsigned long IOCTL_GET = _IOWR(IOCTL_MAGIC, 1, struct Request);

enum GROUP : int {
    MAGIC = 2839,
    GROUP0,
    GROUP1,
    GROUP2,
    GROUP3,
    GROUP4,
    GROUP5,
    GROUP6,
    GROUP7,
    GROUP8,
    GROUP9,
    GROUP10,
    GROUP11,
    GROUP12,
    GROUP13,
    GROUP14,
    GROUP15,
    GROUP16,
    GROUP17,
    GROUP18,
    GROUP19,
    GROUP20,
    GROUP21,
    GROUP22,
    GROUP23,
    GROUP24,
    GROUP25,
    GROUP26,
    GROUP27,
    GROUP28,
    GROUP29,
    GROUP30,
    GROUP31,
    GROUP32,
    GROUP_MAX
};

constexpr int GROUP_NUM = GROUP_MAX - GROUP0;
std::map<std::string, int> g_groupMap;

void InitMap()
{
    g_groupMap["group0"] = GROUP0;
    g_groupMap["group1"] = GROUP1;
    g_groupMap["group2"] = GROUP2;
    g_groupMap["group3"] = GROUP3;
    g_groupMap["group4"] = GROUP4;
    g_groupMap["group5"] = GROUP5;
    g_groupMap["group6"] = GROUP6;
    g_groupMap["group7"] = GROUP7;
    g_groupMap["group8"] = GROUP8;
    g_groupMap["group9"] = GROUP9;
    g_groupMap["group10"] = GROUP10;
    g_groupMap["group11"] = GROUP11;
    g_groupMap["group12"] = GROUP12;
    g_groupMap["group13"] = GROUP13;
    g_groupMap["group14"] = GROUP14;
    g_groupMap["group15"] = GROUP15;
    g_groupMap["group16"] = GROUP16;
    g_groupMap["group17"] = GROUP17;
    g_groupMap["group18"] = GROUP18;
    g_groupMap["group19"] = GROUP19;
    g_groupMap["group20"] = GROUP20;
    g_groupMap["group21"] = GROUP21;
    g_groupMap["group22"] = GROUP22;
    g_groupMap["group23"] = GROUP23;
    g_groupMap["group24"] = GROUP24;
    g_groupMap["group25"] = GROUP25;
    g_groupMap["group26"] = GROUP26;
    g_groupMap["group27"] = GROUP27;
    g_groupMap["group28"] = GROUP28;
    g_groupMap["group29"] = GROUP29;
    g_groupMap["group30"] = GROUP30;
    g_groupMap["group31"] = GROUP31;
    g_groupMap["group32"] = GROUP32;
}

enum Args : int {
    CMD = 1,
    START_CORE,
    END_CORE,
    GROUP_START,
};

#define ARGV_TYPE char *
int Argparse(int argc, ARGV_TYPE argv[], int &startCore, int &endCore, std::map<int, unsigned long long> &params)
{
    try {
        InitMap();
        startCore = std::stoi(argv[START_CORE]);
        endCore = std::stoi(argv[END_CORE]);
        int cores = std::thread::hardware_concurrency();
        if (startCore < 0 || endCore >= cores || startCore > endCore) {
            std::cerr << "invalid core, need to be in range 0-" << (cores - 1) << std::endl;
            return -1;
        }
        for (int i = GROUP_START; i < argc; ++i) {
            std::string paramStr = argv[i];
            size_t pos = paramStr.find('=', 0);
            if (pos == std::string::npos) {
                std::cerr << "invalid key value pair, need format like group0=0" << std::endl;
                return -1;
            }
            std::string key = paramStr.substr(0, pos);
            std::string valueStr = paramStr.substr(pos + 1);
            uint64_t value = std::stoull(valueStr, nullptr, 0);
            auto it = g_groupMap.find(key);
            if (it == g_groupMap.end()) {
                std::cerr << "unknown group: " << key << std::endl;
                return -1;
            }
            params[it->second] = value;
        }
    } catch (const std::invalid_argument& e) {
        std::cerr << "invalid argument " << e.what() << std::endl;
        return -1;
    } catch (const std::out_of_range& e) {
        std::cerr << "args out of range: " << e.what() << std::endl;
        return -1;
    }
    return 0;
}

int RegOp(std::string &cmd, int startCore, int endCore, const std::map<int, unsigned long long> &params)
{
    int fd = open("/dev/prf", O_RDWR);
    if (fd < 0) {
        std::cerr << "open dev failed, errno: " << errno << std::endl;
        return -1;
    }

    struct Request req;
    Entry entries[GROUP_NUM];
    if (cmd == "get") {
        for (int c = startCore; c <= endCore; ++c) {
            req.startCore = c;
            req.entries = entries;
            req.count = GROUP_NUM;
            for (int i = 0; i < GROUP_NUM; ++i) {
                entries[i].id = GROUP0 + i;
            }
            if (ioctl(fd, IOCTL_GET, &req) == -1) {
                std::cerr << "get param fail, errno: " << errno << std::endl;
            }
            for (int i = 0; i < GROUP_NUM; ++i) {
                std::cout << "core" << c << ".group" << i << "=0x" << std::hex <<
                    req.entries[i].value << std::dec << std::endl;
            }
        }
    } else {
        int i = 0;
        for (auto &&it : params) {
            entries[i].id = it.first;
            entries[i].value = it.second;
            ++i;
        }
        req.startCore = startCore;
        req.endCore = endCore;
        req.entries = entries;
        req.count = i;
        if (ioctl(fd, IOCTL_SET, &req) == -1) {
            std::cerr << "set param fail, errno: " << errno << std::endl;
        }
    }
    close(fd);
    return 0;
}
}

int main(int argc, char *argv[])
{
    using namespace RegTool;
    std::string usage = "usage:\n"
                        "\tregtool get <start_core> <end_core>\n"
                        "\tregtool set <start_core> <end_core> <reg_list>";

    if (argc < GROUP_START) {
        std::cerr << usage << std::endl;
        return -1;
    }
    std::string cmd = argv[CMD];
    if (cmd != "get" && cmd != "set") {
        std::cerr << "cmd need to be set or get" << std::endl;
        return -1;
    }

    if (cmd == "get" && argc > GROUP_START) {
        std::cerr << usage << std::endl;
        return -1;
    }

    int startCore;
    int endCore;
    std::map<int, unsigned long long> params;
    if (Argparse(argc, argv, startCore, endCore, params) != 0) {
        return -1;
    }

    return RegOp(cmd, startCore, endCore, params);
}
