#!/usr/bin/env python3
"""Build a TaskSpec draft and bind independent authority; never execute a checker.

Standard library only. Uses existing adjacent safe file/parser helpers. Explicit
paths/hashes authorize no access themselves. Output is not semantic acceptance.
"""
import argparse
import copy
import json
import os
import stat
import sys

sys.dont_write_bytecode = True
from _task_spec_io import Reader, Refused as ReadRefused, allowed, contains, normalized
from prepare_delegation_input import decode, digest, directory, hex_digest, parse

LIMIT = 256 * 1024
KINDS = {'installed_skill', 'helper', 'runtime_executable', 'dependency_lock',
         'input_manifest', 'capability_receipt', 'contract_schema', 'other'}
CATEGORIES = {'tool', 'skill_helper', 'runtime_dependency', 'model_approval',
              'input_output_scope', 'evidence', 'timeout_temp', 'context',
              'ownership', 'failure', 'other'}
SCOPE_GRANTS = {'read_only_paths':'read_grants', 'callee_write_paths':'callee_write_grants',
                'lead_write_paths':'lead_write_grants'}
IDENTITY = ('task_id', 'revision', 'target_agent_id', 'parent_plan')
FAILURE_POLICY = 'report_and_stop_affected_work_without_substitution'


class Refused(ValueError):
    def __init__(self, code):
        self.code = code  # Only constants from the checks below, never input values.


def need(ok, code='INVALID_FIELDS'):
    if not ok:
        raise Refused(code)


def fields(value, required, optional=()):
    need(isinstance(value, dict) and set(required) <= set(value)
         and set(value) <= set(required) | set(optional))


def text(value):
    need(isinstance(value, str) and bool(value.strip()), 'TEXT_REQUIRED')


def strings(value, nonempty=True):
    need(isinstance(value, list) and (not nonempty or bool(value)))
    for item in value:
        text(item)
    need(len(set(value)) == len(value), 'DUPLICATE_VALUE')


def rows(value, key, nonempty=True):
    need(isinstance(value, list) and (not nonempty or bool(value)))
    ids = set()
    for item in value:
        need(isinstance(item, dict) and key in item)
        text(item[key]); need(item[key] not in ids, 'DUPLICATE_ID'); ids.add(item[key])
    return ids


def sha(value):
    need(isinstance(value, str) and hex_digest(value), 'INVALID_EXPECTED_HASH')


def validate_intent(value):
    fields(value, ('intent_version', *IDENTITY, 'instruction_sources',
                   'read_grants', 'callee_write_grants', 'lead_write_grants', 'runtime'))
    need(value['intent_version'] == 'lead-task-authority-intent/v1', 'INTENT_VERSION')
    text(value['task_id']); text(value['target_agent_id'])
    need(type(value['revision']) is int and value['revision'] >= 1, 'REVISION_INVALID')
    fields(value['parent_plan'], ('path','revision')); normalized(value['parent_plan']['path'])
    need(len(value['parent_plan']['path']) > 1, 'PLAN_PATH_INVALID')
    need(type(value['parent_plan']['revision']) is int and value['parent_plan']['revision'] >= 1, 'REVISION_INVALID')
    source = value['instruction_sources']
    need(isinstance(source, list) and len(source) == 1, 'SINGLE_SOURCE_REQUIRED')
    fields(source[0], ('source_id','text')); text(source[0]['source_id']); text(source[0]['text'])
    for key in SCOPE_GRANTS.values():
        grants = value[key]
        need(isinstance(grants, list) and len(grants) <= 128)
        seen = set()
        for grant in grants:
            fields(grant, ('path','kind')); normalized(grant['path'])
            need(grant['kind'] in ('file','directory'))
            item = (grant['path'], grant['kind']); need(item not in seen, 'DUPLICATE_VALUE'); seen.add(item)
    runtime = value['runtime']
    fields(runtime, ('python_executable','environment_prefix','lock_sha256'), ('lock_path',))
    for key in ('python_executable','environment_prefix'):
        normalized(runtime[key])
    if 'lock_path' in runtime:
        normalized(runtime['lock_path'])
    sha(runtime['lock_sha256'])  # Identity data only: no interpreter discovery/execution.


