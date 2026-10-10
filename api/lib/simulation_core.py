#!/usr/bin/env python3
"""
深空生存仿真 —— 核心方程唯一事实来源 (Single Source of Truth)
=================================================================
三端（在线引擎 Simulation_System / 影子引擎 Mission_Dashboard /
无头蒙特卡洛 monte_carlo_test）共用本模块，彻底消除“公式分叉”
（本次修复的 O2 再生断崖、温控系数 50x 差异正是分叉所致）。

调优依据（对照真实生保系统）：
  - NASA ECLSS：ISS 水回收率 WRS ≈ 93%  → WATER_RECOVERY_RATIO
  - 电解水 2H2O→O2 化学计量，制氧随可用功率提升  → 闭环率 O2_CLOSURE
  - 太阳能重标定，使白昼峰值可部分抵消负载        → SOLAR_PEAK
  - 生存预测改为“维生失效后按真实呼吸速率”，不再低估
  - 原“李雅普诺夫势函数”更名为 safety_margin（安全裕度），
    覆盖全部 5 项资源并加入辐射惩罚，语义更准确。
"""

import math
import random

# ---- 集中管理的平衡/物理常数（便于对照真实系统调参）----
WATER_RECOVERY_RATIO = 0.93     # ISS 水回收率 (NASA ECLSS WRS)
O2_CLOSURE = 0.70                # 电解制氧闭环率（满功率时再生≈消耗的 70%）
BIO_CLOSURE_FRAC = 0.35          # 生物再生环（MELiSSA 式）贡献的 O₂ 闭环份额（与电力解耦）
ELECTROLYSIS_WATER_LOSS = 0.15  # 电解额外水损耗比例（化学计量之外的系统损失）
SOLAR_PEAK = 0.22               # 白昼峰值太阳能输出（原 0.08，重标定后可部分抵消负载）

# 各资源临界阈值（用于安全裕度，越大越安全）
CRIT = {"oxygen": 20.0, "food": 20.0, "water": 15.0, "energy": 15.0, "health": 30.0}


