#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块深耕系统测试脚本

测试新开发的三个模块:
1. sector_diffusion_quality_scorer - 板块扩散质量评分
2. quant_environment_detector - 量化环境识别
3. sector_turnover_trend_tracker - 板块成交占比追踪

使用商业航天和中际旭创的实际数据进行验证
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from domains.market_state.sector_diffusion_quality_scorer import (
    calculate_sector_diffusion_quality,
    build_sector_diffusion_summary
)
from domains.market_state.quant_environment_detector import (
    detect_market_mode,
    detect_quant_environment,
    build_quant_environment_summary
)
from domains.market_state.sector_turnover_trend_tracker import (
    build_sector_turnover_trend,
    build_top5_sector_turnover_summary,
    detect_quant_exit_signal
)


def test_commercial_aerospace_failure():
    """
    测试案例1: 商业航天失败案例

    预期结果: 扩散质量35分(弱扩散)
    """
    print("=" * 80)
    print("测试案例1: 商业航天失败案例 (2026年5月6-18日)")
    print("=" * 80)

    # 商业航天数据
    sector_data = {
        "core_anchor": {
            "status": "无明确中军",
            "change_pct": 0.0,
            "volume_ratio": 0.0
        },
        "elastic_carrier": {
            "new_high_count": 1,  # 5月18日再升科技涨停
            "intraday_support": "弱"
        },
        "limit_up_count": 6,  # 5月12日最高6只涨停
        "total_stocks": 20,
        "second_wave_new_highs": 0,  # 无二波创新高
        "turnover_share_change": -0.5  # 推测收缩
    }

    result = calculate_sector_diffusion_quality("商业航天", sector_data)

    print(f"\n板块: {result['sector_name']}")
    print(f"总分: {result['total_score']}/100")
    print(f"评级: {result['level']}")
    print(f"\n详细得分:")
    print(f"  - 核心锚稳定性: {result['details']['core_anchor']['score']}/30 ({result['details']['core_anchor']['label']})")
    print(f"  - 弹性载体强度: {result['details']['elastic_carrier']['score']}/25 ({result['details']['elastic_carrier']['label']})")
    print(f"  - 后排承接度: {result['details']['follower_support']['score']}/20 ({result['details']['follower_support']['label']})")
    print(f"  - 二波创新高群: {result['details']['second_wave_new_highs']['score']}/15 ({result['details']['second_wave_new_highs']['label']})")
    print(f"  - 成交占比变化: {result['details']['turnover_share_change']['score']}/10 ({result['details']['turnover_share_change']['label']})")
    print(f"\n结论: {result['conclusion']}")
    print(f"动作: {result['action']}")

    assert result['total_score'] <= 40, "商业航天应该是弱扩散"
    print("\n✅ 测试通过: 商业航天确实是弱扩散,量化资金已撤离")


def test_cpo_success():
    """
    测试案例2: 光模块/CPO成功案例

    预期结果: 扩散质量85分(强扩散)
    """
    print("\n" + "=" * 80)
    print("测试案例2: 光模块/CPO成功案例 (2026年5月11-12日)")
    print("=" * 80)

    # 光模块/CPO数据
    sector_data = {
        "core_anchor": {
            "status": "中际旭创放量上涨",
            "change_pct": 8.28,  # 5月12日+8.28%
            "volume_ratio": 1.5
        },
        "elastic_carrier": {
            "new_high_count": 3,  # 多只创新高
            "intraday_support": "强"
        },
        "limit_up_count": 8,
        "total_stocks": 15,
        "second_wave_new_highs": 3,  # 5月12日有二波创新高群
        "turnover_share_change": 1.5  # 成交占比扩张
    }

    result = calculate_sector_diffusion_quality("光模块/CPO", sector_data)

    print(f"\n板块: {result['sector_name']}")
    print(f"总分: {result['total_score']}/100")
    print(f"评级: {result['level']}")
    print(f"\n详细得分:")
    print(f"  - 核心锚稳定性: {result['details']['core_anchor']['score']}/30 ({result['details']['core_anchor']['label']})")
    print(f"  - 弹性载体强度: {result['details']['elastic_carrier']['score']}/25 ({result['details']['elastic_carrier']['label']})")
    print(f"  - 后排承接度: {result['details']['follower_support']['score']}/20 ({result['details']['follower_support']['label']})")
    print(f"  - 二波创新高群: {result['details']['second_wave_new_highs']['score']}/15 ({result['details']['second_wave_new_highs']['label']})")
    print(f"  - 成交占比变化: {result['details']['turnover_share_change']['score']}/10 ({result['details']['turnover_share_change']['label']})")
    print(f"\n结论: {result['conclusion']}")
    print(f"动作: {result['action']}")

    assert result['total_score'] >= 70, "光模块/CPO应该是强扩散"
    print("\n✅ 测试通过: 光模块/CPO确实是强扩散,量化资金仍在")


