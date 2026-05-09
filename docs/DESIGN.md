# MiharaScape 設計書

技術アーキテクチャ・実装の詳細・運用フローを記載する。

---

## 1. アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────┐
│                   静的Webアプリ                         │
│                                                          │
│  ┌───────────┐    ┌────────────────┐    ┌──────────┐ │
│  │ index.html│←→ │ photos.geojson │←→ │ photos/  │ │
│  │ (Leaflet) │    │ (FeatureCol.)  │    │ thumbs/  │ │
│  └───────────┘    └────────────────┘    │simulations/│ │
│                                          └──────────┘ │
└──────────────────────────┬──────────────────────────┘
                           │
                  GitHub Pages 配信
                           │
                  motoki-design.github.io/
                       mihara-photo-map/
                           │
                       ブラウザ
                  （PC/スマホ／モダンブラウザ）
```

ビルドステップなし。HTML+JSのみで動作する完全な静的サイト。データはGeoJSONとローカル画像のみ。

## 2. 技術スタック

| 階層 | 技術 | バージョン | 役割 |
|------|------|------------|------|
| フロントエンド | Vanilla HTML/CSS/JS | ES2020+ | UI |
| 地図ライブラリ | Leaflet.js | 1.9.4（CDN） | 地図表示・ピン・ポップアップ |
| ベース地図 | OpenStreetMap | — | デフォルトタイル |
| ベース地図（補助） | 地理院タイル | — | 切替候補（淡色／標準） |
| 画像処理 | Python + Pillow | 11.x | リサイズバッチ |
| データ生成 | Python（標準ライブラリ） | 3.13 | md→GeoJSON変換 |
| ホスティング | GitHub Pages | — | 静的配信 |
| バージョン管理 | Git + GitHub | — | コード・データ管理 |

依存外部CDN：
- `https://unpkg.com/leaflet@1.9.4/dist/leaflet.css`
- `https://unpkg.com/leaflet@1.9.4/dist/leaflet.js`
- `https://cyberjapandata.gsi.go.jp/xyz/{pale,std}/...`
- `https://{s}.tile.openstreetmap.org/...`

## 3. データフロー

```
[1] 原寸写真（ネットワーク共有）
        \\192.168.0.241\...\@Photo\20260427\IMG_*.JPG
              │ （Pillow）
              ▼
[2] リサイズ（一次：ネットワーク共有）
        \\192.168.0.241\...\@Photo\リサイズ写真_20260427\
            ├ web\IMG_*.jpg     (1280px, JPG q80)
            └ thumbs\IMG_*.jpg  (200px,  JPG q75)
              │ （shutil.copy2）
              ▼
[3] リサイズ（二次：リポジトリ）
        assets/photos/IMG_*.jpg
        assets/thumbs/IMG_*.jpg

[4] 写真メタデータ（プロジェクト本体）
        06_経緯ログ/現地写真ログ_2026-04-27.md

[5] 場所辞書 ＋ シミュレーション辞書（リポジトリ）
        data/location_dict.json
        data/simulations.json
              │ （build_geojson.py で統合）
              ▼
[6] photos.geojson（リポジトリ）
        assets/photos.geojson

[7] シミュレーション画像（プロジェクト本体）
        07_景観シミュレーション/009_*.png
              │ （Pillow / 個別変換）
              ▼
[8] Web用シミュ画像（リポジトリ）
        assets/simulations/IMG_0009_*.jpg

[9] 公開
        git push → GitHub Actions → GitHub Pages
              │
              ▼
        https://motoki-design.github.io/mihara-photo-map/
```

## 4. ディレクトリ構成

