# -*- coding: utf-8 -*-
"""
PC 优化大师 - 磁盘清理与游戏优化工具
安全、可视化的电脑清理和性能优化程序
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import os
import sys
import threading
import ctypes
import datetime
import json
import shutil

# ============================================================
# 工具函数
# ============================================================

def run_powershell(cmd, timeout=300):
    """运行 PowerShell 命令并返回输出"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='replace'
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "命令执行超时", -1
    except Exception as e:
        return "", str(e), -1

def run_powershell_admin(cmd, timeout=300):
    """以管理员身份运行 PowerShell 命令"""
    try:
        # 创建临时脚本文件
        script_path = os.path.join(os.environ['TEMP'], f'pc_opt_temp_{datetime.datetime.now().strftime("%H%M%S")}.ps1')
        with open(script_path, 'w', encoding='utf-8-sig') as f:
            f.write(cmd)
            f.write('\n')
        
        # 以管理员身份运行
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
             f"Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"{script_path}\"'"],
            capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='replace'
        )
        # 清理临时文件
        try:
            os.remove(script_path)
        except:
            pass
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), -1

def is_admin():
    """检查是否以管理员身份运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def format_size(bytes_val):
    """格式化字节大小为人类可读"""
    try:
        bytes_val = float(bytes_val)
    except:
        return "未知"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(bytes_val) < 1024.0:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"

def get_disk_info():
    """获取磁盘信息"""
    cmd = """
    Get-PSDrive -PSProvider FileSystem | ForEach-Object {
        $used = $_.Used
        $free = $_.Free
        $total = $used + $free
        $percent = if ($total -gt 0) { [math]::Round($free / $total * 100, 1) } else { 0 }
        [PSCustomObject]@{
            Drive = $_.Name + ":"
            Used = $used
            Free = $free
            Total = $total
            FreePercent = $percent
        }
    } | ConvertTo-Json
    """
    stdout, stderr, rc = run_powershell(cmd)
    try:
        return json.loads(stdout)
    except:
        return []

def get_system_info():
    """获取系统信息"""
    cmd = """
    $os = Get-CimInstance Win32_OperatingSystem
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $cs = Get-CimInstance Win32_ComputerSystem
    $gpu = Get-CimInstance Win32_VideoController | Select-Object -First 1
    [PSCustomObject]@{
        OS = $os.Caption
        Version = $os.Version
        Build = $os.BuildNumber
        CPU = $cpu.Name
        Cores = $cpu.NumberOfCores
        Threads = $cpu.NumberOfLogicalProcessors
        RAM = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
        GPU = if ($gpu) { $gpu.Name } else { "未知" }
        Manufacturer = $cs.Manufacturer
        Model = $cs.Model
    } | ConvertTo-Json
    """
    stdout, stderr, rc = run_powershell(cmd)
    try:
        return json.loads(stdout)
    except:
        return {}

# ============================================================
# 清理功能
# ============================================================

class CleanManager:
    """清理管理器"""
    
    CLEAN_ITEMS = [
        {
            'id': 'temp_files',
            'name': '临时文件',
            'desc': '系统和用户临时文件（%TEMP%、Windows\\Temp）',
            'risk': 'L1',
            'safe': True,
            'scan_cmd': """
                $total = 0
                $paths = @($env:TEMP, "C:\\Windows\\Temp")
                foreach ($p in $paths) {
                    if (Test-Path $p) {
                        $files = Get-ChildItem $p -Recurse -Force -ErrorAction SilentlyContinue -File
                        $total += ($files | Measure-Object Length -Sum).Sum
                    }
                }
                [PSCustomObject]@{ Size = $total } | ConvertTo-Json
            """,
            'clean_cmd': """
                $freed = 0
                $paths = @($env:TEMP, "C:\\Windows\\Temp")
                foreach ($p in $paths) {
                    if (Test-Path $p) {
                        $files = Get-ChildItem $p -Recurse -Force -ErrorAction SilentlyContinue -File
                        $freed += ($files | Measure-Object Length -Sum).Sum
                        Remove-Item $p\\* -Recurse -Force -ErrorAction SilentlyContinue
                    }
                }
                [PSCustomObject]@{ Freed = $freed } | ConvertTo-Json
            """
        },
        {
            'id': 'update_cache',
            'name': 'Windows 更新缓存',
            'desc': 'SoftwareDistribution\\Download 中的更新安装包',
            'risk': 'L1',
            'safe': True,
            'scan_cmd': """
                $path = "C:\\Windows\\SoftwareDistribution\\Download"
                $size = 0
                if (Test-Path $path) {
                    $files = Get-ChildItem $path -Recurse -Force -ErrorAction SilentlyContinue -File
                    $size = ($files | Measure-Object Length -Sum).Sum
                }
                [PSCustomObject]@{ Size = $size } | ConvertTo-Json
            """,
            'clean_cmd': """
                $freed = 0
                $path = "C:\\Windows\\SoftwareDistribution\\Download"
                if (Test-Path $path) {
                    $files = Get-ChildItem $path -Recurse -Force -ErrorAction SilentlyContinue -File
                    $freed = ($files | Measure-Object Length -Sum).Sum
                    Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
                    Remove-Item $path\\* -Recurse -Force -ErrorAction SilentlyContinue
                    Start-Service wuauserv -ErrorAction SilentlyContinue
                }
                [PSCustomObject]@{ Freed = $freed } | ConvertTo-Json
            """
        },
        {
            'id': 'browser_cache',
            'name': '浏览器缓存',
            'desc': 'Chrome、Edge 浏览器的网页缓存（不影响书签、密码、历史记录）',
            'risk': 'L1',
            'safe': True,
            'scan_cmd': """
                $total = 0
                $browsers = @(
                    @{Name="Chrome"; Path="$env:LOCALAPPDATA\\Google\\Chrome\\User Data"},
                    @{Name="Edge"; Path="$env:LOCALAPPDATA\\Microsoft\\Edge\\User Data"}
                )
                foreach ($b in $browsers) {
                    if (Test-Path $b.Path) {
                        $profiles = Get-ChildItem $b.Path -Directory | Where-Object { $_.Name -eq "Default" -or $_.Name -like "Profile *" }
                        foreach ($p in $profiles) {
                            $cachePaths = @("Cache", "Code Cache", "GPUCache", "Service Worker\\CacheStorage")
                            foreach ($cp in $cachePaths) {
                                $full = Join-Path $p.FullName $cp
                                if (Test-Path $full) {
                                    $files = Get-ChildItem $full -Recurse -Force -ErrorAction SilentlyContinue -File
                                    $total += ($files | Measure-Object Length -Sum).Sum
                                }
                            }
                        }
                    }
                }
                [PSCustomObject]@{ Size = $total } | ConvertTo-Json
            """,
            'clean_cmd': """
                $freed = 0
                $browsers = @(
                    @{Name="Chrome"; Path="$env:LOCALAPPDATA\\Google\\Chrome\\User Data"},
                    @{Name="Edge"; Path="$env:LOCALAPPDATA\\Microsoft\\Edge\\User Data"}
                )
                foreach ($b in $browsers) {
                    if (Test-Path $b.Path) {
                        $profiles = Get-ChildItem $b.Path -Directory | Where-Object { $_.Name -eq "Default" -or $_.Name -like "Profile *" }
                        foreach ($p in $profiles) {
                            $cachePaths = @("Cache", "Code Cache", "GPUCache", "Service Worker\\CacheStorage")
                            foreach ($cp in $cachePaths) {
                                $full = Join-Path $p.FullName $cp
                                if (Test-Path $full) {
                                    $files = Get-ChildItem $full -Recurse -Force -ErrorAction SilentlyContinue -File
                                    $freed += ($files | Measure-Object Length -Sum).Sum
                                    Remove-Item $full\\* -Recurse -Force -ErrorAction SilentlyContinue
                                }
                            }
                        }
                    }
                }
                [PSCustomObject]@{ Freed = $freed } | ConvertTo-Json
            """
        },
        {
            'id': 'thumb_cache',
            'name': '缩略图缓存',
            'desc': 'Windows 资源管理器的缩略图缓存',
            'risk': 'L1',
            'safe': True,
            'scan_cmd': """
                $path = "$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer"
                $size = 0
                if (Test-Path $path) {
                    $files = Get-ChildItem $path -Filter "thumbcache_*" -Force -ErrorAction SilentlyContinue -File
                    $size = ($files | Measure-Object Length -Sum).Sum
                }
                [PSCustomObject]@{ Size = $size } | ConvertTo-Json
            """,
            'clean_cmd': """
                $freed = 0
                $path = "$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer"
                if (Test-Path $path) {
                    $files = Get-ChildItem $path -Filter "thumbcache_*" -Force -ErrorAction SilentlyContinue -File
                    $freed = ($files | Measure-Object Length -Sum).Sum
                    Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
                    Remove-Item $path\\thumbcache_* -Force -ErrorAction SilentlyContinue
                    Start-Process explorer
                }
                [PSCustomObject]@{ Freed = $freed } | ConvertTo-Json
            """
        },
        {
            'id': 'shader_cache',
            'name': '着色器缓存',
            'desc': 'NVIDIA、Direct3D 着色器缓存（清理后游戏首次加载会重建）',
            'risk': 'L1',
            'safe': True,
            'scan_cmd': """
                $total = 0
                $paths = @(
                    "$env:LOCALAPPDATA\\NVIDIA\\DXCache",
                    "$env:LOCALAPPDATA\\NVIDIA\\GLCache",
                    "$env:LOCALAPPDATA\\D3DSCache"
                )
                foreach ($p in $paths) {
                    if (Test-Path $p) {
                        $files = Get-ChildItem $p -Recurse -Force -ErrorAction SilentlyContinue -File
                        $total += ($files | Measure-Object Length -Sum).Sum
                    }
                }
                [PSCustomObject]@{ Size = $total } | ConvertTo-Json
            """,
            'clean_cmd': """
                $freed = 0
                $paths = @(
                    "$env:LOCALAPPDATA\\NVIDIA\\DXCache",
                    "$env:LOCALAPPDATA\\NVIDIA\\GLCache",
                    "$env:LOCALAPPDATA\\D3DSCache"
                )
                foreach ($p in $paths) {
                    if (Test-Path $p) {
                        $files = Get-ChildItem $p -Recurse -Force -ErrorAction SilentlyContinue -File
                        $freed += ($files | Measure-Object Length -Sum).Sum
                        Remove-Item $p\\* -Recurse -Force -ErrorAction SilentlyContinue
                    }
                }
                [PSCustomObject]@{ Freed = $freed } | ConvertTo-Json
            """
        },
        {
            'id': 'system_logs',
            'name': '系统日志和错误报告',
            'desc': 'Windows 日志、错误报告、蓝屏转储文件',
            'risk': 'L1',
            'safe': True,
            'scan_cmd': """
                $total = 0
                $paths = @(
                    "C:\\Windows\\Logs",
                    "$env:ProgramData\\Microsoft\\Windows\\WER",
                    "C:\\Windows\\Minidump"
                )
                foreach ($p in $paths) {
                    if (Test-Path $p) {
                        $files = Get-ChildItem $p -Recurse -Force -ErrorAction SilentlyContinue -File
                        $total += ($files | Measure-Object Length -Sum).Sum
                    }
                }
                $dmp = "C:\\Windows\\MEMORY.DMP"
                if (Test-Path $dmp) {
                    $total += (Get-Item $dmp -Force).Length
                }
                [PSCustomObject]@{ Size = $total } | ConvertTo-Json
            """,
            'clean_cmd': """
                $freed = 0
                $paths = @(
                    "C:\\Windows\\Logs",
                    "$env:ProgramData\\Microsoft\\Windows\\WER",
                    "C:\\Windows\\Minidump"
                )
                foreach ($p in $paths) {
                    if (Test-Path $p) {
                        $files = Get-ChildItem $p -Recurse -Force -ErrorAction SilentlyContinue -File
                        $freed += ($files | Measure-Object Length -Sum).Sum
                        Remove-Item $p\\* -Recurse -Force -ErrorAction SilentlyContinue
                    }
                }
                $dmp = "C:\\Windows\\MEMORY.DMP"
                if (Test-Path $dmp) {
                    $freed += (Get-Item $dmp -Force).Length
                    Remove-Item $dmp -Force -ErrorAction SilentlyContinue
                }
                [PSCustomObject]@{ Freed = $freed } | ConvertTo-Json
            """
        },
        {
            'id': 'prefetch',
            'name': '预读取缓存',
            'desc': 'Windows Prefetch 预读取文件（清理后程序首次启动略慢）',
            'risk': 'L1',
            'safe': True,
            'scan_cmd': """
                $path = "C:\\Windows\\Prefetch"
                $size = 0
                if (Test-Path $path) {
                    $files = Get-ChildItem $path -Force -ErrorAction SilentlyContinue -File
                    $size = ($files | Measure-Object Length -Sum).Sum
                }
                [PSCustomObject]@{ Size = $size } | ConvertTo-Json
            """,
            'clean_cmd': """
                $freed = 0
                $path = "C:\\Windows\\Prefetch"
                if (Test-Path $path) {
                    $files = Get-ChildItem $path -Force -ErrorAction SilentlyContinue -File
                    $freed = ($files | Measure-Object Length -Sum).Sum
                    Remove-Item $path\\* -Force -ErrorAction SilentlyContinue
                }
                [PSCustomObject]@{ Freed = $freed } | ConvertTo-Json
            """
        },
        {
            'id': 'recycle_bin',
            'name': '回收站',
            'desc': '已删除的文件（⚠️ 清理后不可恢复！）',
            'risk': 'L1-不可逆',
            'safe': False,
            'scan_cmd': """
                $size = 0
                $shell = New-Object -ComObject Shell.Application
                $recycle = $shell.NameSpace(10)
                if ($recycle) {
                    $items = $recycle.Items()
                    foreach ($item in $items) {
                        $size += $item.Size
                    }
                }
                [PSCustomObject]@{ Size = $size } | ConvertTo-Json
            """,
            'clean_cmd': """
                $freed = 0
                $shell = New-Object -ComObject Shell.Application
                $recycle = $shell.NameSpace(10)
                if ($recycle) {
                    $items = $recycle.Items()
                    foreach ($item in $items) {
                        $freed += $item.Size
                    }
                }
                Clear-RecycleBin -Force -ErrorAction SilentlyContinue
                [PSCustomObject]@{ Freed = $freed } | ConvertTo-Json
            """
        },
    ]
    
    @staticmethod
    def scan_item(item_id):
        """扫描单个清理项"""
        for item in CleanManager.CLEAN_ITEMS:
            if item['id'] == item_id:
                stdout, stderr, rc = run_powershell(item['scan_cmd'])
                try:
                    data = json.loads(stdout)
                    return data.get('Size', 0)
                except:
                    return 0
        return 0
    
    @staticmethod
    def clean_item(item_id):
        """清理单个项目"""
        for item in CleanManager.CLEAN_ITEMS:
            if item['id'] == item_id:
                stdout, stderr, rc = run_powershell(item['clean_cmd'])
                try:
                    data = json.loads(stdout)
                    return data.get('Freed', 0)
                except:
                    return 0
        return 0


# ============================================================
# 游戏优化功能
# ============================================================

class GameOptimizer:
    """游戏优化管理器"""
    
    OPTIMIZE_ITEMS = [
        {
            'id': 'power_plan',
            'name': '高性能电源计划',
            'desc': '切换到高性能电源计划，释放 CPU 全部性能',
            'risk': 'L2',
            'category': '系统设置',
            'check_cmd': """
                $active = (powercfg /getactivescheme) -split ' ' | Where-Object { $_ -match '[0-9a-f]{8}-' } | Select-Object -First 1
                $highPerf = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
                $isHighPerf = $active -eq $highPerf
                [PSCustomObject]@{ Active = $active; IsHighPerf = $isHighPerf } | ConvertTo-Json
            """,
            'apply_cmd': """
                $original = (powercfg /getactivescheme) -split ' ' | Where-Object { $_ -match '[0-9a-f]{8}-' } | Select-Object -First 1
                powercfg /s 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
                [PSCustomObject]@{ Original = $original; Success = $true } | ConvertTo-Json
            """,
            'revert_cmd_template': 'powercfg /s {0}'
        },
        {
            'id': 'game_mode',
            'name': '开启游戏模式',
            'desc': '开启 Windows 游戏模式，优化游戏时的系统资源分配',
            'risk': 'L2',
            'category': '系统设置',
            'check_cmd': """
                $path = "HKCU:\\Software\\Microsoft\\GameBar"
                $val = Get-ItemProperty -Path $path -Name "AutoGameModeEnabled" -ErrorAction SilentlyContinue
                $enabled = if ($val) { $val.AutoGameModeEnabled -eq 1 } else { $false }
                [PSCustomObject]@{ Enabled = $enabled } | ConvertTo-Json
            """,
            'apply_cmd': """
                $path = "HKCU:\\Software\\Microsoft\\GameBar"
                if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
                Set-ItemProperty -Path $path -Name "AutoGameModeEnabled" -Value 1 -Type DWord
                [PSCustomObject]@{ Success = $true } | ConvertTo-Json
            """,
            'revert_cmd': 'Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\GameBar" -Name "AutoGameModeEnabled" -Value 0 -Type DWord'
        },
        {
            'id': 'disable_gamedvr',
            'name': '关闭 Game DVR 后台录制',
            'desc': '关闭 Xbox 后台录制功能，减少游戏时的系统开销',
            'risk': 'L2',
            'category': '系统设置',
            'check_cmd': """
                $path = "HKCU:\\System\\GameConfigStore"
                $val = Get-ItemProperty -Path $path -Name "GameDVR_Enabled" -ErrorAction SilentlyContinue
                $enabled = if ($val) { $val.GameDVR_Enabled -eq 1 } else { $true }
                [PSCustomObject]@{ Enabled = $enabled } | ConvertTo-Json
            """,
            'apply_cmd': """
                $path = "HKCU:\\System\\GameConfigStore"
                if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
                Set-ItemProperty -Path $path -Name "GameDVR_Enabled" -Value 0 -Type DWord
                $path2 = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\GameDVR"
                if (-not (Test-Path $path2)) { New-Item -Path $path2 -Force | Out-Null }
                Set-ItemProperty -Path $path2 -Name "AppCaptureEnabled" -Value 0 -Type DWord
                [PSCustomObject]@{ Success = $true } | ConvertTo-Json
            """,
            'revert_cmd': '''
                Set-ItemProperty -Path "HKCU:\\System\\GameConfigStore" -Name "GameDVR_Enabled" -Value 1 -Type DWord
                Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\GameDVR" -Name "AppCaptureEnabled" -Value 1 -Type DWord
            '''
        },
        {
            'id': 'hags',
            'name': '开启硬件加速 GPU 计划 (HAGS)',
            'desc': '开启硬件加速 GPU 调度，可能改善游戏帧率（需重启生效）',
            'risk': 'L2',
            'category': '显卡设置',
            'check_cmd': """
                $path = "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers"
                $val = Get-ItemProperty -Path $path -Name "HwSchMode" -ErrorAction SilentlyContinue
                $enabled = if ($val) { $val.HwSchMode -eq 2 } else { $false }
                $build = [int](Get-CimInstance Win32_OperatingSystem).BuildNumber
                $supported = $build -ge 19041
                [PSCustomObject]@{ Enabled = $enabled; Supported = $supported } | ConvertTo-Json
            """,
            'apply_cmd': """
                $path = "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers"
                $original = (Get-ItemProperty -Path $path -Name "HwSchMode" -ErrorAction SilentlyContinue).HwSchMode
                Set-ItemProperty -Path $path -Name "HwSchMode" -Value 2 -Type DWord
                [PSCustomObject]@{ Original = $original; Success = $true; NeedReboot = $true } | ConvertTo-Json
            """,
            'revert_cmd_template': 'Set-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers" -Name "HwSchMode" -Value {0} -Type DWord'
        },
    ]
    
    @staticmethod
    def check_item(item_id):
        """检查优化项状态"""
        for item in GameOptimizer.OPTIMIZE_ITEMS:
            if item['id'] == item_id:
                stdout, stderr, rc = run_powershell(item['check_cmd'])
                try:
                    return json.loads(stdout)
                except:
                    return {}
        return {}
    
    @staticmethod
    def apply_item(item_id):
        """应用优化项"""
        for item in GameOptimizer.OPTIMIZE_ITEMS:
            if item['id'] == item_id:
                stdout, stderr, rc = run_powershell(item['apply_cmd'])
                try:
                    return json.loads(stdout)
                except:
                    return {}
        return {}


# ============================================================
# 主程序 GUI
# ============================================================

class PCOptimizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PC 优化大师 - 磁盘清理与游戏优化")
        self.root.geometry("960x680")
        self.root.minsize(860, 600)
        self.root.configure(bg='#f0f2f5')
        
        # 设置样式
        self.setup_styles()
        
        # 状态变量
        self.scan_results = {}
        self.clean_checkboxes = {}
        self.optimize_checkboxes = {}
        self.is_scanning = False
        self.is_cleaning = False
        
        # 创建界面
        self.create_widgets()
        
        # 加载系统信息
        self.load_system_info()
    
    def setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 主色调
        primary = '#2563eb'
        primary_light = '#3b82f6'
        success = '#10b981'
        warning = '#f59e0b'
        danger = '#ef4444'
        bg = '#f0f2f5'
        card_bg = '#ffffff'
        text_primary = '#1f2937'
        text_secondary = '#6b7280'
        
        style.configure('TFrame', background=bg)
        style.configure('Card.TFrame', background=card_bg, relief='flat')
        
        style.configure('TLabel', background=bg, foreground=text_primary, font=('Microsoft YaHei UI', 9))
        style.configure('Title.TLabel', background=card_bg, foreground=text_primary, font=('Microsoft YaHei UI', 14, 'bold'))
        style.configure('Subtitle.TLabel', background=card_bg, foreground=text_secondary, font=('Microsoft YaHei UI', 9))
        style.configure('Sidebar.TLabel', background='#1e293b', foreground='#94a3b8', font=('Microsoft YaHei UI', 10))
        style.configure('SidebarActive.TLabel', background='#2563eb', foreground='white', font=('Microsoft YaHei UI', 10, 'bold'))
        style.configure('SidebarTitle.TLabel', background='#1e293b', foreground='#f1f5f9', font=('Microsoft YaHei UI', 12, 'bold'))
        
        style.configure('TButton', font=('Microsoft YaHei UI', 9), padding=8)
        style.configure('Primary.TButton', font=('Microsoft YaHei UI', 9, 'bold'), padding=8)
        style.map('Primary.TButton',
                  background=[('active', '#1d4ed8'), ('!disabled', '#2563eb')],
                  foreground=[('!disabled', 'white')])
        
        style.configure('Success.TButton', font=('Microsoft YaHei UI', 9, 'bold'), padding=8)
        style.map('Success.TButton',
                  background=[('active', '#059669'), ('!disabled', '#10b981')],
                  foreground=[('!disabled', 'white')])
        
        style.configure('TCheckbutton', background=card_bg, font=('Microsoft YaHei UI', 9))
        
        style.configure('TNotebook', background=bg, borderwidth=0)
        style.configure('TNotebook.Tab', padding=[20, 10], font=('Microsoft YaHei UI', 9))
        
        style.configure('Horizontal.TProgressbar', thickness=20)
        
        # 自定义标签
        self.colors = {
            'primary': primary,
            'success': success,
            'warning': warning,
            'danger': danger,
            'bg': bg,
            'card_bg': card_bg,
            'text_primary': text_primary,
            'text_secondary': text_secondary,
            'sidebar_bg': '#1e293b',
        }
    
    def create_widgets(self):
        """创建主界面"""
        # 主容器
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # 左侧导航栏
        self.sidebar = tk.Frame(main_container, bg='#1e293b', width=200)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        
        # Logo 和标题
        logo_frame = tk.Frame(self.sidebar, bg='#1e293b')
        logo_frame.pack(fill=tk.X, pady=(20, 30), padx=15)
        
        tk.Label(logo_frame, text="⚡ PC 优化大师", bg='#1e293b', fg='#f1f5f9',
                 font=('Microsoft YaHei UI', 13, 'bold')).pack(anchor='w')
        tk.Label(logo_frame, text="v1.0 安全清理与优化", bg='#1e293b', fg='#64748b',
                 font=('Microsoft YaHei UI', 8)).pack(anchor='w', pady=(2, 0))
        
        # 导航按钮
        self.nav_buttons = []
        nav_items = [
            ('📊', '系统概览', self.show_overview),
            ('🧹', '磁盘清理', self.show_cleanup),
            ('🎮', '游戏优化', self.show_game_boost),
            ('⚙️', '系统优化', self.show_system_tuning),
            ('🔧', '实用工具', self.show_tools),
        ]
        
        for icon, name, cmd in nav_items:
            btn_frame = tk.Frame(self.sidebar, bg='#1e293b', cursor='hand2')
            btn_frame.pack(fill=tk.X, padx=8, pady=2)
            
            lbl = tk.Label(btn_frame, text=f"  {icon}  {name}", bg='#1e293b', fg='#94a3b8',
                           font=('Microsoft YaHei UI', 10), anchor='w', padx=10, pady=10)
            lbl.pack(fill=tk.X)
            
            btn_frame.bind('<Button-1>', lambda e, c=cmd, l=lbl: self.nav_click(c, l))
            lbl.bind('<Button-1>', lambda e, c=cmd, l=lbl: self.nav_click(c, l))
            btn_frame.bind('<Enter>', lambda e, f=btn_frame, l=lbl: self.nav_hover_enter(f, l))
            btn_frame.bind('<Leave>', lambda e, f=btn_frame, l=lbl: self.nav_hover_leave(f, l))
            
            self.nav_buttons.append((btn_frame, lbl))
        
        # 底部管理员状态
        admin_frame = tk.Frame(self.sidebar, bg='#1e293b')
        admin_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=15, padx=15)
        
        admin_status = "已获得管理员权限" if is_admin() else "未获得管理员权限"
        admin_color = '#10b981' if is_admin() else '#f59e0b'
        tk.Label(admin_frame, text=f"{'✓' if is_admin() else '⚠'}  {admin_status}",
                 bg='#1e293b', fg=admin_color, font=('Microsoft YaHei UI', 8)).pack(anchor='w')
        
        if not is_admin():
            tk.Label(admin_frame, text="部分功能需要管理员权限",
                     bg='#1e293b', fg='#64748b', font=('Microsoft YaHei UI', 7)).pack(anchor='w', pady=(2, 0))
        
        # 右侧内容区
        self.content = tk.Frame(main_container, bg='#f0f2f5')
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 内容容器
        self.content_frame = tk.Frame(self.content, bg='#f0f2f5')
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 默认显示概览页
        self.show_overview()
        # 高亮第一个导航项
        if self.nav_buttons:
            self.nav_hover_enter(self.nav_buttons[0][0], self.nav_buttons[0][1])
            self.nav_buttons[0][1].configure(bg='#2563eb', fg='white')
    
    def nav_click(self, cmd, label):
        """导航点击"""
        # 重置所有按钮样式
        for frame, lbl in self.nav_buttons:
            frame.configure(bg='#1e293b')
            lbl.configure(bg='#1e293b', fg='#94a3b8')
        
        # 设置当前激活
        label.configure(bg='#2563eb', fg='white')
        
        # 执行命令
        cmd()
    
    def nav_hover_enter(self, frame, label):
        """导航悬停进入"""
        if label.cget('bg') != '#2563eb':
            frame.configure(bg='#334155')
            label.configure(bg='#334155', fg='#e2e8f0')
    
    def nav_hover_leave(self, frame, label):
        """导航悬停离开"""
        if label.cget('bg') != '#2563eb':
            frame.configure(bg='#1e293b')
            label.configure(bg='#1e293b', fg='#94a3b8')
    
    def clear_content(self):
        """清空内容区"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def create_card(self, parent, title="", subtitle=""):
        """创建卡片容器"""
        card = tk.Frame(parent, bg='white', highlightbackground='#e5e7eb', 
                       highlightthickness=1, bd=0)
        card.pack(fill=tk.X, pady=8)
        
        if title:
            header = tk.Frame(card, bg='white')
            header.pack(fill=tk.X, padx=16, pady=(14, 8))
            
            tk.Label(header, text=title, bg='white', fg='#1f2937',
                     font=('Microsoft YaHei UI', 12, 'bold')).pack(anchor='w')
            
            if subtitle:
                tk.Label(header, text=subtitle, bg='white', fg='#6b7280',
                         font=('Microsoft YaHei UI', 9)).pack(anchor='w', pady=(2, 0))
        
        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.X, padx=16, pady=(0, 14))
        
        return card, body
    
    # ============================================================
    # 系统概览页
    # ============================================================
    
    def show_overview(self):
        """显示系统概览页"""
        self.clear_content()
        
        # 页面标题
        title_frame = tk.Frame(self.content_frame, bg='#f0f2f5')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(title_frame, text="系统概览", bg='#f0f2f5', fg='#1f2937',
                 font=('Microsoft YaHei UI', 18, 'bold')).pack(anchor='w')
        tk.Label(title_frame, text="查看电脑状态和磁盘使用情况", bg='#f0f2f5', fg='#6b7280',
                 font=('Microsoft YaHei UI', 10)).pack(anchor='w', pady=(2, 0))
        
        # 系统信息卡片
        sys_card, sys_body = self.create_card(self.content_frame, "系统信息", "你的电脑配置")
        
        # 系统信息网格
        self.sys_info_labels = {}
        info_items = [
            ('操作系统', 'os'),
            ('CPU 处理器', 'cpu'),
            ('核心/线程', 'cores'),
            ('内存大小', 'ram'),
            ('显卡', 'gpu'),
            ('电脑型号', 'model'),
        ]
        
        for i, (label, key) in enumerate(info_items):
            row = i // 2
            col = i % 2
            
            item_frame = tk.Frame(sys_body, bg='white')
            item_frame.grid(row=row, column=col, sticky='ew', padx=5, pady=6)
            sys_body.grid_columnconfigure(col, weight=1)
            
            tk.Label(item_frame, text=label, bg='white', fg='#6b7280',
                     font=('Microsoft YaHei UI', 9)).pack(anchor='w')
            val_label = tk.Label(item_frame, text="加载中...", bg='white', fg='#1f2937',
                                font=('Microsoft YaHei UI', 10, 'bold'))
            val_label.pack(anchor='w', pady=(2, 0))
            self.sys_info_labels[key] = val_label
        
        # 磁盘状态卡片
        disk_card, disk_body = self.create_card(self.content_frame, "磁盘状态", "各磁盘分区使用情况")
        
        self.disk_frames = {}
        self.disk_progress = {}
        self.disk_info_labels = {}
        
        # 磁盘信息容器
        disk_container = tk.Frame(disk_body, bg='white')
        disk_container.pack(fill=tk.X)
        
        # 刷新按钮
        btn_frame = tk.Frame(disk_card, bg='white')
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 14))
        ttk.Button(btn_frame, text="🔄 刷新磁盘信息", command=self.load_disk_info).pack(side=tk.LEFT)
        
        # 快速操作卡片
        quick_card, quick_body = self.create_card(self.content_frame, "快速操作", "一键执行常用操作")
        
        quick_container = tk.Frame(quick_body, bg='white')
        quick_container.pack(fill=tk.X)
        
        quick_actions = [
            ('🧹 一键清理', '快速清理系统垃圾文件', self.show_cleanup, '#10b981'),
            ('🎮 游戏加速', '优化系统设置提升游戏性能', self.show_game_boost, '#8b5cf6'),
            ('📊 扫描大文件', '找出占用空间的大文件', self.show_tools, '#f59e0b'),
            ('⚙️ 启动项管理', '管理开机自启动程序', self.show_system_tuning, '#3b82f6'),
        ]
        
        for i, (title, desc, cmd, color) in enumerate(quick_actions):
            action_frame = tk.Frame(quick_container, bg='white', cursor='hand2',
                                   highlightbackground='#e5e7eb', highlightthickness=1)
            action_frame.grid(row=0, column=i, sticky='nsew', padx=5, pady=5)
            quick_container.grid_columnconfigure(i, weight=1)
            
            action_frame.bind('<Button-1>', lambda e, c=cmd: c())
            
            inner = tk.Frame(action_frame, bg='white')
            inner.pack(padx=15, pady=15, fill=tk.X)
            
            tk.Label(inner, text=title, bg='white', fg=color,
                     font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w')
            tk.Label(inner, text=desc, bg='white', fg='#6b7280',
                     font=('Microsoft YaHei UI', 8), wraplength=140, justify='left').pack(anchor='w', pady=(4, 0))
        
        # 安全提示卡片
        tip_card, tip_body = self.create_card(self.content_frame, "安全提示")
        
        tip_text = ("✅ 所有清理操作仅删除可恢复的缓存和临时文件\n"
                   "✅ 不会删除你的个人文件、文档、照片和下载内容\n"
                   "✅ 系统优化操作均可撤销，提供回滚功能\n"
                   "⚠️  回收站、Windows.old 等不可逆操作会单独提示确认")
        
        tip_label = tk.Label(tip_body, text=tip_text, bg='white', fg='#6b7280',
                            font=('Microsoft YaHei UI', 9), justify='left')
        tip_label.pack(anchor='w')
        
        # 加载数据
        self.load_disk_info()
    
    def load_system_info(self):
        """加载系统信息"""
        def task():
            info = get_system_info()
            self.root.after(0, lambda: self.update_system_info(info))
        
        threading.Thread(target=task, daemon=True).start()
    
    def update_system_info(self, info):
        """更新系统信息显示"""
        mapping = {
            'os': info.get('OS', '未知'),
            'cpu': info.get('CPU', '未知'),
            'cores': f"{info.get('Cores', '?')} 核 / {info.get('Threads', '?')} 线程",
            'ram': f"{info.get('RAM', '?')} GB",
            'gpu': info.get('GPU', '未知'),
            'model': f"{info.get('Manufacturer', '')} {info.get('Model', '')}".strip() or '未知',
        }
        
        for key, val in mapping.items():
            if key in self.sys_info_labels:
                self.sys_info_labels[key].configure(text=val)
    
    def load_disk_info(self):
        """加载磁盘信息"""
        def task():
            disks = get_disk_info()
            self.root.after(0, lambda: self.update_disk_info(disks))
        
        threading.Thread(target=task, daemon=True).start()
    
    def update_disk_info(self, disks):
        """更新磁盘信息显示"""
        # 找到磁盘卡片的 body
        for card in self.content_frame.winfo_children():
            for child in card.winfo_children():
                if isinstance(child, tk.Frame):
                    for sub in child.winfo_children():
                        if isinstance(sub, tk.Frame) and hasattr(sub, 'winfo_children'):
                            pass
        
        # 重新创建磁盘显示
        # 找到 disk_body - 简化处理：直接在概览页的第二个卡片里更新
        cards = []
        for w in self.content_frame.winfo_children():
            if isinstance(w, tk.Frame) and w.cget('bg') == 'white':
                cards.append(w)
        
        if len(cards) >= 2:
            disk_card = cards[1]
            # 找到 body frame
            for w in disk_card.winfo_children():
                if isinstance(w, tk.Frame) and w not in [disk_card.winfo_children()[0]]:
                    # 清空旧的磁盘显示
                    for child in w.winfo_children():
                        child.destroy()
                    
                    # 创建新的磁盘显示
                    for disk in disks:
                        self.create_disk_bar(w, disk)
                    break
    
    def create_disk_bar(self, parent, disk_info):
        """创建磁盘进度条"""
        drive = disk_info.get('Drive', '?')
        used = disk_info.get('Used', 0)
        free = disk_info.get('Free', 0)
        total = disk_info.get('Total', 0)
        free_percent = disk_info.get('FreePercent', 0)
        used_percent = 100 - free_percent
        
        frame = tk.Frame(parent, bg='white')
        frame.pack(fill=tk.X, pady=8)
        
        # 顶部标签
        top_row = tk.Frame(frame, bg='white')
        top_row.pack(fill=tk.X)
        
        tk.Label(top_row, text=f"💾 {drive}", bg='white', fg='#1f2937',
                 font=('Microsoft YaHei UI', 10, 'bold')).pack(side=tk.LEFT)
        
        status_text = f"已用 {format_size(used)} / 共 {format_size(total)}"
        tk.Label(top_row, text=status_text, bg='white', fg='#6b7280',
                 font=('Microsoft YaHei UI', 9)).pack(side=tk.RIGHT)
        
        # 进度条
        bar_bg = tk.Frame(frame, bg='#e5e7eb', height=12)
        bar_bg.pack(fill=tk.X, pady=(6, 4))
        bar_bg.pack_propagate(False)
        
        # 颜色判断
        if free_percent < 10:
            bar_color = '#ef4444'  # 红色
        elif free_percent < 20:
            bar_color = '#f59e0b'  # 黄色
        else:
            bar_color = '#10b981'  # 绿色
        
        bar_width = max(2, int(used_percent))
        bar = tk.Frame(bar_bg, bg=bar_color, width=0)
        bar.pack(side=tk.LEFT, fill=tk.Y)
        
        # 动画效果
        def animate_bar(widget, target_pct, current=0):
            if current <= target_pct:
                widget.configure(width=int(widget.master.winfo_width() * current / 100))
                self.root.after(20, lambda: animate_bar(widget, target_pct, current + 2))
        
        self.root.after(100, lambda: animate_bar(bar, used_percent))
        
        # 底部信息
        bottom_row = tk.Frame(frame, bg='white')
        bottom_row.pack(fill=tk.X)
        
        free_text = f"剩余 {format_size(free)} ({free_percent}%)"
        free_color = '#ef4444' if free_percent < 10 else ('#f59e0b' if free_percent < 20 else '#10b981')
        tk.Label(bottom_row, text=free_text, bg='white', fg=free_color,
                 font=('Microsoft YaHei UI', 9)).pack(side=tk.LEFT)
    
    # ============================================================
    # 磁盘清理页
    # ============================================================
    
    def show_cleanup(self):
        """显示磁盘清理页"""
        self.clear_content()
        self.scan_results = {}
        self.clean_checkboxes = {}
        
        # 页面标题
        title_frame = tk.Frame(self.content_frame, bg='#f0f2f5')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(title_frame, text="磁盘清理", bg='#f0f2f5', fg='#1f2937',
                 font=('Microsoft YaHei UI', 18, 'bold')).pack(anchor='w')
        tk.Label(title_frame, text="安全清理系统垃圾文件，释放磁盘空间", bg='#f0f2f5', fg='#6b7280',
                 font=('Microsoft YaHei UI', 10)).pack(anchor='w', pady=(2, 0))
        
        # 操作栏
        action_bar = tk.Frame(self.content_frame, bg='#f0f2f5')
        action_bar.pack(fill=tk.X, pady=(0, 10))
        
        self.scan_btn = ttk.Button(action_bar, text="🔍 扫描可清理文件", 
                                   style='Primary.TButton', command=self.start_scan)
        self.scan_btn.pack(side=tk.LEFT)
        
        self.clean_btn = ttk.Button(action_bar, text="🧹 清理选中项目", 
                                    style='Success.TButton', command=self.start_clean, state='disabled')
        self.clean_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        self.select_all_var = tk.BooleanVar(value=True)
        select_all_cb = ttk.Checkbutton(action_bar, text="全选安全项目", 
                                        variable=self.select_all_var,
                                        command=self.toggle_select_all)
        select_all_cb.pack(side=tk.LEFT, padx=(15, 0))
        
        # 预计释放空间
        self.total_freed_label = tk.Label(action_bar, text="预计释放: --", 
                                          bg='#f0f2f5', fg='#10b981',
                                          font=('Microsoft YaHei UI', 10, 'bold'))
        self.total_freed_label.pack(side=tk.RIGHT)
        
        # 清理项目列表卡片
        list_card, list_body = self.create_card(self.content_frame, "清理项目", 
                                                "勾选要清理的项目，点击扫描查看可释放空间")
        
        # 滚动区域
        canvas = tk.Canvas(list_body, bg='white', highlightthickness=0, height=380)
        scrollbar = ttk.Scrollbar(list_body, orient="vertical", command=canvas.yview)
        self.clean_scroll_frame = tk.Frame(canvas, bg='white')
        
        self.clean_scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.clean_scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 创建清理项
        for item in CleanManager.CLEAN_ITEMS:
            self.create_clean_item(self.clean_scroll_frame, item)
        
        # 日志区域
        log_card, log_body = self.create_card(self.content_frame, "操作日志")
        
        self.clean_log = scrolledtext.ScrolledText(log_body, height=8, 
                                                    font=('Consolas', 9),
                                                    bg='#1e293b', fg='#94a3b8',
                                                    insertbackground='white',
                                                    relief='flat')
        self.clean_log.pack(fill=tk.X)
        self.clean_log.insert(tk.END, "就绪。点击「扫描可清理文件」开始扫描...\n")
        self.clean_log.configure(state='disabled')
    
    def create_clean_item(self, parent, item):
        """创建单个清理项"""
        frame = tk.Frame(parent, bg='white', highlightbackground='#e5e7eb', 
                        highlightthickness=1)
        frame.pack(fill=tk.X, pady=4, padx=2)
        
        # 左侧复选框和信息
        left_frame = tk.Frame(frame, bg='white')
        left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12, pady=10)
        
        top_row = tk.Frame(left_frame, bg='white')
        top_row.pack(fill=tk.X)
        
        var = tk.BooleanVar(value=item['safe'])
        self.clean_checkboxes[item['id']] = var
        
        cb = ttk.Checkbutton(top_row, text=item['name'], variable=var,
                            command=self.update_total_freed)
        cb.pack(side=tk.LEFT)
        
        # 风险标签
        risk_colors = {
            'L1': '#10b981',
            'L1-不可逆': '#f59e0b',
            'L2': '#f59e0b',
            'L3': '#ef4444',
        }
        risk_color = risk_colors.get(item['risk'], '#6b7280')
        risk_label = tk.Label(top_row, text=f" {item['risk']} ", bg=risk_color, fg='white',
                             font=('Microsoft YaHei UI', 7, 'bold'))
        risk_label.pack(side=tk.LEFT, padx=(8, 0))
        
        # 大小显示
        size_label = tk.Label(top_row, text="--", bg='white', fg='#10b981',
                             font=('Microsoft YaHei UI', 9, 'bold'))
        size_label.pack(side=tk.RIGHT)
        self.scan_results[item['id']] = {'label': size_label, 'size': 0}
        
        # 描述
        desc_label = tk.Label(left_frame, text=item['desc'], bg='white', fg='#6b7280',
                             font=('Microsoft YaHei UI', 8), wraplength=500, justify='left')
        desc_label.pack(anchor='w', pady=(4, 0))
    
    def toggle_select_all(self):
        """全选/取消全选"""
        selected = self.select_all_var.get()
        for item in CleanManager.CLEAN_ITEMS:
            if item['safe']:  # 只选安全项目
                self.clean_checkboxes[item['id']].set(selected)
        self.update_total_freed()
    
    def update_total_freed(self):
        """更新预计释放空间"""
        total = 0
        for item_id, info in self.scan_results.items():
            if self.clean_checkboxes[item_id].get():
                total += info['size']
        
        if total > 0:
            self.total_freed_label.configure(text=f"预计释放: {format_size(total)}")
        else:
            self.total_freed_label.configure(text="预计释放: --")
    
    def start_scan(self):
        """开始扫描"""
        if self.is_scanning:
            return
        
        self.is_scanning = True
        self.scan_btn.configure(state='disabled', text="扫描中...")
        self.append_clean_log("开始扫描可清理文件...\n")
        
        def scan_task():
            total_size = 0
            for item in CleanManager.CLEAN_ITEMS:
                self.append_clean_log(f"  扫描 {item['name']}...")
                size = CleanManager.scan_item(item['id'])
                self.scan_results[item['id']]['size'] = size
                total_size += size
                
                self.root.after(0, lambda i=item['id'], s=size: self.update_item_size(i, s))
                self.append_clean_log(f" {format_size(size)}\n")
            
            self.append_clean_log(f"\n扫描完成！共发现可清理文件 {format_size(total_size)}\n")
            
            self.root.after(0, lambda: self.scan_btn.configure(state='normal', text="🔍 重新扫描"))
            self.root.after(0, lambda: self.clean_btn.configure(state='normal'))
            self.is_scanning = False
            self.update_total_freed()
        
        threading.Thread(target=scan_task, daemon=True).start()
    
    def update_item_size(self, item_id, size):
        """更新项目大小显示"""
        if item_id in self.scan_results:
            self.scan_results[item_id]['label'].configure(text=format_size(size))
    
    def start_clean(self):
        """开始清理"""
        if self.is_cleaning:
            return
        
        # 检查是否选中了不可逆项目
        has_irreversible = False
        irreversible_items = []
        for item in CleanManager.CLEAN_ITEMS:
            if self.clean_checkboxes[item['id']].get() and item['risk'] == 'L1-不可逆':
                has_irreversible = True
                irreversible_items.append(item['name'])
        
        if has_irreversible:
            msg = f"⚠️  你选中了以下不可逆项目：\n\n"
            msg += "\n".join(f"  • {name}" for name in irreversible_items)
            msg += "\n\n这些项目清理后无法恢复，确定要继续吗？"
            if not messagebox.askyesno("确认清理", msg):
                return
        
        # 统计选中项
        selected = []
        total_size = 0
        for item in CleanManager.CLEAN_ITEMS:
            if self.clean_checkboxes[item['id']].get():
                selected.append(item)
                total_size += self.scan_results[item['id']]['size']
        
        if not selected:
            messagebox.showinfo("提示", "请至少选择一个清理项目")
            return
        
        confirm = messagebox.askyesno("确认清理", 
            f"将清理 {len(selected)} 个项目，预计释放 {format_size(total_size)}\n\n确定开始清理吗？")
        if not confirm:
            return
        
        self.is_cleaning = True
        self.clean_btn.configure(state='disabled', text="清理中...")
        self.scan_btn.configure(state='disabled')
        self.append_clean_log("\n" + "="*50 + "\n")
        self.append_clean_log("开始清理...\n")
        
        def clean_task():
            total_freed = 0
            for item in selected:
                self.append_clean_log(f"  清理 {item['name']}...")
                freed = CleanManager.clean_item(item['id'])
                total_freed += freed
                self.append_clean_log(f" 已释放 {format_size(freed)}\n")
                
                # 更新大小显示
                self.root.after(0, lambda i=item['id']: self.update_item_size(i, 0))
            
            self.append_clean_log(f"\n✅ 清理完成！共释放空间 {format_size(total_freed)}\n")
            self.append_clean_log("刷新磁盘信息中...\n")
            
            self.root.after(0, lambda: self.clean_btn.configure(state='normal', text="🧹 清理选中项目"))
            self.root.after(0, lambda: self.scan_btn.configure(state='normal'))
            self.is_cleaning = False
            self.update_total_freed()
            
            # 刷新磁盘信息
            self.load_disk_info()
        
        threading.Thread(target=clean_task, daemon=True).start()
    
    def append_clean_log(self, text):
        """添加清理日志"""
        def _append():
            self.clean_log.configure(state='normal')
            self.clean_log.insert(tk.END, text)
            self.clean_log.see(tk.END)
            self.clean_log.configure(state='disabled')
        
        if threading.current_thread() is threading.main_thread():
            _append()
        else:
            self.root.after(0, _append)
    
    # ============================================================
    # 游戏优化页
    # ============================================================
    
    def show_game_boost(self):
        """显示游戏优化页"""
        self.clear_content()
        self.optimize_checkboxes = {}
        
        # 页面标题
        title_frame = tk.Frame(self.content_frame, bg='#f0f2f5')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(title_frame, text="游戏优化", bg='#f0f2f5', fg='#1f2937',
                 font=('Microsoft YaHei UI', 18, 'bold')).pack(anchor='w')
        tk.Label(title_frame, text="优化系统设置，提升游戏帧率和稳定性", bg='#f0f2f5', fg='#6b7280',
                 font=('Microsoft YaHei UI', 10)).pack(anchor='w', pady=(2, 0))
        
        # 游戏推荐设置卡片
        game_card, game_body = self.create_card(self.content_frame, 
            "🎮 游戏优化建议", "针对你玩的游戏的特别建议")
        
        game_tips = [
            ('三角洲行动', 
             '• UE 引擎，吃显存和 CPU，战斗掉帧多因粒子+阴影\n'
             '• 建议：开 DLSS 质量档 + NVIDIA Reflex\n'
             '• 16GB 内存建议关闭浏览器再进游戏\n'
             '• 阴影质量、体积雾是帧率杀手，优先调低'),
            ('暗区突围',
             '• 吃内存和硬盘速度，确保游戏安装在 SSD 上\n'
             '• 物理内存充足很重要，8GB 内存会明显卡顿\n'
             '• 关闭后台不必要的程序释放内存'),
            ('我的世界 (带模组)',
             '• Java 版非常吃内存，建议分配 4-8GB 内存\n'
             '• 安装 Sodium/Optifine 等性能模组\n'
             '• 降低视距和实体数量可显著提升帧率\n'
             '• 使用 SSD 加载世界更快'),
        ]
        
        for i, (game, tips) in enumerate(game_tips):
            tip_frame = tk.Frame(game_body, bg='white', highlightbackground='#e5e7eb',
                                highlightthickness=1)
            tip_frame.grid(row=0, column=i, sticky='nsew', padx=5, pady=5)
            game_body.grid_columnconfigure(i, weight=1)
            
            inner = tk.Frame(tip_frame, bg='white')
            inner.pack(padx=12, pady=12, fill=tk.BOTH, expand=True)
            
            tk.Label(inner, text=game, bg='white', fg='#8b5cf6',
                     font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w')
            tk.Label(inner, text=tips, bg='white', fg='#6b7280',
                     font=('Microsoft YaHei UI', 8), justify='left',
                     wraplength=200).pack(anchor='w', pady=(6, 0))
        
        # 系统优化项卡片
        opt_card, opt_body = self.create_card(self.content_frame, 
            "⚡ 系统级优化", "修改系统设置提升游戏性能（均可撤销）")
        
        # 操作按钮
        opt_action = tk.Frame(opt_card, bg='white')
        opt_action.pack(fill=tk.X, padx=16, pady=(0, 10))
        
        self.apply_opt_btn = ttk.Button(opt_action, text="🚀 应用选中的优化",
                                        style='Primary.TButton', command=self.apply_optimizations)
        self.apply_opt_btn.pack(side=tk.LEFT)
        
        self.revert_opt_btn = ttk.Button(opt_action, text="↩️ 撤销优化",
                                         command=self.revert_optimizations)
        self.revert_opt_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # 优化项列表
        for item in GameOptimizer.OPTIMIZE_ITEMS:
            self.create_optimize_item(opt_body, item)
        
        # 后台进程优化卡片
        bg_card, bg_body = self.create_card(self.content_frame,
            "📌 后台进程优化", "游戏前关闭不必要的后台程序释放资源")
        
        bg_tips = ("游戏前建议关闭：\n"
                  "  • 浏览器（Chrome/Edge 多标签页占用大量内存）\n"
                  "  • 网盘同步客户端（百度网盘、OneDrive 等）\n"
                  "  • 直播/录屏软件\n"
                  "  • 各种软件管家、加速球类工具（本身就占资源）\n\n"
                  "💡 提示：不要关闭杀毒软件的实时防护，可以在杀毒软件中\n"
                  "     设置游戏免打扰模式或为游戏添加白名单")
        
        tk.Label(bg_body, text=bg_tips, bg='white', fg='#6b7280',
                font=('Microsoft YaHei UI', 9), justify='left').pack(anchor='w')
        
        # 重要提示
        warn_card = tk.Frame(self.content_frame, bg='#fef3c7', 
                            highlightbackground='#f59e0b', highlightthickness=1)
        warn_card.pack(fill=tk.X, pady=10)
        
        warn_inner = tk.Frame(warn_card, bg='#fef3c7')
        warn_inner.pack(padx=15, pady=12)
        
        warn_text = ("⚠️  重要提示\n"
                    "• 软件优化通常带来 5-15% 的帧率改善，不会让 60 帧变成 144 帧\n"
                    "• 帧率上限由硬件决定，如果显卡或 CPU 是瓶颈，优化效果有限\n"
                    "• HAGS 等设置修改后需要重启电脑才能生效\n"
                    "• 笔记本电脑请确保插电使用，并设置为高性能模式")
        
        tk.Label(warn_inner, text=warn_text, bg='#fef3c7', fg='#92400e',
                font=('Microsoft YaHei UI', 9), justify='left').pack(anchor='w')
        
        # 加载优化项状态
        self.load_optimize_status()
    
    def create_optimize_item(self, parent, item):
        """创建单个优化项"""
        frame = tk.Frame(parent, bg='white', highlightbackground='#e5e7eb',
                        highlightthickness=1)
        frame.pack(fill=tk.X, pady=4)
        
        left_frame = tk.Frame(frame, bg='white')
        left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12, pady=10)
        
        top_row = tk.Frame(left_frame, bg='white')
        top_row.pack(fill=tk.X)
        
        var = tk.BooleanVar(value=True)
        self.optimize_checkboxes[item['id']] = {'var': var, 'item': item}
        
        cb = ttk.Checkbutton(top_row, text=item['name'], variable=var)
        cb.pack(side=tk.LEFT)
        
        # 状态标签
        status_label = tk.Label(top_row, text="检测中...", bg='white', fg='#6b7280',
                               font=('Microsoft YaHei UI', 9))
        status_label.pack(side=tk.RIGHT)
        self.optimize_checkboxes[item['id']]['status_label'] = status_label
        
        # 描述
        desc = tk.Label(left_frame, text=item['desc'], bg='white', fg='#6b7280',
                       font=('Microsoft YaHei UI', 8), wraplength=600, justify='left')
        desc.pack(anchor='w', pady=(4, 0))
    
    def load_optimize_status(self):
        """加载优化项状态"""
        def task():
            for item in GameOptimizer.OPTIMIZE_ITEMS:
                status = GameOptimizer.check_item(item['id'])
                self.root.after(0, lambda i=item['id'], s=status: self.update_optimize_status(i, s))
        
        threading.Thread(target=task, daemon=True).start()
    
    def update_optimize_status(self, item_id, status):
        """更新优化项状态"""
        if item_id in self.optimize_checkboxes:
            label = self.optimize_checkboxes[item_id]['status_label']
            if status.get('Enabled', False):
                label.configure(text="✓ 已开启", fg='#10b981')
            elif status.get('Supported', True) == False:
                label.configure(text="✗ 不支持", fg='#ef4444')
            else:
                label.configure(text="○ 未优化", fg='#f59e0b')
    
    def apply_optimizations(self):
        """应用优化"""
        selected = []
        for item_id, info in self.optimize_checkboxes.items():
            if info['var'].get():
                selected.append(info['item'])
        
        if not selected:
            messagebox.showinfo("提示", "请至少选择一个优化项目")
            return
        
        confirm = messagebox.askyesno("确认优化",
            f"将应用 {len(selected)} 项优化设置。\n\n"
            "所有优化均可撤销，确定继续吗？")
        if not confirm:
            return
        
        self.apply_opt_btn.configure(state='disabled', text="应用中...")
        
        def task():
            results = []
            need_reboot = False
            for item in selected:
                result = GameOptimizer.apply_item(item['id'])
                results.append((item['name'], result))
                if result.get('NeedReboot', False):
                    need_reboot = True
            
            msg = f"✅ 已应用 {len(results)} 项优化：\n\n"
            for name, _ in results:
                msg += f"  ✓ {name}\n"
            
            if need_reboot:
                msg += "\n⚠️  部分设置需要重启电脑才能生效"
            
            self.root.after(0, lambda: messagebox.showinfo("优化完成", msg))
            self.root.after(0, lambda: self.apply_opt_btn.configure(state='normal', text="🚀 应用选中的优化"))
            self.root.after(0, self.load_optimize_status)
        
        threading.Thread(target=task, daemon=True).start()
    
    def revert_optimizations(self):
        """撤销优化"""
        messagebox.showinfo("提示", 
            "撤销功能说明：\n\n"
            "• 电源计划：在控制面板→电源选项中改回原来的计划\n"
            "• 游戏模式：在设置→游戏→游戏模式中关闭\n"
            "• Game DVR：在设置→游戏→Xbox Game Bar 中开启\n"
            "• HAGS：在设置→系统→显示→图形设置中关闭\n\n"
            "所有优化都是系统标准设置，可以随时在系统设置中改回。")
    
    # ============================================================
    # 系统优化页
    # ============================================================
    
    def show_system_tuning(self):
        """显示系统优化页"""
        self.clear_content()
        
        # 页面标题
        title_frame = tk.Frame(self.content_frame, bg='#f0f2f5')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(title_frame, text="系统优化", bg='#f0f2f5', fg='#1f2937',
                 font=('Microsoft YaHei UI', 18, 'bold')).pack(anchor='w')
        tk.Label(title_frame, text="管理启动项和系统设置，让电脑更流畅", bg='#f0f2f5', fg='#6b7280',
                 font=('Microsoft YaHei UI', 10)).pack(anchor='w', pady=(2, 0))
        
        # 启动项管理卡片
        startup_card, startup_body = self.create_card(self.content_frame,
            "🚀 启动项管理", "管理开机自启动程序，加快开机速度")
        
        startup_tip = ("启动项太多会拖慢开机速度。建议禁用不需要开机自启的程序。\n\n"
                      "💡 操作方法：\n"
                      "  1. 按 Ctrl + Shift + Esc 打开任务管理器\n"
                      "  2. 切换到「启动应用」选项卡\n"
                      "  3. 右键不需要的程序，选择「禁用」\n\n"
                      "✅ 建议保留：杀毒软件、输入法、云同步（你常用的）\n"
                      "❌ 建议禁用：视频/音乐/购物类App、各种管家助手、游戏平台、更新器")
        
        tk.Label(startup_body, text=startup_tip, bg='white', fg='#6b7280',
                font=('Microsoft YaHei UI', 9), justify='left').pack(anchor='w')
        
        # 内存优化卡片
        memory_card, memory_body = self.create_card(self.content_frame,
            "💾 内存优化", "释放内存，让电脑更流畅")
        
        memory_tips = [
            ('关闭不用的程序', '关闭浏览器中不用的标签页、不用的软件，是释放内存最有效的方法'),
            ('重启电脑', '电脑用久了内存泄漏会越来越多，重启一下能释放全部内存'),
            ('加内存条', '8GB 内存现在已经不够用了，升级到 16GB 是最明显的提升'),
        ]
        
        for title, desc in memory_tips:
            tip_frame = tk.Frame(memory_body, bg='white')
            tip_frame.pack(fill=tk.X, pady=6)
            
            tk.Label(tip_frame, text=f"  • {title}", bg='white', fg='#1f2937',
                     font=('Microsoft YaHei UI', 9, 'bold')).pack(anchor='w')
            tk.Label(tip_frame, text=f"    {desc}", bg='white', fg='#6b7280',
                     font=('Microsoft YaHei UI', 8)).pack(anchor='w', pady=(2, 0))
        
        # 系统加速建议
        speed_card, speed_body = self.create_card(self.content_frame,
            "⚡ 系统加速建议", "按效果从大到小排序")
        
        speed_items = [
            ('1', 'C盘保持充足空间', 'C盘剩余空间小于 10% 会显著变慢，先清理磁盘'),
            ('2', '减少开机自启动', '禁用不必要的启动项，加快开机速度'),
            ('3', '关闭不用的后台程序', '尤其是浏览器多标签页，很占内存'),
            ('4', '机械硬盘换固态硬盘', 'HDD 换 SSD 是老电脑最大的性能提升'),
            ('5', '增加内存', '8GB 升 16GB，多任务和游戏体验明显改善'),
            ('6', '笔记本清灰换硅脂', '散热不好会导致 CPU 降频，性能大打折扣'),
        ]
        
        for rank, title, desc in speed_items:
            item_frame = tk.Frame(speed_body, bg='white')
            item_frame.pack(fill=tk.X, pady=5)
            
            rank_label = tk.Label(item_frame, text=rank, bg='#2563eb', fg='white',
                                 font=('Microsoft YaHei UI', 9, 'bold'), width=2)
            rank_label.pack(side=tk.LEFT)
            
            text_frame = tk.Frame(item_frame, bg='white')
            text_frame.pack(side=tk.LEFT, padx=(10, 0))
            
            tk.Label(text_frame, text=title, bg='white', fg='#1f2937',
                     font=('Microsoft YaHei UI', 9, 'bold')).pack(anchor='w')
            tk.Label(text_frame, text=desc, bg='white', fg='#6b7280',
                     font=('Microsoft YaHei UI', 8)).pack(anchor='w', pady=(1, 0))
    
    # ============================================================
    # 实用工具页
    # ============================================================
    
    def show_tools(self):
        """显示实用工具页"""
        self.clear_content()
        
        # 页面标题
        title_frame = tk.Frame(self.content_frame, bg='#f0f2f5')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(title_frame, text="实用工具", bg='#f0f2f5', fg='#1f2937',
                 font=('Microsoft YaHei UI', 18, 'bold')).pack(anchor='w')
        tk.Label(title_frame, text="更多实用的系统工具", bg='#f0f2f5', fg='#6b7280',
                 font=('Microsoft YaHei UI', 10)).pack(anchor='w', pady=(2, 0))
        
        # 大文件扫描卡片
        bigfile_card, bigfile_body = self.create_card(self.content_frame,
            "📁 大文件扫描", "找出占用磁盘空间最多的大文件")
        
        tk.Label(bigfile_body, text="扫描你的电脑，找出占用空间最大的文件，\n"
               "帮助你决定哪些可以删除或转移到其他盘。", 
               bg='white', fg='#6b7280', font=('Microsoft YaHei UI', 9),
               justify='left').pack(anchor='w')
        
        scan_frame = tk.Frame(bigfile_body, bg='white')
        scan_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.bigfile_drive_var = tk.StringVar(value='C:')
        drive_combo = ttk.Combobox(scan_frame, textvariable=self.bigfile_drive_var,
                                   values=['C:', 'D:', 'E:', 'F:'], width=10, state='readonly')
        drive_combo.pack(side=tk.LEFT)
        
        self.bigfile_btn = ttk.Button(scan_frame, text="🔍 扫描大文件",
                                      style='Primary.TButton', command=self.scan_big_files)
        self.bigfile_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # 大文件结果显示
        self.bigfile_result_frame = tk.Frame(bigfile_body, bg='white')
        self.bigfile_result_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 系统工具快捷方式卡片
        tools_card, tools_body = self.create_card(self.content_frame,
            "🔧 系统工具快捷方式", "快速打开 Windows 自带的系统工具")
        
        tools_list = [
            ('磁盘清理', 'cleanmgr', 'Windows 自带的磁盘清理工具'),
            ('任务管理器', 'taskmgr', '查看进程、性能、启动项'),
            ('程序和功能', 'appwiz.cpl', '卸载已安装的程序'),
            ('系统配置', 'msconfig', '系统启动和服务配置'),
            ('电源选项', 'powercfg.cpl', '设置电源计划'),
            ('设备管理器', 'devmgmt.msc', '管理硬件设备和驱动'),
            ('磁盘管理', 'diskmgmt.msc', '管理磁盘分区'),
            ('事件查看器', 'eventvwr', '查看系统日志'),
        ]
        
        for i, (name, cmd, desc) in enumerate(tools_list):
            row = i // 2
            col = i % 2
            
            tool_frame = tk.Frame(tools_body, bg='white', highlightbackground='#e5e7eb',
                                 highlightthickness=1, cursor='hand2')
            tool_frame.grid(row=row, column=col, sticky='nsew', padx=5, pady=5)
            tools_body.grid_columnconfigure(col, weight=1)
            
            tool_frame.bind('<Button-1>', lambda e, c=cmd: self.run_system_tool(c))
            
            inner = tk.Frame(tool_frame, bg='white')
            inner.pack(padx=12, pady=10, fill=tk.X)
            
            tk.Label(inner, text=name, bg='white', fg='#2563eb',
                     font=('Microsoft YaHei UI', 10, 'bold')).pack(anchor='w')
            tk.Label(inner, text=desc, bg='white', fg='#6b7280',
                     font=('Microsoft YaHei UI', 8)).pack(anchor='w', pady=(2, 0))
        
        # 关于卡片
        about_card, about_body = self.create_card(self.content_frame, "ℹ️ 关于本程序")
        
        about_text = ("PC 优化大师 v1.0\n\n"
                     "一个安全、免费的电脑清理和优化工具。\n\n"
                     "✅ 只清理安全的、可恢复的缓存文件\n"
                     "✅ 不会删除你的个人文件和文档\n"
                     "✅ 所有系统优化均可撤销\n"
                     "✅ 开源透明，无广告、无捆绑\n\n"
                     "⚠️ 本程序仅供学习交流使用，请自行评估风险")
        
        tk.Label(about_body, text=about_text, bg='white', fg='#6b7280',
                font=('Microsoft YaHei UI', 9), justify='left').pack(anchor='w')
    
    def scan_big_files(self):
        """扫描大文件"""
        drive = self.bigfile_drive_var.get()
        
        self.bigfile_btn.configure(state='disabled', text="扫描中...")
        
        # 清空旧结果
        for w in self.bigfile_result_frame.winfo_children():
            w.destroy()
        
        tk.Label(self.bigfile_result_frame, text="正在扫描，请稍候...", 
                bg='white', fg='#6b7280', font=('Microsoft YaHei UI', 9)).pack()
        
        def task():
            cmd = f"""
            Get-ChildItem {drive}\\ -Recurse -Force -ErrorAction SilentlyContinue -File |
                Sort-Object Length -Descending |
                Select-Object -First 20 FullName, Length, LastWriteTime |
                ForEach-Object {{
                    [PSCustomObject]@{{
                        Name = $_.Name
                        Path = $_.FullName
                        Size = $_.Length
                        SizeStr = "{{0:N1}} MB" -f ($_.Length / 1MB)
                        Date = $_.LastWriteTime.ToString("yyyy-MM-dd")
                    }}
                }} | ConvertTo-Json
            """
            stdout, stderr, rc = run_powershell(cmd, timeout=120)
            
            try:
                files = json.loads(stdout)
                if not isinstance(files, list):
                    files = [files]
            except:
                files = []
            
            self.root.after(0, lambda: self.show_big_files(files))
        
        threading.Thread(target=task, daemon=True).start()
    
    def show_big_files(self, files):
        """显示大文件扫描结果"""
        # 清空
        for w in self.bigfile_result_frame.winfo_children():
            w.destroy()
        
        self.bigfile_btn.configure(state='normal', text="🔍 扫描大文件")
        
        if not files:
            tk.Label(self.bigfile_result_frame, text="未找到大文件或扫描失败", 
                    bg='white', fg='#ef4444', font=('Microsoft YaHei UI', 9)).pack()
            return
        
        # 创建表格
        header_frame = tk.Frame(self.bigfile_result_frame, bg='#f3f4f6')
        header_frame.pack(fill=tk.X)
        
        tk.Label(header_frame, text="文件名", bg='#f3f4f6', fg='#374151',
                 font=('Microsoft YaHei UI', 9, 'bold'), width=30, anchor='w').pack(side=tk.LEFT, padx=8, pady=6)
        tk.Label(header_frame, text="大小", bg='#f3f4f6', fg='#374151',
                 font=('Microsoft YaHei UI', 9, 'bold'), width=12, anchor='e').pack(side=tk.RIGHT, padx=8, pady=6)
        tk.Label(header_frame, text="修改日期", bg='#f3f4f6', fg='#374151',
                 font=('Microsoft YaHei UI', 9, 'bold'), width=12, anchor='e').pack(side=tk.RIGHT, padx=8, pady=6)
        
        for i, f in enumerate(files):
            bg_color = 'white' if i % 2 == 0 else '#f9fafb'
            row_frame = tk.Frame(self.bigfile_result_frame, bg=bg_color)
            row_frame.pack(fill=tk.X)
            
            name = f.get('Name', '未知')
            if len(name) > 35:
                name = name[:32] + '...'
            
            tk.Label(row_frame, text=name, bg=bg_color, fg='#1f2937',
                     font=('Microsoft YaHei UI', 8), anchor='w').pack(side=tk.LEFT, padx=8, pady=4)
            
            size_str = f.get('SizeStr', '未知')
            tk.Label(row_frame, text=size_str, bg=bg_color, fg='#ef4444',
                     font=('Microsoft YaHei UI', 8, 'bold'), anchor='e').pack(side=tk.RIGHT, padx=8, pady=4)
            
            date = f.get('Date', '')
            tk.Label(row_frame, text=date, bg=bg_color, fg='#6b7280',
                     font=('Microsoft YaHei UI', 8), anchor='e').pack(side=tk.RIGHT, padx=20, pady=4)
        
        tip = tk.Label(self.bigfile_result_frame, 
                      text="\n💡 提示：这些文件需要你手动判断是否删除，程序不会自动删除任何文件",
                      bg='white', fg='#f59e0b', font=('Microsoft YaHei UI', 8))
        tip.pack(pady=(8, 0))
    
    def run_system_tool(self, cmd):
        """运行系统工具"""
        try:
            subprocess.Popen(cmd, shell=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开：{e}")


# ============================================================
# 程序入口
# ============================================================

def main():
    # 检查是否为 Windows
    if os.name != 'nt':
        print("本程序仅支持 Windows 系统")
        sys.exit(1)
    
    root = tk.Tk()
    app = PCOptimizerApp(root)
    
    # 居中显示
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'+{x}+{y}')
    
    root.mainloop()

if __name__ == '__main__':
    main()
