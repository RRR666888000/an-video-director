import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/course_lookup.py'
spec = importlib.util.spec_from_file_location('course_lookup', SCRIPT)
course = importlib.util.module_from_spec(spec)
spec.loader.exec_module(course)

class LookupTests(unittest.TestCase):
    def test_core_routes_without_private_data(self):
        routes = course.route_matches('一堆直播切片怎么分类混剪')
        self.assertEqual(routes[0]['id'], 'clip-library')
        self.assertTrue(all((ROOT / ref).is_file() for ref in routes[0]['references']))
        self.assertFalse(any(r['id'] == 'commerce' for r in course.route_matches('普通生活不卖货')))
        self.assertEqual(course.route_matches('成熟账号内容体系')[0]['id'], 'account')

    def test_private_index_cannot_enter_skill_folder(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--source', 'not-read.txt',
                                 'index', '--output', str(ROOT/'private-index-test.json')],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Skill', result.stderr)
        self.assertFalse((ROOT/'private-index-test.json').exists())

    def test_optional_private_chapter_routing_and_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source = folder/'source.txt'
            source.write_text('001_合成第一节\n这里是合成材料。\n002_合成第二节\n另一段合成材料。\n')
            index = course.make_index(source)
            (folder/'index.json').write_text(json.dumps(index))
            (folder/'routes.json').write_text(json.dumps([{'id':'account','lessons':['M002']}]))
            config = folder/'config.json'
            config.write_text(json.dumps({'source_path':'source.txt','index_path':'index.json','lesson_routes_path':'routes.json'}))
            def run(*args):
                return subprocess.run([sys.executable,str(SCRIPT),'--config',str(config),*args],capture_output=True,text=True)
            result=run('list','--query','成熟账号')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['lessons'][0]['id'],'M002')
            self.assertEqual(run('read','M002').returncode,0)
            source.write_text(source.read_text()+'已修改')
            self.assertNotEqual(run('read','M002').returncode,0)

if __name__ == '__main__':
    unittest.main()
