import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# ========== 配置 ==========

DEVICE_SERIAL = "3030725483000E2"

PHONE_SOURCES = [
    "/sdcard/DCIM",
    "/sdcard/Pictures", 
    "/sdcard/Movies",
]

PC_SOURCES = [
    Path(r"E:\edge下载文件\iCloud 照片"),
]

TARGET = Path(r"D:\Users\Windows10\Desktop\0V0_燕小重的知识库\图库\未分类")

EXTENSIONS = {
    '.avif', '.gif', '.heif', '.jpeg', '.jpg', 
    '.mp4', '.null', '.png', '.psd', '.raw', 
    '.svg', '.tiff', '.webp'
}

TEMP_DIR = Path(tempfile.gettempdir()) / "phone_media_temp"

DELETE_SOURCE = True

# ========== ADB 函数 ==========

def adb_shell(cmd):
    """执行 adb shell 命令"""
    full_cmd = ["adb", "-s", DEVICE_SERIAL, "shell"] + cmd
    result = subprocess.run(full_cmd, capture_output=True, text=True, encoding='utf-8')
    return result

def adb_pull(remote, local):
    """执行 adb pull"""
    cmd = ["adb", "-s", DEVICE_SERIAL, "pull", remote, str(local)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    return result

# ========== 主程序 ==========

def main():
    print("=" * 60)
    print(f"📦 手机媒体文件迁移 ({'剪切' if DELETE_SOURCE else '复制'}模式)")
    print("=" * 60)
    
    # 验证设备
    devices = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    print("🔍 已连接设备:")
    print(devices.stdout)
    
    if DEVICE_SERIAL not in devices.stdout:
        print(f"❌ 设备 {DEVICE_SERIAL} 未找到")
        return
    
    print(f"✅ 使用设备: {DEVICE_SERIAL}")
    
    all_temp_folders = []
    
    # 处理手机源
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    for phone_path in PHONE_SOURCES:
        print(f"\n📂 扫描: {phone_path}")
        
        # 检查路径存在
        check = adb_shell(["ls", "-d", phone_path])
        if check.returncode != 0:
            print(f"   ❌ 路径不存在或无法访问")
            continue
        
        # 获取文件列表
        result = adb_shell(["find", phone_path, "-type", "f"])
        files = [l.strip() for l in result.stdout.split('\n') if l.strip()]
        print(f"   找到 {len(files)} 个文件")
        
        # 过滤匹配后缀的文件
        matched = [f for f in files if Path(f).suffix.lower() in EXTENSIONS]
        print(f"   匹配后缀: {len(matched)} 个")
        
        if not matched:
            continue
        
        # 创建临时子目录
        temp_sub = TEMP_DIR / phone_path.strip('/').replace('/', '_')
        temp_sub.mkdir(parents=True, exist_ok=True)
        
        for f in matched:
            filename = Path(f).name
            
            # 处理重名
            local_file = temp_sub / filename
            counter = 1
            while local_file.exists():
                stem = Path(filename).stem
                suffix = Path(filename).suffix
                local_file = temp_sub / f"{stem}_{counter:03d}{suffix}"
                counter += 1
            
            # pull
            pull_result = adb_pull(f, local_file)
            if pull_result.returncode != 0:
                print(f"   ❌ pull 失败: {filename}")
                continue
            
            # 验证并删除
            deleted = False
            if DELETE_SOURCE:
                size_result = adb_shell(["stat", "-c%s", f])
                phone_size = int(size_result.stdout.strip()) if size_result.returncode == 0 else None
                local_size = local_file.stat().st_size if local_file.exists() else 0
                
                if phone_size and local_size == phone_size:
                    adb_shell(["rm", f])
                    deleted = True
            
            status = "✂️ " if deleted else "📋 "
            name_display = filename if local_file.name == filename else f"{filename}->{local_file.name}"
            print(f"   {status}{name_display}")
        
        if any(temp_sub.iterdir()):
            all_temp_folders.append(temp_sub)
    
    # 添加电脑源
    all_temp_folders.extend(PC_SOURCES)
    
    # 扁平化移动到目标
    TARGET.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 扁平化移动到: {TARGET}")
    
    moved = 0
    errors = 0
    
    for source in all_temp_folders:
        print(f"\n   📂 处理: {source}")
        if not source.exists():
            print(f"   ⚠️ 不存在")
            continue
        
        for file_path in source.rglob("*"):
            if not file_path.is_file():
                continue
            
            if file_path.suffix.lower() not in EXTENSIONS:
                continue
            
            # 目标路径（处理重名）
            dest = TARGET / file_path.name
            counter = 1
            while dest.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                dest = TARGET / f"{stem}_{counter:03d}{suffix}"
                counter += 1
            
            try:
                shutil.move(str(file_path), str(dest))
                print(f"   ✅ {file_path.name}" + (f"->{dest.name}" if dest.name != file_path.name else ""))
                moved += 1
            except Exception as e:
                print(f"   ❌ {file_path.name}: {e}")
                errors += 1
    
    # 清理
    if TEMP_DIR.exists():
        print(f"\n🧹 清理临时文件...")
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    
    # 统计
    print("\n" + "=" * 60)
    print("📊 处理完成")
    print(f"   成功: {moved} 个文件")
    print(f"   失败: {errors} 个文件")
    print(f"   目标: {TARGET}")
    print("=" * 60)
    
    if moved > 0:
        print(f"\n💡 按 Enter 打开目标文件夹...")
        input()
        os.startfile(str(TARGET))

if __name__ == "__main__":
    main()