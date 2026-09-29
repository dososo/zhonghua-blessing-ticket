#!/usr/bin/env python3
# 版权归爆裂队长NEXT及贡献者所有；依木兰宽松许可证第2版授权，按原样提供，无担保。
# SPDX-License-Identifier: MulanPSL-2.0
"""创建有UTF-8文件名的可复核ZIP；不上传远端，不包含运行历史或凭证。"""
from __future__ import annotations
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from release_check import ROOT, source_files, check_release


def build(output_dir=None):
    result=check_release()
    if not result['ok']:raise ValueError('发布检查失败：'+'；'.join(result['errors']))
    version=(ROOT/'VERSION').read_text().strip()
    output=Path(output_dir) if output_dir else ROOT/'dist'
    output.mkdir(parents=True,exist_ok=True)
    target=output/f'zhbt-v{version}.zip'
    sources=[p for p in source_files() if output.resolve() not in p.resolve().parents and p.resolve()!=target.resolve()]
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sources:
            if p.is_symlink():raise ValueError('不打包软链接：'+p.name)
            name='zhonghua-blessing-ticket/'+p.relative_to(ROOT).as_posix()
            item=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            item.compress_type=zipfile.ZIP_DEFLATED
            item.create_system=3
            item.external_attr=((0o100755 if p.suffix=='.sh' else 0o100644)<<16)
            z.writestr(item,p.read_bytes())
    with zipfile.ZipFile(target) as z:
        bad=z.testzip()
        if bad:raise ValueError('ZIP完整性失败：'+bad)
    sha=hashlib.sha256(target.read_bytes()).hexdigest()
    (output/'SHA256SUMS.txt').write_text(sha+'  '+target.name+'\n',encoding='utf-8')
    manifest={'version':version,'archive':target.name,'sha256':sha,'size_bytes':target.stat().st_size,'file_count':len(sources),
              'zip_integrity':True,'contains_fonts':False,'uploaded_to_github':False,'note':'构建日期字段固定用于可复核打包，与祝福图面日期无关。'}
    (output/'build-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest


def main(argv=None):
    p=argparse.ArgumentParser(description='构建中华民族祝福票发布包');p.add_argument('--out-dir',type=Path);a=p.parse_args(argv)
    try:print(json.dumps(build(a.out_dir),ensure_ascii=False,indent=2));return 0
    except (ValueError,OSError) as e:print('未完成构建：'+str(e));return 1
if __name__=='__main__':raise SystemExit(main())
