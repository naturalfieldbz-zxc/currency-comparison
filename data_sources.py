"""
汇率数据获取模块
支持的数据源：
- 中国银行 (BOC) 官网：真实外汇牌价
- open.er-api.com：免费基准汇率
- 模拟数据：其他银行/券商（基于基准汇率 + 机构点差）
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

# ============================================================
# 数据结构
# ============================================================


@dataclass
class RateQuote:
    """单个机构的汇率报价"""

    institution: str  # 机构名称
    category: str  # "bank" 或 "broker"
    base_currency: str  # 基准货币 (如 USD)
    quote_currency: str  # 标价货币 (如 CNY)
    buy_rate: float  # 机构买入基准货币的价格（你卖出的价格）
    sell_rate: float  # 机构卖出基准货币的价格（你买入的价格）
    mid_rate: float  # 中间价
    spread_bps: float  # 买卖点差 (基点)
    timestamp: datetime  # 数据时间
    is_real_data: bool = False  # 是否为真实数据
    source_label: str = ""  # 数据来源说明

    @property
    def pair(self) -> str:
        return f"{self.base_currency}/{self.quote_currency}"


@dataclass
class RateSnapshot:
    """某一时刻所有机构的汇率快照"""

    rates: List[RateQuote] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    base_mid_rates: Dict[str, float] = field(default_factory=dict)

    def get_by_pair(self, pair: str) -> List[RateQuote]:
        return [r for r in self.rates if r.pair == pair]

    def get_best_buy(self, pair: str) -> Optional[RateQuote]:
        """对用户最有利的买入价（机构买入价最高的 = 你卖出时拿到的钱最多）"""
        candidates = self.get_by_pair(pair)
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.buy_rate)

    def get_best_sell(self, pair: str) -> Optional[RateQuote]:
        """对用户最有利的卖出价（机构卖出价最低的 = 你买入时花的钱最少）"""
        candidates = self.get_by_pair(pair)
        if not candidates:
            return None
        return min(candidates, key=lambda r: r.sell_rate)


# ============================================================
# 机构点差配置（基点, 万分之一）
# 格式: (买入偏移, 卖出偏移) — 相对于中间价
# ============================================================

INSTITUTION_SPREADS: Dict[str, Dict[str, Tuple[float, float]]] = {
    "建设银行": {
        "USD/CNY": (15, 15),
        "USD/HKD": (20, 20),
        "HKD/CNY": (20, 20),
        "CNY/HKD": (20, 20),
        "HKD/USD": (20, 20),
    },
    "建设银行亚洲": {
        "USD/CNY": (14, 14),
        "USD/HKD": (6, 6),
        "HKD/CNY": (14, 14),
        "CNY/HKD": (14, 14),
        "HKD/USD": (6, 6),
    },
    "兴业银行": {
        "USD/CNY": (16, 16),
        "USD/HKD": (22, 22),
        "HKD/CNY": (22, 22),
        "CNY/HKD": (22, 22),
        "HKD/USD": (22, 22),
    },
    "汇丰香港": {
        "USD/CNY": (10, 10),
        "USD/HKD": (8, 8),
        "HKD/CNY": (12, 12),
        "CNY/HKD": (12, 12),
        "HKD/USD": (8, 8),
    },
    "众安银行": {
        "USD/CNY": (6, 6),
        "USD/HKD": (5, 5),
        "HKD/CNY": (8, 8),
        "CNY/HKD": (8, 8),
        "HKD/USD": (5, 5),
    },
    "复星恒利": {
        "USD/CNY": (8, 8),
        "USD/HKD": (6, 6),
        "HKD/CNY": (10, 10),
        "CNY/HKD": (10, 10),
        "HKD/USD": (6, 6),
    },
    "盈立证券": {
        "USD/CNY": (8, 8),
        "USD/HKD": (6, 6),
        "HKD/CNY": (10, 10),
        "CNY/HKD": (10, 10),
        "HKD/USD": (6, 6),
    },
    "盈透证券": {
        "USD/CNY": (2, 2),
        "USD/HKD": (2, 2),
        "HKD/CNY": (3, 3),
        "CNY/HKD": (3, 3),
        "HKD/USD": (2, 2),
    },
}

BANK_CATEGORY = "bank"
BROKER_CATEGORY = "broker"

BOC_BANK_LIST = ["中国银行"]
SIMULATED_BANK_LIST = ["建设银行", "建设银行亚洲", "兴业银行", "汇丰香港", "众安银行"]
SIMULATED_BROKER_LIST = ["复星恒利", "盈立证券", "盈透证券"]

# ============================================================
# 数据获取函数
# ============================================================


def fetch_free_api_rates() -> Dict[str, float]:
    """
    从 open.er-api.com 获取基准汇率（中间价）
    返回: {"USD/CNY": 6.77, "USD/HKD": 7.84, "HKD/CNY": 0.864, ...}
    """
    try:
        resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("result") != "success":
            raise ValueError(f"API returned error: {data}")

        rates = data["rates"]
        usd_cny = rates.get("CNY")
        usd_hkd = rates.get("HKD")

        if not usd_cny or not usd_hkd:
            raise ValueError("Missing CNY or HKD rate")

        hkd_cny = usd_cny / usd_hkd
        cny_hkd = 1 / hkd_cny
        hkd_usd = 1 / usd_hkd

        return {
            "USD/CNY": usd_cny,
            "USD/HKD": usd_hkd,
            "HKD/CNY": hkd_cny,
            "CNY/HKD": cny_hkd,
            "HKD/USD": hkd_usd,
        }
    except Exception as e:
        print(f"[free-api] 获取失败: {e}")
        return {}


def fetch_boc_rates() -> List[RateQuote]:
    """
    从中国银行官网抓取外汇牌价
    BOC 页面上显示的是 100 外币兑人民币的价格
    返回 RateQuote 列表（已转换为 1 外币的价格）
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        resp = requests.get(
            "https://www.boc.cn/sourcedb/whpj/", headers=headers, timeout=15
        )
        resp.encoding = "utf-8"
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # BOC 牌价在表格中，每行格式:
        # <tr>
        #   <td>货币名称</td>
        #   <td>现汇买入价</td>
        #   <td>现钞买入价</td>
        #   <td>现汇卖出价</td>
        #   <td>现钞卖出价</td>
        #   <td>中行折算价</td>
        #   <td>发布日期</td>
        #   <td>发布时间</td>
        # </tr>
        rows = soup.find_all("tr")
        rates = []

        # 提取发布时间
        publish_time = datetime.now()
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 8:
                continue
            currency_name = cells[0].get_text(strip=True)

            if "美元" not in currency_name and "港币" not in currency_name:
                continue

            try:
                # BOC 格式：100 外币的价格
                spot_buy_100 = float(cells[1].get_text(strip=True))
                spot_sell_100 = float(cells[3].get_text(strip=True))
                mid_100 = float(cells[5].get_text(strip=True))
                date_str = cells[6].get_text(strip=True)
                time_str = cells[7].get_text(strip=True)

                # 转换为 1 外币的价格
                spot_buy = spot_buy_100 / 100.0
                spot_sell = spot_sell_100 / 100.0
                mid_rate = mid_100 / 100.0

                # 解析时间
                try:
                    dt_str = f"{date_str} {time_str}"
                    publish_time = datetime.strptime(dt_str, "%Y/%m/%d %H:%M:%S")
                except ValueError:
                    publish_time = datetime.now()

                if "美元" in currency_name:
                    base, quote = "USD", "CNY"
                else:
                    base, quote = "HKD", "CNY"

                spread_bps = (spot_sell - spot_buy) / mid_rate * 10000

                rates.append(
                    RateQuote(
                        institution="中国银行",
                        category=BANK_CATEGORY,
                        base_currency=base,
                        quote_currency=quote,
                        buy_rate=round(spot_buy, 6),
                        sell_rate=round(spot_sell, 6),
                        mid_rate=round(mid_rate, 6),
                        spread_bps=round(spread_bps, 1),
                        timestamp=publish_time,
                        is_real_data=True,
                        source_label=f"中国银行官网 {date_str} {time_str}",
                    )
                )
            except (ValueError, IndexError):
                continue

        # 如果BOC同时提供了USD和HKD数据，计算USD/HKD交叉汇率
        usd_rate = next((r for r in rates if r.pair == "USD/CNY"), None)
        hkd_rate = next((r for r in rates if r.pair == "HKD/CNY"), None)

        if usd_rate and hkd_rate and usd_rate.buy_rate > 0 and hkd_rate.sell_rate > 0:
            usd_hkd_buy = usd_rate.buy_rate / hkd_rate.sell_rate
            usd_hkd_sell = usd_rate.sell_rate / hkd_rate.buy_rate
            usd_hkd_mid = (usd_hkd_buy + usd_hkd_sell) / 2
            usd_hkd_spread = (usd_hkd_sell - usd_hkd_buy) / usd_hkd_mid * 10000

            rates.append(
                RateQuote(
                    institution="中国银行",
                    category=BANK_CATEGORY,
                    base_currency="USD",
                    quote_currency="HKD",
                    buy_rate=round(usd_hkd_buy, 6),
                    sell_rate=round(usd_hkd_sell, 6),
                    mid_rate=round(usd_hkd_mid, 6),
                    spread_bps=round(usd_hkd_spread, 1),
                    timestamp=publish_time,
                    is_real_data=False,
                    source_label="交叉汇率 (USD/CNY ÷ HKD/CNY)",
                )
            )

            # CNY/HKD 交叉汇率（逆 HKD/CNY）
            cny_hkd_buy = 1 / hkd_rate.sell_rate
            cny_hkd_sell = 1 / hkd_rate.buy_rate
            cny_hkd_mid = 1 / hkd_rate.mid_rate
            cny_hkd_spread = (cny_hkd_sell - cny_hkd_buy) / cny_hkd_mid * 10000

            rates.append(
                RateQuote(
                    institution="中国银行",
                    category=BANK_CATEGORY,
                    base_currency="CNY",
                    quote_currency="HKD",
                    buy_rate=round(cny_hkd_buy, 6),
                    sell_rate=round(cny_hkd_sell, 6),
                    mid_rate=round(cny_hkd_mid, 6),
                    spread_bps=round(cny_hkd_spread, 1),
                    timestamp=publish_time,
                    is_real_data=False,
                    source_label="交叉汇率 (1 ÷ HKD/CNY)",
                )
            )

            # HKD/USD 交叉汇率（逆 USD/HKD）
            hkd_usd_buy = 1 / usd_hkd_sell
            hkd_usd_sell = 1 / usd_hkd_buy
            hkd_usd_mid = 1 / usd_hkd_mid
            hkd_usd_spread = (hkd_usd_sell - hkd_usd_buy) / hkd_usd_mid * 10000

            rates.append(
                RateQuote(
                    institution="中国银行",
                    category=BANK_CATEGORY,
                    base_currency="HKD",
                    quote_currency="USD",
                    buy_rate=round(hkd_usd_buy, 6),
                    sell_rate=round(hkd_usd_sell, 6),
                    mid_rate=round(hkd_usd_mid, 6),
                    spread_bps=round(hkd_usd_spread, 1),
                    timestamp=publish_time,
                    is_real_data=False,
                    source_label="交叉汇率 (1 ÷ USD/HKD)",
                )
            )

        return rates

    except Exception as e:
        print(f"[boc] 获取失败: {e}")
        return []


