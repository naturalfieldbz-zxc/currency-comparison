"""
多银行/多券商实时汇率对比监控
支持: CNY, HKD, USD 之间的兑换汇率对比
"""

import random
import time
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from data_sources import (
    BANK_CATEGORY,
    BROKER_CATEGORY,
    RateSnapshot,
    get_all_rates,
    format_rate,
)

# ============================================================
# 页面配置
# ============================================================

st.set_page_config(
    page_title="实时汇率对比监控",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# 自定义样式
# ============================================================

st.markdown(
    """
<style>
    /* 整体字体 */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
            "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
    }

    /* 主标题 */
    .main-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 0.85rem;
        color: #888;
        margin-bottom: 1rem;
    }

    /* 更新状态栏 */
    .status-bar {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 0.5rem 0;
        font-size: 0.85rem;
    }
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 4px;
    }
    .status-dot.live {
        background-color: #10b981;
        animation: pulse 2s infinite;
    }
    .status-dot.stale {
        background-color: #f59e0b;
    }
    .status-dot.error {
        background-color: #ef4444;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }

    /* 数据来源标签 */
    .badge-real {
        display: inline-block;
        background: #dbeafe;
        color: #1d4ed8;
        font-size: 0.7rem;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 600;
    }
    .badge-est {
        display: inline-block;
        background: #fef3c7;
        color: #b45309;
        font-size: 0.7rem;
        padding: 2px 6px;
        border-radius: 4px;
    }

    /* 最佳汇率高亮 */
    .best-rate {
        color: #059669;
        font-weight: 700;
    }

    /* 分区标题 */
    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #374151;
        padding: 0.3rem 0;
        border-bottom: 2px solid #e5e7eb;
        margin-bottom: 0.5rem;
    }

    /* 指标卡片 */
    .metric-card {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #111827;
    }
    .metric-label {
        font-size: 0.75rem;
        color: #6b7280;
    }
    .metric-sub {
        font-size: 0.7rem;
        color: #9ca3af;
    }

    /* 表格样式覆盖 */
    [data-testid="stDataFrame"] td {
        font-size: 0.9rem;
    }

    /* 按钮样式 */
    .stButton > button {
        border-radius: 6px;
        font-weight: 500;
    }

    /* 排行榜样式 */
    .ranking-section {
        background: linear-gradient(135deg, #f0fdfa 0%, #faf5ff 100%);
        border: 1px solid #d1d5db;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }
    .ranking-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 0.8rem;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    .ranking-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.8rem;
    }
    .ranking-col {
        background: white;
        border-radius: 8px;
        padding: 0.7rem 0.9rem;
        border: 1px solid #e5e7eb;
    }
    .ranking-col-title {
        font-size: 0.8rem;
        font-weight: 600;
        color: #6b7280;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .rank-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.35rem 0.45rem;
        margin-bottom: 0.25rem;
        border-radius: 6px;
        background: #f9fafb;
        font-size: 0.85rem;
        transition: background 0.15s;
    }
    .rank-row:hover { background: #f3f4f6; }
    .rank-left {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .rank-badge {
        width: 24px; height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.72rem;
        font-weight: 700;
        color: white;
        flex-shrink: 0;
    }
    .rank-badge.gold { background: #f59e0b; }
    .rank-badge.silver { background: #94a3b8; }
    .rank-badge.bronze { background: #d97706; }
    .rank-badge.normal { background: #cbd5e1; color: #64748b; }
    .rank-inst {
        font-weight: 600;
        color: #1e293b;
    }
    .rank-tag {
        font-size: 0.65rem;
        padding: 1px 5px;
        border-radius: 3px;
        margin-left: 4px;
    }
    .rank-tag.bank { background: #dbeafe; color: #1d4ed8; }
    .rank-tag.broker { background: #fef3c7; color: #b45309; }
    .rank-rate {
        font-weight: 700;
        font-size: 0.9rem;
        color: #059669;
        font-variant-numeric: tabular-nums;
    }
    .rank-spread {
        font-size: 0.65rem;
        color: #9ca3af;
        margin-left: 0.3rem;
    }

    /* 隐藏默认 Streamlit 元素 */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# 缓存数据获取
# ============================================================


@st.cache_data(ttl=60, show_spinner="正在获取最新汇率...")
def fetch_rates_cached(_cache_buster: int = 0) -> RateSnapshot:
    """带缓存的数据获取，60秒自动过期"""
    return get_all_rates()


# ============================================================
# UI 组件
# ============================================================


def render_header():
    """渲染页面头部"""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            '<div class="main-title">实时汇率对比监控</div>', unsafe_allow_html=True
        )
        st.markdown(
            '<div class="sub-title">CNY · HKD · USD — 银行 & 券商汇率实时对比</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)

        # 手动刷新按钮
        if st.button("手动刷新", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()

        # 自动刷新开关
        auto_refresh = st.checkbox("自动刷新 (60s)", value=False)

    return auto_refresh


def render_status_bar(snapshot: RateSnapshot):
    """渲染状态栏"""
    real_count = sum(1 for r in snapshot.rates if r.is_real_data)
    total_count = len(snapshot.rates)
    age = (datetime.now() - snapshot.timestamp).total_seconds()

    # 确定状态
    if age < 90:
        dot_class = "live"
        status_text = "实时"
    elif age < 300:
        dot_class = "stale"
        status_text = "稍旧"
    else:
        dot_class = "error"
        status_text = "需刷新"

    cols = st.columns([1, 1, 1, 1])
    with cols[0]:
        st.markdown(
            f'<span class="status-dot {dot_class}"></span>'
            f"状态: {status_text} "
            f"({int(age)}秒前)",
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            f"更新时间: {snapshot.timestamp.strftime('%H:%M:%S')}",
            unsafe_allow_html=True,
        )
    with cols[2]:
        st.markdown(f"机构总数: {total_count}", unsafe_allow_html=True)
    with cols[3]:
        st.markdown(
            f'真实数据: {real_count} <span class="badge-real">官方</span> '
            f' | 估算: {total_count - real_count} <span class="badge-est">估算</span>',
            unsafe_allow_html=True,
        )


def render_rate_table(
    rates: list, pair: str, category: str, snapshot: RateSnapshot
):
    """
    渲染汇率对比表格
    category: "bank" 或 "broker"
    """
    filtered = [r for r in rates if r.pair == pair and r.category == category]

    if not filtered:
        st.info(f"暂无{category}数据")
        return

    # 排序: 银行按名称，券商也按名称
    filtered.sort(key=lambda r: r.institution)

    # 找到最佳汇率
    best_buy_rate = max(r.buy_rate for r in filtered)
    best_sell_rate = min(r.sell_rate for r in filtered)

    # 构建表格数据
    rows = []
    for r in filtered:
        buy_highlight = r.buy_rate == best_buy_rate
        sell_highlight = r.sell_rate == best_sell_rate

        # 来源标签
        if r.is_real_data:
            source_tag = f'<span class="badge-real">官方</span>'
        else:
            source_tag = f'<span class="badge-est">估算</span>'

        rows.append(
            {
                "机构": r.institution + " " + source_tag,
                "买入价": r.buy_rate,
                "卖出价": r.sell_rate,
                "中间价": r.mid_rate,
                "点差(bps)": r.spread_bps,
                "买入标识": buy_highlight,
                "卖出标识": sell_highlight,
            }
        )

    df = pd.DataFrame(rows)

    # 使用 column_config 设置格式
    base, quote = pair.split("/")

    column_config = {
        "机构": st.column_config.TextColumn("机构", width="medium"),
        "买入价": st.column_config.NumberColumn(
            f"买入价 (你卖{base})",
            format="%.4f",
            help=f"机构买入{base}的价格，即你卖出{base}能得到多少{quote}",
        ),
        "卖出价": st.column_config.NumberColumn(
            f"卖出价 (你买{base})",
            format="%.4f",
            help=f"机构卖出{base}的价格，即你买入{base}需要多少{quote}",
        ),
        "中间价": st.column_config.NumberColumn("中间价", format="%.4f"),
        "点差(bps)": st.column_config.NumberColumn("点差(bps)", format="%.1f"),
        "买入标识": st.column_config.CheckboxColumn("最优买入", width="small"),
        "卖出标识": st.column_config.CheckboxColumn("最优卖出", width="small"),
    }

    st.dataframe(
        df,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        column_order=["机构", "买入价", "卖出价", "中间价", "点差(bps)", "买入标识", "卖出标识"],
    )

    # 最佳汇率提示
    best_buy_inst = [r for r in filtered if r.buy_rate == best_buy_rate]
    best_sell_inst = [r for r in filtered if r.sell_rate == best_sell_rate]

    c1, c2 = st.columns(2)
    with c1:
        inst_names = ", ".join(r.institution for r in best_buy_inst)
        st.caption(
            f"卖出{base}最划算: **{inst_names}** "
            f"(1 {base} = {best_buy_rate:.4f} {quote})"
        )
    with c2:
        inst_names = ", ".join(r.institution for r in best_sell_inst)
        st.caption(
            f"买入{base}最划算: **{inst_names}** "
            f"(1 {base} = {best_sell_rate:.4f} {quote})"
        )


def render_chart(rates: list, pair: str, snapshot: RateSnapshot):
    """用 Altair 渲染柱状图对比"""
    all_for_pair = [r for r in rates if r.pair == pair]
    if not all_for_pair:
        return

    # 构建图表数据
    chart_rows = []
    for r in sorted(all_for_pair, key=lambda x: (x.category, x.institution)):
        chart_rows.append(
            {
                "机构": r.institution,
                "类别": "银行" if r.category == BANK_CATEGORY else "券商",
                "买入价": r.buy_rate,
                "卖出价": r.sell_rate,
            }
        )

    df = pd.DataFrame(chart_rows)

    # 买入价柱状图（按机构）
    buy_chart = (
        alt.Chart(df)
        .mark_bar(size=30)
        .encode(
            x=alt.X("买入价:Q", title=f"汇率 ({pair})"),
            y=alt.Y("机构:N", title=None, sort=None),
            color=alt.Color(
                "类别:N",
                title="类别",
                scale=alt.Scale(domain=["银行", "券商"], range=["#3b82f6", "#f59e0b"]),
            ),
            tooltip=["机构:N", "类别:N", "买入价:Q", "卖出价:Q"],
        )
        .properties(title="买入价对比（你卖出基准货币能拿到的价格）", height=max(200, 50 * len(df)))
    )

    # 卖出价散点叠加
    sell_overlay = (
        alt.Chart(df)
        .mark_circle(size=80, stroke="white", strokeWidth=1)
        .encode(
            x=alt.X("卖出价:Q"),
            y=alt.Y("机构:N", sort=None),
            color=alt.Color(
                "类别:N",
                scale=alt.Scale(domain=["银行", "券商"], range=["#1d4ed8", "#d97706"]),
            ),
            tooltip=["机构:N", "卖出价:Q"],
        )
    )

    combined = (buy_chart + sell_overlay).resolve_scale(
        color="independent"
    )
    st.altair_chart(combined, use_container_width=True)


def render_summary_cards(snapshot: RateSnapshot):
    """渲染顶部概览卡片"""
    pairs = ["USD/CNY", "USD/HKD", "HKD/CNY", "CNY/HKD", "HKD/USD"]
    mid_rates = snapshot.base_mid_rates

    cols = st.columns(len(pairs))
    for i, pair in enumerate(pairs):
        mid = mid_rates.get(pair)
        base, quote = pair.split("/")

        # 找最佳买卖价
        best_buy = snapshot.get_best_buy(pair)
        best_sell = snapshot.get_best_sell(pair)

        with cols[i]:
            st.markdown(
                f"""
            <div class="metric-card">
                <div class="metric-label">{pair}</div>
                <div class="metric-value">{"%.4f" % mid if mid else "N/A"}</div>
                <div class="metric-label">市场中间价</div>
                <div class="metric-sub">
                    最佳买入: {best_buy.institution if best_buy else "N/A"}
                    {" (%.4f)" % best_buy.buy_rate if best_buy else ""}
                </div>
                <div class="metric-sub">
                    最佳卖出: {best_sell.institution if best_sell else "N/A"}
                    {" (%.4f)" % best_sell.sell_rate if best_sell else ""}
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )


def render_ranking(snapshot: RateSnapshot):
    """渲染 TOP 5 汇率排行榜"""

    def _badge_class(rank: int) -> str:
        if rank == 1:
            return "gold"
        elif rank == 2:
            return "silver"
        elif rank == 3:
            return "bronze"
        return "normal"

    def _build_rank_rows(
        rates_list: list, pair: str, sort_by: str, rate_field: str, reverse: bool
    ):
        """构建某货币对某方向的前5排名 HTML"""
        filtered = [r for r in rates_list if r.pair == pair]
        filtered.sort(key=lambda r: getattr(r, sort_by), reverse=reverse)
        top5 = filtered[:5]

        html_parts = []
        for idx, r in enumerate(top5, 1):
            bc = _badge_class(idx)
            tag_class = "bank" if r.category == BANK_CATEGORY else "broker"
            tag_text = "银行" if r.category == BANK_CATEGORY else "券商"
            source = "官方" if r.is_real_data else "估算"
            rate_val = getattr(r, rate_field)
            html_parts.append(
                f'<div class="rank-row">'
                f'<div class="rank-left">'
                f'<div class="rank-badge {bc}">{idx}</div>'
                f'<span class="rank-inst">{r.institution}</span>'
                f'<span class="rank-tag {tag_class}">{tag_text}</span>'
                f'<span style="font-size:0.6rem;color:#9ca3af">({source})</span>'
                f"</div>"
                f'<div>'
                f'<span class="rank-rate">{rate_val:.4f}</span>'
                f'<span class="rank-spread">点差 {r.spread_bps:.0f}bps</span>'
                f"</div>"
                f"</div>"
            )
        return "".join(html_parts)

    pairs = ["USD/CNY", "USD/HKD", "HKD/CNY", "CNY/HKD", "HKD/USD"]
    pair_labels = {
        "USD/CNY": "美元 / 人民币",
        "USD/HKD": "美元 / 港元",
        "HKD/CNY": "港元 / 人民币",
        "CNY/HKD": "人民币 / 港元",
        "HKD/USD": "港元 / 美元",
    }

    st.markdown(
        '<div class="ranking-title">'
        '  <span style="font-size:1.2rem;">🏆</span> 实时排行榜 TOP 5'
        '</div>',
        unsafe_allow_html=True,
    )

    for pair in pairs:
        base, quote = pair.split("/")
        label = pair_labels.get(pair, pair)

        st.markdown(
            f'<div class="ranking-section">'
            f'<div style="font-weight:700;color:#374151;margin-bottom:0.6rem;">'
            f'{label} ({pair})'
            f'</div>'
            f'<div class="ranking-grid">'
            f'<div class="ranking-col">'
            f'<div class="ranking-col-title">'
            f'卖出{base}最划算（买入价最高）'
            f'</div>'
            f'{_build_rank_rows(snapshot.rates, pair, "buy_rate", "buy_rate", reverse=True)}'
            f'</div>'
            f'<div class="ranking-col">'
            f'<div class="ranking-col-title">'
            f'买入{base}最划算（卖出价最低）'
            f'</div>'
            f'{_build_rank_rows(snapshot.rates, pair, "sell_rate", "sell_rate", reverse=False)}'
            f'</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_line_chart(snapshot: RateSnapshot):
    """渲染实时汇率折线图，支持切换时/日/周/月/年"""

    pairs = ["USD/CNY", "USD/HKD", "HKD/CNY", "CNY/HKD", "HKD/USD"]
    pair_labels = {
        "USD/CNY": "美元 / 人民币",
        "USD/HKD": "美元 / 港元",
        "HKD/CNY": "港元 / 人民币",
        "CNY/HKD": "人民币 / 港元",
        "HKD/USD": "港元 / 美元",
    }

    # ---- 控制行：左侧选货币对，右侧切时间范围 ----
    ctl1, ctl2, ctl3 = st.columns([2, 5, 2])
    with ctl1:
        selected_pair = st.selectbox(
            "货币对",
            pairs,
            format_func=lambda p: pair_labels.get(p, p),
            key="line_pair",
        )
    with ctl2:
        time_opts = ["1小时", "1天", "1周", "1月", "1年"]
        selected_range = st.radio(
            "时间范围",
            time_opts,
            horizontal=True,
            index=1,
            key="line_range",
        )

    # ---- 生成模拟历史数据 ----
    range_minutes = {"1小时": 60, "1天": 1440, "1周": 10080, "1月": 43200, "1年": 525600}
    lookback = range_minutes[selected_range]

    interval = min(max(lookback // 24, 1), 1440)
    num_pts = max(lookback // interval, 12)

    vol_map = {
        "USD/CNY": 0.00015, "USD/HKD": 0.00002,
        "HKD/CNY": 0.00010, "CNY/HKD": 0.00010, "HKD/USD": 0.00002,
    }
    vol = vol_map.get(selected_pair, 0.00010)

    current_rates = [r for r in snapshot.rates if r.pair == selected_pair]

    random.seed(42)  # 保证同一页刷新时图表稳定
    now = datetime.now()
    chart_rows = []

    for r in current_rates:
        steps = [random.gauss(0, vol) for _ in range(num_pts - 1)]
        cumsum = [0.0]
        for s in steps:
            cumsum.append(cumsum[-1] + s)

        offset_buy = r.buy_rate - cumsum[-1]
        offset_sell = r.sell_rate - cumsum[-1]

        for i in range(num_pts):
            t = now - timedelta(minutes=interval * (num_pts - 1 - i))
            chart_rows.append({
                "时间": t,
                "机构": r.institution,
                "类别": "银行" if r.category == BANK_CATEGORY else "券商",
                "买入价": round(offset_buy + cumsum[i], 6),
                "卖出价": round(offset_sell + cumsum[i], 6),
            })

    df = pd.DataFrame(chart_rows)

    # ---- 机构筛选 ----
    institutions = sorted(df["机构"].unique().tolist())
    # 把中行排第一，盈透排第二，其余按字母
    priority = ["中国银行", "盈透证券"]
    ordered = [i for i in priority if i in institutions]
    ordered += sorted([i for i in institutions if i not in priority])

    with ctl3:
        show_all = st.checkbox("显示全部", value=False, key="line_show_all")
    if not show_all:
        default_insts = ["中国银行"] if "中国银行" in ordered else ordered[:1]
        selected_insts = st.multiselect(
            "选择机构", ordered, default=default_insts, key="line_insts"
        )
    else:
        selected_insts = ordered

    df = df[df["机构"].isin(selected_insts)]

    # ---- 买入价 / 卖出价 切换 ----
    rate_type = st.radio(
        "查看价格",
        ["买入价 (你卖出基准货币)", "卖出价 (你买入基准货币)"],
        horizontal=True,
        index=0,
        key="line_rate_type",
    )
    y_field = "买入价" if "买入价" in rate_type else "卖出价"
    base, quote = selected_pair.split("/")

    # ---- 颜色映射 ----
    color_palette = [
        "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
        "#ec4899", "#06b6d4", "#84cc16", "#f97316",
    ]
    inst_colors = {inst: color_palette[i % len(color_palette)] for i, inst in enumerate(ordered)}

    # ---- Altair 折线图 ----
    nearest = alt.selection_single(
        nearest=True, on="mouseover", fields=["时间"], empty="none"
    )

    line = (
        alt.Chart(df)
        .mark_line(point=alt.OverlayMarkDef(size=40, filled=True))
        .encode(
            x=alt.X("时间:T", title=None, axis=alt.Axis(grid=True, gridColor="#f3f4f6")),
            y=alt.Y(
                f"{y_field}:Q",
                title=f"汇率 (1 {base} = X {quote})",
                scale=alt.Scale(zero=False),
                axis=alt.Axis(grid=True, gridColor="#f3f4f6"),
            ),
            color=alt.Color(
                "机构:N",
                title=None,
                scale=alt.Scale(domain=list(inst_colors.keys()), range=list(inst_colors.values())),
                legend=alt.Legend(orient="bottom", columns=5, labelFontSize=12),
            ),
            tooltip=[
                alt.Tooltip("时间:T", title="时间", format="%m-%d %H:%M"),
                alt.Tooltip("机构:N", title="机构"),
                alt.Tooltip(f"{y_field}:Q", title=y_field, format=".4f"),
            ],
        )
    )

    # 悬停十字线
    selectors = (
        alt.Chart(df)
        .mark_rule(color="#d1d5db", strokeDash=[3, 3])
        .encode(x="时间:T")
        .add_params(nearest)
    )

    points = line.mark_point().encode(opacity=alt.condition(nearest, alt.value(1), alt.value(0)))

    text = (
        line.mark_text(align="left", dx=5, dy=-10, fontSize=11)
        .encode(text=alt.condition(nearest, f"{y_field}:Q", alt.value(" "), format=".4f"))
    )

    chart = alt.layer(line, selectors, points, text).properties(
        height=380,
    ).configure_view(
        stroke=None,
    )

    st.altair_chart(chart, use_container_width=True)

    # ---- 图例说明 ----
    st.caption(
        "数据为模拟历史走势，基于当前汇率 + 随机游走生成，仅展示趋势形态，"
        "不代表真实历史数据。每次刷新数据会重新生成。"
    )


@st.cache_data(ttl=86400)  # 缓存一天
def _fetch_historical_analysis():
    """从 Yahoo Finance 拉取近一年日线数据并分析最佳购汇时段"""
    import urllib.request
    import json as _json
    import time as _time
    from collections import defaultdict

    tz = datetime.now().astimezone().tzinfo

    def _get_yahoo(symbol, period1, period2, interval="1d"):
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            f"?period1={period1}&period2={period2}&interval={interval}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            data = _json.loads(resp.read())
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            closes = result["indicators"]["quote"][0]["close"]
            return [(ts, c) for ts, c in zip(timestamps, closes) if c is not None]
        except Exception:
            return []

    p2 = int(_time.time())
    p1 = p2 - 365 * 24 * 3600
    day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    results = {}
    for symbol, label, quote in [
        ("CNY=X", "USD/CNY", "CNY"),
        ("HKD=X", "USD/HKD", "HKD"),
    ]:
        data = _get_yahoo(symbol, p1, p2)
        if not data:
            continue

        # 按星期统计
        dow_map = defaultdict(list)
        for ts, rate in data:
            dt = datetime.fromtimestamp(ts, tz=tz)
            if dt.weekday() < 5:  # 仅工作日
                dow_map[dt.weekday()].append(rate)

        dow_stats = []
        for dow, rates in dow_map.items():
            dow_stats.append({
                "day": day_names[dow],
                "dow": dow,
                "avg": round(sum(rates) / len(rates), 4),
                "count": len(rates),
            })
        dow_stats.sort(key=lambda x: x["avg"])

        # 按月统计
        mon_map = defaultdict(list)
        for ts, rate in data:
            dt = datetime.fromtimestamp(ts, tz=tz)
            mon_map[dt.month].append(rate)
        mon_stats = []
        for m, rates in mon_map.items():
            mon_stats.append({
                "month": m,
                "avg": round(sum(rates) / len(rates), 4),
                "count": len(rates),
            })
        mon_stats.sort(key=lambda x: x["avg"])

        # 日内小时级（近7天）
        hp1 = p2 - 7 * 24 * 3600
        hourly_data = _get_yahoo(symbol, hp1, p2, "1h")
        hour_map = defaultdict(list)
        for ts, rate in hourly_data:
            dt = datetime.fromtimestamp(ts, tz=tz)
            if dt.weekday() < 5:
                hour_map[dt.hour].append(rate)
        hour_stats = []
        am_list, pm_list = [], []
        for h, rates in sorted(hour_map.items()):
            avg = round(sum(rates) / len(rates), 4)
            hour_stats.append({"hour": h, "avg": avg, "count": len(rates)})
            if h < 12:
                am_list.extend(rates)
            else:
                pm_list.extend(rates)
        hour_stats.sort(key=lambda x: x["avg"])

        am_avg = round(sum(am_list) / len(am_list), 4) if am_list else None
        pm_avg = round(sum(pm_list) / len(pm_list), 4) if pm_list else None
        better = "下午" if am_avg and pm_avg and pm_avg < am_avg else "上午"

        results[label] = {
            "dow": dow_stats,
            "monthly": mon_stats[:6],
            "hourly": hour_stats,
            "am_avg": am_avg,
            "pm_avg": pm_avg,
            "better_half": better,
            "best_dow": dow_stats[0]["day"] if dow_stats else None,
            "best_month": mon_stats[0]["month"] if mon_stats else None,
        }

    return results


def render_purchase_recommendation(snapshot: RateSnapshot):
    """
    渲染购汇推荐指数卡片（1-5星）
    逻辑：拉取过去一年历史汇率，计算当前汇率在历史中的百分位，
         百分位越低（越接近历史低点）星级越高。
    """
    import urllib.request
    import json as _json
    import time as _time
    from collections import defaultdict

    @st.cache_data(ttl=3600)
    def _fetch_hist_for_recommendation(pair: str, inverse: bool = False, period_days: int = 365):
        """
        获取某货币对指定天数的历史收盘价。
        inverse=True 时返回 1/rate（用于反方向推荐）。
        period_days≥30 用日线，<30 用小时线。
        """
        symbol_map = {
            "USD/CNY": "CNY=X",
            "USD/HKD": "HKD=X",
            "CNY/HKD": "CNYHKD=X",
        }
        symbol = symbol_map.get(pair)
        if not symbol:
            return []
        p2 = int(_time.time())
        p1 = p2 - period_days * 24 * 3600
        interval = "1d" if period_days >= 30 else "1h"
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            f"?period1={p1}&period2={p2}&interval={interval}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            data = _json.loads(resp.read())
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            closes = result["indicators"]["quote"][0]["close"]
            pairs = [(ts, (1 / c if inverse else c)) for ts, c in zip(timestamps, closes) if c is not None]
            return pairs
        except Exception:
            return []

    def _calc_stars(current_rate, hist_rates, higher_is_better: bool = False, period_label: str = "过去一年"):
        """
        根据当前汇率在历史数据中的百分位返回 (星级, 百分位, 理由, 标签)。
        higher_is_better=True  → 汇率越高越推荐（如美元换港元，越高换得越多）
        higher_is_better=False → 汇率越低越推荐（如人民币换美元，越低越便宜）
        """
        if not hist_rates or current_rate is None:
            return None, None, "数据不足", ""
        sorted_rates = sorted(hist_rates)
        n = len(sorted_rates)

        if higher_is_better:
            # 越高越推荐：百分位越高星级越高
            rank = sum(1 for r in sorted_rates if r <= current_rate)
            percentile = rank / n  # 高 = 接近历史高点 = 好
            if percentile >= 0.85:
                stars, label = 5, "非常推荐"
            elif percentile >= 0.65:
                stars, label = 4, "比较推荐"
            elif percentile >= 0.45:
                stars, label = 3, "可以购汇"
            elif percentile >= 0.25:
                stars, label = 2, "不太划算"
            else:
                stars, label = 1, "暂不推荐"
        else:
            # 越低越推荐：百分位越低星级越高
            rank = sum(1 for r in sorted_rates if r <= current_rate)
            percentile = rank / n
            if percentile <= 0.15:
                stars, label = 5, "非常推荐"
            elif percentile <= 0.35:
                stars, label = 4, "比较推荐"
            elif percentile <= 0.55:
                stars, label = 3, "可以购汇"
            elif percentile <= 0.75:
                stars, label = 2, "不太划算"
            else:
                stars, label = 1, "暂不推荐"

        direction_desc = "越高越划算" if higher_is_better else "越低越划算"
        reason = (
            f"处于{period_label} {percentile*100:.0f}% 分位"
            f"（{direction_desc}，区间 {sorted_rates[0]:.6g} ~ {sorted_rates[-1]:.6g}）"
        )
        return stars, percentile, reason, label

    # 推荐指数配置：同一 Yahoo 数据源可以同时服务正反两个方向
    # higher_is_better: True  → 汇率越高越推荐（如美元换港元，换得越多越好）
    # higher_is_better: False → 汇率越低越推荐（如人民币换美元，越低越便宜）
    rec_configs = [
        {
            "yahoo_pair": "USD/CNY",
            "display_pair": "USD/CNY",
            "direction": "用人民币买美元",
            "inverse": False,
            "higher_is_better": False,
        },
        {
            "yahoo_pair": "USD/HKD",
            "display_pair": "USD/HKD",
            "direction": "用港元买美元",
            "inverse": False,
            "higher_is_better": False,
        },
        {
            "yahoo_pair": "CNY/HKD",
            "display_pair": "CNY/HKD",
            "direction": "人民币换港元",
            "inverse": False,
            "higher_is_better": True,
        },
        {
            "yahoo_pair": "USD/HKD",
            "display_pair": "HKD/USD",
            "direction": "美元换港元",
            "inverse": False,
            "higher_is_better": True,
        },
    ]

    results = {}
    for cfg in rec_configs:
        pair_key = cfg["yahoo_pair"]
        mid = snapshot.base_mid_rates.get(pair_key)
        if mid is None:
            continue

        # 当前汇率（反方向时取倒数）
        current_rate = (1 / mid) if cfg["inverse"] else mid

        # 过去一年数据
        hist_year = _fetch_hist_for_recommendation(pair_key, inverse=cfg["inverse"], period_days=365)
        # 近一周数据
        hist_week = _fetch_hist_for_recommendation(pair_key, inverse=cfg["inverse"], period_days=7)

        if not hist_year and not hist_week:
            continue

        # 计算两个维度的星级
        hb = cfg["higher_is_better"]
        yr_result = None
        wk_result = None

        if hist_year:
            yr_rates = [r for _, r in hist_year]
            yr_result = _calc_stars(current_rate, yr_rates, higher_is_better=hb, period_label="过去一年")

        if hist_week:
            wk_rates = [r for _, r in hist_week]
            wk_result = _calc_stars(current_rate, wk_rates, higher_is_better=hb, period_label="近一周")

        if yr_result is None and wk_result is None:
            continue

        results[cfg["display_pair"]] = {
            "current": current_rate,
            "direction": cfg["direction"],
            "year": yr_result if yr_result and yr_result[0] is not None else None,
            "week": wk_result if wk_result and wk_result[0] is not None else None,
            "yr_low": min(yr_rates) if hist_year else None,
            "yr_high": max(yr_rates) if hist_year else None,
            "wk_low": min(wk_rates) if hist_week else None,
            "wk_high": max(wk_rates) if hist_week else None,
        }

    if not results:
        st.info("暂无足够历史数据计算推荐指数")
        return

    # ---- 渲染 UI ----
    st.markdown(
        '<div class="section-header">⭐ 购汇推荐指数</div>',
        unsafe_allow_html=True,
    )

    # 星级显示的 CSS
    st.markdown(
        """
        <style>
        .rec-card {
            background: linear-gradient(135deg, #fefce8 0%, #f0fdf4 100%);
            border: 1px solid #bbf7d0;
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 12px;
        }
        .rec-pair { font-size: 1rem; font-weight: 700; color: #1e293b; margin-bottom: 2px; }
        .rec-dir { font-size: 0.72rem; color: #9ca3af; margin-bottom: 10px; }
        .rec-row {
            display: flex; align-items: center; gap: 10px;
            margin-bottom: 6px; font-size: 0.85rem;
        }
        .rec-row .rec-period { width: 64px; font-size: 0.72rem; color: #6b7280; text-align: right; }
        .rec-row .rec-star { font-size: 1.2rem; letter-spacing: 2px; }
        .rec-label {
            display: inline-block;
            padding: 1px 8px;
            border-radius: 20px;
            font-size: 0.68rem;
            font-weight: 600;
        }
        .rec-label.star5 { background: #dcfce7; color: #166534; }
        .rec-label.star4 { background: #dbeafe; color: #1e40af; }
        .rec-label.star3 { background: #fef9c3; color: #854d0e; }
        .rec-label.star2 { background: #ffedd5; color: #9a3412; }
        .rec-label.star1 { background: #fee2e2; color: #991b1b; }
        .rec-reason { font-size: 0.68rem; color: #9ca3af; margin-left: 4px; }
        .rec-detail {
            display: flex; gap: 12px; flex-wrap: wrap;
            margin-top: 10px; font-size: 0.72rem; color: #9ca3af;
        }
        .rec-detail span {
            background: white; padding: 2px 8px; border-radius: 4px;
            border: 1px solid #e5e7eb;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 2×2 排列，每行 2 张卡片
    rec_items = list(results.items())
    for row_start in range(0, len(rec_items), 2):
        cols = st.columns(2)
        for j in range(2):
            idx = row_start + j
            if idx >= len(rec_items):
                break
            pair, info = rec_items[idx]

            # 构建双行评级
            ratings_html = ""
            for period_key, label in [("year", "过去一年"), ("week", "近一周")]:
                r = info.get(period_key)
                if r is None:
                    ratings_html += (
                        f'<div class="rec-row">'
                        f'<span class="rec-period">{label}</span>'
                        f'<span class="rec-star" style="color:#d1d5db;">☆☆☆☆☆</span>'
                        f'<span class="rec-label star1">数据不足</span>'
                        f'</div>'
                    )
                else:
                    stars, percentile, reason, tag = r
                    star_str = "★" * stars + "☆" * (5 - stars)
                    label_class = f"star{stars}"
                    ratings_html += (
                        f'<div class="rec-row">'
                        f'<span class="rec-period">{label}</span>'
                        f'<span class="rec-star">{star_str}</span>'
                        f'<span class="rec-label {label_class}">{tag}</span>'
                        f'<span class="rec-reason">{reason}</span>'
                        f'</div>'
                    )

            # 构建详情行
            detail_parts = [f'<span>当前 {info["current"]:.6g}</span>']
            if info.get("yr_low") is not None:
                detail_parts.append(f'<span>年内低 {info["yr_low"]:.6g}</span>')
                detail_parts.append(f'<span>年内高 {info["yr_high"]:.6g}</span>')
            if info.get("wk_low") is not None:
                detail_parts.append(f'<span>周内低 {info["wk_low"]:.6g}</span>')
                detail_parts.append(f'<span>周内高 {info["wk_high"]:.6g}</span>')

            with cols[j]:
                st.markdown(
                    f'<div class="rec-card">'
                    f'<div class="rec-pair">{pair}</div>'
                    f'<div class="rec-dir">{info["direction"]}</div>'
                    f'{ratings_html}'
                    f'<div class="rec-detail">{"".join(detail_parts)}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    st.caption(
        "★ 推荐指数说明：过去一年基于日线数据，近一周基于小时线数据。"
        "绿色方向（人民币买美元、港元买美元）：汇率越低越划算；"
        "蓝色方向（人民币换港元、美元换港元）：汇率越高越划算。"
        "数据来源：Yahoo Finance，仅供参考，不构成投资建议。"
    )


def render_best_time_card():
    """渲染最佳购汇时机分析卡片"""
    with st.spinner("正在分析历史汇率数据..."):
        analysis = _fetch_historical_analysis()

    if not analysis:
        st.warning("无法获取历史数据进行分析")
        return

    st.markdown("""
    <style>
    .time-card { background: linear-gradient(135deg, #f0f9ff 0%, #ecfdf5 100%);
        border-radius: 12px; padding: 20px; margin: 16px 0; border: 1px solid #d1d5db; }
    .time-card h4 { margin: 0 0 12px 0; color: #1f2937; font-size: 1.05rem; }
    .time-row { display: flex; gap: 16px; flex-wrap: wrap; }
    .time-col { flex: 1; min-width: 220px; background: white; border-radius: 8px;
        padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
    .time-label { font-size: 0.75rem; color: #6b7280; margin-bottom: 4px; }
    .time-value { font-size: 1.1rem; font-weight: 700; color: #059669; }
    .time-value.warn { color: #dc2626; }
    .time-sub { font-size: 0.7rem; color: #9ca3af; margin-top: 2px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-header">⏰ 最佳购汇时机分析（基于近一年真实市场数据）</div>',
        unsafe_allow_html=True,
    )

    for pair_label, info in analysis.items():
        base, quote = pair_label.split("/")

        # ---- 卡片标题 ----
        st.markdown(f"#### {pair_label}（购{base}，花{quote}）")

        # ---- 三个维度卡片横排 ----
        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown('<div class="time-card">', unsafe_allow_html=True)
            st.markdown(f"<h4>📅 最佳星期</h4>", unsafe_allow_html=True)
            if info["dow"]:
                best = info["dow"][0]
                worst = info["dow"][-1]
                spread = round((worst["avg"] - best["avg"]) * 10000, 1)
                st.markdown(
                    f'<div class="time-label">最划算</div>'
                    f'<div class="time-value">{best["day"]}（均价 {best["avg"]:.4f}）</div>'
                    f'<div class="time-sub">比最差的{worst["day"]}省 {spread} bps</div>',
                    unsafe_allow_html=True,
                )

                # 微型条形图：各天排名
                rows = []
                for i, d in enumerate(info["dow"]):
                    color = "#059669" if i == 0 else ("#dc2626" if i == len(info["dow"]) - 1 else "#9ca3af")
                    bar_w = max(8, int(100 - (d["avg"] - info["dow"][0]["avg"]) * 800))
                    rows.append(
                        f'<div style="display:flex;align-items:center;margin:4px 0;font-size:0.7rem;">'
                        f'<span style="width:36px;text-align:right;margin-right:6px;color:{color};">'
                        f'{d["day"]}</span>'
                        f'<span style="flex:1;height:10px;background:#e5e7eb;border-radius:5px;overflow:hidden;">'
                        f'<span style="display:block;width:{bar_w}%;height:100%;background:{color};'
                        f'border-radius:5px;"></span></span>'
                        f'<span style="width:52px;text-align:right;margin-left:6px;color:{color};">'
                        f'{d["avg"]:.4f}</span></div>'
                    )
                st.markdown("".join(rows), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="time-card">', unsafe_allow_html=True)
            st.markdown(f"<h4>🕐 最佳时段</h4>", unsafe_allow_html=True)
            if info["hourly"]:
                best_h = info["hourly"][0]
                am = info.get("am_avg")
                pm = info.get("pm_avg")
                st.markdown(
                    f'<div class="time-label">日内最优点</div>'
                    f'<div class="time-value">{best_h["hour"]:02d}:00 左右</div>',
                    unsafe_allow_html=True,
                )
                if am and pm:
                    diff = abs(am - pm)
                    st.markdown(
                        f'<div class="time-label" style="margin-top:8px;">上 / 下午对比</div>'
                        f'<div style="font-size:0.8rem;margin-top:2px;">'
                        f'上午均价 {am:.4f} &nbsp;|&nbsp; 下午均价 {pm:.4f}</div>'
                        f'<div class="time-value" style="font-size:0.9rem;">'
                        f'{info["better_half"]}更优'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            st.markdown("</div>", unsafe_allow_html=True)

        with c3:
            st.markdown('<div class="time-card">', unsafe_allow_html=True)
            st.markdown(f"<h4>📆 最佳月份</h4>", unsafe_allow_html=True)
            if info["monthly"]:
                best_m = info["monthly"][0]
                st.markdown(
                    f'<div class="time-value">{best_m["month"]}月（均价 {best_m["avg"]:.4f}）</div>',
                    unsafe_allow_html=True,
                )
                # 列出前3
                top3 = info["monthly"][:3]
                for i, m in enumerate(top3):
                    icon = "🥇" if i == 0 else ("🥈" if i == 1 else "🥉")
                    st.markdown(
                        f'<div style="font-size:0.75rem;margin:2px 0;">'
                        f'{icon} {m["month"]}月：{m["avg"]:.4f}</div>',
                        unsafe_allow_html=True,
                    )
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

    st.caption("💡 数据来源：Yahoo Finance 近一年日线 + 近7天小时级数据。汇率越低 = 花更少人民币/港元买外币。历史规律仅供参考，不构成投资建议。")


def render_data_source_info(snapshot: RateSnapshot):
    """渲染数据来源说明"""
    with st.expander("数据来源说明", expanded=False):
        real_sources = [r for r in snapshot.rates if r.is_real_data]
        sim_sources = [r for r in snapshot.rates if not r.is_real_data]

        st.markdown("#### 真实数据来源")
        if real_sources:
            for r in real_sources:
                st.markdown(f"- **{r.institution}** ({r.pair}): {r.source_label}")
        else:
            st.markdown("- 暂无真实数据，所有银行/券商数据均为估算")

        st.markdown("#### 估算数据说明")
        st.markdown(
            """
        - 未标注「官方」的银行/券商汇率基于市场中间价 + 机构典型点差估算
        - 中国银行数据来自其官网公开外汇牌价页面
        - 市场中间价来自 open.er-api.com (更新频率: 每日)
        - 估算数据仅供参考，实际交易请以各机构实时报价为准
        """
        )

        st.markdown("#### 机构点差说明 (估算)")
        st.markdown(
            """
        | 机构 | USD/CNY | USD/HKD | HKD/CNY | CNY/HKD | HKD/USD |
        |------|---------|---------|---------|---------|---------|
        | 中国银行 | 官方数据 | 交叉汇率 | 官方数据 | 交叉汇率 | 交叉汇率 |
        | 建设银行 | ~30 bps | ~40 bps | ~40 bps | ~40 bps | ~40 bps |
        | 建设银行亚洲 | ~28 bps | ~12 bps | ~28 bps | ~28 bps | ~12 bps |
        | 兴业银行 | ~32 bps | ~44 bps | ~44 bps | ~44 bps | ~44 bps |
        | 汇丰香港 | ~20 bps | ~16 bps | ~24 bps | ~24 bps | ~16 bps |
        | 众安银行 | ~12 bps | ~10 bps | ~16 bps | ~16 bps | ~10 bps |
        | 复星恒利 | ~16 bps | ~12 bps | ~20 bps | ~20 bps | ~12 bps |
        | 盈立证券 | ~16 bps | ~12 bps | ~20 bps | ~20 bps | ~12 bps |
        | 盈透证券 | ~4 bps | ~4 bps | ~6 bps | ~6 bps | ~4 bps |
        """
        )


# ============================================================
# 主页面
# ============================================================


def main():
    # 页面头部
    auto_refresh = render_header()

    # 获取数据
    cache_buster = int(time.time()) if auto_refresh else 0
    snapshot = fetch_rates_cached(cache_buster)

    # 状态栏
    render_status_bar(snapshot)

    st.divider()

    # 概览卡片
    render_summary_cards(snapshot)

    st.divider()

    # TOP 5 排行榜
    with st.expander("🏆 实时排行榜 TOP 5", expanded=True):
        render_ranking(snapshot)

    st.divider()

    # 实时折线图
    with st.expander("📈 实时价格走势", expanded=True):
        render_line_chart(snapshot)

    st.divider()

    # Tab: 五个货币对
    tabs = st.tabs(
        [
            "USD / CNY (美元兑人民币)",
            "USD / HKD (美元兑港元)",
            "HKD / CNY (港元兑人民币)",
            "CNY / HKD (人民币兑港元)",
            "HKD / USD (港元兑美元)",
        ]
    )

    pairs = ["USD/CNY", "USD/HKD", "HKD/CNY", "CNY/HKD", "HKD/USD"]

    for pair, tab in zip(pairs, tabs):
        with tab:
            # 银行对比
            st.markdown(
                f'<div class="section-title">银行汇率对比 — {pair}</div>',
                unsafe_allow_html=True,
            )
            render_rate_table(snapshot.rates, pair, BANK_CATEGORY, snapshot)

            st.markdown("---")

            # 券商对比
            st.markdown(
                f'<div class="section-title">券商汇率对比 — {pair}</div>',
                unsafe_allow_html=True,
            )
            render_rate_table(snapshot.rates, pair, BROKER_CATEGORY, snapshot)

            st.markdown("---")

            # 图表
            render_chart(snapshot.rates, pair, snapshot)

    # 购汇推荐指数
    st.divider()
    render_purchase_recommendation(snapshot)

    # 最佳购汇时机分析
    st.divider()
    render_best_time_card()

    # 数据来源说明
    st.divider()
    render_data_source_info(snapshot)

    # 自动刷新逻辑
    if auto_refresh:
        time.sleep(60)
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
