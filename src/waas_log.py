# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import sys
import os
import tarfile
import glob
import datetime
from datetime import datetime, timezone, timedelta
from logging.handlers import RotatingFileHandler
import util

g_log = None


class CustomRotatingFileHandler(RotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_backup_count = util.LOG_NUM
        self.max_archive_count = 5

    def _open(self):
        if not os.path.exists(self.baseFilename):
            directory = os.path.dirname(self.baseFilename)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, mode=0o755, exist_ok=True)
            fd = os.open(self.baseFilename, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o640)
            return os.fdopen(fd, self.mode, encoding=self.encoding)
        else:
            return open(self.baseFilename, self.mode, encoding=self.encoding)

    def doRollover(self):
        # 关闭当前的文件句柄
        self.stream.close()
        # 调用父类的轮转方法
        super().doRollover()
        # 重新打开新的文件句柄
        self.stream = open(self.baseFilename, 'a', encoding=self.encoding)

        # 修改原日志的文件权限
        if os.path.exists(self.baseFilename):
            os.chmod(self.baseFilename, 0o640)
        
        # 修改备份日志文件的权限
        for i in range(self.backupCount):
            backup_filename = self.rotation_filename(self.baseFilename + '.%d' % (i + 1))
            if os.path.exists(backup_filename):
                os.chmod(backup_filename, 0o440)

        # 检查备份文件数量是否达到上限max_backup_count
        backup_files = glob.glob(self.baseFilename + '.*')
        backup_files = [f for f in backup_files if f != self.baseFilename]
        if len(backup_files) >= self.max_backup_count:
            self.archive_backups()

    def archive_backups(self):
        # 获取所有备份文件，排除当前日志文件
        backup_files = glob.glob(self.baseFilename + '.*')
        backup_files = [f for f in backup_files if f != self.baseFilename]
        if not backup_files:
            return

        # 确保LOG_PATH目录存在
        if not os.path.exists(util.LOG_SAVE_PATH):
            os.makedirs(util.LOG_SAVE_PATH, mode=0o755, exist_ok=True)
        
        # 生成压缩包文件名，包含时间戳，并指定保存路径
        end_time_raw = datetime.now(tz=timezone.utc) + timedelta(hours=8)
        timestamp = end_time_raw.strftime('%Y-%m-%d_%H-%M-%S')
        archive_name = f'WaasCodeploy_log_archive_{timestamp}.tar.gz'
        archive_path = os.path.join(util.LOG_SAVE_PATH, archive_name)

        # 创建备份文件
        with tarfile.open(archive_path, "w:gz") as tar:
            for file in backup_files:
                tar.add(file, arcname=os.path.basename(file))

        # 删除备份文件
        for file in backup_files:
            try:
                os.remove(file)
            except OSError:
                pass

        # 检查压缩包数量，超过max_archive_count则删除最老
        archives = glob.glob(os.path.join(util.LOG_SAVE_PATH, 'WaasCodeploy_log_archive_*.tar.gz'))
        if len(archives) > self.max_archive_count:
            # 找到最老的压缩包
            oldest = min(archives, key=os.path.getctime)
            try:
                os.remove(oldest)
            except OSError:
                pass


class Logger:
    def __init__(self, name, log_file, level='INFO'):
        # 创建logger
        self.logger = logging.getLogger(name)
        self.log_file = log_file
        self.level = level

        # 设置日志级别
        if level.upper() == 'DEBUG':
            self.logger.setLevel(logging.DEBUG)
        elif level.upper() == 'INFO':
            self.logger.setLevel(logging.INFO)
        elif level.upper() == 'WARNING':
            self.logger.setLevel(logging.WARNING)
        elif level.upper() == 'ERROR':
            self.logger.setLevel(logging.ERROR)
        elif level.upper() == 'CRITICAL':
            self.logger.setLevel(logging.CRITICAL)

        # 创建用于写入日志文件的handler
        fh = CustomRotatingFileHandler(
            log_file,
            mode='a',
            maxBytes=util.LOG_SIZE * 1024 * 1024,
            backupCount=util.LOG_NUM,
            encoding='utf-8'
        )
        fh.setLevel(self.logger.level)

        # 创建用于将信息打印到输出台的handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(self.logger.level)

        # 定义handler的输出格式
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        # 给logger添加handler
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def get_logger(self):
        return self.logger


def set_log_instance(log_level: str):
    global g_log
    logging_levels = {util.LOG_LEVEL_DEBUG, util.LOG_LEVEL_CRITICAL, util.LOG_LEVEL_ERROR, util.LOG_LEVEL_INFO, 
                        util.LOG_LEVEL_WARNING}
    if log_level.upper() not in logging_levels:
        return
    
    if g_log:
        for handler in g_log.handlers[:]:
            g_log.removeHandler(handler)
            if hasattr(handler, 'close'):
                handler.close()
    
    logger = logging.getLogger('WaasCodeploy')
    logger.setLevel(getattr(logging, log_level.upper()))

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        if hasattr(handler, 'close'):
            handler.close()

    # 创建Formatter实例
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 创建并配置RotatingFileHandler
    file_handler = CustomRotatingFileHandler(
        util.LOG_PATH,
        mode='a',
        maxBytes=util.LOG_SIZE * 1024 * 1024,
        backupCount=util.LOG_NUM,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    g_log = logger


def debug(msg: str, *args, **kwargs):
    global g_log
    if not g_log:
        set_log_instance(util.GLOBAL_LOG_LEVEL)
        g_log.debug(msg, *args, **kwargs)
    elif not os.path.exists(util.LOG_PATH):
        set_log_instance(util.GLOBAL_LOG_LEVEL)
        g_log.debug(msg, *args, **kwargs)
    else:
        g_log.debug(msg, *args, **kwargs)
        

def info(msg: str, *args, **kwargs):
    global g_log
    if not g_log:
        set_log_instance(util.GLOBAL_LOG_LEVEL)
        g_log.info(msg, *args, **kwargs)
    elif not os.path.exists(util.LOG_PATH):
        set_log_instance(util.GLOBAL_LOG_LEVEL)
        g_log.info(msg, *args, **kwargs)
    else:
        g_log.info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    global g_log
    if not g_log:
        set_log_instance(util.GLOBAL_LOG_LEVEL)
        g_log.warning(msg, *args, **kwargs)
    elif not os.path.exists(util.LOG_PATH):
        set_log_instance(util.GLOBAL_LOG_LEVEL)
        g_log.warning(msg, *args, **kwargs)
    else:
        g_log.warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    global g_log
    if not g_log:
        set_log_instance(util.GLOBAL_LOG_LEVEL)
        g_log.error(msg, *args, **kwargs)
    elif not os.path.exists(util.LOG_PATH):
        set_log_instance(util.GLOBAL_LOG_LEVEL)
        g_log.error(msg, *args, **kwargs)
    else:
        g_log.error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    global g_log
    if not g_log:
        set_log_instance(util.GLOBAL_LOG_LEVEL)
        g_log.critical(msg, *args, **kwargs)
    elif not os.path.exists(util.LOG_PATH):
        set_log_instance(util.GLOBAL_LOG_LEVEL)
        g_log.critical(msg, *args, **kwargs)
    else:
        g_log.critical(msg, *args, **kwargs)