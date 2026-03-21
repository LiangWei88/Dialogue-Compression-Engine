import os
import sys
import subprocess
import pysrt
import argparse
from datetime import timedelta

def get_video_duration(video_path):
    """使用 ffprobe 获取视频总时长（秒）"""
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', video_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"错误: 无法获取视频时长 {video_path}: {e}")
        return None

def srt_to_seconds(srt_time):
    """将 pysrt 时间对象转换为秒数"""
    return srt_time.hours * 3600 + srt_time.minutes * 60 + srt_time.seconds + srt_time.milliseconds / 1000.0

def seconds_to_srt_time(seconds):
    """将秒数转换为 pysrt 时间对象"""
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.total_seconds(), 3600)
    minutes, remainder = divmod(remainder, 60)
    seconds = int(remainder)
    milliseconds = int((remainder - seconds) * 1000)
    return pysrt.SubRipTime(hours=int(hours), minutes=int(minutes), seconds=seconds, milliseconds=milliseconds)

def extract_dialogue_segments(srt_path, video_duration, padding, merge_gap, min_duration):
    """
    根据字幕提取并合并对白片段
    返回列表: [(start, end), ...]
    """
    subs = pysrt.open(srt_path)
    raw_segments = []

    for sub in subs:
        start = srt_to_seconds(sub.start)
        end = srt_to_seconds(sub.end)
        duration = end - start

        # 过滤空字幕或过短片段
        if not sub.text.strip() or duration < min_duration:
            continue
        
        # 应用 Padding 并限制在视频时长内
        start = max(0, start - padding)
        end = min(video_duration, end + padding)
        raw_segments.append([start, end])

    if not raw_segments:
        return []

    # 按开始时间排序
    raw_segments.sort(key=lambda x: x[0])

    # 合并重叠或间隔极短的片段 (merge_gap)
    merged = []
    if raw_segments:
        curr_start, curr_end = raw_segments[0]
        for i in range(1, len(raw_segments)):
            next_start, next_end = raw_segments[i]
            # 如果两个片段重叠，或者间隔小于 merge_gap，则合并
            if next_start <= curr_end + merge_gap:
                curr_end = max(curr_end, next_end)
            else:
                merged.append((curr_start, curr_end))
                curr_start, curr_end = next_start, next_end
        merged.append((curr_start, curr_end))

    return merged

