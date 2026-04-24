from __future__ import annotations

from report.monitoring_pool_rule_registry import build_monitoring_pool_rule_specs
from report.monitoring_pool_rule_runtime import run_monitoring_pool_rule_nodes


def _normalize_candidate(stock, source_pool, bucket):
    stock = stock or {}
    return {
        'stock_name': stock.get('name', '') or stock.get('stock_name', ''),
        'stock_code': stock.get('code', '') or stock.get('stock_code', ''),
        'source_pool': source_pool,
        'source_bucket': bucket,
        'selected_date': stock.get('selected_date', ''),
    }


def build_main_pool_core_candidates(context, node_meta=None, exports=None):
    return {'main_pool': [_normalize_candidate(item, 'main', 'core_stocks') for item in (context.get('core_stocks', []) or [])]}


def build_main_pool_secondary_candidates(context, node_meta=None, exports=None):
    return {'main_pool': [_normalize_candidate(item, 'main', 'secondary_stocks') for item in (context.get('secondary_stocks', []) or [])]}


def build_secondary_pool_crossline_candidates(context, node_meta=None, exports=None):
    return {'secondary_pool': [_normalize_candidate(item, 'secondary', 'crossline_observation_stocks') for item in (context.get('crossline_observation_stocks', []) or [])]}


def build_secondary_pool_gem_candidates(context, node_meta=None, exports=None):
    return {'secondary_pool': [_normalize_candidate(item, 'secondary', 'gem_observation_stocks') for item in (context.get('gem_observation_stocks', []) or [])]}


def build_secondary_pool_generic_candidates(context, node_meta=None, exports=None):
    return {'secondary_pool': [_normalize_candidate(item, 'secondary', 'generic_watch_stocks') for item in (context.get('generic_watch_stocks', []) or [])]}


def build_pool_dedup(context, node_meta=None, exports=None):
    return {}


MONITORING_POOL_RULE_BUILDERS = {
    'main_pool_core_candidates': build_main_pool_core_candidates,
    'main_pool_secondary_candidates': build_main_pool_secondary_candidates,
    'secondary_pool_crossline_candidates': build_secondary_pool_crossline_candidates,
    'secondary_pool_gem_candidates': build_secondary_pool_gem_candidates,
    'secondary_pool_generic_candidates': build_secondary_pool_generic_candidates,
    'pool_dedup': build_pool_dedup,
}


def collect_monitoring_pool_candidates_via_nodes(context, enabled_node_keys=None):
    specs = build_monitoring_pool_rule_specs(MONITORING_POOL_RULE_BUILDERS, enabled_node_keys=enabled_node_keys)
    result = run_monitoring_pool_rule_nodes(specs, context or {})
    return result['exports']
