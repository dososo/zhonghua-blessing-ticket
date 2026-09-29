"""覆盖真实数据、精确中文、图文模式、去重与文件回执；不伪造视觉验收。"""
from __future__ import annotations
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SK=ROOT/'skills/zhonghua-blessing-ticket'
sys.path.insert(0,str(SK/'scripts'))
import engine as e


def png(path,w=3,h=2):
    def chunk(tag,data):return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    raw=b''.join(b'\x00'+bytes([20,80,90])*w for _ in range(h))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
    return path


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.styles,cls.ty,cls.comps,cls.base=e.libraries()
    def test_all_fifty_five_names_and_order(self):
        self.assertEqual(len(self.styles),55)
        self.assertEqual(len({s['name'] for s in self.styles}),55)
        self.assertEqual([s['id']for s in self.styles],[f'{i:02d}'for i in range(1,56)])
    def test_easy_to_confuse_ethnic_names(self):
        self.assertEqual(e.resolve_ethnic('仫佬族',self.styles)['id'],'31')
        self.assertEqual(e.resolve_ethnic('仡佬族',self.styles)['id'],'36')
        self.assertEqual(e.resolve_ethnic('55',self.styles)['name'],'基诺族')
        self.assertEqual(e.resolve_ethnic('miao',self.styles)['id'],'05')
    def test_reject_unknown_ethnic(self):
        with self.assertRaises(ValueError):e.resolve_ethnic('一个泛民族',self.styles)
    def test_reference_bytes_match_approved_artifact(self):
        p=SK/self.base['reference']['path']
        self.assertEqual(e.sha256_file(p),self.base['reference']['sha256'])
        info=e.image_info(p)
        self.assertEqual([info['width'],info['height']],[1448,1086])
    def test_every_style_has_existing_progressive_reference(self):
        for s in self.styles:
            self.assertTrue((SK/f'references/ethnic-{s["id"]}-{s["slug"]}.md').is_file())
            self.assertLessEqual(len(s['supports']),3)
            self.assertTrue(s['cultural_scope'])
            self.assertTrue(s['safety_notes'])
    def test_pools_only_use_defined_recipe_ids(self):
        for s in self.styles:
            for key,lib in [('skeleton_pool',self.ty['skeletons']),('craft_pool',self.ty['crafts']),('layout_pool',self.ty['layouts']),('composition_pool',self.comps)]:
                self.assertTrue(s[key]);self.assertTrue(set(s[key]).issubset(lib))
    def test_light_and_dark_roles_are_not_reversed(self):
        for s in self.styles:
            p={x['id']:x for x in s['palettes']}
            self.assertGreater(e.luminance(p['light']['background']),e.luminance(p['dark']['background']))
            for q in s['palettes']:
                q=e.palette_checked(q);a,b=sorted((e.luminance(q['background']),e.luminance(q['title'])))
                self.assertGreaterEqual((b+.05)/(a+.05),3)
    def test_reference_cells_are_small_references_only(self):
        self.assertEqual(len(self.base['reference_cells']),10)
        for item in self.base['reference_cells']:
            info=e.image_info(SK/item['path']);self.assertLess(info['width'],400)
            self.assertIn('不能作为单张成品',item['role'])
    def test_default_first_batch_titles_follow_approved_baseline(self):
        self.assertEqual([s['blessings'][0] for s in self.styles[:10]],['山河无恙','平安喜乐','天降吉祥','心想事成','岁岁如意','大吉大利','八方来财','万事胜意','皆如所愿','富贵长乐'])