def process_video_and_srt(args):
    video_path = args.input
    srt_path = args.srt
    output_video = args.output
    output_srt = args.output_srt
    
    # 自动查找字幕文件
    if not srt_path:
        base_name = os.path.splitext(video_path)[0]
        possible_srt = base_name + ".srt"
        if os.path.exists(possible_srt):
            srt_path = possible_srt
            print(f"检测到同名字幕文件: {srt_path}")
        else:
            print(f"错误: 未提供字幕文件，且未找到同名 .srt 文件 ({possible_srt})")
            return

    video_duration = get_video_duration(video_path)
    if video_duration is None:
        return

    segments = extract_dialogue_segments(srt_path, video_duration, args.padding, args.merge_gap, args.min_duration)
    if not segments:
        print("未找到有效的对白片段。")
        return

    print(f"共提取到 {len(segments)} 个有效片段。")
    for i, (s, e) in enumerate(segments):
        print(f"  片段 {i+1}: {s:.2f}s -> {e:.2f}s (时长: {e-s:.2f}s)")

    # 1. 生成新字幕文件
    subs = pysrt.open(srt_path)
    new_subs = pysrt.SubRipFile()
    
    # 预计算每个片段在新视频中的开始时间 (cumulative_offset)
    segment_offsets = []
    current_offset = 0.0
    for start, end in segments:
        segment_offsets.append(current_offset)
        current_offset += (end - start)

    # 重映射字幕时间轴
    for sub in subs:
        sub_start = srt_to_seconds(sub.start)
        sub_end = srt_to_seconds(sub.end)
        
        # 过滤空字幕或过短片段 (需与提取逻辑一致)
        if not sub.text.strip() or (sub_end - sub_start) < args.min_duration:
            continue
            
        # 查找该字幕落在哪个片段内（可能跨越，按要求裁剪）
        for i, (seg_start, seg_end) in enumerate(segments):
            # 检查是否有重叠部分
            overlap_start = max(sub_start, seg_start)
            overlap_end = min(sub_end, seg_end)
            
            if overlap_start < overlap_end:
                # 存在重叠，进行重映射
                new_start_sec = overlap_start - seg_start + segment_offsets[i]
                new_end_sec = overlap_end - seg_start + segment_offsets[i]
                
                # 创建新字幕条目（保持原文本）
                new_sub = pysrt.SubRipItem(
                    index=len(new_subs) + 1,
                    start=seconds_to_srt_time(new_start_sec),
                    end=seconds_to_srt_time(new_end_sec),
                    text=sub.text
                )
                new_subs.append(new_sub)

    new_subs.sort()  # 确保字幕索引顺序正确
    new_subs.save(output_srt, encoding='utf-8')
    print(f"新字幕已生成: {output_srt}")

    # 2. 生成 ffmpeg concat 脚本并处理视频
    # 再次校验 segments 确保没有逻辑上的重叠
    for i in range(len(segments) - 1):
        if segments[i][1] > segments[i+1][0]:
            # 强制修正（防御性编程）
            segments[i+1] = (segments[i][1] + 0.001, segments[i+1][1])

    concat_file = "ffmpeg_concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for start, end in segments:
            abs_path = os.path.abspath(video_path).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")
            f.write(f"inpoint {start:.3f}\n")
            f.write(f"outpoint {end:.3f}\n")

    # 执行 ffmpeg 拼接
    if args.copy:
        # 无损拷贝模式
        if video_path.lower().endswith('.webm') and output_video.lower().endswith('.mp4'):
            print("警告: 正在将 WebM 无损拷贝至 MP4，这可能导致播放错误。建议使用默认重编码模式。")
        
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-segment_time_metadata', '1',
            '-i', concat_file, 
            '-c', 'copy', 
            '-avoid_negative_ts', 'make_zero',
            '-fflags', '+genpts',
            output_video
        ]
        print(f"正在执行无损拼接 (Copy Mode)...")
    else:
        # 重编码模式
        if args.gpu:
            ffmpeg_cmd = [
                'ffmpeg', '-y', 
                '-hwaccel', 'cuda', 
                '-f', 'concat', '-safe', '0',
                '-i', concat_file,
                '-c:v', 'h264_nvenc', '-preset', 'p4', '-rc', 'vbr', '-cq', '24',
                '-pix_fmt', 'yuv420p',
                '-fps_mode', 'cfr', 
                '-c:a', 'aac', '-b:a', '128k',
                '-af', 'aresample=async=1',
                output_video
            ]
            print(f"正在执行 GPU 加速重编码 (WebM -> MP4)...")
        else:
            ffmpeg_cmd = [
                'ffmpeg', '-y', 
                '-f', 'concat', '-safe', '0',
                '-i', concat_file,
                '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
                '-fps_mode', 'cfr',
                '-c:a', 'aac', '-b:a', '128k',
                '-af', 'aresample=async=1',
                output_video
            ]
            print(f"正在执行 CPU 重编码拼接...")
    
    try:
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"最终视频已生成: {output_video}")
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg 执行失败: {e.stderr.decode()}")
    finally:
        if os.path.exists(concat_file):
            os.remove(concat_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="字幕驱动的视频对白提取工具")
    
    # 核心参数
    parser.add_argument("input", help="输入视频文件路径")
    parser.add_argument("--srt", help="输入字幕文件路径 (默认查找同名 .srt)")
    parser.add_argument("-o", "--output", help="输出视频文件名 (默认 output.mp4)")
    parser.add_argument("--output_srt", help="输出字幕文件名 (默认 output.srt)")
    
    # 功能开关
    parser.add_argument("--copy", action="store_true", help="使用无损拷贝模式 (速度极快但可能卡顿)")
    parser.add_argument("--no-gpu", action="store_false", dest="gpu", help="禁用 GPU 加速")
    parser.set_defaults(gpu=True)
    
    # 算法参数
    parser.add_argument("--padding", type=float, default=0.3, help="对白前后扩展时间 (秒, 默认 0.3)")
    parser.add_argument("--merge_gap", type=float, default=0.5, help="合并相邻片段的最大间隔 (秒, 默认 0.5)")
    parser.add_argument("--min_duration", type=float, default=0.5, help="最短字幕过滤阈值 (秒, 默认 0.5)")

    args = parser.parse_args()

    # 设置默认输出名
    if not args.output:
        args.output = "output.mp4"
    if not args.output_srt:
        args.output_srt = "output.srt"

    process_video_and_srt(args)
