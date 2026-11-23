"""Extract per-floor 3D-ready geometry from the Hayah DXF.

Walls are drawn as double lines with gaps at doors/windows, so they are
rebuilt by rasterizing the wall layer, filling the thin bands between the
lines and vectorizing the result back into polygons.

Usage: python3 tools/extract.py src/hayah.dxf web/model.js [debug_dir]
"""
import json
import math
import re
import sys
from collections import defaultdict

import cv2
import numpy as np
from ezdxf import bbox, path, recover

RES = 0.02  # meters per pixel
X0, X1, Y0, Y1 = 24.0, 80.0, 200.0, 247.0  # sheet-local drawing window
W, H = int((X1 - X0) / RES), int((Y1 - Y0) / RES)
SHEET_DX = 75.0

# sheet -> (id, name, level z in meters)
FLOORS = [
    (2, "semi", "Semi-subsolo · Garagem", -1.30),
    (3, "terreo", "Térreo · Recepção", 1.70),
    (4, "sob1", "Sobresolo 01 · Garagem", 4.76),
    (5, "sob2", "Sobresolo 02 · Garagem", 7.82),
    (6, "mez1", "Lazer · Piscinas", 10.88),
    (7, "mez2", "Lazer · Academia & Spa", 13.94),
    (8, "tipo", "Pavimento Tipo", 17.00),
    (9, "cobinf", "Cobertura 3201 · Inferior", 111.86),
    (10, "cobsup", "Cobertura 3201 · Superior", 114.92),
]
TIPO_COUNT = 31
FLOOR_H = 3.06
ROOF_Z = 117.98

LABEL_SKIP = re.compile(
    r"JANELA|CONFORMIDADE|SOBE|DESCE|RUA |QUADRA|SENTIDO|R=|CAP\.|MEIO FIO|ACESSO AUTOS|"
    r"PROJEÇÃO|EXAUSTÃO|MECÂNICA|PARTE |FAIXA|ESPAÇO$|OBRA DE ARTE|ÁREA DE ACOMODAÇÃO"
)


def to_px(x, y):
    return (x - X0) / RES, (Y1 - y) / RES


def to_m(c, r):
    return X0 + c * RES, Y1 - r * RES


def flat_paths(entity):
    """Yield lists of (x, y) for an entity, exploding blocks and hatches."""
    t = entity.dxftype()
    if t == "INSERT":
        for v in entity.virtual_entities():
            yield from flat_paths(v)
        return
    if t == "HATCH":
        for p in path.from_hatch(entity):
            pts = [(v.x, v.y) for v in p.flattening(0.02)]
            if len(pts) > 2:
                yield pts
        return
    if t in ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "SPLINE", "ELLIPSE", "SOLID"):
        try:
            p = path.make_path(entity)
        except Exception:
            return
        pts = [(v.x, v.y) for v in p.flattening(0.02)]
        if len(pts) > 1:
            yield pts


def is_closed(entity):
    t = entity.dxftype()
    return t in ("HATCH", "CIRCLE", "SOLID") or (t == "LWPOLYLINE" and entity.closed)


def sheet_of(entity):
    try:
        b = bbox.extents([entity], fast=True)
    except Exception:
        return None
    if not b.has_data:
        return None
    s = int((b.extmin.x - 23) // SHEET_DX) + 1
    return s if 1 <= s <= 10 and b.extmin.y < 250 else None


def local(pts, s):
    dx = SHEET_DX * (s - 1)
    return [(x - dx, y) for x, y in pts]


def fill_mask(groups):
    """Fill ring groups; rings inside one group combine even-odd (hatch holes)."""
    m = np.zeros((H, W), np.uint8)
    for rings in groups:
        g = np.zeros_like(m)
        for pts in rings:
            a = np.array([to_px(x, y) for x, y in pts], np.float64)
            t = np.zeros_like(m)
            cv2.fillPoly(t, [np.round(a * 4).astype(np.int32)], 255, lineType=cv2.LINE_8, shift=2)
            g ^= t
        m |= g
    return m


def line_mask(polys, thick=1):
    m = np.zeros((H, W), np.uint8)
    for pts in polys:
        a = np.array([to_px(x, y) for x, y in pts], np.float64)
        cv2.polylines(m, [np.round(a * 4).astype(np.int32)], False, 255, thick, cv2.LINE_8, shift=2)
    return m


def disk(d_m):
    k = max(3, int(round(d_m / RES)) | 1)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))


