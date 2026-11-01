#!/usr/bin/env python3.14
"""Build sector-first forward replay HTML from historical daily facts."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from collections import Counter
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
PROJECT_ROOT = SCRIPT_ROOT.parent

BUY_WINDOWS = (
    {
        "id": "open_0930_0935",
        "window": "09:30-09:35",
        "proxy_label": "T+1开盘价代理",
        "price_field": "open",
    },
    {
        "id": "mid_0950_1010",
        "window": "09:50-10:10",
        "proxy_label": "T+1日内中枢价代理",
        "price_field": "intraday_mid",
    },
    {
        "id": "late_1430_1455",
        "window": "14:30-14:55",
        "proxy_label": "T+1收盘价代理",
        "price_field": "close",
    },
)

SELL_WINDOWS = (
    {
        "id": "open_0930_0935",
        "window": "09:30-09:35",
        "proxy_label": "T+2开盘价代理",
        "price_field": "open",
    },
    {
        "id": "mid_0950_1010",
        "window": "09:50-10:10",
        "proxy_label": "T+2日内中枢价代理",
        "price_field": "intraday_mid",
    },
    {
        "id": "late_1430_1455",
        "window": "14:30-14:55",
        "proxy_label": "T+2收盘价代理",
        "price_field": "close",
    },
)

INDEX_BENCHMARK_SPECS = (
    {
        "label": "上证指数",
        "context_key": "T0上证指数",
        "chart_key": "excess_shanghai_pct",
        "series_name": "跑赢上证",
    },
    {
        "label": "创业板指",
        "context_key": "T0创业板指",
        "chart_key": "excess_chinext_pct",
        "series_name": "跑赢创业板",
    },
    {
        "label": "科创50",
        "context_key": "T0科创50",
        "chart_key": "excess_star50_pct",
        "series_name": "跑赢科创50",
    },
    {
        "label": "中证500",
        "context_key": "T0中证500",
        "chart_key": "excess_csi500_pct",
        "series_name": "跑赢中证500",
    },
    {
        "label": "全A指数",
        "context_key": "T0全A指数",
        "chart_key": "excess_all_a_pct",
        "series_name": "跑赢全A",
    },
    {
        "label": "中证1000",
        "context_key": "T0中证1000",
        "chart_key": "excess_csi1000_pct",
        "series_name": "跑赢中证1000",
    },
)

LOCAL_MERMAID_RENDERER_SCRIPT = """
  <script>
    (function() {
      const nodes = Array.from(document.querySelectorAll('.mermaid'));
      if (!nodes.length) return;

      const escapeText = (value) => String(value || '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[char]));

      const wrapLabel = (label) => {
        const text = String(label || '').trim();
        if (!text) return [''];
        if (text.length <= 18) return [text];
        const lines = [];
        let rest = text;
        while (rest.length > 18 && lines.length < 3) {
          let cut = rest.lastIndexOf(' ', 18);
          if (cut < 8) cut = 18;
          lines.push(rest.slice(0, cut));
          rest = rest.slice(cut).trim();
        }
        if (rest) lines.push(rest.length > 22 ? `${rest.slice(0, 21)}...` : rest);
        return lines.slice(0, 4);
      };

      const extractNodes = (source) => {
        const labels = new Map();
        const order = [];
        const pattern = /([A-Za-z][A-Za-z0-9_-]*)\\s*(?:\\[\\s*"([^"]+)"\\s*\\]|\\{\\s*"([^"]+)"\\s*\\})/g;
        let match;
        while ((match = pattern.exec(source)) !== null) {
          const id = match[1];
          const label = (match[2] || match[3] || id).trim();
          if (!labels.has(id)) {
            labels.set(id, label);
            order.push(id);
          }
        }
        return order.map((id) => ({ id, label: labels.get(id) || id }));
      };

      const renderLocalSvg = (node) => {
        const graphNodes = extractNodes(node.textContent || '');
        if (!graphNodes.length) {
          node.setAttribute('data-mermaid-status', 'empty');
          return;
        }
        const boxWidth = 230;
        const boxHeight = 86;
        const gap = 42;
        const pad = 18;
        const width = Math.max(320, pad * 2 + graphNodes.length * boxWidth + Math.max(0, graphNodes.length - 1) * gap);
        const height = pad * 2 + boxHeight;
        const boxes = graphNodes.map((item, index) => {
          const x = pad + index * (boxWidth + gap);
          const y = pad;
          const lines = wrapLabel(item.label);
          const text = lines.map((line, lineIndex) => {
            const dy = 34 + lineIndex * 18;
            return `<text x="${x + boxWidth / 2}" y="${y + dy}" text-anchor="middle" font-size="13" fill="#172033">${escapeText(line)}</text>`;
          }).join('');
          return `
            <g>
              <rect x="${x}" y="${y}" width="${boxWidth}" height="${boxHeight}" rx="8" fill="#ffffff" stroke="#d8dee8"></rect>
              ${text}
            </g>
          `;
        }).join('');
        const arrows = graphNodes.slice(0, -1).map((_, index) => {
          const x1 = pad + index * (boxWidth + gap) + boxWidth;
          const x2 = x1 + gap - 8;
          const y = pad + boxHeight / 2;
          return `<line x1="${x1 + 8}" y1="${y}" x2="${x2}" y2="${y}" stroke="#667085" stroke-width="1.6" marker-end="url(#arrow)"></line>`;
        }).join('');
        node.innerHTML = `
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Mermaid flowchart">
            <defs>
              <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
                <path d="M0,0 L8,4 L0,8 z" fill="#667085"></path>
              </marker>
            </defs>
            ${arrows}
            ${boxes}
          </svg>
        `;
        node.setAttribute('data-mermaid-status', 'local-svg');
      };

      nodes.forEach(renderLocalSvg);
    })();
  </script>
"""

WINDOW_PERFORMANCE_ECHARTS_SCRIPT = """
  <script>
    (function() {
      const payloadNode = document.getElementById('sector-window-chart-payload');
      const returnNode = document.getElementById('sector-window-return-chart');
      const excessNode = document.getElementById('sector-window-excess-chart');
      const matrixNode = document.getElementById('sector-window-matrix-chart');
      const metricsNode = document.getElementById('sector-window-metrics-chart');
      const distributionNode = document.getElementById('sector-sample-distribution-chart');
      const curveNode = document.getElementById('sector-window-equity-chart');
      const marketNode = document.getElementById('sector-market-breadth-chart');
      if (!payloadNode) return;

      const chartNodes = [returnNode, excessNode, matrixNode, metricsNode, distributionNode, curveNode, marketNode].filter(Boolean);
      const setMessage = (message) => {
        chartNodes.forEach((node) => {
          node.classList.add('is-empty');
          node.textContent = message;
        });
      };

      let payload = { rows: [] };
      try {
        payload = JSON.parse(payloadNode.textContent || '{}');
      } catch (error) {
        setMessage('图表数据解析失败，请查看下方表格。');
        return;
      }

      const rows = Array.isArray(payload.rows) ? payload.rows : [];
      const hasChartData = rows.length
        || (payload.matrix && Array.isArray(payload.matrix.cells) && payload.matrix.cells.length)
        || (payload.sample_distribution && Array.isArray(payload.sample_distribution.outcomes) && payload.sample_distribution.outcomes.length)
        || (payload.equity_curve && Array.isArray(payload.equity_curve.points) && payload.equity_curve.points.length)
        || (payload.market_breadth && Array.isArray(payload.market_breadth.rows) && payload.market_breadth.rows.length);
      if (!hasChartData) {
        setMessage('暂无可绘制的窗口折算收益图。');
        return;
      }
      if (!window.echarts) {
        setMessage('图表依赖未加载，请查看下方表格。');
        return;
      }

      const numberOrNull = (row, key) => {
        const value = row ? row[key] : null;
        return typeof value === 'number' && Number.isFinite(value) ? value : null;
      };
      const escapeHtml = (value) => String(value || '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[char]));
      const pct = (value) => (typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(2)}%` : '待补');
      const point = (value) => (typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(2)}个百分点` : '待补');
      const labels = rows.map((row) => row.short_label || row.label || '');
      const rootStyles = getComputedStyle(document.documentElement);
      const cssVar = (name, fallback) => rootStyles.getPropertyValue(name).trim() || fallback;
      const chartTone = {
        paper: cssVar('--reader-bg', '#ffffff'),
        ink: cssVar('--reader-text', '#444444'),
        text: cssVar('--reader-text', '#444444'),
        muted: cssVar('--reader-muted', '#888888'),
	        line: cssVar('--reader-line', '#d9d9d9'),
	        surface: cssVar('--reader-surface', '#F3F5F7'),
	        red: cssVar('--accent-red', '#DD4C4F'),
	        green: '#07C160',
	        greenSoft: 'rgba(7, 193, 96, 0.16)',
	        greenMist: '#EAF8EF',
		        redSoft: cssVar('--accent-soft', '#FFD5D5'),
		        redMist: '#F9E7E7',
		        orange: cssVar('--accent-orange', '#ff8a1f'),
		        blue: '#2F7FB8',
		        gold: '#A88400'
		      };
      const readerFont = '"AvenirNext-Regular", "Avenir Next", -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif';
      const commonGrid = { left: 54, right: 32, top: 62, bottom: 86, containLabel: true };
      const axisLabel = { interval: 0, lineHeight: 16, color: chartTone.muted, fontSize: 11 };
      const baseTextStyle = { color: chartTone.ink, fontFamily: readerFont };
	      const splitLine = { lineStyle: { color: chartTone.line, type: 'dashed' } };
	      const axisLine = { lineStyle: { color: chartTone.line } };
		      const signedBarColor = (value) => {
		        const number = Number(value);
		        if (!Number.isFinite(number) || number === 0) return chartTone.line;
		        return number < 0 ? chartTone.green : chartTone.red;
		      };
		      const signedBarRadius = (value) => {
		        const number = Number(value);
		        if (!Number.isFinite(number) || number >= 0) return [7, 7, 0, 0];
		        return [0, 0, 7, 7];
		      };
		      const signedBarData = (key) => rows.map((row) => {
		        const value = numberOrNull(row, key);
		        return { value, itemStyle: { borderRadius: signedBarRadius(value) } };
		      });
			      const seriesBarData = (sourceRows, key, positiveColor) => sourceRows.map((row) => {
			        const value = numberOrNull(row, key);
			        const number = Number(value);
			        const color = Number.isFinite(number) && number < 0 ? chartTone.green : positiveColor;
			        return { value, itemStyle: { borderRadius: signedBarRadius(value), color } };
			      });
		      const signedBarStyle = { color: (params) => signedBarColor(params.value) };
	      const baseTooltip = {
        confine: true,
        appendToBody: false,
        backgroundColor: 'rgba(255,255,255,0.96)',
        borderColor: chartTone.line,
        borderWidth: 1,
        padding: [8, 10],
        textStyle: {
          color: chartTone.text,
          fontSize: 12,
          lineHeight: 18,
          fontFamily: readerFont
        },
        extraCssText: 'max-width:260px;white-space:normal;box-shadow:0 10px 28px rgba(32,24,18,.12);border-radius:10px;'
      };
      const chartInstances = [];

      if (matrixNode && payload.matrix && Array.isArray(payload.matrix.cells) && payload.matrix.cells.length) {
        const matrix = payload.matrix;
	        const matrixValues = matrix.cells
	          .map((cell) => Number(cell.average_return_pct))
	          .filter((value) => Number.isFinite(value));
	        const matrixPositiveMax = Math.max(0.01, ...matrixValues.filter((value) => value > 0));
	        const matrixNegativeMax = Math.max(0.01, ...matrixValues.filter((value) => value < 0).map((value) => Math.abs(value)));
	        const matrixPositiveRamp = ['#fff7ef', '#ffe6d1', '#ffcda2', '#f99a60', '#d95436'];
	        const matrixNegativeRamp = ['#f8fbf7', '#edf5ef', '#dbeadd', '#b9d4c0', '#84ad91'];
	        const matrixBucket = (strength) => {
	          if (strength >= 0.84) return 4;
	          if (strength >= 0.62) return 3;
	          if (strength >= 0.38) return 2;
	          if (strength >= 0.16) return 1;
	          return 0;
	        };
	        const matrixFillColor = (value) => {
	          const number = Number(value);
	          if (!Number.isFinite(number)) return chartTone.surface;
	          if (number > 0) {
	            return matrixPositiveRamp[matrixBucket(Math.min(1, number / matrixPositiveMax))];
	          }
	          if (number < 0) {
	            return matrixNegativeRamp[matrixBucket(Math.min(1, Math.abs(number) / matrixNegativeMax))];
	          }
	          return chartTone.surface;
	        };
        const matrixChart = window.echarts.init(matrixNode, null, { renderer: 'canvas' });
        chartInstances.push(matrixChart);
        matrixChart.setOption({
          backgroundColor: 'transparent',
          textStyle: baseTextStyle,
          tooltip: {
            ...baseTooltip,
            position: 'top',
            formatter: function(params) {
              const cell = matrix.cells[params.dataIndex] || {};
              return [
                `${escapeHtml(cell.buy_window || '')} 买 / ${escapeHtml(cell.sell_window || '')} 卖`,
                `平均代理表现：${pct(cell.average_return_pct)}`,
                `正收益：${escapeHtml(cell.positive_text || '待补')}`,
                `样本：${escapeHtml(cell.sample_count || 0)}`
              ].join('<br>');
            }
          },
          grid: { left: 86, right: 28, top: 30, bottom: 48, containLabel: true },
          xAxis: {
            type: 'category',
            data: matrix.sell_windows || [],
            axisLabel: { color: chartTone.muted, fontSize: 12 },
            axisTick: { show: false },
            axisLine
          },
          yAxis: {
            type: 'category',
            data: matrix.buy_windows || [],
            axisLabel: { color: chartTone.muted, fontSize: 12 },
            axisTick: { show: false },
            axisLine
          },
          visualMap: { show: false },
	          series: [{
	            name: '买卖时间矩阵',
	            type: 'heatmap',
	            data: matrix.cells.map((cell) => ({
	              value: [cell.sell_index, cell.buy_index, cell.average_return_pct],
	              itemStyle: {
	                color: matrixFillColor(cell.average_return_pct),
	                borderColor: cell.is_best ? chartTone.red : 'rgba(255,255,255,0.92)',
	                borderWidth: cell.is_best ? 3 : 1.4
	              }
	            })),
	            itemStyle: {
	              borderColor: 'rgba(255,255,255,0.92)',
	              borderWidth: 1.4
	            },
            label: {
              show: true,
              formatter: function(params) {
                const cell = matrix.cells[params.dataIndex] || {};
                const mark = cell.is_best ? ' ★' : '';
                return `${pct(cell.average_return_pct)}${mark}\n${cell.positive_text || ''}`;
              },
              color: chartTone.text,
              backgroundColor: 'rgba(255,255,255,0.78)',
              borderRadius: 6,
              padding: [3, 5],
              fontSize: 11,
              lineHeight: 15
            },
            emphasis: { itemStyle: { borderColor: chartTone.red, borderWidth: 2 } }
          }]
        });
      }

      if (metricsNode && rows.length) {
        const topRows = rows.slice(0, 10);
        const metricsChart = window.echarts.init(metricsNode, null, { renderer: 'canvas' });
        chartInstances.push(metricsChart);
        metricsChart.setOption({
          backgroundColor: 'transparent',
          textStyle: baseTextStyle,
		          color: [chartTone.orange, chartTone.red, chartTone.green],
          tooltip: {
            ...baseTooltip,
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: function(params) {
              const index = params && params.length ? params[0].dataIndex : 0;
              const row = topRows[index] || {};
              const lines = [escapeHtml(row.label), `参与/原样本：${escapeHtml(row.sample_text || '待补')}`];
              params.forEach((item) => lines.push(`${item.marker}${item.seriesName}：${pct(item.value)}`));
              return lines.join('<br>');
            }
	          },
			          legend: {
			            top: 6,
			            selectedMode: false,
			            itemWidth: 20,
			            itemHeight: 8,
			            textStyle: { color: chartTone.muted },
			            data: [
			              { name: '区间收益', itemStyle: { color: chartTone.orange } },
			              { name: '月度折算参考', itemStyle: { color: chartTone.red } },
			              { name: '负收益', itemStyle: { color: chartTone.green } }
			            ]
			          },
			          grid: { left: 54, right: 28, top: 62, bottom: 86, containLabel: true },
          xAxis: { type: 'category', data: topRows.map((row) => row.short_label || row.label || ''), axisLabel, axisTick: { show: false }, axisLine },
          yAxis: { type: 'value', axisLabel: { color: chartTone.muted, formatter: '{value}%' }, splitLine, axisLine },
          series: [
			            { name: '区间收益', type: 'bar', barMaxWidth: 20, data: seriesBarData(topRows, 'cumulative_return_pct', chartTone.orange) },
			            { name: '月度折算参考', type: 'bar', barMaxWidth: 20, data: seriesBarData(topRows, 'monthly_return_pct', chartTone.red) },
			            { name: '负收益', type: 'bar', silent: true, tooltip: { show: false }, itemStyle: { color: chartTone.green }, data: topRows.map(() => null) }
          ]
        });
      }

      if (distributionNode && payload.sample_distribution && Array.isArray(payload.sample_distribution.outcomes) && payload.sample_distribution.outcomes.length) {
        const distribution = payload.sample_distribution;
        const outcomeItems = distribution.outcomes.map((item) => ({ ...item, group: '样本状态' }));
        const bucketItems = Array.isArray(distribution.return_buckets)
          ? distribution.return_buckets.map((item) => ({ ...item, group: '收益区间' }))
          : [];
        const distributionItems = outcomeItems.concat(bucketItems);
        const distributionChart = window.echarts.init(distributionNode, null, { renderer: 'canvas' });
        chartInstances.push(distributionChart);
        distributionChart.setOption({
          backgroundColor: 'transparent',
          textStyle: baseTextStyle,
          color: [chartTone.red, chartTone.green, chartTone.muted],
          tooltip: {
            ...baseTooltip,
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: function(params) {
              const item = distributionItems[params && params.length ? params[0].dataIndex : 0] || {};
              return [
                escapeHtml(item.group || ''),
                `${escapeHtml(item.label || '')}：${escapeHtml(item.count || 0)}笔`
              ].join('<br>');
            }
          },
          grid: { left: 54, right: 28, top: 42, bottom: 58, containLabel: true },
          xAxis: {
            type: 'category',
            data: distributionItems.map((item) => item.label || ''),
            axisLabel: { color: chartTone.muted, interval: 0 },
            axisTick: { show: false },
            axisLine
          },
          yAxis: {
            type: 'value',
            name: '样本数',
            minInterval: 1,
            nameTextStyle: { color: chartTone.muted },
            axisLabel: { color: chartTone.muted },
            splitLine,
            axisLine
          },
          series: [{
            name: '样本数',
            type: 'bar',
            barMaxWidth: 28,
            label: { show: true, position: 'top', color: chartTone.ink },
            itemStyle: {
              borderRadius: [7, 7, 0, 0],
              color: function(params) {
                const item = distributionItems[params.dataIndex] || {};
                if (item.tone === 'positive') return chartTone.red;
                if (item.tone === 'negative') return chartTone.green;
                if (item.tone === 'flat') return chartTone.muted;
                if (item.tone === 'pending') return chartTone.line;
                return item.label && item.label.indexOf('-') === 0 ? chartTone.green : chartTone.red;
              }
            },
            data: distributionItems.map((item) => item.count)
          }]
        });
      }

      if (curveNode && payload.equity_curve && Array.isArray(payload.equity_curve.points) && payload.equity_curve.points.length) {
        const curve = payload.equity_curve;
        const curveChart = window.echarts.init(curveNode, null, { renderer: 'canvas' });
        chartInstances.push(curveChart);
        curveChart.setOption({
          backgroundColor: 'transparent',
          textStyle: baseTextStyle,
          color: [chartTone.red, chartTone.green],
          tooltip: { ...baseTooltip, trigger: 'axis' },
          legend: { top: 6, textStyle: { color: chartTone.muted } },
          grid: { left: 54, right: 28, top: 58, bottom: 62, containLabel: true },
          xAxis: { type: 'category', data: curve.points.map((point) => point.decision_date || ''), axisLabel: { color: chartTone.muted }, axisTick: { show: false }, axisLine },
          yAxis: [
            { type: 'value', name: '净值', nameTextStyle: { color: chartTone.muted }, axisLabel: { color: chartTone.muted }, splitLine, axisLine },
            { type: 'value', name: '回撤', nameTextStyle: { color: chartTone.muted }, axisLabel: { color: chartTone.muted, formatter: '{value}%' }, splitLine: { show: false } }
          ],
          series: [
            { name: '较高组合净值', type: 'line', smooth: 0.18, symbol: 'circle', symbolSize: 6, lineStyle: { width: 2.4 }, data: curve.points.map((point) => point.net_value) },
            { name: '当时回撤', type: 'bar', yAxisIndex: 1, barMaxWidth: 18, itemStyle: { borderRadius: [7, 7, 7, 7] }, data: curve.points.map((point) => point.drawdown_pct) }
          ]
        });
      }

      if (marketNode && payload.market_breadth && Array.isArray(payload.market_breadth.rows) && payload.market_breadth.rows.length) {
        const market = payload.market_breadth;
        const marketChart = window.echarts.init(marketNode, null, { renderer: 'canvas' });
        chartInstances.push(marketChart);
        marketChart.setOption({
          backgroundColor: 'transparent',
          textStyle: baseTextStyle,
          color: [chartTone.red, chartTone.green, chartTone.blue, chartTone.gold],
          tooltip: { ...baseTooltip, trigger: 'axis' },
          legend: { top: 6, textStyle: { color: chartTone.muted } },
          grid: { left: 54, right: 54, top: 58, bottom: 62, containLabel: true },
          xAxis: { type: 'category', data: market.rows.map((row) => row.date || ''), axisLabel: { color: chartTone.muted }, axisTick: { show: false }, axisLine },
          yAxis: [
            { type: 'value', name: '家数', nameTextStyle: { color: chartTone.muted }, axisLabel: { color: chartTone.muted }, splitLine, axisLine },
            { type: 'value', name: '指数/新高', nameTextStyle: { color: chartTone.muted }, axisLabel: { color: chartTone.muted }, splitLine: { show: false } }
          ],
          series: [
            { name: '上涨家数', type: 'bar', stack: 'breadth', barMaxWidth: 20, itemStyle: { borderRadius: [7, 7, 0, 0] }, data: market.rows.map((row) => row.up_count) },
            { name: '下跌家数', type: 'bar', stack: 'breadth', barMaxWidth: 20, itemStyle: { borderRadius: [0, 0, 7, 7] }, data: market.rows.map((row) => typeof row.down_count === 'number' ? -row.down_count : null) },
            { name: '全A涨跌幅', type: 'line', yAxisIndex: 1, smooth: 0.18, symbolSize: 6, lineStyle: { width: 2.2 }, data: market.rows.map((row) => row.all_a_change_pct) },
            { name: '创新高占比', type: 'line', yAxisIndex: 1, smooth: 0.18, symbolSize: 6, lineStyle: { width: 2.2 }, data: market.rows.map((row) => row.new_high_pct) }
          ]
        });
      }

      let returnChart = null;
      if (returnNode && rows.length) {
        returnChart = window.echarts.init(returnNode, null, { renderer: 'canvas' });
        chartInstances.push(returnChart);
        returnChart.setOption({
          backgroundColor: 'transparent',
          textStyle: baseTextStyle,
          color: [chartTone.red, chartTone.blue, chartTone.green],
          tooltip: {
            ...baseTooltip,
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: function(params) {
              const index = params && params.length ? params[0].dataIndex : 0;
              const row = rows[index] || {};
              const lines = [
                escapeHtml(row.label),
                `参与/原样本：${escapeHtml(row.sample_text || '待补')}`,
                `折算周期：${escapeHtml(row.period_count || '待补')}`
              ];
              params.forEach((item) => {
                lines.push(`${item.marker}${item.seriesName}：${pct(item.value)}`);
              });
              return lines.join('<br>');
            }
          },
          legend: { top: 8, textStyle: { color: chartTone.muted } },
          grid: commonGrid,
          xAxis: { type: 'category', data: labels, axisLabel, axisTick: { show: false }, axisLine },
          yAxis: [
            { type: 'value', name: '收益', nameTextStyle: { color: chartTone.muted }, axisLabel: { color: chartTone.muted, formatter: '{value}%' }, splitLine, axisLine },
            { type: 'value', name: '回撤', nameTextStyle: { color: chartTone.muted }, axisLabel: { color: chartTone.muted, formatter: '{value}%' }, splitLine: { show: false } }
          ],
          series: [
            {
              name: '累计代理收益',
              type: 'bar',
              barMaxWidth: 24,
	              itemStyle: signedBarStyle,
	              data: signedBarData('cumulative_return_pct')
            },
            {
              name: '月化代理收益',
              type: 'bar',
              barMaxWidth: 24,
	              itemStyle: signedBarStyle,
	              data: signedBarData('monthly_return_pct')
            },
            {
              name: '最大回撤',
              type: 'line',
              yAxisIndex: 1,
              smooth: 0.18,
              symbol: 'circle',
              symbolSize: 6,
              lineStyle: { width: 2.2 },
              data: rows.map((row) => numberOrNull(row, 'max_drawdown_pct'))
            }
          ]
        });
      }

      let excessChart = null;
      if (excessNode && payload.benchmark_excess && Array.isArray(payload.benchmark_excess.items) && payload.benchmark_excess.items.length) {
        const benchmarkExcess = payload.benchmark_excess.items;
        const strategyReturnValue = numberOrNull(payload.benchmark_excess, 'strategy_return_pct');
        const benchmarkBarData = (key) => benchmarkExcess.map((item) => ({
          value: typeof item[key] === 'number' ? item[key] : null,
          item
        }));
        excessChart = window.echarts.init(excessNode, null, { renderer: 'canvas' });
        chartInstances.push(excessChart);
        excessChart.setOption({
          backgroundColor: 'transparent',
          textStyle: baseTextStyle,
	          color: [chartTone.orange, chartTone.red],
          tooltip: {
            ...baseTooltip,
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: function(params) {
              const index = params && params.length ? params[0].dataIndex : 0;
              const item = benchmarkExcess[index] || {};
              const lines = [escapeHtml(item.label || '')];
              params.forEach((entry) => {
                lines.push(`${entry.marker}${entry.seriesName}：${pct(entry.value)}`);
              });
              if (item.coverage_note) lines.push(`覆盖状态：${escapeHtml(item.coverage_note)}`);
              return lines.join('<br>');
            }
          },
          legend: { top: 6, textStyle: { color: chartTone.muted } },
          grid: { left: 92, right: 86, top: 58, bottom: 34, containLabel: false },
          xAxis: {
            type: 'value',
            name: '区间涨跌幅',
            nameTextStyle: { color: chartTone.muted },
            axisLabel: { color: chartTone.muted, formatter: '{value}' },
            splitLine,
            axisLine
          },
          yAxis: {
            type: 'category',
            inverse: true,
            data: benchmarkExcess.map((item) => item.label || ''),
            axisLabel: { color: chartTone.text },
            axisTick: { show: false },
            axisLine: { show: false }
          },
          series: [
            {
              name: '策略区间收益',
              type: 'bar',
              barWidth: 7,
              barGap: '18%',
              barCategoryGap: '36%',
              data: benchmarkExcess.map((item) => ({ value: strategyReturnValue, item })),
	              itemStyle: {
	                borderRadius: [0, 6, 6, 0],
	                color: chartTone.orange
	              },
              label: { show: true, position: 'right', color: chartTone.muted, formatter: (params) => pct(params.value) },
              emphasis: { focus: 'series' }
            },
            {
              name: '指数区间涨跌',
              type: 'bar',
              barWidth: 7,
              data: benchmarkBarData('index_return_pct'),
	              itemStyle: { borderRadius: [0, 6, 6, 0], color: chartTone.red },
              label: { show: true, position: 'right', color: chartTone.muted, formatter: (params) => pct(params.value) },
              emphasis: { focus: 'series' }
            }
          ]
        });
      }

      window.addEventListener('resize', () => {
        chartInstances.forEach((chart) => chart.resize());
      });
    })();
  </script>
"""

from daily_report_entry_demo import load_daily_report_data_from_postgres
from daily_report_snapshot_io import load_data_snapshot
from daily_report_render import ReportCriticalDataMissingError
from report import runtime as report_runtime
from report.elimination_tournament import build_sector_capital_preflight_daily_context
from report.elimination_tournament import build_sector_capital_preflight_payload
from report.sector_capital_carrier_strategy import build_sector_capital_carrier_strategy


def _clean(value, default=""):
    text = str(value if value is not None else "").strip()
    return text or default


def _date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _date_text(value):
    if isinstance(value, date):
        return value.isoformat()
    return _clean(value)


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _html(value):
    return html.escape(_clean(value), quote=True)


def _mermaid_svg_id(value, prefix="mermaid"):
    text = _clean(value)
    if not text:
        return f"{prefix}-empty"
    safe = []
    for ch in text:
        if ch.isalnum():
            safe.append(ch.lower())
        elif safe and safe[-1] != "-":
            safe.append("-")
    token = "".join(safe).strip("-")
    return f"{prefix}-{token[:48] or 'block'}"


def _json_for_html(payload):
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("</", "<\\/")
    )


def _echarts_source_path():
    return PROJECT_ROOT / ".generated" / "vendor" / "echarts" / "echarts.min.js"


def _echarts_loader_html():
    source_path = _echarts_source_path()
    if source_path.exists():
        return (
            '<script src="../../.generated/vendor/echarts/echarts.min.js"></script>'
            "<script>"
            "if(!window.echarts){document.write('<script src=\""
            f"{_html(source_path.as_uri())}"
            "\"><\\/script>');}"
            "</script>"
        )
    return ""


def _stock_code(value):
    text = _clean(value)
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 6:
        return digits[-6:]
    return text


def _code_from_row(row):
    if not isinstance(row, dict):
        return ""
    return _stock_code(row.get("code") or row.get("代码") or row.get("stock_code"))


def _name_from_row(row):
    if not isinstance(row, dict):
        return ""
    return _clean(row.get("name") or row.get("名称") or row.get("stock_name"))


def _stock_from_candidate(entry):
    if not isinstance(entry, dict):
        return {}
    stock = entry.get("stock") if isinstance(entry.get("stock"), dict) else {}
    return {
        "name": _clean(stock.get("name") or entry.get("stock_name")),
        "code": _stock_code(stock.get("code") or entry.get("stock_code")),
        "sector": _clean(stock.get("sector") or entry.get("sector")),
    }


def _stock_label(stock):
    stock = stock if isinstance(stock, dict) else {}
    name = _clean(stock.get("name"), "未知")
    code = _stock_code(stock.get("code"))
    return f"{name}({code})" if code else name


def _stock_from_paper_strategy_primary(strategy):
    strategy = strategy if isinstance(strategy, dict) else {}
    primary = strategy.get("primary_candidate") if isinstance(strategy.get("primary_candidate"), dict) else {}
    stock = _stock_from_candidate(primary)
    if stock.get("name") or stock.get("code"):
        return stock
    label = _clean(primary.get("stock_label"))
    match = re.match(r"^(?P<name>.+?)\((?P<code>\d{6})\)$", label)
    if match:
        return {"name": _clean(match.group("name")), "code": _stock_code(match.group("code")), "sector": _clean(primary.get("sector"))}
    return {}


def _review_object_from_paper_strategy(strategy):
    strategy = strategy if isinstance(strategy, dict) else {}
    target = _stock_from_paper_strategy_primary(strategy)
    if _clean(strategy.get("action")) != "paper_participate":
        return {
            "label": _clean(strategy.get("action_label"), "纸面不参与"),
            "target": target,
            "source": "sector_capital_carrier_strategy",
            "reason": _clean(strategy.get("action_reason"), "板块资金扩散链路未恢复出纸面复核对象"),
            "review_only": True,
        }
    if not target:
        return {
            "label": "纸面主样本对象缺失",
            "target": {},
            "source": "sector_capital_carrier_strategy",
            "reason": "板块资金扩散链路有纸面主样本意图，但主样本缺少股票代码或名称",
            "review_only": True,
        }
    return {
        "label": "纸面复核对象",
        "target": target,
        "source": "sector_capital_carrier_strategy",
        "reason": _clean(strategy.get("action_reason"), "板块资金扩散链路恢复出资金载体主样本"),
        "review_only": True,
    }


def _action_stock_label(action):
    action = action if isinstance(action, dict) else {}
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    return _stock_label(target) if target else "无执行对象"


def _paper_review_contrast(legacy_action, review_object):
    legacy_action = legacy_action if isinstance(legacy_action, dict) else {}
    review_object = review_object if isinstance(review_object, dict) else {}
    legacy_pct = _final_position_pct(legacy_action)
    legacy_target = legacy_action.get("target") if isinstance(legacy_action.get("target"), dict) else {}
    review_target = review_object.get("target") if isinstance(review_object.get("target"), dict) else {}
    legacy_key = _stock_code(legacy_target.get("code")) or _clean(legacy_target.get("name"))
    review_key = _stock_code(review_target.get("code")) or _clean(review_target.get("name"))
    if not review_key:
        return {}
    if legacy_key == review_key:
        return {}
    return {
        "type": "legacy_action_vs_paper_review_object",
        "legacy_action": {
            "label": _clean(legacy_action.get("label"), f"{legacy_pct}%"),
            "position_pct": legacy_pct,
            "target": legacy_target,
            "stock_label": _action_stock_label(legacy_action),
            "source": _clean(legacy_action.get("source"), "legacy_final_action"),
            "reason": _clean(legacy_action.get("reason")),
        },
        "paper_review_object": {
            "label": _clean(review_object.get("label"), "纸面复核对象"),
            "target": review_target,
            "stock_label": _action_stock_label(review_object),
            "source": _clean(review_object.get("source"), "sector_capital_carrier_strategy"),
            "reason": _clean(review_object.get("reason")),
            "review_only": True,
        },
        "resolution": "板块优先链路只作为纸面复核对象，不覆盖原日报T0最终动作",
    }


def _load_effective_decision_data(requested_date, *, loader, max_lookback_days=10):
    requested = _date(requested_date)
    errors = []
    for offset in range(max_lookback_days + 1):
        current = requested - timedelta(days=offset)
        current_text = current.isoformat()
        try:
            data = loader(current_text)
        except Exception as exc:  # replay probing must record missing days, not hide them
            errors.append({"date": current_text, "error": f"{type(exc).__name__}: {exc}"})
            continue
        note = ""
        if current_text != requested_date:
            note = f"{requested_date} 无可用日报事实，改用上一可用交易日 {current_text}"
        return data, {
            "requested_decision_date": requested_date,
            "effective_decision_date": current_text,
            "fallback_used": current_text != requested_date,
            "coverage_note": note or f"{requested_date} 日报事实可用",
            "missing_attempts": errors,
        }
    raise ReportCriticalDataMissingError(f"{requested_date} 向前 {max_lookback_days} 天没有可用日报事实")


def _first_dict(*sources):
    for source in sources:
        if isinstance(source, dict) and source:
            return source
    return {}


def _daily_context(data, trade_date=""):
    data = data if isinstance(data, dict) else {}
    execution_context = data.get("execution_stage_context") if isinstance(data.get("execution_stage_context"), dict) else {}
    market_snapshot = data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {}
    return build_sector_capital_preflight_daily_context(
        data,
        execution_context,
        market_snapshot,
        trade_date=trade_date or data.get("target_date") or data.get("trade_date"),
    )


def _build_preflight_payload(trade_date, data, *, variant="forward-replay"):
    data = data if isinstance(data, dict) else {}
    execution_context = data.get("execution_stage_context") if isinstance(data.get("execution_stage_context"), dict) else {}
    market_snapshot = data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {}
    selection_workflow = _first_dict(
        data.get("selection_workflow"),
        execution_context.get("selection_workflow"),
        market_snapshot.get("selection_workflow"),
    )
    final_target_resolution = _first_dict(
        data.get("final_target_resolution"),
        execution_context.get("final_target_resolution"),
        market_snapshot.get("final_target_resolution"),
    )
    position_decision = _first_dict(
        data.get("position_decision"),
        execution_context.get("position_decision"),
        market_snapshot.get("position_decision"),
    )
    elimination = report_runtime._build_runtime_elimination_tournament_payload(
        target_date=trade_date,
        run_mode=variant,
        data=data,
        execution_stage_context=execution_context,
        market_research_snapshot=market_snapshot,
        selection_workflow=selection_workflow,
        final_target_resolution=final_target_resolution,
        position_decision=position_decision,
    )
    return build_sector_capital_preflight_payload(
        trade_date=trade_date,
        variant=variant,
        source_payloads={
            "selection_workflow": selection_workflow,
            "final_target_resolution": final_target_resolution,
            "position_decision": position_decision,
            "elimination_tournament_payload": elimination,
            "sector_capital_carrier_strategy": _build_paper_strategy_decision(trade_date, data),
            "daily_context": _daily_context(data, trade_date),
        },
        elimination_tournament_payload=elimination,
    )


def _first_layer_candidates(preflight_payload):
    for layer in preflight_payload.get("layers", []) if isinstance(preflight_payload, dict) else []:
        if _clean(layer.get("id")) in {"final_action", "final_resolution"}:
            continue
        entries = layer.get("entries")
        stock_entries = []
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                continue
            stock = _stock_from_candidate(entry)
            if stock.get("code") or stock.get("name"):
                stock_entries.append(entry)
        if stock_entries:
            return stock_entries
    return []


def _workflow_candidates_by_code(data):
    workflow = _first_dict(
        data.get("selection_workflow") if isinstance(data, dict) else {},
        (data.get("execution_stage_context") or {}).get("selection_workflow") if isinstance(data, dict) and isinstance(data.get("execution_stage_context"), dict) else {},
        (data.get("market_research_snapshot") or {}).get("selection_workflow") if isinstance(data, dict) and isinstance(data.get("market_research_snapshot"), dict) else {},
    )
    by_code = {}
    for row in workflow.get("candidate_pool", []) if isinstance(workflow, dict) else []:
        stock = row.get("stock") if isinstance(row, dict) and isinstance(row.get("stock"), dict) else {}
        code = _stock_code(stock.get("code") or row.get("stock_code"))
        if code:
            by_code.setdefault(code, []).append(row)
    return by_code


def _rows_by_code(rows):
    result = {}
    for row in rows if isinstance(rows, list) else []:
        code = _code_from_row(row)
        if code:
            result.setdefault(code, []).append(row)
    return result


def _sector_aliases(*values):
    names = set()
    for value in values:
        if isinstance(value, (list, tuple, set)):
            names.update(_sector_aliases(*value))
            continue
        text = _clean(value)
        if not text:
            continue
        names.add(text)
        if "电力" in text or "发电" in text:
            names.update({"电力", "新型电力", "火力发电", "绿色电力"})
        if "煤炭" in text:
            names.update({"煤炭", "煤炭开采", "煤炭开采加工"})
        if "半导体" in text or "芯片" in text:
            names.update({"半导体", "国产芯片替代", "存储芯片", "汽车芯片"})
        if "化学纤维" in text or text == "化纤":
            names.update({"化学纤维", "化纤"})
        if "轨交" in text:
            names.update({"轨交设备"})
        if "元件" in text or "元器件" in text or "被动元件" in text or "PCB" in text:
            names.update({"元件", "元器件", "被动元件", "PCB", "消费电子"})
        if "通信" in text or "CPO" in text or "光通信" in text or "共封装光学" in text:
            names.update({"通信设备", "光通信/CPO", "CPO", "共封装光学", "高速连接器"})
        if "小金属" in text or "锗" in text or "稀土" in text:
            names.update({"小金属", "稀土永磁", "金属新材料"})
        if "化学制品" in text or "化工" in text or "氟" in text:
            names.update({"化学制品", "化工原料", "氟化工"})
    return names


def _names_match(left, right):
    left = _clean(left)
    right = _clean(right)
    if not left or not right:
        return False
    if left == right:
        return True
    if len(left) >= 2 and len(right) >= 2 and (left in right or right in left):
        return True
    return False


def _matching_named_rows(rows, names, *, key="name"):
    result = []
    for row in rows if isinstance(rows, list) else []:
        name = _clean(row.get(key)) if isinstance(row, dict) else ""
        if any(_names_match(name, alias) for alias in names):
            result.append(row)
    return result


def _matching_sector_limit_rows(zt_pool_by_sector, names):
    result = []
    if not isinstance(zt_pool_by_sector, dict):
        return result
    for sector, rows in zt_pool_by_sector.items():
        if any(_names_match(sector, alias) for alias in names):
            result.extend(rows if isinstance(rows, list) else [])
    return result


def _fund_flow_rows(data, names):
    sector_fund_flow = data.get("sector_fund_flow") if isinstance(data, dict) else {}
    rows = []
    if isinstance(sector_fund_flow, dict):
        for side in ("inflow", "outflow"):
            rows.extend(sector_fund_flow.get(side) or [])
    return _matching_named_rows(rows, names, key="name")


def _build_paper_strategy_decision(trade_date, data):
    return build_sector_capital_carrier_strategy(trade_date, data)


def _paper_candidate_as_entry(candidate):
    stock = candidate.get("stock") if isinstance(candidate.get("stock"), dict) else {}
    return {
        "stock": stock,
        "stock_name": stock.get("name"),
        "stock_code": stock.get("code"),
        "sector": stock.get("sector") or candidate.get("sector"),
        "status": candidate.get("status") or "纸面候选",
        "reason": candidate.get("reason"),
        "entry_basis": candidate.get("reason"),
        "candidate_origin": candidate.get("candidate_origin"),
        "source_pools": candidate.get("source_pools") if isinstance(candidate.get("source_pools"), list) else [],
    }


def _paper_outcome_from_evaluation(evaluation):
    outcome = _clean(evaluation.get("target_outcome")) if isinstance(evaluation, dict) else ""
    if "后验失效" in outcome:
        return {"code": "paper_miss", "label": "纸面未通过复核"}
    if any(token in outcome for token in ("价格延续命中", "流程未接住", "走强")):
        return {"code": "paper_stock_hit", "label": "纸面个股命中"}
    if "板块方向命中" in outcome:
        return {"code": "paper_sector_hit_stock_missed", "label": "板块命中但个股未到执行级别"}
    if "仅作热度观察" in outcome:
        return {"code": "paper_attention_only", "label": "只延续热度观察"}
    return {"code": "paper_miss", "label": "纸面未通过复核"}


def _attach_paper_target_review(
    paper_strategy,
    buy_date,
    buy_data,
    sell_date=None,
    sell_data=None,
    price_refill=None,
    decision_date=None,
    decision_data=None,
    minute_refill=None,
    account_capital=10000,
    lot_size=100,
):
    candidates = paper_strategy.get("paper_candidates") if isinstance(paper_strategy, dict) else []
    evaluations = []
    for candidate in candidates[:8]:
        entry = _paper_candidate_as_entry(candidate)
        evaluation = _target_evidence_for(entry, buy_data)
        paper_outcome = _paper_outcome_from_evaluation(evaluation)
        evaluation["paper_outcome"] = paper_outcome["code"]
        evaluation["paper_outcome_label"] = paper_outcome["label"]
        evaluation["buy_review_date"] = buy_date
        evaluation["sell_review_date"] = sell_date or ""
        evaluation["tplus2_exit_review"] = _build_tplus2_exit_review(
            entry,
            buy_date,
            buy_data,
            sell_date=sell_date,
            sell_data=sell_data,
            price_refill=price_refill,
            decision_date=decision_date,
            decision_data=decision_data,
            minute_refill=minute_refill,
            account_capital=account_capital,
            lot_size=lot_size,
            paper_action=paper_strategy.get("action"),
        )
        evaluations.append(evaluation)
    primary_label = _clean((paper_strategy.get("primary_candidate") or {}).get("stock_label")) if isinstance(paper_strategy, dict) else ""
    primary_evaluation = next((item for item in evaluations if item.get("stock_label") == primary_label), {})
    paper_strategy["target_evaluations"] = evaluations
    paper_strategy["target_summary"] = {
        "primary_stock": primary_label,
        "primary_outcome": _clean(primary_evaluation.get("paper_outcome"), "no_primary"),
        "primary_outcome_label": _clean(primary_evaluation.get("paper_outcome_label"), "没有纸面主样本"),
        "hit_count": sum(1 for item in evaluations if item.get("paper_outcome") == "paper_stock_hit"),
        "sector_hit_count": sum(1 for item in evaluations if item.get("paper_outcome") == "paper_sector_hit_stock_missed"),
        "reviewed_count": len(evaluations),
        "buy_date": buy_date,
        "sell_date": sell_date or "",
    }
    return paper_strategy


def _fmt_pct(value):
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return ""


def _fmt_signed_pct(value):
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return ""


def _fmt_signed_point(value):
    try:
        return f"{float(value):+.2f}个百分点"
    except (TypeError, ValueError):
        return ""


def _row_change_pct(row):
    if not isinstance(row, dict):
        return None
    for key in ("change_pct", "涨跌幅", "zdf"):
        value = _safe_float(row.get(key), None)
        if value is not None:
            return value
    return None


def _row_price(row, *keys):
    if not isinstance(row, dict):
        return None
    for key in keys:
        value = _safe_float(row.get(key), None)
        if value is not None and value > 0:
            return value
    return None


def _price_rows_by_code(data):
    data = data if isinstance(data, dict) else {}
    sources = (
        data.get("hot_rank_top50") or [],
        data.get("hot_rank_top30") or [],
        data.get("integrated_hot_list") or [],
        data.get("turnover_rank") or [],
        data.get("zt_pool") or [],
        data.get("lianban_data") or [],
    )
    result = {}
    for rows in sources:
        for row in rows if isinstance(rows, list) else []:
            code = _code_from_row(row)
            if code:
                result.setdefault(code, []).append(row)
    return result


def _normalize_daily_price_bar(row, *, source_label):
    row = row if isinstance(row, dict) else {}
    open_price = _row_price(row, "open", "open_price", "开盘价")
    close_price = _row_price(row, "close", "close_price", "price", "最新价", "收盘价")
    high_price = _row_price(row, "high", "high_price", "最高价")
    low_price = _row_price(row, "low", "low_price", "最低价")
    if not any(value is not None for value in (open_price, close_price, high_price, low_price)):
        return {}
    return {
        "open": open_price,
        "close": close_price,
        "high": high_price,
        "low": low_price,
        "change_pct": _row_change_pct(row),
        "pre_close": _row_price(row, "pre_close", "昨收", "前收盘"),
        "source": source_label,
    }


def _normalize_minute_bar(row, *, source_label):
    row = row if isinstance(row, dict) else {}
    datetime_text = _clean(row.get("datetime") or row.get("trade_time") or row.get("day") or row.get("时间"))
    date_text = _date_text(row.get("date") or (datetime_text[:10] if len(datetime_text) >= 10 else ""))
    time_text = _clean(row.get("time") or (datetime_text[11:19] if len(datetime_text) >= 16 else ""))
    if time_text and len(time_text) == 5:
        time_text += ":00"
    if not date_text or not time_text:
        return {}
    normalized = _normalize_daily_price_bar(row, source_label=source_label)
    if not normalized:
        return {}
    normalized.update(
        {
            "datetime": f"{date_text} {time_text}",
            "date": date_text,
            "time": time_text,
            "source": _clean(row.get("data_source") or row.get("source"), source_label),
        }
    )
    return normalized


def _stock_kline_bar_from_cache(code, target_date):
    code = _stock_code(code)
    target_date = _date_text(target_date)
    if not code or not target_date:
        return None
    path = PROJECT_ROOT / "data" / "market-facts" / "stock-klines" / f"{target_date}-{code}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    stock_klines = payload.get("stock_klines") or payload.get("stockKlines") or {}
    rows = []
    if isinstance(stock_klines, dict):
        rows = stock_klines.get(code) or stock_klines.get(_stock_code(code)) or []
    elif isinstance(stock_klines, list):
        rows = stock_klines
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and _date_text(row.get("date") or row.get("trade_date")) == target_date:
            return dict(row)
    return None


class DailyPriceRefill:
    def __init__(
        self,
        *,
        fetch_daily_price_bars_fn=None,
        fetch_daily_price_bars_by_trade_date_fn=None,
        source_label="TuShare日线",
        startup_error="",
    ):
        self.fetch_daily_price_bars_fn = fetch_daily_price_bars_fn
        self.fetch_daily_price_bars_by_trade_date_fn = fetch_daily_price_bars_by_trade_date_fn
        self.source_label = source_label
        self.startup_error = startup_error
        self.cache = {}
        self.date_cache = {}
        self.date_error_cache = {}
        self.summary = {
            "schema_version": "daily_price_refill_summary.v1",
            "enabled": True,
            "source": source_label,
            "attempted": 0,
            "trade_date_requests": 0,
            "filled": 0,
            "missing": 0,
            "errors": 0,
            "filled_samples": [],
            "missing_samples": [],
            "error_samples": [],
            "date_mismatch_samples": [],
            "basis": "TuShare优先提供T+1/T+2价格事实，不参与T0候选生成、淘汰链生成或最终动作生成",
        }

    def __call__(self, code, trade_date):
        code = _stock_code(code)
        trade_date = _date_text(trade_date)
        if not code or not trade_date:
            return {}
        key = (code, trade_date)
        if key in self.cache:
            return self.cache[key]
        self.summary["attempted"] += 1
        label = f"{trade_date} {code}"
        if self.startup_error:
            self.summary["errors"] += 1
            self.summary["missing"] += 1
            self.summary["error_samples"].append(f"{label}: {self.startup_error}")
            self.cache[key] = {}
            return {}
        if self.fetch_daily_price_bars_by_trade_date_fn is not None:
            if trade_date in self.date_error_cache:
                self.summary["missing"] += 1
                self.summary["missing_samples"].append(label)
                self.cache[key] = {}
                return {}
            try:
                date_rows = self.date_cache.get(trade_date)
                if date_rows is None:
                    self.summary["trade_date_requests"] += 1
                    date_rows = self.fetch_daily_price_bars_by_trade_date_fn(trade_date)
                    self.date_cache[trade_date] = date_rows
                for row in date_rows if isinstance(date_rows, list) else []:
                    if _stock_code((row or {}).get("stock_code") or (row or {}).get("ts_code")) != code:
                        continue
                    row_date = _date_text((row or {}).get("date") or (row or {}).get("trade_date"))
                    if row_date != trade_date:
                        mismatch = f"{label}: 返回日期{row_date or '缺失'}"
                        self.summary["date_mismatch_samples"].append(mismatch)
                        continue
                    source_detail = _clean((row or {}).get("data_source") or (row or {}).get("source"))
                    source_label = self.source_label + (f"({source_detail})" if source_detail else "")
                    matched = _normalize_daily_price_bar(row, source_label=source_label)
                    if matched:
                        self.summary["filled"] += 1
                        self.summary["filled_samples"].append(label)
                        self.cache[key] = matched
                        return matched
            except Exception as exc:
                error_text = f"batch {type(exc).__name__}: {exc}"
                self.date_error_cache[trade_date] = error_text
                self.summary["errors"] += 1
                self.summary["error_samples"].append(f"{trade_date}: {error_text}")
                self.summary["missing"] += 1
                self.summary["missing_samples"].append(label)
                self.cache[key] = {}
                return {}
            self.summary["missing"] += 1
            self.summary["missing_samples"].append(label)
            self.cache[key] = {}
            return {}
        try:
            bars = self.fetch_daily_price_bars_fn(code, trade_date, trade_date, is_index=False)
        except Exception as exc:
            self.summary["errors"] += 1
            self.summary["missing"] += 1
            self.summary["error_samples"].append(f"{label}: {type(exc).__name__}: {exc}")
            self.cache[key] = {}
            return {}
        matched = {}
        for row in bars if isinstance(bars, list) else []:
            if not isinstance(row, dict):
                continue
            row_date = _date_text(row.get("date") or row.get("trade_date"))
            if row_date and row_date != trade_date:
                continue
            source_detail = _clean(row.get("data_source") or row.get("source"))
            source_label = self.source_label + (f"({source_detail})" if source_detail else "")
            matched = _normalize_daily_price_bar(row, source_label=source_label)
            if matched:
                break
        if matched:
            self.summary["filled"] += 1
            self.summary["filled_samples"].append(label)
            self.cache[key] = matched
            return matched
        self.summary["missing"] += 1
        self.summary["missing_samples"].append(label)
        self.cache[key] = {}
        return {}


def build_tushare_daily_price_refill(*, fetch_daily_price_bars_fn=None, fetch_daily_price_bars_by_trade_date_fn=None):
    if fetch_daily_price_bars_fn is None or fetch_daily_price_bars_by_trade_date_fn is None:
        try:
            from market_data.tushare_service import fetch_daily_price_bars as default_daily_fetch
            from market_data.tushare_service import fetch_daily_price_bars_by_trade_date as default_trade_date_fetch
        except Exception as exc:
            return DailyPriceRefill(
                fetch_daily_price_bars_fn=None,
                fetch_daily_price_bars_by_trade_date_fn=None,
                startup_error=f"{type(exc).__name__}: {exc}",
            )
        fetch_daily_price_bars_fn = fetch_daily_price_bars_fn or default_daily_fetch
        fetch_daily_price_bars_by_trade_date_fn = fetch_daily_price_bars_by_trade_date_fn or default_trade_date_fetch
    return DailyPriceRefill(
        fetch_daily_price_bars_fn=fetch_daily_price_bars_fn,
        fetch_daily_price_bars_by_trade_date_fn=fetch_daily_price_bars_by_trade_date_fn,
    )


class MinutePriceRefill:
    def __init__(
        self,
        *,
        fetch_minute_bars_fn=None,
        source_label="TuShare分时",
        startup_error="",
        max_errors=5,
    ):
        self.fetch_minute_bars_fn = fetch_minute_bars_fn
        self.source_label = source_label
        self.startup_error = startup_error
        self.max_errors = max_errors
        self.cache = {}
        self.summary = {
            "schema_version": "minute_price_refill_summary.v1",
            "enabled": True,
            "source": source_label,
            "attempted": 0,
            "filled": 0,
            "missing": 0,
            "errors": 0,
            "filled_samples": [],
            "missing_samples": [],
            "error_samples": [],
            "basis": "分时事实只用于复核T+1买点是否真实可达，不参与T0候选生成、淘汰链生成或最终动作生成",
        }

    def __call__(self, code, trade_date):
        code = _stock_code(code)
        trade_date = _date_text(trade_date)
        if not code or not trade_date:
            return []
        key = (code, trade_date)
        if key in self.cache:
            return self.cache[key]
        self.summary["attempted"] += 1
        label = f"{trade_date} {code}"
        if self.startup_error or not callable(self.fetch_minute_bars_fn):
            self.summary["errors" if self.startup_error else "missing"] += 1
            if self.startup_error:
                self.summary["error_samples"].append(f"{label}: {self.startup_error}")
            else:
                self.summary["missing_samples"].append(label)
            self.cache[key] = []
            return []
        if self.max_errors and self.summary.get("errors", 0) >= self.max_errors:
            self.summary["missing"] += 1
            self.summary["missing_samples"].append(f"{label}: 分时事实源连续错误，停止继续请求")
            self.cache[key] = []
            return []
        try:
            rows = self.fetch_minute_bars_fn(code, trade_date)
        except Exception as exc:
            self.summary["errors"] += 1
            self.summary["missing"] += 1
            self.summary["error_samples"].append(f"{label}: {type(exc).__name__}: {exc}")
            self.cache[key] = []
            return []
        bars = [_normalize_minute_bar(row, source_label=self.source_label) for row in rows or []]
        bars = sorted([bar for bar in bars if bar and bar.get("date") == trade_date], key=lambda item: item.get("datetime", ""))
        if bars:
            self.summary["filled"] += 1
            self.summary["filled_samples"].append(label)
        else:
            self.summary["missing"] += 1
            self.summary["missing_samples"].append(label)
        self.cache[key] = bars
        return bars


def build_tushare_minute_price_refill(*, fetch_minute_bars_fn=None, timeout_seconds=3, max_errors=5):
    if fetch_minute_bars_fn is None:
        try:
            from market_data.tushare_minute_service import fetch_tushare_minute_bars
        except Exception as exc:
            return MinutePriceRefill(startup_error=f"{type(exc).__name__}: {exc}")

        def fetch_minute_bars(code, trade_date):
            return fetch_tushare_minute_bars(code, period="5", target_date=trade_date, timeout_seconds=timeout_seconds)

        fetch_minute_bars_fn = fetch_minute_bars
    return MinutePriceRefill(fetch_minute_bars_fn=fetch_minute_bars_fn, max_errors=max_errors)


def build_static_minute_price_refill(rows_by_key, *, source_label="静态分时"):
    rows_by_key = rows_by_key if isinstance(rows_by_key, dict) else {}

    def fetch_minute_bars(code, trade_date):
        code = _stock_code(code)
        trade_date = _date_text(trade_date)
        return rows_by_key.get((code, trade_date)) or rows_by_key.get(f"{trade_date}-{code}") or []

    return MinutePriceRefill(fetch_minute_bars_fn=fetch_minute_bars, source_label=source_label)


def _empty_price_refill_summary():
    return {
        "schema_version": "daily_price_refill_summary.v1",
        "enabled": False,
        "source": "",
        "attempted": 0,
        "trade_date_requests": 0,
        "filled": 0,
        "missing": 0,
        "errors": 0,
        "filled_samples": [],
        "missing_samples": [],
        "error_samples": [],
        "date_mismatch_samples": [],
        "basis": "未开启外部价格获取，只使用日报事实和本地日K缓存",
    }


def _empty_minute_refill_summary():
    return {
        "schema_version": "minute_price_refill_summary.v1",
        "enabled": False,
        "source": "",
        "attempted": 0,
        "filled": 0,
        "missing": 0,
        "errors": 0,
        "filled_samples": [],
        "missing_samples": [],
        "error_samples": [],
        "basis": "未开启分时事实获取时，只用涨停池、热榜和日线代理识别追高或可能买不到，不替代分时成交路径",
    }


def _minute_refill_summary(minute_refill):
    summary = getattr(minute_refill, "summary", None)
    if isinstance(summary, dict):
        result = dict(summary)
        for key in ("filled_samples", "missing_samples", "error_samples", "date_mismatch_samples"):
            result[key] = list(result.get(key) or [])[:30]
        return result
    return _empty_minute_refill_summary()


def _price_refill_summary(price_refill):
    summary = getattr(price_refill, "summary", None)
    if isinstance(summary, dict):
        result = dict(summary)
        for key in ("filled_samples", "missing_samples", "error_samples"):
            result[key] = list(result.get(key) or [])[:30]
        return result
    if callable(price_refill):
        result = _empty_price_refill_summary()
        result["enabled"] = True
        result["source"] = "自定义价格事实源"
        result["basis"] = "自定义价格事实源优先提供T+1/T+2价格事实，不参与T0候选生成、淘汰链生成或最终动作生成"
        return result
    return _empty_price_refill_summary()


class OpenTradeDateRefill:
    def __init__(self, *, fetch_open_trade_dates_fn=None, source_label="TuShare交易日历", startup_error=""):
        self.fetch_open_trade_dates_fn = fetch_open_trade_dates_fn
        self.source_label = source_label
        self.startup_error = startup_error
        self.cache = {}
        self.summary = {
            "schema_version": "open_trade_date_refill_summary.v1",
            "enabled": True,
            "source": source_label,
            "attempted": 0,
            "range_requests": 0,
            "open_dates_filled": 0,
            "filled": 0,
            "missing": 0,
            "errors": 0,
            "open_date_samples": [],
            "filled_samples": [],
            "missing_samples": [],
            "error_samples": [],
            "basis": "TuShare交易日历优先提供T+2卖出日日期，不参与T0候选生成、淘汰链生成或最终动作生成",
        }

    def open_dates(self, start_date, end_date):
        start_date = _date_text(start_date)
        end_date = _date_text(end_date)
        if not start_date or not end_date:
            return []
        cache_key = (start_date, end_date)
        if cache_key in self.cache:
            return list(self.cache[cache_key] or [])
        self.summary["range_requests"] += 1
        if self.startup_error:
            self.summary["errors"] += 1
            self.summary["missing"] += 1
            self.summary["error_samples"].append(f"{start_date}->{end_date}: {self.startup_error}")
            self.cache[cache_key] = []
            return []
        try:
            dates = self.fetch_open_trade_dates_fn(start_date, end_date)
        except Exception as exc:
            self.summary["errors"] += 1
            self.summary["missing"] += 1
            self.summary["error_samples"].append(f"{start_date}->{end_date}: {type(exc).__name__}: {exc}")
            self.cache[cache_key] = []
            return []
        open_dates = sorted(set(_date_text(item) for item in dates if _date_text(item)))
        if open_dates:
            self.summary["open_dates_filled"] += len(open_dates)
            self.summary["open_date_samples"].append(f"{start_date}->{end_date}: {len(open_dates)}日")
        else:
            self.summary["missing"] += 1
            self.summary["missing_samples"].append(f"{start_date}->{end_date}")
        self.cache[cache_key] = open_dates
        return list(open_dates)

    def next_after(self, trade_date):
        trade_date = _date_text(trade_date)
        if not trade_date:
            return ""
        if trade_date in self.cache:
            return self.cache[trade_date]
        self.summary["attempted"] += 1
        if self.startup_error:
            self.summary["errors"] += 1
            self.summary["missing"] += 1
            self.summary["error_samples"].append(f"{trade_date}: {self.startup_error}")
            self.cache[trade_date] = ""
            return ""
        start = (_date(trade_date) + timedelta(days=1)).isoformat()
        end = (_date(trade_date) + timedelta(days=14)).isoformat()
        try:
            dates = self.fetch_open_trade_dates_fn(start, end)
        except Exception as exc:
            self.summary["errors"] += 1
            self.summary["missing"] += 1
            self.summary["error_samples"].append(f"{trade_date}: {type(exc).__name__}: {exc}")
            self.cache[trade_date] = ""
            return ""
        valid_dates = sorted(_date_text(item) for item in dates if _date_text(item) > trade_date)
        next_date = valid_dates[0] if valid_dates else ""
        if next_date:
            self.summary["filled"] += 1
            self.summary["filled_samples"].append(f"{trade_date}->{next_date}")
        else:
            self.summary["missing"] += 1
            self.summary["missing_samples"].append(trade_date)
        self.cache[trade_date] = next_date
        return next_date


def build_tushare_open_trade_date_refill(*, fetch_open_trade_dates_fn=None):
    if fetch_open_trade_dates_fn is None:
        try:
            from market_data.tushare_market_activity_service import fetch_tushare_open_trade_dates as fetch_open_trade_dates_fn
        except Exception as exc:
            return OpenTradeDateRefill(
                fetch_open_trade_dates_fn=None,
                startup_error=f"{type(exc).__name__}: {exc}",
            )
    return OpenTradeDateRefill(fetch_open_trade_dates_fn=fetch_open_trade_dates_fn)


def _empty_trade_calendar_refill_summary():
    return {
        "schema_version": "open_trade_date_refill_summary.v1",
        "enabled": False,
        "source": "",
        "attempted": 0,
        "range_requests": 0,
        "open_dates_filled": 0,
        "filled": 0,
        "missing": 0,
        "errors": 0,
        "open_date_samples": [],
        "filled_samples": [],
        "missing_samples": [],
        "error_samples": [],
        "basis": "未开启外部交易日历，T+2日期只来自已有历史日报日期序列",
    }


def _trade_calendar_refill_summary(trade_calendar_refill):
    summary = getattr(trade_calendar_refill, "summary", None)
    if isinstance(summary, dict):
        result = dict(summary)
        for key in ("open_date_samples", "filled_samples", "missing_samples", "error_samples"):
            result[key] = list(result.get(key) or [])[:30]
        return result
    return _empty_trade_calendar_refill_summary()


def _daily_price_bar_for(code, trade_date, data, price_refill=None):
    code = _stock_code(code)
    if not code:
        return {}
    if callable(price_refill):
        refilled = price_refill(code, trade_date)
        if isinstance(refilled, dict) and refilled:
            normalized = _normalize_daily_price_bar(
                refilled,
                source_label=_clean(refilled.get("source"), "外部日线事实源"),
            )
            if normalized:
                return normalized
    for row in _price_rows_by_code(data).get(code) or []:
        normalized = _normalize_daily_price_bar(row, source_label="T+1/T+2列表日线字段")
        if normalized:
            return normalized
    cached = _stock_kline_bar_from_cache(code, trade_date)
    if cached:
        normalized = _normalize_daily_price_bar(cached, source_label="本地日K缓存")
        if normalized:
            return normalized
    return {}


def _pct_change_from_prices(exit_price, entry_price):
    exit_price = _safe_float(exit_price)
    entry_price = _safe_float(entry_price)
    if not exit_price or not entry_price:
        return None
    return (exit_price / entry_price - 1) * 100


def _intraday_mid_price(bar):
    high_price = _safe_float((bar or {}).get("high"))
    low_price = _safe_float((bar or {}).get("low"))
    close_price = _safe_float((bar or {}).get("close"))
    if high_price is not None and low_price is not None and high_price > 0 and low_price > 0:
        return (high_price + low_price) / 2
    return close_price


def _window_price(bar, field):
    if field == "intraday_mid":
        return _intraday_mid_price(bar)
    return _safe_float((bar or {}).get(field))


def _sell_window_price(bar, field):
    return _window_price(bar, field)


def _stock_limit_pct(code):
    code = _stock_code(code)
    if code.startswith(("300", "301", "688")):
        return 20.0
    if code.startswith(("8", "4", "9")):
        return 30.0
    return 10.0


def _bar_change_pct(bar):
    if not isinstance(bar, dict) or not bar:
        return None
    change = _safe_float(bar.get("change_pct"), None)
    if change is not None:
        return change
    close_price = _safe_float(bar.get("close"), None)
    pre_close = _safe_float(bar.get("pre_close"), None)
    if close_price is not None and pre_close:
        return _pct_change_from_prices(close_price, pre_close)
    open_price = _safe_float(bar.get("open"), None)
    if close_price is not None and open_price:
        return _pct_change_from_prices(close_price, open_price)
    return None


def _bar_with_pre_close(bar, pre_close):
    bar = dict(bar) if isinstance(bar, dict) else {}
    if not bar:
        return {}
    if _safe_float(bar.get("pre_close"), None) is None:
        pre_close_value = _safe_float(pre_close, None)
        if pre_close_value is not None:
            bar["pre_close"] = pre_close_value
    return bar


def _link_price_path_pre_close(decision_bar, buy_bar, sell_bar):
    decision_bar = dict(decision_bar) if isinstance(decision_bar, dict) else {}
    buy_bar = _bar_with_pre_close(buy_bar, decision_bar.get("close"))
    sell_bar = _bar_with_pre_close(sell_bar, buy_bar.get("close"))
    return decision_bar, buy_bar, sell_bar


def _limit_state(code, bar):
    change_pct = _bar_change_pct(bar)
    if change_pct is None:
        return "待补"
    limit_pct = _stock_limit_pct(code)
    if change_pct >= limit_pct - 0.5:
        return "接近涨停"
    if change_pct <= -limit_pct + 0.5:
        return "接近跌停"
    if change_pct >= limit_pct * 0.75:
        return "接近涨停"
    if change_pct <= -limit_pct * 0.75:
        return "接近跌停"
    return "普通波动"


def _price_path_day(code, trade_date, bar, role):
    return {
        "role": role,
        "trade_date": trade_date or "",
        "change_pct": round(_bar_change_pct(bar), 2) if _bar_change_pct(bar) is not None else None,
        "limit_state": _limit_state(code, bar),
        "open": round(_safe_float((bar or {}).get("open"), 0), 4) if _safe_float((bar or {}).get("open"), None) is not None else None,
        "high": round(_safe_float((bar or {}).get("high"), 0), 4) if _safe_float((bar or {}).get("high"), None) is not None else None,
        "low": round(_safe_float((bar or {}).get("low"), 0), 4) if _safe_float((bar or {}).get("low"), None) is not None else None,
        "close": round(_safe_float((bar or {}).get("close"), 0), 4) if _safe_float((bar or {}).get("close"), None) is not None else None,
        "source": _clean((bar or {}).get("source"), "待补"),
    }


def _minute_time_to_int(value):
    text = _clean(value)
    if not text:
        return None
    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if match:
        try:
            hour = int(match.group(1))
            minute = int(match.group(2))
            if 0 <= hour < 24 and 0 <= minute < 60:
                return hour * 60 + minute
        except (TypeError, ValueError):
            return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        if len(digits) >= 6:
            compact = digits[-6:]
        elif len(digits) == 5:
            compact = "0" + digits
        elif len(digits) == 4:
            compact = digits + "00"
        elif len(digits) == 3:
            compact = "0" + digits + "00"
        else:
            compact = ""
        if compact:
            try:
                hour = int(compact[:2])
                minute = int(compact[2:4])
                if 0 <= hour < 24 and 0 <= minute < 60:
                    return hour * 60 + minute
            except (TypeError, ValueError):
                return None
    try:
        parts = text.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (IndexError, TypeError, ValueError):
        return None


def _time_label_from_minutes(value):
    if value is None:
        return ""
    try:
        hour = int(value) // 60
        minute = int(value) % 60
    except (TypeError, ValueError):
        return ""
    return f"{hour:02d}:{minute:02d}"


def _bar_field_change_pct(bar, field):
    bar = bar if isinstance(bar, dict) else {}
    price = _safe_float(bar.get(field), None)
    if price is None:
        return None
    pre_close = _safe_float(bar.get("pre_close"), None)
    if not pre_close:
        close_price = _safe_float(bar.get("close"), None)
        change_pct = _bar_change_pct(bar)
        if close_price and change_pct is not None and change_pct > -99.9:
            pre_close = close_price / (1 + change_pct / 100)
    if not pre_close:
        return None
    return _pct_change_from_prices(price, pre_close)


def _buyability_proxy_rows_for(code, buy_data):
    code = _stock_code(code)
    buy_data = buy_data if isinstance(buy_data, dict) else {}
    rows = []
    for source_name, keys in (
        ("涨停池", ("zt_pool",)),
        ("连板", ("lianban_data",)),
        ("热榜", ("hot_rank_top50", "hot_rank_top30", "integrated_hot_list")),
        ("成交额榜", ("turnover_rank",)),
    ):
        for key in keys:
            for row in (_rows_by_code(buy_data.get(key) or {}).get(code) if isinstance(buy_data.get(key), list) else []) or []:
                if isinstance(row, dict):
                    item = dict(row)
                    item["_buyability_source"] = source_name
                    rows.append(item)
    return rows


def _first_buyability_row(rows, source_name):
    for row in rows if isinstance(rows, list) else []:
        if _clean(row.get("_buyability_source")) == source_name:
            return row
    return {}


def _buyability_proxy_review(code, buy_bar, buy_data):
    rows = _buyability_proxy_rows_for(code, buy_data)
    has_bar = isinstance(buy_bar, dict) and bool(buy_bar)
    if not rows and not has_bar:
        return {
            "status": "分时事实待补",
            "reason": "缺少T+1分时事实，也缺少可用涨停池、热榜或日线代理，不能判断9:35前买点路径",
            "minute_source": "待补",
            "early_high_change_pct": None,
            "early_close_change_pct": None,
            "minute_count": 0,
            "proxy_source": "",
        }

    limit_pct = _stock_limit_pct(code)
    open_change = _bar_field_change_pct(buy_bar, "open")
    high_change = _bar_field_change_pct(buy_bar, "high")
    low_change = _bar_field_change_pct(buy_bar, "low")
    close_change = _bar_field_change_pct(buy_bar, "close")
    day_change = _bar_change_pct(buy_bar)
    zt_row = _first_buyability_row(rows, "涨停池") or _first_buyability_row(rows, "连板")
    hot_row = _first_buyability_row(rows, "热榜") or _first_buyability_row(rows, "成交额榜")
    row_change = _row_change_pct(zt_row) if zt_row else _row_change_pct(hot_row)
    effective_change = day_change if day_change is not None else row_change
    first_seal = _minute_time_to_int(
        (zt_row or {}).get("首次封板时间")
        or (zt_row or {}).get("first_limit_time")
        or (zt_row or {}).get("first_seal_time")
    )
    last_seal = _minute_time_to_int(
        (zt_row or {}).get("最后封板时间")
        or (zt_row or {}).get("last_limit_time")
        or (zt_row or {}).get("last_seal_time")
    )
    break_count_raw = (
        (zt_row or {}).get("炸板次数")
        or (zt_row or {}).get("open_times")
        or (zt_row or {}).get("break_count")
    )
    break_count = _safe_int(break_count_raw, 0) if _clean(break_count_raw) else 0
    details = []
    if first_seal is not None:
        details.append(f"首次封板{_time_label_from_minutes(first_seal)}")
    if last_seal is not None:
        details.append(f"最后封板{_time_label_from_minutes(last_seal)}")
    if break_count:
        details.append(f"炸板{break_count}次")
    if effective_change is not None:
        details.append(f"T+1涨幅{_fmt_pct(effective_change)}")
    if high_change is not None and (
        effective_change is None or abs(float(high_change) - float(effective_change)) >= 2.0
    ):
        details.append(f"日内最高涨幅{_fmt_pct(high_change)}")

    early_seal = first_seal is not None and first_seal <= 9 * 60 + 35
    late_reseal = last_seal is not None and last_seal >= 14 * 60
    near_limit_open = open_change is not None and open_change >= limit_pct - 0.7
    near_limit_high = high_change is not None and high_change >= limit_pct - 0.7
    near_limit_close = close_change is not None and close_change >= limit_pct - 0.7
    elevated_high = (
        (high_change is not None and high_change >= limit_pct * 0.75)
        or (effective_change is not None and effective_change >= limit_pct * 0.75)
    )
    opened_after_seal = break_count > 0 or (low_change is not None and low_change < limit_pct * 0.65)

    if zt_row and early_seal and opened_after_seal:
        detail_text = "，".join(details) or "早盘封板后有开板痕迹"
        return {
            "status": "追高风险",
            "reason": f"涨停池代理复核：{detail_text}；可能给过成交窗口，但属于开板后的追高风险，仍需分时成交确认",
            "minute_source": "涨停池/日线代理复核（不替代分时成交）",
            "early_high_change_pct": round(high_change, 2) if high_change is not None else None,
            "early_close_change_pct": round(close_change, 2) if close_change is not None else None,
            "minute_count": 0,
            "proxy_source": "涨停池",
        }
    if zt_row and early_seal and (near_limit_open or near_limit_high or near_limit_close):
        detail_text = "，".join(details) or "09:35前已有涨停池记录"
        return {
            "status": "可能买不到",
            "reason": f"涨停池代理复核：{detail_text}；T+1早盘已接近涨停，纸面收益不能直接算作真实可买到",
            "minute_source": "涨停池/日线代理复核（不替代分时成交）",
            "early_high_change_pct": round(high_change, 2) if high_change is not None else None,
            "early_close_change_pct": round(close_change, 2) if close_change is not None else None,
            "minute_count": 0,
            "proxy_source": "涨停池",
        }
    if zt_row and (near_limit_high or near_limit_close or late_reseal):
        detail_text = "，".join(details) or "T+1进入涨停池"
        return {
            "status": "追高风险",
            "reason": f"涨停池代理复核：{detail_text}；缺少分时成交，不能确认是否有从容买点",
            "minute_source": "涨停池/日线代理复核（不替代分时成交）",
            "early_high_change_pct": round(high_change, 2) if high_change is not None else None,
            "early_close_change_pct": round(close_change, 2) if close_change is not None else None,
            "minute_count": 0,
            "proxy_source": "涨停池",
        }
    if hot_row and elevated_high:
        detail_text = "，".join(details) or "T+1热榜或日线涨幅偏高"
        return {
            "status": "追高风险",
            "reason": f"热榜/日线代理复核：{detail_text}；没有9:35前分时路径，不能确认真实买点质量",
            "minute_source": "热榜/日线代理复核（不替代分时成交）",
            "early_high_change_pct": round(high_change, 2) if high_change is not None else None,
            "early_close_change_pct": round(close_change, 2) if close_change is not None else None,
            "minute_count": 0,
            "proxy_source": "热榜/日线",
        }
    return {
        "status": "待分时确认",
        "reason": "只有涨停池、热榜或日线代理事实，能排除一部分明显追高场景，但不能还原9:35前是否给过从容买点",
        "minute_source": "涨停池/热榜/日线代理复核（不替代分时成交）",
        "early_high_change_pct": round(high_change, 2) if high_change is not None else None,
        "early_close_change_pct": round(close_change, 2) if close_change is not None else None,
        "minute_count": 0,
        "proxy_source": "涨停池/热榜/日线",
    }


def _build_buyability_review(code, buy_bar, minute_bars, *, buy_data=None):
    minute_bars = minute_bars if isinstance(minute_bars, list) else []
    if not minute_bars:
        return _buyability_proxy_review(code, buy_bar, buy_data)
    open_price = _safe_float((buy_bar or {}).get("open"), None)
    pre_close = _safe_float((buy_bar or {}).get("pre_close"), None)
    if not pre_close and open_price:
        change_pct = _bar_change_pct(buy_bar)
        if change_pct is not None:
            close_price = _safe_float((buy_bar or {}).get("close"), None)
            if close_price:
                pre_close = close_price / (1 + change_pct / 100)
    base_price = pre_close or open_price
    early_rows = []
    for row in minute_bars:
        minute_value = _minute_time_to_int(row.get("time"))
        if minute_value is not None and 9 * 60 + 30 <= minute_value <= 9 * 60 + 35:
            early_rows.append(row)
    if not early_rows:
        proxy = _buyability_proxy_review(code, buy_bar, buy_data)
        proxy["reason"] = "分时事实未覆盖09:30-09:35；" + _clean(proxy.get("reason"))
        proxy["minute_count"] = len(minute_bars)
        proxy["minute_source"] = (
            _clean(minute_bars[0].get("source"), "分时事实")
            + "；"
            + _clean(proxy.get("minute_source"), "代理复核")
        )
        return proxy
    early_high = max((_safe_float(row.get("high"), None) or 0) for row in early_rows)
    early_close = _safe_float(early_rows[-1].get("close"), None)
    high_change = _pct_change_from_prices(early_high, base_price)
    close_change = _pct_change_from_prices(early_close, base_price)
    limit_pct = _stock_limit_pct(code)
    if high_change is not None and high_change >= limit_pct * 0.75:
        status = "可能买不到"
        reason = "09:35前已接近涨停，纸面收益不能直接算作真实可执行收益"
    elif close_change is not None and close_change >= limit_pct * 0.65:
        status = "追高风险"
        reason = "09:35前涨幅已经偏高，若无回踩承接，买点质量不足"
    else:
        status = "早盘未明显追高"
        reason = "09:35前没有直接逼近涨停，仍可能存在观察或回踩窗口"
    return {
        "status": status,
        "reason": reason,
        "minute_source": _clean(early_rows[0].get("source"), "分时事实"),
        "early_high_change_pct": round(high_change, 2) if high_change is not None else None,
        "early_close_change_pct": round(close_change, 2) if close_change is not None else None,
        "minute_count": len(minute_bars),
    }


def _build_price_path_review(code, decision_date, buy_date, sell_date, decision_bar, buy_bar, sell_bar):
    decision_bar, buy_bar, sell_bar = _link_price_path_pre_close(decision_bar, buy_bar, sell_bar)
    return {
        "t0": _price_path_day(code, decision_date, decision_bar, "T0决策日"),
        "tplus1": _price_path_day(code, buy_date, buy_bar, "T+1买入日"),
        "tplus2": _price_path_day(code, sell_date, sell_bar, "T+2卖出日"),
    }


def _build_window_matrix(stock, buy_date, sell_date, buy_bar, sell_bar):
    rows = []
    missing_fields = []
    code = _stock_code((stock or {}).get("code"))
    buy_day_change_pct = _bar_change_pct(buy_bar)
    buy_limit_state = _limit_state(code, buy_bar)
    buy_close_near_limit = (
        buy_day_change_pct >= _stock_limit_pct(code) - 0.5
        if buy_day_change_pct is not None
        else False
    )
    for buy_window in BUY_WINDOWS:
        entry_price = _window_price(buy_bar, buy_window["price_field"])
        entry_change_pct = _bar_field_change_pct(buy_bar, buy_window["price_field"])
        if entry_price is None:
            missing_fields.append(f"tplus1_{buy_window['id']}_entry_price")
        for sell_window in SELL_WINDOWS:
            exit_price = _sell_window_price(sell_bar, sell_window["price_field"])
            if exit_price is None:
                missing_fields.append(f"tplus2_{sell_window['id']}_exit_price")
            return_pct = _pct_change_from_prices(exit_price, entry_price)
            rows.append(
                {
                    "buy_window_id": buy_window["id"],
                    "buy_window": buy_window["window"],
                    "buy_proxy_label": buy_window["proxy_label"],
                    "sell_window_id": sell_window["id"],
                    "sell_window": sell_window["window"],
                    "sell_proxy_label": sell_window["proxy_label"],
                    "entry_price": round(entry_price, 4) if entry_price is not None else None,
                    "exit_price": round(exit_price, 4) if exit_price is not None else None,
                    "buy_day_change_pct": round(buy_day_change_pct, 2) if buy_day_change_pct is not None else None,
                    "buy_window_entry_change_pct": (
                        round(entry_change_pct, 2) if entry_change_pct is not None else None
                    ),
                    "buy_limit_state": buy_limit_state,
                    "buy_close_near_limit": buy_close_near_limit,
                    "buy_window_buyability_note": (
                        "T+1买入日已接近涨停，尾盘或高位代理不等于真实可买到"
                        if buy_close_near_limit
                        else "T+1买入日未显示接近涨停；仍需分时成交确认"
                    ),
                    "return_pct": round(return_pct, 2) if return_pct is not None else None,
                    "basis": (
                        "缺少分时成交价，使用日线代理；不能当作精确窗口成交；"
                        f"买入价来源={_clean((buy_bar or {}).get('source'), '待补')}；"
                        f"卖出价来源={_clean((sell_bar or {}).get('source'), '待补')}"
                        if return_pct is not None
                        else "价格事实不足，无法计算"
                    ),
                }
            )
    return rows, sorted(set(missing_fields))


def _entry_price_for_buy_window(review, buy_window_id):
    review = review if isinstance(review, dict) else {}
    buy_window = next((item for item in BUY_WINDOWS if item["id"] == buy_window_id), {})
    for row in review.get("window_matrix") or []:
        if isinstance(row, dict) and row.get("buy_window_id") == buy_window_id:
            return _safe_float(row.get("entry_price"), None)
    price_path = review.get("price_path_review") if isinstance(review.get("price_path_review"), dict) else {}
    tplus1 = price_path.get("tplus1") if isinstance(price_path.get("tplus1"), dict) else {}
    return _window_price(tplus1, buy_window.get("price_field"))


def _small_account_fit(entry_price, *, account_capital, lot_size, buyability_status="", paper_action=""):
    entry_price = _safe_float(entry_price, None)
    account_capital = _safe_float(account_capital, None)
    lot_size = _safe_int(lot_size, 100)
    if entry_price is None or entry_price <= 0 or not account_capital or account_capital <= 0 or lot_size <= 0:
        return {
            "entry_price": round(entry_price, 4) if entry_price is not None else None,
            "one_lot_amount": None,
            "one_lot_account_pct": None,
            "account_fit": "待补",
            "position_50pct_basis": "缺少买入代理价，不能换算50%仓位",
            "small_account_action": "价格事实待补，只观察，不新增参与",
        }
    one_lot_amount = entry_price * lot_size
    one_lot_pct = one_lot_amount / account_capital * 100
    if one_lot_amount > account_capital:
        account_fit = "当前账户买不了一手"
        position_basis = "50%条件执行无法落账；一手金额超过账户本金"
        action = "只观察，不参与；换更小资金载体或继续空仓"
    elif one_lot_pct >= 80:
        account_fit = "一手接近满仓"
        position_basis = "50%不能精确落账；一手就是接近满仓暴露"
        action = "按龙空龙处理：只有唯一核心、固定窗口和贴近认错线同时满足，才考虑一手；否则空仓"
    elif one_lot_pct > 60:
        account_fit = "一手高占用"
        position_basis = "50%不能精确落账；一手已经明显超过半仓"
        action = "一手就是上限；条件不够硬就不做"
    elif one_lot_pct >= 40:
        account_fit = "一手约等50%"
        position_basis = "50%条件执行可以用一手近似，不再拆更小仓位"
        action = "满足唯一核心和窗口条件时，一手近似50%；不满足回到空仓"
    else:
        account_fit = "一手低占用"
        position_basis = "50%需要按一手或多手近似，不能用小数仓位表达"
        action = "可用一手起步，但仍只在固定窗口和买入资格成立时参与"
    if buyability_status in {"追高风险", "可能买不到"}:
        if one_lot_amount > account_capital:
            action = "当前账户买不了一手；只观察，不参与，买点复核不改变账户约束"
        elif one_lot_pct >= 80:
            action = "按龙空龙处理，但买点复核偏紧，只观察承接，不追高；账户可买不等于可以买"
        else:
            action = "买点复核偏紧，只观察承接，不追高；账户可买不等于可以买"
    elif _clean(paper_action) != "paper_participate":
        action = "纸面动作不是参与，账户层只保留观察或空仓"
    return {
        "entry_price": round(entry_price, 4),
        "one_lot_amount": round(one_lot_amount, 2),
        "one_lot_account_pct": round(one_lot_pct, 2),
        "account_fit": account_fit,
        "position_50pct_basis": position_basis,
        "small_account_action": action,
    }


def _build_account_fit_review(review, *, account_capital, lot_size, buyability_status="", paper_action=""):
    windows = []
    for buy_window in BUY_WINDOWS:
        fit = _small_account_fit(
            _entry_price_for_buy_window(review, buy_window["id"]),
            account_capital=account_capital,
            lot_size=lot_size,
            buyability_status=buyability_status,
            paper_action=paper_action,
        )
        fit.update(
            {
                "buy_window_id": buy_window["id"],
                "buy_window": buy_window["window"],
                "buy_proxy_label": buy_window["proxy_label"],
            }
        )
        windows.append(fit)
    return {
        "schema_version": "small_account_fit_review.v1",
        "account_capital": round(_safe_float(account_capital, 0), 2),
        "lot_size": _safe_int(lot_size, 100),
        "windows": windows,
        "basis": "A股最小交易单位按一手换算；策略仓位表达意图，实际仓位按一手金额落账",
    }


def _best_trade_window_combo(evaluation):
    review = evaluation.get("tplus2_exit_review") if isinstance(evaluation, dict) else {}
    review = review if isinstance(review, dict) else {}
    best = {}
    for row in review.get("window_matrix") or []:
        if not isinstance(row, dict) or row.get("return_pct") is None:
            continue
        if not best or float(row.get("return_pct")) > float(best.get("return_pct")):
            best = row
    return best


def _build_tplus2_exit_review(
    entry,
    buy_date,
    buy_data,
    sell_date=None,
    sell_data=None,
    price_refill=None,
    decision_date=None,
    decision_data=None,
    minute_refill=None,
    account_capital=10000,
    lot_size=100,
    paper_action="",
):
    stock = _stock_from_candidate(entry)
    code = stock.get("code")
    if not sell_date:
        decision_bar = _daily_price_bar_for(code, decision_date, decision_data or {}, price_refill=price_refill) if decision_date else {}
        buy_bar = _daily_price_bar_for(code, buy_date, buy_data, price_refill=price_refill)
        decision_bar, buy_bar, _ = _link_price_path_pre_close(decision_bar, buy_bar, {})
        minute_bars = minute_refill(code, buy_date) if callable(minute_refill) else []
        price_path = _build_price_path_review(
            code,
            decision_date or "",
            buy_date,
            sell_date or "",
            decision_bar,
            buy_bar,
            {},
        )
        buyability = _build_buyability_review(code, buy_bar, minute_bars, buy_data=buy_data)
        return {
            "stock": stock,
            "stock_label": _stock_label(stock),
            "buy_date": buy_date,
            "sell_date": sell_date or "",
            "entry_basis": "T+1收盘价代理",
            "data_basis": "缺少T+2交易日，不能计算卖出窗口收益",
            "missing_fields": ["tplus2_sell_date"],
            "price_path_review": price_path,
            "tplus1_actual_review": _build_tplus1_actual_review(code, buy_date, buy_bar),
            "buyability_review": buyability,
            "small_account_fit_review": _build_account_fit_review(
                {"price_path_review": price_path, "window_matrix": []},
                account_capital=account_capital,
                lot_size=lot_size,
                buyability_status=buyability.get("status"),
                paper_action=paper_action,
            ),
            "window_matrix": [],
            "windows": [
                {
                    "window": item["window"],
                    "proxy_label": item["proxy_label"],
                    "return_pct": None,
                    "basis": "待补T+2事实",
                }
                for item in SELL_WINDOWS
            ],
        }
    sell_data = sell_data if isinstance(sell_data, dict) else {}
    decision_data = decision_data if isinstance(decision_data, dict) else {}
    decision_bar = _daily_price_bar_for(code, decision_date, decision_data, price_refill=price_refill) if decision_date else {}
    buy_bar = _daily_price_bar_for(code, buy_date, buy_data, price_refill=price_refill)
    sell_bar = _daily_price_bar_for(code, sell_date, sell_data, price_refill=price_refill)
    decision_bar, buy_bar, sell_bar = _link_price_path_pre_close(decision_bar, buy_bar, sell_bar)
    minute_bars = minute_refill(code, buy_date) if callable(minute_refill) else []
    entry_price = _safe_float(buy_bar.get("close"))
    window_matrix, matrix_missing_fields = _build_window_matrix(stock, buy_date, sell_date, buy_bar, sell_bar)
    price_path = _build_price_path_review(code, decision_date or "", buy_date, sell_date, decision_bar, buy_bar, sell_bar)
    buyability = _build_buyability_review(code, buy_bar, minute_bars, buy_data=buy_data)
    missing_fields = []
    if entry_price is None:
        missing_fields.append("tplus1_entry_close_price")
    if not sell_bar:
        missing_fields.append("tplus2_daily_bar")
    if not decision_bar:
        missing_fields.append("t0_daily_bar")
    if not minute_bars:
        missing_fields.append("tplus1_minute_bars")
    missing_fields.extend(matrix_missing_fields)
    windows = []
    for item in SELL_WINDOWS:
        exit_price = _sell_window_price(sell_bar, item["price_field"])
        if exit_price is None:
            missing_fields.append(f"tplus2_{item['id']}_price")
        return_pct = _pct_change_from_prices(exit_price, entry_price)
        windows.append(
            {
                "id": item["id"],
                "window": item["window"],
                "proxy_label": item["proxy_label"],
                "entry_price": round(entry_price, 4) if entry_price is not None else None,
                "exit_price": round(exit_price, 4) if exit_price is not None else None,
                "return_pct": round(return_pct, 2) if return_pct is not None else None,
                "basis": (
                    "缺少分时成交价，使用日线代理；不能当作精确窗口成交；"
                    f"买入价来源={_clean(buy_bar.get('source'), '待补')}；卖出价来源={_clean(sell_bar.get('source'), '待补')}"
                    if return_pct is not None
                    else "价格事实不足，无法计算"
                ),
            }
        )
    return {
        "stock": stock,
        "stock_label": _stock_label(stock),
        "buy_date": buy_date,
        "sell_date": sell_date,
        "entry_basis": "T+1收盘价代理",
        "entry_source": buy_bar.get("source", ""),
        "sell_source": sell_bar.get("source", ""),
        "data_basis": "未发现股票级分时窗口价格，本表用日线开盘/日内中枢/收盘做代理",
        "missing_fields": sorted(set(missing_fields)),
        "price_path_review": price_path,
        "buyability_review": buyability,
        "small_account_fit_review": _build_account_fit_review(
            {"price_path_review": price_path, "window_matrix": window_matrix},
            account_capital=account_capital,
            lot_size=lot_size,
            buyability_status=buyability.get("status"),
            paper_action=paper_action,
        ),
        "window_matrix": window_matrix,
        "windows": windows,
    }


def _projection_label_match(projected, actual, *, kind):
    projected = _clean(projected)
    actual = _clean(actual)
    if not projected or projected == "待判读" or actual in {"", "待判读", "待补事实"}:
        return "待校准"
    if kind == "sector":
        if projected == "延续" and actual in {"扩散", "延续"}:
            return "大体一致"
        if projected == "分歧" and actual == "分歧":
            return "大体一致"
        if projected == "退潮" and actual == "退潮":
            return "大体一致"
    elif projected == actual:
        return "大体一致"
    return "偏离"


def _project_market_emotion_from_t0(data, paper_strategy):
    current = _market_emotion_state(data)
    current_label = _clean(current.get("label"), "待判读")
    action = _clean(paper_strategy.get("action")) if isinstance(paper_strategy, dict) else ""
    primary = paper_strategy.get("primary_candidate") if isinstance(paper_strategy, dict) else {}
    family_count = len(primary.get("evidence_families") or []) if isinstance(primary, dict) else 0
    selected_count = len(paper_strategy.get("selected_sectors") or []) if isinstance(paper_strategy, dict) else 0

    if current_label == "高潮":
        tplus1 = "高潮"
        tplus2 = "震荡"
        reason = "T0已偏热，T+1允许惯性，T+2先按分歧回落后的震荡预案处理"
    elif current_label == "冰点":
        if action == "paper_participate" and family_count >= 2:
            tplus1 = "震荡"
            tplus2 = "震荡"
            reason = "T0偏冷但板块资金载体成立，先按修复到震荡预案处理"
        else:
            tplus1 = "冰点"
            tplus2 = "冰点"
            reason = "T0偏冷且缺少足够资金载体，T+2仍按偏冷预案处理"
    elif current_label == "震荡":
        tplus1 = "震荡"
        tplus2 = "震荡"
        reason = "T0处在震荡，未把局部热度直接升级成高潮预判"
    elif selected_count >= 3 and action == "paper_participate" and family_count >= 2:
        tplus1 = "震荡"
        tplus2 = "震荡"
        reason = "缺少完整市场情绪文本，但热板和资金载体同时存在，只按震荡预案处理"
    else:
        tplus1 = "待判读"
        tplus2 = "待判读"
        reason = "T0市场情绪事实不足，不做确定推演"
    return {
        "current": current,
        "tplus1": {
            "label": tplus1,
            "basis": reason,
        },
        "tplus2": {
            "label": tplus2,
            "basis": reason,
        },
        "basis": "只使用T0市场情绪、板块数量和资金载体强弱做交易预案，不把它当成确定预言",
    }


def _project_sector_emotion_from_t0(data, sector, paper_strategy):
    current = _sector_emotion_state(data, sector)
    current_label = _clean(current.get("label"), "待判读")
    action = _clean(paper_strategy.get("action")) if isinstance(paper_strategy, dict) else ""
    primary = paper_strategy.get("primary_candidate") if isinstance(paper_strategy, dict) else {}
    family_count = len(primary.get("evidence_families") or []) if isinstance(primary, dict) else 0

    if not _clean(sector):
        tplus1 = "待判读"
        tplus2 = "待判读"
        reason = "T0没有主线板块，不能推演板块情绪"
    elif current_label == "扩散":
        tplus1 = "延续"
        tplus2 = "分歧"
        reason = "T0已扩散，T+1看延续确认，T+2先按分歧检验处理"
    elif current_label == "延续":
        tplus1 = "延续"
        tplus2 = "分歧"
        reason = "T0板块已延续，T+2不追认高潮，先看分歧承接"
    elif current_label == "分歧":
        tplus1 = "分歧"
        if action == "paper_participate" and family_count >= 2:
            tplus2 = "分歧"
            reason = "T0板块分歧但资金载体尚在，T+2继续看分歧承接"
        else:
            tplus2 = "退潮"
            reason = "T0板块分歧且资金载体不足，T+2先按退潮预案处理"
    elif action == "paper_participate" and family_count >= 2:
        tplus1 = "延续"
        tplus2 = "分歧"
        reason = "T0板块文本不足但主样本资金载体成立，按延续后分歧检验处理"
    else:
        tplus1 = "待判读"
        tplus2 = "待判读"
        reason = "T0板块热度、资金和宽度证据不足，不做确定推演"
    return {
        "sector": _clean(sector),
        "current": current,
        "tplus1": {
            "label": tplus1,
            "basis": reason,
        },
        "tplus2": {
            "label": tplus2,
            "basis": reason,
        },
        "basis": "只使用T0板块热度、资金、宽度和资金载体角色做预案；T+2事实只用于事后校准",
    }


def _build_t0_emotion_projection(decision_data, paper_strategy):
    primary_sector = _clean((paper_strategy.get("primary_candidate") or {}).get("sector")) if isinstance(paper_strategy, dict) else ""
    market = _project_market_emotion_from_t0(decision_data, paper_strategy)
    sector = _project_sector_emotion_from_t0(decision_data, primary_sector, paper_strategy)
    return {
        "schema_version": "t0_tplus2_emotion_projection.v1",
        "primary_sector": primary_sector,
        "market": market,
        "sector": sector,
        "summary": (
            f"T+2市场预案：{_clean((market.get('tplus2') or {}).get('label'), '待判读')}；"
            f"T+2板块预案：{_clean((sector.get('tplus2') or {}).get('label'), '待判读')}"
        ),
        "basis": "T0复盘时先做T+2交易环境预案，T+2到来后只做校准，不回写T0选择",
    }


def _market_emotion_state(data):
    data = data if isinstance(data, dict) else {}
    text_values = []
    for key in ("market_phase_context", "market_analysis", "market_emotion", "market_overview"):
        value = data.get(key)
        if isinstance(value, dict):
            text_values.extend(_clean(item) for item in value.values() if isinstance(item, (str, int, float)))
        else:
            text_values.append(_clean(value))
    summary = data.get("mainline_turnover_summary") if isinstance(data.get("mainline_turnover_summary"), dict) else {}
    text_values.append(_clean(summary.get("market_regime")))
    joined = "；".join(item for item in text_values if item)
    if "冰点" in joined or "退潮" in joined or "弱" in joined:
        label = "冰点"
    elif "高潮" in joined or "偏热" in joined or "强攻" in joined:
        label = "高潮"
    elif "震荡" in joined or "分歧" in joined or "修复" in joined:
        label = "震荡"
    elif data:
        label = "待判读"
    else:
        label = "待补事实"
    if not joined:
        hot_plates = data.get("hot_plates") if isinstance(data.get("hot_plates"), list) else []
        fund_inflow = (data.get("sector_fund_flow") or {}).get("inflow") if isinstance(data.get("sector_fund_flow"), dict) else []
        if len(hot_plates) >= 3 or len(fund_inflow or []) >= 3:
            label = "震荡"
            joined = "有热板/资金表事实，但缺少整体市场情绪文本"
    return {
        "label": label,
        "basis": joined or "缺少可读市场情绪字段",
    }


def _sector_emotion_state(data, sector):
    data = data if isinstance(data, dict) else {}
    aliases = _sector_aliases(sector)
    hot_plates = _matching_named_rows(data.get("hot_plates") or [], aliases, key="name")
    fund_rows = _fund_flow_rows(data, aliases)
    same_sector_limit_rows = _matching_sector_limit_rows(data.get("zt_pool_by_sector"), aliases)
    evidence = []
    if hot_plates:
        evidence.append("热板出现")
    if fund_rows:
        positive_fund = [
            row for row in fund_rows
            if (_safe_float(row.get("net_inflow_yi")) or 0) > 0 or (_safe_float(row.get("change_pct")) or 0) > 0
        ]
        evidence.append("资金表同向" if positive_fund else "资金表分歧")
    if same_sector_limit_rows:
        evidence.append(f"同板块涨停{len(same_sector_limit_rows)}只")
    if hot_plates and fund_rows and same_sector_limit_rows:
        label = "扩散"
    elif hot_plates and (fund_rows or same_sector_limit_rows):
        label = "延续"
    elif fund_rows or same_sector_limit_rows:
        label = "分歧"
    elif data:
        label = "待判读"
    else:
        label = "待补事实"
    return {
        "sector": _clean(sector),
        "label": label,
        "basis": "、".join(evidence) or "缺少该板块的热度、资金和宽度证据",
    }


def _cached_loader(loader):
    cache = {}

    def load(date_text):
        date_text = _date_text(date_text)
        if date_text not in cache:
            cache[date_text] = loader(date_text)
        return cache[date_text]

    return load


def _forward_replay_data_is_thin(data):
    if not isinstance(data, dict) or not data:
        return True
    report_spine_keys = (
        "selection_workflow",
        "final_target_resolution",
        "two_layer_decision_payload",
        "sniper_target_derivation",
        "elimination_tournament_payload",
    )
    evidence_keys = (
        "hot_plates",
        "zt_pool",
        "zt_pool_by_sector",
        "sector_fund_flow",
        "integrated_hot_list",
        "turnover_rank",
        "market_stats",
        "new_high_feedback",
        "indices",
    )
    has_spine = any(data.get(key) for key in report_spine_keys)
    replay_evidence_count = sum(1 for key in evidence_keys if data.get(key))
    has_replay_evidence = replay_evidence_count >= 2 or any(
        data.get(key)
        for key in (
            "sector_fund_flow",
            "integrated_hot_list",
            "turnover_rank",
            "zt_pool_by_sector",
        )
    )
    return not (has_spine and has_replay_evidence)


def load_daily_report_data_for_forward_replay(target_date):
    postgres_data = None
    postgres_exc = None
    try:
        postgres_data = load_daily_report_data_from_postgres(target_date)
        if not _forward_replay_data_is_thin(postgres_data):
            data = dict(postgres_data)
            data["forward_replay_source"] = data.get("forward_replay_source") or "postgres"
            return data
    except Exception as exc:
        postgres_exc = exc

    snapshot_data, _ = load_data_snapshot(str(target_date or ""))
    if isinstance(snapshot_data, dict) and snapshot_data:
        data = dict(snapshot_data)
        data["forward_replay_source"] = "snapshot"
        if postgres_exc:
            data["forward_replay_postgres_error"] = f"{type(postgres_exc).__name__}: {postgres_exc}"
        elif isinstance(postgres_data, dict):
            data["forward_replay_postgres_note"] = "PostgreSQL事实偏薄，改用冻结快照"
        return data
    if postgres_exc:
        raise postgres_exc
    return postgres_data or {}


def discover_forward_replay_pairs(
    start_date,
    end_date,
    *,
    loader=load_daily_report_data_for_forward_replay,
    trade_calendar_refill=None,
):
    start = _date(start_date)
    end = _date(end_date)
    if end < start:
        raise ValueError("end_date must be greater than or equal to start_date")
    open_date_set = None
    skipped_dates = []
    if trade_calendar_refill and hasattr(trade_calendar_refill, "open_dates"):
        open_dates = trade_calendar_refill.open_dates(start.isoformat(), end.isoformat())
        if open_dates:
            open_date_set = set(open_dates)
    available_dates = []
    missing_dates = []
    current = start
    while current <= end:
        current_text = current.isoformat()
        if open_date_set is not None and current_text not in open_date_set:
            skipped_dates.append({"date": current_text, "reason": "非交易日，不进入T0/T+1/T+2回测链"})
            current += timedelta(days=1)
            continue
        try:
            data = loader(current_text)
        except Exception as exc:
            missing_dates.append(
                {
                    "date": current_text,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
        else:
            if isinstance(data, dict) and data:
                available_dates.append(current_text)
            else:
                missing_dates.append({"date": current_text, "reason": "日报事实为空"})
        current += timedelta(days=1)
    pairs = []
    for index, decision_date in enumerate(available_dates[:-1]):
        buy_date = available_dates[index + 1]
        if index + 2 < len(available_dates):
            sell_date = available_dates[index + 2]
        elif trade_calendar_refill and hasattr(trade_calendar_refill, "next_after"):
            sell_date = trade_calendar_refill.next_after(buy_date) or None
        else:
            sell_date = None
        pairs.append((decision_date, buy_date, sell_date))
    return pairs, {
        "requested_start_date": start.isoformat(),
        "requested_end_date": end.isoformat(),
        "available_dates": available_dates,
        "missing_dates": missing_dates,
        "skipped_dates": skipped_dates,
        "pair_count": len(pairs),
        "trade_calendar_refill_summary": _trade_calendar_refill_summary(trade_calendar_refill),
    }


def _target_evidence_for(entry, target_data):
    stock = _stock_from_candidate(entry)
    code = stock.get("code")
    hot_by_code = _rows_by_code(target_data.get("hot_rank_top50") or target_data.get("hot_rank_top30") or [])
    zt_by_code = _rows_by_code(target_data.get("zt_pool") or [])
    lianban_by_code = _rows_by_code(target_data.get("lianban_data") or [])
    turnover_by_code = _rows_by_code(target_data.get("turnover_rank") or [])
    workflow_by_code = _workflow_candidates_by_code(target_data)

    hot_row = (hot_by_code.get(code) or [{}])[0]
    concepts = hot_row.get("concepts") if isinstance(hot_row, dict) else []
    names = _sector_aliases(stock.get("sector"), hot_row.get("sector") if isinstance(hot_row, dict) else "", concepts)
    hot_plates = _matching_named_rows(target_data.get("hot_plates") or [], names, key="name")
    fund_rows = _fund_flow_rows(target_data, names)
    same_sector_limit_rows = _matching_sector_limit_rows(target_data.get("zt_pool_by_sector"), names)
    zt_rows = zt_by_code.get(code) or []
    lianban_rows = lianban_by_code.get(code) or []
    workflow_hits = workflow_by_code.get(code) or []

    facts = []
    if hot_row:
        rank = _clean(hot_row.get("rank"))
        change = _fmt_pct(hot_row.get("change_pct"))
        status = _clean(hot_row.get("zt_status"))
        facts.append("T+1买入日热榜第" + rank + (f"，涨跌幅{change}" if change else "") + (f"，{status}" if status else ""))
    if zt_rows:
        row = zt_rows[0]
        facts.append(
            "T+1买入日涨停池："
            + _clean(row.get("涨停统计") or row.get("zt_type"), "涨停")
            + (f"，炸板{_clean(row.get('炸板次数'))}次" if _clean(row.get("炸板次数")) else "")
        )
    if lianban_rows:
        row = lianban_rows[0]
        facts.append(f"T+1买入日连板/高度={_clean(row.get('lianban_days') or row.get('xuangubao_limit_up_days'))}")
    if hot_plates:
        facts.append("T+1买入日热度板块：" + "、".join(_clean(row.get("name")) for row in hot_plates[:3]))
    if fund_rows:
        brief = []
        for row in fund_rows[:3]:
            change = _fmt_pct(row.get("change_pct"))
            net = _clean(row.get("net_inflow_yi"))
            brief.append(f"{_clean(row.get('name'))}({change}, 净额{net}亿)")
        facts.append("T+1买入日资金表：" + "、".join(brief))
    if same_sector_limit_rows:
        facts.append(
            "T+1买入日同板块涨停："
            + "、".join(
                _stock_label({"name": row.get("name") or row.get("名称"), "code": row.get("code") or row.get("代码")})
                for row in same_sector_limit_rows[:5]
                if isinstance(row, dict)
            )
        )
    if workflow_hits:
        hit = workflow_hits[0]
        facts.append(
            "T+1买入日自有流程回看仍收录（仅作结果证据）："
            + _clean(hit.get("status"), "过程候选")
            + "；"
            + _clean(hit.get("entry_basis") or hit.get("eliminated_reason") or hit.get("current_reason"))
        )

    target_change_pct = None
    target_change_source = ""
    for source_name, rows in (
        ("热榜", [hot_row]),
        ("涨停池", zt_rows),
        ("连板", lianban_rows),
        ("成交额榜", turnover_by_code.get(code) or []),
    ):
        for row in rows if isinstance(rows, list) else []:
            change_value = _row_change_pct(row)
            if change_value is not None:
                target_change_pct = change_value
                target_change_source = source_name
                break
        if target_change_pct is not None:
            break
    if target_change_pct is not None:
        facts.append(
            "T+1买入日涨幅"
            + _fmt_pct(target_change_pct)
            + "；仅作为T+1买入日强弱复核，不当作可卖出收益"
        )

    change_value = None
    try:
        change_value = float(hot_row.get("change_pct")) if hot_row else None
    except (TypeError, ValueError):
        change_value = None
    status_text = _clean(hot_row.get("zt_status")) if hot_row else ""
    has_limit_up = bool(zt_rows or lianban_rows or status_text == "涨停")
    sector_active = bool(hot_plates or fund_rows or same_sector_limit_rows)
    stock_active = bool(hot_row or has_limit_up or workflow_hits)

    if status_text == "跌停" or (change_value is not None and change_value <= -9):
        outcome = "后验失效：高位风险兑现"
    elif has_limit_up and sector_active and not workflow_hits:
        outcome = "后验走强但流程未接住：回看板块锚/龙头识别"
    elif has_limit_up and workflow_hits:
        outcome = "价格延续命中，但仍需区分旧信号与板块锚"
    elif hot_row and sector_active:
        outcome = "板块方向命中，个股未到执行级别"
    elif stock_active:
        outcome = "仅作热度观察"
    else:
        outcome = "未命中"

    return {
        "stock": stock,
        "stock_label": _stock_label(stock),
        "decision_status": _clean(entry.get("status")),
        "decision_reason": _clean(entry.get("reason") or entry.get("eliminated_reason") or entry.get("entry_basis")),
        "candidate_origin": _clean(entry.get("candidate_origin")),
        "source_pools": entry.get("source_pools") if isinstance(entry.get("source_pools"), list) else [],
        "target_facts": facts or ["T+1买入日未找到热榜、涨停池、连板、流程延续等证据"],
        "target_outcome": outcome,
        "target_change_pct": target_change_pct,
        "target_change_source": target_change_source,
    }


def _layer_rows(preflight_payload):
    rows = []
    previous_survivor_count = None
    for index, layer in enumerate(preflight_payload.get("layers", []), start=1):
        if not isinstance(layer, dict):
            continue
        layer_id = _clean(layer.get("id"))
        input_count = int(layer.get("input_count") or 0)
        eliminated_count = int(layer.get("eliminated_count") or 0)
        survivor_count = int(layer.get("survivor_count") or 0)
        if layer_id == "final_action" and not (preflight_payload.get("final_action") or {}).get("target"):
            input_count = previous_survivor_count if previous_survivor_count is not None else input_count
            eliminated_count = 0
            survivor_count = 0
        rows.append(
            {
                "round": index,
                "id": layer_id,
                "title": _clean(layer.get("title")),
                "input_count": input_count,
                "eliminated_count": eliminated_count,
                "survivor_count": survivor_count,
                "input_labels": [_clean(item.get("stock_label")) for item in layer.get("entries", []) if isinstance(item, dict)],
                "eliminated": [
                    {
                        "stock_label": _clean(item.get("stock_label")),
                        "reason": _clean(item.get("reason")),
                    }
                    for item in layer.get("eliminated", [])
                    if isinstance(item, dict)
                ],
                "survivors": [
                    {
                        "stock_label": _clean(item.get("stock_label")),
                        "reason": _clean(item.get("reason")),
                    }
                    for item in layer.get("survivors", [])
                    if isinstance(item, dict)
                ],
            }
        )
        previous_survivor_count = survivor_count
    return rows


def _final_position_pct(final_action):
    final_action = final_action if isinstance(final_action, dict) else {}
    for key in ("position_pct", "target_position_pct"):
        if key in final_action:
            return _safe_int(final_action.get(key), 0)
    label = _clean(final_action.get("label") or final_action.get("action_text"))
    if "100" in label:
        return 100
    if "50" in label:
        return 50
    return 0


def _last_survivor_layer(layer_rows):
    last = {}
    for layer in layer_rows if isinstance(layer_rows, list) else []:
        if _safe_int(layer.get("survivor_count")) > 0:
            last = layer
    return last


def _first_zero_layer(layer_rows):
    for layer in layer_rows if isinstance(layer_rows, list) else []:
        if _clean(layer.get("id")) == "final_action":
            continue
        if _safe_int(layer.get("input_count")) > 0 and _safe_int(layer.get("survivor_count")) <= 0:
            return layer
    return {}


def _main_elimination_reason(layer):
    eliminated = layer.get("eliminated") if isinstance(layer, dict) else []
    reasons = [
        _clean(item.get("reason"))
        for item in eliminated if isinstance(item, dict) and _clean(item.get("reason"))
    ]
    if reasons:
        return "；".join(reasons[:3])
    return _clean(layer.get("note") if isinstance(layer, dict) else "")


def _diagnosis_category(pair):
    layers = pair.get("layers") if isinstance(pair, dict) else []
    candidate_count = _safe_int(pair.get("candidate_count"))
    final_action = pair.get("final_action") if isinstance(pair, dict) else {}
    final_pct = _final_position_pct(final_action)
    first_zero = _first_zero_layer(layers)
    last_survivor = _last_survivor_layer(layers)
    final_label = _clean(final_action.get("label") if isinstance(final_action, dict) else "", "0%不参与")
    target = final_action.get("target") if isinstance(final_action, dict) and isinstance(final_action.get("target"), dict) else {}

    if final_pct > 0 or target:
        return {
            "category": "已给参与动作",
            "reason": final_label,
            "first_zero_layer": "",
            "last_survivor_layer": _clean(last_survivor.get("title")),
            "last_survivor_count": _safe_int(last_survivor.get("survivor_count")),
        }
    if candidate_count <= 0:
        return {
            "category": "候选入口为空",
            "reason": "T0没有可复核候选，或历史事实未覆盖候选源",
            "first_zero_layer": _clean((layers[0] if layers else {}).get("title")),
            "last_survivor_layer": "",
            "last_survivor_count": 0,
        }
    if first_zero:
        layer_title = _clean(first_zero.get("title"))
        if "市场" in layer_title or ("板块" in layer_title and "载体" not in layer_title):
            category = "板块扩散未通过"
        elif "载体" in layer_title or "角色" in layer_title or "量化" in layer_title:
            category = "资金载体未通过"
        elif "价格" in layer_title:
            category = "价格行为未通过"
        elif "周期" in layer_title or "账户" in layer_title or "盈亏比" in layer_title or "时间" in layer_title:
            category = "周期/账户条件未通过"
        else:
            category = "条件链中途归零"
        return {
            "category": category,
            "reason": _main_elimination_reason(first_zero) or f"{layer_title} 后没有剩余候选",
            "first_zero_layer": layer_title,
            "last_survivor_layer": _clean(last_survivor.get("title")),
            "last_survivor_count": _safe_int(last_survivor.get("survivor_count")),
        }
    if last_survivor and _safe_int(last_survivor.get("survivor_count")) > 0:
        return {
            "category": "最终动作转换异常",
            "reason": "前面仍有候选存活，但最终动作仍为 0%，需要检查最终不参与理由是否具体",
            "first_zero_layer": "",
            "last_survivor_layer": _clean(last_survivor.get("title")),
            "last_survivor_count": _safe_int(last_survivor.get("survivor_count")),
        }
    return {
        "category": "0%原因待补事实",
        "reason": "层级事实不足，无法归因到具体条件",
        "first_zero_layer": "",
        "last_survivor_layer": _clean(last_survivor.get("title")),
        "last_survivor_count": _safe_int(last_survivor.get("survivor_count")),
    }


def _evaluate_mismatch(pair):
    evaluations = pair.get("evaluations") if isinstance(pair, dict) else []
    final_pct = _final_position_pct(pair.get("final_action") if isinstance(pair, dict) else {})
    if final_pct > 0:
        return {}
    strong_outcomes = []
    for item in evaluations if isinstance(evaluations, list) else []:
        outcome = _clean(item.get("target_outcome")) if isinstance(item, dict) else ""
        if any(key in outcome for key in ("流程未接住", "价格延续命中", "板块方向命中", "走强")):
            strong_outcomes.append(
                {
                    "stock_label": _clean(item.get("stock_label")),
                    "target_outcome": outcome,
                    "target_facts": item.get("target_facts") if isinstance(item.get("target_facts"), list) else [],
                }
            )
    if not strong_outcomes:
        return {}
    return {
        "type": "T0不参与但T+1证据走强",
        "items": strong_outcomes,
    }


def _best_exit_window(evaluation):
    review = evaluation.get("tplus2_exit_review") if isinstance(evaluation, dict) else {}
    review = review if isinstance(review, dict) else {}
    best = {}
    for window in review.get("windows") or []:
        if not isinstance(window, dict) or window.get("return_pct") is None:
            continue
        if not best or float(window.get("return_pct")) > float(best.get("return_pct")):
            best = window
    return best


def _build_exit_window_summary(pair_payloads):
    rows = []
    for window in SELL_WINDOWS:
        returns = []
        positive_count = 0
        best_sample = {}
        worst_sample = {}
        for pair in pair_payloads:
            strategy = pair.get("paper_strategy") if isinstance(pair.get("paper_strategy"), dict) else {}
            target_summary = strategy.get("target_summary") if isinstance(strategy.get("target_summary"), dict) else {}
            primary_stock = _clean(target_summary.get("primary_stock"))
            evaluations = strategy.get("target_evaluations") if isinstance(strategy.get("target_evaluations"), list) else []
            primary = next((item for item in evaluations if _clean(item.get("stock_label")) == primary_stock), None)
            if not primary:
                continue
            review = primary.get("tplus2_exit_review") if isinstance(primary.get("tplus2_exit_review"), dict) else {}
            result = next(
                (item for item in review.get("windows") or [] if isinstance(item, dict) and item.get("id") == window["id"]),
                {},
            )
            return_pct = _safe_float(result.get("return_pct"), None)
            if return_pct is None:
                continue
            sample = {
                "decision_date": pair.get("effective_decision_date"),
                "buy_date": pair.get("buy_date"),
                "sell_date": pair.get("sell_date"),
                "stock": primary_stock,
                "return_pct": round(return_pct, 2),
            }
            returns.append(return_pct)
            if return_pct > 0:
                positive_count += 1
            if not best_sample or return_pct > best_sample["return_pct"]:
                best_sample = sample
            if not worst_sample or return_pct < worst_sample["return_pct"]:
                worst_sample = sample
        avg_return = round(sum(returns) / len(returns), 2) if returns else None
        rows.append(
            {
                "id": window["id"],
                "window": window["window"],
                "proxy_label": window["proxy_label"],
                "sample_count": len(returns),
                "average_return_pct": avg_return,
                "positive_count": positive_count,
                "best_sample": best_sample,
                "worst_sample": worst_sample,
                "basis": "股票级分时缺失，使用日线代理统计" if returns else "样本价格事实不足",
            }
        )
    valid_rows = [row for row in rows if row["average_return_pct"] is not None]
    best_row = max(valid_rows, key=lambda item: item["average_return_pct"]) if valid_rows else {}
    if best_row and best_row.get("sample_count", 0) >= 3:
        recommendation = f"当前样本里 {best_row['window']} 的日线代理表现较高，但仍需补股票分时后再确认"
    elif best_row:
        recommendation = f"当前样本太少，只能暂看 {best_row['window']}，不能形成稳定卖出窗口结论"
    else:
        recommendation = "缺少可计算样本，不能建议卖出窗口"
    return {
        "windows": rows,
        "recommended_window": best_row.get("window", ""),
        "recommendation": recommendation,
        "data_basis": "T+1买入按收盘价代理；T+2卖出按开盘、日内中枢、收盘代理；没有股票分钟成交价时不做精确窗口收益",
    }


def _build_equity_curve(samples):
    ordered = sorted(
        (item for item in samples if isinstance(item, dict) and item.get("return_pct") is not None),
        key=lambda item: _clean(item.get("decision_date")),
    )
    equity = 1.0
    peak = 1.0
    max_drawdown_pct = 0.0
    max_drawdown_sample = {}
    curve_points = []
    for sample in ordered:
        return_pct = _safe_float(sample.get("return_pct"), None)
        if return_pct is None:
            continue
        equity *= 1 + return_pct / 100
        if equity > peak:
            peak = equity
        drawdown_pct = ((equity / peak) - 1) * 100 if peak else 0.0
        point = {
            "decision_date": sample.get("decision_date"),
            "buy_date": sample.get("buy_date"),
            "sell_date": sample.get("sell_date"),
            "stock": sample.get("stock"),
            "buy_window": sample.get("buy_window"),
            "sell_window": sample.get("sell_window"),
            "return_pct": round(return_pct, 2),
            "net_value": round(equity, 4),
            "cumulative_return_pct": round((equity - 1) * 100, 2),
            "drawdown_pct": round(drawdown_pct, 2),
        }
        curve_points.append(point)
        if drawdown_pct < max_drawdown_pct:
            max_drawdown_pct = drawdown_pct
            max_drawdown_sample = point
    return {
        "sample_count": len(curve_points),
        "final_net_value": round(equity, 4) if curve_points else None,
        "cumulative_return_pct": round((equity - 1) * 100, 2) if curve_points else None,
        "max_drawdown_pct": round(max_drawdown_pct, 2) if curve_points else None,
        "max_drawdown_sample": max_drawdown_sample,
        "curve_points": curve_points,
        "basis": "按T0日期顺序把每笔日线代理收益复利累乘；未计手续费、滑点和空仓收益，不等于真实成交曲线",
    }


def _build_tplus1_actual_review(code, buy_date, buy_bar):
    buy_bar = buy_bar if isinstance(buy_bar, dict) else {}
    open_price = _window_price(buy_bar, "open")
    high_price = _window_price(buy_bar, "high")
    low_price = _window_price(buy_bar, "low")
    close_price = _window_price(buy_bar, "close")
    open_to_close = _pct_change_from_prices(close_price, open_price)
    open_to_high = _pct_change_from_prices(high_price, open_price)
    open_to_low = _pct_change_from_prices(low_price, open_price)
    return {
        "schema_version": "tplus1_actual_review.v1",
        "trade_date": buy_date,
        "open": round(open_price, 4) if open_price is not None else None,
        "high": round(high_price, 4) if high_price is not None else None,
        "low": round(low_price, 4) if low_price is not None else None,
        "close": round(close_price, 4) if close_price is not None else None,
        "day_change_pct": round(_bar_change_pct(buy_bar), 2) if _bar_change_pct(buy_bar) is not None else None,
        "open_to_close_return_pct": round(open_to_close, 2) if open_to_close is not None else None,
        "open_to_high_return_pct": round(open_to_high, 2) if open_to_high is not None else None,
        "open_to_low_return_pct": round(open_to_low, 2) if open_to_low is not None else None,
        "source": _clean(buy_bar.get("source"), "待补"),
        "basis": (
            "T+1买入日已发生日线事实；09:30-09:35按开盘代理，14:30-14:55按收盘代理；"
            "这里只说明买入日浮动表现，不替代完整T+2卖出窗口收益。"
        ),
    }


def _index_point_from_text(value):
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*/", _clean(value))
    if not match:
        return None
    return _safe_float(match.group(1), None)


def _annualized_reference_text(item):
    period_count = _safe_int((item or {}).get("period_count"), 0)
    value = (item or {}).get("annualized_return_pct")
    if value is None:
        return "待补"
    if period_count < 21:
        return "短样本不展示"
    return _fmt_signed_pct(value)


def _benchmark_spec_by_label():
    return {item["label"]: item for item in INDEX_BENCHMARK_SPECS}


def _build_index_benchmark_summary(pair_payloads):
    ordered_all = sorted(
        (pair for pair in pair_payloads if isinstance(pair, dict)),
        key=lambda item: _clean(item.get("effective_decision_date")),
    )
    expected_start_date = _clean(ordered_all[0].get("effective_decision_date")) if ordered_all else ""
    expected_end_date = _clean(ordered_all[-1].get("effective_decision_date")) if ordered_all else ""
    ordered = sorted(
        (
            pair for pair in pair_payloads
            if isinstance(pair, dict) and isinstance(pair.get("t0_market_context"), dict)
        ),
        key=lambda item: _clean(item.get("effective_decision_date")),
    )
    benchmarks = []
    for spec in INDEX_BENCHMARK_SPECS:
        label = spec["label"]
        key = spec["context_key"]
        start_pair = next(
            (pair for pair in ordered if _index_point_from_text(pair.get("t0_market_context", {}).get(key)) is not None),
            {},
        )
        end_pair = next(
            (
                pair for pair in reversed(ordered)
                if _index_point_from_text(pair.get("t0_market_context", {}).get(key)) is not None
            ),
            {},
        )
        start_point = _index_point_from_text(start_pair.get("t0_market_context", {}).get(key))
        end_point = _index_point_from_text(end_pair.get("t0_market_context", {}).get(key))
        start_date = _clean(start_pair.get("effective_decision_date"))
        end_date = _clean(end_pair.get("effective_decision_date"))
        coverage_complete = bool(
            expected_start_date
            and expected_end_date
            and start_date == expected_start_date
            and end_date == expected_end_date
            and start_point is not None
            and end_point is not None
        )
        cumulative_return_pct = None
        if coverage_complete and start_point and end_point:
            cumulative_return_pct = (end_point / start_point - 1) * 100
        benchmarks.append(
            {
                "id": key,
                "label": label,
                "start_date": start_date,
                "end_date": end_date,
                "expected_start_date": expected_start_date,
                "expected_end_date": expected_end_date,
                "coverage_complete": coverage_complete,
                "coverage_note": (
                    "覆盖样本首尾"
                    if coverage_complete
                    else "未覆盖样本首尾，仅展示可用点位，不计算跑赢"
                ),
                "start_point": round(start_point, 2) if start_point is not None else None,
                "end_point": round(end_point, 2) if end_point is not None else None,
                "cumulative_return_pct": (
                    round(cumulative_return_pct, 2) if cumulative_return_pct is not None else None
                ),
            }
        )
    return {
        "rows": benchmarks,
        "basis": "指数收益按样本T0指数点位首尾计算，和策略窗口使用同一批T0样本；只作市场背景对照",
    }


def _annualized_pct_from_net_value(net_value, periods, annual_periods):
    net_value = _safe_float(net_value, None)
    periods = _safe_float(periods, None)
    if net_value is None or net_value <= 0 or not periods or periods <= 0:
        return None
    return (net_value ** (annual_periods / periods) - 1) * 100


def _open_buy_near_limit(sample):
    entry_change = _safe_float((sample or {}).get("buy_window_entry_change_pct"), None)
    if entry_change is None:
        return False
    code = _stock_code((sample or {}).get("stock"))
    return entry_change >= _stock_limit_pct(code) - 0.5


def _samples_for_combo(pair_payloads, buy_window_id, sell_window_id):
    samples = []
    for pair in pair_payloads:
        strategy = pair.get("paper_strategy") if isinstance(pair.get("paper_strategy"), dict) else {}
        target_summary = strategy.get("target_summary") if isinstance(strategy.get("target_summary"), dict) else {}
        primary_stock = _clean(target_summary.get("primary_stock"))
        evaluations = strategy.get("target_evaluations") if isinstance(strategy.get("target_evaluations"), list) else []
        primary = next((item for item in evaluations if _clean(item.get("stock_label")) == primary_stock), None)
        if not primary:
            continue
        review = primary.get("tplus2_exit_review") if isinstance(primary.get("tplus2_exit_review"), dict) else {}
        result = next(
            (
                item for item in review.get("window_matrix") or []
                if isinstance(item, dict)
                and item.get("buy_window_id") == buy_window_id
                and item.get("sell_window_id") == sell_window_id
            ),
            {},
        )
        return_pct = _safe_float(result.get("return_pct"), None)
        if return_pct is None:
            continue
        samples.append(
            {
                "decision_date": pair.get("effective_decision_date"),
                "buy_date": pair.get("buy_date"),
                "sell_date": pair.get("sell_date"),
                "stock": primary_stock,
                "buy_window": result.get("buy_window"),
                "sell_window": result.get("sell_window"),
                "return_pct": round(return_pct, 2),
                "buy_close_near_limit": result.get("buy_close_near_limit"),
                "buy_window_entry_change_pct": result.get("buy_window_entry_change_pct"),
            }
        )
    return samples


def _build_window_performance_comparison(pair_payloads, matrix_summary, benchmark_summary):
    period_count = max(1, len(pair_payloads))
    benchmark_rows = benchmark_summary.get("rows") if isinstance(benchmark_summary, dict) else []
    benchmark_returns = {
        item.get("label"): item.get("cumulative_return_pct")
        for item in benchmark_rows or []
        if isinstance(item, dict)
    }

    def build_row(label, buy_window_id, sell_window_id, samples, exclusion, all_sample_count=None):
        curve = _build_equity_curve(samples)
        sample_count = curve.get("sample_count", 0)
        returns = [_safe_float(sample.get("return_pct"), None) for sample in samples]
        returns = [item for item in returns if item is not None]
        cumulative_return = curve.get("cumulative_return_pct")
        row = {
            "label": label,
            "buy_window_id": buy_window_id,
            "sell_window_id": sell_window_id,
            "buy_window": samples[0].get("buy_window") if samples else "",
            "sell_window": samples[0].get("sell_window") if samples else "",
            "sample_count": sample_count,
            "all_sample_count": all_sample_count if all_sample_count is not None else sample_count,
            "period_count": period_count,
            "average_return_pct": round(sum(returns) / len(returns), 2) if returns else None,
            "final_net_value": curve.get("final_net_value"),
            "cumulative_return_pct": cumulative_return,
            "monthly_return_pct": (
                round(_annualized_pct_from_net_value(curve.get("final_net_value"), period_count, 21), 2)
                if sample_count else None
            ),
            "annualized_return_pct": (
                round(_annualized_pct_from_net_value(curve.get("final_net_value"), period_count, 252), 2)
                if sample_count else None
            ),
            "max_drawdown_pct": curve.get("max_drawdown_pct"),
            "exclusion": exclusion,
            "basis": "月度按21个交易日折算；252日折算只作短样本参考；空仓日按净值不变处理；未计手续费、滑点和真实分时成交",
        }
        for spec in INDEX_BENCHMARK_SPECS:
            benchmark_label = spec["label"]
            benchmark_return = _safe_float(benchmark_returns.get(benchmark_label), None)
            row[f"excess_{benchmark_label}"] = (
                round(cumulative_return - benchmark_return, 2)
                if cumulative_return is not None and benchmark_return is not None
                else None
            )
        return row

    rows = []
    matrix_rows = matrix_summary.get("rows") if isinstance(matrix_summary, dict) else []
    for item in matrix_rows or []:
        if not isinstance(item, dict) or item.get("average_return_pct") is None:
            continue
        rows.append(
            build_row(
                f"{item.get('buy_window')}买 / {item.get('sell_window')}卖（原始）",
                item.get("buy_window_id"),
                item.get("sell_window_id"),
                _samples_for_combo(pair_payloads, item.get("buy_window_id"), item.get("sell_window_id")),
                "未剔除接近涨停买点",
            )
        )

    filtered_configs = [
        (
            "09:30-09:35买 / 14:30-14:55卖（剔除开盘接近涨停）",
            "open_0930_0935",
            "late_1430_1455",
            lambda sample: not _open_buy_near_limit(sample),
            "剔除T+1开盘买点已接近涨停的样本",
        ),
        (
            "14:30-14:55买 / 14:30-14:55卖（剔除收盘接近涨停）",
            "late_1430_1455",
            "late_1430_1455",
            lambda sample: not sample.get("buy_close_near_limit"),
            "剔除T+1收盘接近涨停的样本",
        ),
    ]
    for label, buy_window_id, sell_window_id, predicate, exclusion in filtered_configs:
        all_samples = _samples_for_combo(pair_payloads, buy_window_id, sell_window_id)
        samples = [sample for sample in all_samples if predicate(sample)]
        rows.append(build_row(label, buy_window_id, sell_window_id, samples, exclusion, all_sample_count=len(all_samples)))

    return {
        "period_count": period_count,
        "rows": rows,
        "basis": "同一T0样本区间内比较策略窗口和指数首尾表现；月度折算只作短样本参考，不代表真实成交承诺",
    }


def _build_trade_window_matrix_summary(pair_payloads):
    rows = []
    all_samples = []
    for buy_window in BUY_WINDOWS:
        for sell_window in SELL_WINDOWS:
            returns = []
            combo_samples = []
            positive_count = 0
            best_sample = {}
            worst_sample = {}
            for pair in pair_payloads:
                strategy = pair.get("paper_strategy") if isinstance(pair.get("paper_strategy"), dict) else {}
                target_summary = strategy.get("target_summary") if isinstance(strategy.get("target_summary"), dict) else {}
                primary_stock = _clean(target_summary.get("primary_stock"))
                evaluations = strategy.get("target_evaluations") if isinstance(strategy.get("target_evaluations"), list) else []
                primary = next((item for item in evaluations if _clean(item.get("stock_label")) == primary_stock), None)
                if not primary:
                    continue
                review = primary.get("tplus2_exit_review") if isinstance(primary.get("tplus2_exit_review"), dict) else {}
                result = next(
                    (
                        item for item in review.get("window_matrix") or []
                        if isinstance(item, dict)
                        and item.get("buy_window_id") == buy_window["id"]
                        and item.get("sell_window_id") == sell_window["id"]
                    ),
                    {},
                )
                return_pct = _safe_float(result.get("return_pct"), None)
                if return_pct is None:
                    continue
                sample = {
                    "decision_date": pair.get("effective_decision_date"),
                    "buy_date": pair.get("buy_date"),
                    "sell_date": pair.get("sell_date"),
                    "stock": primary_stock,
                    "buy_window": result.get("buy_window") or buy_window["window"],
                    "buy_proxy_label": result.get("buy_proxy_label") or buy_window["proxy_label"],
                    "sell_window": result.get("sell_window") or sell_window["window"],
                    "sell_proxy_label": result.get("sell_proxy_label") or sell_window["proxy_label"],
                    "entry_price": result.get("entry_price"),
                    "exit_price": result.get("exit_price"),
                    "buy_day_change_pct": result.get("buy_day_change_pct"),
                    "buy_window_entry_change_pct": result.get("buy_window_entry_change_pct"),
                    "buy_limit_state": result.get("buy_limit_state"),
                    "buy_close_near_limit": result.get("buy_close_near_limit"),
                    "buy_window_buyability_note": result.get("buy_window_buyability_note"),
                    "return_pct": round(return_pct, 2),
                    "basis": result.get("basis"),
                }
                returns.append(return_pct)
                all_samples.append(sample)
                combo_samples.append(sample)
                if return_pct > 0:
                    positive_count += 1
                if not best_sample or return_pct > best_sample["return_pct"]:
                    best_sample = sample
                if not worst_sample or return_pct < worst_sample["return_pct"]:
                    worst_sample = sample
            avg_return = round(sum(returns) / len(returns), 2) if returns else None
            buy_window_entry_changes = [
                _safe_float(sample.get("buy_window_entry_change_pct"), None)
                for sample in combo_samples
                if _safe_float(sample.get("buy_window_entry_change_pct"), None) is not None
            ]
            buy_day_changes = [
                _safe_float(sample.get("buy_day_change_pct"), None)
                for sample in combo_samples
                if _safe_float(sample.get("buy_day_change_pct"), None) is not None
            ]
            near_limit_count = sum(1 for sample in combo_samples if sample.get("buy_close_near_limit"))
            buyability_note = "暂无买入日涨停状态"
            if combo_samples:
                if near_limit_count:
                    buyability_note = (
                        f"{near_limit_count}/{len(combo_samples)} 个T+1买入日收盘接近涨停；"
                        "尾盘买入代理可能只是理论可买"
                    )
                else:
                    buyability_note = "T+1买入日收盘未显示接近涨停；仍需分时成交确认"
            rows.append(
                {
                    "id": f"{buy_window['id']}__{sell_window['id']}",
                    "buy_window_id": buy_window["id"],
                    "buy_window": buy_window["window"],
                    "buy_proxy_label": buy_window["proxy_label"],
                    "sell_window_id": sell_window["id"],
                    "sell_window": sell_window["window"],
                    "sell_proxy_label": sell_window["proxy_label"],
                    "sample_count": len(returns),
                    "average_return_pct": avg_return,
                    "positive_count": positive_count,
                    "average_buy_day_change_pct": (
                        round(sum(buy_day_changes) / len(buy_day_changes), 2) if buy_day_changes else None
                    ),
                    "average_buy_window_entry_change_pct": (
                        round(sum(buy_window_entry_changes) / len(buy_window_entry_changes), 2)
                        if buy_window_entry_changes else None
                    ),
                    "near_limit_buy_count": near_limit_count,
                    "buyability_note": buyability_note,
                    "best_sample": best_sample,
                    "worst_sample": worst_sample,
                    "equity_curve": _build_equity_curve(combo_samples),
                    "basis": "股票级分时缺失，使用T+1/T+2日线代理统计" if returns else "样本价格事实不足",
                }
            )
    valid_rows = [row for row in rows if row["average_return_pct"] is not None]
    best_row = max(valid_rows, key=lambda item: item["average_return_pct"]) if valid_rows else {}
    best_combo = {
        "buy_window_id": best_row.get("buy_window_id", ""),
        "buy_window": best_row.get("buy_window", ""),
        "sell_window_id": best_row.get("sell_window_id", ""),
        "sell_window": best_row.get("sell_window", ""),
        "average_return_pct": best_row.get("average_return_pct"),
        "sample_count": best_row.get("sample_count", 0),
    }
    if best_row and best_row.get("sample_count", 0) >= 3:
        recommendation = (
            f"当前样本里 T+1 {best_row['buy_window']} 价格代理、"
            f"T+2 {best_row['sell_window']} 价格代理的日线代理结果较高"
        )
    elif best_row:
        recommendation = (
            f"当前样本太少，只能暂看 T+1 {best_row['buy_window']} 价格代理、"
            f"T+2 {best_row['sell_window']} 价格代理"
        )
    else:
        recommendation = "缺少可计算样本，不能判断窗口代理组合"
    recommended_curve = best_row.get("equity_curve") if isinstance(best_row.get("equity_curve"), dict) else {}
    return {
        "rows": rows,
        "best_combo": best_combo,
        "recommended_equity_curve": recommended_curve,
        "top_gain_samples": sorted(
            (item for item in all_samples if item["return_pct"] > 0),
            key=lambda item: item["return_pct"],
            reverse=True,
        )[:10],
        "top_loss_samples": sorted(
            (item for item in all_samples if item["return_pct"] < 0),
            key=lambda item: item["return_pct"],
        )[:10],
        "recommendation": recommendation,
        "data_basis": "T+1和T+2都只按日线开盘/日内中枢/收盘做代理；没有股票分钟成交价时不做精确窗口收益，也不形成交易建议",
    }


def _build_buyability_summary(pair_payloads):
    distribution = Counter()
    dates = defaultdict(list)
    rows = []
    executable_dates = []
    unbuyable_dates = []
    risk_dates = []
    missing_dates = []
    pending_confirm_dates = []
    for pair in pair_payloads:
        decision_date = _clean(pair.get("effective_decision_date"))
        strategy = pair.get("paper_strategy") if isinstance(pair.get("paper_strategy"), dict) else {}
        target_summary = strategy.get("target_summary") if isinstance(strategy.get("target_summary"), dict) else {}
        primary_stock = _clean(target_summary.get("primary_stock"))
        evaluations = strategy.get("target_evaluations") if isinstance(strategy.get("target_evaluations"), list) else []
        primary = next((item for item in evaluations if _clean(item.get("stock_label")) == primary_stock), None)
        if not primary:
            continue
        review = primary.get("tplus2_exit_review") if isinstance(primary.get("tplus2_exit_review"), dict) else {}
        buyability = review.get("buyability_review") if isinstance(review.get("buyability_review"), dict) else {}
        status = _clean(buyability.get("status"), "分时事实待补")
        distribution[status] += 1
        dates[status].append(decision_date)
        if status == "早盘未明显追高":
            executable_dates.append(decision_date)
        elif status == "可能买不到":
            unbuyable_dates.append(decision_date)
        elif status == "追高风险":
            risk_dates.append(decision_date)
        elif status == "待分时确认":
            pending_confirm_dates.append(decision_date)
        else:
            missing_dates.append(decision_date)
        rows.append(
            {
                "decision_date": decision_date,
                "buy_date": pair.get("buy_date") or pair.get("target_date"),
                "sell_date": pair.get("sell_date"),
                "stock": primary_stock,
                "status": status,
                "reason": buyability.get("reason"),
                "early_high_change_pct": buyability.get("early_high_change_pct"),
                "early_close_change_pct": buyability.get("early_close_change_pct"),
                "minute_count": buyability.get("minute_count"),
                "minute_source": buyability.get("minute_source"),
            }
        )
    return {
        "sample_count": len(rows),
        "distribution": dict(distribution),
        "dates": {key: value for key, value in dates.items()},
        "early_not_chasing_day_count": len(executable_dates),
        "executable_day_count": len(executable_dates),
        "risk_day_count": len(risk_dates),
        "unbuyable_day_count": len(unbuyable_dates),
        "pending_confirm_day_count": len(pending_confirm_dates),
        "missing_day_count": len(missing_dates),
        "early_not_chasing_dates": executable_dates,
        "executable_dates": executable_dates,
        "risk_dates": risk_dates,
        "unbuyable_dates": unbuyable_dates,
        "pending_confirm_dates": pending_confirm_dates,
        "missing_dates": missing_dates,
        "rows": rows,
        "basis": "只统计纸面主样本的T+1买点可达性；分时事实不足时可用涨停池、热榜和日线代理识别追高或待确认，但不宣称真实可执行",
    }


def _primary_paper_evaluation(pair):
    pair = pair if isinstance(pair, dict) else {}
    strategy = pair.get("paper_strategy") if isinstance(pair.get("paper_strategy"), dict) else {}
    target_summary = strategy.get("target_summary") if isinstance(strategy.get("target_summary"), dict) else {}
    primary_stock = _clean(target_summary.get("primary_stock"))
    evaluations = strategy.get("target_evaluations") if isinstance(strategy.get("target_evaluations"), list) else []
    return next((item for item in evaluations if _clean(item.get("stock_label")) == primary_stock), {})


def _small_account_fit_for_window(evaluation, buy_window_id):
    review = evaluation.get("tplus2_exit_review") if isinstance(evaluation, dict) else {}
    account_review = review.get("small_account_fit_review") if isinstance(review, dict) and isinstance(review.get("small_account_fit_review"), dict) else {}
    return next(
        (
            item for item in account_review.get("windows") or []
            if isinstance(item, dict) and item.get("buy_window_id") == buy_window_id
        ),
        {},
    )


def _build_small_account_summary(pair_payloads, preferred_buy_window_id):
    distribution = Counter()
    action_distribution = Counter()
    rows = []
    for pair in pair_payloads:
        evaluation = _primary_paper_evaluation(pair)
        if not evaluation:
            continue
        fit = _small_account_fit_for_window(evaluation, preferred_buy_window_id)
        if not fit:
            continue
        distribution[_clean(fit.get("account_fit"), "待补")] += 1
        action_distribution[_clean(fit.get("small_account_action"), "待补")] += 1
        rows.append(
            {
                "decision_date": pair.get("effective_decision_date"),
                "buy_date": pair.get("buy_date"),
                "sell_date": pair.get("sell_date"),
                "stock": evaluation.get("stock_label"),
                "buy_window": fit.get("buy_window"),
                "entry_price": fit.get("entry_price"),
                "one_lot_amount": fit.get("one_lot_amount"),
                "one_lot_account_pct": fit.get("one_lot_account_pct"),
                "account_fit": fit.get("account_fit"),
                "position_50pct_basis": fit.get("position_50pct_basis"),
                "small_account_action": fit.get("small_account_action"),
            }
        )
    return {
        "schema_version": "small_account_summary.v1",
        "sample_count": len(rows),
        "preferred_buy_window_id": preferred_buy_window_id,
        "distribution": dict(distribution),
        "action_distribution": dict(action_distribution),
        "rows": rows,
        "basis": "按全样本较高买入窗口换算一手金额；账户结论只修正实际可做性，不改写T0纸面主样本",
    }


def _minute_gap_notice(minute_refill, buyability_summary):
    minute_refill = minute_refill if isinstance(minute_refill, dict) else {}
    buyability_summary = buyability_summary if isinstance(buyability_summary, dict) else {}
    if minute_refill.get("enabled") and _safe_int(minute_refill.get("filled")) <= 0 and (
        _safe_int(minute_refill.get("errors")) > 0 or _safe_int(minute_refill.get("missing")) > 0
    ):
        return (
            "分时事实不可用，本页真实可买性只按涨停池、热榜和日线代理复核；"
            "这些标签能提示追高风险，但不能证明真实成交路径。"
        )
    if _safe_int(buyability_summary.get("missing_day_count")) > 0:
        return "仍有样本缺少可用于买点复核的事实。"
    return "分时或代理复核事实已覆盖当前纸面主样本。"


def _build_target_action_summary(pair_payloads):
    action_distribution = Counter()
    action_dates = defaultdict(list)
    empty_reason_distribution = Counter()
    empty_reason_dates = defaultdict(list)
    target_dates = []
    watch_dates = []
    skip_dates = []
    empty_dates = []
    rows = []
    for pair in pair_payloads:
        decision_date = _clean(pair.get("effective_decision_date"))
        strategy = pair.get("paper_strategy") if isinstance(pair.get("paper_strategy"), dict) else {}
        action = _clean(strategy.get("action"), "paper_skip")
        action_label = _clean(strategy.get("action_label"), "纸面不参与")
        action_reason = _clean(strategy.get("action_reason"), "缺少纸面动作理由")
        primary = strategy.get("primary_candidate") if isinstance(strategy.get("primary_candidate"), dict) else {}
        primary_label = _clean(primary.get("stock_label") or (strategy.get("target_summary") or {}).get("primary_stock"), "无主样本")
        action_distribution[action_label] += 1
        action_dates[action_label].append(decision_date)
        if action == "paper_participate":
            target_dates.append(decision_date)
            decision_type = "有纸面主样本"
        elif action == "paper_watch":
            watch_dates.append(decision_date)
            empty_dates.append(decision_date)
            empty_reason_distribution[action_reason] += 1
            empty_reason_dates[action_reason].append(decision_date)
            decision_type = "观察但不执行"
        else:
            skip_dates.append(decision_date)
            empty_dates.append(decision_date)
            empty_reason_distribution[action_reason] += 1
            empty_reason_dates[action_reason].append(decision_date)
            decision_type = "明确空仓"
        rows.append(
            {
                "decision_date": decision_date,
                "decision_type": decision_type,
                "action_label": action_label,
                "primary_stock": primary_label,
                "reason": action_reason,
            }
        )
    sample_count = len(pair_payloads)
    return {
        "sample_count": sample_count,
        "target_day_count": len(target_dates),
        "target_dates": target_dates,
        "watch_day_count": len(watch_dates),
        "watch_dates": watch_dates,
        "skip_day_count": len(skip_dates),
        "skip_dates": skip_dates,
        "execution_empty_day_count": len(empty_dates),
        "execution_empty_dates": empty_dates,
        "empty_reason_distribution": dict(empty_reason_distribution),
        "empty_reason_dates": {key: dates for key, dates in empty_reason_dates.items()},
        "action_distribution": dict(action_distribution),
        "action_dates": {key: dates for key, dates in action_dates.items()},
        "rows": rows,
        "decision_rule": "纸面主样本只作为复核对象；纸面观察和纸面不参与都不生成原日报执行对象，其中纸面不参与是明确空仓，纸面观察是观察空仓",
    }


def _build_emotion_transition_summary(pair_payloads):
    distribution = Counter()
    rows = []
    for pair in pair_payloads:
        emotion = pair.get("emotion_review") if isinstance(pair.get("emotion_review"), dict) else {}
        strategy = pair.get("paper_strategy") if isinstance(pair.get("paper_strategy"), dict) else {}
        target_summary = strategy.get("target_summary") if isinstance(strategy.get("target_summary"), dict) else {}
        evaluations = strategy.get("target_evaluations") if isinstance(strategy.get("target_evaluations"), list) else []
        primary = next((item for item in evaluations if _clean(item.get("stock_label")) == _clean(target_summary.get("primary_stock"))), {})
        best_window = _best_exit_window(primary)
        t1_market = _clean((emotion.get("tplus1_market") or {}).get("label"), "待补事实")
        t2_market = _clean((emotion.get("tplus2_market") or {}).get("label"), "待补事实")
        t1_sector = _clean((emotion.get("tplus1_sector") or {}).get("label"), "待补事实")
        t2_sector = _clean((emotion.get("tplus2_sector") or {}).get("label"), "待补事实")
        key = f"{t1_market}/{t1_sector} -> {t2_market}/{t2_sector}"
        distribution[key] += 1
        rows.append(
            {
                "decision_date": pair.get("effective_decision_date"),
                "buy_date": pair.get("buy_date"),
                "sell_date": pair.get("sell_date"),
                "primary_stock": target_summary.get("primary_stock"),
                "tplus1_market": t1_market,
                "tplus1_sector": t1_sector,
                "tplus2_market": t2_market,
                "tplus2_sector": t2_sector,
                "best_sell_window": best_window.get("window", ""),
                "best_return_pct": best_window.get("return_pct"),
            }
        )
    return {
        "distribution": dict(distribution),
        "rows": rows,
        "basis": "情绪标签来自历史日报字段和板块事实的可见复核，不是T0时点的确定预言",
    }


def _projection_return_stats(rows):
    stats = []
    for window in SELL_WINDOWS:
        values = [
            _safe_float(row.get("return_pct"), None)
            for row in rows
            if row.get("window_id") == window["id"] and _safe_float(row.get("return_pct"), None) is not None
        ]
        if values:
            avg_return = round(sum(values) / len(values), 2)
            positive_count = sum(1 for value in values if value > 0)
        else:
            avg_return = None
            positive_count = 0
        stats.append(
            {
                "id": window["id"],
                "window": window["window"],
                "sample_count": len(values),
                "average_return_pct": avg_return,
                "positive_count": positive_count,
            }
        )
    valid = [item for item in stats if item["average_return_pct"] is not None]
    best = max(valid, key=lambda item: item["average_return_pct"]) if valid else {}
    return {
        "windows": stats,
        "best_window": best.get("window", ""),
        "best_average_return_pct": best.get("average_return_pct"),
        "basis": "按T+1收盘买入、T+2三段日线代理卖出统计；完整买卖窗口组合见T+1买入 x T+2卖出矩阵",
    }


def _build_emotion_projection_summary(pair_payloads):
    grouped = {}
    for pair in pair_payloads:
        projection = pair.get("emotion_projection") if isinstance(pair.get("emotion_projection"), dict) else {}
        emotion = pair.get("emotion_review") if isinstance(pair.get("emotion_review"), dict) else {}
        strategy = pair.get("paper_strategy") if isinstance(pair.get("paper_strategy"), dict) else {}
        target_summary = strategy.get("target_summary") if isinstance(strategy.get("target_summary"), dict) else {}
        primary_stock = _clean(target_summary.get("primary_stock"))
        evaluations = strategy.get("target_evaluations") if isinstance(strategy.get("target_evaluations"), list) else []
        primary = next((item for item in evaluations if _clean(item.get("stock_label")) == primary_stock), {})
        windows = ((primary.get("tplus2_exit_review") or {}).get("windows") or []) if isinstance(primary, dict) else []
        market_projected = _clean(((projection.get("market") or {}).get("tplus2") or {}).get("label"), "待判读")
        sector_projected = _clean(((projection.get("sector") or {}).get("tplus2") or {}).get("label"), "待判读")
        market_actual = _clean((emotion.get("tplus2_market") or {}).get("label"), "待补事实")
        sector_actual = _clean((emotion.get("tplus2_sector") or {}).get("label"), "待补事实")
        labels = (
            ("market", "T+2市场预案", market_projected, market_actual),
            ("sector", "T+2板块预案", sector_projected, sector_actual),
        )
        for group_type, title, projected, actual in labels:
            key = (group_type, projected)
            bucket = grouped.setdefault(
                key,
                {
                    "type": group_type,
                    "title": title,
                    "projected_label": projected,
                    "sample_count": 0,
                    "actual_distribution": Counter(),
                    "match_distribution": Counter(),
                    "return_rows": [],
                    "correct_return_rows": [],
                    "miss_return_rows": [],
                    "sample_dates": [],
                },
            )
            bucket["sample_count"] += 1
            bucket["actual_distribution"][actual] += 1
            calibration = _projection_label_match(projected, actual, kind=group_type)
            bucket["match_distribution"][calibration] += 1
            bucket["sample_dates"].append(pair.get("effective_decision_date"))
            for window in windows:
                return_pct = _safe_float(window.get("return_pct"), None) if isinstance(window, dict) else None
                if return_pct is None:
                    continue
                row = {
                    "window_id": window.get("id"),
                    "return_pct": return_pct,
                }
                bucket["return_rows"].append(row)
                if calibration == "大体一致":
                    bucket["correct_return_rows"].append(row)
                elif calibration == "偏离":
                    bucket["miss_return_rows"].append(row)
    rows = []
    for _, bucket in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        return_stats = _projection_return_stats(bucket["return_rows"])
        match_count = bucket["match_distribution"].get("大体一致", 0)
        miss_count = bucket["match_distribution"].get("偏离", 0)
        unknown_count = bucket["match_distribution"].get("待校准", 0)
        scorable_count = match_count + miss_count
        rows.append(
            {
                "type": bucket["type"],
                "title": bucket["title"],
                "projected_label": bucket["projected_label"],
                "sample_count": bucket["sample_count"],
                "scorable_count": scorable_count,
                "calibrated_count": match_count,
                "miss_count": miss_count,
                "unknown_count": unknown_count,
                "actual_distribution": dict(bucket["actual_distribution"]),
                "match_distribution": dict(bucket["match_distribution"]),
                "return_stats": return_stats,
                "calibrated_return_stats": _projection_return_stats(bucket["correct_return_rows"]),
                "miss_return_stats": _projection_return_stats(bucket["miss_return_rows"]),
                "sample_dates": bucket["sample_dates"],
            }
        )
    return {
        "rows": rows,
        "basis": "T0只生成T+1/T+2交易环境预案；T+2实际标签和收益用于后验校准，不回写T0选择",
    }


def _attach_pair_diagnostics(pair):
    diagnosis = _diagnosis_category(pair)
    mismatch = _evaluate_mismatch(pair)
    pair["zero_action_diagnosis"] = diagnosis
    pair["mismatch_review"] = mismatch
    return pair


def build_forward_replay_pair(
    requested_decision_date,
    buy_date,
    sell_date=None,
    *,
    loader=load_daily_report_data_for_forward_replay,
    price_refill=None,
    minute_refill=None,
    account_capital=10000,
    lot_size=100,
):
    decision_data, coverage = _load_effective_decision_data(requested_decision_date, loader=loader)
    buy_data = loader(buy_date)
    sell_data = None
    sell_data_missing_reason = ""
    if sell_date:
        try:
            sell_data = loader(sell_date)
        except Exception as exc:
            sell_data = {}
            sell_data_missing_reason = f"缺少T+2日报事实：{type(exc).__name__}: {exc}"
    decision_date = coverage["effective_decision_date"]
    preflight = _build_preflight_payload(decision_date, decision_data)
    candidates = _first_layer_candidates(preflight)
    evaluations = []
    for entry in candidates:
        evaluation = _target_evidence_for(entry, buy_data)
        evaluation["buy_review_date"] = buy_date
        evaluation["sell_review_date"] = sell_date or ""
        evaluation["tplus2_exit_review"] = _build_tplus2_exit_review(
            entry,
            buy_date,
            buy_data,
            sell_date=sell_date,
            sell_data=sell_data,
            price_refill=price_refill,
            decision_date=decision_date,
            decision_data=decision_data,
            minute_refill=minute_refill,
            account_capital=account_capital,
            lot_size=lot_size,
        )
        evaluations.append(evaluation)
    paper_strategy = _attach_paper_target_review(
        _build_paper_strategy_decision(decision_date, decision_data),
        buy_date,
        buy_data,
        sell_date=sell_date,
        sell_data=sell_data,
        price_refill=price_refill,
        decision_date=decision_date,
        decision_data=decision_data,
        minute_refill=minute_refill,
        account_capital=account_capital,
        lot_size=lot_size,
    )
    emotion_projection = _build_t0_emotion_projection(decision_data, paper_strategy)
    layer_rows = _layer_rows(preflight)
    mermaid = render_pair_mermaid(
        requested_decision_date=requested_decision_date,
        effective_decision_date=decision_date,
        buy_date=buy_date,
        sell_date=sell_date,
        layer_rows=layer_rows,
        candidate_count=len(candidates),
    )
    primary_sector = _clean((paper_strategy.get("primary_candidate") or {}).get("sector"))
    legacy_final_action = (
        (preflight.get("source_payloads") or {}).get("elimination_tournament_payload", {}).get("final_action")
        or {}
    )
    preflight_final_action = preflight.get("final_action") or {}
    paper_review_object = _review_object_from_paper_strategy(paper_strategy)
    paper_review_contrast = _paper_review_contrast(legacy_final_action, paper_review_object)
    t0_market_context = _market_context_for_pair(
        {"effective_decision_date": decision_date},
        lambda _date: decision_data,
    )
    return _attach_pair_diagnostics({
        "requested_decision_date": requested_decision_date,
        "effective_decision_date": decision_date,
        "target_date": buy_date,
        "buy_date": buy_date,
        "sell_date": sell_date or "",
        "coverage": coverage,
        "candidate_count": len(candidates),
        "decision_candidate_count": len(candidates),
        "validation_scope": {
            "decision_date": decision_date,
            "validation_date": buy_date,
            "buy_date": buy_date,
            "sell_date": sell_date or "",
            "decision_data_role": "生成决策日候选与淘汰链",
            "target_data_role": "只复核决策日候选的T+1买入日表现",
            "sell_data_role": "只复核T+2卖出窗口代理收益",
            "target_day_not_used_for": ["候选生成", "淘汰链生成", "最终动作生成"],
            "sell_day_not_used_for": ["候选生成", "淘汰链生成", "T+1买入资格生成"],
            "price_refill_role": "优先获取T+1/T+2价格事实" if callable(price_refill) else "未启用外部价格获取",
            "minute_refill_role": "优先获取T+1分时事实以复核真实可买性" if callable(minute_refill) else "未启用分时事实获取",
        },
        "trade_timeline": {
            "decision_date": decision_date,
            "buy_date": buy_date,
            "sell_date": sell_date or "",
            "t0_role": "T0复盘，只生成候选和淘汰链",
            "tplus1_role": "T+1买入日，只复核是否有买入资格",
            "tplus2_role": "T+2卖出日，按三段卖出窗口代理复核收益",
        },
        "emotion_projection": emotion_projection,
        "emotion_review": {
            "tplus1_market": _market_emotion_state(buy_data),
            "tplus1_sector": _sector_emotion_state(buy_data, primary_sector),
            "tplus2_market": (
                _market_emotion_state(sell_data)
                if isinstance(sell_data, dict) and sell_data
                else {"label": "待补事实", "basis": sell_data_missing_reason or "缺少T+2交易日"}
            ),
            "tplus2_sector": (
                _sector_emotion_state(sell_data, primary_sector)
                if isinstance(sell_data, dict) and sell_data
                else {"sector": primary_sector, "label": "待补事实", "basis": sell_data_missing_reason or "缺少T+2交易日"}
            ),
        },
        "final_action": legacy_final_action,
        "legacy_final_action": legacy_final_action,
        "preflight_final_action": preflight_final_action,
        "paper_review_object": paper_review_object,
        "paper_review_contrast": paper_review_contrast,
        "t0_market_context": t0_market_context,
        "layers": layer_rows,
        "evaluations": evaluations,
        "paper_strategy": paper_strategy,
        "price_refill_summary": _price_refill_summary(price_refill),
        "sell_data_missing_reason": sell_data_missing_reason,
        "mermaid": mermaid,
    })


def render_pair_mermaid(*, requested_decision_date, effective_decision_date, buy_date, sell_date, layer_rows, candidate_count):
    lines = ["flowchart LR"]
    if requested_decision_date != effective_decision_date:
        lines.append(f'  A["请求决策日 {requested_decision_date}"] --> B["事实缺失，改用 {effective_decision_date}"]')
        previous = "B"
    else:
        lines.append(f'  A["决策日 {effective_decision_date}"]')
        previous = "A"
    for index, layer in enumerate(layer_rows, start=1):
        node = f"L{index}"
        title = layer.get("title") or f"第{index}层"
        label = f'{title}: 输入{layer.get("input_count", 0)} / 淘汰{layer.get("eliminated_count", 0)} / 剩{layer.get("survivor_count", 0)}'
        lines.append(f'  {previous} --> {node}["{label}"]')
        previous = node
    lines.append(f'  {previous} --> BDAY["T+1买入日 {buy_date} 复核 {candidate_count} 只决策日候选"]')
    lines.append(f'  BDAY --> SDAY["T+2卖出日 {sell_date or "待补"} 三段窗口复核"]')
    return "\n".join(lines)


def _build_forward_replay_summary(pair_payloads, discovery=None):
    action_distribution = Counter()
    action_dates = defaultdict(list)
    legacy_action_distribution = Counter()
    legacy_action_dates = defaultdict(list)
    paper_action_distribution = Counter()
    paper_action_dates = defaultdict(list)
    paper_outcome_distribution = Counter()
    paper_outcome_dates = defaultdict(list)
    diagnosis_distribution = Counter()
    diagnosis_dates = defaultdict(list)
    first_zero_layer_distribution = Counter()
    first_zero_layer_dates = defaultdict(list)
    candidate_zero_dates = []
    mismatch_samples = []
    positive_action_dates = []
    legacy_positive_action_dates = []
    candidate_counts = []
    paper_candidate_counts = []
    paper_candidate_zero_dates = []
    paper_hit_samples = []
    zero_action_with_candidates_dates = []
    paper_review_contrast_samples = []

    for pair in pair_payloads:
        decision_date = _clean(pair.get("effective_decision_date"))
        candidate_count = _safe_int(pair.get("candidate_count"))
        candidate_counts.append(candidate_count)
        final_action = pair.get("legacy_final_action") or pair.get("final_action") or pair.get("preflight_final_action") or {}
        final_pct = _final_position_pct(final_action)
        action_key = f"{final_pct}%"
        action_distribution[action_key] += 1
        action_dates[action_key].append(decision_date)
        if final_pct > 0:
            positive_action_dates.append(decision_date)
        legacy_final_action = pair.get("legacy_final_action") or pair.get("final_action") or {}
        legacy_pct = _final_position_pct(legacy_final_action)
        legacy_key = f"{legacy_pct}%"
        legacy_action_distribution[legacy_key] += 1
        legacy_action_dates[legacy_key].append(decision_date)
        if legacy_pct > 0:
            legacy_positive_action_dates.append(decision_date)
        if candidate_count <= 0:
            candidate_zero_dates.append(decision_date)
        elif final_pct <= 0:
            zero_action_with_candidates_dates.append(decision_date)

        paper_strategy = pair.get("paper_strategy") if isinstance(pair.get("paper_strategy"), dict) else {}
        paper_action = _clean(paper_strategy.get("action_label"), "纸面不参与")
        paper_candidates = paper_strategy.get("paper_candidates") if isinstance(paper_strategy.get("paper_candidates"), list) else []
        target_summary = paper_strategy.get("target_summary") if isinstance(paper_strategy.get("target_summary"), dict) else {}
        paper_candidate_counts.append(len(paper_candidates))
        paper_action_distribution[paper_action] += 1
        paper_action_dates[paper_action].append(decision_date)
        if not paper_candidates:
            paper_candidate_zero_dates.append(decision_date)
        paper_outcome = _clean(target_summary.get("primary_outcome_label"), "没有纸面主样本")
        paper_outcome_distribution[paper_outcome] += 1
        paper_outcome_dates[paper_outcome].append(decision_date)
        if target_summary.get("primary_outcome") in {"paper_stock_hit", "paper_sector_hit_stock_missed"}:
            primary_evaluation = next(
                (
                    item for item in paper_strategy.get("target_evaluations") or []
                    if isinstance(item, dict) and _clean(item.get("stock_label")) == _clean(target_summary.get("primary_stock"))
                ),
                {},
            )
            best_window = _best_exit_window(primary_evaluation)
            best_combo = _best_trade_window_combo(primary_evaluation)
            paper_hit_samples.append(
                {
                    "decision_date": decision_date,
                    "buy_date": pair.get("buy_date") or pair.get("target_date"),
                    "sell_date": pair.get("sell_date"),
                    "paper_action": paper_action,
                    "primary_stock": target_summary.get("primary_stock"),
                    "primary_outcome": paper_outcome,
                    "action_reason": paper_strategy.get("action_reason"),
                    "best_sell_window": best_window.get("window", ""),
                    "best_return_pct": best_window.get("return_pct"),
                    "best_buy_window": best_combo.get("buy_window", ""),
                    "best_combo_sell_window": best_combo.get("sell_window", ""),
                    "best_combo_return_pct": best_combo.get("return_pct"),
                }
            )

        diagnosis = pair.get("zero_action_diagnosis") or {}
        category = _clean(diagnosis.get("category"), "未归因")
        diagnosis_distribution[category] += 1
        diagnosis_dates[category].append(decision_date)
        first_zero_layer = _clean(diagnosis.get("first_zero_layer"))
        if first_zero_layer:
            first_zero_layer_distribution[first_zero_layer] += 1
            first_zero_layer_dates[first_zero_layer].append(decision_date)

        mismatch = pair.get("mismatch_review") or {}
        if mismatch:
            mismatch_samples.append(
                {
                    "decision_date": decision_date,
                    "buy_date": pair.get("buy_date") or pair.get("target_date"),
                    "sell_date": pair.get("sell_date"),
                    "type": mismatch.get("type"),
                    "items": mismatch.get("items") or [],
                    "diagnosis": category,
                }
            )
        paper_review_contrast = pair.get("paper_review_contrast") if isinstance(pair.get("paper_review_contrast"), dict) else {}
        if paper_review_contrast:
            paper_review_contrast_samples.append(
                {
                    "decision_date": decision_date,
                    "legacy_action": paper_review_contrast.get("legacy_action") or {},
                    "paper_review_object": paper_review_contrast.get("paper_review_object") or {},
                    "resolution": paper_review_contrast.get("resolution"),
                }
            )

    sample_count = len(pair_payloads)
    zero_only = bool(pair_payloads) and not positive_action_dates
    all_zero_problem = zero_only and sample_count >= 20
    if all_zero_problem:
        verdict = {
            "level": "invalid_chain",
            "conclusion": f"当前覆盖样本全部显示原日报最终动作 0%，链路需要复核：{sample_count}/{sample_count} 天最终都是 0%",
            "evidence": (
                f"{len(candidate_zero_dates)} 天候选入口为空；"
                f"{len(zero_action_with_candidates_dates)} 天已有候选但最终仍为 0%；"
                f"{len(mismatch_samples)} 组出现 T0不参与但T+1证据走强"
            ),
            "root_causes": [
                "历史候选恢复入口不完整，四月到五月中旬大量快照无法恢复新淘汰赛候选",
                "有候选后的条件链过严，价格行为或周期/账户层把所有样本压成 0%",
                "最终动作转换缺少可执行的具体不参与理由，不能证明这些 0% 都是正确判断",
            ],
        }
        next_action = "停止把该回测当作策略有效证据；下一步先修候选恢复入口，再校准价格行为和最终动作转换"
    elif zero_only and pair_payloads:
        verdict = {
            "level": "needs_diagnosis",
            "conclusion": "样本内最终动作全部为 0%，需要继续排查条件链或数据链",
            "evidence": f"{sample_count} 组样本全部 0%",
            "root_causes": ["样本偏少，先扩大覆盖后再判断是否系统性失效"],
        }
        next_action = "优先排查最终动作转换异常、价格行为层过严或历史事实覆盖缺口，不能解释成每天都没有短线机会"
    elif positive_action_dates:
        verdict = {
            "level": "mixed",
            "conclusion": "样本内存在非 0% 动作，先复核正仓位样本是否真实可执行",
            "evidence": f"{len(positive_action_dates)} 天存在非 0% 动作",
            "root_causes": [],
        }
        next_action = "先复核正仓位样本是否真的来自T0事实，再比较 0% 日期的归因差异"
    else:
        verdict = {
            "level": "insufficient_sample",
            "conclusion": "样本不足，无法判断策略链路",
            "evidence": "没有可用日期对",
            "root_causes": ["历史事实覆盖不足"],
        }
        next_action = "样本不足，先补历史事实覆盖"

    paper_active_count = sum(
        count
        for action, count in paper_action_distribution.items()
        if action in {"板块资金载体主样本", "纸面主样本", "纸面参与", "纸面观察"}
    )
    if sample_count and paper_active_count:
        comparison_verdict = {
            "conclusion": (
                f"新版纸面策略在 {paper_active_count}/{sample_count} 天恢复出板块资金载体，"
                "板块优先链路只作为纸面复核对象，原日报最终动作单独保留"
            ),
            "evidence": (
                f"旧链路非0%日期{len(legacy_positive_action_dates)}天；"
                f"原日报最终动作非0%日期{len(positive_action_dates)}天；"
                f"新版纸面主样本被T+1复核确认或板块确认{len(paper_hit_samples)}天"
            ),
            "next_action": "逐日检查纸面命中与未命中样本，把有效条件沉淀回每日 T0 推演和T+1/T+2预案",
        }
    else:
        comparison_verdict = {
            "conclusion": "新版纸面策略仍没有恢复出足够样本，优先检查历史字段覆盖与板块匹配规则",
            "evidence": f"纸面候选为空{len(paper_candidate_zero_dates)}天",
            "next_action": "先修历史事实字段匹配，不继续调最终动作",
        }

    exit_window_summary = _build_exit_window_summary(pair_payloads)
    trade_window_matrix_summary = _build_trade_window_matrix_summary(pair_payloads)
    buyability_summary = _build_buyability_summary(pair_payloads)
    target_action_summary = _build_target_action_summary(pair_payloads)
    emotion_transition_summary = _build_emotion_transition_summary(pair_payloads)
    emotion_projection_summary = _build_emotion_projection_summary(pair_payloads)
    index_benchmark_summary = _build_index_benchmark_summary(pair_payloads)
    window_performance_comparison = _build_window_performance_comparison(
        pair_payloads,
        trade_window_matrix_summary,
        index_benchmark_summary,
    )
    small_account_summary = _build_small_account_summary(
        pair_payloads,
        _clean(trade_window_matrix_summary.get("best_combo", {}).get("buy_window_id"), "open_0930_0935"),
    )
    return {
        "sample_count": sample_count,
        "zero_only": zero_only,
        "all_zero_problem": all_zero_problem,
        "system_verdict": verdict,
        "action_distribution": dict(sorted(action_distribution.items())),
        "action_dates": {key: dates for key, dates in sorted(action_dates.items())},
        "legacy_action_distribution": dict(sorted(legacy_action_distribution.items())),
        "legacy_action_dates": {key: dates for key, dates in sorted(legacy_action_dates.items())},
        "paper_action_distribution": dict(paper_action_distribution),
        "paper_action_dates": {key: dates for key, dates in paper_action_dates.items()},
        "paper_outcome_distribution": dict(paper_outcome_distribution),
        "paper_outcome_dates": {key: dates for key, dates in paper_outcome_dates.items()},
        "paper_candidate_zero_dates": paper_candidate_zero_dates,
        "paper_candidate_count_min": min(paper_candidate_counts) if paper_candidate_counts else 0,
        "paper_candidate_count_max": max(paper_candidate_counts) if paper_candidate_counts else 0,
        "paper_hit_samples": paper_hit_samples,
        "exit_window_summary": exit_window_summary,
        "trade_window_matrix_summary": trade_window_matrix_summary,
        "buyability_summary": buyability_summary,
        "small_account_summary": small_account_summary,
        "target_action_summary": target_action_summary,
        "index_benchmark_summary": index_benchmark_summary,
        "window_performance_comparison": window_performance_comparison,
        "emotion_transition_summary": emotion_transition_summary,
        "emotion_projection_summary": emotion_projection_summary,
        "comparison_verdict": comparison_verdict,
        "diagnosis_distribution": dict(diagnosis_distribution),
        "diagnosis_dates": {key: dates for key, dates in diagnosis_dates.items()},
        "first_zero_layer_distribution": dict(first_zero_layer_distribution),
        "first_zero_layer_dates": {key: dates for key, dates in first_zero_layer_dates.items()},
        "candidate_zero_dates": candidate_zero_dates,
        "zero_action_with_candidates_dates": zero_action_with_candidates_dates,
        "candidate_count_min": min(candidate_counts) if candidate_counts else 0,
        "candidate_count_max": max(candidate_counts) if candidate_counts else 0,
        "mismatch_samples": mismatch_samples,
        "paper_review_contrast_count": len(paper_review_contrast_samples),
        "paper_review_contrast_samples": paper_review_contrast_samples,
        "positive_action_dates": positive_action_dates,
        "legacy_positive_action_dates": legacy_positive_action_dates,
        "coverage": discovery or {},
        "next_action": next_action,
    }


def build_forward_replay_payload(
    pairs,
    *,
    loader=load_daily_report_data_for_forward_replay,
    discovery=None,
    price_refill=None,
    minute_refill=None,
    trade_calendar_refill=None,
    account_capital=10000,
    lot_size=100,
):
    pair_payloads = []
    for item in pairs:
        if len(item) == 2:
            decision_date, buy_date = item
            sell_date = None
        else:
            decision_date, buy_date, sell_date = item
        pair_payloads.append(
            build_forward_replay_pair(
                decision_date,
                buy_date,
                sell_date,
                loader=loader,
                price_refill=price_refill,
                minute_refill=minute_refill,
                account_capital=account_capital,
                lot_size=lot_size,
            )
        )
    dates = []
    for pair in pair_payloads:
        dates.extend([pair["effective_decision_date"], pair["buy_date"]])
        if pair.get("sell_date"):
            dates.append(pair["sell_date"])
    summary = _build_forward_replay_summary(pair_payloads, discovery=discovery)
    price_summary = _price_refill_summary(price_refill)
    minute_summary = _minute_refill_summary(minute_refill)
    calendar_summary = _trade_calendar_refill_summary(trade_calendar_refill)
    notes = [
        "T0事实只用于生成候选和淘汰链；T+1事实只用于复核买入日表现；T+2事实只用于复核卖出窗口代理收益",
        "页面不展示T+1或T+2自己的最终动作，避免把后续判断误读成T0依据",
        "涨停、热榜、连板是证据，不直接等同于板块锚或执行对象",
        "回测汇总只用于诊断条件链和卖出窗口，不作精确绩效推断",
        "当前未发现股票级分时窗口价格时，T+1买入和T+2卖出都只按日线代理展示",
        minute_summary.get("basis", ""),
        price_summary.get("basis", ""),
        calendar_summary.get("basis", ""),
    ]
    return {
        "schema_version": "sector_forward_replay.v1",
        "sample_count": len(pair_payloads),
        "start_date": min(dates) if dates else "",
        "end_date": max(dates) if dates else "",
        "pairs": pair_payloads,
        "summary": summary,
        "discovery": discovery or {},
        "price_refill_summary": price_summary,
        "minute_refill_summary": minute_summary,
        "trade_calendar_refill_summary": calendar_summary,
        "small_account": {
            "schema_version": "small_account_context.v1",
            "account_capital": round(_safe_float(account_capital, 0), 2),
            "lot_size": _safe_int(lot_size, 100),
            "basis": "按用户1w账户和A股一手交易单位换算；50%仍是策略意图，实际落账看一手金额",
        },
        "notes": [note for note in notes if note],
    }


def _render_flow(pair):
    nodes = []
    if pair["requested_decision_date"] != pair["effective_decision_date"]:
        nodes.append(("请求日", pair["requested_decision_date"], "日报事实缺失"))
        nodes.append(("有效决策日", pair["effective_decision_date"], pair["coverage"]["coverage_note"]))
    else:
        nodes.append(("决策日", pair["effective_decision_date"], pair["coverage"]["coverage_note"]))
    for layer in pair.get("layers", []):
        nodes.append(
            (
                layer["title"],
                f'输入{layer["input_count"]} / 淘汰{layer["eliminated_count"]} / 剩{layer["survivor_count"]}',
                "、".join(item["stock_label"] for item in layer["survivors"][:3]) or "无",
            )
        )
    nodes.append(("T+1买入日复核", pair["buy_date"], f'只复核{pair["candidate_count"]}只决策日候选'))
    nodes.append(("T+2卖出窗口", pair.get("sell_date") or "待补", "三段窗口只做结果复核"))
    parts = []
    for index, (title, value, note) in enumerate(nodes):
        if index:
            parts.append('<div class="flow-arrow">→</div>')
        parts.append(
            '<div class="flow-node">'
            f"<span>{_html(title)}</span>"
            f"<strong>{_html(value)}</strong>"
            f"<p>{_html(note)}</p>"
            "</div>"
        )
    return '<div class="flow-strip">' + "\n".join(parts) + "</div>"


def _render_layer_details(pair):
    sections = []
    for layer in pair.get("layers", []):
        eliminated = "".join(
            f"<tr><td>{_html(row['stock_label'])}</td><td>{_html(row['reason'])}</td></tr>"
            for row in layer.get("eliminated", [])
        ) or '<tr><td colspan="2">无</td></tr>'
        survivors = "".join(
            f"<tr><td>{_html(row['stock_label'])}</td><td>{_html(row['reason'])}</td></tr>"
            for row in layer.get("survivors", [])
        ) or '<tr><td colspan="2">无</td></tr>'
        input_labels = "、".join(label for label in layer.get("input_labels", []) if label) or "无"
        sections.append(
            f"""
            <details class="layer-details">
              <summary>
                <strong>{_html(layer['title'])}</strong>
                <span>输入{layer['input_count']} / 淘汰{layer['eliminated_count']} / 剩{layer['survivor_count']}</span>
              </summary>
              <p class="input-line"><strong>本层输入：</strong>{_html(input_labels)}</p>
              <div class="split-tables">
                <div>
                  <h4>淘汰</h4>
                  <div class="table-scroll"><table><thead><tr><th>股票</th><th>原因</th></tr></thead><tbody>{eliminated}</tbody></table></div>
                </div>
                <div>
                  <h4>剩余</h4>
                  <div class="table-scroll"><table><thead><tr><th>股票</th><th>原因</th></tr></thead><tbody>{survivors}</tbody></table></div>
                </div>
              </div>
            </details>
            """
        )
    return "\n".join(sections)


def _render_evaluation_table(pair):
    rows = []
    for item in pair.get("evaluations", []):
        rows.append(
            "<tr>"
            f"<td>{_html(item['stock_label'])}</td>"
            f"<td>{_html(item['decision_status'])}</td>"
            f"<td>{_html(item['decision_reason'])}</td>"
            f"<td>{_html(item['target_outcome'])}</td>"
            f"<td>{_html('；'.join(item['target_facts']))}</td>"
            "</tr>"
        )
    body = "\n".join(rows) or '<tr><td colspan="5">无候选</td></tr>'
    return f"""
	      <details class="evaluation-block">
        <summary><strong>决策日候选的T+1买入日逐股复核</strong><span>{pair['candidate_count']} 只</span></summary>
        <div class="table-scroll tall">
          <table>
            <thead><tr><th>决策日候选</th><th>决策日状态</th><th>决策日原因</th><th>T+1结论</th><th>T+1证据</th></tr></thead>
            <tbody>{body}</tbody>
          </table>
        </div>
      </details>
    """


def _render_exit_windows(review):
    rows = []
    for item in review.get("windows") or []:
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('window'))}</td>"
            f"<td>{_html(item.get('proxy_label'))}</td>"
            f"<td>{_html(_fmt_pct(item.get('return_pct')) if item.get('return_pct') is not None else '待补')}</td>"
            f"<td>{_html(item.get('entry_price') if item.get('entry_price') is not None else '待补')}</td>"
            f"<td>{_html(item.get('exit_price') if item.get('exit_price') is not None else '待补')}</td>"
            f"<td>{_html(item.get('basis'))}</td>"
            "</tr>"
        )
    return rows


def _render_trade_window_matrix_rows(review):
    rows = []
    for item in review.get("window_matrix") or []:
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('buy_window'))}</td>"
            f"<td>{_html(item.get('buy_proxy_label'))}</td>"
            f"<td>{_html(item.get('sell_window'))}</td>"
            f"<td>{_html(item.get('sell_proxy_label'))}</td>"
            f"<td>{_html(_fmt_pct(item.get('return_pct')) if item.get('return_pct') is not None else '待补')}</td>"
            f"<td>{_html(item.get('entry_price') if item.get('entry_price') is not None else '待补')}</td>"
            f"<td>{_html(item.get('exit_price') if item.get('exit_price') is not None else '待补')}</td>"
            f"<td>{_html(item.get('basis'))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _render_price_path_rows(review):
    path = review.get("price_path_review") if isinstance(review.get("price_path_review"), dict) else {}
    rows = []
    for key in ("t0", "tplus1", "tplus2"):
        item = path.get(key) if isinstance(path.get(key), dict) else {}
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('role'))}</td>"
            f"<td>{_html(item.get('trade_date') or '待补')}</td>"
            f"<td>{_html(_fmt_pct(item.get('change_pct')) if item.get('change_pct') is not None else '待补')}</td>"
            f"<td>{_html(item.get('limit_state'))}</td>"
            f"<td>{_html(item.get('open') if item.get('open') is not None else '待补')}</td>"
            f"<td>{_html(item.get('high') if item.get('high') is not None else '待补')}</td>"
            f"<td>{_html(item.get('low') if item.get('low') is not None else '待补')}</td>"
            f"<td>{_html(item.get('close') if item.get('close') is not None else '待补')}</td>"
            f"<td>{_html(item.get('source'))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _render_buyability_rows(review):
    item = review.get("buyability_review") if isinstance(review.get("buyability_review"), dict) else {}
    return (
        "<tr>"
        f"<td>{_html(item.get('status') or '分时事实待补')}</td>"
        f"<td>{_html(item.get('reason') or '缺少T+1分时事实')}</td>"
        f"<td>{_html(_fmt_pct(item.get('early_high_change_pct')) if item.get('early_high_change_pct') is not None else '待补')}</td>"
        f"<td>{_html(_fmt_pct(item.get('early_close_change_pct')) if item.get('early_close_change_pct') is not None else '待补')}</td>"
        f"<td>{_html(item.get('minute_count') if item.get('minute_count') is not None else 0)}</td>"
        f"<td>{_html(item.get('minute_source') or '待补')}</td>"
        "</tr>"
    )


def _render_pair_emotion_projection(pair):
    projection = pair.get("emotion_projection") if isinstance(pair.get("emotion_projection"), dict) else {}
    review = pair.get("emotion_review") if isinstance(pair.get("emotion_review"), dict) else {}
    market = projection.get("market") if isinstance(projection.get("market"), dict) else {}
    sector = projection.get("sector") if isinstance(projection.get("sector"), dict) else {}
    rows = [
        {
            "object": "市场",
            "current": _clean(((market.get("current") or {}).get("label")), "待判读"),
            "tplus1_plan": _clean(((market.get("tplus1") or {}).get("label")), "待判读"),
            "tplus2_plan": _clean(((market.get("tplus2") or {}).get("label")), "待判读"),
            "tplus1_actual": _clean(((review.get("tplus1_market") or {}).get("label")), "待补事实"),
            "tplus2_actual": _clean(((review.get("tplus2_market") or {}).get("label")), "待补事实"),
            "calibration": _projection_label_match(
                _clean(((market.get("tplus2") or {}).get("label")), "待判读"),
                _clean(((review.get("tplus2_market") or {}).get("label")), "待补事实"),
                kind="market",
            ),
            "basis": _clean(((market.get("tplus2") or {}).get("basis")) or market.get("basis")),
        },
        {
            "object": "板块",
            "current": _clean(((sector.get("current") or {}).get("label")), "待判读"),
            "tplus1_plan": _clean(((sector.get("tplus1") or {}).get("label")), "待判读"),
            "tplus2_plan": _clean(((sector.get("tplus2") or {}).get("label")), "待判读"),
            "tplus1_actual": _clean(((review.get("tplus1_sector") or {}).get("label")), "待补事实"),
            "tplus2_actual": _clean(((review.get("tplus2_sector") or {}).get("label")), "待补事实"),
            "calibration": _projection_label_match(
                _clean(((sector.get("tplus2") or {}).get("label")), "待判读"),
                _clean(((review.get("tplus2_sector") or {}).get("label")), "待补事实"),
                kind="sector",
            ),
            "basis": _clean(((sector.get("tplus2") or {}).get("basis")) or sector.get("basis")),
        },
    ]
    body = "\n".join(
        "<tr>"
        f"<td>{_html(item['object'])}</td>"
        f"<td>{_html(item['current'])}</td>"
        f"<td>{_html(item['tplus1_plan'])}</td>"
        f"<td>{_html(item['tplus2_plan'])}</td>"
        f"<td>{_html(item['tplus1_actual'])}</td>"
        f"<td>{_html(item['tplus2_actual'])}</td>"
        f"<td>{_html(item['calibration'])}</td>"
        f"<td>{_html(item['basis'])}</td>"
        "</tr>"
        for item in rows
    )
    return f"""
	      <details class="projection-block">
        <summary><strong>T0推演T+2交易环境</strong><span>预案与实际分开看</span></summary>
        <div class="table-scroll">
          <table>
            <thead><tr><th>对象</th><th>T0状态</th><th>T+1预案</th><th>T+2预案</th><th>T+1实际</th><th>T+2实际</th><th>校准</th><th>依据</th></tr></thead>
            <tbody>{body}</tbody>
          </table>
        </div>
      </details>
    """


def _render_paper_strategy_table(pair):
    strategy = pair.get("paper_strategy") if isinstance(pair.get("paper_strategy"), dict) else {}
    stages = strategy.get("stages") if isinstance(strategy.get("stages"), list) else []
    stage_sections = []
    for stage in stages:
        survivors = "".join(
            f"<tr><td>{_html(row.get('label'))}</td><td>{_html(row.get('reason'))}</td></tr>"
            for row in stage.get("survivors", [])
            if isinstance(row, dict)
        ) or '<tr><td colspan="2">无</td></tr>'
        eliminated = "".join(
            f"<tr><td>{_html(row.get('label'))}</td><td>{_html(row.get('reason'))}</td></tr>"
            for row in stage.get("eliminated", [])
            if isinstance(row, dict)
        ) or '<tr><td colspan="2">无</td></tr>'
        stage_sections.append(
            f"""
            <details class="layer-details">
              <summary>
                <strong>{_html(stage.get('title'))}</strong>
                <span>输入{stage.get('input_count', 0)} / 淘汰{stage.get('eliminated_count', 0)} / 剩{stage.get('survivor_count', 0)}</span>
              </summary>
              <div class="split-tables">
                <div>
                  <h4>淘汰</h4>
                  <div class="table-scroll"><table><thead><tr><th>对象</th><th>原因</th></tr></thead><tbody>{eliminated}</tbody></table></div>
                </div>
                <div>
                  <h4>剩余</h4>
                  <div class="table-scroll"><table><thead><tr><th>对象</th><th>原因</th></tr></thead><tbody>{survivors}</tbody></table></div>
                </div>
              </div>
            </details>
            """
        )
    rows = []
    exit_rows = []
    path_rows = []
    buyability_rows = []
    for item in strategy.get("target_evaluations", []) if isinstance(strategy.get("target_evaluations"), list) else []:
        change_pct = item.get("target_change_pct")
        change_text = _fmt_pct(change_pct) if change_pct is not None else "无"
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('stock_label'))}</td>"
            f"<td>{_html(item.get('decision_reason'))}</td>"
            f"<td>{_html(item.get('paper_outcome_label'))}</td>"
            f"<td>{_html(change_text)}</td>"
            f"<td>{_html(item.get('target_outcome'))}</td>"
            f"<td>{_html('；'.join(item.get('target_facts') or []))}</td>"
            "</tr>"
            )
        review = item.get("tplus2_exit_review") if isinstance(item.get("tplus2_exit_review"), dict) else {}
        if review:
            path_rows.append(
                "<tr class=\"matrix-stock-row\">"
                f"<td colspan=\"9\"><strong>{_html(item.get('stock_label'))}</strong></td>"
                "</tr>"
                + _render_price_path_rows(review)
            )
            buyability_rows.append(
                "<tr class=\"matrix-stock-row\">"
                f"<td colspan=\"6\"><strong>{_html(item.get('stock_label'))}</strong>："
                f"{_html(review.get('buy_date'))}</td>"
                "</tr>"
                + _render_buyability_rows(review)
            )
        for window in review.get("windows") or []:
            exit_rows.append(
                "<tr>"
                f"<td>{_html(item.get('stock_label'))}</td>"
                f"<td>{_html(review.get('buy_date'))}</td>"
                f"<td>{_html(review.get('sell_date') or '待补')}</td>"
                f"<td>{_html(window.get('window'))}</td>"
                f"<td>{_html(window.get('proxy_label'))}</td>"
                f"<td>{_html(_fmt_pct(window.get('return_pct')) if window.get('return_pct') is not None else '待补')}</td>"
                f"<td>{_html(window.get('basis'))}</td>"
                "</tr>"
            )
    target_rows = "\n".join(rows) or '<tr><td colspan="6">无纸面候选</td></tr>'
    exit_window_rows = "\n".join(exit_rows) or '<tr><td colspan="7">无可计算T+2卖出窗口</td></tr>'
    price_path_rows = "\n".join(path_rows) or '<tr><td colspan="9">无价格路径事实</td></tr>'
    buyability_table_rows = "\n".join(buyability_rows) or '<tr><td colspan="6">无真实可买性事实</td></tr>'
    matrix_rows = []
    for item in strategy.get("target_evaluations", []) if isinstance(strategy.get("target_evaluations"), list) else []:
        review = item.get("tplus2_exit_review") if isinstance(item.get("tplus2_exit_review"), dict) else {}
        body = _render_trade_window_matrix_rows(review)
        if not body:
            continue
        matrix_rows.append(
            "<tr class=\"matrix-stock-row\">"
            f"<td colspan=\"8\"><strong>{_html(item.get('stock_label'))}</strong>："
            f"{_html(review.get('buy_date'))} → {_html(review.get('sell_date') or '待补')}</td>"
            "</tr>"
            + body
        )
    trade_matrix_rows = "\n".join(matrix_rows) or '<tr><td colspan="8">无可计算买卖窗口组合</td></tr>'
    target_summary = strategy.get("target_summary") if isinstance(strategy.get("target_summary"), dict) else {}
    return f"""
	      <details class="paper-block">
        <summary><strong>新版纸面策略：板块资金载体跟随</strong><span>{_html(strategy.get('action_label'))}：{_html(target_summary.get('primary_stock') or '无主样本')}</span></summary>
        <div class="paper-summary">
          <div><dt>纸面动作</dt><dd>{_html(strategy.get('action_label'))}</dd></div>
          <div><dt>动作理由</dt><dd>{_html(strategy.get('action_reason'))}</dd></div>
          <div><dt>T+1主样本复核</dt><dd>{_html(target_summary.get('primary_outcome_label'))}</dd></div>
          <div><dt>纸面候选</dt><dd>{len(strategy.get('paper_candidates') or [])}只</dd></div>
          <div><dt>交易时序</dt><dd>T0复盘，T+1买入，T+2卖出</dd></div>
          <div><dt>收益口径</dt><dd>T+1三段买入代理；T+2三段卖出代理</dd></div>
        </div>
        {''.join(stage_sections)}
	        <details class="layer-details">
          <summary><strong>纸面候选 T+1 买入复核</strong><span>T+1只验收，不生成候选</span></summary>
          <div class="table-scroll tall">
            <table>
              <thead><tr><th>纸面候选</th><th>T0理由</th><th>纸面复核</th><th>T+1涨幅</th><th>T+1结论</th><th>T+1证据</th></tr></thead>
              <tbody>{target_rows}</tbody>
            </table>
          </div>
        </details>
	        <details class="layer-details">
          <summary><strong>T0/T+1/T+2价格路径</strong><span>标注涨幅和涨停/跌停状态</span></summary>
          <div class="table-scroll tall">
            <table>
              <thead><tr><th>日期角色</th><th>日期</th><th>涨幅</th><th>涨停/跌停状态</th><th>开盘</th><th>最高</th><th>最低</th><th>收盘</th><th>来源</th></tr></thead>
              <tbody>{price_path_rows}</tbody>
            </table>
          </div>
        </details>
	        <details class="layer-details">
          <summary><strong>真实可买性复核</strong><span>分时事实决定纸面机会是否可执行</span></summary>
          <div class="table-scroll">
            <table>
              <thead><tr><th>结论</th><th>理由</th><th>09:35前最高涨幅</th><th>09:35收盘涨幅</th><th>分时条数</th><th>来源</th></tr></thead>
              <tbody>{buyability_table_rows}</tbody>
            </table>
          </div>
        </details>
	        <details class="layer-details">
          <summary><strong>T+1买入 x T+2卖出窗口矩阵</strong><span>日线代理，不伪装分时成交</span></summary>
          <div class="table-scroll tall">
            <table>
              <thead><tr><th>T+1买入窗口</th><th>买入价格代理</th><th>T+2卖出窗口</th><th>卖出价格代理</th><th>收益</th><th>买入价</th><th>卖出价</th><th>依据</th></tr></thead>
              <tbody>{trade_matrix_rows}</tbody>
            </table>
          </div>
        </details>
	        <details class="layer-details">
          <summary><strong>T+2三段卖出窗口复核</strong><span>日线代理，不伪装分时成交</span></summary>
          <div class="table-scroll tall">
            <table>
              <thead><tr><th>纸面候选</th><th>T+1买入日</th><th>T+2卖出日</th><th>卖出窗口</th><th>价格代理</th><th>收益</th><th>依据</th></tr></thead>
              <tbody>{exit_window_rows}</tbody>
            </table>
          </div>
        </details>
      </details>
    """


def _render_distribution_rows(mapping, dates_mapping=None):
    rows = []
    dates_mapping = dates_mapping if isinstance(dates_mapping, dict) else {}
    for key, count in (mapping or {}).items():
        dates = dates_mapping.get(key) or []
        rows.append(
            "<tr>"
            f"<td>{_html(key)}</td>"
            f"<td>{_html(count)}</td>"
            f"<td>{_html('、'.join(dates) or '无')}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="3">无</td></tr>'


def _render_mismatch_rows(summary):
    rows = []
    for sample in (summary.get("mismatch_samples") or [])[:30]:
        item_texts = []
        for item in sample.get("items") or []:
            facts = "；".join(item.get("target_facts") or [])
            item_texts.append(f"{_clean(item.get('stock_label'))}: {_clean(item.get('target_outcome'))}；{facts}")
        rows.append(
            "<tr>"
            f"<td>{_html(sample.get('decision_date'))} → {_html(sample.get('buy_date'))} → {_html(sample.get('sell_date') or '待补')}</td>"
            f"<td>{_html(sample.get('diagnosis'))}</td>"
            f"<td>{_html(' | '.join(item_texts))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="3">暂无</td></tr>'


def _render_paper_review_contrast_rows(summary):
    rows = []
    for sample in (summary.get("paper_review_contrast_samples") or [])[:30]:
        legacy = sample.get("legacy_action") if isinstance(sample.get("legacy_action"), dict) else {}
        review_object = sample.get("paper_review_object") if isinstance(sample.get("paper_review_object"), dict) else {}
        rows.append(
            "<tr>"
            f"<td>{_html(sample.get('decision_date'))}</td>"
            f"<td>{_html(legacy.get('label'))} / {_html(legacy.get('stock_label'))}</td>"
            f"<td>{_html(review_object.get('label'))} / {_html(review_object.get('stock_label'))}</td>"
            f"<td>{_html(sample.get('resolution'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="4">暂无</td></tr>'


def _render_paper_hit_rows(summary):
    rows = []
    for sample in (summary.get("paper_hit_samples") or [])[:40]:
        combo = ""
        if sample.get("best_buy_window") or sample.get("best_combo_sell_window"):
            combo = f"{_clean(sample.get('best_buy_window'))}代理 / {_clean(sample.get('best_combo_sell_window'))}代理"
        else:
            combo = _clean(sample.get("best_sell_window"), "待补")
        combo_return = sample.get("best_combo_return_pct")
        if combo_return is None:
            combo_return = sample.get("best_return_pct")
        rows.append(
            "<tr>"
            f"<td>{_html(sample.get('decision_date'))} → {_html(sample.get('buy_date'))} → {_html(sample.get('sell_date') or '待补')}</td>"
            f"<td>{_html(sample.get('paper_action'))}</td>"
            f"<td>{_html(sample.get('primary_stock'))}</td>"
            f"<td>{_html(sample.get('primary_outcome'))}</td>"
            f"<td>{_html(combo)}</td>"
            f"<td>{_html(_fmt_pct(combo_return) if combo_return is not None else '待补')}</td>"
            f"<td>{_html(sample.get('action_reason'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="7">暂无</td></tr>'


def _sample_text(sample):
    if not isinstance(sample, dict) or not sample:
        return "无"
    return (
        f"{_clean(sample.get('decision_date'))} "
        f"{_clean(sample.get('stock'))} "
        f"{_fmt_pct(sample.get('return_pct'))}"
    )


def _render_exit_window_summary_rows(summary):
    exit_summary = summary.get("exit_window_summary") if isinstance(summary.get("exit_window_summary"), dict) else {}
    rows = []
    for item in exit_summary.get("windows") or []:
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('window'))}</td>"
            f"<td>{_html(item.get('proxy_label'))}</td>"
            f"<td>{_html(item.get('sample_count'))}</td>"
            f"<td>{_html(_fmt_pct(item.get('average_return_pct')) if item.get('average_return_pct') is not None else '待补')}</td>"
            f"<td>{_html(item.get('positive_count'))}</td>"
            f"<td>{_html(_sample_text(item.get('best_sample')))}</td>"
            f"<td>{_html(_sample_text(item.get('worst_sample')))}</td>"
            f"<td>{_html(item.get('basis'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="8">暂无可计算窗口</td></tr>'


def _buyability_metrics_text(item):
    if not isinstance(item, dict) or not item:
        return "待补"
    parts = []
    if item.get("average_buy_window_entry_change_pct") is not None:
        parts.append(f"买入点均涨幅{_fmt_signed_pct(item.get('average_buy_window_entry_change_pct'))}")
    if item.get("average_buy_day_change_pct") is not None:
        parts.append(f"T+1日均涨幅{_fmt_signed_pct(item.get('average_buy_day_change_pct'))}")
    parts.append(f"收盘接近涨停{item.get('near_limit_buy_count', 0)}/{item.get('sample_count', 0)}")
    note = _clean(item.get("buyability_note"))
    if note:
        parts.append(note)
    return "；".join(parts)


def _render_trade_window_matrix_summary_rows(summary):
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    rows = []
    for item in matrix_summary.get("rows") or []:
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('buy_window'))}</td>"
            f"<td>{_html(item.get('buy_proxy_label'))}</td>"
            f"<td>{_html(item.get('sell_window'))}</td>"
            f"<td>{_html(item.get('sell_proxy_label'))}</td>"
            f"<td>{_html(item.get('sample_count'))}</td>"
            f"<td>{_html(_fmt_pct(item.get('average_return_pct')) if item.get('average_return_pct') is not None else '待补')}</td>"
            f"<td>{_html(item.get('positive_count'))}</td>"
            f"<td>{_html(_buyability_metrics_text(item))}</td>"
            f"<td>{_html(_sample_text(item.get('best_sample')))}</td>"
            f"<td>{_html(_sample_text(item.get('worst_sample')))}</td>"
            f"<td>{_html(item.get('basis'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="11">暂无可计算买卖窗口组合</td></tr>'


def _trade_window_matrix_summary_grid(summary):
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    rows = matrix_summary.get("rows") if isinstance(matrix_summary.get("rows"), list) else []
    by_key = {
        (row.get("buy_window_id"), row.get("sell_window_id")): row
        for row in rows if isinstance(row, dict)
    }
    best_combo = matrix_summary.get("best_combo") if isinstance(matrix_summary.get("best_combo"), dict) else {}
    best_id = f"{best_combo.get('buy_window_id')}__{best_combo.get('sell_window_id')}" if best_combo else ""
    body_rows = []
    for buy_window in BUY_WINDOWS:
        cells = [
            f"<th>{_html(buy_window['window'])}<br><small>{_html(buy_window['proxy_label'])}</small></th>"
        ]
        for sell_window in SELL_WINDOWS:
            row = by_key.get((buy_window["id"], sell_window["id"])) or {}
            if row.get("average_return_pct") is None:
                cell = "待补"
            else:
                cell = (
                    f"{_fmt_signed_pct(row.get('average_return_pct'))}"
                    f"<br><small>正收益 {row.get('positive_count', 0)}/{row.get('sample_count', 0)}</small>"
                    f"<br><small>买点均涨幅 {_fmt_signed_pct(row.get('average_buy_window_entry_change_pct')) if row.get('average_buy_window_entry_change_pct') is not None else '待补'}</small>"
                    f"<br><small>收盘接近涨停 {row.get('near_limit_buy_count', 0)}/{row.get('sample_count', 0)}</small>"
                )
                if row.get("id") == best_id:
                    cell += "<br><small>较高组合</small>"
            cells.append(f"<td>{cell}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    header = "".join(
        f"<th>{_html(window['window'])}<br><small>{_html(window['proxy_label'])}</small></th>"
        for window in SELL_WINDOWS
    )
    return (
        "<table class=\"matrix-table\">"
        f"<thead><tr><th>T+1买入 \\ T+2卖出</th>{header}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def _render_trade_return_rank_rows(summary, key):
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    samples = matrix_summary.get(key) if isinstance(matrix_summary.get(key), list) else []
    rows = []
    for index, item in enumerate(samples[:10], 1):
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{_html(item.get('decision_date'))} → {_html(item.get('buy_date'))} → {_html(item.get('sell_date') or '待补')}</td>"
            f"<td>{_html(item.get('stock'))}</td>"
            f"<td>{_html(item.get('buy_window'))}<br><small>{_html(item.get('buy_proxy_label'))}</small></td>"
            f"<td>{_html(item.get('sell_window'))}<br><small>{_html(item.get('sell_proxy_label'))}</small></td>"
            f"<td>{_html(_fmt_signed_pct(item.get('return_pct')))}</td>"
            f"<td>{_html(item.get('entry_price') if item.get('entry_price') is not None else '待补')}</td>"
            f"<td>{_html(item.get('exit_price') if item.get('exit_price') is not None else '待补')}</td>"
            f"<td>{_html(item.get('basis'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="9">暂无可计算单笔样本</td></tr>'


def _render_equity_curve_summary_rows(summary):
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    rows = []
    for item in matrix_summary.get("rows") or []:
        curve = item.get("equity_curve") if isinstance(item.get("equity_curve"), dict) else {}
        max_drawdown_sample = curve.get("max_drawdown_sample") if isinstance(curve.get("max_drawdown_sample"), dict) else {}
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('buy_window'))}</td>"
            f"<td>{_html(item.get('sell_window'))}</td>"
            f"<td>{_html(curve.get('sample_count', 0))}</td>"
            f"<td>{_html(curve.get('final_net_value') if curve.get('final_net_value') is not None else '待补')}</td>"
            f"<td>{_html(_fmt_signed_pct(curve.get('cumulative_return_pct')) if curve.get('cumulative_return_pct') is not None else '待补')}</td>"
            f"<td>{_html(_fmt_signed_pct(curve.get('max_drawdown_pct')) if curve.get('max_drawdown_pct') is not None else '待补')}</td>"
            f"<td>{_html(_sample_text(max_drawdown_sample))}</td>"
            f"<td>{_html(curve.get('basis') or item.get('basis'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="8">暂无可计算收益曲线</td></tr>'


def _render_index_benchmark_rows(summary):
    benchmark = summary.get("index_benchmark_summary") if isinstance(summary.get("index_benchmark_summary"), dict) else {}
    rows = []
    for item in benchmark.get("rows") or []:
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('label'))}</td>"
            f"<td>{_html(item.get('start_date'))}</td>"
            f"<td>{_html(item.get('start_point') if item.get('start_point') is not None else '待补')}</td>"
            f"<td>{_html(item.get('end_date'))}</td>"
            f"<td>{_html(item.get('end_point') if item.get('end_point') is not None else '待补')}</td>"
            f"<td>{_html(_fmt_signed_pct(item.get('cumulative_return_pct')) if item.get('cumulative_return_pct') is not None else '待补')}</td>"
            f"<td>{_html(item.get('coverage_note') or '待补')}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="7">暂无可计算指数对照</td></tr>'


def _render_window_performance_comparison_rows(summary):
    comparison = summary.get("window_performance_comparison") if isinstance(summary.get("window_performance_comparison"), dict) else {}
    rows = []
    for item in comparison.get("rows") or []:
        sample_text = f"{item.get('sample_count', 0)}/{item.get('all_sample_count', item.get('sample_count', 0))}"
        benchmark_cells = []
        for spec in INDEX_BENCHMARK_SPECS:
            value = item.get(f"excess_{spec['label']}")
            benchmark_cells.append(
                f"<td>{_html(_fmt_signed_point(value) if value is not None else '待补')}</td>"
            )
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('label'))}</td>"
            f"<td>{_html(sample_text)}</td>"
            f"<td>{_html(item.get('period_count') if item.get('period_count') is not None else '待补')}</td>"
            f"<td>{_html(_fmt_signed_pct(item.get('average_return_pct')) if item.get('average_return_pct') is not None else '待补')}</td>"
            f"<td>{_html(item.get('final_net_value') if item.get('final_net_value') is not None else '待补')}</td>"
            f"<td>{_html(_fmt_signed_pct(item.get('monthly_return_pct')) if item.get('monthly_return_pct') is not None else '待补')}</td>"
            f"<td>{_html(_fmt_signed_pct(item.get('cumulative_return_pct')) if item.get('cumulative_return_pct') is not None else '待补')}</td>"
            f"<td>{_html(_annualized_reference_text(item))}</td>"
            f"<td>{_html(_fmt_signed_pct(item.get('max_drawdown_pct')) if item.get('max_drawdown_pct') is not None else '待补')}</td>"
            f"{''.join(benchmark_cells)}"
            f"<td>{_html(item.get('exclusion'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="16">暂无可计算窗口折算收益</td></tr>'


def _chart_number(value):
    number = _safe_float(value, None)
    return round(number, 2) if number is not None else None


def _chart_net_value(value):
    number = _safe_float(value, None)
    return round(number, 4) if number is not None else None


def _short_window_performance_label(label):
    text = _clean(label)
    text = text.replace("09:30-09:35", "9:30")
    text = text.replace("09:50-10:10", "9:50")
    text = text.replace("14:30-14:55", "14:30")
    text = text.replace("（原始）", "")
    text = text.replace("（剔除开盘接近涨停）", "\n剔开盘接近涨停")
    text = text.replace("（剔除收盘接近涨停）", "\n剔收盘接近涨停")
    text = text.replace(" / ", "\n")
    return text


def _adjust_metric_row_with_tplus1_actual(metric_row, payload):
    metric_row = dict(metric_row) if isinstance(metric_row, dict) else {}
    if not metric_row:
        return {}
    if _safe_int(metric_row.get("tplus1_actual_count"), 0) > 0:
        return metric_row
    items = _pending_tplus1_actual_items(payload)
    net_value = _safe_float(metric_row.get("final_net_value"), None)
    period_count = _safe_int(metric_row.get("period_count"), 0)
    if net_value is None or net_value <= 0 or period_count <= 0 or not items:
        return metric_row
    adjusted_net_value = net_value
    actual_return_sum = 0.0
    valid_count = 0
    for item in items:
        value = _safe_float(item.get("open_to_close_return_pct"), None)
        if value is None:
            continue
        adjusted_net_value *= 1 + value / 100
        actual_return_sum += value
        valid_count += 1
    if not valid_count:
        return metric_row
    adjusted = dict(metric_row)
    original_sample_count = _safe_int(metric_row.get("sample_count"), 0)
    original_average = _safe_float(metric_row.get("average_return_pct"), None)
    adjusted["sample_count"] = original_sample_count + valid_count
    adjusted["all_sample_count"] = _safe_int(metric_row.get("all_sample_count"), metric_row.get("sample_count", 0)) + valid_count
    adjusted["tplus2_settled_sample_count"] = original_sample_count
    adjusted["tplus2_settled_final_net_value"] = metric_row.get("final_net_value")
    adjusted["tplus2_settled_cumulative_return_pct"] = metric_row.get("cumulative_return_pct")
    if original_average is not None and adjusted["sample_count"]:
        adjusted["average_return_pct"] = round(
            (original_average * original_sample_count + actual_return_sum) / adjusted["sample_count"],
            2,
        )
    adjusted["final_net_value"] = round(adjusted_net_value, 4)
    adjusted["cumulative_return_pct"] = round((adjusted_net_value - 1) * 100, 2)
    adjusted["monthly_return_pct"] = round(_annualized_pct_from_net_value(adjusted_net_value, period_count, 21), 2)
    adjusted["annualized_return_pct"] = round(_annualized_pct_from_net_value(adjusted_net_value, period_count, 252), 2)
    adjusted["tplus1_actual_count"] = valid_count
    adjusted["basis"] = (
        "完整T+2已结算样本加上T+1已发生日线表现；"
        "T+1部分只代表买入日浮动表现，不替代完整T+2卖出窗口收益。"
    )
    return adjusted


def _refresh_metric_row_index_excess(metric_row, summary):
    metric_row = dict(metric_row) if isinstance(metric_row, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    benchmark_summary = (
        summary.get("index_benchmark_summary")
        if isinstance(summary.get("index_benchmark_summary"), dict)
        else {}
    )
    benchmark_rows = benchmark_summary.get("rows") if isinstance(benchmark_summary.get("rows"), list) else []
    benchmark_returns = {
        item.get("label"): _safe_float(item.get("cumulative_return_pct"), None)
        for item in benchmark_rows
        if isinstance(item, dict)
    }
    cumulative_return = _safe_float(metric_row.get("cumulative_return_pct"), None)
    for spec in INDEX_BENCHMARK_SPECS:
        label = spec["label"]
        benchmark_return = benchmark_returns.get(label)
        metric_row[f"excess_{label}"] = (
            round(cumulative_return - benchmark_return, 2)
            if cumulative_return is not None and benchmark_return is not None
            else None
        )
    return metric_row


def _same_window(row, metric_row):
    return (
        isinstance(row, dict)
        and isinstance(metric_row, dict)
        and row.get("buy_window_id") == metric_row.get("buy_window_id")
        and row.get("sell_window_id") == metric_row.get("sell_window_id")
    )


def _adjust_equity_curve_with_tplus1_actual(curve, payload):
    curve = dict(curve) if isinstance(curve, dict) else {}
    if not curve or _safe_int(curve.get("tplus1_actual_count"), 0) > 0:
        return curve
    items = _pending_tplus1_actual_items(payload)
    if not items:
        return curve
    points = [dict(point) for point in curve.get("curve_points") or [] if isinstance(point, dict)]
    if not points:
        return curve
    equity = _safe_float(curve.get("final_net_value"), None)
    if equity is None or equity <= 0:
        equity = _safe_float(points[-1].get("net_value"), None)
    if equity is None or equity <= 0:
        return curve
    point_net_values = [
        _safe_float(point.get("net_value"), None)
        for point in points
        if _safe_float(point.get("net_value"), None) is not None
    ]
    peak = max(point_net_values + [equity]) if point_net_values else equity
    max_drawdown_pct = _safe_float(curve.get("max_drawdown_pct"), 0.0) or 0.0
    max_drawdown_sample = curve.get("max_drawdown_sample") if isinstance(curve.get("max_drawdown_sample"), dict) else {}
    valid_count = 0
    for item in items:
        value = _safe_float(item.get("open_to_close_return_pct"), None)
        if value is None:
            continue
        equity *= 1 + value / 100
        if equity > peak:
            peak = equity
        drawdown_pct = ((equity / peak) - 1) * 100 if peak else 0.0
        point = {
            "decision_date": item.get("decision_date"),
            "buy_date": item.get("buy_date"),
            "sell_date": item.get("trade_date") or item.get("buy_date"),
            "stock": item.get("stock"),
            "buy_window": "09:30-09:35",
            "sell_window": "14:30-14:55",
            "return_pct": round(value, 2),
            "net_value": round(equity, 4),
            "cumulative_return_pct": round((equity - 1) * 100, 2),
            "drawdown_pct": round(drawdown_pct, 2),
            "tplus1_actual": True,
        }
        points.append(point)
        if drawdown_pct < max_drawdown_pct:
            max_drawdown_pct = drawdown_pct
            max_drawdown_sample = point
        valid_count += 1
    if not valid_count:
        return curve
    adjusted = dict(curve)
    adjusted["sample_count"] = _safe_int(curve.get("sample_count"), len(points) - valid_count) + valid_count
    adjusted["final_net_value"] = round(equity, 4)
    adjusted["cumulative_return_pct"] = round((equity - 1) * 100, 2)
    adjusted["max_drawdown_pct"] = round(max_drawdown_pct, 2)
    adjusted["max_drawdown_sample"] = max_drawdown_sample
    adjusted["curve_points"] = points
    adjusted["tplus1_actual_count"] = valid_count
    adjusted["basis"] = (
        f"{_clean(curve.get('basis'))}；末端并入T+1已发生日线表现，未把未来T+2当作已发生事实"
    )
    return adjusted


def _apply_tplus1_actual_to_replay_payload(payload):
    payload = _ensure_tplus1_actual_reviews(payload)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if not summary:
        return payload
    comparison = (
        summary.get("window_performance_comparison")
        if isinstance(summary.get("window_performance_comparison"), dict)
        else {}
    )
    rows = comparison.get("rows") if isinstance(comparison.get("rows"), list) else []
    metric_row = _replay_metric_row(summary)
    if metric_row and rows:
        adjusted_rows = []
        for row in rows:
            if _same_window(row, metric_row):
                row = _refresh_metric_row_index_excess(
                    _adjust_metric_row_with_tplus1_actual(row, payload),
                    summary,
                )
            adjusted_rows.append(row)
        comparison["rows"] = adjusted_rows
    matrix_summary = (
        summary.get("trade_window_matrix_summary")
        if isinstance(summary.get("trade_window_matrix_summary"), dict)
        else {}
    )
    best_combo = matrix_summary.get("best_combo") if isinstance(matrix_summary.get("best_combo"), dict) else {}
    if best_combo:
        for item in matrix_summary.get("rows") or []:
            if (
                isinstance(item, dict)
                and item.get("buy_window_id") == best_combo.get("buy_window_id")
                and item.get("sell_window_id") == best_combo.get("sell_window_id")
            ):
                item["equity_curve"] = _adjust_equity_curve_with_tplus1_actual(item.get("equity_curve"), payload)
        if isinstance(matrix_summary.get("recommended_equity_curve"), dict):
            matrix_summary["recommended_equity_curve"] = _adjust_equity_curve_with_tplus1_actual(
                matrix_summary.get("recommended_equity_curve"),
                payload,
            )
    return payload


def _window_performance_chart_payload(summary, payload=None):
    payload = payload if isinstance(payload, dict) else {}
    comparison = summary.get("window_performance_comparison") if isinstance(summary.get("window_performance_comparison"), dict) else {}
    metric_row = _refresh_metric_row_index_excess(
        _adjust_metric_row_with_tplus1_actual(_replay_metric_row(summary), payload),
        summary,
    )
    rows = []
    for item in comparison.get("rows") or []:
        if not isinstance(item, dict):
            continue
        item_for_chart = item
        if metric_row and _same_window(item, metric_row):
            item_for_chart = _refresh_metric_row_index_excess(
                _adjust_metric_row_with_tplus1_actual(item, payload),
                summary,
            )
        label = _clean(item.get("label"))
        if not label:
            continue
        sample_count = item_for_chart.get("sample_count", 0)
        all_sample_count = item_for_chart.get("all_sample_count", item.get("all_sample_count", sample_count))
        sample_text = f"{sample_count}/{all_sample_count}"
        if item_for_chart.get("tplus1_actual_count"):
            sample_text = f"{sample_text} 含T+1"
        rows.append(
            {
                "label": label,
                "short_label": _short_window_performance_label(label),
                "sample_text": sample_text,
                "period_count": item_for_chart.get("period_count"),
                "average_return_pct": _chart_number(item_for_chart.get("average_return_pct")),
                "monthly_return_pct": _chart_number(item_for_chart.get("monthly_return_pct")),
                "cumulative_return_pct": _chart_number(item_for_chart.get("cumulative_return_pct")),
                "max_drawdown_pct": _chart_number(item_for_chart.get("max_drawdown_pct")),
                **{
                    spec["chart_key"]: _chart_number(item_for_chart.get(f"excess_{spec['label']}"))
                    for spec in INDEX_BENCHMARK_SPECS
                },
                "exclusion": _clean(item_for_chart.get("exclusion")),
            }
        )
    benchmark_rows = {}
    benchmark_summary = summary.get("index_benchmark_summary") if isinstance(summary.get("index_benchmark_summary"), dict) else {}
    for item in benchmark_summary.get("rows") or []:
        if isinstance(item, dict):
            benchmark_rows[item.get("label")] = item
    benchmark_excess_items = []
    if metric_row:
        for spec in INDEX_BENCHMARK_SPECS:
            label = spec["label"]
            excess = _chart_number(metric_row.get(f"excess_{label}"))
            benchmark = benchmark_rows.get(label) if isinstance(benchmark_rows.get(label), dict) else {}
            benchmark_excess_items.append(
                {
                    "label": label,
                    "series_name": spec["series_name"],
                    "excess_pct": excess,
                    "index_return_pct": _chart_number(benchmark.get("cumulative_return_pct")),
                    "strategy_return_pct": _chart_number(metric_row.get("cumulative_return_pct")),
                    "coverage_note": _clean(benchmark.get("coverage_note")),
                }
            )
    return {
        "schema_version": "sector_window_performance_echarts.v1",
        "basis": _clean(comparison.get("basis")),
        "rows": rows,
        "benchmark_excess": {
            "strategy_label": _clean(metric_row.get("label")) if metric_row else "",
            "strategy_return_pct": _chart_number(metric_row.get("cumulative_return_pct")) if metric_row else None,
            "items": benchmark_excess_items,
        },
    }


def _matrix_chart_payload(summary):
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    rows = matrix_summary.get("rows") if isinstance(matrix_summary.get("rows"), list) else []
    best_combo = matrix_summary.get("best_combo") if isinstance(matrix_summary.get("best_combo"), dict) else {}
    buy_windows = [window["window"] for window in BUY_WINDOWS]
    sell_windows = [window["window"] for window in SELL_WINDOWS]
    buy_index_by_id = {window["id"]: index for index, window in enumerate(BUY_WINDOWS)}
    sell_index_by_id = {window["id"]: index for index, window in enumerate(SELL_WINDOWS)}
    cells = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        average_return = _chart_number(row.get("average_return_pct"))
        if average_return is None:
            continue
        buy_window_id = row.get("buy_window_id")
        sell_window_id = row.get("sell_window_id")
        cells.append(
            {
                "buy_window_id": buy_window_id,
                "buy_window": _clean(row.get("buy_window")),
                "buy_index": buy_index_by_id.get(buy_window_id),
                "sell_window_id": sell_window_id,
                "sell_window": _clean(row.get("sell_window")),
                "sell_index": sell_index_by_id.get(sell_window_id),
                "sample_count": _safe_int(row.get("sample_count"), 0),
                "positive_count": _safe_int(row.get("positive_count"), 0),
                "positive_text": f"{_safe_int(row.get('positive_count'), 0)}/{_safe_int(row.get('sample_count'), 0)}",
                "average_return_pct": average_return,
                "average_buy_window_entry_change_pct": _chart_number(row.get("average_buy_window_entry_change_pct")),
                "near_limit_buy_count": _safe_int(row.get("near_limit_buy_count"), 0),
                "is_best": (
                    buy_window_id == best_combo.get("buy_window_id")
                    and sell_window_id == best_combo.get("sell_window_id")
                ),
            }
        )
    values = [cell["average_return_pct"] for cell in cells if cell.get("average_return_pct") is not None]
    return {
        "buy_windows": buy_windows,
        "sell_windows": sell_windows,
        "cells": cells,
        "min_return_pct": min(values) if values else 0,
        "max_return_pct": max(values) if values else 0,
    }


def _equity_curve_chart_payload(summary):
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    curve = matrix_summary.get("recommended_equity_curve") if isinstance(matrix_summary.get("recommended_equity_curve"), dict) else {}
    best_combo = matrix_summary.get("best_combo") if isinstance(matrix_summary.get("best_combo"), dict) else {}
    points = []
    for point in curve.get("curve_points") or []:
        if not isinstance(point, dict):
            continue
        points.append(
            {
                "decision_date": _clean(point.get("decision_date")),
                "buy_date": _clean(point.get("buy_date")),
                "sell_date": _clean(point.get("sell_date")),
                "stock": _clean(point.get("stock")),
                "return_pct": _chart_number(point.get("return_pct")),
                "net_value": _chart_net_value(point.get("net_value")),
                "cumulative_return_pct": _chart_number(point.get("cumulative_return_pct")),
                "drawdown_pct": _chart_number(point.get("drawdown_pct")),
            }
        )
    return {
        "label": f"T+1 {best_combo.get('buy_window') or '待补'} / T+2 {best_combo.get('sell_window') or '待补'}",
        "points": points,
        "final_net_value": _chart_net_value(curve.get("final_net_value")),
        "cumulative_return_pct": _chart_number(curve.get("cumulative_return_pct")),
        "max_drawdown_pct": _chart_number(curve.get("max_drawdown_pct")),
        "basis": _clean(curve.get("basis")),
    }


def _first_number_from_text(value):
    match = re.search(r"[-+]?\d+(?:\.\d+)?", _clean(value).replace(",", ""))
    return _safe_float(match.group(0), None) if match else None


def _index_change_from_text(value):
    match = re.search(r"/\s*([+-]?\d+(?:\.\d+)?)%", _clean(value).replace(",", ""))
    return _safe_float(match.group(1), None) if match else None


def _breadth_counts_from_text(value):
    match = re.search(r"(\d+)\s*/\s*(\d+)", _clean(value).replace(",", ""))
    if not match:
        return None, None
    return _safe_int(match.group(1), None), _safe_int(match.group(2), None)


def _new_high_parts_from_text(value):
    match = re.search(r"(\d+)\s*/\s*([0-9.]+)%", _clean(value).replace(",", ""))
    if not match:
        return None, None
    return _safe_int(match.group(1), None), _safe_float(match.group(2), None)


def _market_breadth_chart_payload(payload):
    rows = []
    for pair in payload.get("pairs") or []:
        if not isinstance(pair, dict):
            continue
        context = _t0_market_context_from_pair(pair)
        up_count, down_count = _breadth_counts_from_text(context.get("T0涨跌家数"))
        new_high_count, new_high_pct = _new_high_parts_from_text(context.get("T0创新高全A占比"))
        rows.append(
            {
                "date": _clean(pair.get("effective_decision_date")),
                "up_count": up_count,
                "down_count": down_count,
                "breadth_ratio": round(up_count / down_count, 2) if up_count is not None and down_count else None,
                "new_high_count": new_high_count,
                "new_high_pct": _chart_number(new_high_pct),
                "shanghai_point": _chart_number(_first_number_from_text(context.get("T0上证指数"))),
                "all_a_point": _chart_number(_first_number_from_text(context.get("T0全A指数"))),
                "all_a_change_pct": _chart_number(_index_change_from_text(context.get("T0全A指数"))),
                "csi500_change_pct": _chart_number(_index_change_from_text(context.get("T0中证500"))),
                "chinext_change_pct": _chart_number(_index_change_from_text(context.get("T0创业板指"))),
            }
        )
    return {
        "rows": rows,
        "basis": "涨跌家数、全A涨跌幅、创新高占比只表示T0市场底色，用来解释当日环境，不替代买卖窗口结论",
    }


def _sample_distribution_chart_payload(payload):
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    curve_payload = _equity_curve_chart_payload(summary)
    points = [point for point in curve_payload.get("points") or [] if isinstance(point, dict)]
    settled_returns = [
        _safe_float(point.get("return_pct"), None)
        for point in points
        if _safe_float(point.get("return_pct"), None) is not None
    ]
    pair_count = _safe_int(payload.get("sample_count"), 0)
    if not settled_returns and pair_count <= 0:
        return {
            "outcomes": [],
            "return_buckets": [],
            "settled_count": 0,
            "pending_count": 0,
            "basis": "暂无可聚合的样本收益。",
        }
    positive_count = sum(1 for value in settled_returns if value > 0)
    negative_count = sum(1 for value in settled_returns if value < 0)
    flat_count = sum(1 for value in settled_returns if value == 0)
    pending_count = max(pair_count - len(settled_returns), 0)
    bucket_defs = [
        ("≤-5%", None, -5),
        ("-5%~0%", -5, 0),
        ("0%~5%", 0, 5),
        ("5%~10%", 5, 10),
        (">10%", 10, None),
    ]
    buckets = []
    for label, lower, upper in bucket_defs:
        count = 0
        for value in settled_returns:
            if lower is None and value <= upper:
                count += 1
            elif upper is None and value > lower:
                count += 1
            elif lower is not None and upper is not None and lower < value <= upper:
                count += 1
        buckets.append({"label": label, "count": count})
    return {
        "outcomes": [
            {"label": "正收益", "count": positive_count, "tone": "positive"},
            {"label": "负收益", "count": negative_count, "tone": "negative"},
            {"label": "持平", "count": flat_count, "tone": "flat"},
            {"label": "待补", "count": pending_count, "tone": "pending"},
        ],
        "return_buckets": buckets,
        "settled_count": len(settled_returns),
        "pending_count": pending_count,
        "basis": "按较高买卖窗口的已结算日线代理收益聚合，只看样本分布，不展示逐日操作。",
    }


def _replay_summary_chart_payload(payload):
    payload = _apply_tplus1_actual_to_replay_payload(payload)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    chart_payload = _window_performance_chart_payload(summary, payload)
    chart_payload["matrix"] = _matrix_chart_payload(summary)
    chart_payload["sample_distribution"] = _sample_distribution_chart_payload(payload)
    chart_payload["equity_curve"] = _equity_curve_chart_payload(summary)
    chart_payload["market_breadth"] = _market_breadth_chart_payload(payload)
    return chart_payload


def _best_matrix_row(summary):
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    best_combo = matrix_summary.get("best_combo") if isinstance(matrix_summary.get("best_combo"), dict) else {}
    rows = matrix_summary.get("rows") if isinstance(matrix_summary.get("rows"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("buy_window_id") == best_combo.get("buy_window_id") and row.get("sell_window_id") == best_combo.get("sell_window_id"):
            return row
    return {}


def _replay_metric_row(summary):
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    best_combo = matrix_summary.get("best_combo") if isinstance(matrix_summary.get("best_combo"), dict) else {}
    comparison = summary.get("window_performance_comparison") if isinstance(summary.get("window_performance_comparison"), dict) else {}
    rows = comparison.get("rows") if isinstance(comparison.get("rows"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if (
            row.get("buy_window_id") == best_combo.get("buy_window_id")
            and row.get("sell_window_id") == best_combo.get("sell_window_id")
            and row.get("exclusion") == "未剔除接近涨停买点"
        ):
            return row
    return next((row for row in rows if isinstance(row, dict)), {})


def _benchmark_excess_summary_text(metric_row):
    metric_row = metric_row if isinstance(metric_row, dict) else {}
    if not metric_row:
        return "待补"
    short_labels = {
        "上证指数": "上证",
        "创业板指": "创业板",
        "科创50": "科创50",
        "中证500": "中证500",
        "全A指数": "全A指数",
        "中证1000": "中证1000",
    }
    parts = []
    for spec in INDEX_BENCHMARK_SPECS:
        label = spec["label"]
        value = metric_row.get(f"excess_{label}")
        text = _fmt_signed_point(value) if value is not None else "待补"
        parts.append(f"{short_labels.get(label, label)} {text}")
    return "；".join(parts)


def _replay_market_signal_text(payload):
    rows = _market_breadth_chart_payload(payload).get("rows") or []
    breadth_rows = [
        row for row in rows
        if isinstance(row, dict) and row.get("up_count") is not None and row.get("down_count") is not None
    ]
    if not breadth_rows:
        return "待补"
    up_dominant = sum(1 for row in breadth_rows if row.get("up_count", 0) > row.get("down_count", 0))
    all_a_positive = sum(1 for row in rows if isinstance(row, dict) and _safe_float(row.get("all_a_change_pct"), None) is not None and row.get("all_a_change_pct") > 0)
    new_high_hot = sum(1 for row in rows if isinstance(row, dict) and _safe_float(row.get("new_high_pct"), None) is not None and row.get("new_high_pct") >= 5)
    return f"上涨占优{up_dominant}/{len(breadth_rows)}天；全A收红{all_a_positive}/{len(rows)}天；创新高偏热{new_high_hot}/{len(rows)}天"


def _latest_replay_pair_marker_text(payload):
    pairs = payload.get("pairs") if isinstance(payload, dict) and isinstance(payload.get("pairs"), list) else []
    if not pairs:
        return ""
    pair = pairs[-1] if isinstance(pairs[-1], dict) else {}
    decision_date = _clean(pair.get("effective_decision_date") or pair.get("decision_date"))
    if not decision_date:
        return ""
    buy_date = _clean(pair.get("buy_date"), "待补")
    sell_date = _clean(pair.get("sell_date"), "待补")
    final_action = pair.get("final_action") if isinstance(pair.get("final_action"), dict) else {}
    target_label = _action_stock_label(final_action)
    strategy = pair.get("paper_strategy") if isinstance(pair.get("paper_strategy"), dict) else {}
    if target_label == "无执行对象":
        marker = _paper_status_label(strategy) if strategy else _clean(final_action.get("label"), "明确不参与")
    else:
        marker = target_label
    return f"{decision_date} → {buy_date} → {sell_date}：{marker}"


def _replay_variant_scope_text(payload):
    variant = payload.get("variant") if isinstance(payload, dict) and isinstance(payload.get("variant"), dict) else {}
    parts = []
    label = _clean(variant.get("label"))
    basis = _clean(variant.get("basis"))
    latest_pair = _latest_replay_pair_marker_text(payload)
    if label:
        parts.append(label)
    if basis:
        parts.append(basis)
    if latest_pair:
        parts.append(f"末端样本 {latest_pair}")
    return "；".join(parts)


def _tplus1_actual_from_review(review):
    review = review if isinstance(review, dict) else {}
    actual = review.get("tplus1_actual_review")
    if isinstance(actual, dict) and actual.get("open_to_close_return_pct") is not None:
        return actual
    price_path = review.get("price_path_review") if isinstance(review.get("price_path_review"), dict) else {}
    tplus1 = price_path.get("tplus1") if isinstance(price_path.get("tplus1"), dict) else {}
    if not tplus1:
        return {}
    return _build_tplus1_actual_review(
        _clean((review.get("stock") or {}).get("code")) if isinstance(review.get("stock"), dict) else "",
        _clean(tplus1.get("trade_date") or review.get("buy_date")),
        tplus1,
    )


def _pending_tplus1_actual_items(payload):
    items = []
    pairs = payload.get("pairs") if isinstance(payload, dict) and isinstance(payload.get("pairs"), list) else []
    for pair in pairs:
        if not isinstance(pair, dict) or pair.get("sell_date"):
            continue
        primary = _primary_paper_evaluation(pair)
        if not primary:
            continue
        review = primary.get("tplus2_exit_review") if isinstance(primary.get("tplus2_exit_review"), dict) else {}
        actual = _tplus1_actual_from_review(review)
        if actual.get("open_to_close_return_pct") is None:
            continue
        items.append(
            {
                "decision_date": _clean(pair.get("effective_decision_date")),
                "buy_date": _clean(pair.get("buy_date") or actual.get("trade_date")),
                "stock": _clean(primary.get("stock_label") or review.get("stock_label")),
                **actual,
            }
        )
    return items


def _ensure_tplus1_actual_reviews(payload):
    pairs = payload.get("pairs") if isinstance(payload, dict) and isinstance(payload.get("pairs"), list) else []
    for pair in pairs:
        strategy = pair.get("paper_strategy") if isinstance(pair, dict) and isinstance(pair.get("paper_strategy"), dict) else {}
        evaluations = strategy.get("target_evaluations") if isinstance(strategy.get("target_evaluations"), list) else []
        for evaluation in evaluations:
            if not isinstance(evaluation, dict):
                continue
            review = evaluation.get("tplus2_exit_review") if isinstance(evaluation.get("tplus2_exit_review"), dict) else {}
            if not review:
                continue
            actual = _tplus1_actual_from_review(review)
            if actual.get("open_to_close_return_pct") is not None:
                review["tplus1_actual_review"] = actual
    return payload


def _pending_tplus1_actual_text(payload):
    items = _pending_tplus1_actual_items(payload)
    if not items:
        return ""
    parts = []
    for item in items[:3]:
        parts.append(
            f"{item.get('decision_date')} → {item.get('buy_date')}："
            f"{item.get('stock')} 开盘{item.get('open')} / 收盘{item.get('close')}，"
            f"开盘至收盘 {_fmt_signed_pct(item.get('open_to_close_return_pct'))}，"
            f"当日涨跌 {_fmt_signed_pct(item.get('day_change_pct'))}"
        )
    if len(items) > 3:
        parts.append(f"另有{len(items) - 3}条待补T+2但已有T+1事实")
    return "；".join(parts)


def _pending_tplus1_equity_reference_text(metric_row, payload):
    items = _pending_tplus1_actual_items(payload)
    if not items:
        return ""
    net_value = _safe_float(metric_row.get("final_net_value"), None)
    period_count = _safe_int(metric_row.get("period_count"), 0)
    if net_value is None or net_value <= 0 or period_count <= 0:
        return ""
    adjusted_net_value = net_value
    valid_count = 0
    for item in items:
        value = _safe_float(item.get("open_to_close_return_pct"), None)
        if value is None:
            continue
        adjusted_net_value *= 1 + value / 100
        valid_count += 1
    if not valid_count:
        return ""
    cumulative = (adjusted_net_value - 1) * 100
    monthly = _annualized_pct_from_net_value(adjusted_net_value, period_count, 21)
    return (
        f"并入{valid_count}条T+1已发生浮动表现后：区间参考 {_fmt_signed_pct(cumulative)}；"
        f"月度折算参考 {_fmt_signed_pct(monthly)}"
    )


def _render_replay_summary(payload):
    payload = _apply_tplus1_actual_to_replay_payload(payload)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    best_combo = matrix_summary.get("best_combo") if isinstance(matrix_summary.get("best_combo"), dict) else {}
    best_matrix = _best_matrix_row(summary)
    settled_metric_row = _replay_metric_row(summary)
    metric_row = _adjust_metric_row_with_tplus1_actual(settled_metric_row, payload)
    chart_payload = _replay_summary_chart_payload(payload)
    has_chart = (
        bool(chart_payload.get("rows"))
        or bool((chart_payload.get("matrix") or {}).get("cells"))
        or bool((chart_payload.get("sample_distribution") or {}).get("outcomes"))
        or bool((chart_payload.get("equity_curve") or {}).get("points"))
        or bool((chart_payload.get("market_breadth") or {}).get("rows"))
    )
    if not has_chart:
        return ""
    curve_points = [
        point for point in (chart_payload.get("equity_curve") or {}).get("points") or []
        if isinstance(point, dict) and _safe_float(point.get("return_pct"), None) is not None
    ]
    positive_count = sum(1 for point in curve_points if _safe_float(point.get("return_pct"), 0) > 0)
    sample_count = len(curve_points)
    if not sample_count:
        positive_count = _safe_int(best_matrix.get("positive_count"), 0)
        sample_count = _safe_int(best_matrix.get("sample_count"), best_combo.get("sample_count", 0))
    positive_ratio_text = "待补"
    if sample_count:
        positive_ratio_text = f"{positive_count}/{sample_count}（{positive_count / sample_count * 100:.1f}%）"
    metric_sample_count = _safe_int(metric_row.get("sample_count"), sample_count)
    metric_sample_text = f"{metric_sample_count}/{payload.get('sample_count', 0)}"
    if metric_row.get("tplus1_actual_count"):
        metric_sample_text += f"（含T+1已发生{metric_row.get('tplus1_actual_count')}条）"
    best_window_text = "待补"
    if best_combo.get("buy_window") or best_combo.get("sell_window"):
        best_window_text = f"T+1 {best_combo.get('buy_window') or '待补'} 买 / T+2 {best_combo.get('sell_window') or '待补'} 卖"
    metric_source = _clean(metric_row.get("label"), "较高窗口原始口径")
    variant_scope_text = _replay_variant_scope_text(payload)
    variant_summary_row = (
        f"<tr><td>版本口径</td><td>{_html(variant_scope_text)}</td><td>用于区分末端未结算样本；已结算收益样本按同一口径比较。</td></tr>"
        if variant_scope_text
        else ""
    )
    tplus1_actual_text = _pending_tplus1_actual_text(payload)
    tplus1_actual_row = (
        f"<tr><td>T+1已发生表现</td><td>{_html(tplus1_actual_text)}</td><td>这是买入日已经发生的真实日线表现；不替代完整T+2卖出窗口收益。</td></tr>"
        if tplus1_actual_text
        else ""
    )
    settled_reference_row = (
        f"<tr><td>完整T+2已结算参考</td><td>{_html(_fmt_signed_pct(metric_row.get('tplus2_settled_cumulative_return_pct')) if metric_row.get('tplus2_settled_cumulative_return_pct') is not None else '待补')}</td><td>仅统计完整T+2窗口样本；当前主口径已并入T+1已发生表现。</td></tr>"
        if metric_row.get("tplus1_actual_count")
        else ""
    )
    return f"""
      <section class="replay-summary" id="replay-summary" aria-label="回测摘要">
        <h2 class="bear-section-action">回测摘要</h2>
        <p>只保留可比较的日线代理结论，页面不展开逐日操作明细。</p>
        <div class="reader-table replay-metric-table">
          <table>
            <thead><tr><th>指标</th><th>数值</th><th>说明</th></tr></thead>
            <tbody>
              <tr><td>较高买卖窗口</td><td>{_html(best_window_text)}</td><td>{_html(metric_source)}；未计手续费、滑点和真实分时成交。</td></tr>
              {variant_summary_row}
              <tr><td>收益曲线样本</td><td>{_html(metric_sample_text)}</td><td>完整T+2样本加上已经发生的T+1日线表现；仍未把未来T+2当作已发生事实。</td></tr>
              {tplus1_actual_row}
              <tr><td>正收益占比</td><td>{_html(positive_ratio_text)}</td><td>按较高窗口的已结算日线代理样本统计。</td></tr>
              <tr><td>区间收益</td><td>{_html(_fmt_signed_pct(metric_row.get("cumulative_return_pct")) if metric_row.get("cumulative_return_pct") is not None else "待补")}</td><td>已并入T+1已发生表现；完整T+2仍等后续事实补齐。</td></tr>
              <tr><td>月度折算参考</td><td>{_html(_fmt_signed_pct(metric_row.get("monthly_return_pct")) if metric_row.get("monthly_return_pct") is not None else "待补")}</td><td>按21个交易日折算；当前主口径含T+1已发生表现，不是最终月收益。</td></tr>
              <tr><td>252日折算参考</td><td>{_html(_fmt_signed_pct(metric_row.get("annualized_return_pct")) if metric_row.get("annualized_return_pct") is not None else "待补")}</td><td>短样本复利机械放大，只保留为数学参考，不作为收益结论。</td></tr>
              {settled_reference_row}
              <tr><td>指数对比</td><td>{_html(_benchmark_excess_summary_text(metric_row))}</td><td>策略区间收益减同区间指数涨跌；正数表示高于指数，缺首尾点位则待补。</td></tr>
              <tr><td>最大回撤</td><td>{_html(_fmt_signed_pct(metric_row.get("max_drawdown_pct")) if metric_row.get("max_drawdown_pct") is not None else "待补")}</td><td>按样本顺序复利累乘后的回撤。</td></tr>
              <tr><td>市场迹象</td><td>{_html(_replay_market_signal_text(payload))}</td><td>涨跌家数、全A涨跌幅和创新高占比只解释T0市场底色。</td></tr>
            </tbody>
          </table>
        </div>
        <section class="bear-chart-card" id="replay-window-matrix">
          <div class="bear-chart-copy">
            <span class="bear-chart-eyebrow">图表 1</span>
            <h4>买入 / 卖出时间矩阵</h4>
            <p>颜色表示平均代理表现，星号标出较高组合；括号逻辑看正收益数/样本数。</p>
          </div>
          <div class="bear-chart-frame is-tall">
            <div class="bear-chart" id="sector-window-matrix-chart" role="img" aria-label="买入卖出时间矩阵热力图"></div>
          </div>
        </section>
        <section class="bear-chart-card" id="replay-window-metrics">
          <div class="bear-chart-copy">
            <span class="bear-chart-eyebrow">图表 2</span>
            <h4>区间收益与月度折算参考</h4>
            <p>同一批T0样本折算，先看区间收益；252日折算不作为短样本判断依据。</p>
            <div class="chart-tone-legend" aria-label="收益颜色说明">
              <span><i class="chart-tone-swatch is-interval" aria-hidden="true"></i>区间收益</span>
              <span><i class="chart-tone-swatch is-monthly" aria-hidden="true"></i>月度折算参考</span>
              <span><i class="chart-tone-swatch is-negative" aria-hidden="true"></i>负收益</span>
            </div>
          </div>
          <div class="bear-chart-frame">
            <div class="bear-chart" id="sector-window-metrics-chart" role="img" aria-label="区间收益与月度折算参考柱状图"></div>
          </div>
        </section>
        <section class="bear-chart-card" id="replay-window-excess">
          <div class="bear-chart-copy">
            <span class="bear-chart-eyebrow">图表 3</span>
            <h4>较高窗口与指数区间收益对比</h4>
            <p>每个指数一组两根横向柱：策略本身和指数本身，直接比较两边的区间涨跌幅长度。</p>
          </div>
          <div class="bear-chart-frame">
            <div class="bear-chart" id="sector-window-excess-chart" role="img" aria-label="较高窗口与指数区间收益对比分组横向柱状图"></div>
          </div>
        </section>
        <section class="bear-chart-card" id="replay-sample-distribution">
          <div class="bear-chart-copy">
            <span class="bear-chart-eyebrow">图表 4</span>
            <h4>样本收益分布</h4>
            <p>把正收益、负收益、待补和收益区间放在一张图里，避免被单个高收益样本带偏。</p>
          </div>
          <div class="bear-chart-frame">
            <div class="bear-chart" id="sector-sample-distribution-chart" role="img" aria-label="样本收益分布柱状图"></div>
          </div>
        </section>
        <section class="bear-chart-card" id="replay-equity-curve">
          <div class="bear-chart-copy">
            <span class="bear-chart-eyebrow">图表 5</span>
            <h4>较高组合净值曲线</h4>
            <p>按T0日期顺序复利累乘，配合回撤看波动，不等于真实成交曲线。</p>
          </div>
          <div class="bear-chart-frame">
            <div class="bear-chart" id="sector-window-equity-chart" role="img" aria-label="较高组合净值与回撤图"></div>
          </div>
        </section>
        <section class="bear-chart-card" id="replay-market-breadth">
          <div class="bear-chart-copy">
            <span class="bear-chart-eyebrow">图表 6</span>
            <h4>T0市场底色</h4>
            <p>涨跌家数、全A涨跌幅和创新高占比用来解释环境，不替代买卖窗口结论。</p>
          </div>
          <div class="bear-chart-frame">
            <div class="bear-chart" id="sector-market-breadth-chart" role="img" aria-label="T0市场底色图"></div>
          </div>
        </section>
      </section>
    """


_replay_dashboard_chart_payload = _replay_summary_chart_payload
_render_replay_dashboard = _render_replay_summary


def _render_window_performance_chart(summary):
    payload = _window_performance_chart_payload(summary)
    if not payload.get("rows"):
        return '<p class="chart-empty">暂无可绘制的窗口折算收益图</p>'
    return f"""
              <section class="bear-chart-card">
                <div class="bear-chart-copy">
                  <span class="bear-chart-eyebrow">收益对照</span>
                  <h4>窗口日线代理收益与回撤</h4>
                  <p>非真实分时成交，只比较同一批样本下的窗口表现。</p>
                </div>
                <div class="bear-chart-frame">
                  <div class="bear-chart" id="sector-window-return-chart" role="img" aria-label="窗口收益与回撤柱线图"></div>
                </div>
              </section>
	    """


def _render_recommended_curve_rows(summary):
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    curve = matrix_summary.get("recommended_equity_curve") if isinstance(matrix_summary.get("recommended_equity_curve"), dict) else {}
    points = curve.get("curve_points") if isinstance(curve.get("curve_points"), list) else []
    rows = []
    for item in points:
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('decision_date'))} → {_html(item.get('buy_date'))} → {_html(item.get('sell_date') or '待补')}</td>"
            f"<td>{_html(item.get('stock'))}</td>"
            f"<td>{_html(item.get('buy_window'))} / {_html(item.get('sell_window'))}</td>"
            f"<td>{_html(_fmt_signed_pct(item.get('return_pct')))}</td>"
            f"<td>{_html(item.get('net_value') if item.get('net_value') is not None else '待补')}</td>"
            f"<td>{_html(_fmt_signed_pct(item.get('cumulative_return_pct')) if item.get('cumulative_return_pct') is not None else '待补')}</td>"
            f"<td>{_html(_fmt_signed_pct(item.get('drawdown_pct')) if item.get('drawdown_pct') is not None else '待补')}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="7">暂无较高组合收益曲线</td></tr>'


def _render_target_action_rows(summary):
    target_summary = summary.get("target_action_summary") if isinstance(summary.get("target_action_summary"), dict) else {}
    rows = []
    for item in target_summary.get("rows") or []:
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('decision_date'))}</td>"
            f"<td>{_html(item.get('decision_type'))}</td>"
            f"<td>{_html(item.get('action_label'))}</td>"
            f"<td>{_html(item.get('primary_stock'))}</td>"
            f"<td>{_html(item.get('reason'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="5">暂无判定样本</td></tr>'


def _render_empty_reason_rows(summary):
    target_summary = summary.get("target_action_summary") if isinstance(summary.get("target_action_summary"), dict) else {}
    return _render_distribution_rows(
        target_summary.get("empty_reason_distribution"),
        target_summary.get("empty_reason_dates"),
    )


def _render_emotion_transition_rows(summary):
    emotion_summary = summary.get("emotion_transition_summary") if isinstance(summary.get("emotion_transition_summary"), dict) else {}
    rows = []
    for item in (emotion_summary.get("rows") or [])[:50]:
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('decision_date'))} → {_html(item.get('buy_date'))} → {_html(item.get('sell_date') or '待补')}</td>"
            f"<td>{_html(item.get('primary_stock') or '无主样本')}</td>"
            f"<td>{_html(item.get('tplus1_market'))}</td>"
            f"<td>{_html(item.get('tplus1_sector'))}</td>"
            f"<td>{_html(item.get('tplus2_market'))}</td>"
            f"<td>{_html(item.get('tplus2_sector'))}</td>"
            f"<td>{_html(item.get('best_sell_window') or '待补')}</td>"
            f"<td>{_html(_fmt_pct(item.get('best_return_pct')) if item.get('best_return_pct') is not None else '待补')}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="8">暂无情绪迁移样本</td></tr>'


def _render_buyability_summary_rows(summary):
    buyability_summary = summary.get("buyability_summary") if isinstance(summary.get("buyability_summary"), dict) else {}
    rows = []
    for status, count in (buyability_summary.get("distribution") or {}).items():
        dates = ((buyability_summary.get("dates") or {}).get(status) or []) if isinstance(buyability_summary.get("dates"), dict) else []
        rows.append(
            "<tr>"
            f"<td>{_html(status)}</td>"
            f"<td>{_html(count)}</td>"
            f"<td>{_html('、'.join(dates[:24]))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="3">暂无真实可买性样本</td></tr>'


def _render_buyability_sample_rows(summary):
    buyability_summary = summary.get("buyability_summary") if isinstance(summary.get("buyability_summary"), dict) else {}
    rows = []
    for item in (buyability_summary.get("rows") or [])[:80]:
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('decision_date'))} → {_html(item.get('buy_date'))} → {_html(item.get('sell_date') or '待补')}</td>"
            f"<td>{_html(item.get('stock'))}</td>"
            f"<td>{_html(item.get('status'))}</td>"
            f"<td>{_html(item.get('reason'))}</td>"
            f"<td>{_html(_fmt_pct(item.get('early_high_change_pct')) if item.get('early_high_change_pct') is not None else '待补')}</td>"
            f"<td>{_html(_fmt_pct(item.get('early_close_change_pct')) if item.get('early_close_change_pct') is not None else '待补')}</td>"
            f"<td>{_html(item.get('minute_count') if item.get('minute_count') is not None else 0)}</td>"
            f"<td>{_html(item.get('minute_source') or '待补')}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="8">暂无真实可买性样本</td></tr>'


def _render_small_account_summary_rows(summary):
    small_summary = summary.get("small_account_summary") if isinstance(summary.get("small_account_summary"), dict) else {}
    rows = []
    for item in (small_summary.get("rows") or [])[:80]:
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('decision_date'))} → {_html(item.get('buy_date'))} → {_html(item.get('sell_date') or '待补')}</td>"
            f"<td>{_html(item.get('stock'))}</td>"
            f"<td>{_html(item.get('buy_window') or '待补')}</td>"
            f"<td>{_html(item.get('entry_price') if item.get('entry_price') is not None else '待补')}</td>"
            f"<td>{_html(item.get('one_lot_amount') if item.get('one_lot_amount') is not None else '待补')}</td>"
            f"<td>{_html(_fmt_pct(item.get('one_lot_account_pct')) if item.get('one_lot_account_pct') is not None else '待补')}</td>"
            f"<td>{_html(item.get('account_fit') or '待补')}</td>"
            f"<td>{_html(item.get('position_50pct_basis') or '待补')}</td>"
            f"<td>{_html(item.get('small_account_action') or '待补')}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="9">暂无小账户换算样本</td></tr>'


def _preferred_report_path(trade_date):
    candidates = [
        PROJECT_ROOT / "reports" / "replay" / f"{trade_date}_A股日报_完整版_replay.md",
        PROJECT_ROOT / "reports" / f"{trade_date}_A股日报_完整版.md",
    ]
    return next((path for path in candidates if path.exists()), None)


def _read_report_text(trade_date):
    path = _preferred_report_path(trade_date)
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _first_markdown_table_row(text, labels):
    labels = tuple(labels)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and cells[0] in labels:
            return cells
    return []


def _index_row_from_data(data, *names):
    data = data if isinstance(data, dict) else {}
    indices = data.get("indices") if isinstance(data.get("indices"), dict) else {}
    for name in names:
        if isinstance(indices.get(name), dict):
            return indices.get(name)
    for key in ("wind_a_alternative", "star50_index", "csi500_index", "csi1000_index"):
        row = data.get(key)
        if not isinstance(row, dict):
            continue
        row_name = _clean(row.get("name"))
        row_code = _stock_code(row.get("code"))
        if any(name == row_name or name in row_name or row_name in name or name == row_code for name in names):
            return row
    return {}


def _format_index_value(row):
    row = row if isinstance(row, dict) else {}
    price = _safe_float(row.get("price", row.get("close", row.get("点位"))), None)
    change = _safe_float(row.get("change_pct", row.get("涨跌幅")), None)
    if price is None or price == 0 or change is None:
        return ""
    return f"{price:.2f} / {_fmt_signed_pct(change)}"


def _index_text(data, report_text, label, *names):
    value = _format_index_value(_index_row_from_data(data, *names))
    if value:
        return value
    cells = _first_markdown_table_row(report_text, (label, *names))
    if len(cells) >= 3:
        point_text = re.sub(r"[点,，\\s]", "", cells[1])
        point = _safe_float(point_text, None)
        change = _safe_float(cells[2].replace("%", ""), None)
        if point is not None and point != 0 and change is not None:
            return f"{point:.2f} / {_fmt_signed_pct(change)}"
    return "待补"


class IndexContextRefill:
    def __init__(self, *, fetch_star50_fn=None, fetch_csi500_fn=None, startup_error=""):
        self.fetch_star50_fn = fetch_star50_fn
        self.fetch_csi500_fn = fetch_csi500_fn
        self.startup_error = startup_error
        self.cache = {}
        self.summary = {
            "schema_version": "index_context_refill.v1",
            "attempted": 0,
            "filled": 0,
            "missing": 0,
            "errors": 0,
            "error_samples": [],
        }

    def _index_text(self, trade_date, index_key, fetch_fn):
        trade_date = _date_text(trade_date)
        if not trade_date:
            return ""
        if not fetch_fn:
            if self.startup_error:
                self.summary["errors"] += 1
                self.summary["missing"] += 1
                self.summary["error_samples"].append(f"{index_key} {trade_date}: {self.startup_error}")
            return ""
        cache_key = (index_key, trade_date)
        if cache_key in self.cache:
            return self.cache[cache_key]
        if self.startup_error:
            self.summary["errors"] += 1
            self.summary["missing"] += 1
            self.summary["error_samples"].append(f"{index_key} {trade_date}: {self.startup_error}")
            self.cache[cache_key] = ""
            return ""
        self.summary["attempted"] += 1
        try:
            payload = fetch_fn(trade_date)
        except Exception as exc:
            self.summary["errors"] += 1
            self.summary["missing"] += 1
            self.summary["error_samples"].append(f"{index_key} {trade_date}: {type(exc).__name__}: {exc}")
            self.cache[cache_key] = ""
            return ""
        text = _format_index_value(payload if isinstance(payload, dict) else {})
        if text:
            self.summary["filled"] += 1
        else:
            self.summary["missing"] += 1
        self.cache[cache_key] = text
        return text

    def star50_text(self, trade_date):
        return self._index_text(trade_date, "科创50", self.fetch_star50_fn)

    def csi500_text(self, trade_date):
        return self._index_text(trade_date, "中证500", self.fetch_csi500_fn)


def build_tushare_index_context_refill(*, fetch_star50_fn=None, fetch_csi500_fn=None):
    if fetch_star50_fn is None or fetch_csi500_fn is None:
        try:
            from input.tushare_runtime import (
                get_csi500_from_tushare_first,
                get_star50_from_tushare_first,
            )
        except Exception as exc:
            return IndexContextRefill(startup_error=f"{type(exc).__name__}: {exc}")
        fetch_star50_fn = fetch_star50_fn or get_star50_from_tushare_first
        fetch_csi500_fn = fetch_csi500_fn or get_csi500_from_tushare_first
    return IndexContextRefill(fetch_star50_fn=fetch_star50_fn, fetch_csi500_fn=fetch_csi500_fn)


def _market_breadth_text(data, report_text):
    stats = data.get("market_stats") if isinstance(data, dict) and isinstance(data.get("market_stats"), dict) else {}
    up_count = _safe_int(stats.get("up_count"), 0)
    down_count = _safe_int(stats.get("down_count"), 0)
    if up_count > 0 or down_count > 0:
        return f"{up_count} / {down_count}"
    cells = _first_markdown_table_row(report_text, ("涨跌比",))
    if len(cells) >= 2:
        match = re.search(r"(\d+)\s*[:/]\s*(\d+)", cells[1])
        if match:
            up_count = _safe_int(match.group(1), 0)
            down_count = _safe_int(match.group(2), 0)
            if up_count > 0 or down_count > 0:
                return f"{up_count} / {down_count}"
    return "待补"


def _new_high_signal(all_a_share_pct):
    pct = _safe_float(all_a_share_pct, None)
    if pct is None:
        return ""
    if pct < 2:
        return "趋势扩散偏冷"
    if pct <= 5:
        return "趋势扩散震荡"
    return "趋势扩散偏热"


def _new_high_text(data, report_text):
    feedback = data.get("new_high_feedback") if isinstance(data, dict) and isinstance(data.get("new_high_feedback"), dict) else {}
    count = _safe_int(feedback.get("new_high_count"), 0)
    pct = _safe_float(feedback.get("all_a_share_pct"), None)
    if count > 0 and pct is not None:
        return f"{count} / {pct:.2f}% / {_new_high_signal(pct)}"
    match = re.search(r"阶段新高\s*(\d+)\s*只，占全A约\s*([0-9.]+)%", report_text)
    if match:
        pct = _safe_float(match.group(2), None)
        return f"{_safe_int(match.group(1), 0)} / {pct:.2f}% / {_new_high_signal(pct)}"
    return "待补"


def _market_context_for_pair(pair, loader):
    trade_date = _clean(pair.get("effective_decision_date"))
    data = {}
    try:
        data = loader(trade_date)
    except Exception:
        data = {}
    report_text = _read_report_text(trade_date)
    return {
        "T0上证指数": _index_text(data, report_text, "上证指数", "上证指数", "000001"),
        "T0创业板指": _index_text(data, report_text, "创业板指", "创业板指", "399006"),
        "T0科创50": _index_text(data, report_text, "科创50", "科创50", "000688"),
        "T0中证500": _index_text(data, report_text, "中证500", "中证500", "000905"),
        "T0全A指数": _index_text(data, report_text, "中证全指", "中证全指", "000985"),
        "T0中证1000": _index_text(data, report_text, "中证1000", "中证1000", "000852"),
        "T0涨跌家数": _market_breadth_text(data, report_text),
        "T0创新高全A占比": _new_high_text(data, report_text),
    }


def _apply_index_context_refill(row, pair, index_context_refill):
    if not row or not index_context_refill:
        return
    star50_text = index_context_refill.star50_text(pair.get("effective_decision_date"))
    if star50_text:
        row["T0科创50"] = star50_text
    refill_text = index_context_refill.csi500_text(pair.get("effective_decision_date"))
    if refill_text:
        row["T0中证500"] = refill_text


def _apply_index_context_refill_to_payload(payload, index_context_refill):
    if not isinstance(payload, dict) or not index_context_refill:
        return payload
    for pair in payload.get("pairs") or []:
        if not isinstance(pair, dict):
            continue
        context = pair.get("t0_market_context")
        if not isinstance(context, dict):
            context = {}
            pair["t0_market_context"] = context
        row = {
            "T0科创50": context.get("T0科创50"),
            "T0中证500": context.get("T0中证500"),
        }
        _apply_index_context_refill(row, pair, index_context_refill)
        if row.get("T0科创50"):
            context["T0科创50"] = row["T0科创50"]
        if row.get("T0中证500"):
            context["T0中证500"] = row["T0中证500"]
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary:
        summary["index_benchmark_summary"] = _build_index_benchmark_summary(payload.get("pairs") or [])
        summary["window_performance_comparison"] = _build_window_performance_comparison(
            payload.get("pairs") or [],
            summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {},
            summary["index_benchmark_summary"],
        )
    return payload


def _best_pair_matrix_row(evaluation):
    review = evaluation.get("tplus2_exit_review") if isinstance(evaluation, dict) else {}
    review = review if isinstance(review, dict) else {}
    best = {}
    for row in review.get("window_matrix") or []:
        if not isinstance(row, dict) or row.get("return_pct") is None:
            continue
        if not best or float(row.get("return_pct")) > float(best.get("return_pct")):
            best = row
    return best


def _paper_status_label(strategy):
    strategy = strategy if isinstance(strategy, dict) else {}
    action = _clean(strategy.get("action"))
    if action == "paper_participate":
        return "有纸面主样本"
    if action == "paper_watch":
        return "观察但不参与"
    return "明确不参与"


def _settlement_status_suffix(pair, matrix_row):
    if pair.get("sell_date") and (not isinstance(matrix_row, dict) or matrix_row.get("return_pct") is None):
        return "（待结算）"
    return ""


def build_forward_replay_daily_rows(payload, *, loader=load_daily_report_data_for_forward_replay, index_context_refill=None):
    payload = _ensure_tplus1_actual_reviews(payload)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    best_combo = matrix_summary.get("best_combo") if isinstance(matrix_summary.get("best_combo"), dict) else {}
    buy_window_id = _clean(best_combo.get("buy_window_id"), "open_0930_0935")
    sell_window_id = _clean(best_combo.get("sell_window_id"), "late_1430_1455")
    rows = []
    for pair in payload.get("pairs") or []:
        strategy = pair.get("paper_strategy") if isinstance(pair.get("paper_strategy"), dict) else {}
        target_summary = strategy.get("target_summary") if isinstance(strategy.get("target_summary"), dict) else {}
        primary_stock = _clean(target_summary.get("primary_stock"), "无主样本")
        primary = _primary_paper_evaluation(pair)
        review = primary.get("tplus2_exit_review") if isinstance(primary.get("tplus2_exit_review"), dict) else {}
        matrix_row = next(
            (
                item for item in review.get("window_matrix") or []
                if isinstance(item, dict)
                and item.get("buy_window_id") == buy_window_id
                and item.get("sell_window_id") == sell_window_id
            ),
            {},
        )
        best_daily = _best_pair_matrix_row(primary)
        buyability = review.get("buyability_review") if isinstance(review.get("buyability_review"), dict) else {}
        account_fit = _small_account_fit_for_window(primary, buy_window_id)
        tplus1_actual = _tplus1_actual_from_review(review)
        row = {
            "T0日期": pair.get("effective_decision_date"),
            "T+1买入日": pair.get("buy_date"),
            "T+2卖出日": pair.get("sell_date") or "",
            "状态": _paper_status_label(strategy) + _settlement_status_suffix(pair, matrix_row),
            "纸面主样本": primary_stock,
            "建议T+1买入窗口": best_combo.get("buy_window") if primary else "不参与/只观察",
            "建议T+2卖出窗口": best_combo.get("sell_window") if primary else "不参与/只观察",
            "全样本最佳组合代理收益": _fmt_signed_pct(matrix_row.get("return_pct")) if matrix_row.get("return_pct") is not None else "",
            "当日样本内最高组合": (
                f"{_clean(best_daily.get('buy_window'))} / {_clean(best_daily.get('sell_window'))}"
                if best_daily else ""
            ),
            "当日样本内最高代理收益": _fmt_signed_pct(best_daily.get("return_pct")) if best_daily.get("return_pct") is not None else "",
            "T+1开盘至收盘已发生表现": (
                _fmt_signed_pct(tplus1_actual.get("open_to_close_return_pct"))
                if tplus1_actual.get("open_to_close_return_pct") is not None else ""
            ),
            "T+1当日涨跌幅": (
                _fmt_signed_pct(tplus1_actual.get("day_change_pct"))
                if tplus1_actual.get("day_change_pct") is not None else ""
            ),
            "T+1真实日线": (
                f"开{tplus1_actual.get('open')} / 高{tplus1_actual.get('high')} / 低{tplus1_actual.get('low')} / 收{tplus1_actual.get('close')}"
                if tplus1_actual.get("close") is not None else ""
            ),
            "T+1买点复核": _clean(buyability.get("status")) if primary else "",
            "复核结论": _clean(target_summary.get("primary_outcome_label"), "没有纸面主样本"),
            "说明": _clean(strategy.get("action_reason")),
            "账户本金": _clean((payload.get("small_account") or {}).get("account_capital"), "10000"),
            "T+1买入代理价": account_fit.get("entry_price") if account_fit else "",
            "一手金额": account_fit.get("one_lot_amount") if account_fit else "",
            "一手占账户比例": _fmt_pct(account_fit.get("one_lot_account_pct")) if account_fit.get("one_lot_account_pct") is not None else "",
            "账户可做性": account_fit.get("account_fit") if account_fit else "",
            "小账户动作建议": account_fit.get("small_account_action") if account_fit else "",
            "50%仓位口径": account_fit.get("position_50pct_basis") if account_fit else "",
        }
        row.update(_market_context_for_pair(pair, loader))
        _apply_index_context_refill(row, pair, index_context_refill)
        rows.append(row)
    return rows


def _write_csv_rows(rows, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _matrix_markdown_table(matrix_summary):
    matrix_summary = matrix_summary if isinstance(matrix_summary, dict) else {}
    rows = matrix_summary.get("rows") if isinstance(matrix_summary.get("rows"), list) else []
    by_key = {
        (row.get("buy_window_id"), row.get("sell_window_id")): row
        for row in rows if isinstance(row, dict)
    }
    best_id = ""
    best_combo = matrix_summary.get("best_combo") if isinstance(matrix_summary.get("best_combo"), dict) else {}
    if best_combo:
        best_id = f"{best_combo.get('buy_window_id')}__{best_combo.get('sell_window_id')}"
    lines = [
        "| T+1买入窗口 \\ T+2卖出窗口 | 09:30-09:35 | 09:50-10:10 | 14:30-14:55 |",
        "|---|---:|---:|---:|",
    ]
    for buy_window in BUY_WINDOWS:
        cells = [buy_window["window"]]
        for sell_window in SELL_WINDOWS:
            row = by_key.get((buy_window["id"], sell_window["id"])) or {}
            text = "待补"
            if row.get("average_return_pct") is not None:
                text = f"{_fmt_signed_pct(row.get('average_return_pct'))}（{row.get('positive_count', 0)}/{row.get('sample_count', 0)}）"
            if row.get("id") == best_id:
                text += " **较高**"
            cells.append(text)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _requested_start_date(payload):
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    return coverage.get("requested_start_date") or payload.get("start_date") or ""


def _requested_end_date(payload):
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    return coverage.get("requested_end_date") or payload.get("end_date") or ""


def _settled_daily_rows(rows):
    return [
        row for row in rows
        if row.get("全样本最佳组合代理收益") not in {"", None}
    ]


def render_forward_replay_markdown_summary(payload, rows, *, title="板块资金扩散前向回测窗口摘要", scope_note=""):
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    target_summary = summary.get("target_action_summary") if isinstance(summary.get("target_action_summary"), dict) else {}
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    best_combo = matrix_summary.get("best_combo") if isinstance(matrix_summary.get("best_combo"), dict) else {}
    buyability_summary = summary.get("buyability_summary") if isinstance(summary.get("buyability_summary"), dict) else {}
    small_summary = summary.get("small_account_summary") if isinstance(summary.get("small_account_summary"), dict) else {}
    account = payload.get("small_account") if isinstance(payload.get("small_account"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    missing_dates = coverage.get("missing_dates") if isinstance(coverage.get("missing_dates"), list) else []
    skipped_dates = coverage.get("skipped_dates") if isinstance(coverage.get("skipped_dates"), list) else []
    settled_rows = _settled_daily_rows(rows)
    first_t0 = rows[0]["T0日期"] if rows else ""
    last_t0 = rows[-1]["T0日期"] if rows else ""
    settled_first_t0 = settled_rows[0]["T0日期"] if settled_rows else ""
    settled_last_t0 = settled_rows[-1]["T0日期"] if settled_rows else ""
    pending_rows = [row for row in rows if row.get("状态", "").endswith("（待结算）")]
    lines = [
        f"# {title}",
        "",
        "## 结论",
        f"- 请求区间：{_requested_start_date(payload)} 至 {_requested_end_date(payload)}；有效 T0 覆盖 {first_t0 or '待补'} 至 {last_t0 or '待补'}，形成 {len(rows)} 个 T0/T+1/T+2 日期对。",
        f"- 已结算收益样本：T0 覆盖 {settled_first_t0 or '待补'} 至 {settled_last_t0 or '待补'}，共 {len(settled_rows)} 个；有纸面主样本 {target_summary.get('target_day_count', 0)} 天，观察但不参与 {target_summary.get('watch_day_count', 0)} 天，明确不参与 {target_summary.get('skip_day_count', 0)} 天。",
        f"- 当前已结算样本内较高组合：T+1 `{best_combo.get('buy_window') or '待补'}` 买入代理，T+2 `{best_combo.get('sell_window') or '待补'}` 卖出代理，平均代理表现 {_fmt_signed_pct(best_combo.get('average_return_pct')) if best_combo.get('average_return_pct') is not None else '待补'}，样本 {best_combo.get('sample_count', 0)}。",
        f"- 买点复核：早盘未明显追高 {buyability_summary.get('early_not_chasing_day_count', 0)} 天，追高风险 {buyability_summary.get('risk_day_count', 0)} 天，可能买不到 {buyability_summary.get('unbuyable_day_count', 0)} 天，待分时确认 {buyability_summary.get('pending_confirm_day_count', 0)} 天；所以本表是日线代理复盘，不等于真实成交证明。",
        f"- 小账户口径：账户本金 {account.get('account_capital', 10000)} 元，一手 {account.get('lot_size', 100)} 股；`50%条件执行` 是策略意图，实际参与必须看一手金额、固定窗口和买入资格。",
    ]
    if scope_note:
        lines.append(f"- {scope_note}")
    if missing_dates:
        lines.append(f"- 缺失 T0 事实日 {len(missing_dates)} 天；缺失日期不生成每日标的。")
    if skipped_dates:
        lines.append(f"- 非交易日跳过 {len(skipped_dates)} 天：{', '.join(item.get('date', '') for item in skipped_dates if isinstance(item, dict))}。")
    if pending_rows:
        lines.append(
            "- 待结算日期链："
            + "；".join(
                f"{row.get('T0日期')} -> {row.get('T+1买入日')} -> {row.get('T+2卖出日')}"
                for row in pending_rows
            )
            + "。"
        )
    lines.extend(
        [
            "",
            "## 窗口矩阵图",
            _matrix_markdown_table(matrix_summary),
            "",
            "> 括号内为正收益数/样本数；所有窗口收益均为日线代理，不是逐笔成交回测。",
            "",
            "## 小账户一手换算",
            f"- 账户可做性分布：{_distribution_text(small_summary.get('distribution'))}",
            f"- 小账户动作分布：{_distribution_text(small_summary.get('action_distribution'))}",
            "- 结论：小资金账户里，50%不总是可精确执行；高价股一手若超过60%账户，就按“一手就是上限”处理，超过80%时只有唯一核心、固定窗口和贴近认错线同时满足才考虑，否则空仓。",
            "",
            "## 每日标的与窗口",
            "| T0日期 | T+1 | T+2 | 状态 | 纸面主样本 | T0上证 | T0创业板 | T0科创50 | T0中证500 | T0全A | T0中证1000 | T0涨跌家数 | T0创新高占比 | T+1窗口 | T+2窗口 | 全样本最佳组合收益 | T+1开盘至收盘已发生表现 | T+1当日涨跌幅 | T+1真实日线 | 一手金额 | 一手占账户 | 账户可做性 | 小账户动作 | 买点复核 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| {T0日期} | {T+1买入日} | {T+2卖出日} | {状态} | {纸面主样本} | {T0上证指数} | {T0创业板指} | {T0科创50} | {T0中证500} | {T0全A指数} | {T0中证1000} | {T0涨跌家数} | {T0创新高全A占比} | {建议T+1买入窗口} | {建议T+2卖出窗口} | {全样本最佳组合代理收益} | {T+1开盘至收盘已发生表现} | {T+1当日涨跌幅} | {T+1真实日线} | {一手金额} | {一手占账户比例} | {账户可做性} | {小账户动作建议} | {T+1买点复核} |".format(**row)
        )
    return "\n".join(lines) + "\n"


def _t0_market_context_from_pair(pair):
    context = pair.get("t0_market_context") if isinstance(pair, dict) and isinstance(pair.get("t0_market_context"), dict) else {}
    if context:
        return context
    data = pair.get("decision_data") if isinstance(pair, dict) and isinstance(pair.get("decision_data"), dict) else {}
    if data:
        return _market_context_for_pair(pair, lambda _date: data)
    return {}


def _render_t0_market_context_rows(payload):
    rows = []
    for pair in payload.get("pairs") or []:
        if not isinstance(pair, dict):
            continue
        context = _t0_market_context_from_pair(pair)
        rows.append(
            "<tr>"
            f"<td>{_html(pair.get('effective_decision_date'))}</td>"
            f"<td>{_html(context.get('T0上证指数') or '待补')}</td>"
            f"<td>{_html(context.get('T0创业板指') or '待补')}</td>"
            f"<td>{_html(context.get('T0科创50') or '待补')}</td>"
            f"<td>{_html(context.get('T0中证500') or '待补')}</td>"
            f"<td>{_html(context.get('T0全A指数') or '待补')}</td>"
            f"<td>{_html(context.get('T0中证1000') or '待补')}</td>"
            f"<td>{_html(context.get('T0涨跌家数') or '待补')}</td>"
            f"<td>{_html(context.get('T0创新高全A占比') or '待补')}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="9">暂无T0市场底色</td></tr>'


def save_forward_replay_csv_and_summary(
    payload,
    output_prefix,
    *,
    loader=load_daily_report_data_for_forward_replay,
    scope_note="",
    index_context_refill=None,
):
    payload = _ensure_tplus1_actual_reviews(payload)
    rows = build_forward_replay_daily_rows(payload, loader=loader, index_context_refill=index_context_refill)
    csv_path = _write_csv_rows(rows, f"{output_prefix}_每日标的窗口回测_含T0市场底色_含小账户.csv")
    summary_path = Path(f"{output_prefix}_窗口回测摘要_含小账户.md")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        render_forward_replay_markdown_summary(payload, rows, scope_note=scope_note),
        encoding="utf-8",
    )
    return {"csv": csv_path, "summary": summary_path, "rows": rows}


def _distribution_text(mapping):
    if not isinstance(mapping, dict) or not mapping:
        return "无"
    return "；".join(f"{_clean(key)} {value}" for key, value in mapping.items())


def _projection_window_text(return_stats):
    return_stats = return_stats if isinstance(return_stats, dict) else {}
    windows = []
    for item in return_stats.get("windows") or []:
        if item.get("average_return_pct") is None:
            continue
        windows.append(f"{_clean(item.get('window'))} 代理均值{_fmt_pct(item.get('average_return_pct'))}")
    best = _clean(return_stats.get("best_window"))
    if best:
        windows.append(f"样本内较高：{best}")
    return "；".join(windows) or "暂无可计算收益"


def _projection_score_text(item):
    return (
        f"已校准{item.get('scorable_count', 0)}；"
        f"大体一致{item.get('calibrated_count', 0)}；"
        f"偏离{item.get('miss_count', 0)}；"
        f"待校准{item.get('unknown_count', 0)}"
    )


def _render_emotion_projection_rows(summary):
    projection_summary = summary.get("emotion_projection_summary") if isinstance(summary.get("emotion_projection_summary"), dict) else {}
    rows = []
    for item in projection_summary.get("rows") or []:
        rows.append(
            "<tr>"
            f"<td>{_html(item.get('title'))}</td>"
            f"<td>{_html(item.get('projected_label'))}</td>"
            f"<td>{_html(item.get('sample_count'))}</td>"
            f"<td>{_html(_projection_score_text(item))}</td>"
            f"<td>{_html(_distribution_text(item.get('actual_distribution')))}</td>"
            f"<td>{_html(_distribution_text(item.get('match_distribution')))}</td>"
            f"<td>{_html(_projection_window_text(item.get('return_stats')))}</td>"
            f"<td>{_html(_projection_window_text(item.get('miss_return_stats')))}</td>"
            f"<td>{_html('、'.join((item.get('sample_dates') or [])[:16]))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="9">暂无T0推演样本</td></tr>'


def _refill_samples_text(summary, key):
    items = summary.get(key) if isinstance(summary, dict) else []
    if not isinstance(items, list) or not items:
        return "无"
    suffix = ""
    if len(items) >= 30:
        suffix = " 等"
    return "、".join(_clean(item) for item in items[:30]) + suffix


def _price_refill_samples_text(summary):
    parts = []
    for label, key in (
        ("补到", "filled_samples"),
        ("错日", "date_mismatch_samples"),
        ("缺失", "missing_samples"),
        ("错误", "error_samples"),
    ):
        text = _refill_samples_text(summary, key)
        if text != "无":
            parts.append(f"{label}: {text}")
    return "；".join(parts) or "无"


def _skipped_dates_text(coverage):
    skipped_dates = coverage.get("skipped_dates") if isinstance(coverage, dict) and isinstance(coverage.get("skipped_dates"), list) else []
    dates = [item.get("date", "") for item in skipped_dates if isinstance(item, dict) and item.get("date")]
    return "、".join(dates) or "无"


def _pending_settlement_pairs_text(payload):
    pending = []
    for pair in payload.get("pairs") or []:
        primary = _primary_paper_evaluation(pair)
        review = primary.get("tplus2_exit_review") if isinstance(primary.get("tplus2_exit_review"), dict) else {}
        has_return = any(
            isinstance(item, dict) and item.get("return_pct") is not None
            for item in review.get("window_matrix") or []
        )
        if not has_return:
            pending.append(
                f"{pair.get('effective_decision_date')} -> {pair.get('buy_date')} -> {pair.get('sell_date') or '待补'}"
            )
    return "；".join(pending) or "无"


def _render_global_summary(payload):
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    system_verdict = summary.get("system_verdict") if isinstance(summary.get("system_verdict"), dict) else {}
    coverage = summary.get("coverage") if isinstance(summary.get("coverage"), dict) else {}
    missing_dates = coverage.get("missing_dates") if isinstance(coverage.get("missing_dates"), list) else []
    missing_preview = "、".join(item.get("date", "") for item in missing_dates[:20] if isinstance(item, dict))
    if len(missing_dates) > 20:
        missing_preview += f" 等{len(missing_dates)}天"
    if not missing_preview:
        missing_preview = "无"
    verdict = _clean(system_verdict.get("conclusion"), "样本不足，无法判断策略链路")
    evidence = _clean(system_verdict.get("evidence"))
    root_causes = system_verdict.get("root_causes") if isinstance(system_verdict.get("root_causes"), list) else []
    root_cause_items = "".join(f"<li>{_html(item)}</li>" for item in root_causes)
    comparison = summary.get("comparison_verdict") if isinstance(summary.get("comparison_verdict"), dict) else {}
    exit_summary = summary.get("exit_window_summary") if isinstance(summary.get("exit_window_summary"), dict) else {}
    matrix_summary = summary.get("trade_window_matrix_summary") if isinstance(summary.get("trade_window_matrix_summary"), dict) else {}
    best_combo = matrix_summary.get("best_combo") if isinstance(matrix_summary.get("best_combo"), dict) else {}
    target_summary = summary.get("target_action_summary") if isinstance(summary.get("target_action_summary"), dict) else {}
    buyability_summary = summary.get("buyability_summary") if isinstance(summary.get("buyability_summary"), dict) else {}
    small_account_summary = summary.get("small_account_summary") if isinstance(summary.get("small_account_summary"), dict) else {}
    emotion_summary = summary.get("emotion_transition_summary") if isinstance(summary.get("emotion_transition_summary"), dict) else {}
    projection_summary = summary.get("emotion_projection_summary") if isinstance(summary.get("emotion_projection_summary"), dict) else {}
    price_refill = payload.get("price_refill_summary") if isinstance(payload.get("price_refill_summary"), dict) else {}
    minute_refill = payload.get("minute_refill_summary") if isinstance(payload.get("minute_refill_summary"), dict) else {}
    calendar_refill = payload.get("trade_calendar_refill_summary") if isinstance(payload.get("trade_calendar_refill_summary"), dict) else {}
    minute_notice = _minute_gap_notice(minute_refill, buyability_summary)
    settled_sample_count = best_combo.get("sample_count", 0)
    best_combo_text = "待补"
    if best_combo.get("buy_window") or best_combo.get("sell_window"):
        best_combo_text = (
            f"T+1 {best_combo.get('buy_window') or '待补'} 代理 / "
            f"T+2 {best_combo.get('sell_window') or '待补'} 代理"
        )
    return f"""
      <section class="diagnosis-summary">
        <h2>全局诊断</h2>
	        <div class="summary-grid compact">
	          <div><dt>诊断结论</dt><dd>{_html(verdict)}</dd></div>
	          <div><dt>请求区间</dt><dd>{_html(_requested_start_date(payload))} 至 {_html(_requested_end_date(payload))}</dd></div>
	          <div><dt>日期对</dt><dd>{summary.get("sample_count", 0)}</dd></div>
	          <div><dt>已结算收益样本</dt><dd>{settled_sample_count}</dd></div>
	          <div><dt>日线代理较高窗口</dt><dd>{_html(best_combo_text)}</dd></div>
	          <div><dt>待结算日期链</dt><dd>{_html(_pending_settlement_pairs_text(payload))}</dd></div>
	          <div><dt>纸面复核对象</dt><dd>{target_summary.get("target_day_count", 0)}天；无对象{target_summary.get("execution_empty_day_count", 0)}天</dd></div>
	          <div><dt>下一步</dt><dd>{_html(summary.get("next_action"))}</dd></div>
	        </div>
	        <div class="verdict-box">
	          <strong>{_html(evidence)}</strong>
	          <ul>{root_cause_items}</ul>
	        </div>
	        <details class="summary-detail-pack">
	          <summary><strong>详细复核</strong><span>数据来源、动作分布和逐项表格默认收起</span></summary>
	        <div class="comparison-box">
	          <strong>旧链路 vs 板块优先链路</strong>
	          <p>{_html(comparison.get("conclusion"))}</p>
          <p>{_html(comparison.get("evidence"))}</p>
          <p>{_html(comparison.get("next_action"))}</p>
        </div>
        <div class="comparison-box">
          <strong>T+1买入 x T+2卖出窗口结论</strong>
          <p>{_html(matrix_summary.get("recommendation"))}</p>
          <p>{_html(matrix_summary.get("data_basis"))}</p>
        </div>
        <div class="comparison-box">
          <strong>T+2卖出窗口对照</strong>
          <p>{_html(exit_summary.get("recommendation"))}</p>
          <p>{_html(exit_summary.get("data_basis"))}</p>
        </div>
        <div class="comparison-box">
          <strong>纸面主样本/空仓判定</strong>
          <p>{_html(target_summary.get("decision_rule"))}</p>
          <p>{_html(f"有纸面主样本{target_summary.get('target_day_count', 0)}天；观察但不执行{target_summary.get('watch_day_count', 0)}天；没有纸面对象{target_summary.get('skip_day_count', 0)}天。")}</p>
        </div>
        <div class="comparison-box">
          <strong>真实可买性复核</strong>
          <p>{_html(minute_notice)}</p>
          <p>{_html(minute_refill.get("basis"))}</p>
          <p>{_html(buyability_summary.get("basis") or "没有分时事实的样本只保留纸面窗口，不宣称真实可执行。")}</p>
          <p>{_html(f"早盘未明显追高{buyability_summary.get('early_not_chasing_day_count', 0)}天；追高风险{buyability_summary.get('risk_day_count', 0)}天；可能买不到{buyability_summary.get('unbuyable_day_count', 0)}天；待分时确认{buyability_summary.get('pending_confirm_day_count', 0)}天；代理事实仍缺{buyability_summary.get('missing_day_count', 0)}天。")}</p>
        </div>
        <div class="comparison-box">
          <strong>小账户一手换算</strong>
          <p>{_html(small_account_summary.get("basis") or "按一手金额换算账户实际仓位。")}</p>
          <p>{_html("；".join(f"{key}{value}天" for key, value in (small_account_summary.get("distribution") or {}).items()) or "暂无可换算样本")}</p>
        </div>
        <div class="comparison-box">
          <strong>T+1到T+2情绪迁移</strong>
          <p>{_html(emotion_summary.get("basis"))}</p>
        </div>
        <div class="comparison-box">
          <strong>T0推演T+2交易环境</strong>
          <p>{_html(projection_summary.get("basis"))}</p>
        </div>
        <details>
          <summary><strong>TuShare事实源复核</strong><span>优先获取后验价格和T+2日期</span></summary>
          <div class="table-scroll">
            <table>
              <thead><tr><th>对象</th><th>状态</th><th>补到</th><th>仍缺</th><th>错误</th><th>依据</th><th>样本</th></tr></thead>
              <tbody>
                <tr>
                  <td>价格事实</td>
                  <td>{_html(price_refill.get("source") or "未开启")}</td>
                  <td>{price_refill.get("filled", 0)}</td>
                  <td>{price_refill.get("missing", 0)}</td>
                  <td>{price_refill.get("errors", 0)}</td>
                  <td>{_html(price_refill.get("basis"))}</td>
                  <td>{_html(_price_refill_samples_text(price_refill))}</td>
                </tr>
                <tr>
                  <td>分时事实</td>
                  <td>{_html(minute_refill.get("source") or "未开启")}</td>
                  <td>{minute_refill.get("filled", 0)}</td>
                  <td>{minute_refill.get("missing", 0)}</td>
                  <td>{minute_refill.get("errors", 0)}</td>
                  <td>{_html(minute_refill.get("basis"))}</td>
                  <td>{_html(_refill_samples_text(minute_refill, "filled_samples"))}</td>
                </tr>
                <tr>
                  <td>交易日历</td>
                  <td>{_html(calendar_refill.get("source") or "未开启")}</td>
                  <td>交易日{calendar_refill.get("open_dates_filled", 0)}；T+2补日{calendar_refill.get("filled", 0)}</td>
                  <td>{calendar_refill.get("missing", 0)}</td>
                  <td>{calendar_refill.get("errors", 0)}</td>
                  <td>{_html(calendar_refill.get("basis"))}</td>
                  <td>{_html(_refill_samples_text(calendar_refill, "open_date_samples") + "；" + _refill_samples_text(calendar_refill, "filled_samples"))}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>
        <div class="summary-grid two">
          <div><dt>可用决策日</dt><dd>{_html('、'.join((coverage.get('available_dates') or [])[:18]))}</dd></div>
          <div><dt>缺失日期</dt><dd>{_html(missing_preview)}</dd></div>
        </div>
        <div class="diagnosis-tables">
          <details>
            <summary><strong>原日报最终动作分布</strong><span>只按T0旧链路最终动作统计</span></summary>
            <div class="table-scroll"><table><thead><tr><th>动作</th><th>天数</th><th>日期</th></tr></thead><tbody>{_render_distribution_rows(summary.get("action_distribution"), summary.get("action_dates"))}</tbody></table></div>
          </details>
          <details>
            <summary><strong>旧链路动作分布</strong><span>保留原始结果作对照</span></summary>
            <div class="table-scroll"><table><thead><tr><th>动作</th><th>天数</th><th>日期</th></tr></thead><tbody>{_render_distribution_rows(summary.get("legacy_action_distribution"), summary.get("legacy_action_dates"))}</tbody></table></div>
          </details>
          <details>
            <summary><strong>旧动作 vs 纸面复核对象</strong><span>纸面对象不覆盖T0最终动作</span></summary>
            <div class="table-scroll tall"><table><thead><tr><th>日期</th><th>旧链路动作</th><th>纸面复核对象</th><th>处理</th></tr></thead><tbody>{_render_paper_review_contrast_rows(summary)}</tbody></table></div>
          </details>
          <details>
            <summary><strong>板块优先纸面动作分布</strong><span>看是否恢复出板块资金载体</span></summary>
            <div class="table-scroll"><table><thead><tr><th>纸面动作</th><th>天数</th><th>日期</th></tr></thead><tbody>{_render_distribution_rows(summary.get("paper_action_distribution"), summary.get("paper_action_dates"))}</tbody></table></div>
          </details>
          <details>
            <summary><strong>纸面复核对象/无对象判定</strong><span>纸面主样本不等于原日报最终动作</span></summary>
            <div class="table-scroll tall"><table><thead><tr><th>日期</th><th>判定</th><th>纸面动作</th><th>主样本</th><th>理由</th></tr></thead><tbody>{_render_target_action_rows(summary)}</tbody></table></div>
          </details>
          <details>
            <summary><strong>空仓判定理由分布</strong><span>观察和不参与都没有原日报执行对象，理由分开看</span></summary>
            <div class="table-scroll"><table><thead><tr><th>理由</th><th>天数</th><th>日期</th></tr></thead><tbody>{_render_empty_reason_rows(summary)}</tbody></table></div>
          </details>
          <details>
            <summary><strong>板块优先主样本 T+1 买入复核</strong><span>只看复核标签，不作绩效承诺</span></summary>
            <div class="table-scroll"><table><thead><tr><th>T+1复核</th><th>天数</th><th>日期</th></tr></thead><tbody>{_render_distribution_rows(summary.get("paper_outcome_distribution"), summary.get("paper_outcome_dates"))}</tbody></table></div>
          </details>
          <details>
            <summary><strong>真实可买性分布</strong><span>区分纸面收益和可执行机会</span></summary>
            <div class="table-scroll"><table><thead><tr><th>结论</th><th>天数</th><th>日期</th></tr></thead><tbody>{_render_buyability_summary_rows(summary)}</tbody></table></div>
          </details>
          <details>
            <summary><strong>真实可买性样本</strong><span>9:35前分时路径复核</span></summary>
            <div class="table-scroll tall"><table><thead><tr><th>日期</th><th>主样本</th><th>结论</th><th>理由</th><th>09:35前最高涨幅</th><th>09:35收盘涨幅</th><th>分时条数</th><th>来源</th></tr></thead><tbody>{_render_buyability_sample_rows(summary)}</tbody></table></div>
          </details>
          <details>
            <summary><strong>小账户一手换算</strong><span>50%是策略意图，实际看一手金额</span></summary>
            <div class="table-scroll tall"><table><thead><tr><th>日期</th><th>主样本</th><th>T+1买入窗口</th><th>买入代理价</th><th>一手金额</th><th>一手占账户</th><th>账户可做性</th><th>50%仓位口径</th><th>小账户动作</th></tr></thead><tbody>{_render_small_account_summary_rows(summary)}</tbody></table></div>
          </details>
          <details>
            <summary><strong>代理收益曲线与最大回撤</strong><span>按每个T0样本一次参与复利累乘，仍为日线代理</span></summary>
            <div class="table-scroll"><table><thead><tr><th>T+1买入窗口</th><th>T+2卖出窗口</th><th>样本</th><th>期末净值</th><th>累计代理收益</th><th>最大回撤</th><th>回撤触发样本</th><th>依据</th></tr></thead><tbody>{_render_equity_curve_summary_rows(summary)}</tbody></table></div>
            <div class="table-scroll tall"><table><thead><tr><th>日期链</th><th>主样本</th><th>窗口</th><th>单笔代理表现</th><th>净值</th><th>累计代理收益</th><th>当时回撤</th></tr></thead><tbody>{_render_recommended_curve_rows(summary)}</tbody></table></div>
          </details>
	          <details>
	            <summary><strong>窗口折算收益与指数对照</strong><span>按21个交易日折算参考，指数对比用同区间累计收益差</span></summary>
	            {_render_window_performance_chart(summary)}
	            <div class="table-scroll tall"><table><thead><tr><th>情况</th><th>参与/原样本</th><th>折算周期</th><th>单笔均值</th><th>期末净值</th><th>月度折算参考</th><th>累计代理收益</th><th>252日折算参考</th><th>最大回撤</th><th>跑赢上证</th><th>跑赢创业板</th><th>跑赢科创50</th><th>跑赢中证500</th><th>跑赢全A指数</th><th>跑赢中证1000</th><th>剔除口径</th></tr></thead><tbody>{_render_window_performance_comparison_rows(summary)}</tbody></table></div>
	            <div class="table-scroll"><table><thead><tr><th>指数</th><th>起始T0</th><th>起始点位</th><th>结束T0</th><th>结束点位</th><th>区间涨跌</th><th>覆盖状态</th></tr></thead><tbody>{_render_index_benchmark_rows(summary)}</tbody></table></div>
	          </details>
          <details>
            <summary><strong>买卖时间收益矩阵</strong><span>单元格为平均代理表现；括号逻辑看正收益数/样本数</span></summary>
            <div class="table-scroll">{_trade_window_matrix_summary_grid(summary)}</div>
          </details>
          <details>
            <summary><strong>单笔代理收益前10</strong><span>看最好样本来自哪一天、哪个买卖窗口</span></summary>
            <div class="table-scroll tall"><table><thead><tr><th>序号</th><th>日期链</th><th>主样本</th><th>T+1买入窗口</th><th>T+2卖出窗口</th><th>代理表现</th><th>买入代理价</th><th>卖出代理价</th><th>依据</th></tr></thead><tbody>{_render_trade_return_rank_rows(summary, "top_gain_samples")}</tbody></table></div>
          </details>
          <details>
            <summary><strong>单笔代理亏损前10</strong><span>看最差样本的波动来源</span></summary>
            <div class="table-scroll tall"><table><thead><tr><th>序号</th><th>日期链</th><th>主样本</th><th>T+1买入窗口</th><th>T+2卖出窗口</th><th>代理表现</th><th>买入代理价</th><th>卖出代理价</th><th>依据</th></tr></thead><tbody>{_render_trade_return_rank_rows(summary, "top_loss_samples")}</tbody></table></div>
          </details>
          <details>
            <summary><strong>T+1买入 x T+2卖出窗口矩阵</strong><span>按日线代理统计，不伪装分时成交；补看买点涨幅与接近涨停</span></summary>
            <div class="table-scroll tall"><table><thead><tr><th>T+1买入窗口</th><th>买入价格代理</th><th>T+2卖出窗口</th><th>卖出价格代理</th><th>样本</th><th>平均代理表现</th><th>正收益数</th><th>买点与涨停风险</th><th>较高样本</th><th>较低样本</th><th>依据</th></tr></thead><tbody>{_render_trade_window_matrix_summary_rows(summary)}</tbody></table></div>
          </details>
          <details>
            <summary><strong>T+2卖出窗口统计</strong><span>按日线代理统计，不伪装分时成交</span></summary>
            <div class="table-scroll"><table><thead><tr><th>窗口</th><th>价格代理</th><th>样本</th><th>平均代理表现</th><th>正收益数</th><th>较高样本</th><th>较低样本</th><th>依据</th></tr></thead><tbody>{_render_exit_window_summary_rows(summary)}</tbody></table></div>
          </details>
          <details>
            <summary><strong>T+1到T+2情绪迁移样本</strong><span>市场情绪与板块情绪复核</span></summary>
            <div class="table-scroll tall"><table><thead><tr><th>日期</th><th>主样本</th><th>T+1市场</th><th>T+1板块</th><th>T+2市场</th><th>T+2板块</th><th>样本内较高窗口</th><th>代理收益</th></tr></thead><tbody>{_render_emotion_transition_rows(summary)}</tbody></table></div>
          </details>
          <details>
            <summary><strong>T0推演与T+2校准</strong><span>先做交易预案，再用事实校准</span></summary>
            <div class="table-scroll tall"><table><thead><tr><th>对象</th><th>T0推演</th><th>样本</th><th>后验校准</th><th>T+2实际分布</th><th>校准结果</th><th>全部窗口表现</th><th>偏离样本窗口</th><th>日期</th></tr></thead><tbody>{_render_emotion_projection_rows(summary)}</tbody></table></div>
          </details>
          <details>
            <summary><strong>0% 归因分布</strong><span>看卡在哪一层</span></summary>
            <div class="table-scroll"><table><thead><tr><th>归因</th><th>天数</th><th>日期</th></tr></thead><tbody>{_render_distribution_rows(summary.get("diagnosis_distribution"), summary.get("diagnosis_dates"))}</tbody></table></div>
          </details>
          <details>
            <summary><strong>首次归零层分布</strong><span>逐层滤网复核</span></summary>
            <div class="table-scroll"><table><thead><tr><th>层级</th><th>天数</th><th>日期</th></tr></thead><tbody>{_render_distribution_rows(summary.get("first_zero_layer_distribution"), summary.get("first_zero_layer_dates"))}</tbody></table></div>
          </details>
          <details>
            <summary><strong>异常错配样本</strong><span>T0不参与但T+1走强</span></summary>
            <div class="table-scroll tall"><table><thead><tr><th>日期</th><th>T0归因</th><th>T+1证据</th></tr></thead><tbody>{_render_mismatch_rows(summary)}</tbody></table></div>
          </details>
	          <details>
	            <summary><strong>新版纸面命中样本</strong><span>后续要逐日校准</span></summary>
	            <div class="table-scroll tall"><table><thead><tr><th>日期</th><th>纸面动作</th><th>主样本</th><th>T+1复核</th><th>样本内较高T+2代理窗口</th><th>代理收益</th><th>T0理由</th></tr></thead><tbody>{_render_paper_hit_rows(summary)}</tbody></table></div>
	          </details>
	        </div>
	        </details>
	      </section>
    """


@lru_cache(maxsize=1)
def _daily_report_reader_style_text():
    template_path = SCRIPT_ROOT / "templates" / "daily_report_markdown_reader.html"
    try:
        template_text = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"回测HTML样式模板缺失，停止生成：{template_path}") from exc
    match = re.search(r"<style>\s*(.*?)\s*</style>", template_text, flags=re.DOTALL)
    if not match:
        raise RuntimeError(f"回测HTML样式模板不完整，停止生成：{template_path}")
    return match.group(1).strip()


_FORWARD_REPLAY_STYLE_OVERRIDES = """
.top {
  margin-bottom: 26px;
}

.subtitle,
.top li {
  color: var(--reader-muted);
  font-size: 14px;
}

.top ul {
  margin: 12px 0 0;
  padding-left: 20px;
  color: var(--reader-muted);
}

.replay-summary {
  margin: 26px 0 26px;
}

.replay-metric-table {
  margin: 14px 0 18px;
}

.chart-tone-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  align-items: center;
  margin-top: 3px;
  color: var(--reader-muted);
  font-size: 12px;
  font-weight: 760;
  line-height: 1.4;
}

