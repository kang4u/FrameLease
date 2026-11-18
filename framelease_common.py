"""Shared provenance/statistics/persistence; deliberately no experiment algorithms."""
from __future__ import annotations
import argparse, contextlib, csv, hashlib, json, os, platform, random, statistics, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SCHEMA=2
STATES=('NOT_STARTED','RUNNING','COMPLETED','PARTIAL','BLOCKED','FAILED')
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def artifact_path(value):
    """Resolve relocated evidence without changing its stored identity or bytes."""
    text=str(value).replace('\\','/')
    if os.name!='nt' and text.lower().startswith('d:/dac/'):
        relative=Path(text[len('D:/DAC/'):])
        if '..' in relative.parts:raise ValueError('Artifact path escapes project root')
        return ROOT/relative
    return Path(text) if os.name!='nt' else Path(value)
def file_hash(p):
    h=hashlib.sha256()
    with artifact_path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def seed_for(*parts):return int(digest(parts)[:16],16)

def observation_seed(base_seed,record):
    """Relative capture tick pairs model randomness across server restarts."""
    key=record.get('relative_capture_tick')
    if key is None:key=record['image_sha256']
    return seed_for('framelease_observation_v2',base_seed,key)%(2**31)
def read_json(p):return json.loads(artifact_path(p).read_text(encoding='utf-8-sig'))
def atomic_json(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
    with t.open('x',encoding='utf-8') as f:
        f.write(canonical(x)+'\n');f.flush();os.fsync(f.fileno())
    os.replace(t,p)
def write_csv(p,rows):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);rows=list(rows)
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def quantile(x,q):
    if not x:return None
    x=sorted(x);a=(len(x)-1)*q;lo=int(a);hi=min(lo+1,len(x)-1)
    return x[lo]+(x[hi]-x[lo])*(a-lo)
def bootstrap_mean(values,seed=0,n=1000):
    values=list(values)
    if not values:return {'n':0,'mean':None,'ci95_low':None,'ci95_high':None}
    rng=random.Random(seed);means=[statistics.mean(rng.choices(values,k=len(values))) for _ in range(n)]
    return {'n':len(values),'mean':statistics.mean(values),'ci95_low':quantile(means,.025),'ci95_high':quantile(means,.975)}
@contextlib.contextmanager
def writer_lock(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);p=root/'.writer.lock';token=uuid.uuid4().hex
    fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    with os.fdopen(fd,'w') as f:f.write(canonical({'pid':os.getpid(),'token':token,'created':now()}))
    primary=None
    try:yield
    except BaseException as e:primary=e;raise
    finally:
        try:
            if read_json(p).get('token')==token:p.unlink()
        except BaseException:
            if primary is None:raise
def environment():
    return {'python':sys.version,'executable':sys.executable,'platform':platform.platform(),
            'conda':(Path(sys.prefix)/'conda-meta').is_dir(),'clock':'perf_counter_ns within process; UTC metadata only'}
def require_conda():
    if not (Path(sys.prefix)/'conda-meta').is_dir():raise RuntimeError('Use isolated project Conda, not venv/system Python')
def parser(stage,modes):
    p=argparse.ArgumentParser(description=stage+' independent FrameLease experiment')
    p.add_argument('--mode',choices=modes,default=modes[0]);p.add_argument('--seed',type=int,default=11)
    p.add_argument('--output-dir',type=Path,default=ROOT/'outputs'/stage.split('_')[0])
    p.add_argument('--resume',action='store_true');p.add_argument('--dry-run',action='store_true');p.add_argument('--quick',action='store_true');p.add_argument('--config',type=Path)
    return p
def dry_plan(args,tasks):
    if not args.dry_run:return False
    print(canonical({'status':'NOT_STARTED','mode':args.mode,'tasks':tasks,'written_files':0,'executed':False}));return True
