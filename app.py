from __future__ import annotations

import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse


app = FastAPI(title="Weibo OAuth Callback Demo")


WEIBO_CLIENT_ID = os.getenv("WEIBO_CLIENT_ID", "").strip()
WEIBO_CLIENT_SECRET = os.getenv("WEIBO_CLIENT_SECRET", "").strip()
WEIBO_REDIRECT_URI = os.getenv("WEIBO_REDIRECT_URI", "").strip()

WEIBO_AUTHORIZE_URL = "https://api.weibo.com/oauth2/authorize"
WEIBO_ACCESS_TOKEN_URL = "https://api.weibo.com/oauth2/access_token"
WEIBO_USER_INFO_URL = "https://api.weibo.com/2/users/show.json"

LATEST_AUTH: dict[str, Any] = {}


def html_page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>{title}</title>
          <style>
            body {{
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
              max-width: 960px;
              margin: 48px auto;
              padding: 0 20px;
              line-height: 1.7;
              color: #111827;
            }}
            .card {{
              border: 1px solid #e5e7eb;
              border-radius: 16px;
              padding: 28px;
              box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
            }}
            .btn {{
              display: inline-block;
              padding: 10px 16px;
              border-radius: 10px;
              background: #2563eb;
              color: white !important;
              text-decoration: none;
              margin-right: 12px;
              margin-bottom: 12px;
            }}
            .btn.secondary {{
              background: #4b5563;
            }}
            code, pre {{
              background: #f3f4f6;
              border-radius: 8px;
            }}
            code {{
              padding: 2px 6px;
            }}
            pre {{
              padding: 14px;
              overflow-x: auto;
              white-space: pre-wrap;
              word-break: break-word;
            }}
            .muted {{
              color: #6b7280;
            }}
            .ok {{
              color: #047857;
              font-weight: 600;
            }}
            .warn {{
              color: #b45309;
              font-weight: 600;
            }}
            .danger {{
              color: #b91c1c;
              font-weight: 600;
            }}
            ul {{
              padding-left: 20px;
            }}
            hr {{
              border: none;
              border-top: 1px solid #e5e7eb;
              margin: 24px 0;
            }}
          </style>
        </head>
        <body>
          <div class="card">
            {body}
          </div>
        </body>
        </html>
        """
    )


def mask_token(token: str | None) -> str:
    if not token:
        return ""
    if len(token) <= 12:
        return "*" * len(token)
    return f"{token[:6]}...{token[-4:]}"


def build_authorize_url() -> str:
    if not WEIBO_CLIENT_ID or not WEIBO_REDIRECT_URI:
        return "#"

    params = {
        "client_id": WEIBO_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": WEIBO_REDIRECT_URI,
    }
    return str(httpx.URL(WEIBO_AUTHORIZE_URL, params=params))


def ensure_env_ready() -> None:
    missing = []
    if not WEIBO_CLIENT_ID:
        missing.append("WEIBO_CLIENT_ID")
    if not WEIBO_CLIENT_SECRET:
        missing.append("WEIBO_CLIENT_SECRET")
    if not WEIBO_REDIRECT_URI:
        missing.append("WEIBO_REDIRECT_URI")

    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variables: {', '.join(missing)}",
        )


@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
    auth_url = build_authorize_url()
    env_ok = all([WEIBO_CLIENT_ID, WEIBO_CLIENT_SECRET, WEIBO_REDIRECT_URI])

    last_uid = LATEST_AUTH.get("uid", "")
    last_token = mask_token(LATEST_AUTH.get("access_token"))

    body = f"""
    <h1>微博授权测试页</h1>

    <p>当前服务端读取到的回调地址：</p>
    <p><code>{WEIBO_REDIRECT_URI or "未配置"}</code></p>

    <p>当前服务端生成的实际授权链接：</p>
    <pre>{auth_url}</pre>

    <p class="{"ok" if env_ok else "warn"}">
      {"环境变量已配置，可以发起授权。" if env_ok else "环境变量未配完整，请先配置 Vercel 环境变量。"}
    </p>

    <p>
      <a class="btn" href="{auth_url}">发起微博授权</a>
      <a class="btn secondary" href="/success">查看成功页</a>
      <a class="btn secondary" href="/weibo/me">查看当前授权用户信息</a>
      <a class="btn secondary" href="/health">查看健康检查</a>
    </p>

    <hr />

    <h2>最近一次授权状态</h2>
    <ul>
      <li>uid：<code>{last_uid or "暂无"}</code></li>
      <li>access_token：<code>{last_token or "暂无"}</code></li>
    </ul>

    <p class="muted">
      调试 redirect_uri_mismatch 时，先核对上面这两项：
      “当前服务端读取到的回调地址”和“当前服务端生成的实际授权链接”。
    </p>
    """
    return html_page("Weibo OAuth Demo", body)


@app.get("/weibo/callback")
async def weibo_callback(
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_code: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    if error:
        body = f"""
        <h1>微博授权失败</h1>
        <p><strong>error：</strong><code>{error}</code></p>
        <p><strong>error_code：</strong><code>{error_code or "无"}</code></p>
        <p><strong>error_description：</strong><code>{error_description or "无"}</code></p>
        <p><a class="btn" href="/">返回首页</a></p>
        """
        return html_page("授权失败", body)

    if not code:
        body = """
        <h1>未收到授权 code</h1>
        <p>请从首页重新发起授权，不要直接打开 callback 地址。</p>
        <p><a class="btn" href="/">返回首页</a></p>
        """
        return html_page("未收到 code", body)

    ensure_env_ready()

    print("TOKEN EXCHANGE CODE:", code)
    print("TOKEN EXCHANGE REDIRECT_URI:", WEIBO_REDIRECT_URI)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                WEIBO_ACCESS_TOKEN_URL,
                data={
                    "client_id": WEIBO_CLIENT_ID,
                    "client_secret": WEIBO_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "redirect_uri": WEIBO_REDIRECT_URI,
                    "code": code,
                },
            )
    except Exception as exc:
        body = f"""
        <h1>换取 token 失败</h1>
        <pre>{str(exc)}</pre>
        <p><a class="btn" href="/">返回首页</a></p>
        """
        return html_page("换 token 失败", body)

    if response.status_code != 200:
        print(
            "WEIBO TOKEN ERROR:",
            {
                "redirect_uri_used": WEIBO_REDIRECT_URI,
                "status_code": response.status_code,
                "response_text": response.text,
            },
        )
        body = f"""
        <h1>微博返回异常</h1>
        <p class="danger">HTTP 状态码：<code>{response.status_code}</code></p>
        <p>本次服务端用于换 token 的 redirect_uri：</p>
        <pre>{WEIBO_REDIRECT_URI}</pre>
        <p>微博返回内容：</p>
        <pre>{response.text}</pre>
        <p><a class="btn" href="/">返回首页</a></p>
        """
        return html_page("微博返回异常", body)

    try:
        token_data = response.json()
    except json.JSONDecodeError:
        body = f"""
        <h1>微博返回内容不是 JSON</h1>
        <pre>{response.text}</pre>
        <p><a class="btn" href="/">返回首页</a></p>
        """
        return html_page("返回解析失败", body)

    access_token = token_data.get("access_token", "")
    uid = token_data.get("uid", "")
    expires_in = token_data.get("expires_in", "")
    remind_in = token_data.get("remind_in", "")

    LATEST_AUTH.clear()
    LATEST_AUTH.update(
        {
            "uid": uid,
            "access_token": access_token,
            "expires_in": expires_in,
            "remind_in": remind_in,
            "raw_token_data": token_data,
        }
    )

    print("WEIBO TOKEN RESULT:", token_data)

    return RedirectResponse(url="/success", status_code=302)


@app.get("/success", response_class=HTMLResponse)
async def success() -> HTMLResponse:
    if not LATEST_AUTH:
        body = """
        <h1>暂无授权结果</h1>
        <p>请先从首页发起微博授权。</p>
        <p><a class="btn" href="/">返回首页</a></p>
        """
        return html_page("暂无授权结果", body)

    body = f"""
    <h1>微博授权成功</h1>
    <p class="ok">已成功收到授权并完成 token 交换。</p>

    <ul>
      <li>uid：<code>{LATEST_AUTH.get("uid", "")}</code></li>
      <li>access_token：<code>{mask_token(LATEST_AUTH.get("access_token", ""))}</code></li>
      <li>expires_in：<code>{LATEST_AUTH.get("expires_in", "")}</code></li>
      <li>remind_in：<code>{LATEST_AUTH.get("remind_in", "")}</code></li>
    </ul>

    <p>
      <a class="btn" href="/weibo/me">查看当前授权用户信息</a>
      <a class="btn secondary" href="/">返回首页重新授权</a>
    </p>

    <p class="muted">
      这里不明文展示完整 token，避免截图泄露或刷新重复使用旧 code。
    </p>
    """
    return html_page("授权成功", body)


@app.get("/weibo/me", response_class=HTMLResponse)
async def weibo_me() -> HTMLResponse:
    access_token = LATEST_AUTH.get("access_token")
    uid = LATEST_AUTH.get("uid")

    if not access_token or not uid:
        body = """
        <h1>暂无可用授权信息</h1>
        <p>请先完成微博授权。</p>
        <p><a class="btn" href="/">返回首页</a></p>
        """
        return html_page("暂无授权信息", body)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                WEIBO_USER_INFO_URL,
                params={
                    "access_token": access_token,
                    "uid": uid,
                },
            )
    except Exception as exc:
        body = f"""
        <h1>获取用户信息失败</h1>
        <pre>{str(exc)}</pre>
        <p><a class="btn" href="/">返回首页</a></p>
        """
        return html_page("获取用户信息失败", body)

    if response.status_code != 200:
        body = f"""
        <h1>微博用户信息接口返回异常</h1>
        <p>HTTP 状态码：<code>{response.status_code}</code></p>
        <pre>{response.text}</pre>
        <p><a class="btn" href="/">返回首页</a></p>
        """
        return html_page("用户信息接口异常", body)

    try:
        user_data = response.json()
    except json.JSONDecodeError:
        body = f"""
        <h1>用户信息解析失败</h1>
        <pre>{response.text}</pre>
        <p><a class="btn" href="/">返回首页</a></p>
        """
        return html_page("用户信息解析失败", body)

    pretty = json.dumps(user_data, ensure_ascii=False, indent=2)

    body = f"""
    <h1>当前授权用户信息</h1>
    <pre>{pretty}</pre>
    <p>
      <a class="btn secondary" href="/success">返回成功页</a>
      <a class="btn secondary" href="/">返回首页</a>
    </p>
    """
    return html_page("当前授权用户信息", body)


@app.get("/weibo/revoke", response_class=HTMLResponse)
async def weibo_revoke() -> HTMLResponse:
    body = """
    <h1>已进入取消授权回调页</h1>
    <p>如果你是在微博侧取消授权后跳转到这里，说明取消授权回调地址配置成功。</p>
    <p><a class="btn" href="/">返回首页</a></p>
    """
    return html_page("取消授权回调", body)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "has_client_id": bool(WEIBO_CLIENT_ID),
            "has_client_secret": bool(WEIBO_CLIENT_SECRET),
            "has_redirect_uri": bool(WEIBO_REDIRECT_URI),
            "redirect_uri": WEIBO_REDIRECT_URI,
            "authorize_url": build_authorize_url(),
            "has_latest_auth": bool(LATEST_AUTH),
        }
    )