#!/usr/bin/env python3
"""
深空AI生存預測引擎 — 獨立微服務 (Port 5002)
100% 完整繼承原版 app.py 的 8組AI策略、晝夜節律、資源再生、設備老化與隨機深空灾害事件。
內部原生修正雙階段耦合預測公式，不對原 app.py 做任何修改。
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time
import random
import math
import copy
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from simulation_core import step_simulation

app = Flask(__name__)
CORS(app) # 啟用跨域，對接 survival.html

# ================================================================
# 完整克隆原版 8 組 AI 多實驗組策略配置
# ================================================================
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

DEFAULT_STATE = {
    "running": False, "paused": False, "missionTime": 0, "missionDay": 0, "crewCount": 4,
    "oxygen": 100.0, "food": 100.0, "water": 100.0, "energy": 100.0,
    "radiation": 10.0, "temperature": 22.0, "health": 100.0, "stability": 100.0,
    "survivalPrediction": 365.0, "aiMode": "Normal", "solarStormProbability": 5.0,
    "solarStormActive": False, "equipmentEfficiency": 1.0, "bioEfficiency": 1.0, "activityFactor": 1.0,
    "emergencyMode": False, "events": [], "history": [], "initRadiation": 10.0, "initTemperature": 22.0
}

sim_state = copy.deepcopy(DEFAULT_STATE)
sim_lock = threading.Lock()
stop_event = threading.Event()
sim_thread = None
tick_interval = 1.0 

def simulation_tick():
    with sim_lock:
        s = sim_state
        if not s["running"] or s["paused"]:
            return
        # 单一公式来源：backend/simulation_core.py（消除三端公式分叉）
        mode = AI_MODES.get(s["aiMode"], AI_MODES["Normal"]).copy()
        step_simulation(s, mode)

        s["history"].append({
            "tick": s["missionTime"], "day": s["missionDay"], "hour": s["hour"],
            "oxygen": round(s["oxygen"], 2), "food": round(s["food"], 2),
            "water": round(s["water"], 2), "energy": round(s["energy"], 2),
            "health": round(s["health"], 2), "stability": round(s["stability"], 2),
            "survivalPrediction": s["survivalPrediction"]
        })
        if len(s["history"]) > 500:
            s["history"] = s["history"][-500:]

@app.route('/api/dash/start', methods=['POST'])
def api_start():
    global sim_thread, tick_interval
    stop_event.set()
    if sim_thread and sim_thread.is_alive():
        sim_thread.join(timeout=1.5)
    stop_event.clear()

    data = request.get_json() or {}
    speed = max(1.0, float(data.get('speed', 10.0)))
    tick_interval = 1.0 / speed
    
    with sim_lock:
        sim_state.clear()
        sim_state.update(copy.deepcopy(DEFAULT_STATE))
        sim_state.update({
            "running": True, "crewCount": int(data.get('crewCount', 4)), "aiMode": data.get('aiMode', 'Normal')
        })

    sim_thread = threading.Thread(target=sim_loop, daemon=True)
    sim_thread.start()
    return jsonify({"success": True})

@app.route('/api/dash/status')
def api_status():
    # 【解決 Vercel 時間凍結】：前端只要來請求狀態，雲端就強制推演 1 個 Tick (小時)！
    if sim_state.get("running") and not sim_state.get("paused"):
        if not sim_thread or not sim_thread.is_alive():
            simulation_tick()

    with sim_lock:
        res = {k: v for k, v in sim_state.items() if k != 'history'}
        res['history'] = sim_state['history'][-60:]
        res['events'] = sim_state['events'][-15:]
    return jsonify(res)

@app.route('/api/dash/pause', methods=['POST'])
def api_pause():
    with sim_lock:
        sim_state['paused'] = not sim_state.get('paused', False)
        return jsonify({"paused": sim_state['paused']})

@app.route('/api/dash/inject_snapshot', methods=['POST'])
def inject_snapshot():
    """接收前端注入的 5000 主引擎快照，并重置 5002 的影子引擎"""
    # 🛡️ 安全修复：数字孪生注入通道增加鉴权
    auth_header = request.headers.get('X-Mission-Control-Key')
    if auth_header != "MACAO_SPACE_2026":
        return jsonify({"success": False, "message": "🚨 拒绝恶意的残局注入"}), 401

    global sim_thread
    data = request.get_json() or {}
    
    # 1. 停止当前可能正在运行的 5002 推演
    stop_event.set()
    if sim_thread and sim_thread.is_alive():
        sim_thread.join(timeout=1.5)
    stop_event.clear()
    
    with sim_lock:
        # 2. 重置为默认状态，然后注入 5000 的残局数据
        sim_state.clear()
        sim_state.update(copy.deepcopy(DEFAULT_STATE))
        
        # 注入核心资源数据 (从 5000 搬运过来的家底)
        # 💡 修复：循环遍历接收所有核心物理法则上下文，防止影子引擎“失忆”
        # 💡 修复：将基准线变量也加入同步名单，彻底防止风暴快照导致基准线永久偏移
        core_keys = [
            "missionTime", "missionDay", "crewCount", "oxygen", "food", 
            "water", "energy", "radiation", "temperature", "health", 
            "stability", "survivalPrediction", "aiMode", "solarStormProbability", 
            "solarStormActive", "equipmentEfficiency", "activityFactor", "emergencyMode",
            "initRadiation", "initTemperature"
        ]
        for k in core_keys:
            if k in data:
                sim_state[k] = data[k]
        
        # (删除了原来那两行错误的覆盖赋值)
        
        # 3. 初始化历史记录，让图表从当前残局时刻开始画起（无缝衔接）
        sim_state["history"] = [{
            "tick": sim_state["missionTime"],
            "day": sim_state["missionDay"],
            "hour": sim_state["missionTime"] % 24,
            "oxygen": sim_state["oxygen"], "food": sim_state["food"],
            "water": sim_state["water"], "energy": sim_state["energy"],
            "health": sim_state["health"], "stability": sim_state["stability"],
            "survivalPrediction": sim_state["survivalPrediction"]
        }]
        
    return jsonify({"success": True, "message": "快照注入成功，影子引擎已就绪"})
@app.route('/api/dash/reset', methods=['POST'])
def api_reset():
    stop_event.set()
    if sim_thread and sim_thread.is_alive():
        sim_thread.join(timeout=1.5) # 等待线程死亡
    stop_event.clear()               # 重置信号，允许下次启动
    with sim_lock:
        sim_state.clear()
        sim_state.update(copy.deepcopy(DEFAULT_STATE))
    return jsonify({"success": True})
def sim_loop():
    while not stop_event.is_set():
        simulation_tick()
        stop_event.wait(tick_interval) # 完美替代 sleep，收到停止信號可瞬間打斷
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=False, use_reloader=False)