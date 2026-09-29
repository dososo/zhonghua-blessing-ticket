# 版权归爆裂队长NEXT及贡献者所有；依木兰宽松许可证第2版授权，按原样提供，无担保。
# SPDX-License-Identifier: MulanPSL-2.0
"""中华民族祝福票：离线设计编译、去重、生成回执与尺寸检查。

本模块不调用网络或图像模型。真正生图由读取本 Skill 的宿主调用原生工具完成。
方案生成、文件检查和人工视觉验收是不同状态，不相互冒充。
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import struct
import tempfile
from pathlib import Path
from typing import Any

VERSION = "3.0.0"
SKILL_ROOT = Path(__file__).resolve().parents[1]
DATA = SKILL_ROOT / "data"
FORMAT_ALIASES = {"3:4": "3:4", "3∶4": "3:4", "1080x1440": "3:4", "1080×1440": "3:4", "社媒": "3:4",
                  "long": "long", "长票": "long", "留白": "long", "1080x2336": "long", "1080×2336": "long"}
STAMP = "纯几何小印记，不制造乱码篆文"


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取有效 JSON：{path.name}；{exc}") from exc


def write_json(path: Path, value: Any) -> None:
    """原子替换，避免中断留下半个状态文件。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".zhbt-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def libraries() -> tuple[list[dict], dict, dict, dict]:
    return (read_json(DATA / "ethnic_styles.json"), read_json(DATA / "typography.json"),
            read_json(DATA / "compositions.json"), read_json(DATA / "approved_style.json"))


def resolve_ethnic(value: str, styles: list[dict]) -> dict:
    q = str(value).strip()
    hits = [s for s in styles if q.lower() in (s["id"].lower(), str(int(s["id"])), s["slug"].lower(), s["name"], s["name"].removesuffix("族"))]
    if len(hits) != 1:
        raise ValueError("未找到唯一民族。请使用完整名称，如「苗族」「仫佬族」「仡佬族」，或运行 list 查看55项。")
    return hits[0]


def validate_blessing(text: str) -> str:
    """仅把简短汉字祝福当数据，拒绝指令、年份及伪语言。允许年年有余等常用祝福。"""
    if not isinstance(text, str) or not 1 <= len(text) <= 12:
        raise ValueError("主祝福词须为1至12个汉字；较长文字请另作说明，不塞进主标题。")
    if not re.fullmatch(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0003134f]+", text):
        raise ValueError("主祝福词只接受汉字，不接受年份、数字、外文、换行或指令片段。")
    if re.search(r"[〇零一二三四五六七八九]{4}年", text) or re.search(r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]", text):
        raise ValueError("图面不使用具体年份或干支纪年，请改为不带纪年的祝福。")
    return text


def valid_layout(layout: dict, count: int) -> bool:
    return layout["min"] <= count <= layout["max"] and (not layout.get("even") or count % 2 == 0)


