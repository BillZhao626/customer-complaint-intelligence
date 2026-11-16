"""Small pre-dispatch integrity gate over the existing Dispatcher, not a new harness.

Every source/input is hashed before a request. Loaded project code must match
the frozen files too; an unchanged file after a stale import is insufficient.
Family identity is explicit: renaming a previously seen family cannot hide exposure.
"""
import ast
import hashlib
import inspect
import json
import sys
import types
from pathlib import Path

class IntegrityError(ValueError):
    pass

def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _codes(code):
    result={code.co_qualname:code}
    for value in code.co_consts:
        if isinstance(value,types.CodeType):result.update(_codes(value))
    return result

def _runtime_codes(module):
    for value in vars(module).values():
        if inspect.isfunction(value) and value.__module__==module.__name__:
            yield inspect.unwrap(value).__code__
        elif inspect.isclass(value) and value.__module__==module.__name__:
            for member in vars(value).values():
                if isinstance(member,(classmethod,staticmethod)):member=member.__func__
                if inspect.isfunction(member):yield inspect.unwrap(member).__code__

def verify_loaded_code(root,hashes,*,modules=None):
    root=Path(root).resolve()
    checked=[]
    for name,module in list((sys.modules if modules is None else modules).items()):
        if not (name=='__main__' or name=='src' or name.startswith('src.') or name=='scripts' or name.startswith('scripts.')):continue
        origin=getattr(module,'__file__',None)
        if not origin:continue
        path=Path(origin).resolve()
        if name=='__main__' and (not path.is_relative_to(root) or path.relative_to(root).as_posix() not in hashes):continue
        if not path.is_relative_to(root):raise IntegrityError('Project module imported outside frozen root: '+name)
        relative=path.relative_to(root).as_posix()
        if relative not in hashes:raise IntegrityError('Imported project module absent from freeze: '+relative)
        source=path.read_bytes()
        compiled=_codes(compile(source,str(path),'exec',dont_inherit=True))
        for code in _runtime_codes(module):
            # Generated wrappers whose source belongs to another package are
            # checked via their own project module, rather than misattributed.
            if Path(code.co_filename).resolve()!=path:continue
            expected=compiled.get(code.co_qualname)
            if expected is None or code!=expected:
                raise IntegrityError('Loaded implementation differs from frozen source: '+name+'.'+code.co_qualname)
        for statement in ast.parse(source).body:
            if not isinstance(statement,(ast.Assign,ast.AnnAssign)):continue
            targets=statement.targets if isinstance(statement,ast.Assign) else [statement.target]
            try:value=ast.literal_eval(statement.value)
            except (ValueError,TypeError,SyntaxError):continue
            for target in targets:
                if isinstance(target,ast.Name) and target.id.isupper() and target.id in vars(module) and vars(module)[target.id]!=value:
                    raise IntegrityError('Loaded constant differs from frozen source: '+name+'.'+target.id)
        checked.append(name)
    return checked

def verify(manifest):
    if not manifest or manifest.get('version')!='execution-integrity-v1':raise IntegrityError('Missing frozen execution manifest')
    root=Path(manifest['root']).resolve();hashes=manifest['source_hashes']
    if not hashes:raise IntegrityError('Empty source freeze')
    for relative,expected in hashes.items():
        path=(root/relative).resolve()
        if not path.is_relative_to(root) or not path.is_file() or file_hash(path)!=expected:raise IntegrityError('Frozen source drift: '+relative)
    for entry in manifest.get('inputs',[]):
        path=Path(entry['path'])
        if not path.is_file() or file_hash(path)!=entry['sha256']:raise IntegrityError('Frozen input drift: '+str(path))
    dataset=manifest.get('independent_dataset')
    if dataset:
        pinned={str(Path(x['path']).resolve()) for x in manifest['inputs']}
        paths=[dataset[k] for k in ('candidates','history','aliases')]
        if any(str(Path(p).resolve()) not in pinned for p in paths):raise IntegrityError('Unfrozen family preflight input')
        candidates,history,aliases=[json.loads(Path(p).read_text('utf8')) for p in paths]
        family_preflight(candidates,history,aliases)
    modules=verify_loaded_code(root,hashes)
    return dict(source_count=len(hashes),input_count=len(manifest.get('inputs',[])),loaded_modules=modules,manifest_hash=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest())

def freeze(root,*,inputs=()):
    root=Path(root).resolve()
    paths=[p for folder in ('src','scripts') for p in (root/folder).rglob('*.py') if '__pycache__' not in p.parts]
    result=dict(version='execution-integrity-v1',root=str(root),source_hashes={p.relative_to(root).as_posix():file_hash(p) for p in sorted(paths)},inputs=[dict(path=str(Path(p).resolve()),sha256=file_hash(p)) for p in inputs])
    verify(result)
    return result

def family_preflight(candidates,history,aliases=None):
    """Canonical family + input hashes; no claims of semantic proof from text novelty."""
    aliases=aliases or {}
    def canonical(value):
        seen=set()
        while value in aliases:
            if value in seen:raise IntegrityError('Cyclic family aliases')
            seen.add(value);value=aliases[value]
        return value
    family=lambda r:canonical(r.get('canonical_family') or r['family'])
    hashes={r['input_hash'] for r in history};families={family(r) for r in history};seen_hashes=set();issues=[]
    for r in candidates:
        reasons=[]
        if r['input_hash'] in hashes:reasons.append('EXPOSED_INPUT_HASH')
        if family(r) in families:reasons.append('EXPOSED_CANONICAL_FAMILY')
        if r['input_hash'] in seen_hashes:reasons.append('DUPLICATE_CANDIDATE_INPUT')
        if not r.get('family_review',{}).get('reviewed_against_full_registry'):reasons.append('FAMILY_REVIEW_MISSING')
        seen_hashes.add(r['input_hash'])
        if reasons:issues.append(dict(case_id=r.get('case_id'),reasons=reasons))
    if issues:raise IntegrityError('Independent dataset preflight failed: '+json.dumps(issues,ensure_ascii=False))
    return dict(status='PASS_ENGINEERING_PREFLIGHT_ONLY',candidates=len(candidates),history=len(history),semantic_independence='REQUIRES_REGISTERED_FAMILY_REVIEW_NOT_PROVEN_BY_HASH')
