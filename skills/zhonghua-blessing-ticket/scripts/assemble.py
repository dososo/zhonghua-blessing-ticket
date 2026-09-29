#!/usr/bin/env python3
# 版权归爆裂队长NEXT及贡献者所有；依木兰宽松许可证第2版授权，按原样提供，无担保。
# SPDX-License-Identifier: MulanPSL-2.0
"""可选：把已完成的独立卡片无损拼版。绝不放大、裁切或覆盖卡片主标题。
需要Pillow；这只影响可选拼版，不影响原生总览生图与离线计划。
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path
from engine import write_json, sha256_file


def assemble(images, output, columns=5, gap=12, margin=24, background='#EEE4D0'):
    try:from PIL import Image
    except ImportError as exc:raise ValueError('此可选拼版功能需要Pillow。请在项目虚拟环境安装requirements-optional.txt；不要改为生成式重画。') from exc
    if not images or len(images)>10:raise ValueError('每幅拼版接受1至10张独立图片。')
    if not 1<=columns<=10 or gap<0 or margin<0:raise ValueError('拼版参数不合法。')
    output=Path(output)
    if output.resolve() in [Path(p).resolve() for p in images]:raise ValueError('输出不能覆盖输入原图。')
    cards=[]
    try:
        for p in images:
            with Image.open(p) as im:
                im.load()
                cards.append(im.convert('RGB'))
        size=cards[0].size
        if any(im.size!=size for im in cards):raise ValueError('各卡实际像素不同；本工具拒绝静默裁切或放大，请先生成相同规格的独立卡。')
        columns=min(columns,len(cards));rows=math.ceil(len(cards)/columns)
        w=columns*size[0]+(columns-1)*gap+2*margin
        h=rows*size[1]+(rows-1)*gap+2*margin
        if w*h>120_000_000:raise ValueError('拼版超过1.2亿像素上限，请减少单次卡数。')
        canvas=Image.new('RGB',(w,h),background)
        for i,im in enumerate(cards):canvas.paste(im,(margin+i%columns*(size[0]+gap),margin+i//columns*(size[1]+gap)))
        output.parent.mkdir(parents=True,exist_ok=True)
        canvas.save(output,format='PNG')
        result={'kind':'由独立卡无损拼版','actual_pixels':[w,h],'card_actual_pixels':list(size),'count':len(cards),
                'columns':columns,'rows':rows,'upscaled':False,'cropped':False,'principal_text_overlaid':False,
                'native_generation_pixels':'未知；须查各输入图生图回执','inputs':[{'filename':Path(p).name,'sha256':sha256_file(Path(p))} for p in images],
                'output_sha256':sha256_file(output)}
        write_json(output.with_suffix('.receipt.json'),result)
        return result
    finally:
        for im in cards:im.close()


def main(argv=None):
    p=argparse.ArgumentParser(description='无损拼版，不能从低清总览制造独立高清卡')
    p.add_argument('images',nargs='+',type=Path);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--columns',type=int,default=5);p.add_argument('--gap',type=int,default=12);p.add_argument('--margin',type=int,default=24)
    a=p.parse_args(argv)
    try:print(json.dumps(assemble(a.images,a.out,a.columns,a.gap,a.margin),ensure_ascii=False,indent=2));return 0
    except (ValueError,OSError) as e:print('未完成拼版：'+str(e),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
