import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 无头分析：仅保存图片，不弹窗（避免无显示器环境报错）
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import product

# Windows 默认控制台为 GBK，脚本内含 emoji/中文，强制 UTF-8 输出避免 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
import random
import math
import time
import os
import sys
import warnings

warnings.filterwarnings('ignore')

# 让无头分析脚本能从 backend/ 导入唯一公式来源 simulation_core
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
from simulation_core import step_simulation

# =============================================
# 🔧 全局配置区
# =============================================
CPU_CORES = 12          # 强制使用 12 核
RUNS_PER_SET = 500      # 每种组合 500 次
MAX_DAYS = 365          # 理论最大天数限制

# 🎨 绘图配置
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS'] 
plt.rcParams['axes.unicode_minus'] = False

# --- 参数空间定义 ---
AI_MODES = {
    "Normal": {"activity": 1.00, "energy_save": 0.00, "ration": 1.00, "regen_boost": 1.00, "shield_priority": False},
    "Dynamic AI": {"activity": 0.85, "energy_save": 0.20, "ration": 0.85, "regen_boost": 1.10, "shield_priority": False},
    "Emergency Survival": {"activity": 0.50, "energy_save": 0.45, "ration": 0.60, "regen_boost": 1.30, "shield_priority": True},
    "Energy Conservative": {"activity": 0.90, "energy_save": 0.35, "ration": 0.90, "regen_boost": 0.90, "shield_priority": False},
    "Medical Priority": {"activity": 0.75, "energy_save": 0.15, "ration": 0.95, "regen_boost": 1.05, "shield_priority": True},
    "Maximum Output": {"activity": 1.20, "energy_save": -0.10, "ration": 1.10, "regen_boost": 0.80, "shield_priority": False},
    "Stealth Mode": {"activity": 0.60, "energy_save": 0.50, "ration": 0.70, "regen_boost": 1.20, "shield_priority": True},
    "Balanced Recovery": {"activity": 0.80, "energy_save": 0.25, "ration": 0.80, "regen_boost": 1.15, "shield_priority": False},
}

CREW_SIZES = [3, 4, 5]
STORM_PROBS = [0.02, 0.05, 0.10]

# =============================================
# 🚀 无头高并发仿真核心
# =============================================
def run_headless_simulation(args):
    ai_mode_name, crew_size, storm_prob, runs = args
    results = []
    mode_base = AI_MODES[ai_mode_name]

    for _ in range(runs):
        # 独立初始化状态（字段需覆盖 simulation_core.step_simulation 的全部需求）
        s = {
            "running": True,
            "crewCount": crew_size,
            "oxygen": 100.0, "food": 100.0, "water": 100.0, "energy": 100.0,
            "radiation": 10.0, "temperature": 22.0, "health": 100.0,
            "stability": 100.0, "survivalPrediction": 365.0,
            "aiMode": ai_mode_name,
            "solarStormProbability": storm_prob * 100.0,
            "solarStormActive": False,
            "equipmentEfficiency": 1.0, "bioEfficiency": 1.0, "activityFactor": 1.0, "emergencyMode": False,
            "events": [],
            "initRadiation": 10.0, "initTemperature": 22.0,
            "missionTime": 0, "missionDay": 0,
        }

        days_survived = MAX_DAYS
        total_ticks = MAX_DAYS * 24

        # 单一公式来源：backend/simulation_core.py（消除三端公式分叉 + 全部调优）
        for _tick in range(total_ticks):
            mode = mode_base.copy()
            step_simulation(s, mode)
            if not s["running"]:
                days_survived = s["missionTime"] / 24.0
                break

        results.append({
            "AI_Mode": ai_mode_name,
            "Crew": crew_size,
            "Storm_Prob": storm_prob,
            "days": days_survived,
            "safety_margin": s["safety_margin"],  # 安全裕度（原“李雅普诺夫势函数”扩维版）
        })

    return results

