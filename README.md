# BCI SSVEP 实验管理系统

基于 SSVEP（稳态视觉诱发电位）的脑机接口实验管理系统，提供完整的刺激呈现、在线解码和实验管理功能。

## 🎯 主要功能

- **SSVEP 刺激呈现**：4个频率（10/12/15/20 Hz）的全屏闪烁刺激
- **实时在线解码**：CCA+ 和 FBCCA 算法
- **可视化 GUI 管理器**：一键运行、批量实验、参数配置
- **数据分析工具**：准确率统计、功率谱检查
- **LSL 集成**：支持 Lab Streaming Layer 数据流

## 📁 项目结构

```
bci/
├── stimulus/                 # 刺激呈现模块
│   └── ssvep_pygame.py      # pygame全屏刺激程序
├── online/                   # 在线解码模块
│   ├── online_cca.py        # CCA+解码器（含谐波增强）
│   └── online_fbcca.py      # 滤波器组CCA解码器
├── analysis/                 # 数据分析模块
│   ├── quick_qc_psd.py      # 功率谱质检
│   └── compute_metrics.py   # 准确率统计
├── gui/                      # 图形界面模块
│   └── runner.py            # GUI实验管理器
├── data/                     # 数据存储目录
│   ├── logs/                # 实验日志
│   └── raw/                 # 原始数据
├── requirements.txt          # Python依赖包
└── *.bat                    # 一键启动脚本
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Anaconda/Miniconda
- Windows 10/11

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/yitumulin/bci.git
cd bci
```

2. **创建conda环境**
```bash
conda create -n bci-ssvep python=3.9
conda activate bci-ssvep
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

### 启动方式

#### 方法1：GUI管理器（推荐）
```bash
# 双击启动脚本
启动GUI.bat

# 或命令行启动
conda activate bci-ssvep
python gui/runner.py
```

#### 方法2：命令行运行
```bash
# 运行刺激端
python stimulus/ssvep_pygame.py

# 运行解码器
python online/online_cca.py --window 1.0 --freqs 10,12,15,20 --chs 2,3,6,7
```

## 🎮 GUI使用指南

### 界面布局
- **环境信息**：显示Python路径和Conda环境状态
- **配置参数**：Subject ID、解码器类型、窗口长度、通道模式等
- **单项运行**：独立启动解码器或刺激端
- **批量运行**：自动运行多组实验配置
- **实时日志**：显示程序运行状态和输出

### 实验流程
1. **配置参数**：设置Subject ID、选择解码器类型、调整窗口长度
2. **一键运行**：点击"一键运行当前配置"自动完成实验
3. **批量实验**：选择批量模式进行系统性实验
4. **结果分析**：使用分析工具检查实验结果

## 📊 实验配置

### 刺激参数
- **频率**：10.0, 12.0, 15.0, 20.0 Hz
- **显示**：全屏4象限布局
- **试次**：每频率10次，共40个trial
- **时长**：刺激1.0s，休息2.0s，提示0.5s

### 解码算法
- **CCA+**：经典CCA + 谐波增强 + 窄带滤波
- **FBCCA**：滤波器组CCA，多频带融合

### 数据输出
自动生成规范命名的CSV文件：
- `C1_CCA_w1p0_v5.csv` - 子集通道
- `C1_CCA_w1p0_v5_allch.csv` - 全通道

## 🛠️ 高级配置

### 命令行参数

#### CCA+ 解码器
```bash
python online/online_cca.py \
  --window 1.0 \              # 分析窗口长度(秒)
  --vote 5 \                  # 多数投票窗口大小
  --freqs 10,12,15,20 \       # 目标频率
  --notch 50 \                # 陷波频率(Hz)
  --chs 2,3,6,7 \            # 使用的EEG通道
  --latlog data/logs/test.csv # 日志文件路径
```

#### FBCCA 解码器
```bash
python online/online_fbcca.py \
  --window 1.5 \
  --freqs 10,12,15,20 \
  --chs 0,1,2,3 \
  --vote 3
```

### 批量实验组合

系统支持16种实验配置的自动化批量运行：

| 算法 | 窗口长度 | 投票窗口 | 通道模式 |
|------|----------|----------|----------|
| CCA+ | 0.5s | 5 | 子集(2,3,6,7) |
| CCA+ | 1.0s | 5 | 子集(2,3,6,7) |
| CCA+ | 1.5s | 3 | 子集(2,3,6,7) |
| CCA+ | 2.0s | 3 | 子集(2,3,6,7) |
| FBCCA | 0.5s | 5 | 子集(2,3,6,7) |
| FBCCA | 1.0s | 5 | 子集(2,3,6,7) |
| FBCCA | 1.5s | 3 | 子集(2,3,6,7) |
| FBCCA | 2.0s | 3 | 子集(2,3,6,7) |

同样的8种配置也支持全通道模式。

## 📈 数据分析

### 准确率统计
```bash
python analysis/compute_metrics.py --csv data/logs/latency.csv
```

输出示例：
```
ALL: ACC=85.0% (n=160)
  10 Hz: 87.5% (n=40)
  12 Hz: 82.5% (n=40)
  15 Hz: 90.0% (n=40)
  20 Hz: 80.0% (n=40)

CCA+: ACC=83.8% (n=80)
FBCCA: ACC=86.3% (n=80)
```

### 功率谱检查
```bash
python analysis/quick_qc_psd.py
```

## 🔧 技术特性

### LSL集成
- **Markers流**：发送CUE/TRIAL_START/TRIAL_END标记
- **EEG流订阅**：实时接收脑电数据
- **时间同步**：精确的时间戳记录

### 信号处理
- **预处理**：50Hz陷波滤波、带通滤波、去直流
- **特征提取**：CCA典型相关分析
- **分类**：谐波增强、多数投票、滤波器组融合

### GUI特性
- **进程管理**：自动启动/停止子进程
- **实时监控**：捕获程序输出和错误
- **批量自动化**：无人值守批量实验
- **智能文件命名**：防覆盖、规范命名

## 🐛 故障排除

### 常见问题

#### 1. pygame找不到
```bash
conda activate bci-ssvep
pip install pygame
```

#### 2. LSL连接失败
检查EEG设备是否正常发送LSL流：
```bash
python -c "from pylsl import resolve_stream; print(resolve_stream())"
```

#### 3. GUI启动失败
确保在正确的conda环境中：
```bash
conda activate bci-ssvep
python -c "import tkinter; print('tkinter OK')"
```

#### 4. 权限错误
以管理员身份运行，或检查文件夹权限。

### 调试技巧
- 查看GUI实时日志区域的详细错误信息
- 检查生成的CSV文件是否正常
- 使用命令行单独测试各个模块

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🤝 贡献

欢迎提交Issue和Pull Request！

### 开发指南
1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📞 联系方式

- 项目链接：[https://github.com/yitumulin/bci](https://github.com/yitumulin/bci)
- 问题反馈：[Issues](https://github.com/yitumulin/bci/issues)

## 🙏 致谢

感谢所有贡献者和开源社区的支持！

---

*本项目用于科研和教育目的，请遵守相关伦理规范。*
