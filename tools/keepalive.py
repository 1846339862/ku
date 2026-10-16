"""用无头浏览器打开 demo 应用，防止 Streamlit Cloud 休眠。

背景：Streamlit Cloud 的认证网关依赖 JS 执行才放行访客，
普通 HTTP 请求（curl / UptimeRobot 等）会被 303 重定向到登录页、
永远触达不到应用（实测跳转 50 次、耗时 35 秒），因此保活必须用真实浏览器。

用法：
    APP_URL=https://你的应用.streamlit.app python tools/keepalive.py
"""

import os
import sys

APP_URL = os.environ.get("APP_URL", "https://hr-talent-demo.streamlit.app")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("缺少 playwright：请先执行  pip install playwright && playwright install chromium")
        return 0  # 保活失败不影响主流程，不报错退出

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
            try:
                page.goto(APP_URL, wait_until="domcontentloaded", timeout=120_000)
                # 等 Streamlit 建立 WebSocket 连接并完成首屏渲染
                page.wait_for_timeout(10_000)
                title = page.title() or "(无标题)"
                body = page.inner_text("body")[:200].replace("\n", " ")
                print(f"OK 已访问 {APP_URL}")
                print(f"   页面标题: {title}")
                print(f"   首屏文字: {body}")

                # 校验是否真正进入了应用（而不是停在 Streamlit 平台登录页）
                # 「一键体验」「人才库管理中心」是本应用独有文案，平台登录页不会出现
                markers = ("一键体验", "人才库管理中心", "上传候选人简历", "智能 HR")
                if any(m in body for m in markers):
                    print("RESULT reached_app=yes 已到达应用页面，保活有效")
                else:
                    print("RESULT reached_app=no 未到达应用页面（仍被认证网关拦截或页面异常）")
            except Exception as e:
                print(f"WARN 访问异常（不影响下次重试）: {type(e).__name__}: {e}")
            finally:
                browser.close()
    except Exception as e:
        print(f"WARN 浏览器启动失败: {type(e).__name__}: {e}")

    return 0  # 保活脚本永远返回 0，避免 workflow 报红造成骚扰


if __name__ == "__main__":
    sys.exit(main())
