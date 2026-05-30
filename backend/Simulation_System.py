#!/usr/bin/env python3
"""
深空AI生存计算机仿真实验系统 — Flask 后端
建议一：昼夜节律 / 建议二：资源再生 / 建议三：设备老化 / 建议四：资源耦合
建议六：多实验组AI策略 / 建议七：耦合修正生存预测
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time
import random
import math
import copy

app = Flask(__name__)
CORS(app)

# ================================================================
# 建议六：AI 多实验组策略配置
# ================================================================
AI_MODES = {
    "Normal": {
        "activity": 1.00, "energy_save": 0.00, "ration": 1.00,
        "regen_boost": 1.00, "shield_priority": False,
        "prediction_window": 7,
        "description": "Standard Operation — all systems nominal"
    },
    "Dynamic AI": {
        "activity": 0.85, "energy_save": 0.20, "ration": 0.85,
        "regen_boost": 1.10, "shield_priority": False,
        "prediction_window": 14,
        "description": "Adaptive Optimization — real-time resource balancing"
    },
    "Emergency Survival": {
        "activity": 0.50, "energy_save": 0.45, "ration": 0.60,
        "regen_boost": 1.30, "shield_priority": True,
        "prediction_window": 30,
        "description": "Critical Survival Protocol — oxygen & water priority"
    },
    "Energy Conservative": {
        "activity": 0.90, "energy_save": 0.35, "ration": 0.90,
        "regen_boost": 0.90, "shield_priority": False,
        "prediction_window": 10,
        "description": "Power Saving Mode — solar output maximized"
    },
    "Medical Priority": {
        "activity": 0.75, "energy_save": 0.15, "ration": 0.95,
        "regen_boost": 1.05, "shield_priority": True,
        "prediction_window": 14,
        "description": "Health First Protocol — radiation shielding maximized"
    },
    "Maximum Output": {
        "activity": 1.20, "energy_save": -0.10, "ration": 1.10,
        "regen_boost": 0.80, "shield_priority": False,
        "prediction_window": 3,
        "description": "Full Capacity Operation — high risk high reward"
    },
    "Stealth Mode": {
        "activity": 0.60, "energy_save": 0.50, "ration": 0.70,
        "regen_boost": 1.20, "shield_priority": True,
        "prediction_window": 30,
        "description": "Ultra Low Power Dormancy — extended mission survivability"
    },
    "Balanced Recovery": {
        "activity": 0.80, "energy_save": 0.25, "ration": 0.80,
        "regen_boost": 1.15, "shield_priority": False,
        "prediction_window": 21,
        "description": "Gradual System Recovery — steady-state stabilization"
    },
}

# ================================================================
# 默认仿真初始状态
# ================================================================
DEFAULT_STATE = {
    "running": False, "paused": False,
    "missionTime": 0, "missionDay": 0,
    "crewCount": 4,
    "oxygen":      100.0, "food":        100.0,
    "water":       100.0, "energy":      100.0,
    "radiation":    10.0, "temperature":  22.0,
    "health":      100.0, "stability":   100.0,
    "survivalPrediction": 365.0,
    "aiMode": "Normal",
    "solarStormProbability": 5.0,
    "solarStormActive": False,
    "equipmentEfficiency": 1.0,
    "activityFactor": 1.0,
    "emergencyMode": False,
    "events": [], "history": [],
    "initRadiation": 10.0, "initTemperature": 22.0,
}

sim_state   = copy.deepcopy(DEFAULT_STATE)
sim_lock    = threading.Lock()
stop_event  = threading.Event()
sim_thread  = None
tick_interval = 1.0   # seconds per simulated hour

# ================================================================
# 核心仿真 Tick — 每次执行代表 1 模拟小时
# ================================================================
def simulation_tick():
    with sim_lock:
        s = sim_state
        if not s["running"] or s["paused"]:
            return

        mode = AI_MODES.get(s["aiMode"], AI_MODES["Normal"])
        hour         = s["missionTime"] % 24
        days_elapsed = s["missionTime"] / 24.0
        new_events   = []

        # ─────────────────────────────────────────────────
        # 建议一：昼夜节律 Circadian Rhythm
        # ─────────────────────────────────────────────────
        if 6 <= hour <= 22:
            activity = mode["activity"]
            phase    = "DAY"
        else:
            activity = mode["activity"] * 0.40
            phase    = "NIGHT"
        s["activityFactor"] = round(activity, 3)

        # ─────────────────────────────────────────────────
        # 建议三：设备老化衰减 Equipment Degradation
        # ─────────────────────────────────────────────────
        equip_eff = max(0.50, 1.0 - (days_elapsed / 365.0) * 0.20)
        s["equipmentEfficiency"] = round(equip_eff, 3)

        # ─────────────────────────────────────────────────
        # 随机事件系统（保留）
        # ─────────────────────────────────────────────────
        # 太阳风暴
        if s["solarStormActive"]:
            s["radiation"] = min(100.0, s["radiation"] + 0.80)
            if random.random() < 0.06:
                s["solarStormActive"] = False
                new_events.append(("SOLAR_STORM_END",
                    "☀ Solar storm subsiding — radiation normalizing"))
        elif random.random() < (s["solarStormProbability"] / 100.0) / 24.0:
            s["solarStormActive"] = True
            spike = random.uniform(15.0, 28.0)
            s["radiation"] = min(100.0, s["radiation"] + spike)
            new_events.append(("SOLAR_STORM",
                f"⚡ SOLAR STORM! Radiation +{spike:.1f} mSv"))

        # 随机故障（概率随设备老化上升）
        fail_mult = 2.0 - equip_eff   # 老化越高故障概率越大
        if random.random() < 0.004 * fail_mult:
            leak = round(random.uniform(3.0, 9.0), 1)
            s["oxygen"] = max(0.0, s["oxygen"] - leak)
            new_events.append(("OXYGEN_LEAK",
                f"💨 Oxygen Leak Detected! O₂ −{leak}%"))

        if random.random() < 0.003 * fail_mult:
            loss = round(random.uniform(2.0, 7.0), 1)
            s["food"] = max(0.0, s["food"] - loss)
            new_events.append(("COLDCHAIN_FAIL",
                f"🧊 Cold-Chain Failure! Food −{loss}%"))

        if random.random() < 0.003 * fail_mult:
            loss = round(random.uniform(5.0, 12.0), 1)
            s["energy"] = max(0.0, s["energy"] - loss)
            new_events.append(("ENERGY_FAIL",
                f"🔌 Power System Failure! Energy −{loss}%"))

        if random.random() < 0.0015 * fail_mult:
            loss = round(random.uniform(3.0, 8.0), 1)
            s["health"] = max(0.0, s["health"] - loss)
            new_events.append(("MEDICAL_EMERGENCY",
                f"🚑 Medical Emergency! Health −{loss}%"))

        # ─────────────────────────────────────────────────
        # 建议四：资源耦合计算
        # ─────────────────────────────────────────────────

        # --- 氧气消耗（辐射加剧呼吸损耗）---
        rad_factor    = 1.0 + (s["radiation"] / 100.0) * 0.30
        o2_consumption = s["crewCount"] * activity * rad_factor * 0.03

        # 建议二：氧气再生（电解水，依赖能源，受设备老化影响）
        regen_eff = mode["regen_boost"] * equip_eff
        if s["energy"] > 50.0:
            elec_rate         = 0.50 * regen_eff * (1.0 - mode["energy_save"] * 0.5)
            o2_regen          = elec_rate * 0.015
            water_for_elec    = elec_rate * 0.008
        elif s["energy"] > 20.0:
            frac              = (s["energy"] - 20.0) / 30.0
            o2_regen          = 0.015 * frac * regen_eff
            water_for_elec    = 0.004 * frac
        else:
            # 能源过低：再生完全停止（建议四：强耦合）
            o2_regen       = 0.0
            water_for_elec = 0.0

        s["oxygen"] = max(0.0, min(100.0, s["oxygen"] - o2_consumption + o2_regen))

        # --- 食物消耗（健康影响活动效率，建议四）---
        health_factor    = 1.0 if s["health"] >= 50.0 else (s["health"] / 50.0)
        food_consumption = s["crewCount"] * activity * mode["ration"] * 0.02 * health_factor
        s["food"] = max(0.0, s["food"] - food_consumption)

        # --- 水资源（消耗 − 建议二回收 + 电解消耗）---
        water_consumption = s["crewCount"] * activity * 0.025
        # 建议二：生命支持系统水回收（~32%）
        water_recycling   = s["crewCount"] * 0.008 * equip_eff
        net_water         = water_consumption - water_recycling + water_for_elec
        s["water"] = max(0.0, min(100.0, s["water"] - net_water))

        # --- 能源消耗 ---
        sys_load   = 1.0 - mode["energy_save"]
        temp_ctrl  = abs(s["temperature"] - 22.0) * 0.02
        e_consumption = sys_load * 0.05 + s["radiation"] * 0.01 + temp_ctrl * 0.03

        # 建议四：辐射加速设备耗能
        if s["radiation"] > 60.0:
            e_consumption *= 1.0 + (s["radiation"] - 60.0) / 100.0

        # 建议二：太阳能充电（白天，非太阳风暴，随设备老化衰减）
        solar_output = 0.0
        if not s["solarStormActive"] and 8 <= hour <= 18:
            day_factor   = math.sin(math.pi * (hour - 8) / 10.0)
            solar_output = 0.08 * day_factor * equip_eff

        s["energy"] = max(0.0, min(100.0, s["energy"] - e_consumption + solar_output))

        # --- 健康（辐射 + 资源匮乏，建议四）---
        shield_eff = 0.50 * equip_eff * (1.5 if mode["shield_priority"] else 1.0)
        rad_damage = s["radiation"] * 0.001
        if s["energy"] > 30.0:
            rad_damage *= shield_eff   # 建议四：辐射防护消耗能源
        s["health"] = max(0.0, min(100.0, s["health"] - rad_damage))

        if s["food"]   < 20.0:  s["health"] = max(0.0, s["health"] - 0.10)
        if s["oxygen"] < 30.0:  s["health"] = max(0.0, s["health"] - 0.30)
        if s["water"]  < 20.0:  s["health"] = max(0.0, s["health"] - 0.15)

        # 辐射自然衰减（非风暴时）
        if not s["solarStormActive"]:
            s["radiation"] = max(s["initRadiation"],
                                  round(s["radiation"] - 0.30, 2))

        # ─────────────────────────────────────────────────
        # 建议六：AI 差异化自动调度
        # ─────────────────────────────────────────────────
        emergency = False

        if s["energy"] < 40.0:
            boost = round(1.5 * mode["energy_save"], 3)
            if boost > 0:
                s["energy"] = min(100.0, s["energy"] + boost)
                new_events.append(("AI_DISPATCH",
                    f"🤖 [{s['aiMode']}] Energy critical — non-core shutdown "
                    f"(+{boost:.2f}%, save={mode['energy_save']})"))
            if s["energy"] < 15.0:
                emergency = True

        if s["oxygen"] < 30.0:
            s["activityFactor"] = round(activity * 0.70, 3)
            new_events.append(("AI_DISPATCH",
                f"🤖 [{s['aiMode']}] O₂ < 30% — activity reduced to "
                f"{s['activityFactor']:.2f}"))

        if s["radiation"] > 70.0:
            health_boost = 0.50 * mode["energy_save"]
            s["health"] = min(100.0, s["health"] + health_boost)
            new_events.append(("AI_DISPATCH",
                f"🤖 [{s['aiMode']}] Radiation > 70 — shield boost "
                f"(+{health_boost:.3f})"))
            emergency = True

        if s["food"] < 20.0:
            new_events.append(("AI_DISPATCH",
                f"🤖 [{s['aiMode']}] Food < 20% — emergency rationing "
                f"(ration={mode['ration']})"))

        if s["stability"] < 30.0:
            emergency = True

        s["emergencyMode"] = emergency

        # ─────────────────────────────────────────────────
        # 系统稳定性算法
        # ─────────────────────────────────────────────────
        rad_risk     = (s["radiation"] / 100.0) * 20.0
        s["stability"] = max(0.0, min(100.0, round(
            (s["oxygen"] + s["food"] + s["water"] + s["energy"] + s["health"])
            / 5.0 - rad_risk, 2
        )))

        # ─────────────────────────────────────────────────
        # 建议七：优化生存预测（资源耦合修正）
        # ─────────────────────────────────────────────────
        EPS = 1e-4

        o2_net_rate    = max(EPS, o2_consumption - o2_regen)
        food_rate      = max(EPS, food_consumption)
        water_net_rate = max(EPS, net_water)
        energy_net_rate= max(EPS, e_consumption - solar_output)

        o2_hours     = s["oxygen"] / o2_net_rate
        food_hours   = s["food"]   / food_rate
        water_hours  = s["water"]  / water_net_rate
        energy_hours = s["energy"] / energy_net_rate
        
        # 耦合修正：能源耗尽 → 电解停止 → O₂ 消耗加速
        if energy_hours < o2_hours and s["energy"] > 0.0:
            o2_at_energy_zero = s["oxygen"] - o2_net_rate * energy_hours  # 换成了净消耗率
            o2_hours = energy_hours + max(
                0.0, o2_at_energy_zero / max(EPS, o2_consumption)
            )

        # 耦合修正：水耗尽 → 电解停止 → O₂ 同步恶化
        if water_hours < o2_hours and s["water"] > 0.0:
            o2_after_water = s["oxygen"] - o2_net_rate * water_hours  # 换成了净消耗率
            o2_hours = water_hours + max(
                0.0, o2_after_water / max(EPS, o2_consumption)
            )

        s["survivalPrediction"] = max(0.0, round(
            min(o2_hours, food_hours, water_hours, energy_hours) / 24.0, 1
        ))

        # ─────────────────────────────────────────────────
        # 时间推进 + 历史快照
        # ─────────────────────────────────────────────────
        s["missionTime"] += 1
        s["missionDay"]   = s["missionTime"] // 24

        for etype, desc in new_events:
            s["events"].append({
                "tick": s["missionTime"],
                "type": etype,
                "description": desc
            })
        if len(s["events"]) > 200:
            s["events"] = s["events"][-200:]

        s["history"].append({
            "tick":               s["missionTime"],
            "day":                s["missionDay"],
            "hour":               hour,
            "phase":              phase,
            "oxygen":             round(s["oxygen"],    2),
            "food":               round(s["food"],      2),
            "water":              round(s["water"],     2),
            "energy":             round(s["energy"],    2),
            "health":             round(s["health"],    2),
            "stability":          round(s["stability"], 2),
            "radiation":          round(s["radiation"], 2),
            "temperature":        round(s["temperature"], 2),
            "survivalPrediction": s["survivalPrediction"],
            "activityFactor":     s["activityFactor"],
            "equipmentEfficiency":s["equipmentEfficiency"],
            "solarStormActive":   s["solarStormActive"],
            "solarOutput":        round(solar_output, 4),
            "o2Regen":            round(o2_regen, 4),
            "waterRecycling":     round(water_recycling, 4),
        })
        if len(s["history"]) > 720:
            s["history"] = s["history"][-720:]

        # ─────────────────────────────────────────────────
        # 判断任务失败
        # ─────────────────────────────────────────────────
        fails = []
        if s["oxygen"] <= 0:  fails.append("Oxygen Depleted")
        if s["health"]  <= 0: fails.append("Crew Incapacitated")
        if s["food"]    <= 0: fails.append("Food Exhausted")
        if s["water"]   <= 0: fails.append("Water Exhausted")
        if fails:
            s["running"] = False
            s["events"].append({
                "tick": s["missionTime"],
                "type": "MISSION_FAILED",
                "description": f"💀 MISSION FAILED — {' | '.join(fails)}"
            })


def sim_loop():
    while not stop_event.is_set():
        simulation_tick()
        time.sleep(tick_interval)


# ================================================================
# Flask API
# ================================================================

@app.route('/api/sim/modes')
def api_modes():
    return jsonify([
        {"id": k, "description": v["description"],
         "params": {kk: vv for kk, vv in v.items() if kk != "description"}}
        for k, v in AI_MODES.items()
    ])


@app.route('/api/sim/start', methods=['POST'])
def api_start():
    global sim_thread, tick_interval

    stop_event.set()
    if sim_thread and sim_thread.is_alive():
        sim_thread.join(timeout=1.5)
    stop_event.clear()

    data = request.get_json() or {}
    speed = max(0.5, min(20.0, float(data.get('speed', 1.0))))
    tick_interval = 1.0 / speed

    with sim_lock:
        sim_state.update({
            "running": True, "paused": False,
            "missionTime": 0, "missionDay": 0,
            "crewCount":    int(data.get('crewCount', 4)),
            "oxygen":       float(data.get('oxygen', 100.0)),
            "food":         float(data.get('food',   100.0)),
            "water":        float(data.get('water',  100.0)),
            "energy":       float(data.get('energy', 100.0)),
            "radiation":    float(data.get('radiation', 10.0)),
            "temperature":  float(data.get('temperature', 22.0)),
            "health":       100.0, "stability": 100.0,
            "survivalPrediction": 365.0,
            "aiMode":       data.get('aiMode', 'Normal'),
            "solarStormProbability": float(data.get('solarStormProbability', 5.0)),
            "solarStormActive": False,
            "equipmentEfficiency": 1.0, "activityFactor": 1.0,
            "emergencyMode": False,
            "events": [], "history": [],
            "initRadiation":    float(data.get('radiation',    10.0)),
            "initTemperature":  float(data.get('temperature',  22.0)),
        })

    sim_thread = threading.Thread(target=sim_loop, daemon=True)
    sim_thread.start()
    return jsonify({"success": True, "tickInterval": tick_interval, "speed": speed})


@app.route('/api/sim/status')
def api_status():
    # 【解決 Vercel 時間凍結】：前端只要來請求狀態，雲端就強制推演 1 個 Tick (小時)！
    if sim_state.get("running") and not sim_state.get("paused"):
        simulation_tick()

    with sim_lock:
        result = {k: v for k, v in sim_state.items() if k != 'history'}
        result['recentHistory'] = sim_state['history'][-72:]
        result['events']        = sim_state['events'][-30:]
    return jsonify(result)


@app.route('/api/sim/history')
def api_history():
    with sim_lock:
        return jsonify(sim_state['history'])


@app.route('/api/sim/pause', methods=['POST'])
def api_pause():
    with sim_lock:
        sim_state['paused'] = not sim_state.get('paused', False)
        return jsonify({"paused": sim_state['paused']})


@app.route('/api/sim/reset', methods=['POST'])
def api_reset():
    stop_event.set()
    if sim_thread and sim_thread.is_alive():
        sim_thread.join(timeout=1.5)
    stop_event.clear()
    with sim_lock:
        new = copy.deepcopy(DEFAULT_STATE)
        sim_state.clear()
        sim_state.update(new)
    return jsonify({"success": True})
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)