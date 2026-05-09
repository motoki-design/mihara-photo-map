# -*- coding: utf-8 -*-
"""現地写真ログ.md ＋ location_dict.json から photos.geojson を生成。

処理：
  1. ログから 117 写真の各エントリ（ファイル名・撮影時刻・場所推定・業務関連ポイント・シミュ案）を抽出
  2. 場所推定文字列を辞書のキーワードと照合 → 確定（confirmed）
  3. 場所推定が「IMG_NNNNと同位置」「IMG_NNNNと同地点」の場合、参照先の位置を継承（inherited）
  4. 残りは撮影時刻で前後の confirmed/inherited 写真の間を線形補間（interpolated）
  5. 業務関連ポイント文字列から照明/舗装/サイン/植栽/SF/史跡/景観阻害物のカテゴリを推定（複数可）
  6. GeoJSON FeatureCollection で出力

出力: assets/photos.geojson
"""
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
SRC_LOG = Path(r"c:\Users\motok\Dropbox\03_Cursor_Projects\004_31680_三原駅周辺公共空間デザイン検討\06_経緯ログ\現地写真ログ_2026-04-27.md")
DICT_PATH = ROOT / "data" / "location_dict.json"
OUT_PATH = ROOT / "assets" / "photos.geojson"

# ─── カテゴリ判定キーワード ───
CATEGORY_KEYWORDS = {
    "照明": ["街路灯", "ライトアップ", "照明", "LED", "灯具", "ガス灯", "光源"],
    "舗装": ["舗装", "タイル", "御影石", "石材", "レンガ", "タコ柄"],
    "サイン": ["サイン", "看板", "案内", "誘導", "解説", "バナー", "標識", "標柱", "道標", "ピクト"],
    "植栽": ["植栽", "街路樹", "桜", "松", "フェニックス", "並木", "樹冠", "樹木"],
    "ストリートファニチャー": ["ベンチ", "ボラード", "柵", "手すり", "ゴミ箱", "フェンス", "パラペット"],
    "史跡": ["三原城", "中門跡", "船入櫓跡", "石垣", "天主台", "史跡", "文化財"],
    "景観阻害物": ["撤去", "阻害", "景観阻害", "過剰", "休止中", "シート"],
    "建築": ["建物", "ホテル", "マンション", "雑居ビル", "アーケード", "屋根"],
    "広場": ["広場", "オープンスペース", "ロータリー"]
}


def categorize(business_point: str) -> list:
    """業務関連ポイント文字列からカテゴリタグを推定。"""
    tags = []
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in business_point:
                tags.append(cat)
                break
    return tags


def parse_log(path: Path):
    """写真ログから 117 エントリを抽出。"""
    text = path.read_text(encoding='utf-8')
    entry_pat = re.compile(
        r'^## (IMG_\d+\.JPG)（(\d{2}:\d{2}:\d{2})）\s*\n'
        r'((?:- \*\*.+?\*\*: .+\n?)+)',
        re.MULTILINE
    )
    field_pat = re.compile(r'- \*\*(.+?)\*\*: (.+?)(?=\n- \*\*|\n##|\n---|\Z)', re.DOTALL)

    def strip_md(s):
        s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
        s = re.sub(r'`(.+?)`', r'\1', s)
        return re.sub(r'[ \t]+', ' ', s).strip()

    entries = []
    for m in entry_pat.finditer(text):
        fname, ts = m.group(1), m.group(2)
        body = m.group(3)
        fields = {fm.group(1).strip(): strip_md(fm.group(2).strip())
                  for fm in field_pat.finditer(body)}
        entries.append({
            "file": fname,
            "time_str": ts,
            "subject": fields.get("被写体", ""),
            "location_text": fields.get("場所推定", ""),
            "business_point": fields.get("業務関連ポイント", ""),
            "simulation_idea": fields.get("景観シミュレーション案", "")
        })
    return entries


def match_place(location_text: str, places: list):
    """場所推定文字列を辞書と照合。マッチした最初の地点を返す。"""
    for p in places:
        for kw in p["match"]:
            if kw in location_text:
                return p
    return None


def find_inherit_target(location_text: str):
    """「IMG_NNNNと同位置／同地点／同方向」のような参照を抽出。"""
    m = re.search(r'IMG_(\d{4})', location_text)
    if m and ('同位置' in location_text or '同地点' in location_text or '同方向' in location_text or '同近辺' in location_text or 'と類似' in location_text):
        return f'IMG_{m.group(1)}.JPG'
    return None


def time_to_dt(ts: str):
    return datetime.strptime(f'2026-04-27 {ts}', '%Y-%m-%d %H:%M:%S')


def linear_interp(t_target, t1, p1, t2, p2):
    """時刻線形補間。"""
    total = (t2 - t1).total_seconds()
    if total == 0:
        return p1
    ratio = (t_target - t1).total_seconds() / total
    lat = p1[0] + (p2[0] - p1[0]) * ratio
    lon = p1[1] + (p2[1] - p1[1]) * ratio
    return (lat, lon)


