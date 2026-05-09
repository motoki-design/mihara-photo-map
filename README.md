# 三原駅周辺公共空間デザイン検討業務　現地写真マップ

2026-04-27に三原駅〜三原内港エリアで踏査した写真117枚を、地図上のピンとして配置し、クリックで写真と業務メモが閲覧できるWebアプリ。

## ローカル起動

```bash
cd mihara-photo-map
python -m http.server 8000
```

ブラウザで http://localhost:8000/ を開く。

## ディレクトリ構成

```
mihara-photo-map/
├ index.html                    Leaflet地図UI（単一HTML）
├ assets/
│  ├ photos.geojson             写真ピンのGeoJSON
│  ├ photos/                    Web用JPG (長辺1280px)
│  └ thumbs/                    サムネ (長辺200px)
├ data/
│  └ location_dict.json         場所推定→緯度経度の辞書
└ scripts/
   ├ resize_photos.py           原寸→Web版＋サムネ生成
   └ build_geojson.py           ログ＋辞書から GeoJSON 生成
```

## データソース

- 原寸写真: `\\192.168.0.241\中国支社\★進行業務フォルダ\31096(R8)三原駅周辺公共空間（道路等）デザイン検討業務\07_WORK\@Photo\20260427\`
- リサイズ写真（一次保存）: `\\192.168.0.241\...\@Photo\リサイズ写真_20260427\`
- 写真メタデータ: `06_経緯ログ/現地写真ログ_2026-04-27.md`

## 公開状態

ローカル検証段階。写真公開可否は青木氏・市側との協議のうえ判断する。
