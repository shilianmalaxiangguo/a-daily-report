const escapeText = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
	        "&": "&amp;",
	        "<": "&lt;",
	        ">": "&gt;",
	        '"': "&quot;",
	        "'": "&#39;",
	      })[char]);

	      const cssValue = (name, fallback) => {
	        const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
	        return value || fallback;
	      };

		      const chartTone = {
		        text: cssValue("--reader-text", "#2d1712"),
		        muted: cssValue("--reader-muted", "#6c4537"),
		        line: cssValue("--reader-line", "rgba(108, 69, 55, 0.14)"),
		        red: cssValue("--accent-red", "#e73922"),
		        extremeRed: cssValue("--signal-extreme", "#F92722"),
		        extremeText: cssValue("--signal-extreme-text", "#FFFFFF"),
		        iceBlue: cssValue("--signal-ice", "#2364aa"),
		        deepIceBlue: cssValue("--signal-deep-ice", "#12365a"),
		        green: "#07C160",
		        fluorescentPurple: cssValue("--signal-fluorescent-purple", "#B000FF"),
		        gold: cssValue("--accent-orange", "#ff8a1f"),
		        surface: "#FFFFFF",
		      };

	      const numberValue = value => nullableNumber(value) ?? 0;
	      const nullableNumber = value => typeof value === "number" && Number.isFinite(value) ? value : null;
	      const formatAmount = value => nullableNumber(value) === null ? "待确认" : `${Number(value).toFixed(2)}亿`;
	      const formatSignedAmount = value => {
	        if (nullableNumber(value) === null) return "待确认";
	        const number = numberValue(value);
	        return `${number >= 0 ? "+" : "-"}${Math.abs(number).toFixed(2)}亿`;
	      };
	      const formatPct = value => nullableNumber(value) === null ? "待确认" : `${Number(value).toFixed(1)}%`;
	      const formatSignedPct = (value) => {
	        if (nullableNumber(value) === null) {
	          return "待确认";
	        }
	        const number = numberValue(value);
	        return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
	      };
		      const formatCount = (value) => `${numberValue(value).toFixed(0)}只`;
		      const compactAxisLabel = (value) => {
		        const text = String(value ?? "");
		        return text.length > 10 ? `${text.slice(0, 9)}…` : text;
		      };
		      const compactDateLabel = (value) => String(value ?? "").replace(/^\d{4}-/, "");

		      