def generate_simulated_rate(
    institution: str,
    category: str,
    base: str,
    quote: str,
    mid_rate: float,
    buy_offset_bps: float,
    sell_offset_bps: float,
) -> RateQuote:
    """根据中间价和点差生成模拟汇率"""
    buy_rate = mid_rate * (1 - buy_offset_bps / 10000)
    sell_rate = mid_rate * (1 + sell_offset_bps / 10000)
    spread_bps = buy_offset_bps + sell_offset_bps

    return RateQuote(
        institution=institution,
        category=category,
        base_currency=base,
        quote_currency=quote,
        buy_rate=round(buy_rate, 6),
        sell_rate=round(sell_rate, 6),
        mid_rate=round(mid_rate, 6),
        spread_bps=round(spread_bps, 1),
        timestamp=datetime.now(),
        is_real_data=False,
        source_label="基于市场中间价估算，仅供参考",
    )


def generate_simulated_rates(mid_rates: Dict[str, float]) -> List[RateQuote]:
    """为所有非BOC机构生成模拟汇率"""
    rates = []

    for inst_name in SIMULATED_BANK_LIST:
        spreads = INSTITUTION_SPREADS.get(inst_name, {})
        for pair, mid in mid_rates.items():
            base, quote = pair.split("/")
            buy_off, sell_off = spreads.get(pair, (15, 15))
            rates.append(
                generate_simulated_rate(
                    inst_name, BANK_CATEGORY, base, quote, mid, buy_off, sell_off
                )
            )

    for inst_name in SIMULATED_BROKER_LIST:
        spreads = INSTITUTION_SPREADS.get(inst_name, {})
        for pair, mid in mid_rates.items():
            base, quote = pair.split("/")
            buy_off, sell_off = spreads.get(pair, (8, 8))
            rates.append(
                generate_simulated_rate(
                    inst_name, BROKER_CATEGORY, base, quote, mid, buy_off, sell_off
                )
            )

    return rates


