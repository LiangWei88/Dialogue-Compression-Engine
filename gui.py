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

# --- 字体设置 (根据要求调整大小且不加粗) ---
FONT_MAIN = ("Microsoft YaHei", 16)
FONT_LABEL = ("Microsoft YaHei", 16)
FONT_TITLE = ("Microsoft YaHei", 32, "bold") # 标题保留加粗以便区分
FONT_LOG = ("Consolas", 14)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 窗口设置
        self.title("Subtitle-driven Video Extractor")
        self.geometry("1100x900")
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

        # 1. 顶部标题
        title_label = ctk.CTkLabel(self.main_scroll, text="视频对白提取工具", font=FONT_TITLE, text_color=COLORS["primary"])
        title_label.pack(pady=(30, 20))

        # 2. 文件选择区 (顶部通栏)
        file_container = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        file_container.pack(pady=10, padx=40, fill="x")

        # 视频路径
        v_frame = ctk.CTkFrame(file_container, fg_color="transparent")
        v_frame.pack(fill="x", pady=8)
        ctk.CTkLabel(v_frame, text="视频路径:", width=100, anchor="w", font=FONT_LABEL).pack(side="left")
        self.v_entry = ctk.CTkEntry(v_frame, textvariable=self.video_path, placeholder_text="请选择要处理的视频文件", font=FONT_MAIN)
        self.v_entry.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(v_frame, text="选择视频", width=130, height=45, font=FONT_MAIN, fg_color=COLORS["primary"], hover_color="#FF8E8E", command=self._browse_video).pack(side="right")

        # 字幕路径
        s_frame = ctk.CTkFrame(file_container, fg_color="transparent")
        s_frame.pack(fill="x", pady=8)
        ctk.CTkLabel(s_frame, text="字幕路径:", width=100, anchor="w", font=FONT_LABEL).pack(side="left")
        self.s_entry = ctk.CTkEntry(s_frame, textvariable=self.srt_path, placeholder_text="可选 (默认加载视频同名 SRT)", font=FONT_MAIN)
        self.s_entry.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(s_frame, text="选择字幕", width=130, height=45, font=FONT_MAIN, fg_color=COLORS["primary"], hover_color="#FF8E8E", command=self._browse_srt).pack(side="right")

        # 3. 中间核心区: 左右并排 (配置 vs 日志)
        middle_container = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        middle_container.pack(pady=20, padx=40, fill="x")

        # 左侧: 配置参数
        self.param_frame = ctk.CTkFrame(middle_container, fg_color=COLORS["white"], corner_radius=15, border_width=1, border_color="#E0E0E0")
        self.param_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        ctk.CTkLabel(self.param_frame, text="⚙️ 参数配置", font=FONT_LABEL, text_color=COLORS["text"]).pack(pady=(15, 10), padx=20, anchor="w")
        
        # 参数子项
        self._create_slider(self.param_frame, "Padding (秒) - 对白前后缓冲", self.padding, 0.0, 2.0)
        self._create_slider(self.param_frame, "合并阈值 (秒) - 间隔合并", self.merge_gap, 0.1, 2.0)
        self._create_slider(self.param_frame, "最小长度 (秒) - 字幕过滤", self.min_duration, 0.1, 1.0)
        
        mode_frame = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        mode_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkSwitch(mode_frame, text="GPU 加速", variable=self.use_gpu, font=FONT_MAIN, progress_color=COLORS["secondary"]).pack(side="left", padx=(0, 20))
        ctk.CTkSwitch(mode_frame, text="无损模式", variable=self.use_copy, font=FONT_MAIN, progress_color=COLORS["secondary"]).pack(side="left")
        
        target_size_frame = ctk.CTkFrame(self.param_frame, fg_color="transparent")
        target_size_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(target_size_frame, text="目标大小 (MB):", font=FONT_MAIN).pack(side="left")
        ctk.CTkEntry(target_size_frame, textvariable=self.target_size, width=120, font=FONT_MAIN).pack(side="left", padx=10)

        # 右侧: 处理日志
        self.log_container = ctk.CTkFrame(middle_container, fg_color=COLORS["white"], corner_radius=15, border_width=1, border_color="#E0E0E0")
        self.log_container.pack(side="right", fill="both", expand=True, padx=(10, 0))
        
        ctk.CTkLabel(self.log_container, text="📝 处理日志", font=FONT_LABEL, text_color=COLORS["text"]).pack(pady=(15, 5), padx=20, anchor="w")
        self.log_text = ctk.CTkTextbox(self.log_container, height=300, fg_color="#F8F8F8", font=FONT_LOG, border_width=0)
        self.log_text.pack(pady=10, padx=20, fill="both", expand=True)

        # 4. 底部区: 进度条与按钮
        bottom_container = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        bottom_container.pack(pady=20, padx=40, fill="x")

        # 进度条
        self.progress_bar = ctk.CTkProgressBar(bottom_container, progress_color=COLORS["secondary"], height=25)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=10)
        
        self.status_label = ctk.CTkLabel(bottom_container, text="就绪", font=FONT_MAIN, text_color=COLORS["text"])
        self.status_label.pack(pady=(0, 20))

        # 运行按钮
        self.run_btn = ctk.CTkButton(bottom_container, text="开始处理", height=75, font=("Microsoft YaHei", 24, "bold"), 
                                     fg_color=COLORS["primary"], hover_color="#FF8E8E", corner_radius=38, command=self._start_task)
        self.run_btn.pack(fill="x")

    def _create_slider(self, parent, label, var, start, end):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(f, text=label, font=FONT_MAIN).pack(side="top", anchor="w")
        
        s_row = ctk.CTkFrame(f, fg_color="transparent")
        s_row.pack(fill="x", pady=2)
        s = ctk.CTkSlider(s_row, from_=start, to=end, variable=var, button_color=COLORS["primary"], progress_color=COLORS["secondary"])
        s.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(s_row, textvariable=var, width=60, font=FONT_MAIN).pack(side="right", padx=(10, 0))

    def _browse_video(self):
        p = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.webm *.mkv *.mov *.avi *.flv *.ts")])
        if p: 
            self.video_path.set(p)
            base = os.path.splitext(p)[0]
            if os.path.exists(base + ".srt"):
                self.srt_path.set(base + ".srt")
            else:
                self.srt_path.set("")

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
        
        class Args:
            pass
        
        args = Args()
        args.input = self.video_path.get()
        args.srt = self.srt_path.get()
        args.output = None 
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
