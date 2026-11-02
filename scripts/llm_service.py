from __future__ import annotations

import hashlib
import json
import os
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from storage.database_service import DatabaseService
except Exception:  # pragma: no cover - optional runtime path
    DatabaseService = None

__all__ = [
    "BaseLLMProvider",
    "DeepSeekHTTPProvider",
    "EventAnalysisCache",
    "LLMService",
    "NullProvider",
    "get_llm_client",
    "get_llm_service",
    "get_llm_stats",
    "get_llm_stats_summary",
    "reset_llm_client",
    "reset_llm_service",
    "reset_llm_stats",
]


def _load_local_env_file() -> None:
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for env_path in candidates:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)
        return


_load_local_env_file()
os.environ.setdefault("DEEPSEEK_MODEL", "deepseek-v4-flash")


class EventAnalysisCache:
    ANALYSIS_CONTRACT_VERSION = "llm_event_analysis.v2"
    CACHE_DURATION_DAYS = 5
    CACHE_DURATION_SECONDS = CACHE_DURATION_DAYS * 24 * 60 * 60

    def __init__(self, cache_file: str | None = None):
        self.cache_file = cache_file or str(Path(__file__).resolve().parent.parent / "data" / "event_analysis_cache.json")
        self.cache: Dict[str, Any] = {}
        self._service = self._runtime_cache_service()

    def _runtime_cache_service(self):
        if DatabaseService is None:
            return None
        service = DatabaseService.from_environment()
        checker = getattr(service, "is_postgres_backed", None)
        if callable(checker) and checker():
            return service
        return None

    def _runtime_cache_key(self, event_title: str, event_summary: str = "") -> str:
        return self._make_key(event_title, event_summary)

    def _active_service_entry(self, event_title: str, event_summary: str = "") -> Optional[Dict[str, Any]]:
        if self._service is None:
            return None
        try:
            entry = self._service.get_runtime_cache_entry(
                "llm_event_analysis",
                self._runtime_cache_key(event_title, event_summary),
                "",
            )
        except Exception as error:
            print(f"[EventCache] 读取缓存失败，按未命中继续分析: {error}")
            return None
        if not isinstance(entry, dict):
            return None
        payload = entry.get("payload")
        if not isinstance(payload, dict):
            return None
        if time.time() - float(payload.get("timestamp", 0) or 0) > self.CACHE_DURATION_SECONDS:
            return None
        result = payload.get("result")
        return result if isinstance(result, dict) else None

    def _store_active_service_entry(
        self,
        event_title: str,
        event_summary: str,
        result: Dict[str, Any],
    ) -> None:
        if self._service is None:
            return
        payload = {
            "timestamp": time.time(),
            "title": event_title,
            "summary": event_summary,
            "result": result,
        }
        try:
            self._service.set_runtime_cache_entry(
                "llm_event_analysis",
                self._runtime_cache_key(event_title, event_summary),
                "",
                payload,
                source="llm_service",
                ttl_seconds=self.CACHE_DURATION_SECONDS,
            )
        except Exception as error:
            print(f"[EventCache] 保存缓存失败: {error}")

    def _make_key(self, event_title: str, event_summary: str = "") -> str:
        payload = json.dumps(
            {
                "analysis_contract": self.ANALYSIS_CONTRACT_VERSION,
                "title": str(event_title or "").strip().lower(),
                "summary": str(event_summary or "").strip(),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    def get(self, event_title: str, event_summary: str = "") -> Optional[Dict[str, Any]]:
        key = self._make_key(event_title, event_summary)
        if key in self.cache:
            cached = self.cache.get(key)
            if cached and time.time() - float(cached.get("timestamp", 0)) <= self.CACHE_DURATION_SECONDS:
                result = cached.get("result")
                return result if isinstance(result, dict) else None
            self.cache.pop(key, None)
        service_result = self._active_service_entry(event_title, event_summary)
        if service_result is not None:
            return service_result
        return None

    def set(self, event_title: str, result: Dict[str, Any], event_summary: str = "") -> None:
        key = self._make_key(event_title, event_summary)
        record = {
            "timestamp": time.time(),
            "title": event_title,
            "summary": event_summary,
            "result": result,
        }
        self.cache[key] = record
        self._store_active_service_entry(event_title, event_summary, result)

    def get_stats(self) -> Dict[str, int]:
        if self._service is not None:
            stats = self._service.get_runtime_cache_stats("llm_event_analysis", "")
            return {
                "total_entries": int(stats.get("count") or 0),
                "cache_duration_days": self.CACHE_DURATION_DAYS,
            }
        return {
            "total_entries": len(self.cache),
            "cache_duration_days": self.CACHE_DURATION_DAYS,
        }

    def clear(self) -> None:
        self.cache = {}
        print("[EventCache] 缓存已清空")


class BaseLLMProvider(ABC):
    seed_supported = False

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> str:
        raise NotImplementedError

    def chat_with_metadata(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: float,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        return {
            "content": self.chat(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            ),
            "provider_request_id": "",
            "seed_supported": False,
            "seed": None,
        }


class DeepSeekHTTPProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> str:
        result = self.chat_with_metadata(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return str(result.get("content") or "")

    def chat_with_metadata(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: float,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        import requests

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        choice = (data.get("choices") or [{}])[0] or {}
        message = choice.get("message") or {}
        content = str(message.get("content") or "").strip()
        reasoning_content = str(message.get("reasoning_content") or "").strip()
        finish_reason = str(choice.get("finish_reason") or "").strip()
        if not content and finish_reason == "length" and reasoning_content:
            raise RuntimeError(
                "deepseek reasoning-only length response; increase max_tokens "
                f"(reasoning_len={len(reasoning_content)})"
            )
        return {
            "content": content,
            "provider_request_id": str(data.get("id") or "").strip(),
            "seed_supported": False,
            "seed": None,
        }


class NullProvider(BaseLLMProvider):
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> str:
        return ""


class LLMService:
    DEFAULT_PROVIDER = "deepseek"
    DEFAULT_TIMEOUT = 60.0
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, provider_name: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT):
        if self._initialized:
            return
        self.timeout = timeout
        self.provider_name = (provider_name or os.getenv("LLM_PROVIDER") or self.DEFAULT_PROVIDER).lower()
        self.provider: BaseLLMProvider = self._build_provider(self.provider_name)
        self.model = self._resolve_model(self.provider_name)
        self._stats = self._empty_stats()
        print(f"[LLMService] 初始化完成，provider: {self.provider_name}, model: {self.model}")
        self._initialized = True

    def _empty_stats(self) -> Dict[str, Any]:
        return {
            "call_count": 0,
            "total_time": 0.0,
            "avg_time": 0.0,
            "min_time": float("inf"),
            "max_time": 0.0,
            "errors": 0,
            "empty_responses": 0,
            "provider": self.provider_name,
            "model": self.model,
        }

    def _resolve_model(self, provider_name: str) -> str:
        return os.getenv("DEEPSEEK_MODEL") or "deepseek-v4-flash"

    def _build_provider(self, provider_name: str) -> BaseLLMProvider:
        api_key = os.getenv("DEEPSEEK_API_KEY") or ""
        base_url = os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
        if api_key:
            return DeepSeekHTTPProvider(api_key=api_key, base_url=base_url)
        print("[LLMService] DeepSeek Provider 未配置 API Key，降级为 NullProvider")
        return NullProvider()

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 500,
        max_retries: int = 1,
    ) -> str:
        result = self.chat_with_metadata(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
        )
        return str(result.get("content") or "")

    @property
    def seed_supported(self) -> bool:
        return bool(getattr(self.provider, "seed_supported", False))

    def chat_with_metadata(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 500,
        max_retries: int = 1,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        resolved_max_tokens = max_tokens
        if self.provider_name == "deepseek":
            resolved_max_tokens = max(int(max_tokens or 0), 64)

        for attempt in range(max_retries + 1):
            start_time = time.time()
            try:
                provider_result = self.provider.chat_with_metadata(
                    messages=messages,
                    model=self.model,
                    temperature=temperature,
                    max_tokens=resolved_max_tokens,
                    timeout=self.timeout,
                    seed=seed if self.seed_supported else None,
                )
                elapsed = time.time() - start_time
                if not isinstance(provider_result, dict):
                    provider_result = {"content": provider_result}
                content = str(provider_result.get("content") or "").strip()
                provider_seed_supported = provider_result.get("seed_supported") is True
                provider_effective_config = provider_result.get("effective_config")
                effective_config = (
                    dict(provider_effective_config)
                    if isinstance(provider_effective_config, dict)
                    else {
                        "model": self.model,
                        "temperature": float(temperature),
                        "max_tokens": resolved_max_tokens,
                        "timeout": self.timeout,
                    }
                )
                self._update_stats(elapsed, success=True, empty=not content)
                if not content:
                    if attempt < max_retries:
                        print(f"[LLMService] 空响应，重试 {attempt + 1}/{max_retries}...")
                        time.sleep(1)
                        continue
                    print("[LLMService] 空响应，按正常降级路径处理")
                return {
                    "content": content,
                    "provider_request_id": str(
                        provider_result.get("provider_request_id") or ""
                    ).strip(),
                    "seed_supported": provider_seed_supported,
                    "seed": provider_result.get("seed") if provider_seed_supported else None,
                    "effective_config": effective_config,
                }
            except Exception as error:
                elapsed = time.time() - start_time
                self._update_stats(elapsed, success=False, empty=False)
                if attempt < max_retries:
                    if (
                        self.provider_name == "deepseek"
                        and "reasoning-only length response" in str(error)
                    ):
                        match = re.search(r"reasoning_len=(\d+)", str(error))
                        reasoning_len = int(match.group(1)) if match else 0
                        resolved_max_tokens = max(
                            resolved_max_tokens * 2,
                            reasoning_len + 1024,
                        )
                    print(f"[LLMService] API调用失败 ({elapsed:.2f}s)，重试 {attempt + 1}/{max_retries}: {error}")
                    time.sleep(2)
                    continue
                print(f"[LLMService] API调用失败 ({elapsed:.2f}s): {error}")
                return {
                    "content": "",
                    "provider_request_id": "",
                    "seed_supported": self.seed_supported,
                    "seed": seed if self.seed_supported else None,
                    "effective_config": {
                        "model": self.model,
                        "temperature": float(temperature),
                        "max_tokens": resolved_max_tokens,
                        "timeout": self.timeout,
                    },
                }
        return {
            "content": "",
            "provider_request_id": "",
            "seed_supported": self.seed_supported,
            "seed": seed if self.seed_supported else None,
            "effective_config": {
                "model": self.model,
                "temperature": float(temperature),
                "max_tokens": resolved_max_tokens,
                "timeout": self.timeout,
            },
        }

    def analyze_event_sectors(self, event_title: str, event_summary: str = "") -> Dict[str, Any]:
        full_text = f"{event_title} {event_summary}".strip()
        system_prompt = """你是一个专业的A股板块分析专家，擅长根据财经事件判断相关的A股投资板块。
请严格按照以下JSON格式返回分析结果，不要添加任何解释性文字：
{
    "main_direction": "主要产业链方向",
    "related_sectors": ["细分板块1", "细分板块2", "细分板块3"],
    "trading_logic": "炒作逻辑简述",
    "expectation": "利好/利空/中性",
    "confidence": "高/中/低"
}"""
        prompt = f"""请分析以下财经事件所属的A股产业链方向：

事件内容：{full_text}

可选产业链方向：
- AI应用（AIGC、大模型、智能体、企业软件AI等）
- AI算力（AI芯片、液冷服务器、算力租赁、数据中心等）
- 光通信（CPO、光模块、光纤光缆等）
- 人形机器人
- 新能源（光伏、储能、锂电池、氢能源、绿色燃料、绿电等）
- 半导体（芯片设计、封测、设备材料、电子元器件等）
- 汽车产业链（整车、零部件、智能驾驶、汽车制造机器人等）
- 消费电子（手机、PC、AI PC、可穿戴设备、Computex等）
- 商业航天
- 原油（成品油、油气、OPEC、IEA、大宗能源等）
- 有色金属（铜铝铅锌、贵金属、小金属、LME等）
- 医药医疗（创新药、医疗器械、CXO等）
- 金融流动性（央行公开市场、美联储FOMC、利率、汇率等）
- 宏观经济（经济论坛、宏观数据、顺周期预期等）
- 外贸投资（APEC、贸易部长会议、跨境贸易等）
- 本地生活（美团、外卖、即时零售、酒旅到店等）
- 文旅体育（世界杯、地方足球联赛、体育赛事、文旅消费等）
- 供应链服务（供应链博览会、物流、港口航运等）
- 消费（食品饮料、家电、零售等）
- 房地产（地产开发、建材、家居等）
- 军工
- 其他（仅在完全无法识别时使用）

注意：
1. 不要因为标题里出现“会议/大会/论坛/政策/新规”就归为政策催化。
2. 必须先拆事件主体和产业链对象，例如成品油=原油，Computex=消费电子，LME铅锌=有色金属，绿色燃料=新能源，汽车供应链大会=汽车产业链。

请只返回JSON格式结果，不要添加任何其他内容。"""
        result = self.chat(prompt, system_prompt=system_prompt, max_tokens=300)
        if not result:
            return self._event_sector_fallback("空响应降级")
        try:
            parsed = self._parse_json_response(result)
            return {
                "main_direction": parsed.get("main_direction", "其他"),
                "related_sectors": parsed.get("related_sectors", []),
                "trading_logic": parsed.get("trading_logic", ""),
                "expectation": parsed.get("expectation", "中性"),
                "confidence": parsed.get("confidence", "中"),
            }
        except Exception as error:
            print(f"[LLMService] JSON解析失败: {error}")
            return self._event_sector_fallback(f"解析失败: {str(error)[:80]}")

    def analyze_sector_relationships(self, sector_list: list, context_info: str = "") -> Dict[str, Any]:
        if not sector_list:
            return {"groups": [], "insights": ""}
        sectors_text = "、".join(str(item) for item in sector_list)
        system_prompt = """你是一个专业的A股产业链分析专家。
必须严格返回纯JSON，键名必须是英文：
{
    "groups": [
        {
            "name": "产业链方向名称",
            "sectors": ["板块1", "板块2"],
            "reason": "归类理由（30字以内）",
            "investment_logic": "资金博弈逻辑（50字以内）"
        }
    ],
    "insights": "整体洞察（100字以内）"
}"""
        prompt = f"""请分析以下板块标签的产业链关系：

板块列表：{sectors_text}
上下文：{context_info}

任务：
1. 按产业链关系分组（每组1-3个板块）
2. 给出归类理由和资金博弈逻辑
3. 提供整体洞察

只返回纯JSON，不要markdown标记。"""
        result = self.chat(prompt, system_prompt=system_prompt, max_tokens=1200)
        if not result:
            return {"groups": [], "insights": "空响应降级"}
        try:
            parsed = self._parse_json_response(result)
            groups = parsed.get("groups") or parsed.get("产业链分组") or []
            insights = parsed.get("insights") or parsed.get("整体产业链洞察") or ""
            if not groups and "产业链分组" in parsed:
                for item in parsed["产业链分组"]:
                    groups.append(
                        {
                            "name": item.get("组别", item.get("name", "")),
                            "sectors": item.get("包含板块", item.get("sectors", [])),
                            "reason": item.get("归类理由", item.get("reason", ""))[:50],
                            "investment_logic": item.get("资金博弈逻辑", item.get("investment_logic", ""))[:80],
                        }
                    )
            return {"groups": groups, "insights": str(insights)[:200]}
        except Exception as error:
            print(f"[LLMService] JSON解析失败: {error}")
            return {"groups": [], "insights": "解析失败降级"}

    def adjudicate_calendar_event_news_evidence(
        self,
        event: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        report_date: str = "",
    ) -> Dict[str, Any]:
        if not candidates:
            return {}

        limited_candidates = list(candidates)[:8]
        event_title = str((event or {}).get("title") or "")
        event_date = str((event or {}).get("date") or "")
        event_summary = str((event or {}).get("summary") or "")
        candidate_lines = []
        for idx, candidate in enumerate(limited_candidates):
            title = str(candidate.get("title") or "")[:120]
            source_date = str(candidate.get("source_date") or "")
            evidence_text = str(candidate.get("evidence_text") or "")[:500]
            candidate_lines.append(
                f"[{idx}] title={title}\nsource_date={source_date}\nevidence={evidence_text}"
            )

        system_prompt = """你是A股日报的事件证据审校员。
只判断候选新闻能否作为指定日历事件的同日证据；不要做宽泛联想。
必须严格返回纯JSON，键名必须是英文：
{
    "matched": true,
    "evidence_index": 0,
    "confidence": "高/中/低",
    "match_reason": "30字以内",
    "classification_hint": "可选产业链方向或空字符串",
    "related_sectors": ["细分方向"],
    "policy_evidence": true
}"""
        prompt = f"""报告日期：{report_date}
日历事件：
- 日期：{event_date}
- 标题：{event_title}
- 摘要：{event_summary}

候选新闻：
{chr(10).join(candidate_lines)}

判定要求：
1. matched=true 只在新闻主体、活动名称、公司/机构、时间语境足以确认同一事件时使用。
2. 如果只是共享“大会/论坛/行业/交流/发布”等泛词，必须 matched=false。
3. 如果新闻补足了标题省略的主体且语义能确认同一事件，可以 matched=true。
4. policy_evidence=true 只在候选新闻含官方部门、规则、文件、方案、通知、实施等明确政策文件证据时使用。
5. 不确定时返回 matched=false，confidence=低。

只返回JSON，不要markdown标记。"""
        result = self.chat(prompt, system_prompt=system_prompt, temperature=0.1, max_tokens=900)
        if not result:
            return {}
        try:
            parsed = self._parse_json_response(result)
        except Exception as error:
            print(f"[LLMService] 日历新闻证据判定解析失败: {error}")
            return {}

        raw_index = parsed.get("evidence_index", parsed.get("candidate_index", parsed.get("index", -1)))
        if isinstance(raw_index, bool):
            evidence_index = -1
        else:
            try:
                evidence_index = int(raw_index)
            except (TypeError, ValueError):
                evidence_index = -1
        related_sectors = parsed.get("related_sectors")
        if isinstance(related_sectors, str):
            related_sectors = [item.strip() for item in re.split(r"[、,，/]", related_sectors) if item.strip()]
        elif not isinstance(related_sectors, list):
            related_sectors = []
        raw_confidence = parsed.get("confidence")
        confidence = "" if isinstance(raw_confidence, bool) else str(raw_confidence or "").strip()
        return {
            "matched": parsed.get("matched", False),
            "evidence_index": evidence_index,
            "confidence": confidence,
            "match_reason": str(parsed.get("match_reason") or "").strip()[:120],
            "classification_hint": str(parsed.get("classification_hint") or "").strip()[:40],
            "related_sectors": [str(item).strip() for item in related_sectors if str(item or "").strip()][:5],
            "policy_evidence": parsed.get("policy_evidence", False),
        }

    def analyze_events_batch(
        self,
        events: List[Dict[str, str]],
        batch_size: int = 4,
        progress_callback=None,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        if not events:
            return []
        cache = EventAnalysisCache() if use_cache else None
        cached_results: Dict[int, Dict[str, Any]] = {}
        uncached_events: list[tuple[int, Dict[str, str]]] = []
        for idx, event in enumerate(events):
            title = event.get("title", "")
            summary = event.get("summary", "")
            cached_result = cache.get(title, summary) if cache else None
            if cached_result:
                cached_results[idx] = cached_result
            else:
                uncached_events.append((idx, event))
        if cache and cached_results:
            print(f"      💾 缓存命中 {len(cached_results)}/{len(events)} 个事件，需分析 {len(uncached_events)} 个", flush=True)
        if not uncached_events:
            return [cached_results[i] for i in range(len(events))]

        all_results: List[Any] = [None] * len(events)
        for idx, result in cached_results.items():
            all_results[idx] = result

        total_batches = (len(uncached_events) + batch_size - 1) // batch_size
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            batch_items = uncached_events[start_idx : start_idx + batch_size]
            batch_events = [item[1] for item in batch_items]
            if progress_callback:
                progress_callback(batch_idx + 1, total_batches, len(batch_events))
            else:
                print(f"      🤖 分析第{batch_idx + 1}/{total_batches}批 ({len(batch_events)}个事件)...", flush=True)
            batch_results = self._analyze_events_single_batch(batch_events)
            for item_idx, (original_idx, event) in enumerate(batch_items):
                result = batch_results[item_idx] if item_idx < len(batch_results) else self._event_sector_fallback("结果缺失")
                all_results[original_idx] = result
                if cache:
                    cache.set(event.get("title", ""), result, event.get("summary", ""))
            if not progress_callback:
                print(f"      ✅ 第{batch_idx + 1}/{total_batches}批完成", flush=True)
            if batch_idx < total_batches - 1:
                time.sleep(0.5)
        return [item if isinstance(item, dict) else self._event_sector_fallback("结果缺失") for item in all_results]

    def _analyze_events_single_batch(self, events: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        events_text = "\n".join(f"[{idx + 1}] {event.get('title', '')}" for idx, event in enumerate(events))
        system_prompt = """你是一个专业的A股产业链分析专家。
必须严格使用以下JSON格式返回，键名必须是英文：
{
    "results": [
        {
            "main_direction": "主要产业链方向",
            "related_sectors": ["细分板块1", "细分板块2"],
            "trading_logic": "炒作逻辑（50字以内）",
            "expectation": "利好/利空/中性",
            "confidence": "高/中/低"
        }
    ]
}
可选产业链方向：AI应用、AI算力、光通信、人形机器人、新能源、半导体、汽车产业链、消费电子、商业航天、原油、有色金属、医药医疗、金融流动性、宏观经济、外贸投资、本地生活、文旅体育、供应链服务、消费、房地产、军工、其他。
不要把论坛/会议/大会/政策/新规默认归为政策催化，必须根据事件主体拆到具体产业链。"""
        prompt = f"""请批量分析以下财经事件，识别每个事件涉及的A股产业链方向：

{events_text}

返回纯JSON，包含results数组，顺序与输入事件一致。"""
        result = self.chat(prompt, system_prompt=system_prompt, max_tokens=2000)
        if not result:
            print("[LLMService] 批量分析返回空，回退到单独分析")
            return [self._event_sector_fallback("批量空响应") for _ in events]
        try:
            parsed = self._parse_json_response(result)
            results = parsed.get("results", [])
            if len(results) < len(events):
                results.extend(self._event_sector_fallback("结果缺失") for _ in range(len(events) - len(results)))
            elif len(results) > len(events):
                results = results[: len(events)]
            return results
        except Exception as error:
            print(f"[LLMService] 批量分析解析失败: {error}，回退到单独分析")
            return [self._event_sector_fallback("批量解析失败") for _ in events]

    def _parse_json_response(self, result: str) -> Dict[str, Any]:
        json_str = (result or "").strip()
        if not json_str:
            raise ValueError("empty_response")
        if "```json" in json_str:
            json_str = json_str.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```", 1)[1].split("```", 1)[0].strip()
        return json.loads(json_str)

    def _event_sector_fallback(self, reason: str) -> Dict[str, Any]:
        return {
            "main_direction": "其他",
            "related_sectors": [],
            "trading_logic": reason,
            "expectation": "中性",
            "confidence": "低",
        }

    def _update_stats(self, elapsed: float, success: bool = True, empty: bool = False) -> None:
        self._stats["call_count"] += 1
        self._stats["total_time"] += elapsed
        self._stats["avg_time"] = self._stats["total_time"] / self._stats["call_count"]
        if success:
            self._stats["min_time"] = min(self._stats["min_time"], elapsed)
            self._stats["max_time"] = max(self._stats["max_time"], elapsed)
        else:
            self._stats["errors"] += 1
        if empty:
            self._stats["empty_responses"] += 1

    def get_stats(self) -> Dict[str, Any]:
        return self._stats.copy()

    def get_stats_summary(self) -> str:
        stats = self._stats
        if stats["call_count"] == 0:
            return f"LLM调用: 0次 ({stats['provider']})"
        summary = f"LLM调用: {stats['call_count']}次"
        if stats["errors"] > 0:
            summary += f" (失败{stats['errors']}次)"
        if stats["empty_responses"] > 0:
            summary += f" (空响应{stats['empty_responses']}次)"
        summary += f", provider: {stats['provider']}"
        summary += f", 总耗时: {stats['total_time']:.2f}s"
        summary += f", 平均: {stats['avg_time']:.2f}s"
        return summary

    def reset_stats(self) -> None:
        self._stats = self._empty_stats()


_llm_service = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


get_llm_client = get_llm_service


def reset_llm_service() -> None:
    global _llm_service
    LLMService._instance = None
    _llm_service = None


reset_llm_client = reset_llm_service


def get_llm_stats() -> Dict[str, Any]:
    return get_llm_service().get_stats()


def get_llm_stats_summary() -> str:
    return get_llm_service().get_stats_summary()


def reset_llm_stats() -> None:
    get_llm_service().reset_stats()
