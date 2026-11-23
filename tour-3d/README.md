# Hayah · Tour 3D

Interactive 3D tour of the Hayah residential tower (HX Construtora), generated from
the legal architecture DWG. The DWG is not in this repo: put it in `src/ProjetoLegalHX_Hayah.dwg` to regenerate.

## Run

```bash
cd web && python3 -m http.server 5391
# open http://localhost:5391
```

`web/index.html` also opens directly from disk (three.js loads from jsDelivr, so it needs internet).

## Regenerate the model from the DWG

```bash
brew install libredwg                                  # dwg2dxf
python3 -m pip install --user ezdxf opencv-python-headless
dwg2dxf -y -o src/hayah.dxf src/ProjetoLegalHX_Hayah.dwg
python3 tools/extract.py src/hayah.dxf web/model.js    # optional 3rd arg: debug PNG dir
```

## How the geometry is derived

- Sheets 02–10 are floor plans laid out every 75 m in model space; all share the same origin.
- Walls (`Parede`) are double lines: rasterized at 2 cm/px, bands between lines filled, then vectorized.
- Pillars (`Pilar`), slab-edge ring (`Hachura02`), pools (`Hachura-Piscina*`), planters (`HachuraVerde-*`).
- Windows from `ESQUADRIA-*` elongated symbols; sill/head heights are heuristics (≥1.6 m wide = floor-to-ceiling).
- Furniture from `Apto-MOVEL` / `Apto-WCCOZ` block extents, classified by name and size; cars placed on `Vagas` stalls
  (the car block came empty in the DWG→DXF conversion).
- Levels read from Corte AA: floor-to-floor 3,06 m, 31 typical floors (+17,00 → +108,80), penthouse +111,86 / +114,92, roof +117,98.

Interpretations (not explicit in the DWG): materials and colors, window sill heights, the slab-edge ring rendered as a 1 m
parapet/planter, garage facade openings, the surrounding city.