const baseChartOption = () => ({
	        backgroundColor: "transparent",
	        animation: !matchMedia("(prefers-reduced-motion: reduce)").matches,
 animationDuration: 520,
	        animationEasing: "cubicOut",
	        textStyle: {
	          color: chartTone.text,
	          fontFamily: '"Avenir Next", "PingFang SC", sans-serif',
	        },
	        tooltip: {
	          trigger: "item",
	          confine: true,
	          appendToBody: false,
	          backgroundColor: "rgba(255,255,255,0.96)",
	          borderColor: chartTone.line,
	          borderWidth: 1,
	          padding: [8, 10],
	          textStyle: {
	            color: chartTone.text,
	            fontSize: 12,
	            lineHeight: 18,
	          },
	          extraCssText: "max-width:260px;white-space:normal;box-shadow:0 10px 28px rgba(32,24,18,.12);border-radius:10px;",
	        },
	        grid: {
	          left: 108,
	          right: 46,
	          top: 18,
	          bottom: 28,
	          containLabel: false,
	        },
	      });

		      const marketTrendXAxis = (items) => ({
		        type: "category",
		        data: items.map((item) => item.date),
		        axisLabel: { color: chartTone.muted, formatter: compactDateLabel, rotate: items.length > 12 ? 34 : 0 },
		        axisTick: { show: false },
		        axisLine: { lineStyle: { color: chartTone.line } },
		      });

		      const renderT0MarketBreadthChart = (node, payload) => {
		        const items = Array.isArray(payload?.items) ? payload.items : [];
		        if (!items.length || !window.echarts) {
		          return null;
		        }
		        const breadthDownTone = "#07C160";
		        const breadthDownAlertTone = chartTone.fluorescentPurple;
		        const chart = window.echarts.init(node, null, { renderer: "canvas" });
		        chart.setOption({
		          ...baseChartOption(),
		          color: [chartTone.red, breadthDownTone, chartTone.iceBlue, chartTone.fluorescentPurple],
		          legend: {
		            type: "scroll",
		            top: 4,
		            left: "center",
		            textStyle: { color: chartTone.muted, fontSize: 11 },
		          },
		          grid: { left: 58, right: 58, top: 58, bottom: 48, containLabel: false },
		          tooltip: {
		            ...baseChartOption().tooltip,
		            trigger: "axis",
		            axisPointer: { type: "shadow" },
		            formatter: (params) => {
		              const first = Array.isArray(params) ? params[0] : params;
		              const item = items[first?.dataIndex] || {};
		              const upCount = nullableNumber(item.up_count);
		              const downCount = nullableNumber(item.down_count);
		              const allAChange = nullableNumber(item.all_a_change_pct);
		              const newHighShare = nullableNumber(item.new_high_share_pct);
		              return [
		                `<strong>${escapeText(item.date || "")}</strong>`,
			                `上涨家数：${escapeText(upCount === null ? "未记录" : `${Math.round(upCount)}家`)}`,
			                `下跌家数：${escapeText(downCount === null ? "未记录" : `${Math.round(downCount)}家`)}`,
			                `全A涨跌幅：${escapeText(allAChange === null ? "未记录" : formatSignedPct(allAChange))}`,
			                `创新高全A占比：${escapeText(newHighShare === null ? "未记录" : formatPct(newHighShare))}`,
		              ].join("<br>");
		            },
		          },
		          xAxis: marketTrendXAxis(items),
		          yAxis: [
		            {
		              type: "value",
		              name: "家数",
		              min: (value) => Math.min(-5200, value.min),
		              nameTextStyle: { color: chartTone.muted },
		              axisLabel: { color: chartTone.muted, formatter: (value) => Math.abs(value) },
		              splitLine: { lineStyle: { color: chartTone.line, type: "dashed" } },
		            },
		            {
		              type: "value",
		              name: "涨跌幅/占比",
		              nameTextStyle: { color: chartTone.muted },
		              axisLabel: { color: chartTone.muted, formatter: (value) => `${value}%` },
		              splitLine: { show: false },
		            },
		          ],
		          series: [
		            {
		              name: "上涨家数",
		              type: "bar",
		              stack: "breadth",
		              barMaxWidth: 20,
		              itemStyle: { borderRadius: [7, 7, 0, 0] },
		              data: items.map((item) => nullableNumber(item.up_count)),
		            },
		            {
		              name: "下跌家数",
		              type: "bar",
		              stack: "breadth",
		              barMaxWidth: 20,
		              itemStyle: {
		                borderRadius: [0, 0, 7, 7],
		                color: (params) => params.value < -5000 ? breadthDownAlertTone : breadthDownTone,
		              },
		              markLine: {
		                silent: true,
		                symbol: ["none", "none"],
		                lineStyle: { color: breadthDownTone, type: "dashed", width: 1.5, opacity: 0.82 },
		                label: {
		                  show: true,
		                  formatter: "4000+下跌",
		                  position: "insideEndTop",
		                  color: chartTone.green,
		                  fontSize: 11,
		                  fontWeight: 700,
		                  backgroundColor: chartTone.surface,
		                  borderRadius: 3,
		                  padding: [2, 4],
		                },
		                data: [
		                  { yAxis: -4000 },
		                  {
		                    yAxis: -5000,
		                    lineStyle: { color: breadthDownAlertTone },
		                    label: { formatter: "5000+下跌", color: breadthDownAlertTone },
		                  },
		                ],
		              },
		              data: items.map((item) => {
		                const value = nullableNumber(item.down_count);
		                return value === null ? null : -Math.abs(value);
		              }),
		            },
		            {
		              name: "全A涨跌幅",
		              type: "line",
		              yAxisIndex: 1,
		              smooth: 0.18,
		              showSymbol: false,
		              lineStyle: { width: 2.2 },
		              data: items.map((item) => nullableNumber(item.all_a_change_pct)),
		            },
		            {
		              name: "创新高占比",
		              type: "line",
		              yAxisIndex: 1,
		              smooth: 0.18,
		              showSymbol: false,
		              lineStyle: { width: 2.2, color: chartTone.fluorescentPurple },
		              itemStyle: { color: chartTone.fluorescentPurple },
		              data: items.map((item) => nullableNumber(item.new_high_share_pct)),
		            },
		          ],
		        });
		        return chart;
		      };

		      
