# 项目执行规则

这是可开源的中华民族祝福票Skill仓库。先读README。修改生图流程时读`skills/zhonghua-blessing-ticket/SKILL.md`及`references/visual-contract.md`。

- 作者已认可`assets/approved-overview.png`的效果，不再换风格路线。
- 图案与准确中文主标题直接一体生成，不能默认无字底图后贴主字。
- 十卡总览可独立交付，不能冒称单格1080×2336。单张与总览均记录真实尺寸。
- 只改用户要求的内容。不要生成与任务无关的新图、插件、MCP、前端或后端。
- 不声称离线测试证明审美、中文正确率或55民族专家审查通过。
- 不读凭证文件，不将输出、个人历史、缓存、字体和第三方参考图加入仓库。
- 发布GitHub前检查账号与远端，已存在仓库不覆盖，不强制推送。不得自动修改全局git身份。
- 文档、注释和用户提示使用中文；标识符与工具命令保持其实际拼写。

本地验证：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/zhbt.py validate
python3 scripts/release_check.py
```
