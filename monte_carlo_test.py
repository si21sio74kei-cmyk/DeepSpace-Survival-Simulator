import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import product
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
import random
import math
import time
import os
import warnings

warnings.filterwarnings('ignore')

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
        # 独立初始化状态
        s = {
            "crewCount": crew_size,
            "oxygen": 100.0, "food": 100.0, "water": 100.0, "energy": 100.0,
            "radiation": 10.0, "temperature": 22.0, "health": 100.0,
            "solarStormProbability": storm_prob * 100.0,
            "solarStormActive": False,
            "initRadiation": 10.0, "initTemperature": 22.0,
        }
        
        days_survived = 0
        total_ticks = MAX_DAYS * 24

        for tick in range(total_ticks):
            mode = mode_base.copy()
            hour = tick % 24
            days_elapsed = tick / 24.0

            # 1. 动态AI算法注入
            if ai_mode_name == "Dynamic AI":
                w_o2 = 12.0 if s["oxygen"] < 35.0 else 1.0
                w_en = 10.0 if s["energy"] < 30.0 else 1.0
                w_rad = 6.0 if s["radiation"] > 60.0 else 0.5
                base_act = 0.85 - (w_o2 * 0.04) - (s["radiation"] * 0.002)
                base_es  = 0.20 + (w_en * 0.05) + (s["radiation"] * 0.003)
                mode["activity"] = max(0.35, min(1.20, base_act))
                mode["energy_save"] = max(-0.10, min(0.60, base_es))

            # 2. 昼夜节律与设备老化
            is_day = (6 <= hour <= 22)
            activity = mode["activity"] if is_day else mode["activity"] * 0.40
            equip_eff = max(0.50, 1.0 - (days_elapsed / 365.0) * 0.20)

            # 温度动态波动（白噪声 + 昼夜温差模拟）
            target_t = s["initTemperature"] + (0.6 if is_day else -0.4)
            s["temperature"] = round(s["temperature"] + (target_t - s["temperature"]) * 0.15 + random.uniform(-0.15, 0.15), 2)

            # 3. 随机事件与灾害
            if s["solarStormActive"]:
                s["radiation"] = min(100.0, s["radiation"] + 0.80)
                if random.random() < 0.06: s["solarStormActive"] = False
            elif random.random() < (s["solarStormProbability"] / 100.0) / 24.0:
                s["solarStormActive"] = True
                s["radiation"] = min(100.0, s["radiation"] + random.uniform(15.0, 28.0))

            fail_mult = 2.0 - equip_eff
            if random.random() < 0.004 * fail_mult: s["oxygen"] = max(0.0, s["oxygen"] - random.uniform(3.0, 9.0))
            if random.random() < 0.003 * fail_mult: s["food"] = max(0.0, s["food"] - random.uniform(2.0, 7.0))
            if random.random() < 0.003 * fail_mult: s["energy"] = max(0.0, s["energy"] - random.uniform(5.0, 12.0))
            if random.random() < 0.0015 * fail_mult: s["health"] = max(0.0, s["health"] - random.uniform(3.0, 8.0))

            # 4. 核心资源耦合计算
            rad_factor = 1.0 + (s["radiation"] / 100.0) * 0.30
            o2_consumption = s["crewCount"] * activity * rad_factor * 0.03
            regen_eff = mode["regen_boost"] * equip_eff
            
            if s["energy"] > 50.0:
                elec_rate = 0.50 * regen_eff * (1.0 - mode["energy_save"] * 0.5)
                o2_regen, water_for_elec = elec_rate * 0.015, elec_rate * 0.008
            elif s["energy"] > 20.0:
                frac = (s["energy"] - 20.0) / 30.0
                o2_regen, water_for_elec = 0.015 * frac * regen_eff, 0.004 * frac
            else:
                o2_regen, water_for_elec = 0.0, 0.0
                
            s["oxygen"] = max(0.0, min(100.0, s["oxygen"] - o2_consumption + o2_regen))

            health_factor = 1.0 if s["health"] >= 50.0 else (s["health"] / 50.0)
            s["food"] = max(0.0, s["food"] - (s["crewCount"] * activity * mode["ration"] * 0.02 * health_factor))
            
            water_recycling = s["crewCount"] * 0.008 * equip_eff
            net_water = (s["crewCount"] * activity * 0.025) - water_recycling + water_for_elec
            s["water"] = max(0.0, min(100.0, s["water"] - net_water))

            e_consumption = (1.0 - mode["energy_save"]) * 0.05 + s["radiation"] * 0.01 + abs(s["temperature"] - 22.0) * 0.03
            if s["radiation"] > 60.0: e_consumption *= 1.0 + (s["radiation"] - 60.0) / 100.0
            solar_output = (0.08 * math.sin(math.pi * (hour - 8) / 10.0) * equip_eff) if (not s["solarStormActive"] and 8 <= hour <= 18) else 0.0
            s["energy"] = max(0.0, min(100.0, s["energy"] - e_consumption + solar_output))

            rad_damage = s["radiation"] * 0.001
            if s["energy"] > 30.0: rad_damage *= (0.50 * equip_eff * (1.5 if mode["shield_priority"] else 1.0))
            s["health"] = max(0.0, min(100.0, s["health"] - rad_damage))
            if s["food"] < 20.0: s["health"] -= 0.10
            if s["oxygen"] < 30.0: s["health"] -= 0.30
            if s["water"] < 20.0: s["health"] -= 0.15

            # 🆕 AI自动调度干预 (对齐 Simulation_System.py 的 dispatch 逻辑)
            if s["oxygen"] < 30.0:
                activity = activity * 0.70  # 缺氧时强制降代谢

            if not s["solarStormActive"] and s["radiation"] > s["initRadiation"] + 0.5:
                decay_rate = 0.85 if s["energy"] > 20.0 else 0.95
                s["radiation"] = ((s["radiation"] - s["initRadiation"]) * decay_rate) + s["initRadiation"]

            if s["energy"] < 40.0:
                boost = 1.5 * mode["energy_save"]
                if boost > 0: s["energy"] = min(100.0, s["energy"] + boost)
            if s["radiation"] > 70.0:
                s["health"] = min(100.0, s["health"] + (0.50 if mode["shield_priority"] else 0.10))

            # 🆕 李雅普诺夫势函数 V(S(t)) 诊断计算 (论文公式9)
            # V越小 → 系统越接近崩溃临界; V越大 → 越安全
            # 对应论文: V(S) = sum_i ((Si - Si_crit)/(Si_max - Si_crit))^2 * I(Si > Si_crit)
            o2_crit, w_crit, e_crit = 20.0, 15.0, 15.0
            lyap_v = 0.0
            if s["oxygen"] > o2_crit:
                lyap_v += ((s["oxygen"] - o2_crit) / (100.0 - o2_crit)) ** 2
            if s["water"] > w_crit:
                lyap_v += ((s["water"] - w_crit) / (100.0 - w_crit)) ** 2
            if s["energy"] > e_crit:
                lyap_v += ((s["energy"] - e_crit) / (100.0 - e_crit)) ** 2

            # 5. 失败条件判定 (任何一项归零即判定死亡)
            if s["oxygen"] <= 0 or s["health"] <= 0 or s["food"] <= 0 or s["water"] <= 0:
                days_survived = tick / 24.0
                break
        else:
            # 如果循环顺利跑完没有break，说明撑到了 MAX_DAYS
            days_survived = MAX_DAYS

        results.append({
            "AI_Mode": ai_mode_name,
            "Crew": crew_size,
            "Storm_Prob": storm_prob,
            "days": days_survived,
            "lyapunov_V": round(lyap_v, 6)  # 李雅普诺夫势函数 (论文公式9)
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
        Avg_LyapV=('lyapunov_V', 'mean'),
        Std_LyapV=('lyapunov_V', 'std')
    ).reset_index()

    stats['Std_Days'] = stats['Std_Days'].fillna(0)

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

    print("\n--- 📊 Test Summary ---")
    print(f"Total Simulations Run: {len(df)}")
    print(f"Overall Average Days Survived: {stats['Avg_Days'].mean():.1f} days")
    print(f"Best Scenario Record: {stats['Max_Days'].max():.1f} days")
    print(f"Worst Scenario Record: {stats['Min_Days'].min():.1f} days")

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