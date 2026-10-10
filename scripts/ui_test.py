"""
scripts/ui_test.py —— 界面层自动化测试（用 Streamlit 官方 AppTest）

【AppTest 是什么？】
Streamlit 官方提供的测试工具，能在不打开浏览器的情况下，
把 app.py 真的执行一遍，并且可以模拟"填表单、点按钮"，
最后检查页面上有没有抛异常。

这就补上了冒烟测试测不到的盲区：
services 层是对的，但界面代码可能写错（比如调用了不存在的参数、变量名打错）。
AppTest 能把这些在 10 秒内抓出来。

用法：python scripts/ui_test.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402  (必须在 sys.path 设置之后导入)

APP = str(ROOT / "app.py")
PASS, FAIL = "✅", "❌"
_failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}  {detail}")
        _failures.append(label)


def no_exception(at: AppTest, step: str) -> bool:
    """检查这一步有没有抛异常（并打印堆栈方便定位）"""
    if at.exception:
        for exc in at.exception:
            print(f"     ↳ 异常：{exc.value}")
            if exc.stack_trace:
                print("     " + "\n     ".join(exc.stack_trace[:12]))
        check(f"{step} 无异常", False)
        return False
    check(f"{step} 无异常", True)
    return True


def all_text(at: AppTest) -> str:
    """把页面上所有文本拼起来，方便做包含断言。

    注意 st.tabs 的标签不在 title/markdown 这些属性里，要单独取。
    """
    parts = []
    for attr in ("title", "header", "subheader", "markdown", "caption", "text",
                 "info", "warning", "success", "error"):
        for el in getattr(at, attr, []):
            value = getattr(el, "value", None)
            if value is not None:
                parts.append(str(value))

    # 标签页（st.tabs）单独处理
    for el in at.get("tab"):
        label = getattr(el, "label", None)
        if label:
            parts.append(str(label))

    return "\n".join(parts)


def main() -> int:
    print("=== 星海日记 · 界面层测试（AppTest）===\n")

    # ---------------------------------------------------------------
    print("[1] 首次打开 → 登录页")
    at = AppTest.from_file(APP, default_timeout=60).run()
    if not no_exception(at, "初始渲染"):
        return 1
    text = all_text(at)
    check("显示应用标题「星海日记」", "星海日记" in text)
    check("有登录/注册两个标签页", "登录" in text and "注册" in text)
    check("输入框数量 ≥ 6（登录 2 + 注册 4）", len(at.text_input) >= 6,
          f"实际={len(at.text_input)}")

    # ---------------------------------------------------------------
    print("\n[2] 用错误密码登录 → 应报错")
    at.text_input[0].set_value("demo")
    at.text_input[1].set_value("wrong_password")
    at.button[0].click().run()
    if not no_exception(at, "错误密码提交"):
        return 1
    check("提示用户名或密码错误", "用户名或密码错误" in all_text(at))

    # ---------------------------------------------------------------
    print("\n[3] 用正确密码登录 → 进入房间大厅")
    # 重新构造一个干净实例，避免上一轮的错误状态残留
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input[0].set_value("demo")
    at.text_input[1].set_value("demo123")
    at.button[0].click().run()
    if not no_exception(at, "登录提交"):
        return 1
    text = all_text(at)
    check("进入房间大厅", "我的回忆房间" in text or "房间大厅" in text)
    check("侧边栏显示昵称「演示小助手」", "演示小助手" in text)
    check("能看到演示房间", "王力宏演唱会回忆馆" in text)
    check("显示房间邀请码 WLG2026", "WLG2026" in text)

    # ---------------------------------------------------------------
    print("\n[4] 进入房间 → 看到时间线")
    # 找到「进入房间」按钮并点击
    enter_buttons = [b for b in at.button if "进入房间" in str(b.label)]
    check("存在「进入房间」按钮", len(enter_buttons) > 0)
    if enter_buttons:
        enter_buttons[0].click().run()
        if not no_exception(at, "进入房间"):
            return 1
        text = all_text(at)
        check("显示房间名", "王力宏演唱会回忆馆" in text)
        check("显示成员数", "位成员" in text)
        check("有「写一段新回忆」标签", "写一段新回忆" in text or "写一段新回忆" in text)
        check("有「回忆时间线」标签", "回忆时间线" in text)
        check("时间线里能看到演示回忆标题", "散场后我们谁都没走" in text)
        check("时间线里能看到正文片段", "这是结束" in text or "坐标" in text)
        check("有照片上传组件", len(at.get("file_uploader")) > 0,
              f"实际={len(at.get('file_uploader'))}")

    # ---------------------------------------------------------------
    print("\n[5] 返回房间大厅")
    back_buttons = [b for b in at.button if "返回房间大厅" in str(b.label)]
    check("存在「返回房间大厅」按钮", len(back_buttons) > 0)
    if back_buttons:
        back_buttons[0].click().run()
        if not no_exception(at, "返回大厅"):
            return 1
        check("回到了房间大厅", "我的回忆房间" in all_text(at))

    # ---------------------------------------------------------------
    print("\n" + "=" * 46)
    if _failures:
        print(f"{FAIL} 失败 {len(_failures)} 项：")
        for f in _failures:
            print(f"   - {f}")
        print("=" * 46)
        return 1
    print(f"{PASS} 界面层全部通过 —— 登录/报错提示/房间大厅/进入房间/时间线/返回")
    print("=" * 46)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"\n{FAIL} 测试过程中抛出异常：{exc}")
        sys.exit(1)
