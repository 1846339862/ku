# ==================== 📱 二维码生成工具（把 demo 链接转成可扫码的图片） ====================
"""BOSS 直聘等 IM 对外链有风控，未备案/境外域名常被拦截或打不开；
把链接转成二维码图片发送，HR 扫码即可直达，是最稳的触达方式。

用法（无需把 qrcode 加进项目依赖，uv 临时加载）：
    uv run --with qrcode python tools/make_qr.py https://your-app.streamlit.app
    uv run --with qrcode python tools/make_qr.py https://your-app.streamlit.app my_qr.png

生成后：把 PNG 以「图片」形式发给 HR（不要发链接本身），配一句引导话术。
"""

import sys


def main():
    try:
        import qrcode
    except ImportError:
        sys.exit(
            "缺少 qrcode 依赖。请用以下方式运行（临时加载，不写入项目依赖）：\n"
            "    uv run --with qrcode python tools/make_qr.py <URL> [输出文件名.png]"
        )

    if len(sys.argv) < 2:
        url = input("请输入 demo 链接（如 https://xxx.streamlit.app）: ").strip()
    else:
        url = sys.argv[1].strip()

    if not url.startswith(("http://", "https://")):
        sys.exit(f"链接格式不正确: {url!r}（需以 http:// 或 https:// 开头）")

    output = sys.argv[2] if len(sys.argv) > 2 else "demo_qr.png"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # 15% 容错，IM 压缩后仍可扫
        box_size=12,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1F2937", back_color="white")
    img.save(output)
    print(f"✅ 已生成二维码: {output}")
    print(f"   指向链接: {url}")
    print("   发送方式：在 BOSS 直聘里以【图片】形式发送（扫码直达，绕开外链风控）")


if __name__ == "__main__":
    main()