```
mihara-photo-map/
├ index.html                    エントリポイント（HTML+CSS+JS統合）
├ README.md                     リポジトリ概要
├ .gitignore                    __pycache__等の除外
├ docs/
│  ├ SPEC.md                    仕様書（本書と並列）
│  ├ DESIGN.md                  設計書（本書）
│  ├ USER_MANUAL.md             使い方説明書（詳細）
│  └ QUICK_GUIDE.md             簡単マニュアル（社内向け）
├ assets/
│  ├ photos.geojson             写真のジオJSON（build_geojson.pyが生成）
│  ├ photos/IMG_*.jpg           Web用写真（resize_photos.pyが生成）
│  ├ thumbs/IMG_*.jpg           サムネ（同上）
│  └ simulations/IMG_NNNN_*.jpg シミュレーション画像（手動or別スクリプト）
├ data/
│  ├ location_dict.json         場所推定→緯度経度の辞書（手動メンテ）
│  └ simulations.json           写真ID→シミュレーションバリアントの辞書（手動メンテ）
└ scripts/
   ├ resize_photos.py           原寸→Web版＋サムネのバッチ
   └ build_geojson.py           ログ＋辞書から GeoJSON 生成
```

## 5. 主要コンポーネント

### 5.1 index.html

**責務**：単一ファイルでUI／状態管理／イベント処理／地図描画をすべて担う。

主要なJS要素：

| 識別子 | 種類 | 役割 |
|--------|------|------|
| `osm`, `gsiPale`, `gsiStd` | L.tileLayer | ベースマップ3種 |
| `map` | L.Map | メイン地図インスタンス |
| `allFeatures` | Array | 読み込んだ全GeoJSON Feature |
| `markers` | Array<L.Marker> | 全ピン |
| `routeLine` | L.Polyline | 踏査ルート線 |
| `selectedCats` | Set<String> | 現在ONのカテゴリ集合 |
| `simOnlyMode` | Boolean | シミュ付きのみフィルタ |
| `textFilter` | String | 検索ボックスの入力 |
| `modalState` | Object | モーダル表示中の写真とバリアント |
| `makeMarker(f)` | Function | Feature→L.Marker生成（ピン色＝精度別） |
| `buildPopup(p)` | Function | ポップアップHTMLを組み立て（escAttr/escHtml経由） |
| `applyFilter()` | Function | カテゴリ／シミュ／検索を統合してマーカー表示制御 |
| `renderSidebar()` | Function | 表示中マーカーをサイドリストに反映 |
| `openModalForFeature(file, idx)` | Function | モーダルを写真IDとバリアントindex指定で開く |
| `buildModalTabs()` / `showModalVariant(idx)` | Function | モーダルのタブUI |
| `buildRouteLine()` | Function | 撮影時刻順polyline生成 |

**XSS対策**：ユーザーデータ（場所名・件名等）はすべて `escHtml()` / `escAttr()` 経由でエスケープ。

**イベントハンドリング**：ポップアップ内のサムネ・シミュボタンのクリックは、document レベルのイベントデリゲーション（`data-action="open-modal"` 属性ベース）。インライン `onclick` は使わない（過去にHTML破損バグの原因となった）。

### 5.2 scripts/resize_photos.py

**責務**：原寸写真を Web用1280px ＋ サムネ200px にリサイズし、ネットワーク共有とリポジトリの両方に保存。

**処理フロー**：
1. 原寸フォルダから `IMG_*.JPG` を列挙
2. 各ファイルについて：
   - PIL.Image.open → `ImageOps.exif_transpose`（Orientation補正）
   - RGB変換
   - thumbnail((1280,1280)) → JPGq80 で保存（ネットワーク共有 web/）
   - thumbnail((200,200)) → JPGq75 で保存（ネットワーク共有 thumbs/）
   - `--no-repo-copy` 指定がなければ shutil.copy2 でリポジトリにもコピー
3. 累計サイズと処理時間を出力

**起動オプション**：
- `--limit N`：先頭N枚のみ処理（テスト用）
- `--no-repo-copy`：リポジトリ二次コピーをスキップ

### 5.3 scripts/build_geojson.py

**責務**：写真ログ.md＋辞書類から photos.geojson を生成。

