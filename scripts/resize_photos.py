# -*- coding: utf-8 -*-
r"""原寸写真を Web用1280px ＋ サムネ200px にリサイズし、ネットワーク共有とリポジトリに保存する。

一次保存: \\192.168.0.241\...\@Photo\リサイズ写真_20260427\{web,thumbs}\
二次コピー: ./assets/{photos,thumbs}/   （MVP動作確認用、--no-repo-copy で無効化可）
"""
import argparse
import sys
import shutil
import time
from pathlib import Path
from PIL import Image, ImageOps

sys.stdout.reconfigure(encoding='utf-8')

SRC_DIR = Path(r"\\192.168.0.241\中国支社\★進行業務フォルダ\31096(R8)三原駅周辺公共空間（道路等）デザイン検討業務\07_WORK\@Photo\20260427")
NETWORK_RESIZED_BASE = Path(r"\\192.168.0.241\中国支社\★進行業務フォルダ\31096(R8)三原駅周辺公共空間（道路等）デザイン検討業務\07_WORK\@Photo\リサイズ写真_20260427")
REPO_BASE = Path(__file__).resolve().parent.parent / "assets"

WEB_MAX = 1280
WEB_QUALITY = 80
THUMB_MAX = 200
THUMB_QUALITY = 75


def resize_one(src: Path, dst: Path, max_size: int, quality: int):
    """1枚を最長辺max_sizeにリサイズしてJPGで保存。EXIF Orientationも反映。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)  # 撮影時の縦横補正
        if im.mode != 'RGB':
            im = im.convert('RGB')
        im.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        im.save(dst, 'JPEG', quality=quality, optimize=True, progressive=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-repo-copy', action='store_true', help='リポジトリへの二次コピーをスキップ')
    ap.add_argument('--limit', type=int, default=0, help='処理枚数の上限（テスト用）')
    args = ap.parse_args()

    if not SRC_DIR.exists():
        print(f'ERROR: 原寸フォルダが見つかりません: {SRC_DIR}')
        sys.exit(1)

    files = sorted(SRC_DIR.glob('IMG_*.JPG'))
    if args.limit:
        files = files[:args.limit]
    print(f'対象: {len(files)} 枚')

    # 出力先
    net_web = NETWORK_RESIZED_BASE / 'web'
    net_thumb = NETWORK_RESIZED_BASE / 'thumbs'
    repo_web = REPO_BASE / 'photos'
    repo_thumb = REPO_BASE / 'thumbs'
    for d in [net_web, net_thumb]:
        d.mkdir(parents=True, exist_ok=True)
    if not args.no_repo_copy:
        for d in [repo_web, repo_thumb]:
            d.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    total_web_bytes = 0
    total_thumb_bytes = 0

    for i, src in enumerate(files, 1):
        name = src.stem.lower() + '.jpg'  # IMG_0001.JPG -> img_0001.jpg
        # 命名は元のままIMG_NNNN.jpg（小文字拡張子）が望ましいので、stemをそのまま使う
        name = src.stem + '.jpg'  # IMG_0001.jpg

        web_dst = net_web / name
        thumb_dst = net_thumb / name

        resize_one(src, web_dst, WEB_MAX, WEB_QUALITY)
        resize_one(src, thumb_dst, THUMB_MAX, THUMB_QUALITY)

        total_web_bytes += web_dst.stat().st_size
        total_thumb_bytes += thumb_dst.stat().st_size

        if not args.no_repo_copy:
            shutil.copy2(web_dst, repo_web / name)
            shutil.copy2(thumb_dst, repo_thumb / name)

        if i % 20 == 0 or i == len(files):
            elapsed = time.time() - t0
            print(f'  [{i}/{len(files)}] {name}  累計 web={total_web_bytes/1024/1024:.1f}MB thumbs={total_thumb_bytes/1024/1024:.1f}MB  経過{elapsed:.1f}s')

    print()
    print('完了:')
    print(f'  Web版（1280px）: {total_web_bytes/1024/1024:.2f} MB （{total_web_bytes/len(files)/1024:.0f} KB/枚）')
    print(f'  サムネ（200px） : {total_thumb_bytes/1024/1024:.2f} MB （{total_thumb_bytes/len(files)/1024:.0f} KB/枚）')
    print(f'  合計           : {(total_web_bytes+total_thumb_bytes)/1024/1024:.2f} MB')
    print(f'  ネットワーク保存先: {NETWORK_RESIZED_BASE}')
    if not args.no_repo_copy:
        print(f'  リポジトリコピー: {REPO_BASE}')


if __name__ == '__main__':
    main()
