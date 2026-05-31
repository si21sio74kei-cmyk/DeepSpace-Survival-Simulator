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
    "solarStormActive": False, "equipmentEfficiency": 1.0, "activityFactor": 1.0,
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
        if not s["running"] or s["paused"]: return
        
        mode = AI_MODES.get(s["aiMode"], AI_MODES["Normal"]).copy()
        hour = s["missionTime"] % 24
        days_elapsed = s["missionTime"] / 24.0
        new_events = []
        
        # 🆕 帕累托多目標自適應算法注入 (僅在 Dynamic AI 模式下激活)
        if s["aiMode"] == "Dynamic AI":
            w_o2 = 12.0 if s["oxygen"] < 35.0 else 1.0
            w_en = 10.0 if s["energy"] < 30.0 else 1.0
            w_rad = 6.0 if s["radiation"] > 60.0 else 0.5

            base_act = 0.85 - (w_o2 * 0.04) - (s["radiation"] * 0.002)
            base_es  = 0.20 + (w_en * 0.05) + (s["radiation"] * 0.003)

            mode["activity"] = max(0.35, min(1.20, base_act))
            mode["energy_save"] = max(-0.10, min(0.60, base_es))

        # 1. 晝夜節律
        if 6 <= hour <= 22:
            activity = mode["activity"]
            phase = "DAY"
        else:
            activity = mode["activity"] * 0.40
            phase = "NIGHT"
        s["activityFactor"] = round(activity, 3)

        # 🆕 新增：舱内温度微小动态波动（白噪声 + 昼夜温差模拟）
        base_t = s.get("initTemperature", 22.0)
        target_t = base_t + (0.6 if phase == "DAY" else -0.4) # 白天略热，夜晚略冷
        # 向目标温度平滑逼近，并加入微小随机白噪声扰动 (±0.15度)
        s["temperature"] = round(s["temperature"] + (target_t - s["temperature"]) * 0.15 + random.uniform(-0.15, 0.15), 2)

        # 2. 設備老化
        equip_eff = max(0.50, 1.0 - (days_elapsed / 365.0) * 0.20)
        s["equipmentEfficiency"] = round(equip_eff, 3)

        # 3. 完整克隆原版隨機深空事件系統（流星撞擊、漏氧、風暴等）
        fail_mult = 2.0 - equip_eff
        if s["solarStormActive"]:
            s["radiation"] = min(100.0, s["radiation"] + 0.80)
            if random.random() < 0.06:
                s["solarStormActive"] = False
                new_events.append(("SOLAR_STORM_END", "☀ 太陽風暴已平息 — 宇宙輻射背景恢復正常"))
        elif random.random() < (s["solarStormProbability"] / 100.0) / 24.0:
            s["solarStormActive"] = True
            spike = random.uniform(15.0, 28.0)
            s["radiation"] = min(100.0, s["radiation"] + spike)
            new_events.append(("SOLAR_STORM", f"⚡ 警告：遭遇太陽風暴高能粒子襲擊！輻射突增 +{spike:.1f} mSv"))

        if random.random() < 0.004 * fail_mult:
            leak = round(random.uniform(3.0, 9.0), 1)
            s["oxygen"] = max(0.0, s["oxygen"] - leak)
            new_events.append(("OXYGEN_LEAK", f"💨 氣閘艙發生輕微洩漏！氧氣儲量下降 −{leak}%"))

        if random.random() < 0.003 * fail_mult:
            loss = round(random.uniform(2.0, 7.0), 1)
            s["food"] = max(0.0, s["food"] - loss)
            new_events.append(("COLDCHAIN_FAIL", f"🧊 生物冷凍庫溫控波動！部分食物變質 −{loss}%"))

        if random.random() < 0.003 * fail_mult:
            loss = round(random.uniform(5.0, 12.0), 1)
            s["energy"] = max(0.0, s["energy"] - loss)
            new_events.append(("ENERGY_FAIL", f"🔌 主配電網發生高壓電弧跳閘！能源損耗 −{loss}%"))

        # 4. 資源生命支持生命線耦合計算
        rad_factor = 1.0 + (s["radiation"] / 100.0) * 0.30
        o2_con = s["crewCount"] * activity * rad_factor * 0.03
        
        regen_eff = mode["regen_boost"] * equip_eff
        o2_regen, water_for_elec = 0.0, 0.0
        if s["energy"] > 50.0:
            elec_rate = 0.50 * regen_eff * (1.0 - mode["energy_save"] * 0.5)
            o2_regen, water_for_elec = elec_rate * 0.015, elec_rate * 0.008
        elif s["energy"] > 20.0:
            frac = (s["energy"] - 20.0) / 30.0
            o2_regen, water_for_elec = 0.015 * frac * regen_eff, 0.004 * frac

        s["oxygen"] = max(0.0, min(100.0, s["oxygen"] - o2_con + o2_regen))

        health_factor = 1.0 if s["health"] >= 50.0 else (s["health"] / 50.0)
        f_con = s["crewCount"] * activity * mode["ration"] * 0.02 * health_factor
        s["food"] = max(0.0, s["food"] - f_con)

        w_con = s["crewCount"] * activity * 0.025
        w_rec = s["crewCount"] * 0.008 * equip_eff
        net_w = w_con - w_rec + water_for_elec
        s["water"] = max(0.0, min(100.0, s["water"] - net_w))

        sys_load = 1.0 - mode["energy_save"]
        tmp_ctrl = abs(s["temperature"] - 22.0) * 0.02
        e_con = sys_load * 0.05 + s["radiation"] * 0.01 + tmp_ctrl * 0.03
        if s["radiation"] > 60.0: e_con *= 1.0 + (s["radiation"] - 60.0) / 100.0
        
        solar_out = 0.0
        if not s["solarStormActive"] and 8 <= hour <= 18:
            solar_out = 0.08 * math.sin(math.pi * (hour - 8) / 10.0) * equip_eff
        s["energy"] = max(0.0, min(100.0, s["energy"] - e_con + solar_out))

        shield_eff = 0.50 * equip_eff * (1.5 if mode["shield_priority"] else 1.0)
        rad_dmg = s["radiation"] * 0.001
        if s["energy"] > 30.0: rad_dmg *= shield_eff
        s["health"] = max(0.0, min(100.0, s["health"] - rad_dmg))
        if s["food"] < 20.0: s["health"] = max(0.0, s["health"] - 0.10)
        if s["oxygen"] < 30.0: s["health"] = max(0.0, s["health"] - 0.30)
        if s["water"] < 20.0: s["health"] = max(0.0, s["health"] - 0.15)
        
        # 🔴 修复：指数级衰减模型 + 宇宙射线背景微扰
        if not s["solarStormActive"]:
            # 如果辐射值明显高于基准值，处于风暴后的清洗衰减期
            if s["radiation"] > s["initRadiation"] + 0.5:
                decay_rate = 0.85 if s["energy"] > 20.0 else 0.95
                excess_rad = s["radiation"] - s["initRadiation"]
                s["radiation"] = round((excess_rad * decay_rate) + s["initRadiation"], 2)
            else:
                # 处于平静期：在基准值附近产生真实的物理宇宙微小白噪声波动 (-0.1 到 +0.25)
                s["radiation"] = round(s["initRadiation"] + random.uniform(-0.1, 0.25), 2)

        # 5. AI 自動化調度干預
        emergency = False
        if s["energy"] < 40.0:
            boost = round(1.5 * mode["energy_save"], 3)
            if boost > 0:
                s["energy"] = min(100.0, s["energy"] + boost)
                new_events.append(("AI_DISPATCH", f"🤖 能源危急：AI自動關閉非核心載荷，回收功率 +{boost:.2f}%"))
            if s["energy"] < 15.0: emergency = True
        if s["oxygen"] < 30.0:
            s["activityFactor"] = round(activity * 0.70, 3)
            new_events.append(("AI_DISPATCH", "🤖 氧氣濃度過低：AI強制全體成員進入低代謝靜息狀態"))
        if s["radiation"] > 70.0: emergency = True
        s["emergencyMode"] = emergency

        # 基地穩定度解算
        rad_risk = (s["radiation"] / 100.0) * 20.0
        s["stability"] = max(0.0, min(100.0, round((s["oxygen"] + s["food"] + s["water"] + s["energy"] + s["health"]) / 5.0 - rad_risk, 2)))

        # ================================================================
        # 6. 生存預測核心演算法（★ 在此處原生修正，不干涉 app.py）
        # ================================================================
        EPS = 1e-4
        o2_net = max(EPS, o2_con - o2_regen)
        f_net = max(EPS, f_con)
        w_net = max(EPS, net_w)
        e_net = max(EPS, e_con - solar_out)
        
        o_h = s["oxygen"] / o2_net
        f_h = s["food"] / f_net
        w_h = s["water"] / w_net
        e_h = s["energy"] / e_net
        
        # 雙階段耦合修正：獨立計算並取最小值，防止相互覆蓋
        o_h_final = o_h
        
        # 💡 修复：对齐断电极限降级代谢率
        emergency_o2_con = s["crewCount"] * 0.40 * 0.03
        
        # 修正 1：能源耗盡 → 再生停止 → 氧氣全速下墜
        if e_h < o_h and s["energy"] > 0.0:
            o2_at_energy_zero = s["oxygen"] - o2_net * e_h
            o_h_final = min(o_h_final, e_h + max(0.0, o2_at_energy_zero / max(EPS, emergency_o2_con)))

        # 修正 2：水資源耗盡 → 再生停止 → 氧氣全速下墜
        if w_h < o_h and s["water"] > 0.0:
            o2_after_water = s["oxygen"] - o2_net * w_h
            o_h_final = min(o_h_final, w_h + max(0.0, o2_after_water / max(EPS, emergency_o2_con)))
            
        o_h = o_h_final
            
        s["survivalPrediction"] = max(0.0, round(min(o_h, f_h, w_h, e_h) / 24.0, 1))

        # 時間推進與日誌收錄
        s["missionTime"] += 1
        s["missionDay"] = s["missionTime"] // 24

        for etype, desc in new_events:
            if len(s["events"]) > 200:
                s["events"] = s["events"][-200:]
            s["events"].append({"tick": s["missionTime"], "type": etype, "description": desc})

        s["history"].append({
            "tick": s["missionTime"], "day": s["missionDay"], "hour": hour,
            "oxygen": round(s["oxygen"], 2), "food": round(s["food"], 2),
            "water": round(s["water"], 2), "energy": round(s["energy"], 2),
            "health": round(s["health"], 2), "stability": round(s["stability"], 2),
            "survivalPrediction": s["survivalPrediction"]
        })
        if len(s["history"]) > 500: s["history"] = s["history"][-500:]

        # 失敗判定
        if s["oxygen"] <= 0 or s["health"] <= 0 or s["food"] <= 0 or s["water"] <= 0:
            s["running"] = False
            s["events"].append({"tick": s["missionTime"], "type": "FAILED", "description": "💀 警告：維生核心已完全破裂，模擬終止。"})

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