"""Vercel 单一入口：把 sim / space / dash 三个子服务的路由合并到一个 Flask 应用。

三个子服务的路由前缀互不重叠（/api/sim、/api/space、/api/dash），
直接复用各自 Flask app 上已注册的路由规则，合并进同一个应用。

本地开发不受影响：
    python api/sim.py     -> 127.0.0.1:5000
    python api/space.py   -> 127.0.0.1:5001
    python api/dash.py    -> 127.0.0.1:5002
线上（Vercel）则由本文件作为唯一入口托管全部 /api/* 路由。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, send_from_directory, abort
from flask_cors import CORS

import dash
import sim
import space

app = Flask(__name__)
CORS(app)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ("index.html", "simulation.html", "space.html", "dashboard.html")


@app.route("/")
def serve_index():
    return send_from_directory(ROOT, "index.html")


@app.route("/<page>")
def serve_page(page):
    if page in PAGES:
        return send_from_directory(ROOT, page)
    abort(404)


def _merge_routes(prefix, module):
    sub = module.app
    for rule in sub.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        app.add_url_rule(
            rule.rule,
            endpoint=f"{prefix}_{rule.endpoint}",
            view_func=sub.view_functions[rule.endpoint],
            methods=[m for m in rule.methods if m not in ("HEAD", "OPTIONS")],
        )


_merge_routes("sim", sim)
_merge_routes("space", space)
_merge_routes("dash", dash)