def thin_holes(lines, max_half_m):
    """Fill enclosed regions whose half-thickness is below max_half_m."""
    free = cv2.bitwise_not(lines)
    n, lab = cv2.connectedComponents(free, connectivity=4)
    dist = cv2.distanceTransform(free, cv2.DIST_L2, 5)
    mx = np.zeros(n, np.float32)
    np.maximum.at(mx, lab.ravel(), dist.ravel())
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    keep = mx <= max_half_m / RES
    keep[border] = False
    keep[0] = keep[0] and 0 not in border
    return np.where(keep[lab], 255, 0).astype(np.uint8)


def vectorize(mask, eps_px=1.0, min_area_m2=0.004):
    """Mask -> list of {o: outer ring, h: [hole rings]} in meters."""
    cnts, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    if hier is None:
        return out
    hier = hier[0]
    for i, c in enumerate(cnts):
        if hier[i][3] != -1:
            continue
        if cv2.contourArea(c) * RES * RES < min_area_m2:
            continue
        ring = ring_m(cv2.approxPolyDP(c, eps_px, True))
        holes = []
        j = hier[i][2]
        while j != -1:
            hc = cnts[j]
            if cv2.contourArea(hc) * RES * RES >= min_area_m2:
                holes.append(ring_m(cv2.approxPolyDP(hc, eps_px, True)))
            j = hier[j][0]
        if len(ring) >= 3:
            out.append({"o": ring, "h": [h for h in holes if len(h) >= 3]})
    return out


def ring_m(c):
    # pixel edges -> meters; +0.5 centers the 1px contour on the pixel boundary
    return [[round(v, 3) for v in to_m(p[0][0] + 0.5, p[0][1] + 0.5)] for p in c]


def oriented_rect(pts):
    a = np.array(pts, np.float32)
    (cx, cy), (w, h), ang = cv2.minAreaRect(a)
    if w < h:
        w, h, ang = h, w, ang + 90
    return cx, cy, w, h, math.radians(ang)


def block_rect(ins, cache, doc):
    """Oriented footprint of an INSERT from its block-local extents."""
    name = ins.dxf.name
    if name not in cache:
        try:
            b = bbox.extents(doc.blocks[name], fast=True)
            cache[name] = (b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y) if b.has_data else None
        except Exception:
            cache[name] = None
    e = cache[name]
    if e is None:
        return None
    m = ins.matrix44()
    corners = [m.transform((x, y, 0)) for x, y in ((e[0], e[1]), (e[2], e[1]), (e[2], e[3]), (e[0], e[3]))]
    return oriented_rect([(c.x, c.y) for c in corners])


def classify(name, w, d):
    n = name.lower()
    if "bacia" in n:
        return ("toilet", 0.42)
    if "chuveiro" in n or "barras" in n or "teclado" in n or "monitor" in n or "rodas" in n:
        return None
    if "bancada" in n or "cuba" in n or n.startswith("co-") or "apoio" in n:
        return ("counter", 0.92)
    if "playground" in n or "kids" in n:
        return ("play", 1.1)
    if "bilhar" in n:
        return ("billiard", 0.8)
    if "exercise" in n or "bike" in n:
        return ("gym", 1.1)
    if "vasos" in n or "jardineira" in n:
        return ("plant", 0.9)
    if "cadeira" in n and w < 0.8:
        return ("chair", 0.85)
    if "poltrona" in n:
        return ("armchair", 0.8)
    if "mesa" in n:
        return ("table", 0.75)
    area = w * d
    if w < 0.25 or d < 0.2:
        return None
    if 1.3 <= d and 1.85 <= w <= 2.4:
        return ("bed", 0.55)
    if w >= 1.6 and 0.7 <= d <= 1.15:
        return ("sofa", 0.78)
    if w >= 1.1 and d >= 0.7:
        return ("table", 0.75)
    if w >= 0.9 and d < 0.7:
        return ("cabinet", 0.9)
    if area < 0.6:
        return ("chair", 0.85)
    return ("table", 0.75)