const renderCffexPositionTrendChart = (node, payload) => {
		        const items = Array.isArray(payload?.items) ? payload.items : [];
		        if (!items.length || !window.echarts) {
		          return null;
		        }
		        const targetDate = items.some((item) => item.date === payload?.target_date)
		          ? payload.target_date
		          : "";
		        const defaultWindow = Math.min(60, items.length);
		        let visibleItems = items.slice(-defaultWindow);
		        const handAxisLabel = (value) => {
		          const number = Number(value);
		          return Math.abs(number) >= 10000
		            ? `${(number / 10000).toFixed(1)}万`
		            : `${Math.round(number)}`;
		        };
		        const formatHand = (value) => {
		          const number = nullableNumber(value);
		          if (number === null) return "未记录";
		          return `${number > 0 ? "+" : ""}${Math.round(number).toLocaleString("zh-CN")}手`;
		        };
		        const formatBalance = (value) => {
		          const number = nullableNumber(value);
		          return number === null ? "未记录" : `${Math.round(number).toLocaleString("zh-CN")}手`;
		        };
		        const formatNotional = (value) => {
		          const number = nullableNumber(value);
		          return number === null ? "未记录" : `${number.toFixed(2)}亿元`;
		        };
		        const targetMarkLine = (showLabel) => ({
		          silent: true,
		          symbol: "none",
		          lineStyle: { color: chartTone.gold, type: "dashed", width: 1.4, opacity: 0.9 },
		          label: showLabel ? {
		            show: true,
		            formatter: "目标日",
		            position: "insideEndTop",
		            color: chartTone.muted,
		            fontSize: 11,
		            backgroundColor: chartTone.surface,
		            padding: [2, 4],
		          } : { show: false },
		          data: [{ xAxis: targetDate, name: "目标日" }],
		        });
		        const xAxis = (gridIndex, showLabels) => ({
		          type: "category",
		          gridIndex,
		          data: visibleItems.map((item) => item.date),
		          boundaryGap: gridIndex === 1,
		          axisLabel: {
		            show: showLabels,
		            color: chartTone.muted,
		            formatter: compactDateLabel,
		            interval: visibleItems.length > 40 ? 5 : visibleItems.length > 20 ? 2 : 0,
		            hideOverlap: true,
		            rotate: visibleItems.length > 12 ? 34 : 0,
		          },
		          axisTick: { show: false },
		          axisLine: { lineStyle: { color: chartTone.line } },
		        });
		        const chart = window.echarts.init(node, null, { renderer: "canvas" });
		        chart.setOption({
		          ...baseChartOption(),
		          color: [chartTone.iceBlue, chartTone.red, chartTone.fluorescentPurple],
		          legend: {
		            type: "scroll",
		            data: ["中信名义净空", "中信净空日变", "前20榜单净空差"],
		            top: 4,
		            left: "center",
		            selectedMode: true,
		            itemWidth: 12,
		            itemHeight: 8,
		            itemGap: 8,
		            pageIconSize: 10,
		            textStyle: { color: chartTone.muted, fontSize: 11 },
		          },
		          title: [
		            { text: "中信代客名义净空（亿元）", left: 68, top: 44 },
		            { text: "中信代客净空日变（手，仅复核）", left: 68, top: 206 },
		            { text: "前20榜单净空差（手）", left: 68, top: 368 },
		          ].map((item) => ({
		            ...item,
		            textStyle: { color: chartTone.text, fontSize: 12, fontWeight: 800 },
		          })),
		          grid: [
		            { left: 70, right: 28, top: 76, height: 102, containLabel: false },
		            { left: 70, right: 28, top: 238, height: 102, containLabel: false },
		            { left: 70, right: 28, top: 400, height: 102, containLabel: false },
		          ],
		          axisPointer: { link: [{ xAxisIndex: [0, 1, 2] }] },
		          tooltip: {
		            ...baseChartOption().tooltip,
		            trigger: "axis",
		            axisPointer: { type: "line" },
		            formatter: (params) => {
		              const first = Array.isArray(params) ? params[0] : params;
		              const item = visibleItems[first?.dataIndex] || {};
		              return [
		                `<strong>${escapeText(item.date || "")}${item.date === targetDate ? " · 目标日" : ""}</strong>`,
		                `中信代客名义净空：${escapeText(formatNotional(item.member_net_short_notional_yi))}`,
		                `中信代客净空日变：${escapeText(formatHand(item.member_net_short_change))}`,
		                `前20榜单净空差：${escapeText(formatBalance(item.top20_cross_section_net_short))}`,
		                `较前一披露日：${escapeText(formatHand(item.top20_cross_section_change))}`,
		                "榜单跨日变化包含会员或披露范围变化。",
		              ].join("<br>");
		            },
		          },
		          xAxis: [xAxis(0, false), xAxis(1, false), xAxis(2, true)],
		          yAxis: [
		            {
		              type: "value",
		              gridIndex: 0,
		              scale: true,
		              axisLabel: { color: chartTone.muted, formatter: (value) => `${Math.round(value)}亿` },
		              splitLine: { lineStyle: { color: chartTone.line, type: "dashed" } },
		            },
		            {
		              type: "value",
		              gridIndex: 1,
		              axisLabel: { color: chartTone.muted, formatter: handAxisLabel },
		              splitLine: { lineStyle: { color: chartTone.line, type: "dashed" } },
		            },
		            {
		              type: "value",
		              gridIndex: 2,
		              scale: true,
		              axisLabel: { color: chartTone.muted, formatter: handAxisLabel },
		              splitLine: { lineStyle: { color: chartTone.line, type: "dashed" } },
		            },
		          ],
		          series: [
		            {
		              name: "中信名义净空",
		              type: "line",
		              xAxisIndex: 0,
		              yAxisIndex: 0,
		              smooth: 0.2,
		              showSymbol: false,
		              connectNulls: false,
		              lineStyle: { width: 2.2, color: chartTone.iceBlue },
		              itemStyle: { color: chartTone.iceBlue },
		              data: visibleItems.map((item) => nullableNumber(item.member_net_short_notional_yi)),
		              ...(targetDate ? { markLine: targetMarkLine(true) } : {}),
		            },
		            {
		              name: "中信净空日变",
		              type: "bar",
		              xAxisIndex: 1,
		              yAxisIndex: 1,
		              barMaxWidth: 15,
		              data: visibleItems.map((item) => nullableNumber(item.member_net_short_change)),
		              itemStyle: {
		                color: (params) => nullableNumber(params.value) < 0 ? chartTone.green : chartTone.red,
		                borderRadius: (params) => nullableNumber(params.value) < 0 ? [0, 0, 4, 4] : [4, 4, 0, 0],
		              },
		              markLine: {
		                silent: true,
		                symbol: "none",
		                lineStyle: { color: chartTone.line, type: "dashed", width: 1.2 },
		                label: { show: false },
		                data: [
		                  { yAxis: 0 },
		                  ...(targetDate ? [{ xAxis: targetDate, name: "目标日", lineStyle: { color: chartTone.gold } }] : []),
		                ],
		              },
		            },
		            {
		              name: "前20榜单净空差",
		              type: "line",
		              xAxisIndex: 2,
		              yAxisIndex: 2,
		              smooth: 0.2,
		              showSymbol: false,
		              connectNulls: false,
		              lineStyle: { width: 2.2, color: chartTone.fluorescentPurple },
		              itemStyle: { color: chartTone.fluorescentPurple },
		              data: visibleItems.map((item) => nullableNumber(item.top20_cross_section_net_short)),
		              ...(targetDate ? { markLine: targetMarkLine(false) } : {}),
		            },
		          ],
		        });

		        const control = node.closest("[data-bear-chart-card]")
		          ?.querySelector('[data-bear-chart-window-control="cffex_position_trend"]');
		        if (control) {
		          const buttons = Array.from(control.querySelectorAll("button[data-window-size]"));
		          const setWindow = (requestedSize) => {
		            const size = Math.min(Math.max(Number(requestedSize) || 60, 1), items.length);
		            visibleItems = items.slice(-size);
		            chart.setOption({
		              xAxis: [xAxis(0, false), xAxis(1, false), xAxis(2, true)],
		              series: [
		                { name: "中信名义净空", data: visibleItems.map((item) => nullableNumber(item.member_net_short_notional_yi)) },
		                { name: "中信净空日变", data: visibleItems.map((item) => nullableNumber(item.member_net_short_change)) },
		                { name: "前20榜单净空差", data: visibleItems.map((item) => nullableNumber(item.top20_cross_section_net_short)) },
		              ],
		            });
		            buttons.forEach((button) => {
		              button.setAttribute(
		                "aria-pressed",
		                String(Number(button.dataset.windowSize) === Number(requestedSize)),
		              );
		            });
		          };
		          buttons.forEach((button) => {
		            button.addEventListener("click", () => setWindow(button.dataset.windowSize));
		          });
		          setWindow(60);
		        }
		        return chart;
		      };

		      
