# stimulus/ssvep_pygame.py
import random, time, sys
import pygame
from pylsl import StreamInfo, StreamOutlet, local_clock

# ---------- 参数 ----------
SCREEN_REFRESH = 60           # 显示器刷新率（务必在系统里设为 60Hz）
FREQS = [10.0, 12.0, 15.0, 20.0]  # 四个目标频率
DUTY = 0.5                    # 占空比（此版本用整帧翻转方式，实际效果 ~50%）
TRIAL_LEN = 1.0               # 刺激窗（秒），先固定 1.0
REST_LEN = 2.0                # 休息时长（秒）
CUE_LEN = 0.5                 # 提示时长（秒）
BLOCK_TRIALS = 10             # 每目标试次数 => 共 4*10 = 40 个 trial
FULLSCREEN = True             # 全屏显示

# ---------- LSL 标记 ----------
info = StreamInfo(name='SSVEPMarkers', type='Markers', channel_count=1,
                  channel_format='string', source_id='markers_001')
outlet = StreamOutlet(info)

# ---------- pygame 初始化 ----------
pygame.init()
flags = pygame.FULLSCREEN if FULLSCREEN else 0
screen = pygame.display.set_mode((0,0), flags)
w, h = screen.get_size()
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 64)

# 四个目标位置（屏幕四象限）
rect_size = min(w, h)//6
positions = [
    (w//4 - rect_size//2, h//4 - rect_size//2),         # 左上 -> 10Hz
    (3*w//4 - rect_size//2, h//4 - rect_size//2),       # 右上 -> 12Hz
    (w//4 - rect_size//2, 3*h//4 - rect_size//2),       # 左下 -> 15Hz
    (3*w//4 - rect_size//2, 3*h//4 - rect_size//2)      # 右下 -> 20Hz
]

# 每个目标的半周期帧数（按 60Hz 屏计算）
half_period_frames = [max(1, round(SCREEN_REFRESH/(2*f))) for f in FREQS]

def draw_targets(states, highlight_idx=None):
    screen.fill((0,0,0))
    for i, (x, y) in enumerate(positions):
        on = states[i]
        color = (255,255,255) if on else (80,80,80)
        if highlight_idx == i:
            pygame.draw.rect(screen, (0,255,0), (x-8,y-8,rect_size+16,rect_size+16), 4)
        pygame.draw.rect(screen, color, (x,y,rect_size,rect_size))
    pygame.display.flip()

# Trial 列表：每个目标重复 BLOCK_TRIALS 次并打乱
trials = []
for idx in range(4):
    trials += [idx]*BLOCK_TRIALS
random.shuffle(trials)

# 主循环
try:
    for t_idx, target in enumerate(trials, 1):
        # 显示提示
        cue_text = font.render(f"Focus target freq: {int(FREQS[target])} Hz", True, (255,255,0))
        screen.fill((0,0,0)); screen.blit(cue_text, (w//2 - cue_text.get_width()//2, h//2))
        pygame.display.flip()
        outlet.push_sample([f"CUE|{FREQS[target]}"], local_clock())
        cue_t0 = time.time()
        while time.time() - cue_t0 < CUE_LEN:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit(0)
            clock.tick(SCREEN_REFRESH)

        # 刺激期
        states = [True, True, True, True]
        counters = [0,0,0,0]
        outlet.push_sample([f"TRIAL_START|{FREQS[target]}"], local_clock())
        trial_t0 = time.time()

        while time.time() - trial_t0 < TRIAL_LEN:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit(0)
            # 更新每个方块的闪烁
            for i in range(4):
                counters[i] += 1
                if counters[i] >= half_period_frames[i]:
                    states[i] = not states[i]
                    counters[i] = 0
            draw_targets(states, highlight_idx=target)  # 研究阶段：高亮真值目标
            clock.tick(SCREEN_REFRESH)

        outlet.push_sample([f"TRIAL_END|{FREQS[target]}"], local_clock())

        # 休息期
        outlet.push_sample(["REST_START"], local_clock())
        rest_t0 = time.time()
        while time.time() - rest_t0 < REST_LEN:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit(0)
            draw_targets([False, False, False, False])
            clock.tick(SCREEN_REFRESH)
        outlet.push_sample(["REST_END"], local_clock())

    pygame.quit()
except KeyboardInterrupt:
    pygame.quit()