def orient_furniture(furn, wallmask):
    """Append +1/-1: which side faces a wall (bed headboard, sofa back)."""
    def hits(x, y):
        c, r = to_px(x, y)
        c, r = int(c), int(r)
        return 0 <= r < H and 0 <= c < W and wallmask[r, c] > 0

    for f in furn:
        cx, cy, w, d, ang, kind = f[:6]
        if kind == "bed":
            ux, uy, reach = math.cos(ang), math.sin(ang), w / 2
        elif kind in ("sofa", "armchair"):
            ux, uy, reach = -math.sin(ang), math.cos(ang), d / 2
        else:
            f.append(1)
            continue
        score = {1: 0, -1: 0}
        for sgn in (1, -1):
            for k in range(1, 26):
                t = reach + k * 0.02
                if hits(cx + sgn * ux * t, cy + sgn * uy * t):
                    score[sgn] = 26 - k
                    break
        f.append(1 if score[1] >= score[-1] else -1)


def main(dxf_path, out_path, debug_dir=None):
    doc, _ = recover.readfile(dxf_path)
    msp = doc.modelspace()
    per = defaultdict(lambda: defaultdict(list))
    rect_cache = {}

    for e in msp:
        t = e.dxftype()
        if t == "DIMENSION":
            continue
        s = sheet_of(e)
        if s is None:
            continue
        L = e.dxf.layer
        d = per[s]
        if t == "TEXT" and L == "Texto":
            h = e.dxf.get("height", 0)
            txt = e.dxf.text.strip()
            p = e.dxf.insert
            d["texts"].append((p.x - SHEET_DX * (s - 1), p.y, h, txt))
            continue
        if L == "Parede":
            d["wall"] += [local(p, s) for p in flat_paths(e)]
        elif L == "Pilar":
            d["pillar"] += [[local(p, s)] for p in flat_paths(e) if len(p) > 2]
        elif L == "Hachura02" and is_closed(e):
            d["band"].append([local(p, s) for p in flat_paths(e)])
        elif L.startswith("Hachura-Piscina") and is_closed(e):
            d["pool"].append([local(p, s) for p in flat_paths(e)])
        elif L.startswith("HachuraVerde") and is_closed(e):
            d["green"].append([local(p, s) for p in flat_paths(e)])
        elif L in ("P1", "P2") and t == "LWPOLYLINE" and e.closed:
            pts = local([(x, y) for x, y in e.get_points("xy")], s)
            a = abs(cv2.contourArea(np.array(pts, np.float32)))
            if 100 < a < 1200:
                d["outline"].append([pts])
        if L.startswith("ESQUADRIA"):
            pts = [q for p in flat_paths(e) for q in local(p, s)]
            if len(pts) >= 2:
                d["esq"].append(oriented_rect(pts))
        if t == "LWPOLYLINE" and L == "Vagas" and e.closed:
            cx, cy, w, dd, ang = oriented_rect(local(e.get_points("xy"), s))
            if 4.2 <= w <= 6 and 2.0 <= dd <= 3.2:
                d["furn"].append([round(cx, 3), round(cy, 3), 4.4, 1.8, round(ang, 4), "car", 1.45])
        if t == "INSERT" and L in ("Apto-MOVEL", "Apto-WCCOZ", "P1"):
            r = block_rect(e, rect_cache, doc)
            if r is None:
                continue
            cx, cy, w, dd, ang = r
            c = classify(e.dxf.name, w, dd)
            if c and w < 6:
                d["furn"].append([round(cx - SHEET_DX * (s - 1), 3), round(cy, 3), round(w, 3), round(dd, 3), round(ang, 4), c[0], c[1]])
        elif t == "LWPOLYLINE" and L == "Apto-MOVEL" and e.closed:
            cx, cy, w, dd, ang = oriented_rect(local(e.get_points("xy"), s))
            if 0.9 <= w <= 4 and 0.45 <= dd <= 0.75:
                d["furn"].append([round(cx, 3), round(cy, 3), round(w, 3), round(dd, 3), round(ang, 4), "wardrobe", 2.3])

    model = {"floorH": FLOOR_H, "tipoCount": TIPO_COUNT, "roofZ": ROOF_Z, "floors": []}

    lot = None
    for e in msp.query("LWPOLYLINE[layer=='P2']"):
        if e.closed and len(e) == 5 and sheet_of(e) == 4:
            lot = [[round(x - SHEET_DX * 3, 3), round(y, 3)] for x, y in e.get_points("xy")]
    model["lot"] = lot

    for s, fid, name, z in FLOORS:
        d = per[s]
        lines = line_mask(d["wall"], 1)
        walls = cv2.morphologyEx(lines, cv2.MORPH_CLOSE, disk(0.26))
        walls |= thin_holes(walls, 0.22)
        walls = cv2.morphologyEx(walls, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        pil = fill_mask(d["pillar"])
        walls |= pil
        band = fill_mask(d["band"])
        walls &= cv2.bitwise_not(band)

        windows = []
        for cx, cy, w, h, ang in d["esq"]:
            if w >= 0.5 and h <= 0.45 and w / max(h, 0.01) >= 2.5:
                full = w >= 1.6
                windows.append([round(cx, 3), round(cy, 3), round(w, 3), round(max(h, 0.12), 3), round(ang, 4),
                                0.0 if full else (1.55 if w < 0.8 else 1.0), 2.5 if full else 2.2])
        # carve window gaps so glass is never buried in a wall
        if windows:
            win = np.zeros_like(walls)
            for cx, cy, w, h, ang, _, _ in windows:
                box = cv2.boxPoints((to_px(cx, cy), (w / RES, max(h, 0.3) / RES), -math.degrees(ang)))
                cv2.fillPoly(win, [np.round(box).astype(np.int32)], 255)
            walls &= cv2.bitwise_not(win)

        orient_furniture(d["furn"], walls | band)

        solid = walls | band | fill_mask(d["outline"]) | fill_mask(d["pool"]) | fill_mask(d["green"])
        solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, disk(0.8))
        cnts, _ = cv2.findContours(solid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        slab = np.zeros_like(solid)
        cv2.drawContours(slab, [c for c in cnts if cv2.contourArea(c) * RES * RES > 15], -1, 255, -1)

        labels = []
        txts = d["texts"]
        for x, y, h, txt in txts:
            if not (0.135 <= h <= 0.2) or len(txt) < 3 or x > 79 or LABEL_SKIP.search(txt):
                continue
            if not re.match(r"^[A-ZÀ-Ú][A-ZÀ-Ú0-9 .()/-]+$", txt) or not re.search(r"[A-ZÀ-Ú]{2}", txt):
                continue
            lab = txt.title().replace("Wcb", "Banho").replace("Wc ", "WC ").replace("Apto", "Apto")
            if txt.startswith("APTO"):
                area = next((t2 for x2, y2, _, t2 in txts if t2.endswith("m2") and abs(x2 - x) < 0.6 and -0.5 < y2 - y < 0.05), None)
                if area:
                    lab += " · " + area.replace("m2", " m²").replace(".", ",")
            labels.append([round(x, 2), round(y, 2), lab])

        fl = {
            "id": fid, "name": name, "z": z, "sheet": s,
            "walls": vectorize(walls),
            "band": vectorize(band, 1.5, 0.05),
            "slab": vectorize(slab, 2.0, 1.0),
            "pools": vectorize(fill_mask(d["pool"]), 1.5, 0.5),
            "green": vectorize(fill_mask(d["green"]), 1.5, 0.2),
            "windows": windows,
            "furn": d["furn"],
            "labels": labels,
        }
        model["floors"].append(fl)
        print(f"{fid:7s} walls={len(fl['walls'])} band={len(fl['band'])} slab={len(fl['slab'])} pools={len(fl['pools'])} "
              f"green={len(fl['green'])} win={len(windows)} furn={len(d['furn'])} labels={len(labels)}")
        if debug_dir:
            dbg = cv2.merge([slab // 3, walls, band])
            cv2.imwrite(f"{debug_dir}/{fid}.png", cv2.resize(dbg, (W // 2, H // 2), interpolation=cv2.INTER_AREA))

    # center everything on the tower core
    tipo = next(f for f in model["floors"] if f["id"] == "tipo")
    xs = [p[0] for poly in tipo["slab"] for p in poly["o"]]
    ys = [p[1] for poly in tipo["slab"] for p in poly["o"]]
    model["origin"] = [round((min(xs) + max(xs)) / 2, 3), round((min(ys) + max(ys)) / 2, 3)]

    with open(out_path, "w") as f:
        f.write("window.MODEL=")
        json.dump(model, f, separators=(",", ":"), ensure_ascii=False)
        f.write(";\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
