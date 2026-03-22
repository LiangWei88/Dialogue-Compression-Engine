# 字幕驱动的视频对白提取工具 (Subtitle-driven Video Extractor)

✨ **让视频只剩下“干货”** ✨

这是一个基于 Python 的智能视频处理工具，专门用于从带字幕（SRT）的原始视频中自动删除所有“没有对白”的片段。它会自动重构字幕时间轴，生成一个紧凑、连续的对白拼接视频及完全对齐的新字幕文件。

---

## 🎯 应用场景

本项目最初灵感源于 **沉浸式语言学习 (AJATT/Refold)**：
- **高效二刷**：看外语剧集/电影时，初看为了剧情，二刷/三刷时只想重复听对白以磨练听力。
- **制作听力素材**：将长达 1 小时的视频压缩成只有对白的 15 分钟“精华版”，适合通勤、跑步时碎片化复听。
- **录播剪辑**：自动剔除直播回放中的沉默时段，快速提取核心访谈或教学内容。

---

## 🚀 核心功能

- **智能提取**：根据 SRT 字幕精准定位对白，自动切除空白时段。
- **时间轴重构**：自动计算并映射新视频的字幕时间，确保音画字完美同步。
- **智能命名**：自动生成 `[Dialogue-Only]` 前缀文件，原位保存，不破坏原文件。
- **现代 GUI**：多巴胺配色、扁平化设计的图形界面，操作极其简单。
- **GPU 加速**：支持 NVIDIA GPU (NVENC) 硬件加速，处理长视频如丝般顺滑。
- **高度可调**：支持缓冲时间（Padding）、合并阈值、目标体积（MB）等深度定制。

---

## 🛠️ 安装指南

### 1. 前置要求
- **Python 3.10+**: [下载地址](https://www.python.org/downloads/)
- **FFmpeg**: 必须安装并配置到系统环境变量中。
  - Windows 用户推荐：[Gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
  - 安装后在终端输入 `ffmpeg -version` 确认可用。

### 2. 创建虚拟环境 (推荐)
为了保持系统环境整洁，建议在项目目录下创建虚拟环境：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
.\venv\Scripts\activate

# 激活虚拟环境 (Linux/macOS)
source venv/bin/activate
```

### 3. 安装依赖
在激活的虚拟环境中运行：

```bash
pip install -r requirements.txt
```

---

## 📖 使用手册

### 方式 A：图形界面 (最简单)
运行以下命令启动：
```bash
python gui.py
```
1. 点击 **选择视频**，脚本会自动寻找同目录下的同名 `.srt`。
2. 调整 **参数配置**（默认值已针对大多数场景优化）。
3. 点击 **开始处理**，静候大功告成。

### 方式 B：命令行 (进阶)
```bash
# 基础用法
python main.py my_video.mp4

# 指定目标大小为 50MB
python main.py my_video.mp4 --target-size 50

# 禁用 GPU 加速
python main.py my_video.mp4 --no-gpu
```

---

## 📦 下载与发布 (Portable Version)

对于没有 Python 环境的用户，可以直接下载我们打包好的独立可执行文件：

1. **获取程序**：前往 [GitHub Releases](https://github.com/YOUR_USERNAME/YOUR_REPO/releases) 下载最新的 `DialogueExtractor.exe`。
2. **FFmpeg 依赖**：由于法律和体积原因，`.exe` 文件不包含 FFmpeg。
   - 请确保您的电脑已安装 FFmpeg。
   - **简易方案**：下载 FFmpeg 后，将 `ffmpeg.exe` 和 `ffprobe.exe` 放在与 `DialogueExtractor.exe` 相同的文件夹下即可直接运行。

---

## 🛠️ 开发者：如何打包 EXE

如果您修改了代码并希望重新生成独立的可执行文件，推荐使用项目提供的脚本：

1. **安装 PyInstaller**：
   在虚拟环境中运行：
   ```bash
   pip install pyinstaller
   ```

2. **运行打包脚本**：
   项目根目录下提供了 `build_exe.py`，它会自动定位 `customtkinter` 资源并完成打包：
   ```bash
   python build_exe.py
   ```
   该脚本会自动执行以下操作：
   - `--onefile`: 打包为单个 EXE 文件。
   - `--noconsole`: 运行时不显示黑色的命令行窗口。
   - 自动包含 `customtkinter` 必要的资源文件。

3. **获取产物**：
   打包完成后，在项目目录下的 `dist/` 文件夹内即可找到 `DialogueExtractor.exe`。

4. **注意事项**：
   - 打包前请确保已安装 `customtkinter`, `pysrt`, `tqdm` 等所有依赖。
   - 如果遇到权限错误（PermissionError），请检查是否已关闭正在运行的 `DialogueExtractor.exe` 旧版本。

---

## ⚙️ 参数说明

| 界面参数名 | CLI 命令行参数 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `Padding` | `--padding` | `0.3` | 对白前后额外保留的缓冲时间（秒），防止剪辑生硬。 |
| `合并阈值` | `--merge_gap` | `0.5` | 两个片段间隔小于此值时自动合并（秒），避免画面频繁闪跳。 |
| `最小长度` | `--min_duration` | `0.5` | 过滤掉时长短于此值的字幕（秒），用于剔除杂音。 |
| `目标大小` | `--target-size` | `None` | 输入期望的最终文件大小（MB），脚本会自动反推最佳比特率。 |
| `无损模式` | `--copy` | `False` | 开启后不重编码（极速），但对 WebM 等 VFR 格式兼容性较差。 |
| `GPU 加速` | `--no-gpu` | `True` | 默认开启。若显卡不支持，请在 GUI 关闭或在 CLI 使用 `--no-gpu`。 |
| `CRF` | `--crf` | `26` | CPU 模式下的质量参数（18-30），数值越大体积越小。 |
| `CQ` | `--cq` | `28` | GPU 模式下的质量参数，数值越大体积越小。 |
| `输入字幕` | `--srt` | `自动` | 默认查找同名 .srt 文件。若不同名，请手动指定路径。 |
| `输出视频` | `-o` / `--output` | `自动` | 默认增加 `[Dialogue-Only]` 前缀并保存至原目录。 |

---

## 💡 常见问题

- **处理 WebM 视频卡顿？**
  - 请不要勾选“无损模式”，使用默认的重编码模式（支持 GPU 加速）即可解决。
- **显卡报错？**
  - 如果没有 NVIDIA 显卡，请在界面关闭“GPU 加速”或命令行添加 `--no-gpu`。
- **输出文件太大了？**
  - 尝试设置 `--target-size` 或在配置中增大 `CRF/CQ` 的值。

---

## 📄 开源协议
MIT License. 欢迎提交 Issue 或 PR。
