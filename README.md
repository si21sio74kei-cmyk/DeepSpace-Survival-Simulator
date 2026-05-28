# DeepSpace-Survival-Simulator
# 🌌 DeepSpace Survival Simulator (深空生存模擬器)

![Version](https://img.shields.io/badge/version-5.0-blue.svg)
![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Deployment](https://img.shields.io/badge/deployment-Vercel-black.svg)

> **「在極限的深空環境中，讓 AI 接管生存的每一秒。」**

**DeepSpace Survival Simulator** 是一個基於前後端分離架構（Frontend-Backend Separation）與微服務概念打造的深空生存預測與觀測系統。專案結合了基礎物理資源解算、多策略 AI 演算法控制，以及真實宇宙數據遙測（NASA / SpaceX API），提供極致沉浸的科幻級 UI 控制大屏。

---

## ✨ 核心亮點 (Features)

- 🧠 **AI 驅動的生存預測引擎**：支援 8 種不同的 AI 管控策略（如：緊急生存、極限節能、動態適應等），即時解算氧氣、食物、水、能源與健康度的消耗耦合。
- 🌍 **真實宇宙數據遙測**：對接 NASA 官方 API 與 SpaceX 數據庫，實時獲取 ISS 國際空間站軌道、太陽風暴（CME）警報、真實星體影像與區域大氣數據。
- 🚀 **雲端與本地雙棲架構**：前端具備「智能網址自適應判定」，在本地執行時自動連接 `127.0.0.1`，部署至 Vercel 後自動無縫切換為 Serverless 雲端路由。
- 🎨 **極致的機械美學 UI**：使用 `TailwindCSS` 構建底層，結合 `Anime.js` 實現標誌性的幾何網格呼吸陣列與 HUD 裝甲懸浮特效。

---

## 🏗️ 系統架構 (Architecture)

本專案採用 **Python (Flask) + HTML/JS** 構建，並針對 **Vercel Serverless Functions** 進行了深度優化。

```text
DeepSpace-Survival-Simulator/
│
├── frontend/                     # 🌐 前端靜態資源 (CDN 加速)
│   ├── index.html                # 主網關大屏 (動畫與導航中心)
│   ├── simulation.html           # 模塊 A：仿真實驗室
│   ├── dashboard.html            # 模塊 B：生存總控制台 (共用仿真大腦)
│   └── space.html                # 模塊 C：真實宇宙遙測中心
│
├── backend/                      # ⚙️ 後端微服務 (Vercel Serverless)
│   ├── Simulation_System.py      # 核心仿真引擎 (處理生存公式與 AI 邏輯)
│   ├── Space_Data_Center.py      # 外網數據中心 (對接 NASA 等外部 API)
│   └── Mission_Dashboard.py      # 獨立預測引擎 (備用)
│
├── vercel.json                   # 🔀 Vercel 雲端動態路由設定檔
├── requirements.txt              # 📦 Python 依賴清單
└── README.md