def validate_scope(scope, intent, spec_path):
    fields(scope, SCOPE_GRANTS)
    for key, grants in SCOPE_GRANTS.items():
        strings(scope[key])  # All three existing TaskSpec arrays have minItems=1.
        for path in scope[key]:
            normalized(path)
            need(allowed(path, intent[grants]), 'SCOPE_NOT_AUTHORIZED')
    reads, callee, lead = (scope[k] for k in SCOPE_GRANTS)
    overlap = lambda a,b: contains(a,b) or contains(b,a)
    need(not any(overlap(a,b) for a in callee for b in lead)
         and not any(overlap(a,b) for a in reads for b in callee+lead), 'SCOPE_OVERLAP')
    need(allowed(spec_path, intent['read_grants'])
         and any(contains(p,spec_path) for p in reads), 'SPEC_READ_SCOPE_REQUIRED')


def validate_body(spec, intent, spec_path, reader):
    """Dedicated checks for our current inline-source subset, not a Schema engine."""
    fields(spec, ('spec_version', *IDENTITY, 'purpose', 'instruction_sources', 'hard_constraints',
                  'resources', 'io_scope', 'acceptance_criteria', 'failure_policy', 'delivery_requirements'))
    need(spec['spec_version'] == 'lead-delegation-task/v1')
    # Compare types as well: Python bool must never equal a revision integer.
    fields(spec['parent_plan'], ('path','revision'))
    need(type(spec['revision']) is int and type(spec['parent_plan']['revision']) is int,
         'REVISION_INVALID')
    need(all(spec[k] == intent[k] for k in IDENTITY), 'IDENTITY_MISMATCH')
    text(spec['purpose'])
    sources = spec['instruction_sources']; need(isinstance(sources,list) and len(sources)==1)
    source = sources[0]; fields(source, ('source_id','text','sha256'))
    original = intent['instruction_sources'][0]
    need(source['source_id'] == original['source_id'] and source['text'] == original['text'], 'SOURCE_MISMATCH')
    sha(source['sha256']); need(digest(source['text'].encode('utf8')) == source['sha256'], 'SOURCE_HASH_MISMATCH')
    constraints = rows(spec['hard_constraints'], 'constraint_id')
    for item in spec['hard_constraints']:
        fields(item, ('constraint_id','category','source_id','source_quote','applies_to','verification'))
        need(item['category'] in CATEGORIES and item['applies_to'] in ('lead','callee','both'))
        text(item['source_quote']); text(item['verification'])
        need(item['source_id'] == original['source_id'] and item['source_quote'] in original['text'], 'QUOTE_MISMATCH')
    rows(spec['acceptance_criteria'], 'criterion_id'); covered = set()
    for item in spec['acceptance_criteria']:
        fields(item, ('criterion_id','constraint_ids','text')); text(item['text']); strings(item['constraint_ids'])
        need(set(item['constraint_ids']) <= constraints, 'CONSTRAINT_REFERENCE_MISSING')
        covered.update(item['constraint_ids'])
    need(covered == constraints, 'ACCEPTANCE_COVERAGE_REQUIRED')
    need(spec['failure_policy'] == FAILURE_POLICY); strings(spec['delivery_requirements'])
    validate_scope(spec['io_scope'], intent, spec_path)
    rows(spec['resources'], 'resource_id', nonempty=False)
    for item in spec['resources']:
        fields(item, ('resource_id','constraint_ids','kind','path','sha256'), ('version',))
        strings(item['constraint_ids']); need(set(item['constraint_ids']) <= constraints, 'CONSTRAINT_REFERENCE_MISSING')
        need(item['kind'] in KINDS); sha(item['sha256']); normalized(item['path'])
        if 'version' in item: text(item['version'])
        need(any(contains(p,item['path']) for p in spec['io_scope']['read_only_paths']), 'RESOURCE_READ_SCOPE_REQUIRED')
        raw = reader.read(item['path'], intent['read_grants'])[0]  # 4 MiB original binary bytes; never decode.
        need(digest(raw) == item['sha256'], 'RESOURCE_HASH_MISMATCH')


