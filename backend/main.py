"""电商风险控制系统 - FastAPI 应用入口。

本地启动（项目根目录）：
    .venv\\Scripts\\python.exe -m uvicorn main:app --app-dir backend --port 8005
或直接双击根目录 start.bat。接口文档：http://127.0.0.1:8005/docs
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import blacklists  # noqa: E402
import cases  # noqa: E402
import decision  # noqa: E402
import profile  # noqa: E402
import rules  # noqa: E402
import stats  # noqa: E402
from config import (BLACKLIST_TYPE_LABELS, BLACKLIST_TYPES, CASE_STATUS_LABELS, CASE_STATUSES,
                    DECISION_LABELS, DECISIONS, EVENT_TYPES, EVENT_TYPE_LABELS, FRONTEND_DIST,
                    LEVEL_HIGH_THRESHOLD, LEVEL_MEDIUM_THRESHOLD, RISK_LEVEL_LABELS, RISK_LEVELS,
                    SCORE_CAP)  # noqa: E402
from features import DIMENSION_LABELS, feature_definitions  # noqa: E402
from rules import OPERATORS, OPERATOR_LABELS  # noqa: E402

app = FastAPI(
    title="电商风险控制系统 star-tradeGuard",
    description="覆盖风险识别、规则判断、人工复核、处置留痕与结果查询的实时风控平台",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (decision, rules, cases, blacklists, profile, stats):
    app.include_router(module.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """统一未捕获异常返回，避免前端拿到 HTML 错误页。"""
    return JSONResponse(status_code=500, content={"detail": f"服务内部错误：{exc}"})


@app.get("/api/risk/meta", tags=["基础数据"], summary="查询枚举字典与特征定义")
def meta():
    """前端初始化用：事件类型、风险等级、处理建议、案件状态、黑名单类型、25 个特征定义。"""
    return {
        "event_types": [{"value": t, "label": EVENT_TYPE_LABELS[t]} for t in EVENT_TYPES],
        "risk_levels": [{"value": l, "label": RISK_LEVEL_LABELS[l]} for l in RISK_LEVELS],
        "decisions": [{"value": d, "label": DECISION_LABELS[d]} for d in DECISIONS],
        "case_statuses": [{"value": s, "label": CASE_STATUS_LABELS[s]} for s in CASE_STATUSES],
        "blacklist_types": [{"value": b, "label": BLACKLIST_TYPE_LABELS[b]} for b in BLACKLIST_TYPES],
        "operators": [{"value": o, "label": OPERATOR_LABELS[o]} for o in OPERATORS],
        "features": feature_definitions(),
        "dimensions": [{"value": k, "label": v} for k, v in DIMENSION_LABELS.items()],
        "score_model": {
            "score_cap": SCORE_CAP,
            "high_threshold": LEVEL_HIGH_THRESHOLD,
            "medium_threshold": LEVEL_MEDIUM_THRESHOLD,
        },
        "roles": [
            {"value": "reviewer", "label": "风控审核员", "desc": "查看风险结果、审核案件、填写处理结论"},
            {"value": "admin", "label": "风控管理员", "desc": "维护规则、维护黑名单、查看统计看板"},
            {"value": "viewer", "label": "数据查看人", "desc": "查看用户画像、历史风险记录、命中统计"},
        ],
    }


@app.get("/api/health", tags=["基础数据"], summary="健康检查")
def health():
    return {"status": "ok", "service": "star-tradeGuard"}


# ---------- 前端静态资源（frontend/dist 构建产物，运行时无需 Node） ----------
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """SPA 前端路由回退：非 /api 路径统一返回 index.html。"""
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "接口不存在"})
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def index_placeholder():
        return {
            "message": "前端尚未构建，请先执行：cd frontend && npm install && npm run build",
            "api_docs": "/docs",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8005)
