#!/usr/bin/env python
"""
Coordinate alignment helper wizard for CoSim JSON.

Workflow:
1) Read ERG-exported CSV.
2) Detect the largest Tx/Ty jump (per traffic pair).
3) Compute recommended coordinate_alignment correction.
4) Update JSON coordinate_alignment in-place (with confirmation).
"""

import csv
import json
import math
import os
import re
from typing import Dict, List, Optional, Tuple


def _strip_wrapping_quotes(s: str) -> str:
    t = str(s).strip()
    if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
        return t[1:-1].strip()
    return t


def _ask(prompt: str, default: Optional[str] = None) -> str:
    if default is None:
        return _strip_wrapping_quotes(input(f"{prompt}: "))
    raw = input(f"{prompt} [{default}]: ").strip()
    return default if raw == "" else _strip_wrapping_quotes(raw)


def _ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    d = "y" if default_yes else "n"
    raw = input(f"{prompt} [y/n, default={d}]: ").strip().lower()
    if raw == "":
        return default_yes
    return raw in ("y", "yes", "1", "true")


def _read_csv_lines(csv_path: str) -> List[str]:
    with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
        return [line.rstrip("\n\r") for line in f]


def _parse_name_header(line: str) -> List[str]:
    # Example:
    # #Name,"Time","Traffic.T01.State","Traffic.T01.tx","Traffic.T01.ty"
    payload = line[len("#Name,"):] if line.startswith("#Name,") else line[len("#Name"):]
    row = next(csv.reader([payload]))
    return [c.strip().strip('"') for c in row if c is not None]


def _is_float_token(tok: str) -> bool:
    try:
        float(tok)
        return True
    except Exception:
        return False


def _load_data_rows(lines: List[str]) -> Tuple[List[str], List[List[float]]]:
    header = None
    data_rows: List[List[float]] = []

    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#Name"):
            header = _parse_name_header(s)
            continue
        if s.startswith("#"):
            continue
        row = next(csv.reader([s]))
        tokens = [t.strip().strip('"') for t in row]
        if not tokens or not all(_is_float_token(t) for t in tokens):
            continue
        data_rows.append([float(t) for t in tokens])

    if not data_rows:
        raise ValueError("No numeric data rows found in CSV.")

    if header is None:
        # Fallback generic header
        header = [f"col_{i}" for i in range(len(data_rows[0]))]

    return header, data_rows


def _align_header_to_data(header: List[str], data_rows: List[List[float]]) -> Tuple[List[str], int]:
    # ERG exports sometimes include an extra leading "Name" token in #Name
    # while numeric rows do not. Handle offset robustly.
    n_header = len(header)
    n_data = len(data_rows[0])
    if n_header == n_data:
        return header, 0
    if n_header == n_data + 1:
        return header[1:], 1
    if n_data == n_header + 1:
        return header, -1
    raise ValueError(
        f"Header/data column mismatch not supported (header={n_header}, data={n_data})."
    )


def _find_tx_ty_pairs(columns: List[str]) -> List[Tuple[str, int, int]]:
    # Pair by base prefix ending with .tx/.ty (case-insensitive)
    tx_map: Dict[str, int] = {}
    ty_map: Dict[str, int] = {}
    for idx, name in enumerate(columns):
        n = name.strip()
        ln = n.lower()
        if ln.endswith(".tx"):
            tx_map[n[:-3]] = idx
        elif ln.endswith(".ty"):
            ty_map[n[:-3]] = idx

    pairs = []
    for base, tx_i in tx_map.items():
        if base in ty_map:
            pairs.append((base, tx_i, ty_map[base]))
    return sorted(pairs, key=lambda x: x[0].lower())


def _best_jump_for_pair(
    rows: List[List[float]], tx_i: int, ty_i: int
) -> Tuple[int, float, float, float]:
    # Returns (jump_row_index, dx, dy, jump_norm)
    # jump_row_index is the "current" row index i where jump = row[i]-row[i-1]
    best_i = -1
    best_dx = 0.0
    best_dy = 0.0
    best_norm = -1.0
    for i in range(1, len(rows)):
        dx = rows[i][tx_i] - rows[i - 1][tx_i]
        dy = rows[i][ty_i] - rows[i - 1][ty_i]
        n = math.hypot(dx, dy)
        if n > best_norm:
            best_norm = n
            best_i = i
            best_dx = dx
            best_dy = dy
    return best_i, best_dx, best_dy, best_norm


