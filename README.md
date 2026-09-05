# Gecko Hide Generator

以 CadQuery 建立可重現、可編輯且適合 FDM 列印的守宮岩石躲避屋。模型是底部開放的中空單一 solid：圓角結構殼體、非對稱洞穴入口、四面有石縫的 irregular polygon 岩石，以及低矮的屋頂岩石。

## Requirements and installation

Python 3.11+、CadQuery、NumPy、trimesh 與 pytest。

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Generate

預設尺寸直接生成：

```bash
python build.py
```

完整 acceptance command：

```bash
python build.py --width 180 --depth 120 --height 75 --wall 4 --entrance-width 55 --entrance-height 40 --entrance-offset-x -30 --seed 12345
```

`--seed random` 會列印系統產生的 seed；將該數字再次傳入即可重現相同 geometry。`--preset small|medium|large` 載入 `presets/` JSON，任何 CLI 尺寸或 seed 參數會覆蓋 preset，例如：

```bash
python build.py --preset medium --width 200 --seed 999
```

輸出位於 `output/gecko_hide_seed_<seed>.stl` 與 `output/gecko_hide_seed_<seed>.step`。STEP 保留 CadQuery solid，STL 使用適合 FDM 的 0.15 mm linear deflection。生成等角預覽：

```bash
python render_preview.py output/gecko_hide_seed_12345.stl
```

預覽會輸出同目錄的 `gecko_hide_seed_<seed>_preview.png`。

## Parameters

`GeckoHideConfig` 提供 `width`、`depth`、`height`、`wall_thickness`、`roof_thickness`、`bottom_open`、入口寬/高/X offset、stone 寬/高/depth/gap 範圍、polygon vertex count、irregularity、fillet 範圍、shell profile asymmetry、stone taper/bulge/section jitter、wall vertical jitter、roof rock count 與 `seed`。所有尺寸為 mm；不合理值（例如 wall < 3 mm、入口不在前牆內）會 raise `ValueError`，不會靜默修正。

## Validation and tests

每次 `build.py` 都會重新以 trimesh 載入 STL，檢查 finite vertices、watertight、單一 connected component、非零體積、尺寸界限與 `min Z = 0`。可單獨驗證：

```bash
python validate.py output/gecko_hide_seed_12345.stl --seed 12345
pytest
```

## 3D printing notes

預設 structural wall 為 4 mm，石縫至少 1.2 mm，石頭嵌入殼體至少 0.8 mm；底部完全開放且落在 Z=0，可直接放到列印平台。先以自己的 slicer 檢查材料、縮放與入口方向。

## Known limitations

第一版刻意不提供 GUI、可拆屋頂、通風孔、磁鐵孔、高頻表面 noise 或真實岩石掃描。裝飾 stone 的 fillet/union 在 OCC 無法處理時會安全略過該顆 stone；結構殼、入口、STL 或 STEP 的失敗仍會使 build 失敗。
