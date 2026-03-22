import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from main import process_video_and_srt

# --- 多巴胺配色方案 ---
COLORS = {
    "bg": "#FFFAF0",        # 象牙白 (背景)
    "primary": "#FF6B6B",   # 珊瑚红 (按钮)
    "secondary": "#4ECDC4", # 蒂芙尼蓝 (滑块/进度条)
    "accent": "#FFE66D",    # 柠檬黄 (强调)
    "text": "#2F2F2F",      # 深灰 (文字)
    "success": "#A8E6CF",   # 浅绿
    "white": "#FFFFFF"
}

# --- 字体设置 ---
FONT_MAIN = ("Microsoft YaHei", 14)
FONT_BOLD = ("Microsoft YaHei", 14, "bold")
FONT_TITLE = ("Microsoft YaHei", 28, "bold")
FONT_LOG = ("Consolas", 12)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 窗口设置
        self.title("Subtitle-driven Video Extractor")
        self.geometry("900x900")
        # 默认最大化
        self.after(0, lambda: self.state('zoomed'))
        
        ctk.set_appearance_mode("light")
        self.configure(fg_color=COLORS["bg"])

        # 变量初始化
        self.video_path = tk.StringVar()
        self.srt_path = tk.StringVar()
        self.padding = tk.DoubleVar(value=0.3)
        self.merge_gap = tk.DoubleVar(value=0.5)
        self.min_duration = tk.DoubleVar(value=0.5)
        self.use_gpu = tk.BooleanVar(value=True)
        self.use_copy = tk.BooleanVar(value=False)
        self.target_size = tk.StringVar(value="")
        self.crf = tk.IntVar(value=26)
        self.cq = tk.IntVar(value=28)

        self._setup_ui()

    def _setup_ui(self):
        # 使用滚动容器包裹所有内容
        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.main_scroll.pack(fill="both", expand=True)

        # 标题
        title_label = ctk.CTkLabel(self.main_scroll, text="视频对白提取工具", font=FONT_TITLE, text_color=COLORS["primary"])
        title_label.pack(pady=(30, 20))

        # 文件路径显示与选择按钮
        file_container = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        file_container.pack(pady=15, padx=40, fill="x")

        # 视频路径
        v_frame = ctk.CTkFrame(file_container, fg_color="transparent")
        v_frame.pack(fill="x", pady=8)
        ctk.CTkLabel(v_frame, text="视频路径:", width=100, anchor="w", font=FONT_BOLD).pack(side="left")
        self.v_entry = ctk.CTkEntry(v_frame, textvariable=self.video_path, placeholder_text="请选择要处理的视频文件", font=FONT_MAIN)
        self.v_entry.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(v_frame, text="选择视频", width=120, height=40, font=FONT_BOLD, fg_color=COLORS["primary"], hover_color="#FF8E8E", command=self._browse_video).pack(side="right")

        # 字幕路径
        s_frame = ctk.CTkFrame(file_container, fg_color="transparent")
        s_frame.pack(fill="x", pady=8)
        ctk.CTkLabel(s_frame, text="字幕路径:", width=100, anchor="w", font=FONT_BOLD).pack(side="left")
        self.s_entry = ctk.CTkEntry(s_frame, textvariable=self.srt_path, placeholder_text="可选 (默认加载视频同名 SRT)", font=FONT_MAIN)
        self.s_entry.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(s_frame, text="选择字幕", width=120, height=40, font=FONT_BOLD, fg_color=COLORS["primary"], hover_color="#FF8E8E", command=self._browse_srt).pack(side="right")

        # 配置参数区
        param_frame = ctk.CTkFrame(self.main_scroll, fg_color=COLORS["white"], corner_radius=15)
        param_frame.pack(pady=15, padx=40, fill="x")

        # 左右分栏
        left_p = ctk.CTkFrame(param_frame, fg_color="transparent")
        left_p.pack(side="left", fill="both", expand=True, padx=25, pady=25)
        right_p = ctk.CTkFrame(param_frame, fg_color="transparent")
        right_p.pack(side="right", fill="both", expand=True, padx=25, pady=25)

        # 左侧: 时间参数
        self._create_slider(left_p, "Padding (秒) - 对白前后缓冲", self.padding, 0.0, 2.0)
        self._create_slider(left_p, "合并阈值 (秒) - 间隔小于此值则合并", self.merge_gap, 0.1, 2.0)
        self._create_slider(left_p, "最小长度 (秒) - 过滤掉过短的字幕", self.min_duration, 0.1, 1.0)

        # 右侧: 质量与模式
        ctk.CTkSwitch(right_p, text="开启 GPU 加速 (NVIDIA)", variable=self.use_gpu, font=FONT_MAIN, progress_color=COLORS["secondary"]).pack(pady=15, anchor="w")
        ctk.CTkSwitch(right_p, text="无损模式 (Copy) - 极速但可能卡顿", variable=self.use_copy, font=FONT_MAIN, progress_color=COLORS["secondary"]).pack(pady=15, anchor="w")
        
        target_size_frame = ctk.CTkFrame(right_p, fg_color="transparent")
        target_size_frame.pack(fill="x", pady=15)
        ctk.CTkLabel(target_size_frame, text="目标大小 (MB):", anchor="w", font=FONT_MAIN).pack(side="left")
        ctk.CTkEntry(target_size_frame, textvariable=self.target_size, width=120, font=FONT_MAIN).pack(side="right")

        # 日志区
        log_label = ctk.CTkLabel(self.main_scroll, text="处理日志", font=FONT_BOLD)
        log_label.pack(pady=(15, 5), padx=40, anchor="w")
        self.log_text = ctk.CTkTextbox(self.main_scroll, height=250, fg_color="#F8F8F8", font=FONT_LOG, border_color="#E0E0E0", border_width=1)
        self.log_text.pack(pady=10, padx=40, fill="x")

        # 进度条区 (放在日志之后)
        self.progress_frame = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        self.progress_frame.pack(pady=15, padx=40, fill="x")
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, progress_color=COLORS["secondary"], height=20)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=8)
        
        self.status_label = ctk.CTkLabel(self.progress_frame, text="就绪", font=FONT_BOLD, text_color=COLORS["text"])
        self.status_label.pack()

        # 运行按钮
        self.run_btn = ctk.CTkButton(self.main_scroll, text="开始处理", height=65, font=("Microsoft YaHei", 22, "bold"), 
                                     fg_color=COLORS["primary"], hover_color="#FF8E8E", corner_radius=32, command=self._start_task)
        self.run_btn.pack(pady=30, padx=40, fill="x")

    def _create_slider(self, parent, label, var, start, end):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", pady=10)
        ctk.CTkLabel(f, text=label, font=FONT_MAIN).pack(side="top", anchor="w")
        s = ctk.CTkSlider(f, from_=start, to=end, variable=var, button_color=COLORS["primary"], progress_color=COLORS["secondary"])
        s.pack(side="left", fill="x", expand=True, pady=5)
        ctk.CTkLabel(f, textvariable=var, width=60, font=FONT_BOLD).pack(side="right", padx=5)

    def _browse_video(self):
        p = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.webm *.mkv *.mov *.avi *.flv *.ts")])
        if p: 
            self.video_path.set(p)
            base = os.path.splitext(p)[0]
            if os.path.exists(base + ".srt"):
                self.srt_path.set(base + ".srt")
            else:
                self.srt_path.set("") # 清空之前的选择

    def _browse_srt(self):
        p = filedialog.askopenfilename(filetypes=[("Subtitle files", "*.srt")])
        if p: self.srt_path.set(p)

    def _log(self, msg):
        self.log_text.insert("end", str(msg) + "\n")
        self.log_text.see("end")

    def _update_progress(self, curr, total, desc):
        percent = curr / total if total > 0 else 0
        self.progress_bar.set(percent)
        self.status_label.configure(text=f"{desc}: {percent:.1%}")

    def _start_task(self):
        if not self.video_path.get():
            messagebox.showwarning("警告", "请先选择输入视频文件！")
            return
        
        self.run_btn.configure(state="disabled", text="正在全力处理中...")
        self.log_text.delete("1.0", "end")
        self.progress_bar.set(0)
        self._log("任务启动...")
        
        # 构建类似 argparse 的对象
        class Args:
            pass
        
        args = Args()
        args.input = self.video_path.get()
        args.srt = self.srt_path.get()
        args.output = None # 触发 main.py 的 [Dialogue-Only] 命名逻辑
        args.output_srt = None
        args.padding = self.padding.get()
        args.merge_gap = self.merge_gap.get()
        args.min_duration = self.min_duration.get()
        args.gpu = self.use_gpu.get()
        args.copy = self.use_copy.get()
        args.crf = self.crf.get()
        args.cq = self.cq.get()
        args.bitrate = None
        
        try:
            ts = self.target_size.get().strip()
            args.target_size = float(ts) if ts else None
        except ValueError:
            args.target_size = None
            self._log("警告: 目标大小输入无效，将使用默认质量设置。")

        def run():
            try:
                stats = process_video_and_srt(args, progress_callback=self._update_progress, logger=self._log)
                if stats:
                    self.status_label.configure(text="任务圆满完成！")
                    msg = (f"处理完成！\n\n"
                           f"原始时长：{stats['original_duration']}\n"
                           f"压缩时长：{stats['output_duration']}\n"
                           f"节省时间：{stats['time_saved']}\n"
                           f"压缩率：{stats['compression_ratio']}\n\n"
                           f"保存路径：{os.path.abspath(stats['output_video'])}")
                    messagebox.showinfo("成功", msg)
                else:
                    self.status_label.configure(text="处理失败，请检查日志")
            except Exception as e:
                self._log(f"程序运行异常: {e}")
                messagebox.showerror("错误", f"处理过程中发生错误: {e}")
            finally:
                self.run_btn.configure(state="normal", text="开始处理")

        threading.Thread(target=run, daemon=True).start()

if __name__ == "__main__":
    app = App()
    app.mainloop()
