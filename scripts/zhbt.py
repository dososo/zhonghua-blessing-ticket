#!/usr/bin/env python3
# 版权归爆裂队长NEXT及贡献者所有；依木兰宽松许可证第2版授权，按原样提供，无担保。
# SPDX-License-Identifier: MulanPSL-2.0
"""仓库入口；所有运行依赖都位于可独立安装的Skill目录。"""
from pathlib import Path
import runpy
import sys
SCRIPTS=Path(__file__).resolve().parents[1]/'skills/zhonghua-blessing-ticket/scripts'
sys.path.insert(0,str(SCRIPTS))
runpy.run_path(str(SCRIPTS/'plan.py'),run_name='__main__')