.chart-tone-legend span {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.chart-tone-swatch {
  width: 16px;
  height: 8px;
  border-radius: 999px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.72);
}

.chart-tone-swatch.is-interval {
  background: var(--accent-orange);
}

.chart-tone-swatch.is-monthly {
  background: var(--accent-red);
}

.chart-tone-swatch.is-negative {
  background: #07C160;
}

.bear-chart.is-empty,
.chart-empty {
  display: grid;
  place-items: center;
  min-height: 180px;
  margin: 0;
  color: var(--reader-muted);
  font-size: 13px;
  background: var(--reader-surface);
}
""".strip()


def _forward_replay_reader_style():
    base_style = _daily_report_reader_style_text()
    return f"{base_style}\n\n{_FORWARD_REPLAY_STYLE_OVERRIDES}"


def render_forward_replay_html(payload):
    payload = deepcopy(payload) if isinstance(payload, dict) else payload
    payload = _apply_tplus1_actual_to_replay_payload(payload)
    notes = "".join(f"<li>{_html(note)}</li>" for note in payload.get("notes", []))
    scope_remark = ""
    if payload.get("start_date") == "2026-04-01" and payload.get("summary", {}).get("coverage", {}).get("requested_end_date") == "2026-06-12":
        scope_remark = "<p class=\"subtitle\">扩展观察区间，不与主区间同权重；只用于加看 2026-06-08 至 2026-06-12 的新增样本。</p>"
    variant_scope_text = _replay_variant_scope_text(payload)
    variant_scope_row = (
        f"<tr><td>版本口径</td><td>{_html(variant_scope_text)}</td></tr>"
        if variant_scope_text
        else ""
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="artifact" content="sector-forward-replay">
  <title>{_html(_requested_start_date(payload))} 至 {_html(_requested_end_date(payload))} 板块资金扩散前向回测</title>
  <style>
{_forward_replay_reader_style()}
  </style>
</head>
	<body>
	  <main class="bear-shell">
	    <aside class="outline-sidebar">
	      <div class="outline-sticky">
	        <div class="window-controls" aria-hidden="true"><span></span><span></span><span></span></div>
	        <p class="outline-kicker">回测报告</p>
	        <p class="outline-title">板块资金扩散前向回测</p>
	        <nav class="outline-nav" aria-label="报告目录">
	          <a class="is-active" href="#report-scope">区间说明</a>
	          <a href="#replay-summary">回测摘要</a>
	          <a class="level-3" href="#replay-window-matrix">买卖时间矩阵</a>
	          <a class="level-3" href="#replay-window-metrics">区间收益</a>
	          <a class="level-3" href="#replay-window-excess">指数对比</a>
	          <a class="level-3" href="#replay-sample-distribution">样本分布</a>
	          <a class="level-3" href="#replay-equity-curve">净值曲线</a>
	          <a class="level-3" href="#replay-market-breadth">市场底色</a>
	        </nav>
	      </div>
	    </aside>
	    <article class="editor-pane">
	      <div class="reader-document">
	        <header class="reader-header">
	          <h1>板块资金扩散前向回测</h1>
	          <div class="meta">{_html(_requested_start_date(payload))} 至 {_html(_requested_end_date(payload))} · 日线代理 · 非真实分时成交</div>
	        </header>
	        <div class="markdown-body">
	          <section class="top" id="report-scope">
	            <h2 class="bear-section-map">区间说明</h2>
	            <p class="subtitle">用T0事实生成候选与淘汰链，用T+1事实复核买入日表现，再用T+2事实复核三段卖出窗口。T+1和T+2不参与T0候选生成、淘汰链生成或最终动作生成。</p>
	            {scope_remark}
	            <div class="reader-table">
	              <table>
	                <thead><tr><th>项目</th><th>结论</th></tr></thead>
	                <tbody>
	                  <tr><td>样本数</td><td>{payload.get("sample_count", 0)}</td></tr>
	                  <tr><td>请求起始</td><td>{_html(_requested_start_date(payload))}</td></tr>
	                  <tr><td>请求结束</td><td>{_html(_requested_end_date(payload))}</td></tr>
	                  <tr><td>事实链末端</td><td>{_html(payload.get("end_date"))}</td></tr>
	                  <tr><td>待结算日期链</td><td>{_html(_pending_settlement_pairs_text(payload))}</td></tr>
	                  {variant_scope_row}
	                  <tr><td>输出类型</td><td>前向回测</td></tr>
	                </tbody>
	              </table>
	            </div>
	            <ul>{notes}</ul>
	          </section>
	          {_render_replay_summary(payload)}
	        </div>
	      </div>
	    </article>
	  </main>
	  <script type="application/json" id="sector-window-chart-payload">{_json_for_html(_replay_summary_chart_payload(payload))}</script>
	  <script type="application/json" id="sector-forward-replay-payload">{_json_for_html(payload)}</script>
  {_echarts_loader_html()}
  {WINDOW_PERFORMANCE_ECHARTS_SCRIPT}
  {LOCAL_MERMAID_RENDERER_SCRIPT}
</body>
</html>
"""


