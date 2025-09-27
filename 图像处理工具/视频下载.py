# cd 图像处理工具
# python 视频下载.py

import subprocess
import os
import sys
from datetime import datetime
import glob

# 颜色常量定义
class Colors:
    """ANSI颜色代码"""
    RESET = "\033[0m"
    RED = "\033[91m"      # 错误 
    GREEN = "\033[92m"    # 成功
    YELLOW = "\033[93m"   # 警告
    BLUE = "\033[94m"     # 信息
    PURPLE = "\033[95m"   # 提示
    CYAN = "\033[96m"     # 用户输入
    GRAY = "\033[90m"     # 下载输出

def print_colored(text, color=Colors.RESET):
    """打印带颜色的文本"""
    print(f"{color}{text}{Colors.RESET}")

def is_valid_date(date_str):
    """
    验证日期字符串是否有效
    
    Args:
        date_str: 日期字符串 (YYYYMMDD格式)
    
    Returns:
        bool: 日期是否有效
    """
    if not date_str or date_str == '未知' or len(date_str) != 8:
        return False
    
    try:
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])
        
        # 检查日期是否在合理范围内
        if 1900 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
            return True
        return False
    except ValueError:
        return False

def get_filename_template(video_info, current_time):
    """
    根据视频元数据智能生成文件名模板
    
    Args:
        video_info: 视频信息字典
        current_time: 当前系统时间字符串
    
    Returns:
        str: 文件名模板
    """
    # 检查是否有有效的上传日期
    upload_date = video_info.get('upload_date')
    if is_valid_date(upload_date):
        # 使用上传日期，但需要检查是否有完整的时间信息
        upload_time = video_info.get('upload_time')
        if upload_time and upload_time != '未知':
            # 有完整的时间信息，使用元数据
            filename_template = f"{upload_date}_{upload_time}"
            print_colored(f"✅ 使用视频元数据: {upload_date}_{upload_time}", Colors.GREEN)
            return filename_template
        else:
            # 只有日期没有时间，使用日期+系统时间
            filename_template = f"{upload_date}_{current_time.split('_')[1]}"
            print_colored(f"✅ 使用视频日期+系统时间: {filename_template}", Colors.GREEN)
            return filename_template
    else:
        print_colored(f"⚠️  无有效上传日期，使用系统时间: {current_time}", Colors.YELLOW)
        return current_time

def get_video_info(url):
    """
    获取视频信息
    
    Args:
        url: 视频链接
    
    Returns:
        dict: 视频信息字典，失败时返回None
    """
    print_colored("🔍 正在获取视频信息...", Colors.BLUE)
    info_command = f'yt-dlp --dump-json "{url}"'
    
    try:
        info_result = subprocess.run(info_command, shell=True, capture_output=True, text=True, timeout=30)
        if info_result.returncode == 0:
            import json
            try:
                video_info = json.loads(info_result.stdout)
                print_colored(f"📹 视频标题: {video_info.get('title', '未知')}", Colors.BLUE)
                print_colored(f"📅 上传日期: {video_info.get('upload_date', '未知')}", Colors.BLUE)
                return video_info
            except Exception as e:
                print_colored(f"⚠️  解析视频信息失败: {e}", Colors.YELLOW)
                return None
        else:
            print_colored("⚠️  无法获取视频信息", Colors.YELLOW)
            return None
    except Exception as e:
        print_colored(f"⚠️  获取视频信息失败: {e}", Colors.YELLOW)
        return None

def download_video(url):
    """下载视频到指定目录"""
    try:
        url = url.strip().strip('"').strip("'")
        
        if not url:
            print_colored("❌ 错误：请提供有效的视频链接", Colors.RED)
            return False
            
        save_dir = r"D:\Users\Windows10\Desktop\0V0_燕小重的知识库\视频\未分类"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            print_colored(f"📁 创建目录: {save_dir}", Colors.BLUE)
        
        print_colored("🚀 开始下载!", Colors.GREEN)
        
        # 获取当前系统时间作为默认文件名
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_template = current_time
        
        # 尝试获取视频信息
        video_info = get_video_info(url)
        if video_info:
            # 根据元数据智能生成文件名模板
            filename_template = get_filename_template(video_info, current_time)
        else:
            print_colored(f"⚠️  使用系统时间: {current_time}", Colors.YELLOW)
        
        # 构建下载命令
        command = f'yt-dlp -P "{save_dir}" -o "{filename_template}.%(ext)s" "{url}"'
        
        # 使用实时输出，保留命令行原始输出
        process = subprocess.Popen(
            command, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # 实时读取并显示输出，使用灰色字体
        for line in process.stdout:
            print_colored(line.rstrip(), Colors.GRAY)
        
        # 等待进程完成
        process.wait()
        
        if process.returncode == 0:
            # 清理以 filename_template 为前缀的常见临时文件（不假设固定扩展名）
            temp_patterns = [
                f"{filename_template}*.part",
                f"{filename_template}*.part*",
                f"{filename_template}*.ytdl",
                f"{filename_template}*.ytdl*",
                f"{filename_template}*.aria2",
                f"{filename_template}*.aria2*",
                f"{filename_template}*.temp",
                f"{filename_template}*.tmp",
            ]
            removed_any = False
            for pattern in temp_patterns:
                for temp_path in glob.glob(os.path.join(save_dir, pattern)):
                    # 仅删除带有明显临时标记的文件，避免误删最终成品
                    if any(suffix in temp_path for suffix in ('.part', '.ytdl', '.aria2', '.temp', '.tmp')):
                        try:
                            os.remove(temp_path)
                            removed_any = True
                        except Exception:
                            pass
            if removed_any:
                print_colored("🧹 已清理临时文件", Colors.GREEN)
            print_colored("✅ 下载完成！", Colors.GREEN)
            print_colored("-" * 20, Colors.GRAY)
            return True
        else:
            print_colored(f"❌ 下载失败，返回码: {process.returncode}", Colors.RED)
            print_colored("-" * 20, Colors.GRAY)
            return False
            
    except Exception as e:
        print_colored(f"❌ 下载出错: {str(e)}", Colors.RED)
        print_colored("-" * 20, Colors.GRAY)
        return False

def main():
    """主函数"""
    print_colored("=" * 50, Colors.PURPLE)
    print_colored("🎬 视频下载工具", Colors.PURPLE)
    print_colored("使用方法:", Colors.PURPLE)
    print_colored("1. 直接输入视频链接", Colors.PURPLE)
    print_colored("2. 输入 'quit' 或 'exit' 退出程序", Colors.PURPLE)
    print_colored("=" * 50, Colors.PURPLE)
    
    while True:
        try:
            # 获取用户输入
            url = input(f"{Colors.CYAN}-> 请输入视频链接: {Colors.RESET}").strip()
            
            # 检查退出命令
            if url.lower() in ['quit', 'exit', 'q', '退出']:
                print_colored("-" * 20, Colors.GRAY)
                print_colored("👋 再见！", Colors.GREEN)
                break
            
            # 如果输入为空，继续下一轮
            if not url:
                print_colored("⚠️  请输入有效的视频链接", Colors.YELLOW)
                print_colored("-" * 20, Colors.GRAY)
                continue
            
            # 下载视频
            download_video(url)
                
        except KeyboardInterrupt:
            print_colored("-" * 20, Colors.GRAY)
            print_colored("\n👋 程序被中断，再见！", Colors.GREEN)
            break
        except EOFError:
            print_colored("-" * 20, Colors.GRAY)
            print_colored("👋 再见！", Colors.GREEN)
            break

if __name__ == "__main__":
    main()