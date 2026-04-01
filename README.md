# MACRO DASHBOARD

Bloomberg Terminal-style macro dashboard. No build step — pure HTML + CDN.

## Files

```
macro-dashboard/
├── index.html        ← Toàn bộ dashboard (1 file duy nhất)
├── fetch_data.py     ← Python pipeline lấy dữ liệu thật
├── data/
│   ├── market.csv    ← IWM, SPY, QQQ, sector ETFs
│   ├── liquidity.csv ← M2, FED_BS, FFR, T10Y, T2Y, CPI
│   └── credit.csv    ← HY/IG spread, DXY, Oil, XLF, KRE
└── README.md
```

## Cách dùng

### Bước 1 — Lấy dữ liệu thật
```bash
pip install pandas yfinance fredapi
python fetch_data.py
```
→ Ghi file vào `data/` (dữ liệu từ 2005 đến hôm nay)

### Bước 2 — Chạy local
Mở `index.html` bằng trình duyệt (cần server do fetch CSV):
```bash
python -m http.server 8000
# → http://localhost:8000
```

### Bước 3 — Deploy GitHub Pages
```bash
git init
git add .
git commit -m "initial"
git branch -M main
git remote add origin https://github.com/USERNAME/macro-dashboard.git
git push -u origin main
```
→ GitHub → Settings → Pages → Source: `main` branch → Save

**Xong.** Truy cập: `https://USERNAME.github.io/macro-dashboard`

## Nguồn dữ liệu

| File | Nguồn | Series |
|------|-------|--------|
| market.csv | Yahoo Finance | IWM, SPY, QQQ, XLK, XLY, XLF, XLI, XLB, XLE, XLV, XLP, XLU, XLRE |
| liquidity.csv | FRED | M2SL, WALCL, FEDFUNDS, DGS10, DGS2, CPIAUCSL |
| credit.csv | FRED + Yahoo | BAMLH0A0HYM2, BAMLC0A0CM, DGS10, DX-Y.NYB, CL=F, XLF, KRE |

## Cập nhật dữ liệu

```bash
python fetch_data.py
git add data/*.csv
git commit -m "data refresh"
git push
```