def main():
    # 入力読み込み
    entries = parse_log(SRC_LOG)
    print(f'写真ログ entries: {len(entries)}')

    dict_obj = json.loads(DICT_PATH.read_text(encoding='utf-8'))
    places = dict_obj["places"]
    print(f'場所辞書 places: {len(places)}')

    # ステージ1: 辞書マッチ
    for e in entries:
        e["dt"] = time_to_dt(e["time_str"])
        place = match_place(e["location_text"], places)
        if place:
            e["lat"] = place["lat"]
            e["lon"] = place["lon"]
            e["place_id"] = place["id"]
            e["place_name"] = place["name"]
            e["accuracy"] = "confirmed"

    confirmed_count = sum(1 for e in entries if e.get("accuracy") == "confirmed")
    print(f'ステージ1（辞書マッチ）: {confirmed_count}/{len(entries)}')

    # ステージ2: 「IMG_NNNNと同位置」継承（最大3周）
    by_file = {e["file"]: e for e in entries}
    for _ in range(3):
        changed = 0
        for e in entries:
            if "lat" in e:
                continue
            target = find_inherit_target(e["location_text"])
            if target and target in by_file and "lat" in by_file[target]:
                src = by_file[target]
                e["lat"] = src["lat"]
                e["lon"] = src["lon"]
                e["place_id"] = src.get("place_id", "inherited")
                e["place_name"] = src.get("place_name", "（参照）") + f' ← {target}'
                e["accuracy"] = "inherited"
                changed += 1
        if changed == 0:
            break

    inherited_count = sum(1 for e in entries if e.get("accuracy") == "inherited")
    print(f'ステージ2（参照継承）: {inherited_count}')

    # ステージ3: 時系列補間
    located = [e for e in entries if "lat" in e]
    located.sort(key=lambda x: x["dt"])

    for e in entries:
        if "lat" in e:
            continue
        # 前後の located を探す
        before = None
        after = None
        for le in located:
            if le["dt"] <= e["dt"]:
                before = le
            elif after is None and le["dt"] > e["dt"]:
                after = le
                break
        if before and after:
            lat, lon = linear_interp(e["dt"], before["dt"], (before["lat"], before["lon"]),
                                     after["dt"], (after["lat"], after["lon"]))
            e["lat"] = lat
            e["lon"] = lon
            e["place_id"] = "interpolated"
            e["place_name"] = f'{before["place_name"]} → {after["place_name"]} の途中'
            e["accuracy"] = "interpolated"
        elif before:  # 末端
            e["lat"] = before["lat"]
            e["lon"] = before["lon"]
            e["place_id"] = "interpolated"
            e["place_name"] = f'{before["place_name"]} 付近（外挿）'
            e["accuracy"] = "extrapolated"
        elif after:
            e["lat"] = after["lat"]
            e["lon"] = after["lon"]
            e["place_id"] = "interpolated"
            e["place_name"] = f'{after["place_name"]} 付近（外挿）'
            e["accuracy"] = "extrapolated"
        else:
            e["lat"] = 34.39810
            e["lon"] = 133.07920
            e["place_id"] = "fallback"
            e["place_name"] = "三原駅（フォールバック）"
            e["accuracy"] = "fallback"

    interp_count = sum(1 for e in entries if e.get("accuracy") in ("interpolated", "extrapolated"))
    print(f'ステージ3（時系列補間）: {interp_count}')

    # GeoJSON 構築
    features = []
    for e in entries:
        cats = categorize(e["business_point"])
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(e["lon"], 6), round(e["lat"], 6)]
            },
            "properties": {
                "file": e["file"],
                "time": e["time_str"],
                "subject": e["subject"],
                "location_text": e["location_text"],
                "business_point": e["business_point"],
                "simulation_idea": e["simulation_idea"],
                "place_id": e.get("place_id", ""),
                "place_name": e.get("place_name", ""),
                "accuracy": e.get("accuracy", ""),
                "categories": cats,
                "thumb": f'assets/thumbs/{Path(e["file"]).stem}.jpg',
                "photo": f'assets/photos/{Path(e["file"]).stem}.jpg'
            }
        })

    gj = {"type": "FeatureCollection", "features": features}
    OUT_PATH.write_text(json.dumps(gj, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n保存: {OUT_PATH}')
    print(f'総 features: {len(features)}')

    # 精度別集計
    acc_count = {}
    for e in entries:
        acc_count[e["accuracy"]] = acc_count.get(e["accuracy"], 0) + 1
    print('精度別:', acc_count)

    # カテゴリ別集計
    cat_count = {}
    for f in features:
        for c in f["properties"]["categories"]:
            cat_count[c] = cat_count.get(c, 0) + 1
    print('カテゴリ別:', dict(sorted(cat_count.items(), key=lambda x: -x[1])))


if __name__ == '__main__':
    main()
