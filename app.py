"""
多银行/多券商实时汇率对比监控
支持: CNY, HKD, USD 之间的兑换汇率对比
"""

import time
from datetime import datetime

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
