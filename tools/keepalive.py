"""用无头浏览器「当一次真实用户」打开 demo 应用，防止 Streamlit Cloud 休眠。

背景：Streamlit Cloud 的认证网关依赖 JS 执行才放行，普通 HTTP 探针
（curl / UptimeRobot）会被 303 弹到登录页、永远触达不到应用，
因此保活必须用真实浏览器，并且要停留到应用完全唤醒才算一次有效访问。

脚本行为（等价于一个访客的完整动作）：
  1. 打开应用网址（休眠中会先显示占位页，等待唤醒）
  2. 自动点击「一键体验」按钮进入演示账号
  3. 等待人才库看板渲染出来（同步预热模型初始化与索引构建）
  4. 在页面停留一会儿模拟真实访客，然后截图留证

用法：
    APP_URL=https://你的应用.streamlit.app python tools/keepalive.py
"""

import os
import sys
import time

APP_URL = os.environ.get("APP_URL", "https://hr-talent-demo.streamlit.app")
SCREENSHOT = os.environ.get("SCREENSHOT", "keepalive.png")

# 应用独有文案，用于判断是否真正进入了应用
LOGIN_MARKERS = ("一键体验", "人才库管理中心", "上传候选人简历", "智能 HR")
DASH_MARKERS = ("人才库管理中心", "简历源文件管理", "上传候选人简历", "模型配置")


def page_text(page) -> str:
    """取页面全文。用 text_content 而非 inner_text：
    Streamlit 页面上 inner_text 在无头环境下可能返回空，text_content 更可靠。"""
    try:
        return page.locator("body").text_content() or ""
    except Exception:
        return ""


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
                print(f"   初始标题: {page.title() or '(无标题)'}")

                # 1) 等待登录页渲染（休眠唤醒可能要 1-3 分钟）
                login_ready = False
                for _ in range(60):
                    page.wait_for_timeout(2_000)
                    if any(m in page_text(page) for m in LOGIN_MARKERS):
                        login_ready = True
                        break
                print(f"   登录页就绪: {login_ready}（{time.time()-started:.0f}s）")

                # 2) 点击「一键体验」进入演示账号（多种定位方式兜底）
                clicked = False
                for selector in ("button:has-text('一键体验')",
                                 "text=一键体验",
                                 "[data-testid='stButton']:has-text('一键体验')"):
                    try:
                        loc = page.locator(selector)
                        if loc.count() > 0:
                            loc.first.click(timeout=8_000)
                            clicked = True
                            print(f"   已点击「一键体验」（{selector}）")
                            break
                    except Exception as e:
                        print(f"   点击失败 {selector}: {type(e).__name__}")
                if not clicked:
                    print("   未能点击一键体验（保留在登录页，保活依然有效）")

                # 3) 等待人才库看板渲染（这一步会预热模型初始化与索引构建）
                dash_ready = False
                for _ in range(90):
                    page.wait_for_timeout(2_000)
                    if any(m in page_text(page) for m in DASH_MARKERS):
                        dash_ready = True
                        break
                print(f"   人才库看板就绪: {dash_ready}（累计 {time.time()-started:.0f}s）")

                # 4) 停留 30 秒模拟真实访客，让会话真正计入活跃
                page.wait_for_timeout(30_000)

                elapsed = time.time() - started
                body = page_text(page)[:300].replace("\n", " ")
                print(f"   最终标题: {page.title() or '(无标题)'}")
                print(f"   页面文字: {body}")
                print(f"   总耗时: {elapsed:.0f}s")
                print(f"RESULT login_ready={login_ready} clicked={clicked} "
                      f"dashboard_ready={dash_ready} total_seconds={elapsed:.0f}")

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
