"""真实临时目录安装与打包边界测试，不改动操作者的用户目录。"""
from __future__ import annotations
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import install
import release_check
sys.path.insert(0,str(ROOT/'skills/zhonghua-blessing-ticket/scripts'))
import assemble
try:
    from PIL import Image
except ImportError:Image=None


class InstallTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.dest=Path(self.tmp.name)/'.agents/skills'
    def tearDown(self):self.tmp.cleanup()
    def test_self_contained_install_copies_data_and_reference(self):
        r=install.install(self.dest);target=Path(r['installed'])
        self.assertTrue((target/'SKILL.md').is_file())
        self.assertTrue((target/'assets/approved-overview.png').is_file())
        self.assertTrue((target/'data/ethnic_styles.json').is_file())
        self.assertTrue((target/'scripts/plan.py').is_file())
        self.assertEqual(json.loads((target/'data/ethnic_styles.json').read_text(encoding='utf-8'))[4]['name'],'苗族')
    def test_existing_install_never_silently_overwritten(self):
        install.install(self.dest)
        with self.assertRaises(ValueError):install.install(self.dest)
    def test_upgrade_creates_backup_instead_of_deleting(self):
        r=install.install(self.dest);old=Path(r['installed']);(old/'个人说明.txt').write_text('保留',encoding='utf-8')
        r=install.install(self.dest,replace=True);backup=Path(r['backup'])
        self.assertEqual((backup/'个人说明.txt').read_text(encoding='utf-8'),'保留')
        self.assertFalse((Path(r['installed'])/'个人说明.txt').exists())
    def test_uninstall_only_owned_install(self):
        r=install.install(self.dest);install.uninstall(self.dest)
        self.assertFalse(Path(r['installed']).exists())
        bad=self.dest/install.NAME;bad.mkdir();(bad/'do-not-delete.txt').write_text('keep')
        with self.assertRaises(ValueError):install.uninstall(self.dest)
        self.assertTrue((bad/'do-not-delete.txt').exists())
    def test_forbid_recursive_target(self):
        with self.assertRaises(ValueError):install.install(install.SOURCE/'nested')
        self.assertFalse((install.SOURCE/'nested').exists())
    def test_replace_does_not_follow_existing_symlink(self):
        outside=Path(self.tmp.name)/'other';outside.mkdir();(outside/'important.txt').write_text('keep')
        self.dest.mkdir(parents=True)
        try:(self.dest/install.NAME).symlink_to(outside,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest('本测试环境未授权创建符号链接')
        r=install.install(self.dest,replace=True)
        self.assertEqual((outside/'important.txt').read_text(),'keep')
        self.assertTrue(Path(r['backup']).is_symlink())


@unittest.skipIf(Image is None,'未安装可选Pillow，跳过无损拼版测试')
class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.images=[]
        for i in range(10):
            p=self.root/f'{i}.png';Image.new('RGB',(12,20),(i*10,20,40)).save(p);self.images.append(p)
    def tearDown(self):self.tmp.cleanup()
    def test_no_loss_layout_dimensions_and_pixels(self):
        out=self.root/'canvas.png';r=assemble.assemble(self.images,out,5,gap=2,margin=3)
        self.assertEqual(r['actual_pixels'],[74,48]);self.assertFalse(r['upscaled']);self.assertFalse(r['cropped'])
        with Image.open(out)as im:self.assertEqual(im.getpixel((3,3)),(0,20,40))
    def test_mixed_dimensions_rejected(self):
        Image.new('RGB',(11,20)).save(self.images[0])
        with self.assertRaises(ValueError):assemble.assemble(self.images,self.root/'out.png')
    def test_cannot_overwrite_input(self):
        with self.assertRaises(ValueError):assemble.assemble(self.images,self.images[0])
    def test_five_card_one_row(self):
        r=assemble.assemble(self.images[:5],self.root/'out.png')
        self.assertEqual(r['rows'],1);self.assertEqual(r['columns'],5)


class ReleaseTests(unittest.TestCase):
    def test_source_files_exclude_outputs_and_caches(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp)
            for rel in('README.md','outputs/secret.json','dist/pkg.zip','__pycache__/a.pyc','.git/config','skills/a/SKILL.md',
                       'private/note.txt','local-references/reference.png','tasks/todo.md','debug.log','history.lock',
                       'reports/local-smoke.json','docs/CODEX_TASK.md','docs/CODEX_PUBLISH.md',
                       'package.egg-info/PKG-INFO','.coverage','nested/debug.log','nested/history.lock',
                       'nested/package.egg-info/PKG-INFO','nested/.coverage','.env','.env.example','.env.log','.env.lock','.env.egg-info'):
                p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('test')
            names={p.relative_to(root).as_posix()for p in release_check.source_files(root)}
            self.assertEqual(names,{'README.md','skills/a/SKILL.md','.env','.env.example','.env.log','.env.lock','.env.egg-info'})
    def test_private_task_documents_are_not_required(self):
        with tempfile.TemporaryDirectory()as tmp:
            errors=release_check.check_release(Path(tmp),include_validation=False)['errors']
            for rel in('docs/CODEX_TASK.md','docs/CODEX_PUBLISH.md'):
                self.assertNotIn('缺少必需文件：'+rel,errors)
    def test_relative_links_must_point_to_published_files(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp)
            hidden=('reports/local-smoke.json','docs/CODEX_TASK.md','docs/CODEX_PUBLISH.md','outputs/image.png')
            for rel in(*hidden,'docs/说明.md'):
                p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('本地占位内容',encoding='utf-8')
            (root/'README.md').write_text('\n'.join('[引用]('+rel+')'for rel in(*hidden,'docs/说明.md','docs/','reports/')),encoding='utf-8')
            errors=release_check.check_release(root,include_validation=False)['errors']
            for rel in(*hidden,'reports/'):
                self.assertIn('相对链接未纳入发布：README.md → '+rel,errors)
            self.assertFalse([e for e in errors if '→ docs/说明.md' in e or e.endswith('→ docs/')])
    def test_ignored_environment_files_still_fail_release_check(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp)
            for name in('.env','.env.example','.env.log','.env.lock','.env.egg-info'):(root/name).write_text('占位内容',encoding='utf-8')
            errors=release_check.check_release(root,include_validation=False)['errors']
            for name in('.env','.env.example','.env.log','.env.lock','.env.egg-info'):self.assertIn('疑似凭证文件：'+name,errors)
    def test_repository_contains_no_fonts(self):
        self.assertFalse([p for p in release_check.source_files()if p.suffix.lower()in release_check.FONT_EXTS])
    def test_metadata_versions(self):
        for name in('plugin.json','.codex-plugin/plugin.json'):
            meta=json.loads((ROOT/name).read_text(encoding='utf-8'));self.assertEqual(meta['version'],'3.0.0')
    def test_all_python_sources_are_valid(self):
        import ast
        for p in release_check.source_files():
            if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8'),feature_version=(3,9))

if __name__=='__main__':unittest.main()
