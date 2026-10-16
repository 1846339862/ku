"""用无头浏览器「当一次真实用户」打开 demo 应用，防止 Streamlit Cloud 休眠。

背景：Streamlit Cloud 的认证网关依赖 JS 执行才放行，普通 HTTP 探针
（curl / UptimeRobot）会被 303 弹到登录页、永远触达不到应用，
因此保活必须用真实浏览器，并且要停留到应用完全唤醒才算一次有效访问。

脚本行为（等价于一个访客的完整动作）：
  1. 打开应用网址（休眠中会先显示占位页，等待唤醒）
  2. 自动点击「一键体验」按钮进入演示账号
  3. 等待人才库看板渲染出来（证明上传解析/索引/问答链路可用）
  4. 截图保存为 keepalive.png，并上传为 GitHub Actions 工件供人工检查

用法：
    APP_URL=https://你的应用.streamlit.app python tools/keepalive.py
"""

import os
import sys
import time

APP_URL = os.environ.get("APP_URL", "https://hr-talent-demo.streamlit.app")
SCREENSHOT = os.environ.get("SCREENSHOT", "keepalive.png")

# 应用独有文案，用于判断是否真正进入了应用
MARKERS = ("一键体验", "人才库管理中心", "上传候选人简历", "智能 HR",
           "简历源文件管理", "模型配置")


def body_text(page) -> str:
    try:
        return page.inner_text("body")[:400].replace("\n", " ")
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

                # 1) 等待登录页就绪后，点击「一键体验」真正进入应用
                clicked = False
                for _ in range(30):
                    page.wait_for_timeout(2_000)
                    if any(m in body_text(page) for m in MARKERS):
                        break
                    try:
                        btn = page.locator("button:has-text('一键体验')")
                        if btn.count() > 0 and btn.first.is_visible():
                            btn.first.click(timeout=5_000)
                            clicked = True
                            print("   已点击「一键体验」进入演示账号")
                            break
                    except Exception:
                        pass
                if not clicked:
                    print("   未执行点击（可能已在应用内或按钮未出现）")

                # 2) 等待人才库看板渲染（上传解析 / 索引构建都在这一步完成）
                reached = False
                for _ in range(60):
                    page.wait_for_timeout(2_000)
                    if any(m in body_text(page) for m in MARKERS):
                        reached = True
                        break

                elapsed = time.time() - started
                print(f"   最终标题: {page.title() or '(无标题)'}")
                print(f"   首屏文字: {body_text(page)}")
                print(f"   总耗时: {elapsed:.0f}s")
                print(f"RESULT reached_app={'yes' if reached else 'no'} "
                      f"wake_seconds={elapsed:.0f}")

                # 3) 截图留证（无论成功与否，便于人工诊断）
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
