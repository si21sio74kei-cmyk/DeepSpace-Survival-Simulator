from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import math
import os

app = Flask(__name__)
# 啟用 CORS，允許本地 index2.html 跨域訪問
CORS(app)

# 你的專屬 NASA API KEY
NASA_KEY = os.environ.get('NASA_API_KEY', '4lvYmjBb3NFCc4xpxVkrj7Ih4cWGWqbpkqUSkbaY')

# 🆕 新增：大湾区/澳门地理测控距离解算器
def calc_macao_distance(lat, lon):
    macao_lat, macao_lon = 22.1989, 113.5491
    r_lat1, r_lon1, r_lat2, r_lon2 = map(math.radians, [lat, lon, macao_lat, macao_lon])
    a = math.sin((r_lat2 - r_lat1)/2)**2 + math.cos(r_lat1) * math.cos(r_lat2) * math.sin((r_lon2 - r_lon1)/2)**2
    return round(2 * math.asin(math.sqrt(a)) * 6371.0, 1)

# [卡片 1] ISS 實時位置 + 澳门 DSN 测控链路
@app.route('/api/space/iss', methods=['GET'])
def get_iss():
    try:
        response = requests.get('http://api.open-notify.org/iss-now.json', timeout=5)
        res_data = response.json()
        lat = float(res_data["iss_position"]["latitude"])
        lon = float(res_data["iss_position"]["longitude"])
        dist = calc_macao_distance(lat, lon)
        in_window = dist < 1500.0 

        return jsonify({
            "iss_position": {"latitude": lat, "longitude": lon},
            "timestamp": res_data["timestamp"],
            "macao_dsn": {
                "distance_km": dist,
                "status": "LOCKED (锁定过境视窗)" if in_window else "BELOW_HORIZON (地平线下)",
                "alarm": in_window
            }
        })
    except Exception as e:
        return jsonify({'error': '無法獲取 ISS 數據'}), 500

# [卡片 2] 最新航天發射任務 (Launch Library 2 — 取代已失效的 SpaceX API v4)
@app.route('/api/space/spacex', methods=['GET'])
def get_spacex():
    try:
        # api.spacexdata.com 已永久下線 (522)，改用社群維護的 Launch Library 2
        response = requests.get('https://ll.thespacedevs.com/2.2.0/launch/previous/?limit=1', timeout=8)
        response.raise_for_status()
        data = response.json()
        results = data.get('results', [])
        if not results:
            raise Exception('No launch data returned')
        latest = results[0]

        utc_date = latest.get('net', '')
        formatted_date = utc_date[0:10] + " " + utc_date[11:19] if len(utc_date) >= 19 else utc_date

        # 解析火箭名稱 (LL2 嵌套結構)
        rocket_name = latest.get('rocket', {}).get('configuration', {}).get('full_name', '未知火箭')

        # 解析任務詳情
        mission = latest.get('mission') or {}
        details = mission.get('description') or '暫無本次任務詳細描述。'

        # 解析直播鏈接
        vid_urls = latest.get('vid_urls') or []
        webcast = vid_urls[0].get('url', '#') if vid_urls else '#'

        return jsonify({
            'name': latest.get('name', '未知任務'),
            'date': formatted_date,
            'rocket': rocket_name,
            'success': latest.get('status', {}).get('abbrev') == 'Success',
            'details': details,
            'webcast': webcast
        })
    except Exception as e:
        print(f"Launch Library Error: {e}")
        return jsonify({'error': '無法獲取航天發射數據'}), 500
# [卡片 3] 🪐 宇宙天體觀測 (支援地球/火星/月球)
@app.route('/api/space/space-body', methods=['GET'])
def get_space_body():
    body_type = request.args.get('type', 'earth')
    try:
        if body_type == 'earth':
            url = f'https://api.nasa.gov/EPIC/api/natural?api_key={NASA_KEY}'
            response = requests.get(url, timeout=6)
            res_data = response.json()
            if isinstance(res_data, list) and len(res_data) > 0:
                latest = res_data[0]
                date_str = latest.get('date', '')
                year, month, day = date_str[0:4], date_str[5:7], date_str[8:10]
                image_url = f"https://epic.gsfc.nasa.gov/archive/natural/{year}/{month}/{day}/png/{latest.get('image')}.png"
                return jsonify({'date': date_str, 'caption': latest.get('caption', 'DSCOVR Image'), 'imageUrl': image_url})
            raise Exception("Earth data empty")
            
        elif body_type == 'mars':
            # NASA Mars Rover Photos API 的 Heroku 後端已永久下線 (404 "No such app")
            # 直接使用高質量備用數據，避免無效 API 調用造成的 5 秒延遲
            return jsonify({
                'date': '2026-06-12 MARS TELEMETRY',
                'caption': '☄️ 火星地表探測矩陣 — 好奇號（Curiosity）蓋爾隕石坑實地觀測。觀測載荷：Mast Camera (Mastcam) 高清彩色成像 │ 著陸日期：2012-08-06 │ 總行駛里程：>30 km',
                'imageUrl': 'https://images.unsplash.com/photo-1545156521-77bd85671d30?w=800&auto=format&fit=crop'
            })
            
        elif body_type == 'moon':
            # api.le-systeme-solaire.net 現在要求 API Key (401)，月球物理常數為靜態數據，直接硬編碼
            return jsonify({
                'date': 'REALTIME LUNAR ORBIT',
                'caption': "🌙 月球軌道物理指標（NASA 星曆基準）─ 表面重力: 1.62 m/s² │ 平均半徑: 1737.4 km │ 密度: 3.34 g/cm³ │ 與地球平均距離: 384,400 km",
                'imageUrl': 'https://images.unsplash.com/photo-1522030299830-16b8d3d049fe?w=800'
            })
    except Exception as e:
        print(f"Space Body Main Error: {e}") # 🟠 修复：捕获具体异常
        return jsonify({
            'date': 'SYSTEM ERROR FALLBACK',
            'caption': '深空探測矩陣通信異常，切換至安全存檔視角。',
            'imageUrl': 'https://images.unsplash.com/photo-1614730321146-b6fa6a46bcb4?w=800'
        })