class TextTests(unittest.TestCase):
    def test_normal_annual_wishes_are_allowed(self):
        for text in ('年年有余','岁岁平安','大吉大利','皆如所愿','萬事勝意'):
            self.assertEqual(e.validate_blessing(text),text)
    def test_reject_dates_scripts_and_bad_input(self):
        for text in ('2026','二〇二六年','甲辰大吉','大吉\n大利','<script>','GOOD LUCK','','福'*13):
            with self.subTest(text=text),self.assertRaises(ValueError):e.validate_blessing(text)
    def test_layout_count_gating(self):
        ty=e.libraries()[1]
        self.assertTrue(e.valid_layout(ty['layouts']['four_two_lines'],4))
        self.assertFalse(e.valid_layout(ty['layouts']['four_two_lines'],5))
        self.assertFalse(e.valid_layout(ty['layouts']['three_staggered'],4))
        self.assertFalse(e.valid_layout(ty['layouts']['paired_columns'],5))
    def test_all_allowed_lengths_preserve_every_character(self):
        samples=['福','平安','皆如愿','大吉大利','皆如所愿','愿所求皆所愿','一二三四五六七','一二三四五六七八','一二三四五六七八九','一二三四五六七八九十','一二三四五六七八九十福','一二三四五六七八九十福喜']
        for text in samples:
            p=e.compile_single('苗族',text)
            self.assertEqual(p['exact_text']['value'],text)
            self.assertEqual(''.join(p['exact_text']['layout_lines']),text)
            self.assertTrue(e.valid_layout(p['typography']['layout'],len(text)))
    def test_two_line_reading_order(self):
        self.assertEqual(e.title_lines('大吉大利','four_two_lines'),['大吉','大利'])
        self.assertEqual(e.title_lines('皆如愿','three_staggered'),['皆','如愿'])
    def test_five_char_wish_never_forced_into_three(self):
        for seed in range(10):
            p=e.compile_single('朝鲜族','所愿皆如意',seed=seed)
            self.assertNotIn(p['typography']['layout_id'],('three_staggered','four_two_lines','two_giant'))
            self.assertEqual(p['exact_text']['character_count'],5)


class PlanTests(unittest.TestCase):
    def test_integrated_text_is_default(self):
        p=e.compile_single('苗族','大吉大利')
        self.assertEqual(p['render_mode'],'integrated_direct')
        self.assertFalse(p['separate_text_overlay'])
        self.assertIn('同时生成',p['prompt'])
        self.assertIsNone(p['label'])
    def test_target_does_not_pretend_actual_pixels(self):
        p=e.compile_single('苗族','大吉大利','1080×2336')
        self.assertEqual(p['format']['target_pixels'],[1080,2336])
        self.assertIsNone(p['format']['actual_pixels'])
        self.assertFalse(p['format']['native_pixels_verified'])
        self.assertFalse(p['generation']['current_host_verified'])
        self.assertEqual(p['status'],'planned_not_rendered')
    def test_same_seed_same_design(self):
        a=e.compile_single('傣族','财源广进',seed=42);b=e.compile_single('傣族','财源广进',seed=42)
        self.assertEqual(a,b)
    def test_first_design_uses_approved_preference(self):
        p=e.compile_single('苗族','大吉大利')
        self.assertEqual(p['typography']['craft_id'],'silver')
        self.assertEqual(p['palette']['id'],'dark')
    def test_material_edge_and_surface_do_not_mix_random_effects(self):
        for i in range(15):
            p=e.compile_single('苗族','大吉大利',variation=i)
            craft=p['typography']['craft']
            self.assertEqual(p['typography']['surface'],craft['recipe'])
            self.assertEqual(p['typography']['edge'],craft['edge'])
    def test_visual_fingerprint_not_just_seed_or_text(self):
        p=e.compile_single('苗族','大吉大利');q=e.compile_single('苗族','心想事成')
        self.assertEqual(p['visual_fingerprint'],q['visual_fingerprint'])
        self.assertNotEqual(p['request_fingerprint'],q['request_fingerprint'])
    def test_custom_title_does_not_get_replaced_with_default(self):
        p=e.compile_single('苗族','萬事勝意')
        self.assertEqual(p['exact_text']['value'],'萬事勝意')
        self.assertIn('「萬事勝意」',p['prompt'])
    def test_invalid_parameters_fail_cleanly(self):
        for kwargs in ({'fmt':'16:9'},{'variation':-1},{'seed':True}):
            with self.assertRaises(ValueError):e.compile_single('苗族','大吉大利',**kwargs)
    def test_canvas_modes_are_honest(self):
        p=e.compile_canvas();q=e.compile_canvas(strategy='assembled')
        self.assertEqual(p['kind'],'overview')
        self.assertEqual(p['generation_budget']['initial_calls'],1)
        self.assertEqual(q['generation_budget']['initial_calls'],10)
        self.assertTrue(p['target_is_overview_not_individual_hires'])
    def test_all_six_batches_cover_55_once(self):
        canvases=[e.compile_canvas(start,min(10,56-start))for start in (1,11,21,31,41,51)]
        self.assertEqual([c['grid']['count']for c in canvases],[10,10,10,10,10,5])
        ids=[p['ethnic']['id']for c in canvases for p in c['cards']]
        self.assertEqual(ids,[f'{i:02d}'for i in range(1,56)])
    def test_canvas_no_labels_and_common_wish(self):
        p=e.compile_canvas(label=False,common_blessing='皆如愿')
        self.assertEqual(p['label_policy'],'不显示民族名称')
        self.assertTrue(all(c['exact_text']['value']=='皆如愿'for c in p['cards']))
        self.assertNotIn('小标签「',p['prompt'])
    def test_canvas_range_errors(self):
        for args in ((0,10),(51,10),(56,1),(1,11),(1,0)):
            with self.assertRaises(ValueError):e.compile_canvas(*args)
    def test_limits_and_repair_preserve_explicit_title(self):
        p=e.compile_single('布依族','平安喜乐')
        self.assertEqual(p['generation']['max_calls'],3)
        self.assertIn('平安喜乐',p['repair_prompt'])
        self.assertIn('重新检查',p['repair_prompt'])


class HistoryTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'history.json'
    def tearDown(self):self.tmp.cleanup()
    def test_history_rotates_design_and_not_saves_private_phrase(self):
        used=[]
        for i in range(4):
            p=e.compile_single('苗族','大吉大利',history=e.history_entries(self.path))
            used.append(p['visual_fingerprint']);e.reserve_history(self.path,[p])
        self.assertEqual(len(set(used)),4)
        self.assertNotIn('大吉大利',self.path.read_text(encoding='utf-8'))
    def test_conflicting_reservation_leaves_original(self):
        p=e.compile_single('苗族','大吉大利');e.reserve_history(self.path,[p]);original=self.path.read_bytes()
        with self.assertRaises(ValueError):e.reserve_history(self.path,[p])
        self.assertEqual(self.path.read_bytes(),original)
        self.assertFalse(self.path.with_name(self.path.name+'.lock').exists())
    def test_existing_lock_is_respected(self):
        self.path.with_name(self.path.name+'.lock').write_text('')
        with self.assertRaises(ValueError):e.reserve_history(self.path,[e.compile_single('苗族','大吉大利')])
        self.assertFalse(self.path.exists())
    def test_reject_legacy_or_corrupt_history(self):
        self.path.write_text('{"version":"2.0.0","entries":[]}')
        with self.assertRaises(ValueError):e.history_entries(self.path)
        self.path.write_text('{')
        with self.assertRaises(ValueError):e.history_entries(self.path)


class ReceiptTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.p=png(Path(self.tmp.name)/'test.png')
    def tearDown(self):self.tmp.cleanup()
    def test_actual_png_size_and_hash(self):
        info=e.image_info(self.p)
        self.assertEqual((info['width'],info['height']),(3,2))
        self.assertEqual(len(info['sha256']),64)
        self.assertFalse(info['text_verified'])
    def test_corrupt_header_is_not_claimed_as_image(self):
        self.p.write_bytes(b'not-an-image')
        with self.assertRaises(ValueError):e.image_info(self.p)
    def test_receipt_does_not_conflate_transcription_and_aesthetic(self):
        p=e.compile_single('苗族','大吉大利');r=e.create_receipt(p,self.p,'大吉大利')
        self.assertTrue(r['transcription_matches'])
        self.assertFalse(r['exact_size_matches'])
        self.assertIsNone(r['visual_pass']);self.assertIsNone(r['cultural_pass'])
        self.assertFalse(r['native_size_certified'])
    def test_wrong_title_is_recorded_as_failure(self):
        r=e.create_receipt(e.compile_single('苗族','大吉大利'),self.p,'大吉大刂')
        self.assertFalse(r['transcription_matches'])
    def test_canvas_transcript_order(self):
        p=e.compile_canvas(51,5);texts='|'.join(c['exact_text']['value']for c in p['cards'])
        r=e.create_receipt(p,self.p,texts)
        self.assertTrue(r['transcription_matches']);self.assertIsNone(r['target_pixels'])
    def test_atomic_json_writes_utf8(self):
        p=Path(self.tmp.name)/'data.json';e.write_json(p,{'文字':'祝福'})
        self.assertEqual(e.read_json(p),{'文字':'祝福'})
        self.assertFalse(list(p.parent.glob('.zhbt-*')))


