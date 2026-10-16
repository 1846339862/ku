"""用无头浏览器「当一次真实用户」打开 demo 应用，防止 Streamlit Cloud 休眠。

背景：Streamlit Cloud 的认证网关依赖 JS 执行才放行，普通 HTTP 探针
（curl / UptimeRobot）会被 303 弹到登录页、永远触达不到应用，
因此保活必须用真实浏览器，并且要停留到应用完全唤醒才算一次有效访问。

脚本行为（等价于一个访客的完整动作）：
  1. 打开应用网址（休眠中会先显示占位页，等待唤醒）
  2. 自动点击「一键体验」按钮进入演示账号
  3. 等待人才库看板渲染出来（同步预热模型初始化与索引构建）
  4. 在页面停留一会儿模拟真实访客，然后截图留证

判据说明：用 page.title() 判断应用是否就绪最可靠——
st.set_page_config 设置的标题「智能 HR…」只在应用真正加载后出现；
而 body 的 text_content 在 Streamlit 页面会混入外壳固有的
<noscript> 文本，不适合做判据（实测踩坑）。

用法：
    APP_URL=https://你的应用.streamlit.app python tools/keepalive.py
"""

import os
import sys
import time

APP_URL = os.environ.get("APP_URL", "https://hr-talent-demo.streamlit.app")
SCREENSHOT = os.environ.get("SCREENSHOT", "keepalive.png")
APP_TITLE_MARK = "智能 HR"


def app_ready(page) -> bool:
    """应用是否已加载：标题由 st.set_page_config 设置，是最可靠的判据。"""
    try:
        return APP_TITLE_MARK in (page.title() or "")
    except Exception:
        return False


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("缺少 playwright：pip install playwright && playwright install chromium")
        return 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )
            try:
                started = time.time()
                page.goto(APP_URL, wait_until="domcontentloaded", timeout=120_000)
                print(f"OK 已访问 {APP_URL}")

                # 1) 等待应用加载完成（从休眠唤醒通常 30-90 秒）
                while not app_ready(page) and time.time() - started < 180:
                    page.wait_for_timeout(1_000)
                wake_s = time.time() - started
                print(f"   应用就绪: {app_ready(page)}（唤醒耗时 {wake_s:.0f}s）")

                # 2) 点击「一键体验」进入演示账号
                # 注意：标题就绪后 Streamlit 的 React 组件还需时间 hydrate，
                # 按钮不会立刻出现在 DOM 里，必须轮询等待而不是立即点。
                clicked = False
                for _ in range(30):
                    for selector in ("button:has-text('一键体验')", "text=一键体验"):
                        try:
                            loc = page.locator(selector)
                            if loc.count() > 0 and loc.first.is_visible():
                                loc.first.click(timeout=8_000)
                                clicked = True
                                print(f"   已点击「一键体验」（{selector}）")
                                break
                        except Exception as e:
                            print(f"   点击失败 {selector}: {type(e).__name__}")
                    if clicked:
                        break
                    page.wait_for_timeout(1_000)
                if not clicked:
                    n = page.locator("button").count()
                    print(f"   未点击（30 秒内按钮未出现，当前页面按钮数={n}）")

                # 3) 进入演示账号后等待看板渲染（预热模型与索引）
                page.wait_for_timeout(5_000)
                dash_s = time.time() - started
                print(f"   已进入演示账号并停留（累计 {dash_s:.0f}s）")

                # 4) 再停留 30 秒模拟真实访客，确保会话计入活跃
                page.wait_for_timeout(30_000)

                elapsed = time.time() - started
                print(f"   最终标题: {page.title() or '(无标题)'}")
                print(f"RESULT app_ready={app_ready(page)} clicked={clicked} "
                      f"wake_seconds={wake_s:.0f} total_seconds={elapsed:.0f}")

                # 5) 截图留证
                try:
                    page.screenshot(path=SCREENSHOT, full_page=False)
                    print(f"   截图已保存: {SCREENSHOT}")
                except Exception as e:
                    print(f"   截图失败: {e}")
            except Exception as e:
                print(f"WARN 访问异常（不影响下次重试）: {type(e).__name__}: {e}")
            finally:
                browser.close()
    except Exception as e:
        print(f"WARN 浏览器启动失败: {type(e).__name__}: {e}")

    return 0  # 保活脚本永不报错退出，避免 workflow 频繁标红造成骚扰


if __name__ == "__main__":
    sys.exit(main())
