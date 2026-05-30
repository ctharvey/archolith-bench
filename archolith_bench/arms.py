"""Experiment arm registry for archolith-bench.

Arms isolate each layer's contribution through named configurations
that map to proxy /admin/config overrides.

| Arm                | Filter (L0-L2) | Proxy assembly (L4)            | What it proves            |
|--------------------|-----------------|---------------------------------|---------------------------|
| direct             | off             | off                             | Baseline                  |
| filter_only        | on              | off                             | Filter token savings      |
| proxy_only         | off             | on (baseline compression)      | Context engine no filter  |
| proxy_plus_filter  | on              | on (filter as engine)          | Full-stack headline       |
| proxy_typed_state  | on              | on + typed work state           | Typed state continuity    |
| proxy_state_snippets| on             | on + exact snippet injection    | Snippet continuity        |
"""

from __future__ import annotations


ARM_DEFINITIONS = {
    "direct": {
        "label": "Direct (baseline)",
        "filter_enabled": False,
        "proxy_enabled": False,
        "config_overrides": {},
    },
    "filter_only": {
        "label": "Filter only",
        "filter_enabled": True,
        "proxy_enabled": False,
        "config_overrides": {
            "rtk_enabled": False,
        },
    },
    "proxy_only": {
        "label": "Proxy only (baseline assembly)",
        "filter_enabled": False,
        "proxy_enabled": True,
        "config_overrides": {
            "rtk_enabled": False,
        },
    },
    "proxy_plus_filter": {
        "label": "Proxy + filter (full stack)",
        "filter_enabled": True,
        "proxy_enabled": True,
        "config_overrides": {
            "rtk_enabled": True,
        },
    },
    "proxy_typed_state": {
        "label": "Proxy + typed state",
        "filter_enabled": True,
        "proxy_enabled": True,
        "config_overrides": {
            "rtk_enabled": True,
            "assembly_mode": "typed_state",
        },
    },
    "proxy_state_snippets": {
        "label": "Proxy + state snippets",
        "filter_enabled": True,
        "proxy_enabled": True,
        "config_overrides": {
            "rtk_enabled": True,
            "assembly_mode": "state_snippets",
        },
    },
}


ARMS = dict(ARM_DEFINITIONS)

PROXY_FAMILY_ARMS = [k for k in ARMS if ARMS[k]["proxy_enabled"]]