class CliTests(unittest.TestCase):
    def run_cli(self,*args):
        return subprocess.run([sys.executable,str(ROOT/'scripts/zhbt.py'),*map(str,args)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    def test_cli_version(self):self.assertEqual(self.run_cli('--version').stdout.strip(),'3.0.0')
    def test_cli_list_has_55_lines(self):
        r=self.run_cli('list');self.assertEqual(r.returncode,0);self.assertEqual(len(r.stdout.strip().splitlines()),55)
    def test_cli_single_outputs_plan_and_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'方案.json';r=self.run_cli('single','--ethnic','苗族','--blessing','大吉大利','--out',p)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertTrue(p.with_suffix('.prompt.txt').is_file())
            self.assertEqual(e.read_json(p)['status'],'planned_not_rendered')
    def test_cli_invalid_request_returns_nonzero_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.run_cli('single','--ethnic','苗族','--blessing','2026','--out',Path(tmp)/'a.json')
            self.assertEqual(r.returncode,2);self.assertNotIn('Traceback',r.stderr)
    def test_cli_last_canvas_defaults_to_five(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'p.json';r=self.run_cli('canvas','--start','51','--out',p)
            self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(e.read_json(p)['grid']['count'],5)
    def test_chinese_output_survives_legacy_pipe_encoding(self):
        env=dict(os.environ,PYTHONIOENCODING='cp1252')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'方案.json'
            cases=[('scripts/zhbt.py',['single','--ethnic','苗族','--blessing','大吉大利','--out',str(p)],0,'已写入：'),
                   ('skills/zhonghua-blessing-ticket/scripts/plan.py',['list'],0,'苗族'),
                   ('scripts/install.py',['--scope','project','--project',tmp],0,'请在Codex新会话'),
                   ('scripts/release_check.py',[],0,'离线发布检查'),
                   ('scripts/build_release.py',['--out-dir',str(Path(tmp)/'dist')],0,'构建日期字段固定')]
            for script,args,code,expected in cases:
                with self.subTest(script=script):
                    r=subprocess.run([sys.executable,str(ROOT/script),*args],cwd=ROOT,env=env,capture_output=True,encoding='utf-8')
                    self.assertEqual(r.returncode,code,r.stderr);self.assertIn(expected,r.stdout)
            self.assertEqual(e.read_json(p)['exact_text']['value'],'大吉大利')
    def test_chinese_errors_survive_legacy_pipe_encoding(self):
        env=dict(os.environ,PYTHONIOENCODING='cp1252')
        with tempfile.TemporaryDirectory() as tmp:
            cases=[('scripts/zhbt.py',['single','--ethnic','苗族','--blessing','2026','--out',str(Path(tmp)/'x.json')],'未完成：'),
                   ('scripts/install.py',['--scope','project'],'未完成安装：'),
                   ('skills/zhonghua-blessing-ticket/scripts/assemble.py',['缺失.png','--out',str(Path(tmp)/'x.png')],'未完成拼版：')]
            for script,args,expected in cases:
                with self.subTest(script=script):
                    r=subprocess.run([sys.executable,str(ROOT/script),*args],cwd=ROOT,env=env,capture_output=True,encoding='utf-8')
                    self.assertEqual(r.returncode,2);self.assertIn(expected,r.stderr);self.assertNotIn('Traceback',r.stderr)

if __name__=='__main__':unittest.main()
