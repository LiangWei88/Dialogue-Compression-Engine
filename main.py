import os
import sys
import subprocess
import pysrt
import argparse
import time
from tqdm import tqdm
from datetime import timedelta

def get_video_duration(video_path):
    """使用 ffprobe 获取视频总时长（秒）"""
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', video_path
    ]
    # 在 Windows 下隐藏控制台窗口
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            check=True,
            creationflags=creationflags
        )
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

def format_size(size_bytes):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def run_ffmpeg_with_progress(cmd, total_duration, desc="Processing", progress_callback=None):
    """运行 FFmpeg 并解析进度条"""
    # 强制 FFmpeg 将进度输出到 stdout
    cmd = cmd + ['-progress', '-', '-nostats']
    
    # 在 Windows 下隐藏控制台窗口
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    # 统计信息
    start_time = time.time()
    
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True, 
        encoding='utf-8',
        errors='ignore',
        creationflags=creationflags
    )
    
    last_time = 0.0
    # 如果没有 GUI callback，使用 tqdm 命令行进度条
    pbar = None
    if not progress_callback:
        pbar = tqdm(total=total_duration, desc=desc, unit="s", bar_format='{l_bar}{bar}| {n:.1f}/{total:.1f}s [{elapsed}<{remaining}, {rate_fmt}]')

    for line in process.stdout:
        if 'out_time_us=' in line:
            try:
                # out_time_us=12345678 (单位是微秒)
                curr_time = int(line.split('=')[1]) / 1_000_000.0
                if curr_time > last_time:
                    if progress_callback:
                        progress_callback(curr_time, total_duration, desc)
                    if pbar:
                        pbar.update(curr_time - last_time)
                    last_time = curr_time
            except (ValueError, IndexError):
                pass
    
    process.wait()
    if pbar:
        pbar.close()
        
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd)
        
    return time.time() - start_time