def extract_quote(request, quote):
    fields(quote, ('text',), ('line_start','line_end')); text(quote['text'])
    need(('line_start' in quote) == ('line_end' in quote), 'QUOTE_RANGE_INVALID')
    start, end = 0, len(request)
    if 'line_start' in quote:
        lines = request.splitlines(keepends=True)
        a,b = quote['line_start'],quote['line_end']
        need(type(a) is int and type(b) is int and 1 <= a <= b <= len(lines), 'QUOTE_RANGE_INVALID')
        start,end = sum(map(len,lines[:a-1])),sum(map(len,lines[:b]))
    first = request.find(quote['text'],start,end)
    need(first >= 0, 'QUOTE_NOT_FOUND')
    need(request.find(quote['text'],first+1,end) < 0, 'QUOTE_AMBIGUOUS')
    finish = first+len(quote['text'])
    return {'start_utf8_byte':len(request[:first].encode('utf8')),
            'end_utf8_byte':len(request[:finish].encode('utf8'))}


def mapped_spec(definition, intent, request):
    fields(definition, ('role','purpose','role_task','io_scope','resources','hard_constraints',
                        'acceptance_criteria','failure_policy','delivery_requirements'))
    need(definition['role'] in ('lead','requirements','commercial','visual','evidence'))
    text(definition['role_task'])
    source = intent['instruction_sources'][0]
    need(request == source['text'], 'SOURCE_MISMATCH')
    spec = {k:copy.deepcopy(intent[k]) for k in IDENTITY}
    spec.update(spec_version='lead-delegation-task/v1', instruction_sources=[dict(source,sha256=digest(request.encode('utf8')))])
    for key in ('purpose','io_scope','acceptance_criteria','failure_policy','delivery_requirements'):
        spec[key] = copy.deepcopy(definition[key])
    rows(definition['hard_constraints'],'constraint_id'); mapped=[]; spec['hard_constraints']=[]
    for item in definition['hard_constraints']:
        fields(item, ('constraint_id','category','source_id','quote','applies_to','verification'))
        span=extract_quote(request,item['quote'])
        value={k:v for k,v in item.items() if k!='quote'}; value['source_quote']=item['quote']['text']
        spec['hard_constraints'].append(value)
        mapped.append(dict(span,constraint_id=item['constraint_id'],source_id=item['source_id']))
    rows(definition['resources'],'resource_id',nonempty=False); spec['resources']=[]
    for item in definition['resources']:
        fields(item, ('resource_id','constraint_ids','kind','path','expected_sha256'), ('version',))
        value={k:v for k,v in item.items() if k!='expected_sha256'}; value['sha256']=item['expected_sha256']
        spec['resources'].append(value)
    assignment={k:copy.deepcopy(spec[k]) for k in ('io_scope','resources','parent_plan','delivery_requirements')}
    assignment['role_task']=definition['role_task']
    return spec,assignment,mapped


