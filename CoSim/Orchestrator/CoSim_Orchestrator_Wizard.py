#!/usr/bin/env python
"""
Prompt-based wizard wrapper for CoSim_Vtype_Orchestrator_simple_RT.py.

Keeps the same core behavior (SUMO vType rebuild + JSON mapping generation),
while adding an interactive setup flow for paths and configurable knobs.
"""

import argparse
import json
import os
import xml.etree.ElementTree as ET

import CoSim_Vtype_Orchestrator_simple_RT as base


def _strip_wrapping_quotes(s):
    if s is None:
        return s
    t = str(s).strip()
    if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
        return t[1:-1].strip()
    return t


def _parse_bool(raw, default):
    if raw is None:
        return default
    v = str(raw).strip().lower()
    if v in ("", "default"):
        return default
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    raise ValueError("Expected true/false value")


def _ask(prompt, default=None):
    if default is None:
        s = input(f"{prompt}: ").strip()
        return _strip_wrapping_quotes(s)
    s = input(f"{prompt} [{default}]: ").strip()
    return default if s == "" else _strip_wrapping_quotes(s)


def _ask_bool(prompt, default):
    raw = _ask(prompt, "true" if default else "false")
    return _parse_bool(raw, default)


def _ask_int(prompt, default, min_value=None):
    raw = _ask(prompt, str(default))
    val = int(raw)
    if min_value is not None and val < min_value:
        raise ValueError(f"Expected integer >= {min_value}")
    return val


def _ask_float(prompt, default, min_open=None):
    raw = _ask(prompt, str(default))
    val = float(raw)
    if min_open is not None and val <= min_open:
        raise ValueError(f"Expected number > {min_open}")
    return val


def _resolve_routes_path(sumo_path):
    p = _strip_wrapping_quotes(sumo_path)
    p = os.path.abspath(os.path.expanduser(p))
    if os.path.isdir(p):
        # Flexible discovery: accept any *.rou.xml in the folder.
        # Prefer "scenario.rou.xml" for backward compatibility; otherwise
        # choose the lexicographically first candidate for deterministic behavior.
        candidates = [
            os.path.join(p, name)
            for name in os.listdir(p)
            if name.lower().endswith(".rou.xml") and os.path.isfile(os.path.join(p, name))
        ]
        if not candidates:
            raise FileNotFoundError(
                f"No SUMO routes file (*.rou.xml) found in folder: {p}"
            )
        preferred = os.path.join(p, "scenario.rou.xml")
        p = preferred if preferred in candidates else sorted(candidates)[0]
    if not os.path.isfile(p):
        raise FileNotFoundError(f"SUMO routes not found: {p}")
    # Basic guardrail to catch accidental TestRun or non-XML files early.
    if not p.lower().endswith(".xml"):
        raise ValueError(
            f"SUMO routes path must point to an XML file (typically scenario.rou.xml), got: {p}"
        )
    return p


def _resolve_sumocfg_path(routes_path):
    """
    Resolve SUMO .sumocfg with robust naming:
      1) <routes_base>.sumocfg (same basename as *.rou.xml)
      2) scenario.sumocfg
      3) any *.sumocfg (lexicographically first)
    """
    routes_path = os.path.abspath(routes_path)
    folder = os.path.dirname(routes_path)
    routes_name = os.path.basename(routes_path)
    routes_base = routes_name[:-8] if routes_name.lower().endswith(".rou.xml") else os.path.splitext(routes_name)[0]

    same_base = os.path.join(folder, f"{routes_base}.sumocfg")
    if os.path.isfile(same_base):
        return same_base

    scenario_cfg = os.path.join(folder, "scenario.sumocfg")
    if os.path.isfile(scenario_cfg):
        return scenario_cfg

    cfg_candidates = [
        os.path.join(folder, name)
        for name in os.listdir(folder)
        if name.lower().endswith(".sumocfg") and os.path.isfile(os.path.join(folder, name))
    ]
    if cfg_candidates:
        return sorted(cfg_candidates)[0]

    raise FileNotFoundError(
        f"No SUMO config file (*.sumocfg) found near routes file: {routes_path}"
    )