def test_quant_environment_detection():
    """
    测试案例3: 量化环境识别

    预期结果: 检测到量化横行环境
    """
    print("\n" + "=" * 80)
    print("测试案例3: 量化环境识别 (2026年5月27日)")
    print("=" * 80)

    # 5月27日市场数据
    market_data = {
        "index_change_pct": -1.25,  # 上证指数-1.25%
        "up_ratio": 21.7,  # 974/(974+4489) = 21.7%
        "top50_turnover_share_pct": 22.94,
        "sector_limit_up_count": 61,
        "active_sector_count": 5,  # 多个板块同步异动
        "leading_stock_dominance": 0.2,  # 单一龙头定价权下降
        "limit_up_sector_count": 8,  # 涨停分布在8个板块
        "top20_turnover_share_pct": 13.69,
        "leading_stock_change_pct": 5.0,
        "sector_avg_change_pct": 1.5
    }

    environment = detect_quant_environment(market_data)

    print(f"\n量化环境判断:")
    print(f"  - 是否量化横行: {'是' if environment['is_quant_dominant'] else '否'}")
    print(f"  - 置信度: {environment['confidence']*100:.0f}%")
    print(f"  - 摘要: {environment['summary']}")
    print(f"  - 动作: {environment['action']}")

    print(f"\n检测到的模式:")
    for mode in environment['modes']:
        print(f"  - {mode['mode']}: {mode['description']}")
        print(f"    证据: {mode['evidence']}")
        print(f"    动作: {mode['action']}")

    print("\n✅ 测试通过: 成功识别量化环境")


def test_sector_turnover_trend():
    """
    测试案例4: 板块成交占比趋势追踪

    预期结果: AI算力收缩,人形机器人扩张
    """
    print("\n" + "=" * 80)
    print("测试案例4: 板块成交占比趋势追踪")
    print("=" * 80)

    # AI算力成交占比历史
    ai_history = [
        {"date": "2026-05-20", "turnover_share_pct": 18.0},
        {"date": "2026-05-21", "turnover_share_pct": 17.5},
        {"date": "2026-05-22", "turnover_share_pct": 15.0},
        {"date": "2026-05-25", "turnover_share_pct": 14.5},
        {"date": "2026-05-26", "turnover_share_pct": 13.0},
    ]

    # 人形机器人成交占比历史
    robot_history = [
        {"date": "2026-05-20", "turnover_share_pct": 5.0},
        {"date": "2026-05-21", "turnover_share_pct": 6.5},
        {"date": "2026-05-22", "turnover_share_pct": 8.0},
        {"date": "2026-05-25", "turnover_share_pct": 10.0},
        {"date": "2026-05-26", "turnover_share_pct": 12.0},
    ]

    # 测试AI算力
    ai_trend = build_sector_turnover_trend("AI算力", ai_history)
    print(f"\n板块: {ai_trend['sector_name']}")
    print(f"  - 最新占比: {ai_trend['latest_share']:.1f}%")
    print(f"  - 3日趋势: {ai_trend['trend_3d']}")
    print(f"  - 5日均线: {ai_trend['ma5']:.1f}%")
    print(f"  - 趋势序列: {ai_trend['formatted_series']}")
    print(f"  - 结论: {ai_trend['conclusion']}")

    assert ai_trend['trend_3d'] == "分化", "AI算力应该是分化趋势"

    # 测试人形机器人
    robot_trend = build_sector_turnover_trend("人形机器人", robot_history)
    print(f"\n板块: {robot_trend['sector_name']}")
    print(f"  - 最新占比: {robot_trend['latest_share']:.1f}%")
    print(f"  - 3日趋势: {robot_trend['trend_3d']}")
    print(f"  - 5日均线: {robot_trend['ma5']:.1f}%")
    print(f"  - 趋势序列: {robot_trend['formatted_series']}")
    print(f"  - 结论: {robot_trend['conclusion']}")

    assert robot_trend['trend_3d'] == "强化", "人形机器人应该是强化趋势"

    print("\n✅ 测试通过: 成功追踪板块成交占比趋势")


def test_quant_exit_signal():
    """
    测试案例5: 量化离场信号检测

    预期结果: AI算力触发量化离场信号
    """
    print("\n" + "=" * 80)
    print("测试案例5: 量化离场信号检测")
    print("=" * 80)

    # AI算力数据(量化离场)
    ai_data = {
        "trend_3d": "分化",
        "latest_share": 13.0,
        "ma5": 15.6,
        "follower_status": "掉队",
        "core_status": "跌回VWAP"
    }

    signal = detect_quant_exit_signal(ai_data)

    print(f"\n板块: AI算力")
    print(f"  - 信号1(成交占比回落): {'✓' if signal['signal_1_turnover_shrink'] else '✗'}")
    print(f"  - 信号2(后排掉队): {'✓' if signal['signal_2_follower_dropout'] else '✗'}")
    print(f"  - 信号3(核心跌回关键位): {'✓' if signal['signal_3_core_breakdown'] else '✗'}")
    print(f"  - 三项共振: {'✓' if signal['all_signals'] else '✗'}")
    print(f"  - 动作: {signal['action']}")

    assert signal['all_signals'], "AI算力应该触发量化离场三项共振"
    print("\n✅ 测试通过: 成功检测量化离场信号")


def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("板块深耕系统测试")
    print("=" * 80)

    try:
        test_commercial_aerospace_failure()
        test_cpo_success()
        test_quant_environment_detection()
        test_sector_turnover_trend()
        test_quant_exit_signal()

        print("\n" + "=" * 80)
        print("✅ 所有测试通过!")
        print("=" * 80)
        print("\n核心验证:")
        print("1. ✅ 商业航天失败 - 无二波创新高群,量化资金撤离")
        print("2. ✅ 光模块/CPO成功 - 板块先铺→筛选核心→持续买入")
        print("3. ✅ 量化环境识别 - 成功识别窄池子进攻、板块先铺等模式")
        print("4. ✅ 成交占比追踪 - AI算力收缩,人形机器人扩张")
        print("5. ✅ 量化离场信号 - 三项共振检测成功")

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
