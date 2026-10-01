"""单词复习与检验 —— Streamlit 版。运行：streamlit run app.py"""
import html
import json
import random
import re
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
PROGRESS = ROOT / "progress.json"
ROUND = 50
NEED_STREAK = 2


@st.cache_data
def load_words():
    words, seen = [], set()
    for line in (ROOT / "words.txt").read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 4 or parts[0].lower() in seen:
            continue
        seen.add(parts[0].lower())
        words.append(dict(zip(("en", "zh", "ex", "exzh"), parts)))
    return words


WORDS = load_words()
BY_KEY = {w["en"].lower(): w for w in WORDS}
ALL_KEYS = list(BY_KEY)


def load_progress():
    try:
        p = json.loads(PROGRESS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        p = {}
    p.setdefault("weak", [])
    p.setdefault("errors", {})
    p.setdefault("decks", {})
    p.setdefault("test_stats", {"right": 0, "wrong": 0})
    p["weak"] = [k for k in p["weak"] if k in BY_KEY]
    p["errors"] = {k: v for k, v in p["errors"].items() if k in BY_KEY}
    return p


if "p" not in st.session_state:
    st.session_state.p = load_progress()
P = st.session_state.p


def save():
    try:
        PROGRESS.write_text(json.dumps(P, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # 只读环境（如部分云端部署）下仅保留本次会话内的进度


def get_deck(name, src, pool):
    d = P["decks"].setdefault(f"{name}:{src}", {"order": list(pool), "pos": 0})
    # 词库有增减时同步顺序：去掉已不在库中的，追加新加入的
    pool_set = set(pool)
    d["order"] = [k for k in d["order"] if k in pool_set]
    in_order = set(d["order"])
    d["order"] += [k for k in pool if k not in in_order]
    d["pos"] = min(d["pos"], len(d["order"]))
    return d


def round_info(d):
    total = max(1, -(-len(d["order"]) // ROUND))
    rnd = min(d["pos"] // ROUND, total - 1)
    start = rnd * ROUND
    size = min(start + ROUND, len(d["order"])) - start
    return total, rnd, d["pos"] - start, size


def esc(s):
    return html.escape(s, quote=True)


def mark(ex, en):
    """转义例句并把其中的复习单词（含 -s/-ed/-ing 等变形）标成蓝色。"""
    words = [re.escape(p) for p in en.split()]
    pat = r"(?<![A-Za-z])" + r"[\s-]+".join(words) + r"(?:s|es|d|ed|ing)?(?![A-Za-z])"
    out, last = [], 0
    for m in re.finditer(pat, ex, re.I):
        out += [esc(ex[last:m.start()]), f'<span class="hl">{esc(m.group())}</span>']
        last = m.end()
    return "".join(out) + esc(ex[last:])


def norm(s):
    s = re.sub(r"[‘’`´]", "'", s.lower()).replace(",", " ")
    return re.sub(r"[.!?]+$", "", re.sub(r"\s+", " ", s).strip())


def pattern(en):
    return "&nbsp;&nbsp;&nbsp;".join(re.sub(r"[A-Za-z]", "_", p) for p in en.split())


def dots(n):
    return "".join(f'<i class="dot{" on" if i < n else ""}"></i>' for i in range(NEED_STREAK))


def speak_button(text, label="🔊 朗读"):
    t = json.dumps(text)
    st.iframe(
        f"""<body style="margin:0;overflow:hidden"><button onclick='speechSynthesis.cancel();const u=new SpeechSynthesisUtterance({t});u.lang="en-US";u.rate=.9;speechSynthesis.speak(u)'
        style="font:14px sans-serif;padding:4px 12px;border-radius:8px;border:1px solid #ccc;background:#fff;cursor:pointer">{label}</button>""",
        height=40,
    )


def focus_input():
    st.iframe(
        "<script>setTimeout(()=>{const i=window.parent.document.querySelector('input[type=text]');if(i)i.focus()},50)</script>",
        height=1,
    )


def card(body, cls=""):
    st.markdown(f'<div class="card {cls}">{body}</div>', unsafe_allow_html=True)


def round_controls(name, d, info, reset_stats=None):
    total, rnd, _, _ = info
    c1, c2 = st.columns([3, 1])
    picked = c1.selectbox(
        "轮次", range(total), index=rnd, format_func=lambda i: f"第 {i + 1} 轮 / 共 {total} 轮",
        key=f"{name}_round_{rnd}_{total}", label_visibility="collapsed",
    )
    if picked != rnd:
        d["pos"] = picked * ROUND
        if reset_stats:
            reset_stats()
        save()
        st.rerun()
    if c2.button("🔀 打乱", key=f"{name}_shuffle", width="stretch", help="打乱顺序并从第 1 轮开始"):
        random.shuffle(d["order"])
        d["pos"] = 0
        if reset_stats:
            reset_stats()
        save()
        st.rerun()


def progress_bar(info, extra=""):
    _, _, idx, size = info
    if size:
        done = min(idx, size)
        st.progress(done / size, text=f"本轮 {done} / {size}{extra}")


st.set_page_config(page_title="单词复习与检验", page_icon="📘", layout="centered")
st.markdown(
    """<style>
.card{border:1px solid rgba(128,128,128,.3);border-radius:18px;padding:36px 24px;min-height:260px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;
  box-shadow:0 6px 24px rgba(30,30,40,.08);margin-bottom:14px;animation:flip .35s ease}
@keyframes flip{from{transform:perspective(900px) rotateY(80deg);opacity:.3}to{transform:none;opacity:1}}
.card .word{font-size:46px;font-weight:700;word-break:break-word}
.card .zh{font-size:26px;font-weight:600;margin-bottom:14px}
.card .ex{font-size:17px;line-height:1.5;margin-bottom:6px}
.card .exzh{font-size:15px;opacity:.65}
.card .pattern{font-family:Consolas,monospace;font-size:20px;letter-spacing:2px;opacity:.6;margin-top:10px}
.card .tag{font-size:12px;padding:2px 10px;border-radius:999px;background:#fbf0dd;color:#c7811a;margin-bottom:12px}
.card.good{background:#e3f6ea;border-color:#1f9d55}.card.good .word{color:#1f9d55}
.card.bad{background:#fbe7e7;border-color:#d64545}.card.bad .word{color:#d64545}
.card.good .ex,.card.bad .ex{color:#23262b}
.card .typed{margin-top:8px;color:#6b7078}.card .typed s{color:#d64545}
.card .note{margin-top:10px;font-weight:600}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;border:2px solid #1f9d55;margin:0 2px;vertical-align:-1px}
.dot.on{background:#1f9d55}
.card .hl{color:#2f6fdb;font-weight:700;background:rgba(47,111,219,.12);padding:0 3px;border-radius:4px}
.streak{margin-top:12px;font-size:13px;opacity:.75}
.card{position:relative}
.card .cardhint{position:absolute;bottom:12px;left:0;right:0;font-size:12px;opacity:.5}
.st-key-rv_card{position:relative;gap:0}
.st-key-rv_card .card{cursor:pointer;transition:box-shadow .15s}
.st-key-rv_card:hover .card{box-shadow:0 8px 30px rgba(47,111,219,.18)}
.st-key-rv_card [data-testid="stElementContainer"]:has(.stButton){position:absolute;inset:0 0 14px 0;width:100% !important;z-index:2}
.st-key-rv_card .stButton,.st-key-rv_card .stButton > div{width:100%;height:100%}
.st-key-rv_card .stButton button{width:100%;height:100%;opacity:0;cursor:pointer}
</style>""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("📘 单词复习与检验")
    mode = st.radio("分区", ["📖 复习", "✍️ 拼写检验"], label_visibility="collapsed")
    st.divider()
    st.metric("词库总数", len(WORDS))
    c1, c2 = st.columns(2)
    c1.metric("不太熟", len(P["weak"]))
    c2.metric("错误清单", len(P["errors"]))
    st.caption("进度自动保存在 progress.json")
    if st.button("清空全部进度", type="secondary"):
        st.session_state.p = {"weak": [], "errors": {}, "decks": {}, "test_stats": {"right": 0, "wrong": 0}}
        st.session_state.pop("ts_result", None)
        P = st.session_state.p
        save()
        st.rerun()


def review_page():
    src = st.radio(
        "词库", ["all", "weak"], horizontal=True, key="rv_src",
        format_func=lambda s: f"全部单词（{len(WORDS)}）" if s == "all" else f"不太熟（{len(P['weak'])}）",
    )
    d = get_deck("review", src, ALL_KEYS if src == "all" else P["weak"])
    info = round_info(d)
    round_controls("rv", d, info)
    progress_bar(info)
    total, rnd, idx, size = info

    if not d["order"]:
        st.info("「不太熟」词库还是空的。复习时点击「不太熟」，单词就会被收进这里。")
    elif idx >= size:
        last = rnd >= total - 1
        card(f'<div class="zh">🎉 第 {rnd + 1} 轮完成</div><div class="exzh">本轮复习 {size} 个单词，「不太熟」词库现有 {len(P["weak"])} 个</div>')
        if st.button("从第 1 轮重新开始" if last else f"开始第 {rnd + 2} 轮", type="primary", width="stretch"):
            if last:
                d["pos"] = 0
            save()
            st.rerun()
    else:
        key = d["order"][d["pos"]]
        w = BY_KEY[key]
        flipped = st.session_state.get("rv_flip") == key
        tag = '<div class="tag">不太熟</div>' if key in P["weak"] else ""
        with st.container(key="rv_card"):
            if flipped:
                card(f'<div class="zh">{esc(w["zh"])}</div><div class="ex">{mark(w["ex"], w["en"])}</div><div class="exzh">{esc(w["exzh"])}</div>'
                     '<div class="cardhint">点击卡片翻回英文</div>')
            else:
                card(f'{tag}<div class="word">{esc(w["en"])}</div><div class="cardhint">点击卡片查看中文和例句</div>')
            # 透明按钮铺满卡片，点击卡片即翻面
            if st.button("翻面", key="rv_flip_btn"):
                st.session_state.rv_flip = None if flipped else key
                st.rerun()
        speak_button(w["ex"] if flipped else w["en"])
        a, b = st.columns(2)
        if a.button("不太熟", width="stretch"):
            if key not in P["weak"]:
                P["weak"].append(key)
            d["pos"] += 1
            save()
            st.rerun()
        if b.button("下一个词", type="primary", width="stretch"):
            d["pos"] += 1
            save()
            st.rerun()
        if src == "weak" and st.button("已经熟了，移出「不太熟」词库", type="tertiary"):
            P["weak"].remove(key)
            save()
            st.rerun()

    with st.expander(f"查看「不太熟」词库（{len(P['weak'])}）"):
        if P["weak"]:
            st.dataframe(
                [{"英文": BY_KEY[k]["en"], "中文": BY_KEY[k]["zh"]} for k in P["weak"]],
                hide_index=True, width="stretch",
            )
        else:
            st.caption("（空）")


def test_page():
    stats = P["test_stats"]

    def reset_stats():
        P["test_stats"] = {"right": 0, "wrong": 0}
        st.session_state.pop("ts_result", None)

    src = st.radio(
        "词库", ["all", "errors"], horizontal=True, key="ts_src", on_change=reset_stats,
        format_func=lambda s: f"全部单词（{len(WORDS)}）" if s == "all" else f"错误清单（{len(P['errors'])}）",
    )
    d = get_deck("test", src, ALL_KEYS if src == "all" else list(P["errors"]))
    info = round_info(d)
    round_controls("ts", d, info, reset_stats)
    stats = P["test_stats"]
    progress_bar(info, f"　✔ {stats['right']}　✘ {stats['wrong']}")
    total, rnd, idx, size = info
    result = st.session_state.get("ts_result")

    def advance(key):
        st.session_state.pop("ts_result", None)
        dd = get_deck("test", src, ALL_KEYS if src == "all" else list(P["errors"]))
        # 错误清单模式下，被移出的词已不在顺序表里，下一词会自动补位
        if dd["pos"] < len(dd["order"]) and dd["order"][dd["pos"]] == key:
            dd["pos"] += 1
        save()

    if result:
        w = BY_KEY[result["key"]]
        ok = result["ok"]
        typed = "" if ok else f'<div class="typed">你的拼写：<s>{esc(result["typed"])}</s></div>'
        note = f'<div class="note">{result["note"]}</div>' if result["note"] else ""
        card(f'<div class="word">{esc(w["en"])}</div>{typed}<div class="ex" style="margin-top:14px">{mark(w["ex"], w["en"])}</div>{note}',
             "good" if ok else "bad")
        if ok:
            # 停留期间隐藏上一屏残留的题目卡片和输入框
            st.markdown('<style>[data-stale="true"]{display:none}</style>', unsafe_allow_html=True)
            time.sleep(1.2)
            advance(result["key"])
            st.rerun()
        c0, c1 = st.columns([1, 3])
        with c0:
            speak_button(w["en"])
        if c1.button("下一个 ➜", type="primary", width="stretch"):
            advance(result["key"])
            st.rerun()
    elif not d["order"]:
        st.success("错误清单是空的 👍 拼写检验中拼错的单词会自动收进这里。")
    elif idx >= size:
        last = rnd >= total - 1
        card(f'<div class="zh">✅ 第 {rnd + 1} 轮完成</div>'
             f'<div class="ex">拼对 <b style="color:#1f9d55">{stats["right"]}</b>　拼错 <b style="color:#d64545">{stats["wrong"]}</b>　'
             f'错误清单 <b>{len(P["errors"])}</b></div>')
        if st.button("从第 1 轮重新开始" if last else f"开始第 {rnd + 2} 轮", type="primary", width="stretch"):
            if last:
                d["pos"] = 0
            reset_stats()
            save()
            st.rerun()
    else:
        key = d["order"][d["pos"]]
        w = BY_KEY[key]
        in_err = key in P["errors"]
        tag = '<div class="tag">错误清单</div>' if in_err else ""
        streak = f'<div class="streak">连续拼对 {dots(P["errors"][key])}</div>' if in_err else ""
        card(f'{tag}<div class="zh">{esc(w["zh"])}</div><div class="exzh">{esc(w["exzh"])}</div>'
             f'<div class="pattern">{pattern(w["en"])}</div>{streak}')
        with st.form("ts_form", clear_on_submit=True, border=False):
            c1, c2 = st.columns([4, 1])
            typed = c1.text_input("拼写", placeholder="输入英文拼写，按 Enter 提交", label_visibility="collapsed")
            submitted = c2.form_submit_button("提交", type="primary", width="stretch")
        focus_input()
        if submitted and typed.strip():
            ok = norm(typed) == norm(w["en"])
            note = ""
            if ok:
                stats["right"] += 1
                if in_err:
                    P["errors"][key] += 1
                    if P["errors"][key] >= NEED_STREAK:
                        del P["errors"][key]
                        note = "🎉 连续拼对 2 次，已移出错误清单"
                    else:
                        note = f"离移出错误清单还差 {NEED_STREAK - P['errors'][key]} 次"
            else:
                stats["wrong"] += 1
                note = "连续次数已清零" if in_err else "已加入错误清单"
                P["errors"][key] = 0
            save()
            st.session_state.ts_result = {"key": key, "ok": ok, "typed": typed, "note": note}
            st.rerun()

    with st.expander(f"查看错误清单（{len(P['errors'])}，连续拼对 2 次才会移出）"):
        if P["errors"]:
            st.dataframe(
                [{"英文": BY_KEY[k]["en"], "中文": BY_KEY[k]["zh"], "连续拼对": f"{v} / {NEED_STREAK}"} for k, v in P["errors"].items()],
                hide_index=True, width="stretch",
            )
        else:
            st.caption("（空）")


if mode == "📖 复习":
    review_page()
else:
    test_page()