**処理フロー**：
1. **ログ抽出**：`現地写真ログ_2026-04-27.md` を正規表現で解析。117エントリそれぞれから「ファイル名／撮影時刻／被写体／場所推定／業務関連ポイント／景観シミュレーション案」を抽出。
2. **辞書読み込み**：`location_dict.json`（35地点）と `simulations.json`（写真ID→バリアント）。
3. **位置推定 ステージ1（辞書マッチ）**：場所推定文字列の中に辞書の `match` キーワードのいずれかが含まれていれば、その地点として確定（`accuracy: confirmed`）。
4. **位置推定 ステージ2（参照継承）**：場所推定が「IMG_NNNNと同位置／同地点／同方向／同近辺／と類似」を含む場合、参照先の写真の位置をコピー（`accuracy: inherited`）。最大3周ループ。
5. **位置推定 ステージ3（時系列補間）**：未確定の写真は、撮影時刻で前後の確定写真の間を**線形補間**（`accuracy: interpolated`）。両端の場合は外挿（`extrapolated`）、両側ともなければ駅中心にフォールバック（`fallback`）。
6. **カテゴリ判定**：業務関連ポイント文字列内のキーワードから、9カテゴリのタグを推定（複数可）。
7. **シミュレーション merge**：`simulations.json` から該当写真IDのバリアント配列を properties.simulations に格納。
8. **GeoJSON書き出し**：FeatureCollection で `assets/photos.geojson` に保存。

**カテゴリキーワード辞書**：
- 照明 → `["街路灯", "ライトアップ", "照明", "LED", "灯具", "ガス灯", "光源"]`
- 舗装 → `["舗装", "タイル", "御影石", "石材", "レンガ", "タコ柄"]`
- サイン → `["サイン", "看板", "案内", "誘導", "解説", "バナー", "標識", "標柱", "道標", "ピクト"]`
- 植栽 → `["植栽", "街路樹", "桜", "松", "フェニックス", "並木", "樹冠", "樹木"]`
- ストリートファニチャー → `["ベンチ", "ボラード", "柵", "手すり", "ゴミ箱", "フェンス", "パラペット"]`
- 史跡 → `["三原城", "中門跡", "船入櫓跡", "石垣", "天主台", "史跡", "文化財"]`
- 景観阻害物 → `["撤去", "阻害", "景観阻害", "過剰", "休止中", "シート"]`
- 建築 → `["建物", "ホテル", "マンション", "雑居ビル", "アーケード", "屋根"]`
- 広場 → `["広場", "オープンスペース", "ロータリー"]`

## 6. 場所推定アルゴリズムの詳細

### 6.1 辞書マッチ（confirmed）

```
for place in places:
  for keyword in place.match:
    if keyword in photo.location_text:
      photo.lat, photo.lon = place.lat, place.lon
      photo.accuracy = "confirmed"
      break
```

最初にマッチした地点が採用される（辞書登録順を優先順位として活用）。

### 6.2 参照継承（inherited）

「IMG_NNNNと同位置」のような参照表現を最大3周ループで解決：

```
for round in range(3):
  for photo in unresolved:
    target = re.search(r'IMG_(\d{4})', photo.location_text)
    if target and ('同位置' or '同地点' or ...) in photo.location_text:
      if target_photo.has_coords:
        photo.lat, photo.lon = target_photo.lat, target_photo.lon
        photo.accuracy = "inherited"
```

3周ループにより、A→B→C のような連鎖参照も解決可能。

### 6.3 時系列補間（interpolated/extrapolated）

未確定写真は、撮影時刻順にソートした確定済み写真リストの中から「前」と「後」の最近接を取得し、時刻比率で線形補間：

```
ratio = (photo.t - before.t) / (after.t - before.t)
photo.lat = before.lat + (after.lat - before.lat) * ratio
photo.lon = before.lon + (after.lon - before.lon) * ratio
```

両端の場合（前 or 後 のみ存在）は外挿として最近接の確定位置を採用（`extrapolated`）。
両端どちらもなければ駅中心 (34.39810, 133.07920) にフォールバック（`fallback`）。

### 6.4 結果（2026-05-09 時点）

