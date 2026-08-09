#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MC 服务器备份脚本
自动备份 Minecraft 服务器世界文件
"""

import os
import sys
import shutil
import zipfile
import datetime
import glob

# ====== 配置 ======
# 服务器目录
SERVER_DIR = r"./minecraft_server"
# 世界文件夹名
WORLD_NAME = "world"
# 备份保存目录
BACKUP_DIR = r"./backups"
# 保留最近 N 份备份
KEEP_BACKUPS = 10
# 是否压缩（zip）
USE_ZIP = True
# ==================

def log(msg):
    """打印日志"""
    time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{time_str}] {msg}")

def create_backup():
    """创建备份"""
    # 检查服务器目录
    world_path = os.path.join(SERVER_DIR, WORLD_NAME)
    if not os.path.exists(world_path):
        log(f"错误：找不到世界目录 {world_path}")
        return False

    # 创建备份目录
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        log(f"创建备份目录：{BACKUP_DIR}")

    # 生成备份文件名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    log(f"开始备份：{WORLD_NAME}")
    log(f"备份到：{backup_path}")

    try:
        if USE_ZIP:
            # zip 压缩备份
            zip_path = backup_path + ".zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(world_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, SERVER_DIR)
                        zipf.write(file_path, arcname)
            backup_size = os.path.getsize(zip_path) / 1024 / 1024
            log(f"备份完成！大小：{backup_size:.2f} MB")
        else:
            # 直接复制文件夹
            shutil.copytree(world_path, backup_path)
            log("备份完成！")

        return True

    except Exception as e:
        log(f"备份失败：{e}")
        return False

def cleanup_old_backups():
    """清理旧备份"""
    if not os.path.exists(BACKUP_DIR):
        return

    # 获取所有备份文件
    if USE_ZIP:
        backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "backup_*.zip")))
    else:
        backups = sorted([
            os.path.join(BACKUP_DIR, d) 
            for d in os.listdir(BACKUP_DIR) 
            if d.startswith("backup_") and os.path.isdir(os.path.join(BACKUP_DIR, d))
        ])

    # 删除多余的备份
    if len(backups) > KEEP_BACKUPS:
        to_delete = backups[:len(backups) - KEEP_BACKUPS]
        for old_backup in to_delete:
            try:
                if os.path.isdir(old_backup):
                    shutil.rmtree(old_backup)
                else:
                    os.remove(old_backup)
                log(f"删除旧备份：{os.path.basename(old_backup)}")
            except Exception as e:
                log(f"删除失败：{e}")

def main():
    log("=" * 40)
    log("MC 服务器备份脚本启动")
    log("=" * 40)

    # 创建备份
    success = create_backup()

    # 清理旧备份
    if success:
        cleanup_old_backups()

    log("=" * 40)
    log("备份任务结束")
    log("=" * 40)

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