def encoded(value):
    raw=(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode('utf8')
    need(len(raw)<=LIMIT,'OUTPUT_TOO_LARGE'); return raw


def publish(output, values, reader):
    """Exclusive new files, retaining descriptors until final bytes/identity checks."""
    fd=directory(output); opened=[]
    def verify():
        now=directory(output)
        try:
            a,b=os.fstat(fd),os.fstat(now)
            need((a.st_dev,a.st_ino)==(b.st_dev,b.st_ino),'OUTPUT_DIRECTORY_CHANGED')
        finally: os.close(now)
        for name,out,raw in opened:
            a,b=os.fstat(out),os.stat(name,dir_fd=fd,follow_symlinks=False)
            identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_nlink)
            need(stat.S_ISREG(b.st_mode) and a.st_nlink==1 and identity(a)==identity(b),'OUTPUT_CHANGED')
            os.lseek(out,0,os.SEEK_SET); observed=b''
            while len(observed)<=len(raw):
                part=os.read(out,min(65536,len(raw)+1-len(observed)))
                if not part:break
                observed+=part
            need(observed==raw,'OUTPUT_CHANGED')
    try:
        reader.stable()
        for name,raw in values.items():
            verify()
            out=os.open(name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
            opened.append((name,out,raw));offset=0
            while offset<len(raw):
                n=os.write(out,raw[offset:]);need(n>0,'OUTPUT_WRITE_FAILED');offset+=n
            os.fsync(out);verify()
        os.fsync(fd);reader.stable();verify()
    finally:
        for _,out,_ in opened:os.close(out)
        os.close(fd)


def run(args):
    reader=Reader()
    def read(pair, grants=None):
        path,expected=pair;sha(expected)
        raw=reader.read(path,grants,limit=LIMIT)[0]
        need(digest(raw)==expected,'HASH_MISMATCH')
        return raw
    intent_raw=read(args.authority_intent);intent=parse(decode(intent_raw));validate_intent(intent)
    normalized(args.output_directory)
    name=args.output_name
    need(isinstance(name,str) and 1<=len(name)<=80 and name[0].isalnum()
         and all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name),'OUTPUT_NAME_INVALID')
    # Existing directory is required; opening does not confer construction authority.
    fd=directory(args.output_directory);os.close(fd)
    if args.command=='draft':
        request_raw=read(args.request);request=decode(request_raw)
        definition_raw=read(args.definition);definition=parse(decode(definition_raw))
        spec_path=args.output_directory+'/'+name+'.spec.json'
        spec,assignment,mapping=mapped_spec(definition,intent,request)
        validate_body(spec,intent,spec_path,reader)
        source_map={'semantic_completeness':'not_established','authorship':'not_authenticated',
                    'source_sha256':digest(request_raw),'quotes':mapping,
                    'input_sha256':{'request':digest(request_raw),'authority_intent':digest(intent_raw),
                                    'definition':digest(definition_raw)}}
        values={name+'.spec.json':encoded(spec),name+'.assignment.json':encoded(assignment),
                name+'.source-map.json':encoded(source_map)}
        receipt={'status':'draft_only','semantic_completeness':'not_established','authorship':'not_authenticated',
                 'files':{k:{'sha256':digest(v),'byte_length':len(v)} for k,v in values.items()}}
        values[name+'.draft-manifest.json']=encoded(receipt)
    else:
        spec_raw=read(args.spec,intent['read_grants']);spec=parse(decode(spec_raw))
        validate_body(spec,intent,args.spec[0],reader)
        authority={k:copy.deepcopy(v) for k,v in intent.items() if k!='intent_version'}
        authority.update(authority_version='lead-task-spec-authority/v1',spec_sha256=digest(spec_raw))
        values={name+'.authority.json':encoded(authority)}
        receipt={'status':'authority_bound_only','semantic_completeness':'not_established',
                 'authorship':'not_authenticated','spec_sha256':digest(spec_raw),
                 'files':{k:{'sha256':digest(v),'byte_length':len(v)} for k,v in values.items()}}
    publish(args.output_directory,values,reader)
    return receipt


class Parser(argparse.ArgumentParser):
    def error(self,message):raise Refused('ARGUMENTS_INVALID')


def main():
    parser=Parser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    for command in ('draft','bind-authority'):
        p=commands.add_parser(command)
        for name in (('request','authority-intent','definition') if command=='draft' else ('authority-intent','spec')):
            p.add_argument('--'+name,nargs=2,required=True,metavar=('PATH','EXPECTED_SHA256'))
        p.add_argument('--output-directory',required=True);p.add_argument('--output-name',required=True)
    try:
        print(json.dumps(run(parser.parse_args()),ensure_ascii=False));return 0
    except Refused as error:code=error.code
    except ReadRefused as error:code=error.code  # Fixed labels from our adjacent owned reader only.
    except FileExistsError:code='OUTPUT_EXISTS'
    except (ValueError,OSError,KeyError,TypeError,RecursionError,UnicodeError):code='INPUT_OR_IO_REFUSED'
    print(json.dumps({'status':'refused','code':code,'partial_output_policy':'preserved_if_created'}),file=sys.stderr)
    return 2


if __name__=='__main__':sys.exit(main())
