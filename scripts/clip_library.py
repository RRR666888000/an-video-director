#!/usr/bin/env python3
"""Local media register and conservative edit-plan checks; no automatic understanding."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

SKILL_ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = json.loads((SKILL_ROOT / 'references/clip-taxonomy.json').read_text())
MEDIA_EXT = {'.mp4', '.mov', '.m4v', '.mkv', '.webm', '.avi', '.mts', '.m2ts'}
ARRAY_FIELDS = ('product_identity', 'topic', 'content_roles', 'evidence_types',
                'emotional_state', 'context_dependency')
ENUM_FIELDS = ('semantic_complete', 'timeliness', 'use_status', 'review_status')
DEFAULTS = dict(product_identity=[], topic=[], content_roles=[], evidence_types=['unknown'],
                emotional_state=['unknown'], context_dependency=[],
                semantic_complete='uncertain', timeliness='unknown',
                use_status='candidate', review_status='proposed')


class LibraryError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def external(path):
    p = Path(path).expanduser().resolve()
    if p == SKILL_ROOT or SKILL_ROOT in p.parents:
        raise LibraryError('Project data and media must be outside the installed/release skill directory')
    return p


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def write_json(path, value):
    p = external(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + p.name, dir=p.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, p)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load_library(path, create=False):
    p = external(path)
    if not p.exists() and create:
        return dict(schema_version=1, sources={}, clips={}, coverage={}, failures=[])
    lib = read_json(p)
    if lib.get('schema_version') != 1:
        raise LibraryError('Unsupported library schema version')
    return lib


def tool(name):
    found = shutil.which(name)
    if not found:
        raise LibraryError(name + ' is required for this command')
    return found


def probe(path):
    proc = subprocess.run([tool('ffprobe'), '-v', 'error', '-show_format',
                           '-show_streams', '-of', 'json', str(path)],
                          capture_output=True, text=True)
    if proc.returncode:
        raise LibraryError('ffprobe failed: ' + proc.stderr.strip()[:500])
    data = json.loads(proc.stdout)
    duration = float(data.get('format', {}).get('duration', 0))
    if not math.isfinite(duration) or duration <= 0:
        raise LibraryError('Media duration could not be verified')
    videos = [s for s in data.get('streams', []) if s['codec_type'] == 'video']
    if not videos:
        raise LibraryError('No video stream found')
    v = videos[0]
    return dict(duration_s=duration, width=v.get('width'), height=v.get('height'),
                frame_rate=v.get('avg_frame_rate'),
                has_audio=any(s['codec_type'] == 'audio' for s in data['streams']),
                probe_status='verified')


def ingest(lib, paths, recursive=False):
    result = []
    for value in paths:
        p = Path(value).expanduser().resolve()
        if p.is_dir():
            iterator = p.rglob('*') if recursive else p.iterdir()
            files = sorted(x for x in iterator if x.is_file() and x.suffix.lower() in MEDIA_EXT)
        else:
            files = [p]
        for path in files:
            try:
                sha = digest(path)
            except OSError as exc:
                lib['failures'].append(dict(path=str(path), error=str(exc), at=now()))
                result.append(dict(path=str(path), status='unreadable'))
                continue
            sid = 'src_' + sha
            if sid in lib['sources']:
                src = lib['sources'][sid]
                if str(path) not in src['paths']:
                    src['paths'].append(str(path))
                # Retrying an unavailable probe does not discard prior annotations.
                if src['probe_status'] != 'verified':
                    try:
                        src.update(probe(path))
                        src.pop('probe_error', None)
                    except LibraryError as exc:
                        src['probe_error'] = str(exc)
                result.append(dict(source_id=sid, status='existing', path=str(path)))
                continue
            src = dict(source_id=sid, sha256=sha, paths=[str(path)],
                       original_name=path.name, byte_size=path.stat().st_size,
                       recorded_at=None, added_at=now(), duration_s=None,
                       probe_status='pending')
            try:
                src.update(probe(path))
            except LibraryError as exc:
                src['probe_error'] = str(exc)
            lib['sources'][sid] = src
            lib['coverage'][sid] = dict(proposed=[], transcript=[], av=[], records=[])
            result.append(dict(source_id=sid, status=src['probe_status'], path=str(path)))
    return result


def interval(source, start, end):
    if any(isinstance(n, bool) or not isinstance(n, (int, float)) or
           not math.isfinite(n) for n in (start, end)):
        raise LibraryError('Timecodes must be finite numbers in seconds')
    duration = source.get('duration_s')
    if source.get('probe_status') != 'verified' or duration is None:
        raise LibraryError('A verified source duration is required')
    if start < 0 or end <= start or end > duration + 0.001:
        raise LibraryError('Timecodes are outside the source duration')
    return float(start), min(float(end), duration)


def merge(intervals):
    out = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def seconds(intervals):
    return round(sum(end - start for start, end in merge(intervals)), 6)


def coverage(lib, source_id, stage, start, end, note):
    if stage not in ('proposed', 'transcript', 'av') or not str(note).strip():
        raise LibraryError('Coverage needs a valid stage and an explicit review note')
    if source_id not in lib['sources']:
        raise LibraryError('Unknown source_id')
    start, end = interval(lib['sources'][source_id], start, end)
    rec = lib['coverage'][source_id]
    rec[stage] = merge(rec[stage] + [[start, end]])
    rec['records'].append(dict(stage=stage, start_s=start, end_s=end, note=note, at=now()))


def source_for(lib, sid):
    if sid not in lib['sources']:
        raise LibraryError('Unknown source_id: ' + str(sid))
    return lib['sources'][sid]


def validate_annotation(lib, item):
    if not isinstance(item, dict):
        raise LibraryError('Each annotation must be an object')
    source = source_for(lib, item.get('source_id'))
    start, end = interval(source, item.get('start_s'), item.get('end_s'))
    key = f"{source['source_id']}|{start:.9f}|{end:.9f}"
    cid = 'clip_' + hashlib.sha256(key.encode()).hexdigest()[:24]
    if item.get('clip_id') not in (None, cid):
        raise LibraryError('clip_id must match this source and time window; changed cuts get new IDs')
    record = copy.deepcopy(DEFAULTS)
    record.update(item)
    record.update(clip_id=cid, start_s=start, end_s=end)
    for name in ARRAY_FIELDS:
        values = record[name]
        if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
            raise LibraryError(name + ' must be an array of non-empty strings')
        if len(values) != len(set(values)):
            raise LibraryError(name + ' contains duplicate labels')
        if name in TAXONOMY and any(v not in TAXONOMY[name] for v in values):
            raise LibraryError('Unknown label in ' + name)
    for name in ENUM_FIELDS:
        if record[name] not in TAXONOMY[name]:
            raise LibraryError('Unknown label in ' + name)
    for name, exclusive in [('context_dependency', {'standalone'}),
                            ('evidence_types', {'none', 'unknown'}),
                            ('emotional_state', {'unknown'})]:
        if len(record[name]) > 1 and exclusive.intersection(record[name]):
            raise LibraryError(name + ' has contradictory labels')
    if record['review_status'] != 'proposed' and not str(record.get('review_note', '')).strip():
        raise LibraryError('Checked annotations require a review_note describing actual review')
    if record['use_status'] == 'usable' and record['review_status'] != 'av_checked':
        raise LibraryError('usable requires av_checked; text checks alone are insufficient')
    return record


def annotate(lib, items):
    if not isinstance(items, list):
        raise LibraryError('Annotation input must be a JSON array')
    # Validate the complete import before mutating anything.
    records = [validate_annotation(lib, item) for item in items]
    ids = []
    for record in records:
        cid = record['clip_id']
        previous = lib['clips'].get(cid)
        comparable = {k: v for k, v in (previous or {}).items()
                      if k not in ('revision', 'updated_at', 'history')}
        if previous and comparable == record:
            ids.append(cid)
            continue
        history = copy.deepcopy(previous.get('history', [])) if previous else []
        if previous:
            history.append({k: v for k, v in previous.items() if k != 'history'})
        record.update(revision=(previous or {}).get('revision', 0) + 1,
                      updated_at=now(), history=history)
        lib['clips'][cid] = record
        stage = {'proposed': 'proposed', 'transcript_checked': 'transcript',
                 'av_checked': 'av'}[record['review_status']]
        coverage(lib, record['source_id'], 'proposed', record['start_s'], record['end_s'],
                 'Annotated time window; review stage recorded separately')
        if stage != 'proposed':
            coverage(lib, record['source_id'], stage, record['start_s'], record['end_s'],
                     record['review_note'])
        ids.append(cid)
    return ids


def verified_source(source):
    for value in source['paths']:
        p = Path(value)
        try:
            if p.is_file() and digest(p) == source['sha256']:
                return p
        except OSError:
            pass
    raise LibraryError('No source alias matches the registered hash; restore or ingest changed media')


def check_plan(lib, plan):
    errors = []
    if not isinstance(plan, dict):
        raise LibraryError('Plan must be an object')
    for field in ('purpose', 'hypothesis'):
        if not isinstance(plan.get(field), str) or not plan[field].strip():
            errors.append(field + ' is required')
    if 'target_product_id' not in plan or (plan['target_product_id'] is not None and
                                         not isinstance(plan['target_product_id'], str)):
        errors.append('target_product_id must be a product ID string or explicit null for category content')
    target = plan.get('target_product_id')
    if target == '':
        errors.append('target_product_id cannot be blank')
    segments = plan.get('segments')
    if not isinstance(segments, list) or not segments:
        return dict(structural_check_passed=False, errors=errors + ['segments must be a non-empty array'],
                    scope='Structural and recorded-review checks only; not ad approval or an effect prediction')
    plan_ids = {s.get('clip_id') for s in segments if isinstance(s, dict)}
    verified = set()
    for i, seg in enumerate(segments):
        prefix = f'segment {i + 1}: '
        if not isinstance(seg, dict) or seg.get('clip_id') not in lib['clips']:
            errors.append(prefix + 'unknown clip_id')
            continue
        c = lib['clips'][seg['clip_id']]
        role = seg.get('actual_role')
        if role not in TAXONOMY['content_roles']:
            errors.append(prefix + 'valid actual_role is required')
        elif role not in c['content_roles'] and not str(seg.get('role_reason', '')).strip():
            errors.append(prefix + 'a new actual_role outside candidate roles requires role_reason')
        for field, required in [('review_status', 'av_checked'), ('use_status', 'usable'),
                                ('semantic_complete', 'complete'), ('timeliness', 'stable')]:
            if c[field] != required:
                errors.append(prefix + field + ' must be ' + required)
        if not c.get('review_note'):
            errors.append(prefix + 'review_note is missing')
        deps = c['context_dependency']
        if deps != ['standalone']:
            refs = seg.get('resolved_context', [])
            if (not deps or not isinstance(refs, list) or not refs or
                any(ref not in plan_ids or ref == c['clip_id'] for ref in refs) or
                not str(seg.get('context_resolution_note', '')).strip()):
                errors.append(prefix + 'context is unresolved; supply included supporting clips and explanation')
            elif 'neighboring_speech' in deps:
                neighbors = {segments[n].get('clip_id') for n in (i - 1, i + 1)
                             if 0 <= n < len(segments) and isinstance(segments[n], dict)}
                if not neighbors.intersection(refs):
                    errors.append(prefix + 'neighboring_speech needs an adjacent supporting segment')
        products = c['product_identity']
        relation = seg.get('relation')
        if relation not in (None, 'same_product', 'category_example', 'general_visual'):
            errors.append(prefix + 'unknown relation')
        if relation == 'general_visual':
            if role != 'broll' or not str(seg.get('relation_note', '')).strip():
                errors.append(prefix + 'general_visual requires broll role and an explanation; it cannot be evidence')
        elif target is not None:
            if products != [target]:
                errors.append(prefix + 'product does not exactly match target; use a separate category/comparison plan')
        elif products:
            if relation != 'category_example' or not str(seg.get('relation_note', '')).strip():
                errors.append(prefix + 'category examples require an explicit relation and product/claim explanation')
        elif role in ('feature', 'experience', 'evidence', 'objection', 'choice'):
            errors.append(prefix + 'product-bound claim has no verified product identity')
        try:
            src = source_for(lib, c['source_id'])
            interval(src, c['start_s'], c['end_s'])
            if c['source_id'] not in verified:
                verified_source(src)
                verified.add(c['source_id'])
        except LibraryError as exc:
            errors.append(prefix + str(exc))
    return dict(structural_check_passed=not errors, errors=errors,
                scope='Structural and recorded-review checks only; not ad approval or an effect prediction')


def inspect(lib, role=None, status=None, source_id=None):
    clips = [c for c in lib['clips'].values()
             if (not role or role in c['content_roles']) and
             (not status or status == c['use_status']) and
             (not source_id or source_id == c['source_id'])]
    coverage_report = {}
    for sid, rec in lib['coverage'].items():
        if source_id and sid != source_id:
            continue
        duration = lib['sources'][sid]['duration_s']
        av = seconds(rec['av'])
        initial_or_reviewed = seconds(rec['proposed'] + rec['av'])
        coverage_report[sid] = dict(duration_s=duration, av_checked_s=av,
                                   proposed_only_s=round(initial_or_reviewed - av, 6),
                                   unprocessed_s=None if duration is None else round(max(0, duration - initial_or_reviewed), 6),
                                   transcript_checked_s=seconds(rec['transcript']),
                                   intervals={k: rec[k] for k in ('proposed', 'transcript', 'av')})
    return dict(source_count=len(lib['sources']), clip_count=len(clips),
                clips=clips, coverage=coverage_report, failures=lib['failures'])


def cut(lib, clip_id, output):
    if clip_id not in lib['clips']:
        raise LibraryError('Unknown clip_id')
    out = external(output)
    if out.suffix.lower() != '.mp4':
        raise LibraryError('Output must end in .mp4')
    if out.exists() or out.is_symlink():
        raise LibraryError('Refusing to overwrite an existing output')
    c = lib['clips'][clip_id]
    src = source_for(lib, c['source_id'])
    source_path = verified_source(src)
    start, end = interval(src, c['start_s'], c['end_s'])
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.clip-', suffix='.mp4', dir=out.parent)
    os.close(fd)
    temp = Path(name)
    try:
        cmd = [tool('ffmpeg'), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
               '-i', str(source_path), '-ss', str(start), '-t', str(end - start),
               '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'libx264', '-preset', 'fast',
               '-crf', '18', '-c:a', 'aac', '-movflags', '+faststart', str(temp)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode:
            raise LibraryError('ffmpeg failed: ' + proc.stderr.strip()[:1000])
        metadata = probe(temp)
        if abs(metadata['duration_s'] - (end - start)) > 0.15:
            raise LibraryError('Export duration differs materially from requested time window')
        if digest(source_path) != src['sha256']:
            raise LibraryError('Source changed during export; output not committed')
        # Atomic, no-clobber creation even if another writer creates the output.
        os.link(temp, out)
        return dict(output=str(out), clip_id=clip_id, source_id=c['source_id'],
                    source_start_s=start, source_end_s=end, sha256=digest(out),
                    metadata=metadata, state='exported_pending_visual_and_audio_review',
                    note='A cut module, not an assembled or approved advertisement')
    finally:
        temp.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', required=True, help='External project library JSON path')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('ingest')
    p.add_argument('paths', nargs='+')
    p.add_argument('--recursive', action='store_true')
    p = sub.add_parser('annotate')
    p.add_argument('--input', required=True)
    p = sub.add_parser('coverage')
    p.add_argument('--source-id', required=True)
    p.add_argument('--stage', choices=['proposed', 'transcript', 'av'], required=True)
    p.add_argument('--start', type=float, required=True)
    p.add_argument('--end', type=float, required=True)
    p.add_argument('--note', required=True)
    p = sub.add_parser('inspect')
    p.add_argument('--role', choices=list(TAXONOMY['content_roles']))
    p.add_argument('--status', choices=list(TAXONOMY['use_status']))
    p.add_argument('--source-id')
    p = sub.add_parser('check-plan')
    p.add_argument('--input', required=True)
    p = sub.add_parser('cut')
    p.add_argument('--clip-id', required=True)
    p.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        lib = load_library(args.library, create=args.command == 'ingest')
        if args.command == 'ingest':
            result = ingest(lib, args.paths, args.recursive)
        elif args.command == 'annotate':
            result = dict(clip_ids=annotate(lib, read_json(args.input)))
        elif args.command == 'coverage':
            coverage(lib, args.source_id, args.stage, args.start, args.end, args.note)
            result = inspect(lib, source_id=args.source_id)['coverage']
        elif args.command == 'inspect':
            result = inspect(lib, args.role, args.status, args.source_id)
        elif args.command == 'check-plan':
            result = check_plan(lib, read_json(args.input))
        else:
            result = cut(lib, args.clip_id, args.output)
        if args.command in ('ingest', 'annotate', 'coverage'):
            write_json(args.library, lib)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 2 if args.command == 'check-plan' and not result['structural_check_passed'] else 0
    except (LibraryError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps(dict(error=str(exc)), ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
