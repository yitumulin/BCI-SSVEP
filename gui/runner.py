# -*- coding: utf-8 -*-
# gui/runner.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import subprocess
import threading
import time
import sys
import os
from pathlib import Path

class BCIRunner:
    def __init__(self, root):
        self.root = root
        self.root.title("BCI SSVEP 实验管理器")
        self.root.geometry("900x800")
        
        # 进程管理
        self.decoder_process = None
        self.stimulus_process = None
        self.batch_running = False
        self.stop_batch = False
        
        # 工作目录（确保在 bci 根目录）
        self.bci_root = Path(__file__).parent.parent
        os.chdir(self.bci_root)
        
        # 检测conda环境
        self.conda_env = self.detect_conda_env()
        
        self.setup_ui()
        
    def detect_conda_env(self):
        """检测当前是否在conda环境中"""
        conda_env = os.environ.get('CONDA_DEFAULT_ENV')
        conda_prefix = os.environ.get('CONDA_PREFIX')
        
        if conda_env:
            self.log(f"检测到Conda环境: {conda_env}")
            return conda_env
        elif conda_prefix:
            env_name = os.path.basename(conda_prefix)
            self.log(f"检测到Conda环境: {env_name}")
            return env_name
        else:
            self.log("警告: 未检测到Conda环境，可能会缺少依赖包")
            return None
        
    def get_conda_python(self):
        """获取conda环境中的python路径"""
        if self.conda_env:
            # 尝试不同的conda路径
            possible_paths = [
                os.path.join(os.path.expanduser("~"), "miniconda3", "envs", self.conda_env, "python.exe"),
                os.path.join(os.path.expanduser("~"), "anaconda3", "envs", self.conda_env, "python.exe"),
                os.path.join(os.path.expanduser("~"), "miniforge3", "envs", self.conda_env, "python.exe"),
            ]
            
            # 检查CONDA_PREFIX
            conda_prefix = os.environ.get('CONDA_PREFIX')
            if conda_prefix:
                possible_paths.insert(0, os.path.join(conda_prefix, "python.exe"))
            
            for path in possible_paths:
                if os.path.exists(path):
                    return path
                    
        # 如果找不到conda python，使用当前python
        return sys.executable
        
    def setup_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 环境信息显示
        env_frame = ttk.LabelFrame(main_frame, text="环境信息", padding="5")
        env_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        env_text = f"Python: {sys.executable}"
        if self.conda_env:
            env_text += f" | Conda环境: {self.conda_env}"
        else:
            env_text += " | 警告: 未检测到Conda环境"
            
        ttk.Label(env_frame, text=env_text, font=("Arial", 8)).grid(row=0, column=0, sticky=tk.W)
        
        # 配置区域
        config_frame = ttk.LabelFrame(main_frame, text="配置参数", padding="10")
        config_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Subject ID
        ttk.Label(config_frame, text="Subject ID:").grid(row=0, column=0, sticky=tk.W)
        self.subject_var = tk.StringVar(value="C1")
        ttk.Entry(config_frame, textvariable=self.subject_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=(5, 20))
        
        # 解码器类型
        ttk.Label(config_frame, text="解码器:").grid(row=0, column=2, sticky=tk.W)
        self.decoder_var = tk.StringVar(value="CCA+")
        decoder_combo = ttk.Combobox(config_frame, textvariable=self.decoder_var, values=["CCA+", "FBCCA"], width=8, state="readonly")
        decoder_combo.grid(row=0, column=3, sticky=tk.W, padx=(5, 20))
        
        # 窗口长度
        ttk.Label(config_frame, text="窗口长度:").grid(row=1, column=0, sticky=tk.W)
        self.window_var = tk.StringVar(value="1.0")
        window_combo = ttk.Combobox(config_frame, textvariable=self.window_var, values=["0.5", "1.0", "1.5", "2.0"], width=8, state="readonly")
        window_combo.grid(row=1, column=1, sticky=tk.W, padx=(5, 20))
        window_combo.bind('<<ComboboxSelected>>', self.on_window_change)
        
        # 投票窗口
        ttk.Label(config_frame, text="投票窗口:").grid(row=1, column=2, sticky=tk.W)
        self.vote_var = tk.StringVar(value="5")
        vote_combo = ttk.Combobox(config_frame, textvariable=self.vote_var, values=["1", "3", "5", "7"], width=8, state="readonly")
        vote_combo.grid(row=1, column=3, sticky=tk.W, padx=(5, 20))
        
        # 通道模式
        ttk.Label(config_frame, text="通道模式:").grid(row=2, column=0, sticky=tk.W)
        self.channel_var = tk.StringVar(value="子集通道")
        channel_combo = ttk.Combobox(config_frame, textvariable=self.channel_var, values=["子集通道", "全通道"], width=12, state="readonly")
        channel_combo.grid(row=2, column=1, sticky=tk.W, padx=(5, 20))
        
        # Notch 频率
        ttk.Label(config_frame, text="Notch:").grid(row=2, column=2, sticky=tk.W)
        self.notch_var = tk.StringVar(value="50")
        notch_combo = ttk.Combobox(config_frame, textvariable=self.notch_var, values=["50", "60"], width=8, state="readonly")
        notch_combo.grid(row=2, column=3, sticky=tk.W, padx=(5, 20))
        
        # 日志目录
        ttk.Label(config_frame, text="日志目录:").grid(row=3, column=0, sticky=tk.W)
        self.logdir_var = tk.StringVar(value="data/logs")
        ttk.Entry(config_frame, textvariable=self.logdir_var, width=30).grid(row=3, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=(5, 5))
        ttk.Button(config_frame, text="浏览", command=self.browse_logdir).grid(row=3, column=3, sticky=tk.W, padx=(5, 0))
        
        # 单项运行区域
        single_frame = ttk.LabelFrame(main_frame, text="单项运行", padding="10")
        single_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(single_frame, text="运行解码器", command=self.run_decoder).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(single_frame, text="运行刺激端", command=self.run_stimulus).grid(row=0, column=1, padx=(5, 5))
        ttk.Button(single_frame, text="一键运行当前配置", command=self.run_current).grid(row=0, column=2, padx=(5, 5))
        ttk.Button(single_frame, text="停止所有", command=self.stop_all).grid(row=0, column=3, padx=(5, 0))
        
        # 批量运行区域
        batch_frame = ttk.LabelFrame(main_frame, text="批量运行", padding="10")
        batch_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(batch_frame, text="子集通道 8 组", command=lambda: self.run_batch("subset")).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(batch_frame, text="全通道 8 组", command=lambda: self.run_batch("all")).grid(row=0, column=1, padx=(5, 5))
        ttk.Button(batch_frame, text="全部 16 组", command=lambda: self.run_batch("both")).grid(row=1, column=0, padx=(0, 5))
        ttk.Button(batch_frame, text="停止批量", command=self.stop_batch_run).grid(row=1, column=1, padx=(5, 5))
        
        # 状态显示
        status_frame = ttk.LabelFrame(main_frame, text="运行状态", padding="10")
        status_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(status_frame, textvariable=self.status_var, font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W)
        
        self.progress_var = tk.StringVar(value="")
        ttk.Label(status_frame, textvariable=self.progress_var).grid(row=1, column=0, sticky=tk.W)
        
        # 日志显示
        log_frame = ttk.LabelFrame(main_frame, text="实时日志", padding="10")
        log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置权重
        main_frame.rowconfigure(4, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        
        # 初始化窗口长度联动
        self.on_window_change(None)
        
        # 添加欢迎信息
        self.log("BCI SSVEP 实验管理器已启动")
        if self.conda_env:
            self.log(f"已检测到Conda环境: {self.conda_env}")
        else:
            self.log("警告: 未检测到Conda环境，请确保已激活 bci-ssvep")
        self.log("请配置参数后点击相应按钮开始实验")
        
    def log(self, message):
        """添加日志信息"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        # 如果log_text还没创建，先打印到控制台
        if hasattr(self, 'log_text'):
            self.log_text.insert(tk.END, log_message)
            self.log_text.see(tk.END)
            self.root.update_idletasks()
        else:
            print(log_message.strip())
        
    def create_conda_cmd(self, python_cmd):
        """创建在conda环境中运行的命令"""
        # 直接使用conda环境的python路径，避免conda命令找不到的问题
        conda_python = self.get_conda_python()
        return [conda_python] + python_cmd[1:]
        
    def on_window_change(self, event):
        """窗口长度变化时自动调整投票窗口"""
        window = float(self.window_var.get())
        if window <= 1.0:
            self.vote_var.set("5")
        else:
            self.vote_var.set("3")
            
    def browse_logdir(self):
        """浏览日志目录"""
        dir_path = filedialog.askdirectory(initialdir=self.logdir_var.get())
        if dir_path:
            self.logdir_var.set(dir_path)
            
    def ensure_logdir(self):
        """确保日志目录存在"""
        logdir = Path(self.logdir_var.get())
        logdir.mkdir(parents=True, exist_ok=True)
        
    def get_decoder_cmd(self, window, vote, channels, logfile):
        """生成解码器命令"""
        decoder = self.decoder_var.get()
        notch = self.notch_var.get()
        
        if decoder == "CCA+":
            script = "online/online_cca.py"
        else:
            script = "online/online_fbcca.py"
            
        python_cmd = [
            "python", script,
            "--window", str(window),
            "--vote", str(vote),
            "--freqs", "10,12,15,20",
            "--notch", notch,
            "--latlog", logfile
        ]
        
        if channels == "subset":
            python_cmd.extend(["--chs", "2,3,6,7"])
            
        return self.create_conda_cmd(python_cmd)
        
    def get_logfile_name(self, window, vote, channels):
        """生成日志文件名"""
        subject = self.subject_var.get()
        decoder = self.decoder_var.get()
        window_str = f"w{window:.1f}".replace(".", "p")
        
        base_name = f"{subject}_{decoder}_{window_str}_v{vote}"
        if channels == "all":
            base_name += "_allch"
            
        logfile = Path(self.logdir_var.get()) / f"{base_name}.csv"
        
        # 防止文件覆盖
        counter = 1
        while logfile.exists():
            new_name = f"{base_name}_{counter}.csv"
            logfile = Path(self.logdir_var.get()) / new_name
            counter += 1
            
        return str(logfile)
        
    def run_decoder(self):
        """运行解码器"""
        if self.decoder_process and self.decoder_process.poll() is None:
            self.log("解码器已在运行")
            return
            
        try:
            self.ensure_logdir()
            window = float(self.window_var.get())
            vote = int(self.vote_var.get())
            channels = "subset" if self.channel_var.get() == "子集通道" else "all"
            logfile = self.get_logfile_name(window, vote, channels)
            
            cmd = self.get_decoder_cmd(window, vote, channels, logfile)
            self.log(f"启动解码器: {self.decoder_var.get()}, 窗口: {window}s, 投票: {vote}")
            self.log(f"命令: {' '.join(cmd)}")
            
            self.decoder_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.status_var.set("解码器运行中")
            
            # 启动线程监控输出
            threading.Thread(target=self.monitor_decoder, daemon=True).start()
            
        except Exception as e:
            self.log(f"启动解码器失败: {e}")
            messagebox.showerror("错误", f"启动解码器失败: {e}")
            
    def run_stimulus(self):
        """运行刺激端"""
        if self.stimulus_process and self.stimulus_process.poll() is None:
            self.log("刺激端已在运行")
            return
            
        try:
            python_cmd = ["python", "stimulus/ssvep_pygame.py"]
            cmd = self.create_conda_cmd(python_cmd)
            
            self.log("启动刺激端...")
            self.log(f"命令: {' '.join(cmd)}")
            
            self.stimulus_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.status_var.set("刺激端运行中")
            
            # 启动线程监控输出
            threading.Thread(target=self.monitor_stimulus, daemon=True).start()
            
        except Exception as e:
            self.log(f"启动刺激端失败: {e}")
            messagebox.showerror("错误", f"启动刺激端失败: {e}")
            
    def run_current(self):
        """一键运行当前配置"""
        if self.batch_running:
            self.log("批量运行中，请先停止")
            return
            
        self.log("开始一键运行当前配置...")
        threading.Thread(target=self.run_current_thread, daemon=True).start()
        
    def run_current_thread(self):
        """一键运行线程"""
        try:
            # 先启动解码器
            self.run_decoder()
            self.log("等待解码器初始化...")
            time.sleep(2)  # 等待解码器启动
            
            # 再启动刺激端
            self.run_stimulus()
            
            # 等待刺激端结束
            if self.stimulus_process:
                self.stimulus_process.wait()
                self.log("刺激端已结束")
                
            # 停止解码器
            self.stop_decoder()
            self.status_var.set("就绪")
            
        except Exception as e:
            self.log(f"一键运行失败: {e}")
            
    def stop_decoder(self):
        """停止解码器"""
        if self.decoder_process and self.decoder_process.poll() is None:
            self.decoder_process.terminate()
            self.log("解码器已停止")
            
    def stop_stimulus(self):
        """停止刺激端"""
        if self.stimulus_process and self.stimulus_process.poll() is None:
            self.stimulus_process.terminate()
            self.log("刺激端已停止")
            
    def stop_all(self):
        """停止所有进程"""
        self.stop_decoder()
        self.stop_stimulus()
        self.status_var.set("就绪")
        self.log("所有进程已停止")
        
    def monitor_decoder(self):
        """监控解码器输出"""
        if not self.decoder_process:
            return
            
        try:
            for line in iter(self.decoder_process.stdout.readline, ''):
                if line:
                    self.log(f"[解码器] {line.strip()}")
                    
            self.decoder_process.stdout.close()
            self.decoder_process.wait()
            self.log("解码器进程结束")
            
        except Exception as e:
            self.log(f"解码器监控错误: {e}")
            
    def monitor_stimulus(self):
        """监控刺激端输出"""
        if not self.stimulus_process:
            return
            
        try:
            for line in iter(self.stimulus_process.stdout.readline, ''):
                if line:
                    self.log(f"[刺激端] {line.strip()}")
                    
            self.stimulus_process.stdout.close()
            self.stimulus_process.wait()
            self.log("刺激端进程结束")
            
        except Exception as e:
            self.log(f"刺激端监控错误: {e}")
            
    def generate_batch_configs(self, mode):
        """生成批量配置"""
        configs = []
        decoders = ["CCA+", "FBCCA"]
        windows = [0.5, 1.0, 1.5, 2.0]
        
        for decoder in decoders:
            for window in windows:
                vote = 5 if window <= 1.0 else 3
                
                if mode in ["subset", "both"]:
                    configs.append({
                        "decoder": decoder,
                        "window": window,
                        "vote": vote,
                        "channels": "subset"
                    })
                    
                if mode in ["all", "both"]:
                    configs.append({
                        "decoder": decoder,
                        "window": window,
                        "vote": vote,
                        "channels": "all"
                    })
                    
        return configs
        
    def run_batch(self, mode):
        """批量运行"""
        if self.batch_running:
            self.log("批量运行已在进行中")
            return
            
        mode_names = {"subset": "子集通道", "all": "全通道", "both": "全部"}
        result = messagebox.askyesno("确认", f"确定要开始批量运行 {mode_names[mode]} 实验吗？\n这将需要较长时间。")
        if not result:
            return
            
        configs = self.generate_batch_configs(mode)
        total = len(configs)
        
        self.batch_running = True
        self.stop_batch = False
        
        self.log(f"开始批量运行 {total} 组配置")
        threading.Thread(target=self.run_batch_thread, args=(configs,), daemon=True).start()
        
    def run_batch_thread(self, configs):
        """批量运行线程"""
        try:
            total = len(configs)
            
            for i, config in enumerate(configs, 1):
                if self.stop_batch:
                    self.log("批量运行被用户停止")
                    break
                    
                self.progress_var.set(f"运行第 {i}/{total} 组")
                self.log(f"开始第 {i}/{total} 组: {config['decoder']} {config['window']}s {config['channels']}")
                
                # 临时设置GUI参数
                old_decoder = self.decoder_var.get()
                old_window = self.window_var.get()
                old_vote = self.vote_var.get()
                old_channel = self.channel_var.get()
                
                self.decoder_var.set(config["decoder"])
                self.window_var.set(str(config["window"]))
                self.vote_var.set(str(config["vote"]))
                self.channel_var.set("子集通道" if config["channels"] == "subset" else "全通道")
                
                # 运行当前配置
                self.ensure_logdir()
                logfile = self.get_logfile_name(config["window"], config["vote"], config["channels"])
                
                # 启动解码器
                cmd = self.get_decoder_cmd(config["window"], config["vote"], config["channels"], logfile)
                self.decoder_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                
                time.sleep(2)  # 等待解码器启动
                
                # 启动刺激端
                python_cmd = ["python", "stimulus/ssvep_pygame.py"]
                stimulus_cmd = self.create_conda_cmd(python_cmd)
                self.stimulus_process = subprocess.Popen(stimulus_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                
                # 等待刺激端结束
                self.stimulus_process.wait()
                
                # 停止解码器
                if self.decoder_process and self.decoder_process.poll() is None:
                    self.decoder_process.terminate()
                    self.decoder_process.wait()
                    
                # 恢复GUI参数
                self.decoder_var.set(old_decoder)
                self.window_var.set(old_window)
                self.vote_var.set(old_vote)
                self.channel_var.set(old_channel)
                
                self.log(f"第 {i}/{total} 组完成")
                
                if i < total:
                    self.log("休息 3 秒...")
                    time.sleep(3)
                    
        except Exception as e:
            self.log(f"批量运行错误: {e}")
        finally:
            self.batch_running = False
            self.stop_batch = False
            self.progress_var.set("")
            self.status_var.set("就绪")
            self.log("批量运行完成")
            messagebox.showinfo("完成", "批量实验已完成！")
            
    def stop_batch_run(self):
        """停止批量运行"""
        self.stop_batch = True
        self.stop_all()
        self.log("正在停止批量运行...")
        
def main():
    root = tk.Tk()
    app = BCIRunner(root)
    root.mainloop()
    
if __name__ == "__main__":
    main()