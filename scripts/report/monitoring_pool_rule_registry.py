from __future__ import annotations


def build_monitoring_pool_rule_specs(node_builders, enabled_node_keys=None):
    ordered_keys = [
        'main_pool_core_candidates',
        'main_pool_secondary_candidates',
        'secondary_pool_crossline_candidates',
        'secondary_pool_gem_candidates',
        'secondary_pool_generic_candidates',
        'pool_dedup',
    ]
    enabled = set(enabled_node_keys or ordered_keys)
    specs = []
    for key in ordered_keys:
        if key not in enabled:
            continue
        specs.append({'key': key, 'builder': node_builders[key]})
    return specs
