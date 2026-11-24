#!/usr/bin/env python
# cosim_vehicle_orchestrator.py
#
# First step:
# - Hardcoded paths to:
#   - CarMaker TestRun (CM_Sumo)
#   - IPG vehicle catalog directory (for later use)
#   - SUMO routes file (scenario.rou.xml)
# - Discover which IPG vehicle templates are used (ego + Traffic.*)
# - Ensure SUMO has vTypes for each of those templates
# - Write a JSON summary with the IPG vehicle templates (for future use in C++)

import argparse
import os
import re
import json
import xml.etree.ElementTree as ET
from collections import OrderedDict

# ---------------------------------------------------------------------------
# HARD-CODED PATHS (adjust to your machine; later we’ll turn these into flags)
# ---------------------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# CarMaker project root (contains Data/, CoSim/, src/, …)
CM_PROJECT_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, "Progetto CM v2"))
CM_TESTRUN_PATH = os.path.join(CM_PROJECT_DIR, "Data", "TestRun", "CM_Sumo")


def discover_ipg_carmaker_roots(prefer_version="14.1.1"):
    """
    Locate IPG Traffic Template and Vehicle roots without hardcoding an old CM version.

    Search order:
      1) CARMAKER_DIR / CM_ROOT / IPG_CARMAKER env (install root or .../win64-x.y.z)
      2) C:/IPG/carmaker/win64-* installs (prefer prefer_version, else newest)
    Returns (traffic_template_root, ego_vehicle_root).
    """
    def _ver_key(win64_dir):
        m = re.search(r"win64-(\d+)\.(\d+)\.(\d+)", os.path.basename(win64_dir))
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    def _as_install_root(path):
        if not path:
            return None
        p = os.path.abspath(os.path.expanduser(str(path).strip().strip('"')))
        if not p:
            return None
        # Accept either install root (win64-x.y.z) or its Data subfolder.
        if os.path.basename(p).lower() == "data":
            p = os.path.dirname(p)
        if os.path.isdir(os.path.join(p, "Data", "Traffic", "Template")):
            return p
        # Env may point at C:/IPG/carmaker — pick a child below.
        if os.path.isdir(p) and not os.path.basename(p).lower().startswith("win64-"):
            return None
        return p if os.path.isdir(p) else None

    candidates = []
    for key in ("CARMAKER_DIR", "CM_ROOT", "IPG_CARMAKER"):
        root = _as_install_root(os.environ.get(key))
        if root:
            candidates.append(root)

    base = r"C:\IPG\carmaker"
    if os.path.isdir(base):
        for name in os.listdir(base):
            if name.lower().startswith("win64-"):
                root = _as_install_root(os.path.join(base, name))
                if root:
                    candidates.append(root)

    # Unique, newest first
    uniq = []
    seen = set()
    for c in sorted(candidates, key=_ver_key, reverse=True):
        if c not in seen:
            seen.add(c)
            uniq.append(c)

    preferred = None
    for c in uniq:
        if prefer_version and prefer_version in os.path.basename(c):
            preferred = c
            break
    chosen = preferred or (uniq[0] if uniq else None)
    if not chosen:
        # Last-resort placeholders (will fail clearly if paths missing)
        chosen = r"C:\IPG\carmaker\win64-14.1.1"

    traffic = os.path.join(chosen, "Data", "Traffic", "Template")
    ego = os.path.join(chosen, "Data", "Vehicle")
    return traffic, ego


# Base directory for IPG vehicle templates / ego vehicles (CM 14.1.1+ aware)
IPG_VEHICLE_TEMPLATE_ROOT, IPG_EGO_VEHICLE_ROOT = discover_ipg_carmaker_roots("14.1.1")
# SUMO scenario (routes); scenario.sumocfg is expected in the same directory for C++ / bridge.
SUMO_ROUTES_PATH = os.path.normpath(
    os.path.join(_SCRIPT_DIR, "SUMO", "scenario.rou.xml")
)

COSIM_DIR = os.path.join(CM_PROJECT_DIR, "CoSim")
OUTPUT_JSON_PATH = os.path.join(COSIM_DIR, "cosim_vehicle_mapping.json")


def _sumo_sumocfg_path_for_json():
    """Absolute path to scenario.sumocfg as forward slashes (for cosim JSON + CarMaker)."""
    d = os.path.dirname(os.path.normpath(SUMO_ROUTES_PATH))
    return os.path.join(d, "scenario.sumocfg").replace("\\", "/")


# ---------------------------------------------------------------------------
# Helpers: parse TestRun
# ---------------------------------------------------------------------------