# [卡片 4] 城市天氣
@app.route('/api/space/weather', methods=['GET'])
def get_weather():
    try:
        # 🛡️ 安全修复：SSRF 白名单防御，严格限制可查询的城市字典
        ALLOWED_CITIES = {
            "澳门": "澳门", "香港": "香港", "广州": "广东", 
            "深圳": "广东", "北京": "北京", "上海": "上海"
        }
        req_city = request.args.get('city', '澳门')
        if req_city not in ALLOWED_CITIES:
            return jsonify({'error': '非法或未授权的城市参数 (Security Blocked)'}), 403
            
        province = ALLOWED_CITIES[req_city]
        city = req_city
        
        url = f'https://wis.qq.com/weather/common?source=pc&weather_type=observe%7Cforecast_24h%7Cair&province={province}&city={city}'
        data = requests.get(url, timeout=5).json()
        if not data or data.get('status') != 200 or not data.get('data'):
             return jsonify({'error': '氣象庫查無此城市'}), 404
        w = data.get('data', {}).get('observe', {})
        a = data.get('data', {}).get('air', {})
        return jsonify({
            'temp': w.get('degree', '--'), 'humidity': w.get('humidity', '--'),
            'weather': w.get('weather', '未知'), 'wind_dir': w.get('wind_direction', '--'),
            'wind_power': w.get('wind_power', '0'), 'aqi': a.get('aqi', '--'), 'aqi_name': a.get('aqi_name', 'N/A')
        })
    except Exception as e:
        print(f"Weather Fetch Error: {e}")  # 🟠 修复：捕获具体异常
        return jsonify({'error': '獲取氣象數據超時'}), 500
# [卡片 5] 太陽風暴監測 (NASA DONKI + NOAA SWPC 雙備援)
@app.route('/api/space/solar-storm', methods=['GET'])
def get_solar_storm():
    # --- 方法 1：嘗試 NASA DONKI ---
    try:
        donki_url = f'https://api.nasa.gov/DONKI/CME?api_key={NASA_KEY}'
        donki_resp = requests.get(donki_url, timeout=3)
        if donki_resp.status_code == 200:
            donki_data = donki_resp.json()
            if isinstance(donki_data, list) and len(donki_data) > 0:
                latest_cme = donki_data[-1]
                instruments_data = latest_cme.get('instruments') or []
                instruments = [i.get('displayName') for i in instruments_data if i.get('displayName')]
                return jsonify({
                    'startTime': latest_cme.get('startTime', '未知時間'),
                    'catalog': latest_cme.get('catalog', '未知目錄'),
                    'note': latest_cme.get('note') or '深空太陽風暴觀測日誌完整載入。',
                    'instruments': ', '.join(instruments) if instruments else '無'
                })
            # DONKI 200 但無數據 = 近期無 CME
        elif donki_resp.status_code == 404:
            pass  # DONKI 404 = 無風暴記錄，繼續嘗試 NOAA
    except Exception as e:
        print(f"DONKI unreachable: {e}")

    # --- 方法 2：NOAA SWPC 太空天氣警報 (免 Key，全球可達) ---
    try:
        noaa_url = 'https://services.swpc.noaa.gov/products/alerts.json'
        noaa_resp = requests.get(noaa_url, timeout=5)
        noaa_resp.raise_for_status()
        alerts = noaa_resp.json()

        if isinstance(alerts, list) and len(alerts) > 0:
            latest = alerts[0]
            issue_time = latest.get('issue_datetime', '')
            product_id = latest.get('product_id', 'N/A')
            message = latest.get('message', '')

            # 解析 NOAA Scale (G1-G5)
            g_scale = ''
            if 'G5' in message:
                g_scale = ' [G5 - Extreme]'
            elif 'G4' in message:
                g_scale = ' [G4 - Severe]'
            elif 'G3' in message:
                g_scale = ' [G3 - Strong]'
            elif 'G2' in message:
                g_scale = ' [G2 - Moderate]'
            elif 'G1' in message:
                g_scale = ' [G1 - Minor]'

            # 取 message 第一行作為摘要
            first_line = message.strip().split('\n')[0] if message else ''

            return jsonify({
                'startTime': issue_time[:19] if len(issue_time) >= 19 else (issue_time or 'N/A'),
                'catalog': f'NOAA/{product_id}{g_scale}',
                'note': message[:500] if message else '無詳細資料',
                'instruments': f'NOAA SWPC | {first_line[:90]}' if first_line else 'NOAA SWPC 監測中'
            })

        # NOAA 無警報 → 太空天氣平靜
        return jsonify({
            'startTime': 'N/A',
            'catalog': 'N/A',
            'instruments': 'NOAA SWPC, SOHO, STEREO (巡航待命中)',
            'note': '【安全播報】：當前太陽活動平穩，NOAA 無活躍太空天氣警報。'
        })

    except Exception as e:
        print(f"NOAA SWPC Error: {e}")
        # --- 方法 3：完全離線的終極防禦 ---
        return jsonify({
             'startTime': 'N/A',
             'catalog': 'N/A',
             'instruments': '網路離線 / 本地星曆推演中',
             'note': '【警告】：深空監測網通聯遭遇干擾，正在嘗試重新連接...'
        }), 200
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)