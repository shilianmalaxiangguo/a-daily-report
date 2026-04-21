# A股日报生成技能 - 全finshare + 东方财富热榜解密方案

## 📋 技能概述

本技能提供完整的A股日报生成功能，包括：
1. 大盘指数 + 两市成交额（全finshare方案）
2. 热度前十个股（东方财富热榜解密方案）
3. 成交额>100亿个股（52打板网 + 腾讯API验证）
4. 行业资金净流向
5. 市场板块趋势
6. 狙击手视角分析（三档仓位框架）

## 🚀 快速开始

### 1. 安装依赖
```bash
# 必需依赖
pip3 install finshare
pip3 install akshare
pip3 install pycryptodome
pip3 install pandas
```

### 2. 生成A股日报
```bash
# 方法1：使用规范demo生成指定日期报告
python3 scripts/daily_report_entry_demo.py 2026-03-26

# 方法2：复制demo创建具体日期脚本
cp scripts/daily_report_entry_demo.py scripts/daily_report_2026-03-26.py
python3 scripts/daily_report_2026-03-26.py

# 方法3：直接运行测试脚本
python3 scripts/get_today_data.py
```

## 📊 核心功能模块

### 1. 数据收集器 (`scripts/data_collector.py`)
- 全finshare方案获取指数数据
- 腾讯财经API验证个股数据
- 支持主板、科创板、创业板、北交所的涨跌幅规则

### 2. 东方财富热榜解密 (`scripts/eastmoney_hot_rank.py`)
- **AES-CBC + Pkcs7** 解密算法
- Key: `MD5("getUtilsFromFile")`
- IV: `"getClassFromFile"`
- 支持历史日期排名提取

### 3. 历史数据获取 (`scripts/hot_rank_with_history_data.py`)
- 使用akshare获取历史日频数据
- 确保涨跌幅、成交额等数据是目标日期的，不是当前实时数据
- 支持批量获取和错误处理

### 4. 板块涨跌幅数据 (`scripts/daily_report_entry_demo.py`) - **v2.3.44新增**
- **同花顺问财API**：获取板块涨跌幅排行（首选）
- **支持历史数据**：可获取任意历史日期的板块涨跌幅
- **数据字段**：板块名称、涨跌幅、主力净流入、领涨股
- **使用方法**：
  ```python
  # 获取今天数据
  get_sector_change_from_iwencai(rank_type='up', limit=10)
  
  # 获取昨天数据
  get_sector_change_from_iwencai(rank_type='up', limit=10, target_date='2026-04-09')
  ```
- **认证方式**：环境变量 `IWENCAI_API_KEY`

### 5. 工具函数 (`scripts/utils.py`)
- 涨停板分类规则（主板10%、科创板/创业板20%、北交所30%、ST/*ST 5%）
- 数据格式化显示
- JSON序列化支持

## 🔧 技术架构

### 数据获取流程图
```
东方财富热榜数据流
┌─────────────────────────────┐
│   步骤1：获取热榜排名       │
│   ↓                         │
│   从popularityList.js获取   │
│   加密Base64数据            │
│   ↓                         │
│   AES-CBC + Pkcs7解密       │
│   ↓                         │
│   提取指定日期历史排名       │
│   ↓                         │
│   获得股票代码列表          │
└─────────────┬───────────────┘
              │
┌─────────────▼───────────────┐
│   步骤2：获取历史数据       │
│   ↓                         │
│   使用akshare获取历史日频    │
│   数据（涨跌幅、成交额等）   │
│   ↓                         │
│   验证数据为指定日期        │
│   ↓                         │
│   获取完整股票详情          │
└─────────────┬───────────────┘
              │
┌─────────────▼───────────────┐
│   步骤3：生成报告           │
│   ↓                         │
│   格式化为Markdown表格      │
│   ↓                         │
│   集成到A股日报中           │
└─────────────────────────────┘
```

### 热榜双路径规范
1. **当天/实时热榜**: `akshare.stock_hot_rank_em()`
2. **历史热榜**: 东方财富解密 + akshare历史数据
3. **数据验证**: 所有数据必须经过API验证，确保时效性和准确性

## 📝 使用示例

### 示例1：获取特定日期热榜
```python
from scripts.hot_rank_with_history_data import HotRankHistoricalDataCollector

collector = HotRankHistoricalDataCollector()
data = collector.get_complete_hot_rank_data('2026-03-25')
print(f"热榜数据: {data}")
```

### 示例2：生成完整A股日报
```python
from scripts.data_collector import AShareDataCollector

collector = AShareDataCollector()

# 获取大盘指数
index_data = collector.get_index_data()

# 获取热榜数据
hot_rank_data = collector.get_hot_rank_data('2026-03-25')

# 获取成交额>100亿个股
high_turnover = collector.get_high_turnover_stocks()
```

### 示例3：测试解密功能
```python
from scripts.eastmoney_hot_rank import EastMoneyHotRankCollector

collector = EastMoneyHotRankCollector()
rank_list = collector.get_hot_rank_for_date('2026-03-25')
print(f"热榜排名: {rank_list}")
```

## ⚠️ 重要规范

### 涨停板分类规则
- **科创板(20%涨停)**: 股票代码以68开头
- **创业板(20%涨停)**: 股票代码以30开头  
- **北交所(30%涨停)**: 股票代码以43、83、87开头
- **ST/*ST(5%涨停)**: 股票名称包含"ST"或"*ST"标识
- **主板(10%涨停)**: 股票代码以00、60开头（除上述特殊板块外）

### 狙击手视角三档仓位
- **一档（最优核心）**: 必须是50%仓位
- **二档（稳健补充）**: 必须是30%仓位
- **三档（保底操作）**: 空仓或持有ETF（T+1的20%，T+0的30%到50%）

### 数据真实性原则
1. **不凑数**: 成交额必须真实≥100亿才可进入对应模块
2. **不伪造**: 热榜数据缺失时宁可留空，不用模拟数据补位
3. **不伪装**: 指数数据异常时明确标注，不用0值伪装真实结果

## 🔍 故障排除

### 常见问题
1. **解密失败**: 检查网络连接，确认`popularityList.js`接口可用
2. **akshare数据缺失**: 某些股票历史数据可能不完整，使用备用方案
3. **依赖安装失败**: 使用国内镜像源，如 `pip3 install -i https://pypi.tuna.tsinghua.edu.cn/simple`

### 备用方案
- 东方财富数据失败 → 使用akshare实时热榜
- akshare历史数据失败 → 使用腾讯API获取当前数据（需标注时效性）
- finshare指数数据失败 → 使用腾讯财经API获取指数数据

## 📁 文件结构
```
a-daily-report/
├── README.md                    # 本文档
├── SKILL.md                     # 技能详细文档
└── scripts/
    ├── data_collector.py        # 主数据收集器
    ├── eastmoney_hot_rank.py    # 东方财富热榜解密
    ├── hot_rank_with_history_data.py # 历史数据获取
    ├── utils.py                 # 工具函数
    ├── daily_report_entry_demo.py    # 规范入口demo
    ├── get_today_data.py        # 今日数据获取脚本
    └── test_finshare.py         # finshare功能测试
```

## 📞 支持与贡献

### 问题反馈
- 如遇问题，请检查错误日志并查看SKILL.md中的解决方案
- 数据源问题可尝试备用方案

### 代码贡献
- 遵循现有文件结构，避免破坏性变更
- 提交代码前先编写测试用例
- 代码变更后同步更新相关文档

---

**技能版本**: v1.2 (2026-03-26)  
**维护状态**: ✅ 正常运作  
**最后更新**: 2026年3月26日

# a-daily-report
