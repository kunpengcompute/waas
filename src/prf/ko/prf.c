/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved
*/

#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/smp.h>
#include <linux/fs.h>
#include <linux/cdev.h>
#include <linux/ioctl.h>
#include <linux/device.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/version.h>

#define VENDOR_ID_SHIFT 24
#define VENDOR_ID_MASK 0xFF
#define PART_ID_SHIFT 4
#define PART_ID_MASK 0xFFF
#define PRINT_ONLY 0x1111ffff
#define NOTHING_CHANGED 0xffffffff

#define MSRSTR(opcode) "msr " #opcode ", %0"
#define MSRASM(reg, opcode) asm volatile(MSRSTR(opcode)::"r"(reg))
#define WRITE_REG(para, opcode) \
    if ((para) != NOTHING_CHANGED) { \
        MSRASM(para, opcode); \
    } \

#define MRSSTR(opcode) "mrs %0, " #opcode ""
#define MRSASM(reg, opcode) asm volatile(MRSSTR(opcode) : "=r"(reg))
#define READ_REG(para, opcode) \
    if ((para) == PRINT_ONLY) { \
        MRSASM(para, opcode); \
    } \

#define GEN3 0xd02
#define GEN5 0xd06
const unsigned long SUPPORT_PART_ID[] = {
    GEN3,
    GEN5,
};

