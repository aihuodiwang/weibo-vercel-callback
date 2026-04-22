from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import os
import httpx

app = FastAPI(title="Weibo OAuth Callback Demo")

WEIBO_CLIENT_ID = os.getenv("WEIBO_CLIENT_ID", "")
WEIBO_CLIENT_SECRET = os.getenv("WEIBO_CLIENT_SECRET", "")
WEIBO_REDIRECT_URI = os.getenv("WEIBO_REDIRECT_URI", "")


@app.get("/", response_class=HTMLResponse)
async def home():
    auth_url = (
        "https://api.weibo.com/oauth2/authorize"
        f"?client_id={WEIBO_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={WEIBO_REDIRECT_URI}"
    )
    return f"""
    <html>
      <head><meta charset="utf-8"><title>Weibo OAuth Demo</title></head>
      <body style="font-family: sans-serif; max-width: 760px; margin: 40px auto;">
        <h1>微博授权测试页</h1>
        <p>回调地址：<code>{WEIBO_REDIRECT_URI}</code></p>
        <p><a href="{auth_url}">发起微博授权</a></p>
      </body>
    </html>
    """


@app.get("/weibo/callback", response_class=HTMLResponse)
async def weibo_callback(code: str | None = None, error: str | None = None):
    if error:
        return f"<html><body><h2>授权失败</h2><p>{error}</p></body></html>"

    if not code:
        return "<html><body><h2>未收到 code</h2></body></html>"

    token_result = "未尝试换取 token"

    if WEIBO_CLIENT_ID and WEIBO_CLIENT_SECRET and WEIBO_REDIRECT_URI:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://api.weibo.com/oauth2/access_token",
                    data={
                        "client_id": WEIBO_CLIENT_ID,
                        "client_secret": WEIBO_CLIENT_SECRET,
                        "grant_type": "authorization_code",
                        "redirect_uri": WEIBO_REDIRECT_URI,
                        "code": code,
                    },
                )
                token_result = resp.text
        except Exception as e:
            token_result = f"换 token 失败: {e}"

    return f"""
    <html>
      <head><meta charset="utf-8"><title>Weibo Callback</title></head>
      <body style="font-family: sans-serif; max-width: 760px; margin: 40px auto;">
        <h1>微博授权成功</h1>
        <p>收到 code：</p>
        <pre>{code}</pre>
        <p>token 返回：</p>
        <pre>{token_result}</pre>
      </body>
    </html>
    """


@app.get("/weibo/revoke", response_class=HTMLResponse)
async def weibo_revoke():
    return "<html><body><h2>取消授权回调成功</h2></body></html>"


@app.get("/health")
async def health():
    return {"ok": True}