def step_simulation(s, mode, stochastic=True):
    """推演一个模拟小时（tick）。原地修改状态字典 s，返回 s。

    s 必须包含：crewCount, oxygen, food, water, energy, radiation,
    temperature, health, stability, survivalPrediction, aiMode,
    solarStormProbability, solarStormActive, equipmentEfficiency,
    activityFactor, emergencyMode, events, history(可选), initRadiation,
    initTemperature, missionTime, missionDay。
    mode 为 AI 模式参数字典（activity/energy_save/ration/regen_boost/
    shield_priority）。
    stochastic=False 时关闭全部随机事件（风暴、故障、噪声扰动），
    用于多组对比/回归测试的确定性演算；默认 True 保持真实随机。
    """
    hour = int(s["missionTime"]) % 24
    days_elapsed = s["missionTime"] / 24.0
    new_events = []

    # ── 帕累托多目标自适应算法（仅 Dynamic AI 激活）──
    if s.get("aiMode") == "Dynamic AI":
        w_o2 = 12.0 if s["oxygen"] < 35.0 else 1.0
        w_en = 10.0 if s["energy"] < 30.0 else 1.0
        w_rad = 6.0 if s["radiation"] > 60.0 else 0.5
        base_act = 0.85 - (w_o2 * 0.04) - (s["radiation"] * 0.002)
        base_es = 0.20 + (w_en * 0.05) + (s["radiation"] * 0.003)
        mode["activity"] = max(0.35, min(1.20, base_act))
        mode["energy_save"] = max(-0.10, min(0.60, base_es))

    # ── 昼夜节律 ──
    if 6 <= hour <= 22:
        activity = mode["activity"]
        phase = "DAY"
    else:
        activity = mode["activity"] * 0.40
        phase = "NIGHT"
    s["activityFactor"] = round(activity, 3)

    # ── 舱内温度动态波动（白噪声 + 昼夜温差）──
    base_t = s.get("initTemperature", 22.0)
    target_t = base_t + (0.6 if phase == "DAY" else -0.4)
    noise_t = random.uniform(-0.15, 0.15) if stochastic else 0.0
    s["temperature"] = round(
        s["temperature"] + (target_t - s["temperature"]) * 0.15 + noise_t, 2)

    # ── 设备老化衰减 ──
    equip_eff = max(0.50, 1.0 - (days_elapsed / 365.0) * 0.20)
    s["equipmentEfficiency"] = round(equip_eff, 3)

    # ── 随机事件：太阳风暴 ──
    if s["solarStormActive"]:
        s["radiation"] = min(100.0, s["radiation"] + 0.80)
        if stochastic and random.random() < 0.06:
            s["solarStormActive"] = False
            new_events.append(("SOLAR_STORM_END",
                               "☀ Solar storm subsiding — radiation normalizing"))
    elif stochastic and random.random() < (s["solarStormProbability"] / 100.0) / 24.0:
        s["solarStormActive"] = True
        spike = random.uniform(15.0, 28.0)
        s["radiation"] = min(100.0, s["radiation"] + spike)
        new_events.append(("SOLAR_STORM",
                           f"⚡ SOLAR STORM! Radiation +{spike:.1f} mSv"))

    # ── 随机故障（概率随设备老化上升；确定性模式下关闭）──
    fail_mult = 2.0 - equip_eff
    if stochastic and random.random() < 0.004 * fail_mult:
        leak = round(random.uniform(3.0, 9.0), 1)
        s["oxygen"] = max(0.0, s["oxygen"] - leak)
        new_events.append(("OXYGEN_LEAK", f"💨 Oxygen Leak Detected! O₂ −{leak}%"))
    if stochastic and random.random() < 0.003 * fail_mult:
        loss = round(random.uniform(2.0, 7.0), 1)
        s["food"] = max(0.0, s["food"] - loss)
        new_events.append(("COLDCHAIN_FAIL", f"🧊 Cold-Chain Failure! Food −{loss}%"))
    if stochastic and random.random() < 0.003 * fail_mult:
        loss = round(random.uniform(5.0, 12.0), 1)
        s["energy"] = max(0.0, s["energy"] - loss)
        new_events.append(("ENERGY_FAIL", f"🔌 Power System Failure! Energy −{loss}%"))
    if stochastic and random.random() < 0.0015 * fail_mult:
        loss = round(random.uniform(3.0, 8.0), 1)
        s["health"] = max(0.0, s["health"] - loss)
        new_events.append(("MEDICAL_EMERGENCY", f"🚑 Medical Emergency! Health −{loss}%"))

    # ── 资源耦合计算 ──
    rad_factor = 1.0 + (s["radiation"] / 100.0) * 0.30
    o2_consumption = s["crewCount"] * activity * rad_factor * 0.03

    # 电解制氧：随可用功率（20%→100%）与再生增益提升，满功率时闭环率≈O2_CLOSURE
    regen_eff = mode["regen_boost"] * equip_eff
    if s["energy"] > 20.0:
        power_frac = (s["energy"] - 20.0) / 80.0
        o2_regen = o2_consumption * regen_eff * power_frac * O2_CLOSURE
        water_for_elec = o2_regen * ELECTROLYSIS_WATER_LOSS
    else:
        o2_regen = 0.0
        water_for_elec = 0.0

    # 生物再生环（MELiSSA 式：藻类/植物光合产氧，独立于电力）
    # 效率随辐射（高能粒子损伤藻类）与温度偏离下降，并随设备老化缓慢衰减；条件好时缓慢恢复
    bio_target = max(0.0, 1.0 - (s["radiation"] / 100.0) * 0.40
                     - abs(s["temperature"] - s.get("initTemperature", 22.0)) * 0.02) * equip_eff
    s["bioEfficiency"] = round(max(0.20, min(1.0,
        s["bioEfficiency"] + (bio_target - s["bioEfficiency"]) * 0.05)), 3)
    bio_o2 = o2_consumption * BIO_CLOSURE_FRAC * s["bioEfficiency"]

    s["oxygen"] = max(0.0, min(100.0, s["oxygen"] - o2_consumption + o2_regen + bio_o2))
    s["bioO2"] = round(bio_o2, 4)

    health_factor = 1.0 if s["health"] >= 50.0 else (s["health"] / 50.0)
    food_consumption = s["crewCount"] * activity * mode["ration"] * 0.02 * health_factor
    s["food"] = max(0.0, s["food"] - food_consumption)

    water_consumption = s["crewCount"] * activity * 0.025
    # 水回收对齐真实生保：ISS WRS ≈ 93% 闭环率
    water_recycling = s["crewCount"] * activity * 0.025 * WATER_RECOVERY_RATIO * equip_eff
    net_water = water_consumption - water_recycling + water_for_elec
    s["water"] = max(0.0, min(100.0, s["water"] - net_water))

    sys_load = 1.0 - mode["energy_save"]
    # 温控能耗：|ΔT|*0.03（相对用户设定基温 initTemperature，已对齐无头版）
    e_consumption = (sys_load * 0.05 + s["radiation"] * 0.01
                     + abs(s["temperature"] - s.get("initTemperature", 22.0)) * 0.03)
    if s["radiation"] > 60.0:
        e_consumption *= 1.0 + (s["radiation"] - 60.0) / 100.0

    # 太阳能充电（白昼、非风暴、随老化衰减），峰值重标定为 SOLAR_PEAK
    solar_output = 0.0
    if not s["solarStormActive"] and 8 <= hour <= 18:
        day_factor = math.sin(math.pi * (hour - 8) / 10.0)
        solar_output = SOLAR_PEAK * day_factor * equip_eff
    s["energy"] = max(0.0, min(100.0, s["energy"] - e_consumption + solar_output))

    # ── 健康（辐射 + 资源匮乏）──
    shield_eff = 0.50 * equip_eff * (1.5 if mode["shield_priority"] else 1.0)
    rad_damage = s["radiation"] * 0.001
    if s["energy"] > 30.0:
        rad_damage *= shield_eff
    s["health"] = max(0.0, min(100.0, s["health"] - rad_damage))
    if s["food"] < 20.0:
        s["health"] = max(0.0, s["health"] - 0.10)
    if s["oxygen"] < 30.0:
        s["health"] = max(0.0, s["health"] - 0.30)
    if s["water"] < 20.0:
        s["health"] = max(0.0, s["health"] - 0.15)

    # ── 辐射指数衰减（风暴后清洗期 + 宇宙射线背景微扰）──
    if not s["solarStormActive"]:
        if s["radiation"] > s["initRadiation"] + 0.5:
            decay_rate = 0.85 if s["energy"] > 20.0 else 0.95
            excess_rad = s["radiation"] - s["initRadiation"]
            s["radiation"] = round((excess_rad * decay_rate) + s["initRadiation"], 2)
        else:
            jitter = random.uniform(-0.1, 0.25) if stochastic else 0.0
            s["radiation"] = round(s["initRadiation"] + jitter, 2)

    # ── AI 差异化自动调度 ──
    if s["oxygen"] < 30.0:
        activity = activity * 0.70
        s["activityFactor"] = round(activity, 3)
        new_events.append(("AI_DISPATCH",
                           f"🤖 [{s.get('aiMode')}] O₂ < 30% — activity reduced to {s['activityFactor']:.2f}"))

    if s["energy"] < 40.0:
        boost = round(1.5 * mode["energy_save"], 3)
        if boost > 0:
            s["energy"] = min(100.0, s["energy"] + boost)
            new_events.append(("AI_DISPATCH",
                               f"🤖 [{s.get('aiMode')}] Energy critical — non-core shutdown (+{boost:.2f}%)"))

    if s["radiation"] > 70.0:
        health_boost = 0.50 if mode["shield_priority"] else 0.10
        s["health"] = min(100.0, s["health"] + health_boost)
        new_events.append(("AI_DISPATCH",
                           f"🤖 [{s.get('aiMode')}] Radiation > 70 — shield boost (+{health_boost:.3f})"))

    if s["food"] < 20.0:
        new_events.append(("AI_DISPATCH",
                           f"🤖 [{s.get('aiMode')}] Food < 20% — emergency rationing (ration={mode['ration']})"))

    # ── 系统稳定性 ──
    rad_risk = (s["radiation"] / 100.0) * 20.0
    s["stability"] = max(0.0, min(100.0, round(
        (s["oxygen"] + s["food"] + s["water"] + s["energy"] + s["health"])
        / 5.0 - rad_risk, 2)))

    # ── 生存预测（动态耦合修正）──
    EPS = 1e-4
    o2_net_rate = max(EPS, o2_consumption - o2_regen - bio_o2)
    food_rate = max(EPS, food_consumption)
    water_net_rate = max(EPS, net_water)
    energy_net_rate = max(EPS, e_consumption - solar_output)

    o2_hours = s["oxygen"] / o2_net_rate
    food_hours = s["food"] / food_rate
    water_hours = s["water"] / water_net_rate
    energy_hours = s["energy"] / energy_net_rate

    # 维生失效（断能/断水）后电解停止，但生物再生环（自带闭环水）仍供氧，
    # 故净耗氧 = 消耗 − 生物再生；按真实呼吸速率计算，不再低估
    emergency_o2_con = max(EPS, o2_consumption - bio_o2)
    o2h_final = o2_hours
    if energy_hours < o2_hours and s["energy"] > 0.0:
        o2_at_energy_zero = s["oxygen"] - o2_net_rate * energy_hours
        o2h_final = min(o2h_final, energy_hours + max(0.0, o2_at_energy_zero / max(EPS, emergency_o2_con)))
    if water_hours < o2_hours and s["water"] > 0.0:
        o2_after_water = s["oxygen"] - o2_net_rate * water_hours
        o2h_final = min(o2h_final, water_hours + max(0.0, o2_after_water / max(EPS, emergency_o2_con)))
    o2_hours = o2h_final

    s["survivalPrediction"] = max(0.0, round(
        min(o2_hours, food_hours, water_hours, energy_hours) / 24.0, 1))

    # ── 安全裕度 safety_margin（替代原“李雅普诺夫势函数”）──
    # 覆盖全部 5 项资源，越高于临界越安全；高辐射施加惩罚。
    margin = 0.0
    for res, crit in CRIT.items():
        if s[res] > crit:
            margin += ((s[res] - crit) / (100.0 - crit)) ** 2
    margin -= (s["radiation"] / 100.0) ** 2 * 0.2
    s["safety_margin"] = round(margin, 6)

    # ── 紧急模式标志 ──
    s["emergencyMode"] = bool(
        s["energy"] < 15.0 or s["radiation"] > 70.0 or s["stability"] < 30.0)

    # ── 时间推进 + 历史辅助字段 ──
    s["hour"] = hour
    s["phase"] = phase
    s["solarOutput"] = round(solar_output, 4)
    s["o2Regen"] = round(o2_regen, 4)
    s["waterRecycling"] = round(water_recycling, 4)
    s["missionTime"] += 1
    s["missionDay"] = s["missionTime"] // 24

    # ── 事件落库（统一用推进后的 tick）──
    for etype, desc in new_events:
        s["events"].append({"tick": s["missionTime"], "type": etype, "description": desc})
    if len(s["events"]) > 200:
        s["events"] = s["events"][-200:]

    # ── 失败判定 ──
    fails = []
    if s["oxygen"] <= 0:
        fails.append("Oxygen Depleted")
    if s["health"] <= 0:
        fails.append("Crew Incapacitated")
    if s["food"] <= 0:
        fails.append("Food Exhausted")
    if s["water"] <= 0:
        fails.append("Water Exhausted")
    if fails:
        s["running"] = False
        s["events"].append({
            "tick": s["missionTime"], "type": "MISSION_FAILED",
            "description": f"💀 MISSION FAILED — {' | '.join(fails)}"})

    return s
