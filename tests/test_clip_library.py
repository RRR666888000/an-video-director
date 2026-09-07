"""Synthetic regression tests; no personal media or project records are used."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('clip_library', ROOT / 'scripts/clip_library.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='clip-library-test-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.raw = self.path / 'source.mp4'
        self.raw.write_bytes(b'synthetic source identity, not playable')
        sha = m.digest(self.raw)
        self.sid = 'src_' + sha
        self.lib = dict(schema_version=1, sources={self.sid: dict(source_id=self.sid, sha256=sha,
                        paths=[str(self.raw)], duration_s=30.0, probe_status='verified')}, clips={},
                        coverage={self.sid: dict(proposed=[], transcript=[], av=[], records=[])}, failures=[])

    def annotation(self, **overrides):
        data = dict(source_id=self.sid, start_s=1.0, end_s=5.0, product_identity=['bag_a_v1'],
                    content_roles=['experience', 'evidence'], context_dependency=['standalone'],
                    semantic_complete='complete', timeliness='stable', use_status='usable',
                    review_status='av_checked', review_note='Synthetic review attestation for structural tests only')
        data.update(overrides)
        return data

    def add(self, **overrides):
        return m.annotate(self.lib, [self.annotation(**overrides)])[0]

    def plan(self, cid, **segment):
        return dict(purpose='Demonstrate key access', hypothesis='Concrete action clarifies use',
                    target_product_id='bag_a_v1', segments=[dict(clip_id=cid, actual_role='experience', **segment)])

    def test_invalid_timecodes_and_atomic_annotation_import(self):
        for start, end in [(-1, 2), (1, 1), (3, 2), (0, 31), (float('nan'), 2),
                           (0, float('inf')), (False, 1), ('0', 2)]:
            with self.subTest(start=start, end=end), self.assertRaises(m.LibraryError):
                m.annotate(self.lib, [self.annotation(), self.annotation(start_s=start, end_s=end)])
            self.assertEqual(self.lib['clips'], {})
        with self.assertRaises(m.LibraryError):
            self.add(source_id='missing')

    def test_stable_ids_idempotent_import_and_revisions(self):
        cid = self.add()
        self.assertEqual(cid, self.add())
        self.assertEqual(self.lib['clips'][cid]['revision'], 1)
        self.add(topic=['key access'])
        self.assertEqual(self.lib['clips'][cid]['revision'], 2)
        self.assertEqual(len(self.lib['clips'][cid]['history']), 1)
        self.assertNotEqual(cid, self.add(start_s=1.1))

    def test_safe_defaults_and_taxonomy_validation(self):
        cid = m.annotate(self.lib, [dict(source_id=self.sid, start_s=2, end_s=3)])[0]
        self.assertEqual(self.lib['clips'][cid]['review_status'], 'proposed')
        self.assertFalse(m.check_plan(self.lib, self.plan(cid))['structural_check_passed'])
        for fields in [dict(content_roles=['viral_guaranteed']),
                       dict(context_dependency=['standalone', 'neighboring_speech']),
                       dict(evidence_types=['none', 'observed_action']),
                       dict(review_status='transcript_checked'), dict(review_note='')]:
            with self.subTest(fields=fields), self.assertRaises(m.LibraryError):
                self.add(**fields)

    def test_coverage_merges_ranges_and_separates_transcripts(self):
        m.coverage(self.lib, self.sid, 'transcript', 0, 30, 'Text coverage only')
        self.add()
        self.add(start_s=3, end_s=7)
        report = m.inspect(self.lib)['coverage'][self.sid]
        self.assertEqual(report['av_checked_s'], 6)
        self.assertEqual(report['transcript_checked_s'], 30)
        self.assertEqual(report['unprocessed_s'], 24)
        self.assertEqual(report['proposed_only_s'], 0)

    def test_text_checked_annotations_are_processed_but_not_av_checked(self):
        self.add(use_status='candidate', review_status='transcript_checked')
        report = m.inspect(self.lib)['coverage'][self.sid]
        self.assertEqual(report['proposed_only_s'], 4)
        self.assertEqual(report['transcript_checked_s'], 4)
        self.assertEqual(report['av_checked_s'], 0)
        self.assertEqual(report['unprocessed_s'], 26)

    def test_plan_rejects_changed_source_and_missing_intent(self):
        cid = self.add()
        self.assertTrue(m.check_plan(self.lib, self.plan(cid))['structural_check_passed'])
        p = self.plan(cid)
        del p['hypothesis']
        self.assertFalse(m.check_plan(self.lib, p)['structural_check_passed'])
        self.raw.write_bytes(b'changed')
        self.assertFalse(m.check_plan(self.lib, self.plan(cid))['structural_check_passed'])

    def test_product_gates_and_explicit_category_relation(self):
        cid = self.add(product_identity=['bag_b_v1'])
        self.assertFalse(m.check_plan(self.lib, self.plan(cid))['structural_check_passed'])
        p = self.plan(cid)
        p['target_product_id'] = None
        self.assertFalse(m.check_plan(self.lib, p)['structural_check_passed'])
        p['segments'][0].update(relation='category_example', relation_note='Clearly identified B example, no A claim')
        self.assertTrue(m.check_plan(self.lib, p)['structural_check_passed'])
        p['target_product_id'] = 'bag_a_v1'
        self.assertFalse(m.check_plan(self.lib, p)['structural_check_passed'])

    def test_broll_is_not_cross_product_evidence(self):
        cid = self.add(product_identity=['bag_b_v1'], content_roles=['broll', 'evidence'])
        p = self.plan(cid, relation='general_visual', relation_note='Ambient view only')
        p['segments'][0]['actual_role'] = 'evidence'
        self.assertFalse(m.check_plan(self.lib, p)['structural_check_passed'])
        p['segments'][0]['actual_role'] = 'broll'
        self.assertTrue(m.check_plan(self.lib, p)['structural_check_passed'])

    def test_context_must_be_present_and_adjacent(self):
        cid = self.add(context_dependency=['neighboring_speech'])
        supporting = self.add(start_s=5, end_s=8)
        p = self.plan(cid)
        self.assertFalse(m.check_plan(self.lib, p)['structural_check_passed'])
        p['segments'][0].update(resolved_context=[supporting], context_resolution_note='Adjacent question supplies the object')
        self.assertFalse(m.check_plan(self.lib, p)['structural_check_passed'])
        p['segments'].append(dict(clip_id=supporting, actual_role='experience'))
        self.assertTrue(m.check_plan(self.lib, p)['structural_check_passed'])

    def test_review_completeness_and_timeliness_gates(self):
        for changes in [dict(use_status='candidate', review_status='proposed'),
                        dict(semantic_complete='incomplete'), dict(timeliness='expired'),
                        dict(timeliness='time_bound'), dict(timeliness='unknown')]:
            with self.subTest(changes=changes):
                cid = self.add(**changes)
                self.assertFalse(m.check_plan(self.lib, self.plan(cid))['structural_check_passed'])

    def test_external_storage_atomic_roundtrip_and_inspection_filter(self):
        for p in (ROOT / 'local.json', ROOT / 'runs/out.mp4'):
            with self.assertRaises(m.LibraryError):
                m.external(p)
        self.add()
        m.write_json(self.path / 'library.json', self.lib)
        self.assertEqual(m.load_library(self.path / 'library.json'), self.lib)
        self.assertEqual(m.inspect(self.lib, role='evidence')['clip_count'], 1)
        self.assertEqual(m.inspect(self.lib, role='cta')['clip_count'], 0)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg/ffprobe required')
class MediaIntegrationTests(unittest.TestCase):
    def test_ingest_dedup_accurate_cut_no_overwrite_and_source_preserved(self):
        with tempfile.TemporaryDirectory(prefix='clip-media-test-') as value:
            root = Path(value)
            source = root / 'synthetic.mp4'
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                            '-i', 'testsrc2=size=160x240:rate=30:duration=2', '-f', 'lavfi', '-i',
                            'sine=frequency=440:duration=2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac', '-shortest', str(source)], check=True)
            sha = m.digest(source)
            lib = m.load_library(root / 'library.json', create=True)
            result = m.ingest(lib, [source])
            sid = result[0]['source_id']
            self.assertEqual(result[0]['status'], 'verified')
            alias = root / 'renamed.mp4'
            shutil.copy2(source, alias)
            m.ingest(lib, [alias])
            self.assertEqual(len(lib['sources']), 1)
            self.assertEqual(len(lib['sources'][sid]['paths']), 2)
            cid = m.annotate(lib, [dict(source_id=sid, start_s=0.2, end_s=1.4)])[0]
            result = m.cut(lib, cid, root / 'modules/cut.mp4')
            self.assertAlmostEqual(result['metadata']['duration_s'], 1.2, delta=0.08)
            self.assertTrue(result['metadata']['has_audio'])
            self.assertEqual(m.digest(source), sha)
            self.assertEqual(result['state'], 'exported_pending_visual_and_audio_review')
            with self.assertRaises(m.LibraryError):
                m.cut(lib, cid, root / 'modules/cut.mp4')
            source.write_bytes(b'changed')
            # A verified identical alias remains a legitimate source.
            self.assertEqual(m.verified_source(lib['sources'][sid]), alias.resolve())
            alias.write_bytes(b'changed too')
            with self.assertRaises(m.LibraryError):
                m.cut(lib, cid, root / 'modules/changed.mp4')

    def test_probe_failure_remains_pending(self):
        with tempfile.TemporaryDirectory(prefix='clip-invalid-test-') as value:
            root = Path(value)
            source = root / 'invalid.mp4'
            source.write_bytes(b'not a video')
            lib = m.load_library(root / 'library.json', create=True)
            sid = m.ingest(lib, [source])[0]['source_id']
            self.assertEqual(lib['sources'][sid]['probe_status'], 'pending')
            self.assertIsNone(lib['sources'][sid]['duration_s'])
            with self.assertRaises(m.LibraryError):
                m.annotate(lib, [dict(source_id=sid, start_s=0, end_s=1)])


if __name__ == '__main__':
    unittest.main()