def save_forward_replay_html(payload, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_forward_replay_html(payload), encoding="utf-8")
    return path


def _parse_pair(text):
    if ":" not in text:
        raise argparse.ArgumentTypeError("日期格式应为 T0:T+1 或 T0:T+1:T+2")
    parts = text.split(":")
    if len(parts) not in {2, 3}:
        raise argparse.ArgumentTypeError("日期格式应为 T0:T+1 或 T0:T+1:T+2")
    for part in parts:
        _date(part)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], parts[1], parts[2]


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成板块资金扩散前向回测 HTML")
    parser.add_argument(
        "--pair",
        action="append",
        type=_parse_pair,
        help="日期，格式：T0:T+1 或 T0:T+1:T+2，例如 2026-06-08:2026-06-09:2026-06-10",
    )
    parser.add_argument(
        "--start-date",
        help="自动发现日期对的起始日期，例如 2026-04-01",
    )
    parser.add_argument(
        "--end-date",
        help="自动发现日期对的结束日期，例如 2026-06-12",
    )
    parser.add_argument(
        "--output",
        default="reports/replay/2026-06-08_2026-06-09_板块资金扩散前向回测.html",
        help="输出 HTML 路径",
    )
    parser.add_argument(
        "--export-prefix",
        help="同时导出 CSV 和 Markdown 摘要的路径前缀，例如 reports/replay/2026-04-01_2026-06-05",
    )
    parser.add_argument(
        "--scope-note",
        default="",
        help="写入 Markdown 摘要的区间说明",
    )
    parser.add_argument(
        "--account-capital",
        type=float,
        default=10000.0,
        help="小账户换算本金，默认10000元",
    )
    parser.add_argument(
        "--lot-size",
        type=int,
        default=100,
        help="一手股数，默认100股",
    )
    parser.add_argument(
        "--tushare-refill",
        action="store_true",
        default=True,
        help="用TuShare优先获取T+1/T+2股票日线价格事实，仅用于后验复核；默认开启",
    )
    parser.add_argument(
        "--no-tushare-refill",
        action="store_false",
        dest="tushare_refill",
        help="关闭TuShare价格优先获取，仅用于排查本地事实覆盖",
    )
    parser.add_argument(
        "--tushare-extend-sell-date",
        action="store_true",
        default=True,
        help="用TuShare交易日历补最后一组T+2卖出日，仅用于后验复核；默认开启",
    )
    parser.add_argument(
        "--no-tushare-extend-sell-date",
        action="store_false",
        dest="tushare_extend_sell_date",
        help="关闭TuShare交易日历补T+2卖出日",
    )
    parser.add_argument(
        "--tushare-minute-refill",
        action="store_true",
        default=True,
        help="用TuShare优先获取T+1股票5分钟分时事实，仅用于真实可买性复核；默认开启",
    )
    parser.add_argument(
        "--no-tushare-minute-refill",
        action="store_false",
        dest="tushare_minute_refill",
        help="关闭TuShare分时事实获取，仅保留日线代理回测",
    )
    parser.add_argument(
        "--tushare-minute-timeout",
        type=float,
        default=3.0,
        help="TuShare分时单次请求超时秒数，默认3秒",
    )
    parser.add_argument(
        "--tushare-minute-max-errors",
        type=int,
        default=5,
        help="TuShare分时连续错误达到该次数后停止继续请求，默认5次",
    )
    parser.add_argument(
        "--tushare-index-context-refill",
        action="store_true",
        default=True,
        help="用TuShare优先补齐导出表里的T0科创50、中证500历史指数背景；默认开启",
    )
    parser.add_argument(
        "--no-tushare-index-context-refill",
        action="store_false",
        dest="tushare_index_context_refill",
        help="关闭导出表T0科创50、中证500历史指数补齐",
    )
    args = parser.parse_args(argv)
    loader = _cached_loader(load_daily_report_data_for_forward_replay)
    price_refill = build_tushare_daily_price_refill() if args.tushare_refill else None
    index_context_refill = build_tushare_index_context_refill() if args.tushare_index_context_refill else None
    minute_refill = (
        build_tushare_minute_price_refill(
            timeout_seconds=args.tushare_minute_timeout,
            max_errors=args.tushare_minute_max_errors,
        )
        if args.tushare_minute_refill
        else None
    )
    trade_calendar_refill = build_tushare_open_trade_date_refill() if args.tushare_extend_sell_date else None
    discovery = None
    if args.start_date or args.end_date:
        if not args.start_date or not args.end_date:
            parser.error("--start-date and --end-date must be provided together")
        pairs, discovery = discover_forward_replay_pairs(
            args.start_date,
            args.end_date,
            loader=loader,
            trade_calendar_refill=trade_calendar_refill,
        )
        if args.pair:
            pairs.extend(args.pair)
    else:
        pairs = args.pair or []
    if not pairs:
        parser.error("请提供 --pair，或同时提供 --start-date 与 --end-date")
    payload = build_forward_replay_payload(
        pairs,
        loader=loader,
        discovery=discovery,
        price_refill=price_refill,
        minute_refill=minute_refill,
        trade_calendar_refill=trade_calendar_refill,
        account_capital=args.account_capital,
        lot_size=args.lot_size,
    )
    _apply_index_context_refill_to_payload(payload, index_context_refill)
    path = save_forward_replay_html(payload, args.output)
    print(path)
    if args.export_prefix:
        artifacts = save_forward_replay_csv_and_summary(
            payload,
            args.export_prefix,
            loader=loader,
            scope_note=args.scope_note,
            index_context_refill=index_context_refill,
        )
        print(artifacts["csv"])
        print(artifacts["summary"])


if __name__ == "__main__":
    main()
