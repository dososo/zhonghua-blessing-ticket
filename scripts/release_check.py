#!/usr/bin/env python3
# 版权归爆裂队长NEXT及贡献者所有；依木兰宽松许可证第2版授权，按原样提供，无担保。
# SPDX-License-Identifier: MulanPSL-2.0
"""发布前离线检查：结构、版本、基准、相对链接、敏感文件和实际方案。"""
from __future__ import annotations
import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SK=ROOT/'skills/zhonghua-blessing-ticket'
sys.path.insert(0,str(SK/'scripts'))
from engine import VERSION, validate_all, read_json

EXCLUDED_DIRS={'.git','.venv','venv','__pycache__','dist','outputs','.zhbt','.pytest_cache','.mypy_cache','node_modules',
               'private','local-references','tasks','reports'}
EXCLUDED_FILES={'docs/CODEX_TASK.md','docs/CODEX_PUBLISH.md'}
FONT_EXTS={'.ttf','.otf','.woff','.woff2','.ttc','.dfont'}
REQUIRED=['README.md','AGENTS.md','LICENSE','NOTICE','ASSETS.md','CONTRIBUTING.md','SECURITY.md','VERSION','plugin.json',
          'skills/zhonghua-blessing-ticket/SKILL.md','skills/zhonghua-blessing-ticket/agents/openai.yaml',
          'skills/zhonghua-blessing-ticket/assets/provenance.json','scripts/install.py','scripts/build_release.py',
          'docs/SMOKE_TEST.md','.github/workflows/test.yml','.github/workflows/release.yml']

def source_files(root=ROOT):
    """明确跳过运行产物；发布时不跟随软链接。"""
    root=Path(root)
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root)
        if rel.as_posix() in EXCLUDED_FILES:continue
        if any(x in EXCLUDED_DIRS for x in rel.parts) or any(x.endswith('.egg-info') for x in rel.parts[:-1]) or p.name in ('.DS_Store','.coverage'):continue
        if p.is_symlink():
            yield p
        elif p.is_file() and (p.name=='.env' or p.name.startswith('.env.') or not p.name.endswith(('.pyc','.pyo','.pyd','.log','.lock'))):
            yield p

def check_release(root=ROOT, include_validation=True):
    root=Path(root).resolve();errors=[];warnings=[];files=list(source_files(root))
    published_paths={p.resolve() for p in files}
    published_paths.update(parent for p in files for parent in p.parents if parent==root or root in parent.parents)
    for rel in REQUIRED:
        if not (root/rel).is_file():errors.append('缺少必需文件：'+rel)
    version=(root/'VERSION').read_text().strip() if (root/'VERSION').is_file() else None
    if version!=VERSION:errors.append('VERSION与编译器版本不同。')
    for p in files:
        rel=p.relative_to(root).as_posix()
        if p.is_symlink():errors.append('发布源不允许软链接：'+rel);continue
        if p.suffix.lower() in FONT_EXTS:errors.append('禁止随包分发字体文件：'+rel)
        if p.name=='.env' or p.name.startswith('.env.') or p.suffix.lower() in ('.pem','.key','.p12'):
            errors.append('疑似凭证文件：'+rel)
        if p.suffix in ('.md','.py','.json','.yml','.yaml','.txt','.sh') or p.name in ('LICENSE','NOTICE','VERSION'):
            try:text=p.read_text(encoding='utf-8')
            except UnicodeError:errors.append('文本不是UTF-8：'+rel);continue
            # 只匹配真实形状的密钥，不把文档里的“API密钥”字样当泄漏。
            if re.search(r'(?<![\w-])(?:sk-[A-Za-z0-9_-]{30,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',text):errors.append('疑似密钥内容：'+rel)
            if '\ufffd' in text:errors.append('出现Unicode替代字符：'+rel)
            if p.suffix=='.py':
                try:ast.parse(text,filename=rel,feature_version=(3,9))
                except SyntaxError as e:errors.append('Python3.9语法不兼容：'+rel+' '+str(e))
            if p.suffix=='.json':
                try:json.loads(text)
                except json.JSONDecodeError:errors.append('无效JSON：'+rel)
            if p.suffix=='.md':
                # 链接目标必须随公开文件一起分发，不能借本地过程件通过检查。
                for link in re.findall(r'(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)|!\[[^\]\n]*\]\(([^)\n]+)\)',text):
                    dest=next(x for x in link if x).split('#')[0].strip('<>')
                    if not dest or ':' in dest or '<' in dest or '{' in dest:continue
                    target=(p.parent/dest).resolve()
                    if not target.exists():errors.append('相对链接失效：'+rel+' → '+dest)
                    elif target not in published_paths:errors.append('相对链接未纳入发布：'+rel+' → '+dest)
    for meta in ('plugin.json','.codex-plugin/plugin.json'):
        if (root/meta).is_file():
            try:
                obj=read_json(root/meta)
                if obj.get('version')!=version or obj.get('name')!='zhonghua-blessing-ticket':errors.append('插件版本或名称不匹配：'+meta)
            except ValueError as e:errors.append(str(e))
    for p in (root/'examples').glob('*.json'):
        if str(root) in p.read_text(encoding='utf-8'):errors.append('公开示例含构建机器路径：'+p.name)
    result=validate_all() if include_validation and root.resolve()==ROOT.resolve() else None
    if result and not result['ok']:errors.extend(result['errors'])
    return {'ok':not errors,'version':version,'checked_files':len(files),'errors':errors,'warnings':warnings,
            'offline_validation':result,'scope':'离线发布检查；不是GitHub已发布状态、完整安全审计或宿主生图验收'}

def main(argv=None):
    p=argparse.ArgumentParser(description='检查可发布源文件');p.add_argument('--out',type=Path);a=p.parse_args(argv)
    r=check_release();text=json.dumps(r,ensure_ascii=False,indent=2)+'\n'
    if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(text,encoding='utf-8')
    print(text);return 0 if r['ok'] else 1
if __name__=='__main__':
    # 管道输出统一为UTF-8，避免Windows默认编码无法表示中文。
    for stream in (sys.stdout,sys.stderr):stream.reconfigure(encoding='utf-8')
    raise SystemExit(main())