def get_all_rates() -> RateSnapshot:
    """
    聚合所有数据源，返回完整的汇率快照
    如果BOC数据获取失败，中国银行也使用模拟数据
    """
    snapshot = RateSnapshot(timestamp=datetime.now())

    # 1. 获取基准中间价
    mid_rates = fetch_free_api_rates()
    if not mid_rates:
        # 使用硬编码的 fallback 值
        fallback_hkd_cny = 6.77 / 7.84
        mid_rates = {
            "USD/CNY": 6.77,
            "USD/HKD": 7.84,
            "HKD/CNY": fallback_hkd_cny,
            "CNY/HKD": 1 / fallback_hkd_cny,
            "HKD/USD": 1 / 7.84,
        }
        snapshot.base_mid_rates = mid_rates
    else:
        snapshot.base_mid_rates = mid_rates

    # 2. 尝试获取中国银行真实数据
    boc_rates = fetch_boc_rates()

    if boc_rates:
        snapshot.rates.extend(boc_rates)
    else:
        # BOC 获取失败，用模拟数据代替
        boc_spreads = {
            "USD/CNY": (15, 15), "USD/HKD": (20, 20), "HKD/CNY": (20, 20),
            "CNY/HKD": (20, 20), "HKD/USD": (20, 20),
        }
        for pair, mid in mid_rates.items():
            base, quote = pair.split("/")
            buy_off, sell_off = boc_spreads.get(pair, (15, 15))
            snapshot.rates.append(
                generate_simulated_rate(
                    "中国银行",
                    BANK_CATEGORY,
                    base,
                    quote,
                    mid,
                    buy_off,
                    sell_off,
                )
            )
            # 标记中国银行模拟数据
            snapshot.rates[-1].source_label = "模拟数据 (BOC官网获取失败)"

    # 3. 生成其他机构的模拟汇率
    simulated = generate_simulated_rates(mid_rates)
    snapshot.rates.extend(simulated)

    return snapshot


# ============================================================
# 辅助函数
# ============================================================


def format_rate(rate: float, pair: str) -> str:
    """格式化汇率显示"""
    if "JPY" in pair or "KRW" in pair:
        return f"{rate:.4f}"
    return f"{rate:.4f}"


def get_rate_change_label(buy: float, sell: float, mid: float) -> str:
    """计算买卖价差相对于中间价的百分比"""
    spread_pct = (sell - buy) / mid * 100
    return f"{spread_pct:.3f}%"