class StageRun:
    """Invocation ledger only; stages enumerate, execute and analyze their own work."""
    def __init__(self,stage,args,config,evidence,dependencies=()):
        require_conda();self.root=args.output_dir;self.stage=stage;self.args=args
        sources=[ROOT/(stage+'.py'),ROOT/'framelease_common.py',*[Path(x) for x in dependencies]]
        self.identity={'schema':SCHEMA,'stage':stage,'config':config,'seed':args.seed,'code':{str(p):file_hash(p) for p in sources if p.is_file()},'environment':environment()}
        self.id=digest(self.identity);self.path=self.root/'runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8])
        for name in ('raw','metrics','figures','logs'):(self.path/name).mkdir(parents=True,exist_ok=False)
        # Freeze source bytes before execution; later edits cannot erase reproducibility.
        (self.path/'source').mkdir()
        for p in sources:
            if p.is_file():(self.path/'source'/(p.name+'.txt')).write_bytes(p.read_bytes())
        self.state={'schema':SCHEMA,'stage':stage,'mode':args.mode,'identity':self.identity,'identity_sha256':self.id,'evidence_type':evidence,'status':'RUNNING','acceptance_status':'PARTIAL','created':now(),'run_dir':str(self.path),'tasks':[],'blockers':[],'artifacts':{}}
        import subprocess
        try:
            self.state['git']={'commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),'tracked_changes':subprocess.check_output(['git','-C',str(ROOT),'status','--short','--untracked-files=no'],text=True).strip(),'source_snapshot_directory':'source'}
        except (OSError,subprocess.CalledProcessError):self.state['git']={'status':'UNAVAILABLE','source_snapshot_directory':'source'}
        atomic_json(self.path/'config.json',config);self.save()
    def save(self):atomic_json(self.path/'manifest.json',self.state)
    def log(self,event,**data):
        with (self.path/'logs/events.jsonl').open('a',encoding='utf-8') as f:f.write(canonical({'utc':now(),'monotonic_ns':time.perf_counter_ns(),'event':event,**data})+'\n');f.flush()
    def cache_path(self,task):return self.root/'raw'/self.id/(digest(task)+'.json')
    def cached(self,task):
        p=self.cache_path(task)
        if not self.args.resume or not p.exists():return None
        x=read_json(p)
        if x.get('identity')!=self.identity or x.get('task')!=task or x.get('sha256')!=digest(x.get('data')) or x.get('status')!='COMPLETED':raise ValueError('Cache identity/content mismatch: '+str(p))
        return x['data']
    def record(self,task,data,status='COMPLETED',reason=None):
        if status not in STATES:raise ValueError(status)
        if status=='COMPLETED':
            p=self.cache_path(task);payload={'schema':SCHEMA,'status':status,'identity':self.identity,'task':task,'data':data,'sha256':digest(data)}
            if p.exists() and read_json(p)!=payload:p=self.path/'raw'/(digest(task)+'.json')
            atomic_json(p,payload);item={'task':task,'status':status,'path':str(p),'sha256':file_hash(p)}
        else:item={'task':task,'status':status,'reason':reason,'data':data}
        self.state['tasks'].append(item);self.save();return item
    def finish(self,status,report,blockers=(),acceptance=None):
        self.state.update(status=status,acceptance_status=acceptance or status,finished=now(),blockers=list(blockers))
        (self.path/'report.md').write_text(report,encoding='utf-8')
        self.state['artifacts']={str(p.relative_to(self.path)):file_hash(p) for p in self.path.rglob('*') if p.is_file() and p.name!='manifest.json'}
        self.save();atomic_json(self.root/'manifest.json',self.state);atomic_json(self.root/'config.json',self.identity['config'])
        (self.root/'report.md').write_text(report+'\n\nInvocation: '+str(self.path)+'\n',encoding='utf-8')
        print(canonical({'stage':self.stage,'status':status,'acceptance_status':self.state['acceptance_status'],'run_dir':str(self.path),'tasks':len(self.state['tasks']),'blockers':list(blockers)}))
        return 0 if status=='COMPLETED' else (1 if status=='FAILED' else 2)
def verified_manifest(path):
    m=read_json(path);base=artifact_path(m['run_dir'])
    if digest(m['identity'])!=m['identity_sha256']:raise ValueError('Manifest identity corrupted')
    for rel,h in m['artifacts'].items():
        if file_hash(base/rel)!=h:raise ValueError('Corrupt artifact: '+str(base/rel))
    for t in m['tasks']:
        if t['status']=='COMPLETED' and file_hash(t['path'])!=t['sha256']:raise ValueError('Corrupt task cache')
    return m
def saved_data(m):
    for t in m['tasks']:
        if t['status']=='COMPLETED':
            e=read_json(t['path'])
            if e['sha256']!=digest(e['data']):raise ValueError('Result payload hash mismatch')
            yield e['task'],e['data']
def figure_save(fig,base):
    base=Path(base);base.parent.mkdir(parents=True,exist_ok=True)
    for ext in ('png','pdf','svg'):fig.savefig(str(base)+'.'+ext,bbox_inches='tight',dpi=220)


ROUTE_A_GATES={1:'official_native_closed_loop',2:'legal_fast_candidate',3:'progressive_state_reuse',4:'measured_refinement_benefit',5:'online_avl',6:'anytime_runtime',7:'paired_crossover'}
ROUTE_A_EVIDENCE_TYPES={1:{'REAL_VLA','CARLA_CLOSED_LOOP'},2:{'REAL_VLA','REAL_GPU'},3:{'REAL_VLA','REAL_GPU'},4:{'REAL_VLA','REAL_GPU'},5:{'DEPLOYMENT_PERCEPTION','ONLINE_AVL','CARLA_CLOSED_LOOP'},6:{'REAL_VLA','REAL_GPU','ANYTIME_RUNTIME'},7:{'REAL_VLA','REAL_GPU','CARLA_CLOSED_LOOP','PAIRED_CROSSOVER'}}

def route_a_gate_evidence(path=None):
    """A status string cannot promote a gate without intact, same-backend evidence.
    Gates are sequential; historical ReCog/WAM evidence cannot authorize Route A.
    """
    path=Path(path or ROOT/'audits/route_a/acceptance.json')
    state=read_json(path) if path.exists() else {'backend':'UniDriveVLA','gates':{}}
    rows=[];prefix_ok=True
    for number,name in ROUTE_A_GATES.items():
        entry=state.get('gates',{}).get(str(number),{});refs=entry.get('evidence',[]);errors=[]
        declared=entry.get('status','BLOCKED')
        for ref in refs:
            try:
                p=Path(ref['manifest']);m=verified_manifest(p)
                if file_hash(p)!=ref['sha256']:errors.append('manifest identity changed')
                if m.get('status')!='COMPLETED' or m.get('acceptance_status')!='COMPLETED':errors.append('research evidence is not accepted COMPLETED')
                if not ROUTE_A_EVIDENCE_TYPES[number].issubset(set(m.get('evidence_type',[]))):errors.append('required real experiment evidence types absent')
                if m['identity']['config'].get('backend')!=state['backend']:errors.append('backend mismatch')
                for t in m['tasks']:
                    if t['status']=='COMPLETED':
                        payload=read_json(t['path'])
                        if payload.get('identity')!=m['identity'] or payload.get('task')!=t['task']:errors.append('task identity mismatch')
                if not any(task.get('kind')=='route_a_gate_result' and task.get('gate')==number and data.get('gate')==number and data.get('backend')==state['backend'] and data.get('passed') is True for task,data in saved_data(m)):errors.append('no measured passing gate result')
            except (OSError,ValueError,KeyError,TypeError) as e:errors.append(repr(e))
        passed=prefix_ok and declared=='COMPLETED' and bool(refs) and not errors
        reason=entry.get('reason','No measured gate evidence')
        if declared=='COMPLETED' and not passed:reason='Unverified gate promotion rejected: '+('; '.join(errors) or 'missing evidence or upstream gate')
        rows.append({'gate':number,'name':name,'status':'COMPLETED' if passed else 'BLOCKED','reason':reason,'evidence':refs,'verification_errors':errors})
        prefix_ok=passed
    return {'backend':state['backend'],'gates':rows,'all_passed':all(r['status']=='COMPLETED' for r in rows),'formal_tables':'NOT_AVAILABLE','formal_tables_reason':'A separate verified multi-method matrix and statistical coverage are required; prerequisite gates alone do not publish Table 1/2','acceptance_sha256':file_hash(path) if path.exists() else None}

def route_a_gate_check(stage,args,required):
    if dry_plan(args,[{'mode':'route-a-gate','required_gates':required}]):return 0
    evidence=route_a_gate_evidence();run=StageRun(stage,args,{'mode':'route-a-gate','backend':evidence['backend'],'required_gates':required,'acceptance_sha256':evidence['acceptance_sha256']},['PREREQUISITE_AUDIT'])
    run.record({'kind':'verified_route_a_gates'},evidence);blocked=[r['name']+': '+r['reason'] for r in evidence['gates'] if r['gate'] in required and r['status']!='COMPLETED']
    atomic_json(run.path/'metrics/gates.json',evidence)
    return run.finish('BLOCKED' if blocked else 'COMPLETED',canonical(evidence),blocked,acceptance='BLOCKED' if blocked else 'PREREQUISITES_ONLY')

