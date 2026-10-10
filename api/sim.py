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
from lib.simulation_core import step_simulation

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
    "bioEfficiency": 1.0,
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
        # 单一公式来源：backend/simulation_core.py（消除三端公式分叉）
        mode = AI_MODES.get(s["aiMode"], AI_MODES["Normal"]).copy()
        step_simulation(s, mode)

        # 历史快照（字段与前端大屏一致）
        s["history"].append({
            "tick":                s["missionTime"],
            "day":                 s["missionDay"],
            "hour":                s["hour"],
            "phase":               s["phase"],
            "oxygen":              round(s["oxygen"],    2),
            "food":                round(s["food"],      2),
            "water":               round(s["water"],     2),
            "energy":              round(s["energy"],    2),
            "health":              round(s["health"],    2),
            "stability":           round(s["stability"], 2),
            "radiation":           round(s["radiation"], 2),
            "temperature":         round(s["temperature"], 2),
            "survivalPrediction":  s["survivalPrediction"],
            "activityFactor":      s["activityFactor"],
            "equipmentEfficiency": s["equipmentEfficiency"],
            "solarStormActive":    s["solarStormActive"],
            "solarOutput":         s["solarOutput"],
            "o2Regen":             s["o2Regen"],
            "waterRecycling":      s["waterRecycling"],
        })
        if len(s["history"]) > 720:
            s["history"] = s["history"][-720:]
def sim_loop():
    while not stop_event.is_set():
        simulation_tick()
        stop_event.wait(tick_interval) # 完美替代 sleep，收到停止信號可瞬間打斷

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
        sim_state.clear()
        sim_state.update(copy.deepcopy(DEFAULT_STATE))
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
            "equipmentEfficiency": 1.0, "bioEfficiency": 1.0, "activityFactor": 1.0,
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
        if not sim_thread or not sim_thread.is_alive():
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

# 🆕 新增：地面站上行控制链路 (Uplink Command)
@app.route('/api/sim/command', methods=['POST'])
def api_command():
    # 🛡️ 安全修复：核心执行器增加极简 API_KEY 鉴权
    auth_header = request.headers.get('X-Mission-Control-Key')
    if auth_header != "MACAO_SPACE_2026":
        return jsonify({"success": False, "message": "🚨 未经授权的控制指令拦截"}), 401

    data = request.get_json() or {}
    cmd = data.get('command')

    with sim_lock:
        s = sim_state
        if not s["running"]:
            return jsonify({"success": False, "message": "模拟未启动"}), 400

        if cmd == "ACTIVATE_RAD_SHIELD":
            s["energy"] = max(0.0, s["energy"] - 15.0) 
            s["radiation"] = max(s["initRadiation"], s["radiation"] * 0.4) 
            s["events"].append({
                "tick": s["missionTime"], "type": "AI_DISPATCH",
                "description": "📡 [地面上行指令] CMD: ACTIVATE_RAD_SHIELD 成功。磁盾全功率过载，强行削减辐射！"
            })
        elif cmd == "ENTER_SAFE_MODE":
            s["aiMode"] = "Stealth Mode"
            s["activityFactor"] = 0.60
            s["events"].append({
                "tick": s["missionTime"], "type": "AI_DISPATCH",
                "description": "📡 [地面上行指令] CMD: ENTER_SAFE_MODE。主控被地面接管，强制切入低代谢隐蔽休眠！"
            })
        else:
            return jsonify({"success": False, "message": "未知或非法指令"}), 400
    return jsonify({"success": True})

if __name__ == '__main__':
    # 1. host='0.0.0.0' 允许公网/外网访问（核心修复！）
    # 2. 生产环境建议关闭 debug 和 reloader，防止线程重复启动
    app.run(
        host='0.0.0.0', 
        port=5000, 
        debug=False, 
        use_reloader=False
    )