enum GORUP {
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
#define GROUP_NUM (GROUP_MAX - MAGIC)

#define IOCTL_MAGIC 'K'
#define IOCTL_SET _IOWR(IOCTL_MAGIC, 0, struct request)
#define IOCTL_GET _IOWR(IOCTL_MAGIC, 1, struct request)

static void write_cpu_registers(void *data)
{
    long long unsigned int *group = (long long unsigned int *)data;
    WRITE_REG(group[12], S3_1_c15_c0_0)
    WRITE_REG(group[13], S3_1_c15_c0_1)
    WRITE_REG(group[14], S3_1_c15_c0_4)
    WRITE_REG(group[15], S3_1_c11_c0_2)
    WRITE_REG(group[16], S3_1_c15_c2_0)
    WRITE_REG(group[17], S3_1_c15_c2_2)
    WRITE_REG(group[18], S3_1_c15_C2_5)
    WRITE_REG(group[1], S3_1_c15_C3_2)
    WRITE_REG(group[2], S3_1_c15_C3_3)
    WRITE_REG(group[19], S3_1_c15_C3_4)
    WRITE_REG(group[3], S3_1_c15_C5_3)
    WRITE_REG(group[4], S3_1_c15_C6_1)
    WRITE_REG(group[5], S3_1_c15_C6_3)
    WRITE_REG(group[6], S3_1_c15_C6_4)
    WRITE_REG(group[7], S3_1_c15_C6_5)
    WRITE_REG(group[8], S3_1_c15_C6_6)
    WRITE_REG(group[9], S3_1_c15_C6_7)
    WRITE_REG(group[10], S3_1_c15_C7_0)
    WRITE_REG(group[11], S3_1_c15_C7_1)
    WRITE_REG(group[20], S3_1_c15_C7_2)
    WRITE_REG(group[21], S3_1_c15_C7_3)
    WRITE_REG(group[22], S3_1_c15_C7_4)
    WRITE_REG(group[23], S3_1_c15_c7_5)
    WRITE_REG(group[24], S3_1_c15_C6_0)
    WRITE_REG(group[25], S3_1_c15_c8_3)
    WRITE_REG(group[26], S3_1_c15_c8_5)
    WRITE_REG(group[27], S3_1_c15_c8_6)
    WRITE_REG(group[0], S3_1_c15_c9_5)
    WRITE_REG(group[28], S3_1_c15_c8_7)
    WRITE_REG(group[29], S3_1_c15_c9_0)
    WRITE_REG(group[30], S3_1_c15_c4_6)
    WRITE_REG(group[31], S3_1_c15_c4_7)
    WRITE_REG(group[32], S3_1_c15_c5_2)
}

static void read_cpu_registers(void *data)
{
    long long unsigned int *group = (long long unsigned int *)data;
    READ_REG(group[12], S3_1_c15_c0_0)
    READ_REG(group[13], S3_1_c15_c0_1)
    READ_REG(group[14], S3_1_c15_c0_4)
    READ_REG(group[15], S3_1_c11_c0_2)
    READ_REG(group[16], S3_1_c15_c2_0)
    READ_REG(group[17], S3_1_c15_c2_2)
    READ_REG(group[18], S3_1_c15_C2_5)
    READ_REG(group[1], S3_1_c15_C3_2)
    READ_REG(group[2], S3_1_c15_C3_3)
    READ_REG(group[19], S3_1_c15_C3_4)
    READ_REG(group[3], S3_1_c15_C5_3)
    READ_REG(group[4], S3_1_c15_C6_1)
    READ_REG(group[5], S3_1_c15_C6_3)
    READ_REG(group[6], S3_1_c15_C6_4)
    READ_REG(group[7], S3_1_c15_C6_5)
    READ_REG(group[8], S3_1_c15_C6_6)
    READ_REG(group[9], S3_1_c15_C6_7)
    READ_REG(group[10], S3_1_c15_C7_0)
    READ_REG(group[11], S3_1_c15_C7_1)
    READ_REG(group[20], S3_1_c15_C7_2)
    READ_REG(group[21], S3_1_c15_C7_3)
    READ_REG(group[22], S3_1_c15_C7_4)
    READ_REG(group[23], S3_1_c15_c7_5)
    READ_REG(group[24], S3_1_c15_C6_0)
    READ_REG(group[25], S3_1_c15_c8_3)
    READ_REG(group[26], S3_1_c15_c8_5)
    READ_REG(group[27], S3_1_c15_c8_6)
    READ_REG(group[0], S3_1_c15_c9_5)
    READ_REG(group[28], S3_1_c15_c8_7)
    READ_REG(group[29], S3_1_c15_c9_0)
    READ_REG(group[30], S3_1_c15_c4_6)
    READ_REG(group[31], S3_1_c15_c4_7)
    READ_REG(group[32], S3_1_c15_c5_2)
}

struct entry {
    int __user group_id;
    long long unsigned int __user value;
};

struct request {
    int start_core;
    int end_core; // available on set
    struct entry __user *entries;
    size_t count;
};

static int handle_set_reg(int start_core, int end_core, struct entry *entries, size_t entry_num)
{
    int i;
    int index;
    int cpu;
    long long unsigned int *group;

    group = kmalloc(GROUP_NUM * sizeof(long long unsigned int), GFP_KERNEL);
    if (!group) {
        return -ENOMEM;
    }

    for (i = 0; i < GROUP_NUM; i++) {
        group[i] = NOTHING_CHANGED;
    }
    for (i = 0; i < entry_num; ++i) {
        if (entries[i].group_id < GROUP0 || entries[i].group_id >= GROUP_MAX) {
            pr_err("invalid group id\n");
            kfree(group);
            return -EINVAL;
        }
        index = entries[i].group_id - GROUP0;
        group[index] = entries[i].value;
    }

    if (start_core == NOTHING_CHANGED || end_core == NOTHING_CHANGED) {
        on_each_cpu(write_cpu_registers, group, 1);
    } else {
        for (cpu = start_core; cpu <= end_core; cpu++) {
            smp_call_function_single(cpu, write_cpu_registers, group, 1);
        }
    }
    kfree(group);
    return 0;
}

static int handle_get_reg(int cpu, struct entry *entries, size_t entry_num)
{
    int i;
    int index;
    long long unsigned int *group;

    group = kmalloc(GROUP_NUM * sizeof(long long unsigned int), GFP_KERNEL);
    if (!group) {
        return -ENOMEM;
    }
    for (i = 0; i < GROUP_NUM; i++) {
        group[i] = PRINT_ONLY;
    }

    smp_call_function_single(cpu, read_cpu_registers, group, 1);
    for (i = 0; i < entry_num; ++i) {
        if (entries[i].group_id < GROUP0 || entries[i].group_id >= GROUP_MAX) {
            pr_err("invalid group id\n");
            kfree(group);
            return -EINVAL;
        }
        index = entries[i].group_id - GROUP0;
        entries[i].value = group[index];
    }

    kfree(group);
    return 0;
}

static int handle_reg_ioctl(unsigned int cmd, void __user *arg)
{
    struct request __user *user_req = arg;
    struct request req;
    struct entry *entries;

    if (copy_from_user(&req, user_req, sizeof(req))) {
        pr_err("copy req from usr fail\n");
        return -EFAULT;
    }

    if (req.count > GROUP_NUM || req.count == 0) {
        pr_err("invalid request count\n");
        return -EINVAL;
    }

    entries = kmalloc(req.count * sizeof(struct entry), GFP_KERNEL);
    if (!entries) {
        return -ENOMEM;
    }

    if (copy_from_user(entries, req.entries, req.count * sizeof(struct entry))) {
        pr_err("copy entries from usr fail\n");
        kfree(entries);
        return -EFAULT;
    }

    if (cmd == IOCTL_SET) {
        if (handle_set_reg(req.start_core, req.end_core, entries, req.count) != 0) {
            pr_err("set reg fail\n");
            kfree(entries);
            return -EFAULT;
        }
    } else if (cmd == IOCTL_GET) {
        if (handle_get_reg(req.start_core, entries, req.count) != 0) {
            pr_err("get reg fail\n");
            kfree(entries);
            return -EFAULT;
        }

        if (copy_to_user(req.entries, entries, req.count * sizeof(struct entry))) {
            pr_err("copy entries to usr fail\n");
            kfree(entries);
            return -EFAULT;
        }
    }
    kfree(entries);
    return 0;
}

static long handle_ioctl(struct file *filp, unsigned int cmd, unsigned long arg)
{
    void __user *argp = (void __user *)arg;
    long ret = 0;
    switch (cmd) {
        case IOCTL_SET:
        case IOCTL_GET:
            ret = handle_reg_ioctl(cmd, argp);
            break;
        default:
            ret = -ENOTTY;
    }
    return ret;
}

static int check_cpu(void)
{
    int i = 0;
    unsigned long cpu_id = 0;
    unsigned long vendor_id;
    unsigned long part_id;
    MRSASM(cpu_id, MIDR_EL1);
    vendor_id = (cpu_id >> VENDOR_ID_SHIFT) & VENDOR_ID_MASK;
    part_id = (cpu_id >> PART_ID_SHIFT) & PART_ID_MASK;

    if (vendor_id == 0x48) {
        for (i = 0; i < sizeof(SUPPORT_PART_ID) / sizeof(SUPPORT_PART_ID[0]); i ++) {
            if (part_id == SUPPORT_PART_ID[i]) {
                return 0;
            }
        }
    }

    pr_err("Unsupport CPU, vendor id: 0x%lx, part id: 0x%lx\n", vendor_id, part_id);
    return -1;
}

static int open_dev(struct inode *, struct file *)
{
    pr_debug("Device opened\n");
    return 0;
}

static struct file_operations fops = {
    .open = open_dev,
    .release = NULL,
    .unlocked_ioctl = handle_ioctl,
    .owner = THIS_MODULE,

};

static struct cdev prf_cdev;
static dev_t dev_num;
static struct class *prf_class;
static struct device *prf_device;

static int __init init(void)
{
    int ret;
    if (check_cpu() != 0) {
        return -EFAULT;
    }

    ret = alloc_chrdev_region(&dev_num, 0, 1, "prf");
    if (ret < 0) {
        pr_err("Failed to allocate device number\n");
        return ret;
    }

    pr_info("prf registered with MAJOR: %d, MINOR: %d\n", MAJOR(dev_num), MINOR(dev_num));

#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 6, 0)
    prf_class = class_create(THIS_MODULE, "prf_class");
#else
    prf_class = class_create("prf_class");
#endif
    

    if (IS_ERR(prf_class)) {
        unregister_chrdev_region(dev_num, 1);
        return PTR_ERR(prf_class);
    }

    prf_device = device_create(prf_class, NULL, dev_num, NULL, "prf");

    if (IS_ERR(prf_device)) {
        class_destroy(prf_class);
        unregister_chrdev_region(dev_num, 1);
        return PTR_ERR(prf_device);
    }

    cdev_init(&prf_cdev, &fops);
    prf_cdev.owner = THIS_MODULE;
    ret = cdev_add(&prf_cdev, dev_num, 1);
    if (ret < 0) {
        pr_err("Failed to add char device\n");
        device_destroy(prf_class, dev_num);
        class_destroy(prf_class);
        unregister_chrdev_region(dev_num, 1);
        return ret;
    }

    pr_info("prf module loaded\n");
    return 0;
}

static void __exit fini(void)
{
    device_destroy(prf_class, dev_num);
    class_unregister(prf_class);
    class_destroy(prf_class);
    cdev_del(&prf_cdev);
    unregister_chrdev_region(dev_num, 1);
    pr_info("prf module unloaded\n");
}

module_init(init);
module_exit(fini);
MODULE_LICENSE("GPL");
MODULE_AUTHOR("Huawei");
MODULE_DESCRIPTION("prf module");