def parse_cm_testrun_for_templates(testrun_path):
    """
    Parse the CM_Sumo TestRun text file, return:
      - ego_template: string or None
      - traffic_slots_by_index: dict[idx] -> {ipg_name, template, free_motion}
      - actor_slots_by_index: dict[idx] -> {ipg_name, template, free_motion}
    """
    ego_template = None  # e.g. "Examples/Demo_Audi_R8" or Car.Template.FName
    traffic_slots_by_index = {}  # key: Traffic.<i> index, value: {"ipg_name": "...", "template": "..."}

    name_re = re.compile(r"^Traffic\.(\d+)\.Name\s*=\s*(\S+)")
    tmpl_re = re.compile(r"^Traffic\.(\d+)\.Template\.FName\s*=\s*(\S+)")
    free_re = re.compile(r"^Traffic\.(\d+)\.FreeMotion\s*=\s*(\S+)")

    # Ego vehicle/template:
    # - Modern TestRuns often have: Vehicle = Examples/Demo_Audi_R8
    # - Some have: Car.Template.FName = 1_Vehicles/IPG_CompanyCar_2018_Blue
    ego_tmpl_re   = re.compile(r"^Car\.Template\.FName\s*=\s*(\S+)")
    ego_vehicle_re = re.compile(r"^Vehicle\s*=\s*(\S+)")

    # Temporary storage while we see Name and Template in separate lines
    temp_by_index = {}

    with open(testrun_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            m_ego = ego_tmpl_re.match(line)
            if m_ego:
                ego_template = m_ego.group(1)
                continue

            m_veh = ego_vehicle_re.match(line)
            if m_veh and ego_template is None:
                ego_template = m_veh.group(1)
                continue

            m_name = name_re.match(line)
            if m_name:
                idx, name = m_name.groups()
                d = temp_by_index.setdefault(idx, {})
                d["name"] = name
                continue

            m_tmpl = tmpl_re.match(line)
            if m_tmpl:
                idx, tmpl = m_tmpl.groups()
                d = temp_by_index.setdefault(idx, {})
                d["template"] = tmpl
                continue
            m_free = free_re.match(line)
            if m_free:
                idx, freev = m_free.groups()
                d = temp_by_index.setdefault(idx, {})
                d["free_motion"] = freev
                continue

    # Build mapping Traffic index -> {ipg_name, template}
    actor_slots_by_index = {}
    for idx in sorted(temp_by_index, key=lambda s: int(s)):
        d = temp_by_index[idx]
        name = d.get("name")
        tmpl = d.get("template")
        fm_raw = d.get("free_motion")
        fm = None
        if fm_raw is not None:
            try:
                fm = int(float(fm_raw))
            except Exception:
                fm = None
        if name and tmpl:
            rec = {"ipg_name": name, "template": tmpl, "free_motion": fm}
            # Actor rule (phase-1): non-ego, non-free-motion traffic entities are treated as roleplay actors.
            if fm == 0 and name.lower() != "ego":
                actor_slots_by_index[int(idx)] = rec
            else:
                traffic_slots_by_index[int(idx)] = rec

    return ego_template, traffic_slots_by_index, actor_slots_by_index


# ---------------------------------------------------------------------------
# Helpers: parse & patch SUMO routes
# ---------------------------------------------------------------------------

def parse_sumo_routes(routes_path):
    """
    Parse scenario.rou.xml, return:
      - root Element
      - dict of vType_id -> vType Element
    """
    tree = ET.parse(routes_path)
    root = tree.getroot()

    vtypes = {}
    for v in root.findall("vType"):
        vid = v.get("id")
        if vid:
            vtypes[vid] = v
    return tree, root, vtypes


def ensure_ego_vtype(root, existing_vtypes, ego_template, ego_length_m):
    """
    Ensure there is a dedicated vType for the ego vehicle, named 'ego_car',
    with the correct length from the IPG ego template.

    Returns the vType id used for ego ("ego_car") or None if no ego_template.
    """
    if not ego_template:
        return None

    ego_vtype_id = "ego_car"

    if ego_vtype_id in existing_vtypes:
        v = existing_vtypes[ego_vtype_id]
    else:
        # Try to reuse some defaults from existing 'car' vType if present
        defaults = {
            "accel": "1.5",
            "decel": "4.5",
            "sigma": "0.5",
            "length": "4.5",
            "maxSpeed": "13.89",
            "guiShape": "passenger",
        }
        if "car" in existing_vtypes:
            car = existing_vtypes["car"]
            for k in defaults:
                if car.get(k) is not None:
                    defaults[k] = car.get(k)

        # Create ego_car vType but insert it next to existing vTypes
        v = ET.Element("vType")
        v.set("id", ego_vtype_id)
        for k, val in defaults.items():
            v.set(k, val)
        existing_vtypes[ego_vtype_id] = v
        # Will insert v into root below

    # Re-position ego_car so that all <vType> elements are grouped at the top:
    # <vType id="car" .../>
    # <vType id="ego_car" .../>
    children = list(root)
    # Find insertion point: after the last existing vType
    insert_pos = 0
    for i, child in enumerate(children):
        if child.tag == "vType":
            insert_pos = i + 1
    # If v already in children, remove it first
    if v in children:
        root.remove(v)
    root.insert(insert_pos, v)

    # Update ego length if we have it
    if ego_length_m is not None:
        v.set("length", f"{ego_length_m:.3f}")

    return ego_vtype_id


# ---------------------------------------------------------------------------
# Helpers: find and parse IPG vehicle templates for dimensions
# ---------------------------------------------------------------------------

def find_template_file(tmpl_fname):
    """
    Given an IPG template FName like "1_Vehicles/BMW_5_2017", try to locate the
    corresponding .tpl file under IPG_VEHICLE_TEMPLATE_ROOT.
    """
    base_dir = IPG_VEHICLE_TEMPLATE_ROOT
    # Try direct path first
    direct_path = os.path.join(base_dir, tmpl_fname)

    # Case 1: tmpl_fname points to a directory that contains a .tpl
    if os.path.isdir(direct_path):
        vehicle_name = os.path.basename(direct_path)
        for root, dirs, files in os.walk(direct_path):
            for file in files:
                file_base, ext = os.path.splitext(file)
                if file_base == vehicle_name and ext.lower() == ".tpl":
                    return os.path.join(root, file)

    # Case 2: direct file (some templates have no extension)
    if os.path.isfile(direct_path):
        return direct_path

    # Case 3: search by basename across the template tree (either .tpl or no extension)
    vehicle_name = os.path.basename(tmpl_fname)
    vehicle_base = os.path.splitext(vehicle_name)[0]
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            file_base, ext = os.path.splitext(file)
            if file_base == vehicle_base and (ext.lower() == ".tpl" or ext == ""):
                return os.path.join(root, file)

    return None


def get_template_dimensions(tmpl_fname):
    """
    Return a dict with basic physical specs parsed from an IPG traffic template:
      - length/width/height in meters (from Basics.Dimension)
      - vmax_ms in m/s (from LVD.vMax if present; supports km/h or m/s heuristics)
      - axmax_ms2 in m/s^2 (from LVD.AxMax if present)

    Returns {} if not found / parse failed.
    """
    tpl_path = find_template_file(tmpl_fname)
    if not tpl_path:
        return {}

    try:
        with open(tpl_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        dims = {}
        m = re.search(r"Basics\.Dimension\s*=\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", content)
        if m:
            dims["length"] = abs(float(m.group(1)))
            dims["width"] = abs(float(m.group(2)))
            dims["height"] = abs(float(m.group(3)))

        # Classification / visualization (optional)
        m = re.search(r"\bObjectClass\s*=\s*([A-Za-z0-9_+-]+)", content)
        if m:
            dims["object_class"] = m.group(1).strip()

        # IPG template color is usually 0..1 floats: "Color = 1.0 0.0 0.0"
        m = re.search(r"\bColor\s*=\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", content)
        if m:
            try:
                r = float(m.group(1)); g = float(m.group(2)); b = float(m.group(3))
                # clamp
                r = max(0.0, min(1.0, r))
                g = max(0.0, min(1.0, g))
                b = max(0.0, min(1.0, b))
                dims["color_rgb01"] = (r, g, b)
            except Exception:
                pass

        # Physical capabilities (optional)
        # Examples seen in IPG files: "LVD.vMax = 250" (often km/h) or "LVD.vMax = 55.56" (m/s)
        m = re.search(r"\bLVD\.vMax\s*=\s*([-\d.]+)", content)
        if m:
            vmax_raw = float(m.group(1))
            # Heuristic: values > 120 are almost certainly km/h (typical road vehicles).
            dims["vmax_ms"] = vmax_raw / 3.6 if vmax_raw > 120.0 else vmax_raw

        m = re.search(r"\bLVD\.AxMax\s*=\s*([-\d.]+)", content)
        if m:
            dims["axmax_ms2"] = float(m.group(1))

        return dims
    except Exception:
        return {}


def get_ego_vehicle_dimensions(ego_vehicle_fname):
    """
    Ego vehicles live under IPG_EGO_VEHICLE_ROOT (e.g. Data/Vehicle/Examples/Demo_Audi_R8).
    Extract basic dimensions from:
        Vehicle.OuterSkin = xFront yLeft zUp xRear yRight zDown
    and compute:
        length = xRear - xFront
        width  = yLeft - yRight
        height = zDown - zUp
    Returns {} if not found.
    """
    if not ego_vehicle_fname:
        return {}

    # Normalize separators and join to base
    rel = ego_vehicle_fname.replace("\\", "/")
    ego_path = os.path.join(IPG_EGO_VEHICLE_ROOT, *rel.split("/"))
    if not os.path.isfile(ego_path):
        return {}

    try:
        with open(ego_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        m = re.search(r"Vehicle\.OuterSkin\s*=\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", content)
        if not m:
            return {}
        x_front = float(m.group(1))
        y_left  = float(m.group(2))
        z_up    = float(m.group(3))
        x_rear  = float(m.group(4))
        y_right = float(m.group(5))
        z_down  = float(m.group(6))

        length = x_rear - x_front
        width  = y_left - y_right
        height = z_down - z_up
        dims = {
            "length": abs(length),
            "width": abs(width),
            "height": abs(height),
        }

        # Optional physical capabilities if present in the vehicle file
        m = re.search(r"\bLVD\.vMax\s*=\s*([-\d.]+)", content)
        if m:
            vmax_raw = float(m.group(1))
            dims["vmax_ms"] = vmax_raw / 3.6 if vmax_raw > 120.0 else vmax_raw

        m = re.search(r"\bLVD\.AxMax\s*=\s*([-\d.]+)", content)
        if m:
            dims["axmax_ms2"] = float(m.group(1))

        return dims
    except Exception:
        return {}


def ensure_traffic_vtypes(root, existing_vtypes, traffic_templates):
    """
    Ensure that each distinct non-ego IPG traffic template has a corresponding
    SUMO vType, mainly so that the scenario file documents which vehicle
    templates are in play.

    We:
      - Use the basename of the template as vType id (e.g. "IPG_CompanyCar_2018_Blue").
      - Reuse accel/decel/sigma/maxSpeed/guiShape from 'car' if present.
      - Set vType length from IPG template dimensions if available.
    """
    # Prepare defaults (reused for all)
    defaults = {
        "accel": "1.5",
        "decel": "4.5",
        "sigma": "0.5",
        "length": "4.5",
        "maxSpeed": "13.89",
        "guiShape": "passenger",
    }
    if "car" in existing_vtypes:
        car = existing_vtypes["car"]
        for k in defaults:
            if car.get(k) is not None:
                defaults[k] = car.get(k)

    for tmpl in sorted(traffic_templates):
        # NOTE: this helper is kept for backwards compatibility but no longer used.
        # vTypes are rebuilt via rebuild_sumo_vtypes_from_ipg_models().
        pass


def rebuild_sumo_vtypes_from_ipg_models(root, ego_dims, traffic_template_dims):
    """
    Rebuild <vType> section so it contains ONLY:
      - vType id="ego_car"
      - vType id="car1", "car2", ... (one per distinct traffic template)

    Returns:
      (ego_vtype_id, template_to_vtype_id)
    """
    # Remove all existing vType elements (including legacy 'car')
    for v in list(root.findall("vType")):
        root.remove(v)

    # Determine insertion point (before first non-vType element)
    children = list(root)
    insert_pos = 0
    for i, child in enumerate(children):
        if child.tag != "vType":
            insert_pos = i
            break
        insert_pos = i + 1

    def _map_objectclass_to_sumo(obj_class_raw):
        """
        Map IPG TrafficTemplate ObjectClass to SUMO vClass/guiShape.
        Unknowns default to passenger.
        """
        if not obj_class_raw:
            return ("passenger", "passenger")
        oc = str(obj_class_raw).strip().lower()

        # Common IPG classes
        if oc in ("car", "passenger", "passengercar"):
            return ("passenger", "passenger")
        if oc in ("van", "delivery", "lcv"):
            return ("delivery", "delivery")
        if oc in ("taxi",):
            return ("taxi", "taxi")
        if oc in ("truck", "hgv"):
            return ("truck", "truck")
        if oc in ("trailer", "semitrailer", "trucktrailer"):
            return ("trailer", "truck/trailer")
        if oc in ("bus",):
            return ("bus", "bus")
        if oc in ("coach",):
            return ("coach", "bus/coach")
        if oc in ("motorcycle", "motorbike"):
            return ("motorcycle", "motorcycle")
        if oc in ("bicycle", "bike"):
            return ("bicycle", "bicycle")
        if oc in ("pedestrian", "person"):
            return ("pedestrian", "pedestrian")

        return ("passenger", "passenger")

    def _color_for_vtype(vid, dims):
        """
        Choose a stable, distinguishable color for this vType.
        Prefer IPG template color if present and not the common default red.
        Else generate a deterministic palette based on vType id.
        Returns SUMO color string "r,g,b" with 0..1 floats.
        """
        ipg = None
        if dims and dims.get("color_rgb01") is not None:
            ipg = dims["color_rgb01"]
        # Many example templates ship with pure red; avoid making everything red in SUMO.
        if ipg and not (abs(ipg[0] - 1.0) < 1e-6 and abs(ipg[1]) < 1e-6 and abs(ipg[2]) < 1e-6):
            return f"{ipg[0]:.3f},{ipg[1]:.3f},{ipg[2]:.3f}"

        # Deterministic HSV -> RGB using a hash of vid (spread hues well)
        h = 0
        for ch in str(vid):
            h = (h * 131 + ord(ch)) & 0xFFFFFFFF
        # Use golden ratio conjugate to avoid clustering for nearby ids
        hue = ((h / 4294967296.0) + 0.61803398875) % 1.0
        # If id ends with a number (car1/car2/...), add a strong offset so colors differ
        mnum = re.search(r"(\d+)$", str(vid))
        if mnum:
            hue = (hue + (int(mnum.group(1)) * 0.17320508075)) % 1.0  # ~sqrt(3)-1
        # Also vary saturation/value a bit deterministically
        sat = 0.70 + 0.25 * (((h >> 8) & 0xFF) / 255.0)
        val = 0.85 + 0.10 * (((h >> 16) & 0xFF) / 255.0)

        # inline hsv->rgb
        i = int(hue * 6.0)
        f = hue * 6.0 - i
        p = val * (1.0 - sat)
        q = val * (1.0 - f * sat)
        t = val * (1.0 - (1.0 - f) * sat)
        i = i % 6
        if i == 0:
            r, g, b = val, t, p
        elif i == 1:
            r, g, b = q, val, p
        elif i == 2:
            r, g, b = p, val, t
        elif i == 3:
            r, g, b = p, q, val
        elif i == 4:
            r, g, b = t, p, val
        else:
            r, g, b = val, p, q
        return f"{r:.3f},{g:.3f},{b:.3f}"

    def _mk_vtype(vid, dims, fallback_gui="passenger"):
        v = ET.Element("vType")
        v.set("id", vid)
        # NOTE: In SUMO, accel/decel/sigma describe *driver behavior* (car-following),
        # not the physical limits. Physical limits are expressed via maxSpeed and
        # profiles like maxAccelProfile.
        v.set("accel", "1.5")
        v.set("decel", "4.5")
        v.set("sigma", "0.5")
        if dims and dims.get("vmax_ms") is not None:
            v.set("maxSpeed", f"{float(dims['vmax_ms']):.3f}")
        else:
            v.set("maxSpeed", "13.890")
        vclass, guishape = _map_objectclass_to_sumo(dims.get("object_class") if dims else None)
        # Allow explicit fallback override (used for ego)
        if fallback_gui and fallback_gui != "passenger" and (not dims or not dims.get("object_class")):
            guishape = fallback_gui
        v.set("vClass", vclass)
        v.set("guiShape", guishape)
        v.set("color", _color_for_vtype(vid, dims))
        if dims and dims.get("length") is not None:
            v.set("length", f"{dims['length']:.3f}")
        else:
            v.set("length", "4.500")

        if dims and dims.get("width") is not None:
            v.set("width", f"{dims['width']:.3f}")
        if dims and dims.get("height") is not None:
            v.set("height", f"{dims['height']:.3f}")

        # Physical max acceleration capability profile (simple constant profile).
        if dims and dims.get("axmax_ms2") is not None:
            ax = float(dims["axmax_ms2"])
            # Use a constant profile across all speeds (0..2778 m/s is SUMO's typical sentinel range).
            # According to SUMO's vType docs, maxAccelProfile is a list of accelerations
            # corresponding 1:1 to the entries in speedTable.
            v.set("speedTable", "0.0 2778")
            v.set("maxAccelProfile", f"{ax:.3f} {ax:.3f}")
        return v

    ego_vtype_id = "ego_car"
    root.insert(insert_pos, _mk_vtype(ego_vtype_id, ego_dims, fallback_gui="passenger"))
    insert_pos += 1

    template_to_vtype = {}
    # Stable ordering by template name (deterministic)
    for idx, (tmpl, dims) in enumerate(sorted(traffic_template_dims.items()), start=1):
        vid = f"car{idx}"
        template_to_vtype[tmpl] = vid
        root.insert(insert_pos, _mk_vtype(vid, dims, fallback_gui="passenger"))
        insert_pos += 1

    return ego_vtype_id, template_to_vtype


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_cosim_args():
    p = argparse.ArgumentParser(
        description="RT cosim vehicle orchestrator: SUMO vTypes + cosim_vehicle_mapping.json"
    )
    p.add_argument(
        "--sumo-step-length-s",
        type=float,
        default=0.01,
        help="SUMO --step-length (sim seconds per TraCI step); also drives default rt_bridge_hz = 1/this.",
    )
    p.add_argument(
        "--sumo-substeps",
        type=int,
        default=10,
        help="CarMaker Traffic cycles between SUMO steps (for in-process build; stored in JSON).",
    )
    p.add_argument(
        "--rt-bridge-hz",
        type=float,
        default=None,
        help="Host rt_bridge_phase2 --hz written to JSON. Default: 1/sumo_step_length_s (real-time pacing).",
    )
    return p.parse_args()


def main():
    args = parse_cosim_args()
    step_len = float(args.sumo_step_length_s)
    if step_len <= 0 or step_len != step_len:
        raise SystemExit("--sumo-step-length-s must be a positive number")
    substeps = max(1, int(args.sumo_substeps))
    if args.rt_bridge_hz is not None and args.rt_bridge_hz > 0:
        bridge_hz = float(args.rt_bridge_hz)
    else:
        bridge_hz = round(1.0 / step_len, 6)

    print("=== cosim_vehicle_orchestrator ===")
    print(
        f"  Timing knobs: sumo_step_length_s={step_len:g}  sumo_substeps={substeps}  "
        f"rt_bridge_hz={bridge_hz:g} (orchestrator / rt_orchestrator)"
    )
    print(f"Reading TestRun: {CM_TESTRUN_PATH}")

    ego_tmpl, traffic_slots_by_index, actor_slots_by_index = parse_cm_testrun_for_templates(CM_TESTRUN_PATH)

    print(f"  Ego template: {ego_tmpl}")
    print("  Traffic templates:")
    traffic_templates = OrderedDict()
    for slot_idx in sorted(traffic_slots_by_index.keys()):
        info = traffic_slots_by_index[slot_idx]
        traffic_templates[info["ipg_name"]] = info["template"]
        print(f"    {info['ipg_name']} -> {info['template']}")
    actor_templates = OrderedDict()
    if actor_slots_by_index:
        print("  Actor templates (FreeMotion=0):")
        for slot_idx in sorted(actor_slots_by_index.keys()):
            info = actor_slots_by_index[slot_idx]
            actor_templates[info["ipg_name"]] = info["template"]
            print(f"    {info['ipg_name']} -> {info['template']}")

    print(f"\nReading SUMO routes: {SUMO_ROUTES_PATH}")
    tree, root, vtypes = parse_sumo_routes(SUMO_ROUTES_PATH)

    print("  Existing vTypes in SUMO:")
    for vid in vtypes:
        print(f"    {vid}")

    # --- Build dimensions for ego + each distinct traffic template ---
    ego_dims = get_ego_vehicle_dimensions(ego_tmpl) if ego_tmpl else {}
    traffic_tmpls = sorted(set(traffic_templates.values()))
    actor_tmpls = sorted(set(actor_templates.values()))
    all_tmpls = sorted(set(traffic_tmpls + actor_tmpls))
    traffic_dims = {tmpl: get_template_dimensions(tmpl) for tmpl in all_tmpls}

    # --- Rebuild SUMO vTypes so only IPG models exist (no legacy 'car') ---
    print("\nRebuilding SUMO vTypes from IPG models...")
    ego_vtype_id, template_to_vtype = rebuild_sumo_vtypes_from_ipg_models(root, ego_dims, traffic_dims)
    print(f"  Ego vType id: {ego_vtype_id}")
    for tmpl, vid in template_to_vtype.items():
        print(f"  Traffic template {tmpl} -> vType {vid}")

    # Point SUMO ego vehicle to ego vType
    ego_vehicle = root.find("./vehicle[@id='ego']")
    if ego_vehicle is not None and ego_vtype_id:
        old_type = ego_vehicle.get("type")
        ego_vehicle.set("type", ego_vtype_id)
        print(f"  Updated SUMO ego vehicle type: {old_type} -> {ego_vtype_id}")

    # Build a SUMO vTypeDistribution for traffic mix if we have >= 2 traffic types.
    traffic_dist_id = None
    if len(traffic_tmpls) >= 2:
        vtype_ids = [template_to_vtype.get(traffic_tmpls[0]),
                     template_to_vtype.get(traffic_tmpls[1])]
        # 70% first type (typically car1), 30% second (typically car2 / truck)
        probs = ["0.7", "0.3"]
        if all(vtype_ids):
            traffic_dist_id = "traffic_mix"
            # If we run the orchestrator multiple times, remove the old distribution
            # so we don't accumulate duplicates in scenario.rou.xml.
            for vd in list(root.findall("vTypeDistribution")):
                if vd.get("id") == traffic_dist_id:
                    root.remove(vd)
            dist = ET.Element("vTypeDistribution")
            dist.set("id", traffic_dist_id)
            dist.set("vTypes", " ".join(vtype_ids))
            dist.set("probabilities", " ".join(probs))

            # Insert distribution after the last vType element for readability
            children = list(root)
            insert_pos = 0
            for i, child in enumerate(children):
                if child.tag == "vType":
                    insert_pos = i + 1
            root.insert(insert_pos, dist)

    # Update flows:
    # - If a distribution was created, point all "car" flows to it
    # - Else (single traffic type), keep using that single vType
    default_flow_vtype = template_to_vtype.get(traffic_tmpls[0]) if traffic_tmpls else None
    for flow in root.findall("flow"):
        if flow.get("type") == "car":
            if traffic_dist_id is not None:
                flow.set("type", traffic_dist_id)
            elif default_flow_vtype:
                flow.set("type", default_flow_vtype)

    # Actor bootstrap insertion into SUMO routes:
    # create/update explicit <vehicle> entries for roleplay actors.
    # Route choice is intentionally simple in phase-1 (first available route id).
    route_ids = [r.get("id") for r in root.findall("route") if r.get("id")]
    first_route_id = route_ids[0] if route_ids else None
    if actor_slots_by_index and not first_route_id:
        print("  WARNING: no <route id=...> found in scenario.rou.xml; actor SUMO vehicle stubs skipped")
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
        if veh.get("depart") is None:
            veh.set("depart", "0.00")
        veh.set("route", first_route_id)

    # Flow prefixes used by C++ to include all generated vehicles from multiple flows.
    flow_prefixes = []
    for flow in root.findall("flow"):
        fid = flow.get("id")
        if fid:
            pref = f"{fid}."
            if pref not in flow_prefixes:
                flow_prefixes.append(pref)
    if not flow_prefixes:
        flow_prefixes = ["flow"]  # safe fallback

    # Write back modified SUMO routes (in-place for now; later we can write to a copy)
    backup_path = SUMO_ROUTES_PATH + ".bak"
    if not os.path.exists(backup_path):
        os.replace(SUMO_ROUTES_PATH, backup_path)
        print(f"  Backed up original routes to: {backup_path}")
    # Pretty-print (Python 3.9+)
    try:
        ET.indent(tree, space="  ", level=0)
    except Exception:
        pass
    tree.write(SUMO_ROUTES_PATH, encoding="utf-8", xml_declaration=True)
    print(f"  Updated routes written to: {SUMO_ROUTES_PATH}")

    # Static per test-run mapping: CM Traffic.Txx slot -> expected SUMO vType id
    # Used by C++ to assign flow0.* vehicles into the correct IPG traffic object pool.
    traffic_slots_json = []
    vtype_to_slot_names = {}
    vtype_to_slot_indices = {}
    for slot_idx in sorted(traffic_slots_by_index.keys()):
        tmpl = traffic_slots_by_index[slot_idx]["template"]
        expected_vtype_id = template_to_vtype.get(tmpl)
        if expected_vtype_id:
            dims = traffic_dims.get(tmpl, {})
            traffic_slots_json.append({
                "slot_index": int(slot_idx),
                "ipg_name": traffic_slots_by_index[slot_idx]["ipg_name"],
                "expected_vtype_id": expected_vtype_id,
                "length_m": dims.get("length"),
            })
            vtype_to_slot_names.setdefault(expected_vtype_id, []).append(traffic_slots_by_index[slot_idx]["ipg_name"])
            vtype_to_slot_indices.setdefault(expected_vtype_id, []).append(int(slot_idx))

    actor_instances_json = []
    for slot_idx in sorted(actor_slots_by_index.keys()):
        info = actor_slots_by_index[slot_idx]
        actor_tmpl = info["template"]
        actor_vtype = template_to_vtype.get(actor_tmpl)
        actor_instances_json.append({
            "ipg_name": info["ipg_name"],
            "template": actor_tmpl,
            "vtype_id": actor_vtype,
            "free_motion": info.get("free_motion"),
        })

    # Build vehicle specs with dimensions from IPG templates (ego + distinct traffic templates)
    vehicles = []
    if ego_tmpl:
        vehicles.append({
            "role": "ego",
            "template": ego_tmpl,
            "vtype_id": ego_vtype_id,
            "length_m": ego_dims.get("length"),
            "width_m":  ego_dims.get("width"),
            "height_m": ego_dims.get("height"),
            "vmax_ms": ego_dims.get("vmax_ms"),
            "axmax_ms2": ego_dims.get("axmax_ms2"),
        })

    for tmpl in traffic_tmpls:
        dims = traffic_dims.get(tmpl, {})
        vehicles.append({
            "role": "traffic",
            "template": tmpl,
            "vtype_id": template_to_vtype.get(tmpl),
            "length_m": dims.get("length"),
            "width_m":  dims.get("width"),
            "height_m": dims.get("height"),
            "vmax_ms": dims.get("vmax_ms"),
            "axmax_ms2": dims.get("axmax_ms2"),
        })
    for tmpl in actor_tmpls:
        dims = traffic_dims.get(tmpl, {})
        vehicles.append({
            "role": "actor",
            "template": tmpl,
            "vtype_id": template_to_vtype.get(tmpl),
            "length_m": dims.get("length"),
            "width_m":  dims.get("width"),
            "height_m": dims.get("height"),
            "vmax_ms": dims.get("vmax_ms"),
            "axmax_ms2": dims.get("axmax_ms2"),
        })

    # Emit JSON summary for C++ / tools to read lengths/types later
    summary = {
        "ego_template": ego_tmpl,
        # In-process CarMaker: libsumo Simulation::start -c (must match this machine).
        "sumo_sumocfg_path": _sumo_sumocfg_path_for_json(),
        "SUMO_lights": True,
        # CarMaker cycles between SUMO_do_step() calls (1 cycle ~= 1 ms in typical setup).
        "sumo_substeps": substeps,
        # SUMO simulation seconds advanced per TraCI Simulation::step (CLI --step-length).
        "sumo_step_length_s": step_len,
        # Host rt_bridge_phase2 loop rate; ~1/sumo_step_length_s matches one SUMO step per real second.
        "rt_bridge_hz": bridge_hz,
        # Optional no-delay dead reckoning between SUMO steps using SUMO speed+yaw.
        "sumo_predict_pose_between_steps": False,
        # Phase-1 RT bridge mode: host sends traffic slot updates to RT via UDP.
        # When true, RT User.cpp uses UDP input path instead of local in-process SUMO stepping.
        "rt_host_rx_enable": True,
        "rt_host_rx_port": 50051,
        "rt_host_rx_timeout_s": 0.5,
        "rt_ego_tx_enable": True,
        "rt_ego_tx_ip": "192.168.100.22",
        "rt_ego_tx_port": 50052,
        "rt_ego_tx_decimation": 10,
        # Actor TX decimation defaults to ego decimation for parity.
        "rt_actor_tx_decimation": 10,
        # Global actor mirroring switch: true=enabled, false=disabled.
        "actor_enabled": False,
        # Global ROI for SUMO-managed traffic feed (actors handled separately).
        "roi": None,
        "vehicles": vehicles,
        "template_to_vtype": {
            "ego": ego_vtype_id,
            **template_to_vtype
        },
        "traffic_slots": traffic_slots_json,
        "actor_instances": actor_instances_json,
        "flow_prefixes": flow_prefixes,
        # Demography of available CarMaker slot pool per SUMO vType.
        # Example: "car1": ["T00","T01",...], "car2": ["T08",...]
        "vtype_slots": vtype_to_slot_names,
        # Same grouping but with numeric indices (faster for C++ consumers).
        "vtype_slot_indices": vtype_to_slot_indices,
        "coordinate_alignment": {
            "g_theta_rad": 0.0,
            "g_dx": 0.0,
            "g_dy": -328.57
        }
    }

    os.makedirs(COSIM_DIR, exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as jf:
        json.dump(summary, jf, indent=2)
    print(f"\nWrote mapping summary JSON to: {OUTPUT_JSON_PATH}")
    print(f"  sumo_sumocfg_path in JSON: {summary.get('sumo_sumocfg_path')}")


if __name__ == "__main__":
    main()