def process_video_and_srt(args, progress_callback=None, logger=print):
    start_wall_time = time.time()
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
            logger(f"检测到同名字幕文件: {srt_path}")
        else:
            logger(f"错误: 未提供字幕文件，且未找到同名 .srt 文件 ({possible_srt})")
            return None

    # 统一命名逻辑：如果未指定输出名，则使用 [Dialogue-Only] 前缀
    input_dir = os.path.dirname(video_path)
    input_filename = os.path.basename(video_path)
    input_base = os.path.splitext(input_filename)[0]
    
    if not output_video or output_video == "output.mp4":
        output_video = os.path.join(input_dir, f"[Dialogue-Only] {input_base}.mp4")
    
    if not output_srt or output_srt == "output.srt":
        output_srt = os.path.join(input_dir, f"[Dialogue-Only] {input_base}.srt")

    video_duration = get_video_duration(video_path)
    if video_duration is None:
        return None

    segments = extract_dialogue_segments(srt_path, video_duration, args.padding, args.merge_gap, args.min_duration)
    if not segments:
        logger("未找到有效的对白片段。")
        return None

    total_output_duration = sum(end - start for start, end in segments)
    
    # 如果用户指定了目标大小，自动计算比特率
    if hasattr(args, 'target_size') and args.target_size and not args.bitrate:
        video_bitrate_kbps = (args.target_size * 8192) / total_output_duration - 128
        if video_bitrate_kbps < 100:
            video_bitrate_kbps = 100
            logger(f"警告: 目标大小过小，已设置为保底比特率 100kbps")
        args.bitrate = f"{int(video_bitrate_kbps)}k"
        logger(f"根据目标大小 {args.target_size}MB 反推视频比特率: {args.bitrate}")

    logger(f"\n--- 任务信息 ---")
    logger(f"原始视频时长: {video_duration:.2f}s")
    logger(f"提取后总时长: {total_output_duration:.2f}s (时间压缩率: {total_output_duration/video_duration:.1%})")
    logger(f"共提取到 {len(segments)} 个有效片段。")

    # 1. 生成新字幕文件
    subs = pysrt.open(srt_path)
    new_subs = pysrt.SubRipFile()
    
    segment_offsets = []
    current_offset = 0.0
    for start, end in segments:
        segment_offsets.append(current_offset)
        current_offset += (end - start)

    for sub in subs:
        sub_start = srt_to_seconds(sub.start)
        sub_end = srt_to_seconds(sub.end)
        if not sub.text.strip() or (sub_end - sub_start) < args.min_duration:
            continue
        for i, (seg_start, seg_end) in enumerate(segments):
            overlap_start = max(sub_start, seg_start)
            overlap_end = min(sub_end, seg_end)
            if overlap_start < overlap_end:
                new_start_sec = overlap_start - seg_start + segment_offsets[i]
                new_end_sec = overlap_end - seg_start + segment_offsets[i]
                new_sub = pysrt.SubRipItem(
                    index=len(new_subs) + 1,
                    start=seconds_to_srt_time(new_start_sec),
                    end=seconds_to_srt_time(new_end_sec),
                    text=sub.text
                )
                new_subs.append(new_sub)

    new_subs.sort()
    new_subs.save(output_srt, encoding='utf-8')

    for i in range(len(segments) - 1):
        if segments[i][1] > segments[i+1][0]:
            segments[i+1] = (segments[i][1] + 0.001, segments[i+1][1])

    concat_file = "ffmpeg_concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for start, end in segments:
            abs_path = os.path.abspath(video_path).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")
            f.write(f"inpoint {start:.3f}\n")
            f.write(f"outpoint {end:.3f}\n")

    if args.copy:
        if video_path.lower().endswith('.webm') and output_video.lower().endswith('.mp4'):
            logger("警告: 正在将 WebM 无损拷贝至 MP4，这可能导致播放错误。建议使用默认重编码模式。")
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-segment_time_metadata', '1',
            '-i', concat_file, 
            '-c', 'copy', 
            '-avoid_negative_ts', 'make_zero',
            '-fflags', '+genpts',
            output_video
        ]
        desc = "正在拼接 (Copy Mode)"
    else:
        if args.gpu:
            ffmpeg_cmd = [
                'ffmpeg', '-y', 
                '-hwaccel', 'cuda', 
                '-f', 'concat', '-safe', '0',
                '-i', concat_file,
                '-c:v', 'h264_nvenc', '-preset', 'p4', '-rc', 'vbr',
            ]
            if args.bitrate:
                ffmpeg_cmd += ['-b:v', args.bitrate]
            else:
                ffmpeg_cmd += ['-cq', str(args.cq)]
            ffmpeg_cmd += [
                '-pix_fmt', 'yuv420p',
                '-fps_mode', 'cfr', 
                '-c:a', 'aac', '-b:a', '128k',
                '-af', 'aresample=async=1',
                output_video
            ]
            desc = "正在重编码 (GPU 加速)"
        else:
            ffmpeg_cmd = [
                'ffmpeg', '-y', 
                '-f', 'concat', '-safe', '0',
                '-i', concat_file,
                '-c:v', 'libx264', '-preset', 'fast',
            ]
            if args.bitrate:
                ffmpeg_cmd += ['-b:v', args.bitrate]
            else:
                ffmpeg_cmd += ['-crf', str(args.crf)]
            ffmpeg_cmd += [
                '-fps_mode', 'cfr',
                '-c:a', 'aac', '-b:a', '128k',
                '-af', 'aresample=async=1',
                output_video
            ]
            desc = "正在重编码 (CPU 模式)"
    
    try:
        processing_time = run_ffmpeg_with_progress(ffmpeg_cmd, total_output_duration, desc=desc, progress_callback=progress_callback)
        total_elapsed = time.time() - start_wall_time
        
        stats = {
            "output_video": output_video,
            "original_duration": f"{video_duration:.2f}s",
            "output_duration": f"{total_output_duration:.2f}s",
            "time_saved": f"{video_duration - total_output_duration:.2f}s",
            "compression_ratio": f"{total_output_duration/video_duration:.1%}",
            "output_srt": output_srt,
            "total_elapsed": f"{total_elapsed:.2f}s",
            "ffmpeg_time": f"{processing_time:.2f}s",
            "speed": f"{total_output_duration/processing_time:.2f}x"
        }
        
        logger(f"\n--- 任务完成 ---")
        logger(f"最终视频: {os.path.basename(output_video)}")
        logger(f"时间统计: 原始 {stats['original_duration']} -> 压缩后 {stats['output_duration']}")
        logger(f"节省时长: {stats['time_saved']} (压缩率: {stats['compression_ratio']})")
        logger(f"总处理耗时: {stats['total_elapsed']} (处理速度: {stats['speed']})")
        return stats
    except subprocess.CalledProcessError as e:
        logger(f"\nFFmpeg 执行失败，返回码: {e.returncode}")
        return None
    finally:
        if os.path.exists(concat_file):
            os.remove(concat_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="字幕驱动的视频对白提取工具")
    parser.add_argument("input", help="输入视频文件路径")
    parser.add_argument("--srt", help="输入字幕文件路径 (默认查找同名 .srt)")
    parser.add_argument("-o", "--output", help="输出视频文件名 (默认 output.mp4)")
    parser.add_argument("--output_srt", help="输出字幕文件名 (默认 output.srt)")
    parser.add_argument("--copy", action="store_true", help="使用无损拷贝模式 (速度极快但可能卡顿)")
    parser.add_argument("--no-gpu", action="store_false", dest="gpu", help="禁用 GPU 加速")
    parser.set_defaults(gpu=True)
    parser.add_argument("--padding", type=float, default=0.3, help="对白前后扩展时间 (秒, 默认 0.3)")
    parser.add_argument("--merge_gap", type=float, default=0.5, help="合并相邻片段的最大间隔 (秒, 默认 0.5)")
    parser.add_argument("--min_duration", type=float, default=0.5, help="最短字幕过滤阈值 (秒, 默认 0.5)")
    parser.add_argument("--crf", type=int, default=26, help="CPU 模式下的 CRF 质量参数 (18-28, 默认 26, 越大体积越小)")
    parser.add_argument("--cq", type=int, default=28, help="GPU 模式下的 CQ 质量参数 (默认 28, 越大体积越小)")
    parser.add_argument("--bitrate", help="目标视频比特率 (如 1M, 2M, 会覆盖 CRF/CQ)")
    parser.add_argument("--target-size", type=float, help="期望的最终视频文件大小 (MB, 会自动计算比特率)")

    args = parser.parse_args()
    if not args.output:
        args.output = "output.mp4"
    if not args.output_srt:
        args.output_srt = "output.srt"

    process_video_and_srt(args)