def _detect_time_index(columns: List[str]) -> int:
    for i, c in enumerate(columns):
        if c.strip().lower() == "time":
            return i
    return 0


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, obj: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def main() -> None:
    print("=== Coordinate Alignment Wizard ===")
    csv_path = os.path.abspath(os.path.expanduser(_ask("CSV path")))
    json_path = os.path.abspath(os.path.expanduser(_ask("JSON path")))

    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    if not os.path.isfile(json_path):
        raise FileNotFoundError(f"JSON not found: {json_path}")

    lines = _read_csv_lines(csv_path)
    raw_header, rows = _load_data_rows(lines)
    columns, offset = _align_header_to_data(raw_header, rows)
    pairs = _find_tx_ty_pairs(columns)
    if not pairs:
        raise ValueError(
            "No .tx/.ty column pairs found. Ensure CSV includes columns like Traffic.T01.tx and Traffic.T01.ty."
        )

    print(f"\nDetected {len(pairs)} Tx/Ty pair(s):")
    pair_jumps = []
    t_idx = _detect_time_index(columns)
    for k, (base, tx_i, ty_i) in enumerate(pairs, start=1):
        ji, dx, dy, jn = _best_jump_for_pair(rows, tx_i, ty_i)
        t = rows[ji][t_idx] if 0 <= ji < len(rows) and 0 <= t_idx < len(rows[0]) else float("nan")
        pair_jumps.append((base, tx_i, ty_i, ji, dx, dy, jn, t))
        print(f"  {k:2d}) {base}: jump_norm={jn:.6f} at row={ji} time={t:.6f}s dx={dx:.6f} dy={dy:.6f}")

    pair_jumps_sorted = sorted(pair_jumps, key=lambda x: x[6], reverse=True)
    default_base = pair_jumps_sorted[0][0]
    chosen = _ask(
        "\nChoose pair base name to use (or press Enter for strongest jump)",
        default_base,
    )
    chosen_row = None
    for rec in pair_jumps:
        if rec[0] == chosen:
            chosen_row = rec
            break
    if chosen_row is None:
        raise ValueError(f"Pair '{chosen}' not found.")

    base, tx_i, ty_i, ji, dx, dy, jn, t = chosen_row
    print("\nSelected jump:")
    print(f"  pair={base}")
    print(f"  row={ji}, time={t:.6f}s")
    print(f"  dx={dx:.6f}, dy={dy:.6f}, norm={jn:.6f}")

    cfg = _load_json(json_path)
    ca = cfg.get("coordinate_alignment")
    if not isinstance(ca, dict):
        ca = {}
        cfg["coordinate_alignment"] = ca

    old_theta = float(ca.get("g_theta_rad", 0.0))
    old_dx = float(ca.get("g_dx", 0.0))
    old_dy = float(ca.get("g_dy", 0.0))

    # Correction strategy:
    # if vehicle jumps by (+dx,+dy) when SUMO takes over, shift alignment by (-dx,-dy).
    new_dx = old_dx - dx
    new_dy = old_dy - dy
    new_theta = old_theta

    print("\nProposed coordinate_alignment update:")
    print(f"  g_theta_rad: {old_theta:.9g} -> {new_theta:.9g} (unchanged)")
    print(f"  g_dx       : {old_dx:.9g} -> {new_dx:.9g}")
    print(f"  g_dy       : {old_dy:.9g} -> {new_dy:.9g}")

    if not _ask_yes_no("Apply and overwrite JSON?", default_yes=True):
        print("Aborted. JSON not changed.")
        return

    ca["g_theta_rad"] = new_theta
    ca["g_dx"] = new_dx
    ca["g_dy"] = new_dy
    _save_json(json_path, cfg)
    print(f"Updated JSON: {json_path}")


if __name__ == "__main__":
    main()
