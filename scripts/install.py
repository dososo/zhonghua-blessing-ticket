#!/usr/bin/env python3
# 版权归爆裂队长NEXT及贡献者所有；依木兰宽松许可证第2版授权，按原样提供，无担保。
# SPDX-License-Identifier: MulanPSL-2.0
"""安全安装单个自包含Skill。不更改全局Codex配置，不启用MCP，不联网。"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

NAME='zhonghua-blessing-ticket'
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'skills'/NAME
MARKER='.zhbt-install.json'


def install(target_root: Path, replace: bool=False) -> dict:
    target_root=target_root.expanduser().resolve()
    if SOURCE.resolve() == target_root or SOURCE.resolve() in target_root.parents:
        raise ValueError('目标不能位于源Skill目录内部，避免递归复制。')
    target_root.mkdir(parents=True,exist_ok=True)
    target=target_root/NAME
    if target.resolve()==SOURCE.resolve():raise ValueError('源和目标相同，不需要重复安装。')
    # 不跟随已有软链接并写进未知目录。
    exists=os.path.lexists(str(target))
    if exists and not replace:raise ValueError('发现已有同名Skill，未覆盖。确认升级后使用--replace；原目录将自动备份。')
    if not (SOURCE/'SKILL.md').is_file():raise ValueError('源Skill缺失，请确认解压了整个仓库。')
    stage=Path(tempfile.mkdtemp(prefix='.zhbt-stage-',dir=str(target_root)))
    backup=None
    try:
        candidate=stage/NAME
        shutil.copytree(SOURCE,candidate,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store'))
        (candidate/MARKER).write_text(json.dumps({'project':NAME,'version':'3.0.0'},ensure_ascii=False),encoding='utf-8')
        if exists:
            backup=target_root.parent/'zhbt-backups'/f'{NAME}-{uuid.uuid4().hex[:10]}'
            backup.parent.mkdir(parents=True,exist_ok=True)
            target.rename(backup)
        try:candidate.rename(target)
        except Exception:
            if backup is not None and not os.path.lexists(str(target)):backup.rename(target)
            raise
    finally:shutil.rmtree(stage,ignore_errors=True)
    return {'installed':str(target),'backup':str(backup) if backup else None,'version':'3.0.0'}


def uninstall(target_root: Path) -> str:
    target=target_root.expanduser().resolve()/NAME
    if target.is_symlink():raise ValueError('目标是软链接，未删除；请自行确认来源。')
    if not (target/MARKER).is_file():raise ValueError('没有本安装器的归属标记，未删除任何目录。')
    marker=json.loads((target/MARKER).read_text(encoding='utf-8'))
    if marker.get('project')!=NAME:raise ValueError('归属标记不匹配，未删除。')
    shutil.rmtree(target)
    return str(target)


def main(argv=None):
    if sys.version_info < (3,9):
        print('安装器需要Python3.9或更新；也可按README手动复制整个Skill目录。',file=sys.stderr);return 2
    p=argparse.ArgumentParser(description='安装中华民族祝福票Skill')
    p.add_argument('--scope',choices=['user','project'],default='user')
    p.add_argument('--project',type=Path,help='项目级安装的工作目录')
    p.add_argument('--replace',action='store_true',help='备份已存在的同名Skill再升级')
    p.add_argument('--uninstall',action='store_true',help='仅删除有本安装器归属标记的Skill')
    a=p.parse_args(argv)
    try:
        if a.scope=='project' and a.project is None:raise ValueError('项目安装须提供--project。')
        target=(Path.home() if a.scope=='user' else a.project)/'.agents/skills'
        result=uninstall(target) if a.uninstall else install(target,a.replace)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if not a.uninstall:print('请在Codex新会话中使用$zhonghua-blessing-ticket；未显示时重启应用。旧插件同名入口请自行停用，避免冲突。')
        return 0
    except (OSError,ValueError) as e:print('未完成安装：'+str(e),file=sys.stderr);return 2
if __name__=='__main__':
    # 管道输出统一为UTF-8，避免Windows默认编码无法表示中文。
    for stream in (sys.stdout,sys.stderr):stream.reconfigure(encoding='utf-8')
    raise SystemExit(main())