# =============================================
# 📊 数据处理与可视化
# =============================================
def process_and_visualize(all_data):
    df = pd.DataFrame(all_data)

    # 现在的核心指标变成了 平均存活天数 (Avg_Days)
    stats = df.groupby(['AI_Mode', 'Crew', 'Storm_Prob']).agg(
        Avg_Days=('days', 'mean'),
        Max_Days=('days', 'max'),
        Min_Days=('days', 'min'),
        Std_Days=('days', 'std'),
        Avg_Safety=('safety_margin', 'mean'),
        Std_Safety=('safety_margin', 'std')
    ).reset_index()

    stats['Std_Days'] = stats['Std_Days'].fillna(0)

    # 🆕 蒙特卡洛收敛诊断：95% 置信区间 (1.96·SEM) 与收敛判定（参考 OpenGNC Monte Carlo Verification）
    n_runs = df.groupby(['AI_Mode', 'Crew', 'Storm_Prob']).size().rename('N').reset_index()
    stats = stats.merge(n_runs, on=['AI_Mode', 'Crew', 'Storm_Prob'])
    stats['SEM_Days'] = stats['Std_Days'] / np.sqrt(stats['N'])
    stats['CI95_Days'] = (1.96 * stats['SEM_Days']).round(3)
    stats['SEM_Safety'] = stats['Std_Safety'] / np.sqrt(stats['N'])
    stats['CI95_Safety'] = (1.96 * stats['SEM_Safety']).round(4)
    # 收敛判据：95% CI 半宽 < 5% 均值（排除均值≈0 的退化组）
    stats['Converged'] = stats['CI95_Days'] < (0.05 * stats['Avg_Days'].clip(lower=1.0))

    csv_name = f"deep_space_sim_results_{int(time.time())}.csv"
    stats.to_csv(csv_name, index=False)
    print(f"\n✅ 数据已保存至: {csv_name}")

    # 绘制热力图 (基于平均存活天数)
    for prob in STORM_PROBS:
        prob_df = stats[stats['Storm_Prob'] == prob]
        pivot_table = prob_df.pivot_table(
            values='Avg_Days', index='AI_Mode', columns='Crew'
        ).reindex(columns=[3, 4, 5])

        plt.figure(figsize=(12, 8))
        # cmap 改为 YlGnBu (天数越长颜色越深)，fmt 改为保留一位小数的 '.1f'
        sns.heatmap(
            pivot_table, annot=True, fmt='.1f', cmap='YlGnBu', linewidths=.5
        )
        plt.title(f'Average Survival Days Heatmap (Storm Prob: {prob*100}%) | Total Runs: {len(df)}')
        plt.ylabel('AI Strategy Mode')
        plt.xlabel('Crew Size')

        img_name = f"survival_days_heatmap_storm_{int(prob*100)}.png"
        plt.tight_layout()
        plt.savefig(img_name, dpi=150)
        plt.close()
        print(f"✅ 图表已保存: {img_name}")

    # 🆕 蒙特卡洛收敛诊断图：全局累计均值 + 95% CI 带，直观展示估计随样本数收敛
    df_sorted = df.sort_values(['AI_Mode', 'Crew', 'Storm_Prob']).reset_index(drop=True)
    n_seq = np.arange(1, len(df_sorted) + 1)
    cum_mean = df_sorted['days'].expanding().mean()
    cum_std = df_sorted['days'].expanding().std()
    cum_ci = 1.96 * (cum_std / np.sqrt(n_seq))
    plt.figure(figsize=(12, 6))
    plt.plot(n_seq, cum_mean, color='#1f77b4', label='Global mean survival (cumulative)')
    plt.fill_between(n_seq, cum_mean - cum_ci, cum_mean + cum_ci, color='#1f77b4', alpha=0.2,
                    label='95% confidence interval')
    plt.xlabel('Number of simulation runs')
    plt.ylabel('Mean survival days')
    plt.title('Monte Carlo Convergence Diagnostic')
    plt.legend(loc='best')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    conv_name = f"mc_convergence_{int(time.time())}.png"
    plt.savefig(conv_name, dpi=150)
    plt.close()
    print(f"✅ 收敛诊断图已保存: {conv_name}")

    print("\n--- 📊 Test Summary ---")
    print(f"Total Simulations Run: {len(df)}")
    print(f"Overall Average Days Survived: {stats['Avg_Days'].mean():.1f} days")
    print(f"Best Scenario Record: {stats['Max_Days'].max():.1f} days")
    print(f"Worst Scenario Record: {stats['Min_Days'].min():.1f} days")
    conv_rate = stats['Converged'].mean() * 100.0
    print(f"Converged groups (95% CI < 5% mean): {conv_rate:.0f}%  "
          f"(RUNS_PER_SET={RUNS_PER_SET})")

# =============================================
# 🏁 主程序入口
# =============================================
if __name__ == '__main__':
    print(f"🚀 Starting Headless Monte Carlo Simulation...")
    total_combinations = len(AI_MODES) * len(CREW_SIZES) * len(STORM_PROBS)
    total_runs_expected = total_combinations * RUNS_PER_SET
    
    print(f"⚙️ Config: Cores={CPU_CORES}, Sets={total_combinations}, Runs/Set={RUNS_PER_SET}")
    print(f"🎯 Target Total Simulations: {total_runs_expected}")

    tasks = []
    for mode, crew, prob in product(AI_MODES.keys(), CREW_SIZES, STORM_PROBS):
        tasks.append((mode, crew, prob, RUNS_PER_SET))

    final_data = []
    start_time = time.time()

    # 使用 12 核并行计算
    with Pool(processes=CPU_CORES) as pool:
        with tqdm(total=total_runs_expected, desc="Simulating") as pbar:
            for res_list in pool.imap_unordered(run_headless_simulation, tasks):
                final_data.extend(res_list)
                pbar.update(RUNS_PER_SET)

    print(f"\n⏱️ Simulation finished in {time.time() - start_time:.2f} seconds.")
    process_and_visualize(final_data)