const renderLhbNetFlowChart = (node, payload) => {
	        const items = Array.isArray(payload?.items) ? payload.items : [];
	        if (!items.length || !window.echarts) {
	          return null;
	        }
	        const maxAbs = Math.max(1, ...items.map((item) => Math.abs(numberValue(item.amount))));
	        const bound = Math.ceil(maxAbs * 1.2);
	        const chart = window.echarts.init(node, null, { renderer: "canvas" });
	        chart.setOption({
	          ...baseChartOption(),
	          grid: { left: 132, right: 82, top: 20, bottom: 34, containLabel: false },
	          xAxis: {
	            type: "value",
	            min: -bound,
	            max: bound,
            axisLabel: { color: chartTone.muted, formatter: (value) => value === 0 ? "" : `${Math.abs(value)}亿` },
	            splitLine: { lineStyle: { color: chartTone.line, type: "dashed" } },
	          },
	          yAxis: {
	            type: "category",
	            inverse: true,
	            data: items.map((item) => `${item.side === "buy" ? "买" : "卖"} ${nullableNumber(item.rank) === null ? "待确认" : Math.round(nullableNumber(item.rank))}. ${item.name}`),
	            axisLabel: { color: chartTone.text, formatter: compactAxisLabel },
	            axisTick: { show: false },
	            axisLine: { show: false },
	          },
	          tooltip: {
	            ...baseChartOption().tooltip,
	            formatter: (params) => {
	              const item = params.data.item || {};
	              return [
	                `<strong>${escapeText(item.name)}(${escapeText(item.code)})</strong>`,
	                `方向：${item.side === "buy" ? "净买入" : "净流出"}`,
	                `净额：${escapeText(formatSignedAmount(item.amount))}`,
	                `板块：${escapeText(item.sector || "待确认")}`,
	                `涨跌幅：${escapeText(formatSignedPct(item.change_pct))}`,
	                item.status ? `状态：${escapeText(item.status)}` : "",
	              ].filter(Boolean).join("<br>");
	            },
	          },
	          series: [{
	            name: "龙虎榜净额",
	            type: "bar",
	            barWidth: 12,
	            data: items.map((item) => ({ value: nullableNumber(item.amount), item })),
	            itemStyle: {
	              borderRadius: [7, 7, 7, 7],
	              color: (params) => numberValue(params.data.item.amount) >= 0 ? chartTone.red : chartTone.green,
	            },
	            label: {
	              show: true,
	              position: "right",
	              color: chartTone.muted,
	              formatter: (params) => formatSignedAmount(params.value),
	            },
	            markLine: {
	              silent: true,
	              symbol: "none",
	              label: { color: chartTone.muted, formatter: "0轴" },
	              lineStyle: { color: chartTone.line },
	              data: [{ xAxis: 0 }],
	            },
	          }],
	        });
	        return chart;
	      };

		      