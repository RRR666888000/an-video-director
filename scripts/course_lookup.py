#!/usr/bin/env python3
"""Read-only method routing and optional local course retrieval; explicit index writes only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path.home() / '.codex' / 'skill-data' / 'an-video-director' / 'local.json'
HEAD = re.compile(r'^(\d{3,4})[_.．]([^\n\r\u2028]+)$', re.M)
NOTE = '规则同义映射和标题/主题排序，非语义搜索；没命中不代表概念不存在。'


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def normalized(value):
    return re.sub(r'[\s\W_]+', '', value.casefold())


def route_matches(query):
    q = normalized(query)
    routes = json.loads((ROOT / 'references' / 'query-routes.json').read_text())
    found = []
    for route in routes:
        route_query = q
        if route['id'] == 'commerce':
            # Ignore explicitly declined actions; another positive commercial goal may remain.
            route_query = re.sub(r'(?:不想|不要|不用|不做|不)(?:再|只|去|硬)?(?:卖货|带货|投流|进房|成交)', '', q)
        hits = [term for term in route['queries'] if normalized(term) in route_query]
        if hits:
            found.append({**route, 'matched': hits, 'score': max(len(normalized(t)) for t in hits)})
    return sorted(found, key=lambda r: -r['score'])


def expanded_terms(query, routes, literal=False):
    terms = [query.strip()]
    if not literal:
        terms.extend(t for r in routes for t in r['terms'])
    return list(dict.fromkeys(t for t in terms if t))


def configuration(args):
    path = Path(args.config or os.environ.get('AN_COURSE_CONFIG') or DEFAULT_CONFIG).expanduser()
    if not path.is_file():
        if args.config or os.environ.get('AN_COURSE_CONFIG'):
            raise ValueError(f'指定配置不存在：{path}')
        return {}, path
    config = json.loads(path.read_text())
    if not isinstance(config, dict):
        raise ValueError('本机配置必须是JSON对象。')
    return config, path


def configured_path(value, config_path):
    path = Path(value).expanduser()
    return path if path.is_absolute() else config_path.parent / path


def load_index(args, config, config_path):
    value = args.index or os.environ.get('AN_COURSE_INDEX') or config.get('index_path')
    if not value:
        raise ValueError('未配置课程索引。核心策划和route可直接使用；仅查课程需要--index或本机配置。')
    path = Path(value).expanduser() if args.index or os.environ.get('AN_COURSE_INDEX') else configured_path(value, config_path)
    index = json.loads(path.read_text())
    if not isinstance(index.get('lessons'), list):
        raise ValueError('课程索引缺少lessons列表。')
    return index


def load_text(args, index, config, config_path):
    value = args.source or os.environ.get('AN_COURSE_SOURCE') or config.get('source_path') or index.get('source_path')
    if not value:
        raise ValueError('未配置课程原文。核心方法可继续使用；查原文时用--source指定已有文件。')
    path = configured_path(value, config_path) if config.get('source_path') == value and not args.source and not os.environ.get('AN_COURSE_SOURCE') else Path(value).expanduser()
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != index['source_sha256']:
        raise ValueError('课程原文与索引哈希不符。先在工作目录生成新索引，不使用过期位置。')
    return raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')


def ranked_rows(index, query, routes, terms):
    if not query:
        return [(0, row) for row in index['lessons']]
    q = normalized(query)
    priority = {}
    for r in routes:
        for i, key in enumerate(r.get('lessons', [])):
            priority[key] = max(priority.get(key, 0), 100 - i * 12 + r['score'])
    result = []
    for row in index['lessons']:
        title = normalized(row['title'])
        topic = normalized(row.get('topic', ''))
        score = priority.get(row['id'], 0)
        score += 1000 if q == normalized(row['id']) else 0
        score += 80 if q and q in title else 0
        score += 35 if q and q in topic else 0
        score += min(60, sum(20 for t in terms if normalized(t) in title))
        score += min(20, sum(5 for t in terms if normalized(t) in topic))
        if score:
            result.append((score, row))
    return sorted(result, key=lambda pair: (-pair[0], pair[1]['start']))


def get_lesson(index, key):
    for row in index['lessons']:
        if row['id'].upper() == key.upper():
            return row
    raise ValueError(f'找不到课程编号{key}；先list确认实际编号。')


def make_index(source):
    raw = source.read_bytes()
    text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    heads = list(HEAD.finditer(text))
    if not heads:
        raise ValueError('未识别到课程标题，不猜测章节边界。')
    rows, ids = [], set()
    for i, h in enumerate(heads):
        num = h.group(1)
        key = ('M' if len(num) == 3 else 'E') + num
        if key in ids:
            raise ValueError(f'课程编号重复：{key}')
        ids.add(key)
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        rows.append({'id': key, 'title': h.group(0), 'start': h.start(), 'end': end,
                     'line': text.count('\n', 0, h.start()) + 1, 'characters': end - h.start(),
                     'review_status': 'indexed_only'})
    return {'source_sha256': hashlib.sha256(raw).hexdigest(), 'characters': len(text), 'lessons': rows}


def snippets(body, terms, context, limit):
    candidates = []
    heading_end = body.find('\n')
    for priority, term in enumerate(terms):
        for match in re.finditer(re.escape(term), body, re.I):
            if heading_end >= 0 and match.start() < heading_end:
                continue
            lo, hi = max(0, match.start() - context), min(len(body), match.end() + context)
            candidates.append((priority, match.start(), lo, hi, term))
    chosen = []
    for priority, pos, lo, hi, term in sorted(candidates):
        if any(lo < h['end_offset'] and hi > h['start_offset'] for h in chosen):
            continue
        chosen.append({'match_offset': pos, 'start_offset': lo, 'end_offset': hi,
                       'matched_term': term, 'text': body[lo:hi]})
        if len(chosen) >= limit:
            break
    return chosen


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', help='可选本机JSON配置；参数放在子命令前')
    p.add_argument('--index', help='已有索引文件')
    p.add_argument('--source', help='已有课程原文')
    sub = p.add_subparsers(dest='command', required=True)
    route = sub.add_parser('route'); route.add_argument('query')
    local = sub.add_parser('local'); local.add_argument('--query', default='')
    listing = sub.add_parser('list'); listing.add_argument('--query', default='')
    reading = sub.add_parser('read'); reading.add_argument('lesson'); reading.add_argument('--offset', type=int, default=0); reading.add_argument('--chars', type=int, default=5000)
    search = sub.add_parser('search'); search.add_argument('query'); search.add_argument('--lesson'); search.add_argument('--limit', type=int, default=6); search.add_argument('--context', type=int, default=180); search.add_argument('--literal', action='store_true')
    indexing = sub.add_parser('index'); indexing.add_argument('--output', type=Path, required=True); indexing.add_argument('--replace', action='store_true')
    args = p.parse_args(argv)
    try:
        if args.command == 'route':
            if not args.query.strip(): raise ValueError('query不能为空。')
            routes = route_matches(args.query)
            emit({'query': args.query, 'count': len(routes), 'routes': routes,
                  'note': NOTE, 'fallback': '未匹配时阅读SKILL.md任务表，按上下文选择；无需原课。' if not routes else None})
            return 0
        if args.command == 'index':
            args.output = args.output.expanduser().resolve()
            if args.output == ROOT or ROOT in args.output.parents:
                raise ValueError('私人课程索引必须保存到 Skill 目录之外。')
            if not args.source: raise ValueError('index需要--source；新索引不继承旧阅读状态。')
            if args.output.exists() and not args.replace: raise ValueError('索引已存在；选新路径或显式--replace。')
            result = make_index(Path(args.source).expanduser())
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
            emit({'output': str(args.output), 'sections': len(result['lessons']), 'characters': result['characters'], 'note': '索引不保存原文绝对路径；read/search需--source或本机配置。'})
            return 0
        config, config_path = configuration(args)
        if args.command == 'local':
            cases = config.get('cases', [])
            if not isinstance(cases, list) or any(not isinstance(c, dict) for c in cases):
                raise ValueError('配置cases必须是对象列表。')
            if args.query:
                q = normalized(args.query)
                cases = [c for c in cases if any(normalized(t) in q for t in c.get('keywords', []) if normalized(t))]
            cases = [{**c, 'path': str(configured_path(c['path'], config_path))} if c.get('path') else c for c in cases]
            emit({'configured': bool(config), 'source_configured': bool(config.get('source_path')), 'cases': cases,
                  'note': '只读当前任务相关的案例；仅返回配置位置，不证明文件内容或业务事实当前有效。'})
            return 0
        index = load_index(args, config, config_path)
        query = getattr(args, 'query', '')
        routes = route_matches(query) if query else []
        if config.get('lesson_routes_path'):
            private_routes = json.loads(configured_path(config['lesson_routes_path'], config_path).read_text())
            lesson_map = {r['id']: r.get('lessons', []) for r in private_routes}
            routes = [{**r, 'lessons': lesson_map.get(r['id'], [])} for r in routes]
        terms = expanded_terms(query, routes, getattr(args, 'literal', False))
        ranked = ranked_rows(index, query, routes, terms)
        if args.command == 'list':
            rows = [{**{k: row.get(k) for k in ['id','title','characters','line','topic','review_status']}, 'score': score} for score, row in ranked]
            emit({'count': len(rows), 'source_verified': False, 'expanded_terms': terms, 'note': NOTE + '目录不是逐字阅读记录。', 'lessons': rows})
            return 0
        text = load_text(args, index, config, config_path)
        if args.command == 'read':
            if not 1 <= args.chars <= 20000 or args.offset < 0: raise ValueError('chars须为1–20000，offset不能为负数。')
            row = get_lesson(index, args.lesson); body = text[row['start']:row['end']]
            if args.offset > len(body): raise ValueError('offset超出本节长度。')
            end = min(len(body), args.offset + args.chars)
            emit({'id': row['id'], 'title': row['title'], 'offset': args.offset, 'end_offset': end,
                  'total_characters': len(body), 'has_more': end < len(body), 'source_line': row['line'], 'text': body[args.offset:end]})
            return 0
        if not query.strip() or not 1 <= args.limit <= 30 or not 0 <= args.context <= 1000:
            raise ValueError('query不能为空；limit为1–30；context为0–1000。')
        if args.lesson:
            chosen = [get_lesson(index, args.lesson)]
        else:
            scored_ids = {row['id'] for _, row in ranked}
            chosen = [row for _, row in ranked] + [row for row in index['lessons'] if row['id'] not in scored_ids]
        groups = []
        for row in chosen:
            body = text[row['start']:row['end']]
            hits = snippets(body, terms, args.context, args.limit + 1)
            if hits:
                groups.append([{**hit, 'id': row['id'], 'title': row['title']} for hit in hits])
        hits, seen = [], set()
        # One hit per relevant lesson before returning to another hit in the same lesson.
        for n in range(args.limit + 1):
            for group in groups:
                if n >= len(group): continue
                item = group[n]; signature = normalized(item['text'])
                if signature in seen: continue
                seen.add(signature); hits.append(item)
                if len(hits) > args.limit: break
            if len(hits) > args.limit: break
        more = len(hits) > args.limit
        emit({'query': query, 'count': min(len(hits), args.limit), 'limit_reached': more,
              'expanded_terms': terms, 'note': NOTE + '邻近片段去重，优先不同相关课节；--literal仅取消同义扩展。',
              'hits': hits[:args.limit]})
        return 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as e:
        print(f'课程检索失败：{e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