def title_lines(text: str, layout_id: str) -> list[str]:
    if layout_id == "four_two_lines":
        return [text[:2], text[2:]]
    if layout_id == "paired_columns":
        return [text[:len(text)//2], text[len(text)//2:]]
    if layout_id == "three_staggered":
        return [text[0], text[1:]]
    if layout_id == "hero_first":
        return [text[0], text[1:]]
    if layout_id == "horizon":
        return [text]
    return list(text)


def semantics(text: str) -> dict:
    candidates = [("丰足", "财富金丰盈禄", "收拢与展开并置，传达努力所得和生活丰足"),
                  ("安康", "安康宁寿恙和", "稳定清楚、温暖有承托，不强制低饱和"),
                  ("顺遂", "愿顺如成程通", "有行气的舒展流动，避免笔画彼此纠缠"),
                  ("吉庆", "吉福喜祥瑞", "浓淡与大小有起伏，主字明快有力")]
    scored = [(sum(c in chars for c in text), i, name, action) for i, (name, chars, action) in enumerate(candidates)]
    score, _, name, action = max(scored, key=lambda x: (x[0], -x[1]))
    return {"type": name if score else "自定义祝福", "motion": action if score else "保持输入词序，以温暖、清楚、有节奏的手写组织画面"}


def luminance(c: str) -> float:
    rgb = [int(c[i:i+2], 16)/255 for i in (1, 3, 5)]
    rgb = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    return sum(v*w for v, w in zip(rgb, (.2126, .7152, .0722)))


def palette_checked(p: dict) -> dict:
    p = dict(p)
    a,b = sorted((luminance(p["background"]), luminance(p["title"])))
    if (b+.05)/(a+.05) < 3.0:
        options = ("#F5EDD8", "#152D30")
        def contrast(c):
            low, high = sorted((luminance(p["background"]), luminance(c)))
            return (high+.05)/(low+.05)
        p["title"] = max(options, key=contrast)
        p["contrast_adjustment"] = "为保持标题可读，调整标题明度；这是设计提示检查，不是图像像素验收。"
    return p


def history_entries(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    obj = read_json(path)
    if obj.get("version") != VERSION or not isinstance(obj.get("entries"), list):
        raise ValueError("历史文件版本或结构不匹配。请新建v3历史文件；不静默改写旧版历史。")
    return obj["entries"]


def reserve_history(path: Path | None, plans: list[dict]) -> None:
    """历史仅保留设计指纹，不记录个人输入文字。并发写入以排他锁保护。"""
    if path is None:
        return
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError("历史正在被另一任务使用；请稍后重试。中断遗留锁仅在确认没有运行任务后手动删除。") from exc
    try:
        os.close(fd)
        entries = history_entries(path)
        keys = {e["visual_fingerprint"] for e in entries}
        for p in plans:
            if p["visual_fingerprint"] in keys:
                raise ValueError("另一任务刚使用了相同设计，请重试编译；没有覆盖历史。")
            keys.add(p["visual_fingerprint"])
            entries.append({"ethnic_id":p["ethnic"]["id"], "visual_fingerprint":p["visual_fingerprint"],
                            "skeleton":p["typography"]["skeleton_id"],"layout":p["typography"]["layout_id"],
                            "composition":p["composition"]["id"],"palette":p["palette"]["id"],"status":"已规划，未证明已成图"})
        write_json(path, {"version":VERSION,"entries":entries})
    finally:
        lock.unlink(missing_ok=True)


def _choice(values: list, key: str, n: int) -> Any:
    i = int(hashlib.sha256(f"{key}:{n}".encode()).hexdigest()[:16],16) % len(values)
    return values[i]


def compile_single(ethnic: str, blessing: str, fmt: str = "3:4", seed: int = 0, variation: int = 0,
                   label: bool = False, history: list[dict] | None = None, occupied: set[str] | None = None) -> dict:
    styles, type_lib, comps, base = libraries()
    s = resolve_ethnic(ethnic, styles)
    text = validate_blessing(blessing)
    if fmt not in FORMAT_ALIASES:
        raise ValueError("规格须为3:4或1080×2336。总览通过canvas命令生成。")
    fmt = FORMAT_ALIASES[fmt]
    if type(seed) is not int or type(variation) is not int or variation < 0:
        raise ValueError("seed须为整数，variation须为非负整数。")
    hist = history or []
    used = {e["visual_fingerprint"] for e in hist} | (occupied or set())
    recent = [e for e in hist if e["ethnic_id"]==s["id"]][-3:]
    layouts = [key for key in s["layout_pool"] if valid_layout(type_lib["layouts"][key],len(text))]
    if not layouts:
        layouts = [k for k,v in type_lib["layouts"].items() if valid_layout(v,len(text))]
    if not layouts:
        raise ValueError("当前祝福字数没有可用布局。")
    best=None
    for attempt in range(128):
        key=f'{s["id"]}:{seed}:{variation+attempt}'
        anchored = seed == 0 and variation == 0 and attempt == 0
        pref=s["preferred"]
        skeleton=pref["skeleton"] if anchored else _choice(s["skeleton_pool"],key,1)
        if len(text)>6 and skeleton=="seal": skeleton="running_script"
        craft=pref["craft"] if anchored else _choice(s["craft_pool"],key,2)
        layout=pref["layout"] if anchored and pref["layout"] in layouts else _choice(layouts,key,3)
        comp=pref["composition"] if anchored else _choice(s["composition_pool"],key,4)
        palette=palette_checked(next(p for p in s["palettes"] if p["id"] == pref["palette"]) if anchored else _choice(s["palettes"],key,5))
        background=s["backgrounds"][palette["id"]]
        dyn=_choice(type_lib["dynamics"],key,7)
        fusion=_choice(type_lib["fusion"],key,8)
        # 不含民族编号、祝福、种子：这是实际视觉配置的指纹，不靠换编号制造不同。
        visual={"hero":s["hero"],"skeleton":skeleton,"craft":craft,"layout":layout,"composition":comp,
                "palette":palette,"background":background,"dynamics":dyn,"fusion":fusion,"format":fmt}
        fp=digest(visual)
        if fp in used: continue
        penalty=sum((skeleton==e["skeleton"])+(layout==e["layout"])+(comp==e["composition"])+(palette["id"]==e["palette"]) for e in recent)
        if best is None or penalty<best[0]:best=(penalty,visual,fp,attempt)
        if penalty==0:break
    if best is None:
        raise ValueError("本轮候选与已有历史重复；请更换variation或重置另一个有明确用途的历史文件，不能假称不重复。")
    _,v,fp,attempt=best
    title_spec={"value":text,"characters":list(text),"character_count":len(text),"layout_lines":title_lines(text,v["layout"]),
                "reading_rule":type_lib["layouts"][v["layout"]]["rule"],"allow_extra_text":False}
    native_size=base["format_policy"]["long_target" if fmt=="long" else "social_target"]
    reference={**base["reference"],"attach_path":str(SKILL_ROOT/base["reference"]["path"])}
    plan={"version":VERSION,"status":"planned_not_rendered","render_mode":"integrated_direct","separate_text_overlay":False,
          "ethnic":{"id":s["id"],"name":s["name"],"scope":s["cultural_scope"]},"exact_text":title_spec,
          "format":{"id":fmt,"target_pixels":native_size,"actual_pixels":None,"native_pixels_verified":False},
          "reference":reference,"local_reference_cell":s["reference_cell"],
          "style_binding":base["id"],"route":s["route"],"hero":s["hero"],"supports":s["supports"],
          "semantic":semantics(text),"palette":v["palette"],"background":v["background"],
          "composition":{"id":v["composition"],**comps[v["composition"]]},
          "typography":{"skeleton_id":v["skeleton"],"skeleton":type_lib["skeletons"][v["skeleton"]],
                        "craft_id":v["craft"],"craft":type_lib["crafts"][v["craft"]],"layout_id":v["layout"],
                        "layout":type_lib["layouts"][v["layout"]],"dynamics":v["dynamics"],"fusion":v["fusion"],
                        "surface":type_lib["crafts"][v["craft"]]["recipe"],"edge":type_lib["crafts"][v["craft"]]["edge"],
                        "negative_space":("主字周边连续低密度区，深色本身也可留白" if v["palette"]["id"] != "light" else "主字周边连续低密度区，纸色不承担统一模板"),
                        "time":type_lib["crafts"][v["craft"]]["time"]},
          "label":s["name"] if label else None,"seals":STAMP,"cultural_review":s["evidence"],"cultural_notes":s["safety_notes"],
          "visual_fingerprint":fp,"request_fingerprint":digest({"visual":fp,"text":text}),"seed":seed,"variation_used":variation+attempt,
          "generation":{"native_tool_required":True,"max_calls":3,"read_reference_before_generation":True,"attach_reference_when_supported":True,
                        "current_host_verified":False,"retry":"一次初稿，最多两次定向编辑；不能承诺局部编辑绝对不改变其他细节。"}}
    plan["prompt"]=render_prompt(plan,base)
    plan["repair_prompt"]=repair_prompt(plan)
    return plan


def render_prompt(p: dict, base: dict) -> str:
    t=p["typography"]; txt=p["exact_text"];colors=p["palette"]
    label=f'允许独立小标签「{p["label"]}」，不能作为主标题。' if p["label"] else '不在卡面显示民族名称。'
    size='×'.join(map(str,p["format"]["target_pixels"]))
    return '\n'.join([
        '以随附的已确认总览图作为绘画与印刷气质基准，创作一张完整中文祝福票。图案、文字和工艺色同时生成，禁止生成无字底图后再贴字。',
        '继承装饰性山河、细密民艺纹饰、清楚有力的书法和柔和纸绢触感。只借审美，不挪用参考图中其他民族的文化符号。没有附件时先读取本包基准图并尝试将其作为图像参考，不能声称已参考未读取的图片。',
        f'主标题必须逐字为「{txt["value"]}」，共{txt["character_count"]}字，字序：'+ '、'.join(txt['characters'])+'。不得改字、增字、减字、同音替换或追加另一句。',
        f'版式：{t["layout"]["name"]}。{txt["reading_rule"]}；文字分组：'+ ' / '.join(txt['layout_lines'])+'。',
        f'主字：{t["skeleton"]["name"]}，{t["skeleton"]["recipe"]}；{t["dynamics"]}。工艺：{t["craft"]["name"]}，{t["craft"]["recipe"]}。不做立体挤出、亮片广告字，不为材质牺牲汉字。',
        f'文化范围：{p["ethnic"]["name"]}，{p["ethnic"]["scope"]}。主锚点：{p["hero"]}；辅助只用：'+ '、'.join(p['supports'])+'。具体器物比例与花纹服从可信实物，不臆造文字或神圣符号。',
        f'图面组织：{p["composition"]["name"]}，{p["composition"]["rule"]}。{t["fusion"]}。{t["negative_space"]}。祝福情绪：{p["semantic"]["motion"]}。',
        f'色彩：底色{colors["background"]}、主字{colors["title"]}、副色{colors["secondary"]}、点色{colors["accent"]}。{colors["behavior"]}。底材：{p["background"]}。时间质感：{t["time"]}；完整清楚优先，做旧仅局部可选。',
        f'目标尺寸：{size}。'+('长票重新安排天地与字侧留白，不能拉伸3:4版。' if p['format']['id']=='long' else '3:4独立布局，标题占据明确重心，不裁切长票冒充。'),
        label+'不出现年份、日期、生肖纪年、未经核验的民族文字、随机外文、作者签名或水印。小印只用纯几何或标题内的字。',
        '避免：'+'；'.join(base['do_not_drift'])+'。',
        '文化防串项：'+'；'.join(p['cultural_notes'][:1])+'。'
    ])


def repair_prompt(p: dict) -> str:
    text=p['exact_text']['value']
    return (f'编辑本轮真实生成的原图，保持其绘画语言、主锚点、配色和主构图，仅修复已指出的错误。'
            f'主标题严格是「{text}」，'+ '、'.join(p['exact_text']['characters'])+'，不增加任何字。'
            '保留既定书体与平面工艺表现，不将标题替换成默认电脑字体。任何编辑都需重新检查全图，不能假定其余部分完全没变。')


def compile_canvas(start: int=1, count: int=10, seed: int=0, fmt: str='3:4', strategy: str='overview',
                   label: bool=True, common_blessing: str | None=None, history: list[dict] | None=None) -> dict:
    if type(start) is not int or type(count) is not int or not 1<=count<=10 or not 1<=start<=55 or start+count-1>55:
        raise ValueError('画布范围须在01—55内，每张1至10卡。最后一辑默认51—55五卡。')
    if strategy not in ('overview','assembled'):raise ValueError('策略仅支持overview或assembled。')
    styles,_,_,base=libraries()
    selected=styles[start-1:start-1+count]
    plans=[]; occupied=set(); hist=list(history or [])
    for i,s in enumerate(selected):
        p=compile_single(s['name'],common_blessing or s['blessings'][0],fmt,seed,variation=0,label=False,history=hist,occupied=occupied)
        plans.append(p);occupied.add(p['visual_fingerprint'])
        hist.append({'ethnic_id':s['id'],'visual_fingerprint':p['visual_fingerprint'],'skeleton':p['typography']['skeleton_id'],
                     'layout':p['typography']['layout_id'],'composition':p['composition']['id'],'palette':p['palette']['id']})
    cols=min(5,count);rows=math.ceil(count/cols)
    compact=[]
    for i,p in enumerate(plans):
        t=p['typography']; pal=p['palette'];txt=p['exact_text']
        compact.append(f'第{i+1}卡，位于第{i//cols+1}行第{i%cols+1}列：主标题「{txt["value"]}」；字序'+ '、'.join(txt['characters'])+
                       f'；{p["ethnic"]["name"]}的{p["hero"]}，辅助'+ '、'.join(p['supports'][:2])+
                       f'；{p["composition"]["name"]}；{t["skeleton"]["name"]}＋{t["craft"]["name"]}，{t["layout"]["name"]}；'+
                       f'底{pal["background"]}、字{pal["title"]}、点色{pal["accent"]}。'+
                       (f'小标签「{p["ethnic"]["name"]}」。' if label else '无民族标签。')+'文化防串：'+p['cultural_notes'][0])
    prompt=('生成一张'+str(cols)+'列'+str(rows)+'行、共'+str(count)+'个独立卡位的中华民族祝福票总览图。'
        '随附参考图定义古典民艺印刷、书法张力、精细纹饰、山河层次和整套展陈秩序。'
        '每卡是不同民族的独立设计，图与准确文字同时生成，禁止多出来的卡、重复民族、卡位错序或总览里混入另一套画风。\n'+
        '\n'.join(compact)+'\n'
        '卡位之间只保留细窄浅色间隔；底部有细薄的浅纸色山水收束带，主字清楚大于说明。'
        '底部总题只写「中华民族祝福票」，不写年份、日期、数字编号、作者名、外文或随机小字。'
        '主字以宽笔、行书、碑意和票券书写为同族群变化；工艺差异为平面细节，不改成立体广告。'
        '图面可有浅纸、深靛、青绿、朱红等不同底色，标题周围保持明度差和可读空间。'
        '仅把这张图交付为系列总览，不声称任一卡位是1080×2336原生单图。')
    return {'version':VERSION,'status':'planned_not_rendered','strategy':strategy,'kind':'overview' if strategy=='overview' else 'assembled_canvas',
            'range':[start,start+count-1],'grid':{'columns':cols,'rows':rows,'count':count},
            'requested_aspect':'4:3' if rows>1 else '16:9','target_is_overview_not_individual_hires':True,
            'label_policy':'目录小标注' if label else '不显示民族名称','style_binding':base['id'],'reference':plans[0]['reference'],
            'cards':plans,'prompt':prompt,'generation_budget':{'initial_calls':1 if strategy=='overview' else count,'max_repair_calls':1 if strategy=='overview' else count*2},
            'diversity':{'skeletons':len({p['typography']['skeleton_id'] for p in plans}),
                         'crafts':len({p['typography']['craft_id'] for p in plans}),
                         'layouts':len({p['typography']['layout_id'] for p in plans}),
                         'palettes':len({p['palette']['id'] for p in plans}),
                         'note':'这些是方案变量统计，不是成图视觉评分。无强制异画种配额。'}}


def image_info(path: Path) -> dict:
    """只检查文件实际几何尺寸，绝不据此推断是否为原生分辨率。"""
    path=Path(path)
    if not path.is_file():raise ValueError('图像文件不存在。')
    with path.open('rb') as f:
        head=f.read(32)
        if head.startswith(b'\x89PNG\r\n\x1a\n') and head[12:16]==b'IHDR' and len(head)>=24:
            width,height=struct.unpack('>II',head[16:24]);fmt='PNG'
        elif head.startswith(b'\xff\xd8'):
            f.seek(2);width=height=0;fmt='JPEG'
            while True:
                b=f.read(1)
                if not b:break
                if b!=b'\xff':continue
                while b==b'\xff':b=f.read(1)
                if not b:break
                marker=b[0]
                if marker in (0xD8,0xD9) or 0xD0<=marker<=0xD7:continue
                raw=f.read(2)
                if len(raw)!=2:break
                size=struct.unpack('>H',raw)[0]
                if size<2:break
                if marker in (0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF):
                    raw=f.read(5)
                    if len(raw)==5:height,width=struct.unpack('>HH',raw[1:])
                    break
                f.seek(size-2,1)
            if not width or not height:raise ValueError('无法解析JPEG图像尺寸。')
        else:
            raise ValueError('目前回执支持PNG/JPEG；其他格式请保留原图并用宿主实际图像信息记录，不能伪报尺寸。')
    if not 0<width<=100000 or not 0<height<=100000:raise ValueError('图像尺寸无效。')
    return {'filename':path.name,'format':fmt,'width':width,'height':height,'size_bytes':path.stat().st_size,
            'sha256':sha256_file(path),'native_generation_resolution':'未知，须结合真实生图工具回执','text_verified':False,'validation_level':'文件几何头与哈希；不是完整解码或内容验收'}


def create_receipt(plan: dict, image: Path, transcription: str | None=None, reviewer_note: str | None=None) -> dict:
    info=image_info(image)
    is_canvas='cards' in plan
    target=None if is_canvas else plan['format']['target_pixels']
    expected=[p['exact_text']['value'] for p in plan['cards']] if is_canvas else [plan['exact_text']['value']]
    given=transcription.split('|') if transcription is not None else None
    text_matches=None if given is None else given==expected
    return {'version':VERSION,'status':'rendered_requires_visual_review','image':info,
            'target_pixels':target,'exact_size_matches':None if target is None else target==[info['width'],info['height']],
            'expected_texts':expected,'reviewer_supplied_transcription':given,'transcription_matches':text_matches,
            'transcription_source':'人工或宿主视觉提交；本工具不运行OCR，不自行判断字形' if given is not None else '未提交',
            'reviewer_note':reviewer_note,'visual_pass':None,'cultural_pass':None,
            'native_size_certified':False,'result_kind':'十卡或多卡总览' if is_canvas else '单张图文祝福票',
            'reference_sha256':plan['reference']['sha256'],'note':'尺寸匹配和转录一致仍不等于书法、文化和审美通过。记录真实工具调用证据后再由人验收。'}


def validate_all() -> dict:
    styles,tl,cs,base=libraries();errors=[]
    if len(styles)!=55:errors.append('民族条目不是55项。')
    if len({s['name'] for s in styles})!=55:errors.append('民族名称重复。')
    if [s['id'] for s in styles]!=[f'{i:02d}'for i in range(1,56)]:errors.append('民族顺序错误。')
    ref=SKILL_ROOT/base['reference']['path']
    if not ref.is_file() or sha256_file(ref)!=base['reference']['sha256']:errors.append('审美基准图缺失或被更改。')
    for s in styles:
        for pool,lib in [('skeleton_pool',tl['skeletons']),('craft_pool',tl['crafts']),('layout_pool',tl['layouts']),('composition_pool',cs)]:
            if not s[pool] or any(v not in lib for v in s[pool]):errors.append(s['name']+'存在无效风格引用。')
        if len(s['supports'])>3:errors.append(s['name']+'辅助元素过多。')
        if s.get('reference_cell') and not (SKILL_ROOT/s['reference_cell']).is_file():errors.append(s['name']+'局部参考缺失。')
    plans=[];canvases=[]
    if not errors:
        for s in styles:
            for fmt in ('long','3:4'):
                p=compile_single(s['name'],s['blessings'][0],fmt)
                plans.append(p)
                if ''.join(p['exact_text']['layout_lines'])!=p['exact_text']['value']:errors.append('分组丢失文字。')
        for start in (1,11,21,31,41,51):canvases.append(compile_canvas(start,min(10,56-start)))
    return {'ok':not errors,'version':VERSION,'errors':errors,'style_count':len(styles),'compiled_plans':len(plans),
            'canvas_counts':[c['grid']['count'] for c in canvases],'reference_integrity':ref.is_file() and sha256_file(ref)==base['reference']['sha256'],
            'typography_counts':{'skeletons':len(tl['skeletons']),'crafts':len(tl['crafts']),'layouts':len(tl['layouts'])},
            'verified_scope':'离线数据、文字分组、方案编译、参考完整性；没有调用图像模型','codex_desktop_e2e':'未在用户机器执行','generated_visual_review':'未执行；用户认可的是已附基准图'}