def _validate_routes_xml(routes_path):
    """
    Validate that routes_path is a parseable SUMO routes XML file.
    """
    try:
        tree = ET.parse(routes_path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise ValueError(
            f"Invalid SUMO routes XML at '{routes_path}'. "
            f"Expected scenario.rou.xml, but parsing failed: {e}"
        ) from e

    if root is None or root.tag != "routes":
        raise ValueError(
            f"Invalid SUMO routes XML at '{routes_path}'. Root tag must be <routes>, got <{root.tag if root is not None else 'None'}>."
        )


def _find_project_root_from_testrun(testrun_path):
    cur = os.path.abspath(os.path.dirname(testrun_path))
    while True:
        if os.path.isdir(os.path.join(cur, "Data")) and os.path.isdir(os.path.join(cur, "src")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    raise FileNotFoundError(f"Could not infer CarMaker project root from TestRun path: {testrun_path}")


def _parse_roi(raw):
    if raw is None:
        return None
    v = str(raw).strip().lower()
    if v in ("", "none", "null"):
        return None
    r = float(v)
    if r <= 0.0:
        raise ValueError("ROI radius must be > 0")
    return r


# Defaults aligned with BR692 CoSim/cosim_vehicle_mapping.json (native_cosim contract).
_DEFAULTS = {
    "cosim_enable": True,
    "sumo_gui": False,
    "SUMO_lights": True,
    "sumo_substeps": 100,
    "sumo_step_length_s": 0.1,
    "rt_bridge_hz": 1000.0,
    "cosim_advance_sync": True,
    "cosim_ego_predict_horizon_s": 0.1,
    "rt_target_ip": "192.168.0.241",
    "rt_host_rx_enable": True,
    "rt_host_rx_port": 50051,
    "rt_host_rx_timeout_s": 0.5,
    "rt_ego_tx_enable": True,
    "rt_ego_tx_ip": "192.168.0.22",
    "rt_ego_tx_port": 50052,
    "rt_ego_tx_decimation": 1,
    "rt_actor_tx_decimation": 1,
    "actor_enabled": False,
    "cosim_logging_enabled": False,
    "roi": 200.0,
    "sumo_home": "",  # optional; Cosim_bridge spawn → <sumo_home>/bin/sumo.exe
}


def _default_ipg_paths():
    """Prefer CM 14.1.1 Traffic Template / Vehicle roots; fall back to discovered install."""
    if hasattr(base, "discover_ipg_carmaker_roots"):
        return base.discover_ipg_carmaker_roots("14.1.1")
    return base.IPG_VEHICLE_TEMPLATE_ROOT, base.IPG_EGO_VEHICLE_ROOT


def _parse_args():
    default_templates, default_ego = _default_ipg_paths()
    d = _DEFAULTS

    p = argparse.ArgumentParser(
        description="Interactive CoSim orchestrator wizard (RT schema compatible).",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  Interactive wizard (recommended):\n"
            "    python CoSim_Orchestrator_Wizard.py\n\n"
            "  Non-interactive with defaults/flags:\n"
            "    python CoSim_Orchestrator_Wizard.py --no-wizard --testrun \"C:\\\\...\\\\Data\\\\TestRun\\\\CM_Sumo\" --sumo-routes \"C:\\\\...\\\\SUMO\"\n\n"
            "  RT-focused tuning example:\n"
            "    python CoSim_Orchestrator_Wizard.py --no-wizard --sumo-step-length-s 0.1 --sumo-substeps 100 --rt-bridge-hz 1000\n\n"
            "Tips:\n"
            "  - In --no-wizard mode, --testrun and --sumo-routes are mandatory.\n"
            "  - --sumo-routes accepts either scenario.rou.xml or its containing folder.\n"
            "  - If --output-json is omitted, output defaults to <project>/CoSim/cosim_vehicle_mapping.json.\n"
            "  - Use --roi none to disable ROI-based recycling."
        ),
    )
    p.add_argument("--no-wizard", action="store_true", help="Run non-interactive; requires --testrun and --sumo-routes.")
    p.add_argument("--testrun", default=None, help="Path to CarMaker TestRun file (required with --no-wizard).")
    p.add_argument("--sumo-routes", default=None, help="Path to SUMO scenario.rou.xml or containing folder (required with --no-wizard).")
    p.add_argument("--ipg-template-root", default=default_templates, help="IPG Traffic Template root.")
    p.add_argument("--ipg-ego-root", default=default_ego, help="IPG Vehicle root for ego file.")
    p.add_argument("--output-json", default=None, help="Output mapping JSON path. Default: <project>/CoSim/cosim_vehicle_mapping.json")

    p.add_argument("--cosim-enable", default="true" if d["cosim_enable"] else "false", choices=["true", "false"])
    p.add_argument("--sumo-gui", default="true" if d["sumo_gui"] else "false", choices=["true", "false"])
    p.add_argument(
        "--sumo-home",
        default=d["sumo_home"],
        help="Optional SUMO install root for Cosim_bridge (empty = omit / use env PATH).",
    )
    p.add_argument("--sumo-lights", default="true" if d["SUMO_lights"] else "false", choices=["true", "false"], help="Enable SUMO light mapping.")
    p.add_argument("--sumo-substeps", type=int, default=d["sumo_substeps"], help="CarMaker cycles between SUMO steps.")
    p.add_argument("--sumo-step-length-s", type=float, default=d["sumo_step_length_s"], help="SUMO step length in seconds.")
    p.add_argument("--cosim-advance-sync", default="true" if d["cosim_advance_sync"] else "false", choices=["true", "false"])
    p.add_argument("--cosim-ego-predict-horizon-s", type=float, default=d["cosim_ego_predict_horizon_s"])
    p.add_argument("--rt-target-ip", default=d["rt_target_ip"], help="RT target IP (host→RT traffic TX).")
    p.add_argument("--roi", default=str(int(d["roi"]) if float(d["roi"]).is_integer() else d["roi"]), help="ROI radius meters or 'none'.")

    p.add_argument("--rt-bridge-hz", type=float, default=d["rt_bridge_hz"], help="rt_bridge_phase2 rate [Hz].")
    p.add_argument("--rt-host-rx-enable", default="true" if d["rt_host_rx_enable"] else "false", choices=["true", "false"])
    p.add_argument("--rt-host-rx-port", type=int, default=d["rt_host_rx_port"])
    p.add_argument("--rt-host-rx-timeout-s", type=float, default=d["rt_host_rx_timeout_s"])
    p.add_argument("--rt-ego-tx-enable", default="true" if d["rt_ego_tx_enable"] else "false", choices=["true", "false"])
    p.add_argument("--rt-ego-tx-ip", default=d["rt_ego_tx_ip"])
    p.add_argument("--rt-ego-tx-port", type=int, default=d["rt_ego_tx_port"])
    p.add_argument("--rt-ego-tx-decimation", type=int, default=d["rt_ego_tx_decimation"])
    p.add_argument("--rt-actor-tx-decimation", type=int, default=d["rt_actor_tx_decimation"])
    p.add_argument("--actor-enabled", default="true" if d["actor_enabled"] else "false", choices=["true", "false"])
    p.add_argument("--cosim-logging-enabled", default="true" if d["cosim_logging_enabled"] else "false", choices=["true", "false"])
    return p.parse_args()


def _collect_config(args):
    cfg = {
        "testrun": _strip_wrapping_quotes(args.testrun),
        "sumo_routes": _strip_wrapping_quotes(args.sumo_routes),
        "ipg_template_root": _strip_wrapping_quotes(args.ipg_template_root),
        "ipg_ego_root": _strip_wrapping_quotes(args.ipg_ego_root),
        "output_json": _strip_wrapping_quotes(args.output_json),
        "cosim_enable": _parse_bool(args.cosim_enable, _DEFAULTS["cosim_enable"]),
        "sumo_gui": _parse_bool(args.sumo_gui, _DEFAULTS["sumo_gui"]),
        "sumo_home": _strip_wrapping_quotes(args.sumo_home) or "",
        "sumo_lights": _parse_bool(args.sumo_lights, _DEFAULTS["SUMO_lights"]),
        "sumo_substeps": int(args.sumo_substeps),
        "sumo_step_length_s": float(args.sumo_step_length_s),
        "cosim_advance_sync": _parse_bool(args.cosim_advance_sync, _DEFAULTS["cosim_advance_sync"]),
        "cosim_ego_predict_horizon_s": float(args.cosim_ego_predict_horizon_s),
        "rt_target_ip": args.rt_target_ip,
        "roi": _parse_roi(args.roi),
        "rt_bridge_hz": float(args.rt_bridge_hz),
        "rt_host_rx_enable": _parse_bool(args.rt_host_rx_enable, _DEFAULTS["rt_host_rx_enable"]),
        "rt_host_rx_port": int(args.rt_host_rx_port),
        "rt_host_rx_timeout_s": float(args.rt_host_rx_timeout_s),
        "rt_ego_tx_enable": _parse_bool(args.rt_ego_tx_enable, _DEFAULTS["rt_ego_tx_enable"]),
        "rt_ego_tx_ip": args.rt_ego_tx_ip,
        "rt_ego_tx_port": int(args.rt_ego_tx_port),
        "rt_ego_tx_decimation": int(args.rt_ego_tx_decimation),
        "rt_actor_tx_decimation": int(args.rt_actor_tx_decimation),
        "actor_enabled": _parse_bool(args.actor_enabled, _DEFAULTS["actor_enabled"]),
        "cosim_logging_enabled": _parse_bool(args.cosim_logging_enabled, _DEFAULTS["cosim_logging_enabled"]),
    }

    if not args.no_wizard:
        print("=== CoSim Orchestrator Wizard ===")
        cfg["testrun"] = _ask("CarMaker TestRun path", cfg["testrun"])
        cfg["sumo_routes"] = _ask("SUMO routes path (scenario.rou.xml or folder)", cfg["sumo_routes"])
        cfg["ipg_template_root"] = _ask("IPG Traffic Template root", cfg["ipg_template_root"])
        cfg["ipg_ego_root"] = _ask("IPG Ego Vehicle root", cfg["ipg_ego_root"])
        cfg["output_json"] = _ask(
            "Output JSON path (leave empty for default under project CoSim)",
            cfg["output_json"] if cfg["output_json"] else "",
        )
        cfg["output_json"] = None if cfg["output_json"] == "" else cfg["output_json"]

        cfg["cosim_enable"] = _ask_bool("cosim_enable", cfg["cosim_enable"])
        cfg["sumo_gui"] = _ask_bool("sumo_gui", cfg["sumo_gui"])
        env_sumo = os.environ.get("SUMO_HOME", "")
        sumo_home_default = cfg["sumo_home"] or env_sumo or ""
        cfg["sumo_home"] = _ask(
            "sumo_home (SUMO install root for Cosim_bridge; blank = omit)",
            sumo_home_default,
        )
        cfg["sumo_home"] = (cfg["sumo_home"] or "").strip()
        cfg["sumo_lights"] = _ask_bool("SUMO_lights", cfg["sumo_lights"])
        cfg["sumo_substeps"] = _ask_int("sumo_substeps", cfg["sumo_substeps"], min_value=1)
        cfg["sumo_step_length_s"] = _ask_float("sumo_step_length_s", cfg["sumo_step_length_s"], min_open=0.0)
        cfg["cosim_advance_sync"] = _ask_bool("cosim_advance_sync", cfg["cosim_advance_sync"])
        cfg["cosim_ego_predict_horizon_s"] = _ask_float(
            "cosim_ego_predict_horizon_s", cfg["cosim_ego_predict_horizon_s"], min_open=-1.0
        )
        cfg["rt_target_ip"] = _ask("rt_target_ip", cfg["rt_target_ip"])
        roi_raw = _ask(
            "roi (meters or 'none')",
            "none" if cfg["roi"] is None else str(int(cfg["roi"]) if float(cfg["roi"]).is_integer() else cfg["roi"]),
        )
        cfg["roi"] = _parse_roi(roi_raw)

        cfg["rt_bridge_hz"] = _ask_float("rt_bridge_hz", cfg["rt_bridge_hz"], min_open=0.0)
        cfg["rt_host_rx_enable"] = _ask_bool("rt_host_rx_enable", cfg["rt_host_rx_enable"])
        cfg["rt_host_rx_port"] = _ask_int("rt_host_rx_port", cfg["rt_host_rx_port"], min_value=1)
        cfg["rt_host_rx_timeout_s"] = _ask_float("rt_host_rx_timeout_s", cfg["rt_host_rx_timeout_s"], min_open=0.0)
        cfg["rt_ego_tx_enable"] = _ask_bool("rt_ego_tx_enable", cfg["rt_ego_tx_enable"])
        cfg["rt_ego_tx_ip"] = _ask("rt_ego_tx_ip", cfg["rt_ego_tx_ip"])
        cfg["rt_ego_tx_port"] = _ask_int("rt_ego_tx_port", cfg["rt_ego_tx_port"], min_value=1)
        cfg["rt_ego_tx_decimation"] = _ask_int("rt_ego_tx_decimation", cfg["rt_ego_tx_decimation"], min_value=1)
        cfg["rt_actor_tx_decimation"] = _ask_int(
            "rt_actor_tx_decimation", cfg["rt_actor_tx_decimation"], min_value=1
        )
        cfg["actor_enabled"] = _ask_bool("actor_enabled", cfg["actor_enabled"])
        cfg["cosim_logging_enabled"] = _ask_bool("cosim_logging_enabled", cfg["cosim_logging_enabled"])
    else:
        if not cfg["testrun"] or not cfg["sumo_routes"]:
            raise ValueError(
                "In --no-wizard mode you must provide both --testrun and --sumo-routes."
            )

    if cfg["sumo_substeps"] <= 0:
        raise ValueError("sumo_substeps must be > 0")
    if cfg["sumo_step_length_s"] <= 0.0:
        raise ValueError("sumo_step_length_s must be > 0")
    if not cfg["testrun"]:
        raise ValueError("CarMaker TestRun path is required.")
    if not cfg["sumo_routes"]:
        raise ValueError("SUMO routes path is required.")
    if cfg["rt_bridge_hz"] <= 0.0:
        raise ValueError("rt_bridge_hz must be > 0")
    return cfg


def _run(cfg):
    testrun_path = _strip_wrapping_quotes(cfg["testrun"])
    testrun_path = os.path.abspath(os.path.expanduser(testrun_path))
    if not os.path.isfile(testrun_path):
        raise FileNotFoundError(f"TestRun file not found: {testrun_path}")
    sumo_routes_path = _resolve_routes_path(cfg["sumo_routes"])
    _validate_routes_xml(sumo_routes_path)

    project_root = _find_project_root_from_testrun(testrun_path)
    output_json_path = _strip_wrapping_quotes(cfg["output_json"])
    if not output_json_path:
        output_json_path = os.path.join(project_root, "CoSim", "cosim_vehicle_mapping.json")
    output_json_path = os.path.abspath(os.path.expanduser(output_json_path))
    existing_coordinate_alignment = None
    if os.path.isfile(output_json_path):
        try:
            with open(output_json_path, "r", encoding="utf-8") as prevf:
                prev_json = json.load(prevf)
            prev_ca = prev_json.get("coordinate_alignment")
            if isinstance(prev_ca, dict):
                existing_coordinate_alignment = prev_ca
        except Exception:
            existing_coordinate_alignment = None
    existing_logging = None
    if os.path.isfile(output_json_path):
        try:
            with open(output_json_path, "r", encoding="utf-8") as prevf:
                prev_json = json.load(prevf)
            if "cosim_logging_enabled" in prev_json:
                existing_logging = bool(prev_json["cosim_logging_enabled"])
        except Exception:
            existing_logging = None

    base.IPG_VEHICLE_TEMPLATE_ROOT = os.path.abspath(os.path.expanduser(cfg["ipg_template_root"]))
    base.IPG_EGO_VEHICLE_ROOT = os.path.abspath(os.path.expanduser(cfg["ipg_ego_root"]))
    base.SUMO_ROUTES_PATH = sumo_routes_path

    print("=== cosim_vehicle_orchestrator_wizard ===")
    print(f"Reading TestRun: {testrun_path}")
    print(f"Reading SUMO routes: {sumo_routes_path}")
    print(f"JSON output: {output_json_path}")

    ego_tmpl, traffic_slots_by_index, actor_slots_by_index = base.parse_cm_testrun_for_templates(testrun_path)
    traffic_templates = {v["ipg_name"]: v["template"] for _, v in sorted(traffic_slots_by_index.items())}
    actor_templates = {v["ipg_name"]: v["template"] for _, v in sorted(actor_slots_by_index.items())}

    tree, root, _ = base.parse_sumo_routes(sumo_routes_path)
    ego_dims = base.get_ego_vehicle_dimensions(ego_tmpl) if ego_tmpl else {}
    traffic_tmpls = sorted(set(traffic_templates.values()))
    actor_tmpls = sorted(set(actor_templates.values()))
    all_tmpls = sorted(set(traffic_tmpls + actor_tmpls))
    traffic_dims = {tmpl: base.get_template_dimensions(tmpl) for tmpl in all_tmpls}

    ego_vtype_id, template_to_vtype = base.rebuild_sumo_vtypes_from_ipg_models(root, ego_dims, traffic_dims)

    ego_vehicle = root.find("./vehicle[@id='ego']")
    if ego_vehicle is not None and ego_vtype_id:
        ego_vehicle.set("type", ego_vtype_id)

    traffic_dist_id = None
    # Build traffic mix from the actual IPG traffic pool demography:
    # probability(vType) = slots_of_that_vType / total_traffic_slots.
    traffic_vtype_counts = {}
    for slot_idx in sorted(traffic_slots_by_index.keys()):
        tmpl = traffic_slots_by_index[slot_idx]["template"]
        vid = template_to_vtype.get(tmpl)
        if not vid:
            continue
        traffic_vtype_counts[vid] = traffic_vtype_counts.get(vid, 0) + 1

    if len(traffic_vtype_counts) >= 2:
        traffic_dist_id = "traffic_mix"
        for vd in list(root.findall("vTypeDistribution")):
            if vd.get("id") == traffic_dist_id:
                root.remove(vd)

        # Stable ordering by vType id (car1, car2, car3, ...)
        vtype_ids = sorted(traffic_vtype_counts.keys())
        total_slots = sum(traffic_vtype_counts.values())
        raw_probs = [traffic_vtype_counts[vid] / float(total_slots) for vid in vtype_ids]

        # Build 2-decimal probabilities that always sum exactly to 1.00.
        # We convert to integer "cents" (sum=100), then distribute remainder
        # by largest fractional parts.
        raw_scaled = [p * 100.0 for p in raw_probs]
        prob_cents = [int(x) for x in raw_scaled]  # floor for positive values
        remainder = 100 - sum(prob_cents)
        frac_order = sorted(
            range(len(raw_scaled)),
            key=lambda i: (raw_scaled[i] - prob_cents[i]),
            reverse=True,
        )
        for i in range(remainder):
            prob_cents[frac_order[i % len(frac_order)]] += 1
        probs = [c / 100.0 for c in prob_cents]

        dist = ET.Element("vTypeDistribution")
        dist.set("id", traffic_dist_id)
        dist.set("vTypes", " ".join(vtype_ids))
        dist.set("probabilities", " ".join(f"{p:.2f}" for p in probs))

        insert_pos = 0
        for i, child in enumerate(list(root)):
            if child.tag == "vType":
                insert_pos = i + 1
        root.insert(insert_pos, dist)

    default_flow_vtype = template_to_vtype.get(traffic_tmpls[0]) if traffic_tmpls else None
    for flow in root.findall("flow"):
        ftype = flow.get("type")
        if ftype in ("car", "traffic_mix"):
            if traffic_dist_id is not None:
                flow.set("type", traffic_dist_id)
            elif default_flow_vtype:
                flow.set("type", default_flow_vtype)

    route_ids = [r.get("id") for r in root.findall("route") if r.get("id")]
    first_route_id = route_ids[0] if route_ids else None
    for slot_idx in sorted(actor_slots_by_index.keys()):
        info = actor_slots_by_index[slot_idx]
        actor_id = info["ipg_name"]
        actor_tmpl = info["template"]
        actor_vtype = template_to_vtype.get(actor_tmpl)
        if not actor_vtype or not first_route_id:
            continue
        veh = root.find(f"./vehicle[@id='{actor_id}']")
        if veh is None:
            veh = ET.Element("vehicle")
            veh.set("id", actor_id)
            root.append(veh)
        veh.set("type", actor_vtype)
        veh.set("route", first_route_id)
        if veh.get("depart") is None:
            veh.set("depart", "0.00")

    flow_prefixes = []
    for flow in root.findall("flow"):
        fid = flow.get("id")
        if fid:
            pfx = f"{fid}."
            if pfx not in flow_prefixes:
                flow_prefixes.append(pfx)
    if not flow_prefixes:
        flow_prefixes = ["flow"]

    backup_path = sumo_routes_path + ".bak"
    if not os.path.exists(backup_path):
        os.replace(sumo_routes_path, backup_path)
        print(f"Backed up original routes to: {backup_path}")
    try:
        ET.indent(tree, space="  ", level=0)
    except Exception:
        pass
    tree.write(sumo_routes_path, encoding="utf-8", xml_declaration=True)
    print(f"Updated routes written to: {sumo_routes_path}")

    traffic_slots_json = []
    vtype_to_slot_names = {}
    vtype_to_slot_indices = {}
    for slot_idx in sorted(traffic_slots_by_index.keys()):
        tmpl = traffic_slots_by_index[slot_idx]["template"]
        expected_vtype_id = template_to_vtype.get(tmpl)
        if not expected_vtype_id:
            continue
        dims = traffic_dims.get(tmpl, {})
        traffic_slots_json.append(
            {
                "slot_index": int(slot_idx),
                "ipg_name": traffic_slots_by_index[slot_idx]["ipg_name"],
                "expected_vtype_id": expected_vtype_id,
                "length_m": dims.get("length"),
            }
        )
        vtype_to_slot_names.setdefault(expected_vtype_id, []).append(traffic_slots_by_index[slot_idx]["ipg_name"])
        vtype_to_slot_indices.setdefault(expected_vtype_id, []).append(int(slot_idx))

    actor_instances_json = []
    for slot_idx in sorted(actor_slots_by_index.keys()):
        info = actor_slots_by_index[slot_idx]
        actor_instances_json.append(
            {
                "ipg_name": info["ipg_name"],
                "template": info["template"],
                "vtype_id": template_to_vtype.get(info["template"]),
                "free_motion": info.get("free_motion"),
            }
        )

    vehicles = []
    if ego_tmpl:
        vehicles.append(
            {
                "role": "ego",
                "template": ego_tmpl,
                "vtype_id": ego_vtype_id,
                "length_m": ego_dims.get("length"),
                "width_m": ego_dims.get("width"),
                "height_m": ego_dims.get("height"),
                "vmax_ms": ego_dims.get("vmax_ms"),
                "axmax_ms2": ego_dims.get("axmax_ms2"),
            }
        )
    for tmpl in traffic_tmpls:
        dims = traffic_dims.get(tmpl, {})
        vehicles.append(
            {
                "role": "traffic",
                "template": tmpl,
                "vtype_id": template_to_vtype.get(tmpl),
                "length_m": dims.get("length"),
                "width_m": dims.get("width"),
                "height_m": dims.get("height"),
                "vmax_ms": dims.get("vmax_ms"),
                "axmax_ms2": dims.get("axmax_ms2"),
            }
        )
    for tmpl in actor_tmpls:
        dims = traffic_dims.get(tmpl, {})
        vehicles.append(
            {
                "role": "actor",
                "template": tmpl,
                "vtype_id": template_to_vtype.get(tmpl),
                "length_m": dims.get("length"),
                "width_m": dims.get("width"),
                "height_m": dims.get("height"),
                "vmax_ms": dims.get("vmax_ms"),
                "axmax_ms2": dims.get("axmax_ms2"),
            }
        )

    sumocfg_path = _resolve_sumocfg_path(sumo_routes_path).replace("\\", "/")
    summary = {
        "$schema": "cosim_vehicle_mapping.schema.json",
        "cosim_enable": cfg["cosim_enable"],
        "ego_template": ego_tmpl,
        "sumo_sumocfg_path": sumocfg_path,
        "SUMO_lights": cfg["sumo_lights"],
        "sumo_gui": cfg["sumo_gui"],
        "sumo_substeps": cfg["sumo_substeps"],
        "sumo_step_length_s": cfg["sumo_step_length_s"],
        "rt_bridge_hz": cfg["rt_bridge_hz"],
        "cosim_advance_sync": cfg["cosim_advance_sync"],
        "cosim_ego_predict_horizon_s": cfg["cosim_ego_predict_horizon_s"],
        "rt_target_ip": cfg["rt_target_ip"],
        "rt_host_rx_enable": cfg["rt_host_rx_enable"],
        "rt_host_rx_port": cfg["rt_host_rx_port"],
        "rt_host_rx_timeout_s": cfg["rt_host_rx_timeout_s"],
        "rt_ego_tx_enable": cfg["rt_ego_tx_enable"],
        "rt_ego_tx_ip": cfg["rt_ego_tx_ip"],
        "rt_ego_tx_port": cfg["rt_ego_tx_port"],
        "rt_ego_tx_decimation": cfg["rt_ego_tx_decimation"],
        "rt_actor_tx_decimation": cfg["rt_actor_tx_decimation"],
        "actor_enabled": cfg["actor_enabled"],
        "cosim_logging_enabled": (
            existing_logging if existing_logging is not None else cfg["cosim_logging_enabled"]
        ),
        "roi": cfg["roi"],
        "vehicles": vehicles,
        "template_to_vtype": {"ego": ego_vtype_id, **template_to_vtype},
        "traffic_slots": traffic_slots_json,
        "actor_instances": actor_instances_json,
        "flow_prefixes": flow_prefixes,
        "vtype_slots": vtype_to_slot_names,
        "vtype_slot_indices": vtype_to_slot_indices,
        "coordinate_alignment": (
            existing_coordinate_alignment
            if existing_coordinate_alignment is not None
            else {"g_theta_rad": 0.0, "g_dx": 0.0, "g_dy": 0.0}
        ),
    }
    sumo_home = (cfg.get("sumo_home") or "").strip()
    if sumo_home:
        # Insert after sumo_sumocfg_path for readability.
        items = list(summary.items())
        out = []
        for k, v in items:
            out.append((k, v))
            if k == "sumo_sumocfg_path":
                out.append(("sumo_home", sumo_home.replace("\\", "/")))
        summary = dict(out)

    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as jf:
        json.dump(summary, jf, indent=2)
    print(f"Wrote mapping summary JSON to: {output_json_path}")


def main():
    args = _parse_args()
    cfg = _collect_config(args)
    _run(cfg)


if __name__ == "__main__":
    main()