- confirmed: 106 / 117 (91%)
- inherited:   5 / 117 ( 4%)
- interpolated: 6 / 117 ( 5%)
- extrapolated: 0
- fallback:     0

## 7. デプロイ

### 7.1 手順
1. リポジトリで変更を `git commit`
2. `git push origin main`
3. GitHub Actions の `pages-build-deployment` ワークフローが自動起動（45秒前後で完了）
4. https://motoki-design.github.io/mihara-photo-map/ に反映

### 7.2 GitHub Pages 設定
- Source: `main` ブランチ root
- Custom domain: 未設定
- HTTPS: 強制（デフォルト）
- 設定方法（gh CLI）：
  ```bash
  gh api -X POST repos/motoki-design/mihara-photo-map/pages \
    -f "source[branch]=main" -f "source[path]=/"
  ```

### 7.3 リソース URL
| 種別 | URL |
|------|-----|
| サイト | https://motoki-design.github.io/mihara-photo-map/ |
| GeoJSON | https://motoki-design.github.io/mihara-photo-map/assets/photos.geojson |
| サムネ例 | https://motoki-design.github.io/mihara-photo-map/assets/thumbs/IMG_0001.jpg |
| Web写真例 | https://motoki-design.github.io/mihara-photo-map/assets/photos/IMG_0089.jpg |
| シミュ例 | https://motoki-design.github.io/mihara-photo-map/assets/simulations/IMG_0009_A.jpg |

## 8. 運用フロー

### 8.1 写真メタの修正
1. `06_経緯ログ/現地写真ログ_2026-04-27.md` を編集
2. `python scripts/build_geojson.py` を実行
3. `git commit -m "..." && git push`

### 8.2 場所推定の精度向上（座標校正）
1. `data/location_dict.json` を編集（lat/lon を実地点に合わせて修正、または新規地点を追加）
2. `python scripts/build_geojson.py` を再実行
3. commit/push

### 8.3 新しい現地調査の写真を追加（例：5/26調査）
**当面の方針案**：
- ネットワーク共有に新フォルダ `\\...\@Photo\20260526\` を配置
- リサイズスクリプトを `--src-dir` フラグで対応するよう拡張（フェーズ2）
- ログを `06_経緯ログ/現地写真ログ_2026-05-26.md` で別ファイルとして作成
- build_geojson.py を複数ログ対応に拡張
- 写真を `assets/photos/` 内で日付プレフィクス（例：`20260526_IMG_0001.jpg`）に分けるか、サブフォルダ化

### 8.4 シミュレーションの追加
1. `07_景観シミュレーション/` で生成した画像（PNG）を、Pillowで JPG 変換して `assets/simulations/` に配置
2. `data/simulations.json` に新しいエントリを追加：
   ```json
   "IMG_0089.JPG": [
     { "id": "A", "title": "...", "image": "assets/simulations/IMG_0089_A.jpg", "summary": "..." }
   ]
   ```
3. `python scripts/build_geojson.py` を再実行
4. commit/push

該当する写真ピンは自動的に橙縁取りに変わり、ポップアップに「景観シミュレーション ▶」セクションが追加される。

## 9. セキュリティ・XSS対策

- ユーザー入力（実際にはGeoJSON経由のテキスト）は `escHtml()` / `escAttr()` で必ずエスケープしてからDOMに挿入
- インライン `onclick` は使用しない（HTML破損リスク回避＋XSS対策）
- イベントは document レベルのデリゲーションで処理
- 外部CDN（Leaflet）は SRI（integrity属性）付きで読み込み

## 10. 既知の制約

- 場所辞書は守山の概算座標（35地点）。実地点との照合が未完
- 117枚の精度内訳：confirmed 91%、その他は補間・継承（赤・橙ピン）
- ピンのドラッグ補正UIは未実装
- 写真のEXIFは Orientation のみ反映、GPSは元画像に存在しないため埋込なし
- フェーズ2以降の機能（複数日対応、認証、ARオーバーレイ等）は未実装
