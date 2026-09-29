#!/usr/bin/env python3
# 版权归爆裂队长NEXT及贡献者所有；依木兰宽松许可证第2版授权，按原样提供，无担保。
# SPDX-License-Identifier: MulanPSL-2.0
"""离线计划工具。该命令生成设计方案，不伪装为已经生成图片。"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from engine import (VERSION, SKILL_ROOT, libraries, read_json, write_json, compile_single, compile_canvas,
                    history_entries, reserve_history, validate_all, image_info, create_receipt)


def dump_result(obj, out=None):
    if out:
        write_json(Path(out),obj)
        if 'prompt' in obj:Path(out).with_suffix('.prompt.txt').write_text(obj['prompt']+'\n',encoding='utf-8')
        print('已写入：'+str(Path(out).resolve()))
        if obj.get('status')=='planned_not_rendered':print('当前仅完成设计方案；下一步由宿主原生图像工具生成成图。')
    else:print(json.dumps(obj,ensure_ascii=False,indent=2))


def main(argv=None):
    parser=argparse.ArgumentParser(description='中华民族祝福票：方案编译、总览计划与真实回执')
    parser.add_argument('--version',action='version',version=VERSION)
    sub=parser.add_subparsers(dest='cmd',required=True)
    sub.add_parser('list',help='查看55个民族')
    sub.add_parser('doctor',help='只检查本地文件与Python，不冒称探测到宿主图像工具')
    va=sub.add_parser('validate',help='离线完整性检查');va.add_argument('--out')
    single=sub.add_parser('single',help='编译单张图文一体方案')
    single.add_argument('--ethnic',required=True);single.add_argument('--blessing',required=True)
    single.add_argument('--format',default='3:4');single.add_argument('--seed',type=int,default=0)
    single.add_argument('--variation',type=int,default=0);single.add_argument('--labels',action='store_true')
    single.add_argument('--history',type=Path);single.add_argument('--out',required=True)
    ca=sub.add_parser('canvas',help='编译十卡总览或独立卡拼版计划')
    ca.add_argument('--start',type=int,default=1);ca.add_argument('--count',type=int)
    ca.add_argument('--strategy',choices=['overview','assembled'],default='overview')
    ca.add_argument('--format',default='3:4');ca.add_argument('--seed',type=int,default=0)
    ca.add_argument('--no-labels',action='store_true');ca.add_argument('--blessing')
    ca.add_argument('--history',type=Path);ca.add_argument('--out',required=True)
    al=sub.add_parser('all',help='生成六批55民族计划，仍不代表55张图已经产生');al.add_argument('--out-dir',type=Path,required=True)
    ins=sub.add_parser('inspect',help='读取真实PNG/JPEG尺寸');ins.add_argument('image',type=Path);ins.add_argument('--out')
    rec=sub.add_parser('receipt',help='记录实际成图，验收仍由人工或宿主视觉完成')
    rec.add_argument('--plan',type=Path,required=True);rec.add_argument('--image',type=Path,required=True)
    rec.add_argument('--transcription',help='依卡位顺序，以|分隔准确转录的主标题')
    rec.add_argument('--note');rec.add_argument('--out',required=True)
    args=parser.parse_args(argv)
    try:
        if args.cmd=='list':
            for s in libraries()[0]:print(f'{s["id"]}  {s["name"]}  {s["route"]}')
        elif args.cmd=='doctor':
            report=validate_all()
            dump_result({'version':VERSION,'python':sys.version.split()[0],'skill_root':str(SKILL_ROOT),'reference_ok':report['reference_integrity'],
                         'library_ok':report['ok'],'native_image_tool':'须由Codex会话读取当前可用工具后确认','api_key_needed_for_planning':False,
                         'runtime_requirements':'Python 3.9或更新；纯Skill使用不需要运行本命令。'})
            return 0 if report['ok'] else 1
        elif args.cmd=='validate':
            report=validate_all();dump_result(report,args.out);return 0 if report['ok'] else 1
        elif args.cmd=='single':
            p=compile_single(args.ethnic,args.blessing,args.format,args.seed,args.variation,args.labels,history_entries(args.history))
            # 先完成方案文件再提交历史；输出目录失败时不污染历史。
            dump_result(p,args.out);reserve_history(args.history,[p])
        elif args.cmd=='canvas':
            count=args.count if args.count is not None else min(10,56-args.start)
            p=compile_canvas(args.start,count,args.seed,args.format,args.strategy,not args.no_labels,args.blessing,history_entries(args.history))
            dump_result(p,args.out);reserve_history(args.history,p['cards'])
        elif args.cmd=='all':
            args.out_dir.mkdir(parents=True,exist_ok=True)
            for start in (1,11,21,31,41,51):
                c=compile_canvas(start,min(10,56-start));dump_result(c,args.out_dir/f'canvas-{start:02d}-{start+c["grid"]["count"]-1:02d}.json')
        elif args.cmd=='inspect':dump_result(image_info(args.image),args.out)
        elif args.cmd=='receipt':dump_result(create_receipt(read_json(args.plan),args.image,args.transcription,args.note),args.out)
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('未完成：'+str(exc),file=sys.stderr);return 2

if __name__=='__main__':
    # 管道输出统一为UTF-8，避免Windows默认编码无法表示中文。
    for stream in (sys.stdout,sys.stderr):stream.reconfigure(encoding='utf-8')
    raise SystemExit(main())
