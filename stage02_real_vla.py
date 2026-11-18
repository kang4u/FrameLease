"""Real ReCogDrive-Base-IL inference and audited DDIM clean-candidate refinement.
Missing weights/input/platform dependencies are BLOCKED, never simulated.
"""
from __future__ import annotations
import dataclasses, math, subprocess, sys, time, traceback, types
from pathlib import Path
from framelease_common import *
REPO=ROOT/'third_party/recogdrive'
sys.path.insert(0,str(ROOT/'third_party/nuplan-devkit'))
class DependencyBlocked(RuntimeError):pass

def source_audit():
    import ast
    files={};functions={}
    for name in ('recogdrive_agent.py','recogdrive_backbone.py','recogdrive_diffusion_planner.py','recogdrive_features.py','recogdrive_dit.py'):
        p=REPO/'navsim/agents/recogdrive'/name;s=p.read_text(encoding='utf-8');tree=ast.parse(s)
        files[name]=file_hash(p);functions[name]=[{'name':n.name,'line':n.lineno} for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
    alt=ROOT/'third_party/WAM-Flow'
    for p in (REPO/'navsim/agents/recogdrive').rglob('*.py'):
        key=str(p.relative_to(REPO/'navsim/agents/recogdrive'));files.setdefault(key,file_hash(p))
    wam=[{'path':str(p.relative_to(alt)),'sha256':file_hash(p)} for p in alt.rglob('*.py') if 'sampl' in p.name or 'agent' in p.name][:30]
    return {'source_sha256':files,'functions':functions,'clean_candidate':'p_mean_variance third return x_recon then denorm_odo; noisy sample_chain never executed as a trajectory',
            'cooperative_boundary':'between DDIM steps after CUDA synchronization; no arbitrary kernel preemption',
            'native_resume_api':False,'instrumented_resume_requires_equivalence':True,'wam_source_files':wam,
            'wam_runtime':'See separately identified wam-audit evidence; source audit alone establishes no runtime capability',
            'official_source_revision':subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()}

def validated_input(path,require_planner=False):
    if not path.is_file():raise DependencyBlocked('Complete real input manifest missing: '+str(path))
    data=read_json(path)
    genuine_log=data.get('synthetic') is False and data.get('source_type','REAL_DRIVING_LOG')=='REAL_DRIVING_LOG'
    actual_carla=data.get('source_type')=='CARLA_SENSOR_RECORDING' and data.get('fabricated') is False
    if not (genuine_log or actual_carla):raise ValueError('Require provenance-backed real log or explicitly labeled actual CARLA sensor recording; fabricated input rejected')
    if not data.get('source') or not data.get('records'):raise ValueError('Missing source and actual records')
    for r in data['records']:
        image=artifact_path(r['image_path'])
        if not image.is_absolute():image=path.parent/image
        if file_hash(image)!=r['image_sha256']:raise ValueError('Camera image hash mismatch')
        r['image_path']=str(image)
        hist=r['ego_history']
        if len(hist)!=4:raise ValueError('Official interface requires four ego history states')
        for e in hist:
            for key,size in (('pose',3),('velocity',2),('acceleration',2),('driving_command',4)):
                if len(e[key])!=size or not all(math.isfinite(float(v)) for v in e[key]):raise ValueError('Invalid '+key)
            if any(v not in (0,1) for v in e['driving_command']) or sum(e['driving_command'])!=1:raise ValueError('Navigation command must be one-hot left/straight/right/unknown')
            if e['driving_command'][3]:raise DependencyBlocked('Official ReCogDrive prompt maps only left/straight/right; unknown command is not supported by this inference path')
        times=[e['capture_s'] for e in hist]
        if any(b<=a for a,b in zip(times,times[1:])) or abs(times[-1]-r['capture_s'])>1e-6:raise ValueError('History and camera time mismatch')
        if r.get('coordinate_frame')!='ego_local_xy_heading_radians':raise ValueError('History frame must match official local convention')
        if require_planner:
            actual=sum(len(hist[-1][k]) for k in ('driving_command','velocity','acceleration'))
            if actual!=8:raise DependencyBlocked('Official trained planner requires 8 status features; supplied '+str(actual)+'. Eighth signal semantics must be established from official data, not zero padded.')
    return data

def trusted_planner_checkpoint(path):
    import torch
    expected='4569221da6962d4e26d21a463cd70c06a7ad4d76654943fb3870086f43bdb443'
    if file_hash(path)!=expected:raise DependencyBlocked('Planner checkpoint is not the audited official IL snapshot')
    # Official pickle carries OmegaConf metadata. Only this pinned, inspected archive is trusted.
    return torch.load(path,map_location='cpu',weights_only=False)['state_dict']

def validate_trajectory(array,max_speed=60,max_acceleration=20):
    import numpy as np
    a=np.asarray(array,dtype=float)
    if a.shape!=(8,3) or not np.isfinite(a).all():return {'valid':False,'reason':'shape/nonfinite'}
    speed=np.linalg.norm(np.diff(np.vstack([np.zeros((1,2)),a[:,:2]]),axis=0),axis=1)/.5
    accel=np.diff(speed)/.5
    valid=bool(np.max(speed)<=max_speed and (len(accel)==0 or np.max(np.abs(accel))<=max_acceleration))
    return {'valid':valid,'reason':'kinematic_screen_only' if valid else 'speed/acceleration_limit','max_speed_mps':float(np.max(speed)),'max_acceleration_mps2':float(np.max(np.abs(accel))),'collision_validated':False}

def candidate_validity(trajectory,steps,complete=True):
    """Independent statuses; numerical screening is not vehicle/road/safety acceptance."""
    start=time.perf_counter_ns();kin=validate_trajectory(trajectory)
    decoded=kin.get('reason')!='shape/nonfinite'
    levels={'decoded':'PASS' if decoded else 'FAIL','kinematic':'PASS' if kin['valid'] else 'FAIL',
            'control_executable':'NOT_EVALUATED','road_valid':'NOT_EVALUATED','dynamic_safe':'NOT_EVALUATED','closed_loop_valid':'NOT_EVALUATED'}
    return {'levels':levels,'plan_role':('FAST_CANDIDATE' if steps==3 else 'DEEP_CANDIDATE') if complete and steps in (3,5) else 'NON_EXECUTABLE_INTERMEDIATE',
            'complete_schedule':complete,'schedule_steps':steps,'diagnostic_admissible':bool(complete and steps in (3,5) and kin['valid']),
            'deployment_admissible':False,'kinematic_screen':kin,'validation_wall_ms':(time.perf_counter_ns()-start)/1e6}

def ddim_schedule_audit():
    import ast
    p=REPO/'navsim/agents/recogdrive/recogdrive_diffusion_planner.py';tree=ast.parse(p.read_text(encoding='utf8'))
    cfg=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DDIMConfig')
    n=next(ast.literal_eval(f.value) for f in cfg.body if isinstance(f,ast.AnnAssign) and f.target.id=='num_train_timesteps')
    schedules={str(k):list(reversed([i*(n//k) for i in range(k)])) for k in (3,5)}
    return {'source':str(p),'sha256':file_hash(p),'train_timesteps':n,'schedules':schedules,'direct_3_to_5_continuation':False,
            'reason':'Three-step and five-step DDIM schedules have different starting timesteps and transition coefficients; completed three-step x cannot continue as the five-step prefix.',
            'reusable':'VLM and feature/history/ego conditioning embeddings for exactly the same observation',
            'recompute':'All five denoising steps from identically seeded initial noise; no three-step denoising quantum counted as reused',
            'existing_resume_equivalence_scope':'Suspend/resume within one unchanged schedule only; not 3-to-5 refinement'}

class ReCogAdapter:
    def __init__(self,vlm,planner):
        import torch
        sys.path.insert(0,str(REPO))
        try:
            from navsim.agents.recogdrive.recogdrive_agent import ReCogDriveAgent
            from nuplan.planning.simulation.trajectory.trajectory_sampling import TrajectorySampling
        except ImportError as e:raise DependencyBlocked('Official Agent import: '+repr(e)) from e
        if not Path(vlm).is_dir() or not Path(planner).is_file():raise DependencyBlocked('Verified VLM snapshot and planner checkpoint required')
        self.torch=torch
        self.agent=ReCogDriveAgent(TrajectorySampling(time_horizon=4,interval_length=.5),vlm_path=str(vlm),checkpoint_path=str(planner),cache_mode=False,cache_hidden_state=False,dit_type='small',vlm_size='small',sampling_method='ddim')
        raw=trusted_planner_checkpoint(planner);state={k.removeprefix('agent.'):v for k,v in raw.items()}
        required={k:v for k,v in self.agent.named_parameters() if k.startswith('action_head.')}
        missing=[k for k,v in required.items() if k not in state or state[k].shape!=v.shape]
        if missing:raise DependencyBlocked('Planner trained-parameter coverage incomplete: '+repr(missing[:15]))
        self.agent.initialize();self.agent.eval()
        self.provenance={'planner_sha256':file_hash(planner),'vlm_config_sha256':file_hash(Path(vlm)/'config.json'),'planner_parameters_verified':len(required),'random_planner_parameters':0}
        self.builder=self.agent.get_feature_builders()[0]
    def features(self,record):
        ego=[types.SimpleNamespace(ego_pose=e['pose'],ego_velocity=e['velocity'],ego_acceleration=e['acceleration'],driving_command=e['driving_command']) for e in record['ego_history']]
        camera=types.SimpleNamespace(cam_f0=types.SimpleNamespace(image=record['image_path']))
        inp=types.SimpleNamespace(ego_statuses=ego,cameras=[camera])
        return {k:v.unsqueeze(0) for k,v in self.builder.compute_features(inp).items()}
    def infer(self,record,seed,capture_intermediate=True):
        torch=self.torch;torch.manual_seed(seed);torch.cuda.manual_seed_all(seed);torch.cuda.reset_peak_memory_stats()
        events=[];clean=[];head=self.agent.action_head;original=head.p_mean_variance;original_get=head.get_action;context={}
        def pmv(*a,**kw):
            st,en=torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True);t=time.perf_counter_ns();st.record();result=original(*a,**kw);en.record();en.synchronize()
            events.append({'kind':'denoising_quantum','index':len(clean),'cuda_ms':st.elapsed_time(en),'wall_ms':(time.perf_counter_ns()-t)/1e6})
            if capture_intermediate:
                decoded=head.denorm_odo(result[2]).detach().float().cpu().squeeze(0).numpy()
                clean.append({'index':len(clean),'trajectory':decoded.tolist(),'validation':validate_trajectory(decoded),'kind':'decoded_clean_x0'})
            return result
        def get_action(vl,action_input,*a,**kw):
            context.update(vl=vl.detach().clone(),action_input=action_input,rng_cpu=torch.get_rng_state(),rng_cuda=torch.cuda.get_rng_state())
            return original_get(vl,action_input,*a,**kw)
        times={}
        def hook_before(module,inputs):
            st=torch.cuda.Event(enable_timing=True);st.record();times['start']=(time.perf_counter_ns(),st)
        def hook_after(module,inputs,output):
            en=torch.cuda.Event(enable_timing=True);en.record();en.synchronize();t,st=times['start'];events.append({'kind':'vlm_encoding','cuda_ms':st.elapsed_time(en),'wall_ms':(time.perf_counter_ns()-t)/1e6})
        handles=[self.agent.backbone.register_forward_pre_hook(hook_before),self.agent.backbone.register_forward_hook(hook_after)]
        head.p_mean_variance=pmv;head.get_action=get_action
        try:
            features=self.features(record);torch.cuda.synchronize();t=time.perf_counter_ns()
            with torch.inference_mode():out=self.agent.forward(features)['pred_traj']
            torch.cuda.synchronize();wall=(time.perf_counter_ns()-t)/1e6;arr=out.float().cpu().squeeze(0).numpy()
        finally:
            head.p_mean_variance=original;head.get_action=original_get
            for h in handles:h.remove()
        return {'trajectory':arr.tolist(),'validation':validate_trajectory(arr),'events':events,'clean_candidates':clean,'wall_ms':wall,'peak_memory_bytes':torch.cuda.max_memory_allocated(),'checkpoint':self.provenance,'input_image_sha256':record['image_sha256'],'capture_s':record['capture_s']},context
    def start_job(self,record,seed,steps=None):
        """Encode once and retain actual trained-network DDIM state for cooperative scheduling."""
        torch=self.torch;head=self.agent.action_head;context={};original=head.get_action
        if steps is not None:
            if steps not in (3,5):raise ValueError('Legal jobs require a complete 3/5-step schedule')
            head.config.num_inference_steps=steps;head._init_ddim_sampler(head.config.ddim_cfg);head.cuda()
        def capture(vl,action_input,*a,**kw):
            context.update(vl=vl,action_input=action_input)
            return {} # Internal conditioning capture only; no trajectory is returned or fabricated.
        head.get_action=capture;start=time.perf_counter_ns();a,b=torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True);a.record()
        try:
            with torch.inference_mode():
                self.agent.forward(self.features(record));vl=head.feature_encoder(context['vl']);action=context['action_input'];hist=head.his_traj_encoder(action.his_traj.unsqueeze(1)).repeat(1,head.config.action_horizon,1);ego=head.ego_status_encoder(action.status_feature)
                torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
                x=torch.randn((vl.shape[0],head.config.action_horizon,head.config.action_dim),device=vl.device,dtype=vl.dtype)
                rng=torch.cuda.get_rng_state()
            b.record();b.synchronize()
        finally:head.get_action=original
        return {'vl':vl,'hist':hist,'ego':ego,'x':x,'rng':rng,'depth':0,'record':record,'encode_wall_s':(time.perf_counter_ns()-start)/1e9,'encode_cuda_ms':a.elapsed_time(b),'seed':seed,'schedule_steps':head.ddim_steps,'initial_x':x.clone(),'initial_rng':rng.clone(),'conditioning_reused':False}
    def restart_deep(self,fast_job):
        if fast_job['schedule_steps']!=3 or fast_job['depth']!=3:raise ValueError('Requires completed legal Fast plan')
        return {**fast_job,'x':fast_job['initial_x'].clone(),'rng':fast_job['initial_rng'].clone(),'depth':0,'schedule_steps':5,'conditioning_reused':True,'encode_wall_s':0.,'encode_cuda_ms':0.,'denoising_quanta_reused':0}
    def step_job(self,job):
        torch=self.torch;head=self.agent.action_head;i=job['depth']
        steps=job.get('schedule_steps',head.ddim_steps)
        if head.ddim_steps!=steps:head.config.num_inference_steps=steps;head._init_ddim_sampler(head.config.ddim_cfg);head.cuda()
        if i>=head.ddim_steps:raise ValueError('Completed job cannot refine further')
        a,b=torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True);start=time.perf_counter_ns();a.record()
        with torch.inference_mode():
            torch.cuda.set_rng_state(job['rng']);x=job['x'];t=head.make_timesteps(x.shape[0],head.ddim_t[i],x.device);idx=head.make_timesteps(x.shape[0],i,x.device)
            mean,logvar,clean=head.p_mean_variance(x,t,idx,job['vl'],job['hist'],job['ego'],False)
            std=torch.exp(.5*logvar).to(x.dtype).clamp(min=getattr(head,'eval_min_sampling_denoising_std',.0001));noise=torch.randn_like(x).clamp_(-getattr(head,'eval_randn_clip_value',1),getattr(head,'eval_randn_clip_value',1))
            job['x']=mean+std*noise;job['rng']=torch.cuda.get_rng_state();job['depth']+=1
            candidate=clean
            if job['depth']==head.ddim_steps:
                clip=getattr(head,'final_action_clip_value',1.)
                candidate=job['x'].clamp(-clip,clip) if clip is not None else job['x']
            trajectory=head.denorm_odo(candidate).detach().float().cpu().squeeze(0).numpy()
        b.record();b.synchronize()
        return {'depth':job['depth'],'schedule_steps':steps,'trajectory':trajectory.tolist(),'validation':validate_trajectory(trajectory),'validity':candidate_validity(trajectory,steps,job['depth']==steps),'kind':'official_final' if job['depth']==head.ddim_steps else 'decoded_clean_x0','wall_s':(time.perf_counter_ns()-start)/1e9,'cuda_ms':a.elapsed_time(b),'noisy_state_executed':False}

    def refinement_equivalence(self,context,reference):
        torch=self.torch;head=self.agent.action_head;torch.set_rng_state(context['rng_cpu']);torch.cuda.set_rng_state(context['rng_cuda'])
        action=context['action_input'];steps=[]
        with torch.inference_mode():
            vl=head.feature_encoder(context['vl']);hist=head.his_traj_encoder(action.his_traj.unsqueeze(1)).repeat(1,head.config.action_horizon,1);ego=head.ego_status_encoder(action.status_feature)
            x=torch.randn((vl.shape[0],head.config.action_horizon,head.config.action_dim),device=vl.device,dtype=vl.dtype)
            split=max(1,head.ddim_steps//2);snapshot=None
            def quantum(x,i):
                t=head.make_timesteps(x.shape[0],head.ddim_t[i],x.device);idx=head.make_timesteps(x.shape[0],i,x.device)
                mean,logvar,clean=head.p_mean_variance(x,t,idx,vl,hist,ego,False)
                std=torch.exp(.5*logvar).to(x.dtype).clamp(min=getattr(head,'eval_min_sampling_denoising_std',.0001))
                noise=torch.randn_like(x).clamp_(-getattr(head,'eval_randn_clip_value',1),getattr(head,'eval_randn_clip_value',1))
                return mean+std*noise,head.denorm_odo(clean)
            for i in range(head.ddim_steps):
                start=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True);start.record();x,clean=quantum(x,i);end.record();end.synchronize()
                steps.append({'index':i,'cuda_ms':start.elapsed_time(end),'candidate':clean.float().cpu().tolist()})
                if i+1==split:snapshot=(x.clone(),torch.cuda.get_rng_state())
            clip=getattr(head,'final_action_clip_value',1.)
            final=head.denorm_odo(x.clamp(-clip,clip) if clip is not None else x)
            resumed=snapshot[0];torch.cuda.set_rng_state(snapshot[1])
            for i in range(split,head.ddim_steps):resumed,_=quantum(resumed,i)
            resumed=head.denorm_odo(resumed.clamp(-clip,clip) if clip is not None else resumed)
            ref=torch.tensor(reference,device=final.device,dtype=final.dtype).unsqueeze(0)
        return {'official_final_allclose':bool(torch.allclose(final,ref,rtol=1e-5,atol=1e-5)),'resume_allclose':bool(torch.allclose(final,resumed,rtol=1e-5,atol=1e-5)),'max_official_error':float((final-ref).abs().max()),'steps':steps,'resume_boundary':split,'reuse':'cached VLM and conditioning embeddings plus x and CUDA RNG state','noisy_states_executable':False,'kernel_preemption':False}

def windows_inference_components():
    """Explicit inference-only port: no fake nuPlan modules and no upstream file edits.
    Import-time evaluator dependencies and GRPO scoring config are removed from a
    separately named module. All inference method ASTs stay byte-for-byte equivalent.
    Two compiled modulation expressions run in explicitly declared eager mode.
    """
    import ast,torch
    sys.path.insert(0,str(REPO))
    package='navsim.agents.recogdrive'
    from navsim.agents.recogdrive import recogdrive_dit
    eager_functions=[]
    for cls in (recogdrive_dit.FinalLayer,recogdrive_dit.LightningDiTBlock):
        compiled=cls.modulate;eager=getattr(compiled,'_torchdynamo_orig_callable',None)
        if eager is None:eager=getattr(cls,'_framelease_audited_eager',None)
        if eager is None:raise DependencyBlocked('Expected official compiled modulate wrapper absent; refuse undocumented port')
        cls._framelease_audited_eager=eager;cls.modulate=eager;eager_functions.append(cls.__name__+'.modulate')
    planner_path=REPO/'navsim/agents/recogdrive/recogdrive_diffusion_planner.py'
    source=planner_path.read_text(encoding='utf8');tree=ast.parse(source);removed=[]
    kept=[]
    for node in tree.body:
        if isinstance(node,ast.ImportFrom) and node.module and (node.module.startswith('navsim.') or node.module.startswith('nuplan.')):
            removed.append(ast.get_source_segment(source,node));continue
        if isinstance(node,ast.ClassDef) and node.name=='GRPOConfig':
            for i,field_node in enumerate(node.body):
                if isinstance(field_node,ast.AnnAssign) and isinstance(field_node.target,ast.Name) and field_node.target.id=='scorer_config':
                    removed.append(ast.get_source_segment(source,field_node));node.body[i]=ast.parse('scorer_config: Any = None').body[0]
        kept.append(node)
    tree.body=kept;ast.fix_missing_locations(tree)
    module=types.ModuleType('framelease_recogdrive_windows_inference');module.__package__=package;module.__file__=str(planner_path)
    sys.modules[module.__name__]=module
    exec(compile(tree,str(planner_path)+'[inference_only_port]','exec'),module.__dict__)
    # Reuse exact official factory and forward methods without importing Agent evaluator base.
    agent_path=REPO/'navsim/agents/recogdrive/recogdrive_agent.py';agent_source=agent_path.read_text(encoding='utf8');agent_tree=ast.parse(agent_source)
    selected=[];names=[]
    for node in agent_tree.body:
        if isinstance(node,ast.FunctionDef) and node.name=='make_recogdrive_config':selected.append(node);names.append(node.name)
        if isinstance(node,ast.ClassDef) and node.name=='ReCogDriveAgent':
            for fn in node.body:
                if isinstance(fn,ast.FunctionDef) and fn.name in ('forward','_decode_paths_from_tensor'):selected.append(fn);names.append(fn.name)
    from typing import Any,Dict,List,Union,Optional
    from transformers.feature_extraction_utils import BatchFeature
    from navsim.agents.recogdrive.utils.internvl_preprocess import load_image
    from navsim.agents.recogdrive.utils.utils import format_number
    ns=dict(torch=torch,Any=Any,Dict=Dict,List=List,Union=Union,Optional=Optional,BatchFeature=BatchFeature,load_image=load_image,format_number=format_number,ReCogDriveDiffusionPlannerConfig=module.ReCogDriveDiffusionPlannerConfig)
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(agent_path)+'[selected_official_methods]','exec'),ns)
    # Prove the declared scalar eager expression against its explicit equation on CUDA.
    x=torch.arange(24,device='cuda',dtype=torch.float32).reshape(2,3,4)/10;shift=torch.ones((2,4),device='cuda')*.2;scale=torch.ones_like(shift)*.3
    err=float((eager(None,x,shift,scale)-(x*(1+scale[:,None])+shift[:,None])).abs().max())
    return module,ns,{'backend':'windows_eager_inference_port','official_agent_import_supported':False,'official_compiled_execution':False,'eager_functions':eager_functions,'removed_evaluator_imports_and_config':removed,'official_method_extraction':names,'planner_source_sha256':file_hash(planner_path),'agent_source_sha256':file_hash(agent_path),'modulate_eager_expression_max_error':err,'inference_math_changes':[],'linux_official_full_forward_equivalence':'NOT_RUN'}

class WindowsInferenceAdapter(ReCogAdapter):
    def __init__(self,vlm,planner):
        import torch
        sys.path.insert(0,str(REPO))
        from navsim.agents.recogdrive.recogdrive_backbone import RecogDriveBackbone
        module,ns,port=windows_inference_components();self.torch=torch
        cfg=ns['make_recogdrive_config']('small',action_dim=3,action_horizon=8,input_embedding_dim=384,sampling_method='ddim');cfg.vlm_size='small'
        if cfg.grpo:raise DependencyBlocked('Inference-only port cannot execute GRPO')
        agent=torch.nn.Module();agent.cache_hidden_state=False;agent.grpo=False
        agent.backbone=RecogDriveBackbone('internvl',str(vlm),'cuda')
        agent.action_head=module.ReCogDriveDiffusionPlanner(cfg).cuda()
        state={k.removeprefix('agent.action_head.'):v for k,v in trusted_planner_checkpoint(planner).items() if k.startswith('agent.action_head.')}
        agent.action_head.load_state_dict(state,strict=True)
        self.agent=agent;agent.forward=types.MethodType(ns['forward'],agent);agent._decode_paths_from_tensor=ns['_decode_paths_from_tensor'].__func__ if isinstance(ns['_decode_paths_from_tensor'],staticmethod) else ns['_decode_paths_from_tensor'];agent.eval()
        self.provenance={**port,'planner_sha256':file_hash(planner),'vlm_config_sha256':file_hash(Path(vlm)/'config.json'),'planner_parameters_verified':len(dict(agent.action_head.named_parameters())),'planner_state_tensors_verified':len(state),'strict_checkpoint_load':True,'random_planner_parameters':0}
        # Exact official no-cache feature method; its only executed dependency is torch.
        import ast
        p=REPO/'navsim/agents/recogdrive/recogdrive_features.py';t=ast.parse(p.read_text(encoding='utf8'))
        fn=next(fn for cl in t.body if isinstance(cl,ast.ClassDef) and cl.name=='ReCogDriveFeatureBuilder' for fn in cl.body if isinstance(fn,ast.FunctionDef) and fn.name=='compute_features')
        for a in fn.args.args:a.annotation=None
        fn.returns=None
        namespace={'torch':torch};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(p)+'[official_feature_method]','exec'),namespace)
        self.builder=types.SimpleNamespace(cache_hidden_state=False);self.builder.compute_features=types.MethodType(namespace['compute_features'],self.builder)
    def configure_profile(self,max_patches,steps):
        from functools import partial
        from navsim.agents.recogdrive.utils.internvl_preprocess import load_image
        self.agent.forward.__func__.__globals__['load_image']=partial(load_image,max_num=max_patches)
        head=self.agent.action_head;head.config.num_inference_steps=steps;head._init_ddim_sampler(head.config.ddim_cfg);head.cuda()
        self.provenance['profile_override']={'max_image_tiles_before_thumbnail':max_patches,'patch_size':448,'ddim_steps':steps,'scheduler_buffers_rebuilt_with_official_method_after_strict_weight_load':True}

def resolve_resources():
    env=ROOT/'configs/staged_environment.json'
    if not env.exists():raise DependencyBlocked('Run Stage00 prepare; verified environment resource manifest absent')
    cfg=read_json(env);paths={}
    for repo in cfg['resources']:
        if repo['status']!='COMPLETED':raise DependencyBlocked(repo['repo_id']+': snapshot incomplete')
        for f in repo['files']:
            if f['status']!='COMPLETED' or file_hash(f['path'])!=f['sha256']:raise DependencyBlocked('Snapshot checksum fails: '+f['name'])
        paths[repo['repo_id']]=repo
    v=paths['owl10/ReCogDrive-VLM-2B'];vlm=ROOT/'checkpoints/ReCogDrive-VLM-2B'/v['revision']
    planners=[Path(f['path']) for f in paths['owl10/ReCogDrive-2B-IL']['files'] if f['name'].endswith('.ckpt')]
    if len(planners)!=1:raise DependencyBlocked('Planner checkpoint selection must resolve exactly one official checkpoint')
    return vlm,planners[0]

def run_backbone_diagnostic(run,args,data,vlm):
    """Official pretrained visual-language encoder only, not planner/closed-loop evidence."""
    import torch
    sys.path.insert(0,str(REPO))
    from navsim.agents.recogdrive.recogdrive_backbone import RecogDriveBackbone
    from navsim.agents.recogdrive.utils.internvl_preprocess import load_image
    from navsim.agents.recogdrive.utils.utils import format_number
    records=data['records'][:1] if args.mode=='smoke' else data['records']
    rows=[]
    with writer_lock(ROOT/'results/shared_gpu_resource'):
        start=time.perf_counter();model=RecogDriveBackbone('internvl',str(vlm),'cuda')
        load_s=time.perf_counter()-start
        provenance={'scope':'PRETRAINED_VLM_BACKBONE_ONLY','full_driving_vla':False,'snapshot':str(vlm),'weights_sha256':file_hash(vlm/'model.safetensors'),'load_wall_s':load_s,'dtype':str(next(model.parameters()).dtype),'parameter_count':sum(p.numel() for p in model.parameters()),'attention_backend':getattr(model.model.language_model.config,'_attn_implementation',None),'vision_flash_attention':getattr(model.model.vision_model.config,'use_flash_attn',None),'source_type':data['source_type'],'kernel_trace_available':False}
        atomic_json(run.path/'raw/backbone_provenance.json',provenance)
        for i,record in enumerate(records):
            hist=record['ego_history'];command=['turn left','go straight','turn right'][max(range(3),key=lambda j:hist[-1]['driving_command'][j])]
            history=' '.join(f'   - t-{3-j}: ({format_number(e["pose"][0])}, {format_number(e["pose"][1])}, {format_number(e["pose"][2])})' for j,e in enumerate(hist))
            question=("<image>\nAs an autonomous driving system, predict the vehicle's trajectory based on:\n1. Visual perception from front camera view\n"+f"2. Historical motion context (last 4 timesteps):{history}\n3. Active navigation command: [{command.upper()}]"+"\nOutput requirements:\n- Predict 8 future trajectory points\n- Each point format: (x:float, y:float, heading:float)\n- Use [PT, ...] to encapsulate the trajectory\n- Maintain numerical precision to 2 decimal places")
            pixels=load_image(record['image_path']).cuda();torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();a,b=torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True)
            t=time.perf_counter_ns();a.record()
            with torch.inference_mode():out=model(pixels,[question],[pixels.shape[0]])
            b.record();b.synchronize();wall=(time.perf_counter_ns()-t)/1e6;hidden=out.hidden_states[-1].detach()
            if not torch.isfinite(hidden).all():raise RuntimeError('Pretrained encoder produced nonfinite features')
            tensor_path=run.path/'raw'/('hidden_%03d.pt'%i);torch.save(hidden.cpu(),tensor_path)
            result={'scope':'PRETRAINED_VLM_BACKBONE_ONLY','image_sha256':record['image_sha256'],'capture_s':record['capture_s'],'patches':pixels.shape[0],'hidden_shape':list(hidden.shape),'hidden_sha256':file_hash(tensor_path),'hidden_path':str(tensor_path),'hidden_mean':float(hidden.float().mean()),'hidden_std':float(hidden.float().std()),'wall_ms':wall,'cuda_ms':a.elapsed_time(b),'peak_memory_bytes':torch.cuda.max_memory_allocated(),'question':question,'planner_executed':False,'trajectory_produced':False,'cold_first_forward':i==0}
            run.record({'kind':'actual_backbone_forward','record':record['image_sha256']},result);rows.append(result);del out,hidden,pixels
        write_csv(run.path/'metrics/backbone.csv',[{k:v for k,v in r.items() if k!='question'} for r in rows])
    run.state['evidence_type']=['REAL_GPU']
    return run.finish('PARTIAL','# Stage02 pretrained VLM backbone diagnostic\n\n'+canonical({'samples':len(rows),'provenance':provenance})+'\n\nActual official pretrained visual/language features saved. This is not a driving planner result or REAL_VLA completion. CUDA event spans and synchronized host time are measured; no kernel profiler trace. Input is actual CARLA recording, not a real-road dataset. First forward includes warmup. Full planner input protocol, official Agent platform import and compiled DiT remain separate gates.\n',acceptance='PARTIAL')

def run_plan_audit(args):
    source=args.saved_manifest
    if dry_plan(args,[{'saved_manifest':str(source),'new_inference':False,'paired_depths':[3,5]}]):return 0
    m=verified_manifest(source);run=StageRun('stage02_real_vla',args,{'mode':'plan-audit','source_manifest':str(source),'source_sha256':file_hash(source),'schedule':ddim_schedule_audit()},['REAL_VLA'])
    import numpy as np
    pairs={};rows=[]
    for task,result in saved_data(m):
        if 'trajectory' not in result or task.get('ddim_steps') not in (3,5):continue
        key=(task['record'],task['max_patches'],task['seed'],task['repeat']);pairs.setdefault(key,{})[task['ddim_steps']]=(task,result)
        validity=candidate_validity(result['trajectory'],task['ddim_steps'])
        run.record({'kind':'saved_candidate_validation',**task},{'trajectory':result['trajectory'],'validity':validity,'source_run':m['run_dir']})
    for key,pair in pairs.items():
        if set(pair)!={3,5}:raise ValueError('Unpaired Fast/Deep evidence')
        f,d=pair[3][1],pair[5][1];a,b=np.array(f['trajectory']),np.array(d['trajectory'])
        rows.append({'input_image_sha256':key[0],'max_patches':key[1],'seed':key[2],'repeat':key[3],'fast_wall_ms':f['wall_ms'],'deep_wall_ms':d['wall_ms'],'deep_minus_fast_wall_ms':d['wall_ms']-f['wall_ms'],
            'mean_position_difference_m':float(np.linalg.norm(a[:,:2]-b[:,:2],axis=1).mean()),'final_position_difference_m':float(np.linalg.norm(a[-1,:2]-b[-1,:2])),
            'fast_max_acceleration_mps2':f['validation'].get('max_acceleration_mps2'),'deep_max_acceleration_mps2':d['validation'].get('max_acceleration_mps2'),
            'deep_higher_acceleration_proxy':d['validation'].get('max_acceleration_mps2',0)>f['validation'].get('max_acceleration_mps2',0),'quality_improvement':'NOT_AVAILABLE_NO_REFERENCE_ROAD_OR_INTERACTION_LABELS'})
    write_csv(run.path/'metrics/paired_fast_deep.csv',rows)
    summary={'pairs':len(rows),'unique_correlated_images':len({r['input_image_sha256'] for r in rows}),'independent_driving_episodes':1,'mean_position_difference_m':statistics.mean(r['mean_position_difference_m'] for r in rows),'deep_higher_acceleration_proxy_count':sum(r['deep_higher_acceleration_proxy'] for r in rows),'schedule_audit':ddim_schedule_audit(),'quality_gain':'UNPROVEN','road_control_dynamic_closed_loop':'NOT_EVALUATED'}
    run.record({'kind':'paired_summary'},summary)
    return run.finish('PARTIAL','# Legal Fast/Deep saved-output audit\n\n'+canonical(summary)+'\n\nAll paired saved outputs retained; no new inference or selective exclusion. Higher acceleration is a diagnostic proxy, not proof of worse planning. Same-schedule resume does not prove three-to-five-step continuation. Separate validity levels remain unknown without their own evidence.',acceptance='PARTIAL')

def run_closed_loop_candidate_audit(args):
    path=args.closed_loop_episode
    if dry_plan(args,[{'episode':str(path),'operation':'posthoc_candidate_road_and_tracking_audit','new_inference':False}]):return 0
    if not path:raise ValueError('--closed-loop-episode required')
    source=path/'final_events.json';d=read_json(source);run=StageRun('stage02_real_vla',args,{'mode':'closed-loop-audit','source':str(source),'source_sha256':file_hash(source),'interpretation':'posthoc evaluation only; no deployment truth input'},['REAL_VLA','CARLA_CLOSED_LOOP'])
    rows=[];unique=sorted({t.get('active_observation_id') for t in d['ticks'] if t.get('active_observation_id') is not None})
    for obs in unique:
        file=path/('candidate_'+str(obs)+'.json');candidate=read_json(file);trajectory=candidate['result']['trajectory'];steps=len(candidate['result']['clean_candidates']);v=candidate_validity(trajectory,steps)
        ticks=[t for t in d['ticks'] if t.get('active_observation_id')==obs and not t['fallback']]
        first,last=min(t['frame'] for t in ticks),max(t['frame'] for t in ticks)
        lane=[e for e in d.get('lane_invasions',[]) if first<=e['frame']<=last];collision=[e for e in d['collisions'] if first<=e['frame']<=last]
        control=[t['tracker'] for t in ticks];max_error=max(abs(c.get('cross_track_error_m',0)) for c in control)
        road_min=min(t['evaluation_context']['road']['center_to_boundary_m'] for t in ticks if t['evaluation_context']['road'])
        # These checks describe only the short applied interval, not all eight future points.
        v['levels']['control_executable']='OBSERVED_APPLIED_INTERVAL_ONLY' if control else 'NOT_EVALUATED'
        v['levels']['road_valid']='FAIL_OBSERVED_LANE_CROSSING' if lane else 'UNVALIDATED_NO_CALLBACK_IN_SHORT_INTERVAL'
        v['levels']['closed_loop_valid']='FAIL_OBSERVED_COLLISION_OR_LANE_CROSSING' if lane or collision else 'UNVALIDATED_SHORT_INTERVAL'
        row={'observation_id':obs,'steps':steps,'candidate_sha256':file_hash(file),'applied_ticks':len(ticks),'applied_duration_s':len(ticks)*.05,'cross_track_max_m':max_error,'nearest_lane_center_boundary_min_m':road_min,'lane_invasion_callbacks':len(lane),'collision_callbacks':len(collision),'road_check_scope':'posthoc CARLA ground-truth evaluator, no full-horizon road validation','validity':v}
        run.record({'kind':'actual_candidate_closed_loop_audit','observation_id':obs},row);rows.append(row)
    write_csv(run.path/'metrics/closed_loop_candidate_validity.csv',[{**r,'validity':canonical(r['validity'])} for r in rows])
    summary={'candidates':len(rows),'candidates_with_lane_crossing':sum(r['lane_invasion_callbacks']>0 for r in rows),'candidates_with_collision':sum(r['collision_callbacks']>0 for r in rows),'safe_full_horizon_candidates':None,'reason':'Safe outcome over one short application interval does not validate the entire four-second candidate','episode_count':1}
    run.record({'kind':'closed_loop_summary'},summary)
    return run.finish('PARTIAL','# Candidate validity by independent criterion\n\n'+canonical(summary)+'\n\nKinematic pass is retained separately from observed lane crossing and tracking error. No ground-truth road evaluator output enters the model/controller. Candidates with no short-interval failure remain unvalidated for full-horizon dynamic safety.',acceptance='PARTIAL')

def run_legal_pair(args):
    if dry_plan(args,['one actual 3-step Fast, feature-reused 5-step Deep, independent 5-step equivalence']):return 0
    run=StageRun('stage02_real_vla',args,{'mode':'legal-pair','backend':args.backend,'input_sha256':file_hash(args.input_manifest),'schedule':ddim_schedule_audit()},['REAL_VLA','REAL_GPU'])
    try:
        if args.backend!='windows-eager':raise DependencyBlocked('This measured port experiment requires explicit windows-eager')
        import numpy as np
        records=validated_input(args.input_manifest,True)['records'];vlm,planner=resolve_resources()
        with writer_lock(ROOT/'results/shared_gpu_resource'):
            model=WindowsInferenceAdapter(vlm,planner);model.configure_profile(12,3);job=model.start_job(records[0],args.seed,3);events=[]
            for _ in range(3):fast=model.step_job(job);events.append({'phase':'fast',**fast})
            start=time.perf_counter_ns();deep_job=model.restart_deep(job);reuse_setup=(time.perf_counter_ns()-start)/1e6
            for _ in range(5):deep=model.step_job(deep_job);events.append({'phase':'deep_recompute',**deep})
            model.configure_profile(12,5);reference,_=model.infer(records[0],args.seed)
            error=float(np.max(np.abs(np.array(deep['trajectory'])-np.array(reference['trajectory']))))
            result={'fast':fast,'deep':deep,'events':events,'encode_wall_s':job['encode_wall_s'],'encode_cuda_ms':job['encode_cuda_ms'],'feature_reuse_setup_ms':reuse_setup,'denoising_quanta_reused':0,'deep_denoising_quanta_recomputed':5,'conditioning_reused':True,'independent_deep_max_error':error,'independent_deep_allclose':error<=1e-5,'provenance':model.provenance,'source_input':records[0]}
            run.record({'kind':'legal_fast_deep_pair','record':records[0]['image_sha256'],'seed':args.seed},result)
            if error>1e-5:raise AssertionError('Feature-reused Deep differs from independent five-step result')
        return run.finish('PARTIAL','Actual 3-step and complete 5-step candidates measured. Feature embeddings reused; all five Deep denoising quanta recomputed. Independent five-step equality max error='+str(error)+'. Kinematics do not establish control/road/dynamic safety.',acceptance='PARTIAL')
    except BaseException:run.log('failure',traceback=traceback.format_exc());return run.finish('FAILED',traceback.format_exc())

def run_experiment(args):
    if args.mode=='wam-audit':return run_wam_audit(args)
    if args.mode in ('contract-audit','anytime-audit','wam-audit','unidrive-audit','unidrive-resources','minddrive-audit','unidrive-operator'):return run_road_refinement_audit(args)
    if args.mode=='closed-loop-audit':return run_closed_loop_candidate_audit(args)
    if args.mode=='plan-audit':return run_plan_audit(args)
    if args.mode=='legal-pair':return run_legal_pair(args)
    if dry_plan(args,['official source audit','strict verified weights/input gate','real forward','clean x0 refinement and resume equivalence']):return 0
    inputs=args.input_manifest
    source=source_audit();source['selected_backend']=args.backend;source['profile_sweep']=args.profile_sweep;resource_manifest=ROOT/'configs/staged_environment.json'
    run=StageRun('stage02_real_vla',args,{'mode':args.mode,'backbone_only':args.backbone_only,'input_manifest':str(inputs),'input_manifest_sha256':file_hash(inputs) if inputs.is_file() else None,'resource_manifest_sha256':file_hash(resource_manifest) if resource_manifest.is_file() else None,'source':source,'quick':args.quick},[],[REPO/'navsim/agents/recogdrive/recogdrive_agent.py',REPO/'navsim/agents/recogdrive/recogdrive_diffusion_planner.py'])
    try:
        run.record({'kind':'source_audit'},source)
        blockers=[]
        try:data=validated_input(inputs,require_planner=not args.backbone_only)
        except (DependencyBlocked,ValueError) as e:blockers.append(str(e))
        try:vlm,planner=resolve_resources()
        except DependencyBlocked as e:blockers.append(str(e))
        if args.backbone_only and not blockers:return run_backbone_diagnostic(run,args,data,vlm)
        sys.path.insert(0,str(REPO))
        if args.backend=='official':
            try:from navsim.agents.recogdrive.recogdrive_agent import ReCogDriveAgent
            except Exception as e:blockers.append('Actual official Agent import failed: '+repr(e));run.log('official_import_failure',traceback=traceback.format_exc())
        if blockers:
            for b in blockers:run.record({'kind':'real_inference_gate','blocker':b},{},'BLOCKED',b)
            run.state['evidence_type']=[]
            return run.finish('BLOCKED','# Stage02 real VLA blocked\n\n'+'\n'.join('- '+b for b in blockers)+'\n\nNo model output, simulated replacement, measured refinement or completed acceptance. Source auditing is not inference.\n',blockers)
        with writer_lock(ROOT/'results/shared_gpu_resource'):
            adapter=(ReCogAdapter if args.backend=='official' else WindowsInferenceAdapter)(vlm,planner);atomic_json(run.path/'raw/adapter_provenance.json',adapter.provenance);rows=[];repeat=1 if args.mode=='smoke' else (3 if args.quick else 30)
            profiles=[(p,s) for p in (1,2,12) for s in (1,3,5)] if args.profile_sweep else [(12,5)]
            for max_patches,steps in profiles:
                if args.profile_sweep:adapter.configure_profile(max_patches,steps)
                for record in data['records']:
                    for repeat_id in range(repeat):
                        task={'record':record['image_sha256'],'repeat':repeat_id,'seed':args.seed+repeat_id,'max_patches':max_patches,'ddim_steps':steps}
                        result=run.cached(task)
                        if result is None:
                            result,context=adapter.infer(record,args.seed+repeat_id)
                            if args.mode in ('refinement','full') and steps>1:result['refinement']=adapter.refinement_equivalence(context,result['trajectory'])
                        run.state['evidence_type']=['REAL_VLA'];run.record(task,result);rows.append({**task,'wall_ms':result['wall_ms'],'valid':result['validation']['valid'],'peak_memory_bytes':result['peak_memory_bytes'],'vlm_cuda_ms':sum(e['cuda_ms'] for e in result['events'] if e['kind']=='vlm_encoding'),'planner_quanta_cuda_ms':sum(e['cuda_ms'] for e in result['events'] if e['kind']=='denoising_quantum')})
            write_csv(run.path/'metrics/inference.csv',rows)
            summary={'n':len(rows),'p50_ms':quantile([x['wall_ms'] for x in rows],.5),'p95_ms':quantile([x['wall_ms'] for x in rows],.95),'p99_ms':quantile([x['wall_ms'] for x in rows],.99),'valid_rate':sum(x['valid'] for x in rows)/len(rows)}
            atomic_json(run.path/'metrics/summary.json',summary)
            profiles_summary=[]
            for p,s in profiles:
                group=[r for r in rows if r['max_patches']==p and r['ddim_steps']==s]
                profiles_summary.append({'max_patches':p,'ddim_steps':s,'n':len(group),'wall_p50_ms':quantile([r['wall_ms'] for r in group],.5),'wall_p95_ms':quantile([r['wall_ms'] for r in group],.95),'valid_rate':sum(r['valid'] for r in group)/len(group),'peak_memory_bytes':max(r['peak_memory_bytes'] for r in group)})
            write_csv(run.path/'metrics/profile_conditions.csv',profiles_summary)
        return run.finish('PARTIAL','# Stage02 real inference\n\n'+canonical(summary)+'\n\nBackend: '+args.backend+'. Official pretrained VLM and strict planner weights. Explicit Windows eager port isolates evaluator-only imports and two compile wrappers; no Linux native compiled equivalence claimed. DDIM resume comparison uses exact extracted official inference methods in this same declared backend. Kinematic validity is not collision safety. Profile conditions: '+canonical(profiles_summary)+'\n\nFormal accuracy needs reference trajectories and calibrated input domain; no kernel-level trace is available. Image-tiling/depth overrides are experimental settings, not certified quality improvements. CUDA event timing plus synchronized host spans include diagnostic hook/copy overhead. Small-n quantiles are descriptive and include cold first forward; six frames are correlated from one CARLA recording.',acceptance='PARTIAL')
    except DependencyBlocked as e:return run.finish('BLOCKED',str(e),[str(e)])
    except BaseException as e:run.log('failure',traceback=traceback.format_exc());return run.finish('FAILED',traceback.format_exc())
def run_road_refinement_audit(args):
    if not args.closed_loop_episode:raise ValueError('--closed-loop-episode required')
    files=sorted(args.closed_loop_episode.glob('candidate_*.json'),key=lambda p:int(p.stem.split('_')[-1]))
    if not files:raise ValueError('No actual observations/candidates')
    if dry_plan(args,[{'mode':args.mode,'actual_candidates':len(files)}]):return 0
    run=StageRun('stage02_real_vla',args,{'mode':args.mode,'episode':str(args.closed_loop_episode),'candidate_sources':{str(p):file_hash(p) for p in files},'schedule':ddim_schedule_audit()},['REAL_VLA'],[ROOT/'stage05_carla_closed_loop.py',REPO/'navsim/agents/recogdrive/recogdrive_features.py',REPO/'navsim/agents/recogdrive/utils/internvl_preprocess.py'])
    try:
        import numpy as np,torch,ast,shutil
        if args.mode=='contract-audit':
            sys.path.insert(0,str(REPO))
            from PIL import Image
            from navsim.agents.recogdrive.utils.internvl_preprocess import load_image,dynamic_preprocess
            msg=read_json(files[0]);record=msg['record'];root=run.path/'raw';shutil.copy2(record['image_path'],root/'original.png');image=Image.open(record['image_path']).convert('RGB')
            tiles=dynamic_preprocess(image,max_num=12,use_thumbnail=True)
            for i,tile in enumerate(tiles):tile.save(root/f'processed_tile_{i:02d}.png')
            pixels=load_image(record['image_path']);np.save(root/'normalized_pixels.npy',pixels.numpy())
            source=REPO/'navsim/agents/recogdrive/recogdrive_features.py';tree=ast.parse(source.read_text(encoding='utf8'));fn=next(f for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='ReCogDriveFeatureBuilder' for f in c.body if isinstance(f,ast.FunctionDef) and f.name=='compute_features')
            for a in fn.args.args:a.annotation=None
            fn.returns=None;namespace={'torch':torch};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),namespace)
            builder=types.SimpleNamespace(cache_hidden_state=False);builder.compute_features=types.MethodType(namespace['compute_features'],builder)
            ego=[types.SimpleNamespace(ego_pose=e['pose'],ego_velocity=e['velocity'],ego_acceleration=e['acceleration'],driving_command=e['driving_command']) for e in record['ego_history']]
            features=builder.compute_features(types.SimpleNamespace(ego_statuses=ego,cameras=[types.SimpleNamespace(cam_f0=types.SimpleNamespace(image=record['image_path']))]))
            numeric={k:v.tolist() for k,v in features.items()};atomic_json(root/'official_features.json',numeric);atomic_json(root/'source_record.json',record)
            summary={'source':str(files[0]),'image_shape':list(image.size),'pixels_shape':list(pixels.shape),'pixels_dtype':str(pixels.dtype),'normalized_min':pixels.min().item(),'normalized_max':pixels.max().item(),'normalized_sha256':file_hash(root/'normalized_pixels.npy'),'history_times':[e['capture_s'] for e in record['ego_history']],'camera_capture_s':record['capture_s'],'command':numeric['high_command_one_hot'],'official_prompt_command':['turn left','go straight','turn right'][int(features['high_command_one_hot'].argmax())],'status_feature':numeric['status_feature'],'camera_intrinsic_640x360_fov90':[[320.,0.,320.],[0.,320.,180.],[0.,0.,1.]],'training_camera_calibration_equivalence':'UNKNOWN','reference_point':record.get('reference_point','legacy_body_origin'),'output_sampling_s':[.5*i for i in range(1,9)],'source_features_sha256':file_hash(source)}
            run.record({'kind':'official_preprocessing_and_status'},summary)
        else:
            from stage05_carla_closed_loop import trajectory_reference,route_polygon,footprint_route_check
            route_path=args.route_geometry or args.closed_loop_episode/'route_geometry.json';route=read_json(route_path);polygon=route_polygon(route);geom=read_json(args.closed_loop_episode/'vehicle_and_map.json');rows=[]
            for file in files:
                msg=read_json(file);record=msg['record'];cg=dict(geom);o=cg.get('bounding_box_offset_model_m',[0.,0.]);cg['bounding_box_offset_model_m']=[o[0]-record.get('reference_offset_x_m',0),o[1]]
                for index,q in enumerate(msg['result']['clean_candidates']):
                    traj=q.get('trajectory',q.get('candidate'));checks=[footprint_route_check(trajectory_reference(traj,record['origin'],k*.05)['pose'],cg,route,polygon) for k in range(81)]
                    kin=validate_trajectory(traj);rows.append({'observation_id':record['frame'],'source_sha256':file_hash(file),'depth':index+1,'schedule_steps':len(msg['result']['clean_candidates']),'kinematic':kin['valid'],'route_outside_samples':sum(x['outside'] is True for x in checks),'route_unknown_samples':sum(x['outside'] is None for x in checks),'final':index+1==len(msg['result']['clean_candidates'])})
            write_csv(run.path/'metrics/same_schedule_candidates.csv',rows)
            bydepth={str(d):{'n':len(g),'kinematic_pass':sum(r['kinematic'] for r in g),'road_geometry_pass':sum(r['route_outside_samples']==0 and r['route_unknown_samples']==0 for r in g)} for d in sorted({r['depth'] for r in rows}) for g in [[r for r in rows if r['depth']==d]]}
            vlm,planner=resolve_resources()
            with writer_lock(ROOT/'results/shared_gpu_resource'):
                model=WindowsInferenceAdapter(vlm,planner);record=read_json(files[0])['record'];job=model.start_job(record,args.seed,5);q1=model.step_job(job);torch.cuda.synchronize();start=time.perf_counter_ns()
                state={k:v.clone() if torch.is_tensor(v) else v for k,v in job.items()};snapshot_ms=(time.perf_counter_ns()-start)/1e6
                direct=[model.step_job(job) for _ in range(4)]
                other=model.start_job(read_json(files[-1])['record'],args.seed+1,3);other_candidate=model.step_job(other)
                start=time.perf_counter_ns();resumed=[model.step_job(state) for _ in range(4)];restore_and_continue_ms=(time.perf_counter_ns()-start)/1e6
                error=float(np.max(np.abs(np.array(direct[-1]['trajectory'])-np.array(resumed[-1]['trajectory']))))
                probe={'first':q1,'continued':direct,'resumed':resumed,'interleaved_other_observation':other_candidate,'max_error':error,'snapshot_ms':snapshot_ms,'restore_and_continue_ms':restore_and_continue_ms,'prefix_quanta_reused':1,'provenance':model.provenance,'quality':'UNPROVEN','suspend_semantics':'Unchanged 5-step schedule, device state cloned; intervening 3-step observation reconfigures sampler; original schedule restored'}
                run.record({'kind':'actual_same_schedule_interleaved_resume'},probe)
                if error>1e-5:raise AssertionError('State restore numerical mismatch')
            summary={'all_saved_intermediate_candidates':len(rows),'by_depth':bydepth,'same_schedule_resume_max_error':error,'three_to_five':'NO_COMMON_PREFIX','progressive_deployment':'PROGRESSIVE_VLA_BLOCKED','reason':'Numerical continuation exists, but executable road-valid early outputs and stable quality gains are unproven; complete 3/5 schedules are independent inference.'}
            run.record({'kind':'anytime_summary'},summary)
        atomic_json(run.path/'metrics/summary.json',summary);return run.finish('PARTIAL',canonical(summary),acceptance='PARTIAL')
    except BaseException:run.log('failure',traceback=traceback.format_exc());return run.finish('FAILED',traceback.format_exc())

def strict_wam_numbers(text):
    """No padding, truncation, or picking numbers out of malformed natural language."""
    import re
    value=text.strip()
    if 'Trajectory:' in value and 'Driving decision:' in value:value=value.split('Trajectory:',1)[1].split('Driving decision:',1)[0].strip()
    if not re.fullmatch(r'\s*[-+]?\d+(?:\.\d+)?(?:\s*,\s*[-+]?\d+(?:\.\d+)?){15}\s*',value):return None
    values=[float(v) for v in value.split(',')]
    return values if all(math.isfinite(v) for v in values) else None

def wam_final_batch(states):
    """Official Softmax intermediate shape is [steps+1,tokens], not three-dimensional."""
    if len(states.shape)!=2:raise ValueError('Unexpected official WAM intermediate shape')
    return states[-1].reshape(1,-1).clone()

def run_wam_audit(args):
    """Actual official WAM implementation, evaluator-free extraction, no model substitute.
    Raw generated text is checked before official permissive number padding can hide failure.
    """
    repo=ROOT/'third_party/WAM-Flow';net=read_json(ROOT/'audits/road_refinement/official_network_probe.json')
    wam=ROOT/'checkpoints/WAM-Flow'/net['wam_weights']['revision'];fudoki=ROOT/'checkpoints/FUDOKI'/net['fudoki']['revision']
    if dry_plan(args,[{'mode':'official_wam_forward','checkpoint':str(wam),'steps':[2,5],'input_episode':str(args.closed_loop_episode)}]):return 0
    sources=[repo/'navsim/agents/wam_flow_agent.py',repo/'fudoki/janus/models/modeling_vlm.py',repo/'flow_matching/solver/discrete_solver.py',repo/'flow_matching/path/mixture.py',repo/'fudoki/eval_loop.py']
    run=StageRun('stage02_real_vla',args,{'mode':'wam-audit','wam_revision':net['wam_weights']['revision'],'fudoki_revision':net['fudoki']['revision'],'source_commit':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),'steps':[2,5],'dtype':'official float32','adaptation':'extract exact official agent methods and Trajectory dataclass, remove evaluator base initialization only; no sampler or attention edits'},[],sources)
    try:
        needed=[(wam,'config.json',net['wam_weights']),(wam,'model.safetensors',net['wam_weights']),(wam,'best_model_epoch95.pt',net['wam_weights'])]+[(fudoki,f,net['fudoki']) for f in ('text_embedding.pt','image_embedding.pt','tokenizer.json','tokenizer_config.json','processor_config.json','preprocessor_config.json','special_tokens_map.json')]
        identity=[];blockers=[]
        for base,name,meta in needed:
            p=base/name;item=next(x for x in meta['files'] if x['name']==name)
            if not p.is_file():blockers.append('Missing complete verified resource '+str(p));continue
            h=file_hash(p);expected=(item.get('lfs') or {}).get('sha256')
            if p.stat().st_size!=item['size'] or (expected and expected!=h):raise ValueError('Official resource identity mismatch '+str(p))
            identity.append({'path':str(p),'sha256':h,'bytes':p.stat().st_size})
        run.record({'kind':'wam_resource_gate'},{'files':identity,'blockers':blockers})
        if blockers:return run.finish('BLOCKED','WAM actual inference prerequisites incomplete. No timing, candidate or incremental quality result is invented.',blockers)
        import ast,re,typing
        sys.path[:0]=[str(ROOT/'resources/wam_dependencies'),str(repo)]
        import torch,numpy as np
        import torch.nn as nn
        from PIL import Image
        from torchvision import transforms
        from flow_matching.path import MixtureDiscreteSoftmaxProbPath
        from flow_matching.solver import MixtureDiscreteSoftmaxEulerSolver
        from fudoki.eval_loop import CFGScaledModel
        from fudoki.janus.models import VLChatProcessor,MultiModalityCausalLM
        from fudoki.janus.models.heading_mlp import TrajectoryHeadingMLP
        from nuplan.planning.simulation.trajectory.trajectory_sampling import TrajectorySampling
        from numpy import typing as npt
        # Exact official return dataclass avoids evaluator-only fcntl dependencies.
        dc=repo/'navsim/common/dataclasses.py';dtree=ast.parse(dc.read_text(encoding='utf8'));trajectory_node=next(n for n in dtree.body if isinstance(n,ast.ClassDef) and n.name=='Trajectory')
        ns={**vars(typing),'torch':torch,'nn':nn,'np':np,'npt':npt,'re':re,'os':os,'Image':Image,'transforms':transforms,'cudnn':torch.backends.cudnn,'dataclass':dataclasses.dataclass,'TrajectorySampling':TrajectorySampling,'NAVSIM_INTERVAL_LENGTH':.5}
        exec(compile(ast.Module(body=[trajectory_node],type_ignores=[]),str(dc)+'[exact_Trajectory]', 'exec'),ns)
        src=sources[0];tree=ast.parse(src.read_text(encoding='utf8'));body=[]
        for n in tree.body:
            if isinstance(n,ast.FunctionDef):body.append(n)
            if isinstance(n,ast.ClassDef) and n.name=='WamFlowAgent':
                n.bases=[]
                for f in n.body:
                    if isinstance(f,ast.FunctionDef):
                        if f.name=='__init__':f.body=[s for s in f.body if not (isinstance(s,ast.Expr) and isinstance(s.value,ast.Call) and isinstance(s.value.func,ast.Attribute) and isinstance(s.value.func.value,ast.Call) and isinstance(s.value.func.value.func,ast.Name) and s.value.func.value.func.id=='super')]
                        for a in f.args.args:a.annotation=None
                        f.returns=None
                body.append(n)
        ns.update(IMG_LEN=576,MixtureDiscreteSoftmaxProbPath=MixtureDiscreteSoftmaxProbPath,MixtureDiscreteSoftmaxEulerSolver=MixtureDiscreteSoftmaxEulerSolver,CFGScaledModel=CFGScaledModel,VLChatProcessor=VLChatProcessor,MultiModalityCausalLM=MultiModalityCausalLM,TrajectoryHeadingMLP=TrajectoryHeadingMLP)
        exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(src)+'[evaluator_free_exact_methods]','exec'),ns)
        official_parser=ns['extract_num_list'];parser_events=[]
        def record_official_parser(value):
            result=official_parser(value);parser_events.append({'text':value,'numbers':result});return result
        ns['extract_num_list']=record_official_parser
        files=sorted(args.closed_loop_episode.glob('candidate_*.json'),key=lambda p:int(p.stem.split('_')[-1]));record=read_json(files[0])['record'];last=record['ego_history'][-1]
        ego=types.SimpleNamespace(driving_command=np.array(last['driving_command']),ego_velocity=np.array(last['velocity']),ego_acceleration=np.array(last['acceleration']))
        scene=types.SimpleNamespace(scene_metadata=types.SimpleNamespace(num_history_frames=1),frames=[types.SimpleNamespace(ego_status=ego)])
        inp=types.SimpleNamespace(cameras=[types.SimpleNamespace(cam_f0=types.SimpleNamespace(image=record['image_path']))])
        atomic_json(run.path/'raw/input_record.json',record);rows=[]
        from stage05_carla_closed_loop import route_polygon,footprint_route_check,trajectory_reference
        route=read_json(args.closed_loop_episode/'route_geometry.json');polygon=route_polygon(route);geom=read_json(args.closed_loop_episode/'vehicle_and_map.json');offset=geom.get('bounding_box_offset_model_m',[0.,0.]);geom['bounding_box_offset_model_m']=[offset[0]-record.get('reference_offset_x_m',0.),offset[1]]
        with writer_lock(ROOT/'results/shared_gpu_resource'):
            agent=ns['WamFlowAgent'](fudoki_path=str(fudoki),wam_flow_path=str(wam),text_embedding_path=str(fudoki/'text_embedding.pt'),image_embedding_path=str(fudoki/'image_embedding.pt'),heading_mlp_path=str(wam/'best_model_epoch95.pt'),discrete_fm_steps=2,seed=args.seed,dtype='default')
            st=time.perf_counter();agent.initialize();torch.cuda.synchronize();load_s=time.perf_counter()-st
            original_sample=agent.solver.sample
            for steps in (2,5):
                agent.discrete_fm_steps=steps;torch.manual_seed(args.seed);torch.cuda.manual_seed_all(args.seed);captured={};events=[];original_model=agent.solver.model;snapshots=[];clean_texts=[]
                initial_rng=(torch.get_rng_state(),torch.cuda.get_rng_state());parser_events.clear()
                class ModelRecorder(torch.nn.Module):
                    g_or_u='understanding'
                    def __init__(self):super().__init__()
                    def forward(self,**kw):
                        snapshots.append({'x':kw['x'].clone(),'rng_cpu':torch.get_rng_state(),'rng_cuda':torch.cuda.get_rng_state(),'datainfo':kw['datainfo']})
                        start=time.perf_counter_ns();a,b=torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True);a.record();r=original_model(**kw);b.record();b.synchronize()
                        tokens=r[0].argmax(-1)[r[2]['text_token_mask']==1].reshape(1,-1);clean_texts.append(agent.vl_chat_processor.tokenizer.batch_decode(tokens,skip_special_tokens=True)[0])
                        events.append({'wall_ms':(time.perf_counter_ns()-start)/1e6,'cuda_ms':a.elapsed_time(b),'input_tokens_sha256':hashlib.sha256(kw['x'].detach().cpu().numpy().tobytes()).hexdigest()});return r
                agent.solver.model=ModelRecorder()
                def capture_sample(*a,**kw):
                    # Request every original uniform-grid boundary, preserving all transition times.
                    grid=torch.tensor([i/steps for i in range(steps+1)])
                    states=original_sample(*a,**{**kw,'return_intermediates':True,'time_grid':grid});captured['states']=states.detach().cpu()
                    torch.save(captured['states'],run.path/'raw'/f'wam_states_{steps}.pt')
                    atomic_json(run.path/'raw'/f'wam_forward_{steps}.json',{'events':events,'clean_texts':clean_texts})
                    # Official Softmax solver flattens intermediate output to [steps+1,tokens].
                    # compute_trajectory requires [batch,tokens], including batch size one.
                    return wam_final_batch(states)
                agent.solver.sample=capture_sample;torch.cuda.reset_peak_memory_stats();t=time.perf_counter_ns()
                try:trajectory=agent.compute_trajectory(inp,scene);torch.cuda.synchronize()
                finally:agent.solver.sample=original_sample;agent.solver.model=original_model
                wall=(time.perf_counter_ns()-t)/1e6;states=captured['states'];texts=agent.vl_chat_processor.tokenizer.batch_decode(states.reshape(-1,states.shape[-1]),skip_special_tokens=True);decoded=[]
                for index,text in enumerate(texts):
                    stripped=text.strip();valid=strict_wam_numbers(stripped) is not None
                    decoded.append({'index':index,'text':text,'strict_16_number_sequence':valid,'numeric_count':len(re.findall(r'[-+]?[0-9]*\.?[0-9]+',stripped)),'executable':'UNKNOWN' if valid else 'FAIL_DECODE','kind':'initial_or_noisy_transition' if index<steps else 'final_clean_tokens'})
                torch.save(states,run.path/'raw'/f'wam_states_{steps}.pt')
                instrumented_parser=parser_events[-1]
                torch.set_rng_state(initial_rng[0]);torch.cuda.set_rng_state(initial_rng[1]);reference_start=time.perf_counter_ns()
                reference_trajectory=agent.compute_trajectory(inp,scene);torch.cuda.synchronize();reference_ms=(time.perf_counter_ns()-reference_start)/1e6
                reference_parser=parser_events[-1];instrumentation_error=float(np.max(np.abs(trajectory.poses-reference_trajectory.poses)))
                atomic_json(run.path/'raw'/f'wam_equivalence_{steps}.json',{'instrumented_parser':instrumented_parser,'reference_parser':reference_parser,'trajectory_max_error':instrumentation_error})
                if instrumentation_error>1e-5 or instrumented_parser['text']!=reference_parser['text']:raise AssertionError('WAM instrumentation changes official output; do not use as equivalent inference')
                # Execute a different captured observation before restoring this task's complete state.
                other=read_json(files[-1])['record'];other_last=other['ego_history'][-1]
                other_ego=types.SimpleNamespace(driving_command=np.array(other_last['driving_command']),ego_velocity=np.array(other_last['velocity']),ego_acceleration=np.array(other_last['acceleration']))
                other_scene=types.SimpleNamespace(scene_metadata=types.SimpleNamespace(num_history_frames=1),frames=[types.SimpleNamespace(ego_status=other_ego)])
                other_input=types.SimpleNamespace(cameras=[types.SimpleNamespace(cam_f0=types.SimpleNamespace(image=other['image_path']))])
                agent.discrete_fm_steps=2;other_start=time.perf_counter_ns();other_trajectory=agent.compute_trajectory(other_input,other_scene);torch.cuda.synchronize();other_ms=(time.perf_counter_ns()-other_start)/1e6;agent.discrete_fm_steps=steps
                boundary=2 if steps==5 else 1;snapshot=snapshots[boundary];torch.set_rng_state(snapshot['rng_cpu']);torch.cuda.set_rng_state(snapshot['rng_cuda']);resume_start=time.perf_counter_ns()
                restored=original_sample(x_init=snapshot['x'],step_size=None,time_grid=torch.tensor([i/steps for i in range(boundary,steps+1)]),return_intermediates=False,div_free=0,dtype_categorical=torch.float32,datainfo=snapshot['datainfo'],cfg_scale=0)
                torch.cuda.synchronize();resume_ms=(time.perf_counter_ns()-resume_start)/1e6;resume_equal=bool(torch.equal(restored.cpu(),states[-1:].reshape(restored.shape)))
                torch.save({'x':snapshot['x'].cpu(),'rng_cpu':snapshot['rng_cpu'],'rng_cuda':snapshot['rng_cuda'],'boundary':boundary,'schedule_steps':steps,'datainfo':{k:v.cpu() if isinstance(v,torch.Tensor) else v for k,v in snapshot['datainfo'].items()}},run.path/'raw'/f'wam_resume_state_{steps}.pt')
                row={'steps':steps,'wall_ms':wall,'model_forward_events':events,'load_wall_s':load_s,'peak_memory_bytes':torch.cuda.max_memory_allocated(),'raw_decoded_states':decoded,'official_padded_output':trajectory.poses.tolist(),'kinematic':validate_trajectory(trajectory.poses),'strict_final_decode':decoded[-1]['strict_16_number_sequence'],'input_image_sha256':record['image_sha256'],'forward_instrumentation':'exact solver return_intermediates=True; output final state unchanged','quality':'UNKNOWN','resume':'NOT_VERIFIED','progressive':'UNKNOWN_NOT_ASSUMED'}
                row.update(official_parser_event=instrumented_parser,uninstrumented_parser_event=reference_parser,uninstrumented_wall_ms=reference_ms,instrumentation_trajectory_max_error=instrumentation_error,instrumentation_text_equal=instrumented_parser['text']==reference_parser['text'],interleaved_other_observation={'image_sha256':other['image_sha256'],'capture_s':other['capture_s'],'wall_ms':other_ms,'official_output':other_trajectory.poses.tolist()},clock_scope='single cold instrumented and warm reference execution; not statistical latency percentiles')
                clean_candidates=[]
                for depth,text in enumerate(clean_texts,1):
                    values=strict_wam_numbers(text);item={'depth':depth,'text':text,'strict_decode':values is not None}
                    if values is not None:
                        xy=torch.tensor(values,dtype=torch.float32,device='cuda').reshape(1,8,2)
                        with torch.inference_mode():headings=agent.heading_model(xy).cpu().reshape(8,1).numpy()
                        tr=np.concatenate([xy.cpu().reshape(8,2).numpy(),headings],axis=1).tolist();checks=[footprint_route_check(trajectory_reference(tr,record['origin'],k*.05)['pose'],geom,route,polygon) for k in range(81)]
                        item.update(trajectory=tr,kinematic=validate_trajectory(tr),road_outside_samples=sum(r['outside'] is True for r in checks),road_unknown_samples=sum(r['outside'] is None for r in checks),quality_scope='single actual CARLA observation; no statistical refinement gain')
                    clean_candidates.append(item)
                row.update(clean_argmax_candidates=clean_candidates,resume={'boundary':boundary,'prefix_quanta_reused':boundary,'final_tokens_equal':resume_equal,'remaining_quanta':steps-boundary,'wall_ms':resume_ms,'scope':'Unchanged schedule tail through official custom time_grid API; not variable-schedule prefix equivalence'})
                official_checks=[footprint_route_check(trajectory_reference(trajectory.poses.tolist(),record['origin'],k*.05)['pose'],geom,route,polygon) for k in range(81)]
                row.update(official_final_road_outside_samples=sum(c['outside'] is True for c in official_checks),official_final_road_unknown_samples=sum(c['outside'] is None for c in official_checks),official_parser_matches_strict_numbers=instrumented_parser['numbers']==strict_wam_numbers(decoded[-1]['text']))
                if not resume_equal:raise AssertionError('WAM tail restore changes final tokens')
                run.record({'kind':'real_wam_inference','steps':steps,'seed':args.seed},row);rows.append(row);run.state['evidence_type']=['REAL_VLA','REAL_GPU']
        summary={'real_trials':len(rows),'steps':[r['steps'] for r in rows],'strict_decode_pass':[r['strict_final_decode'] for r in rows],'wall_ms':[r['wall_ms'] for r in rows],'same_schedule_resume_equal':[r['resume']['final_tokens_equal'] for r in rows],'first_two_model_input_hashes':[[e['input_tokens_sha256'] for e in r['model_forward_events'][:2]] for r in rows],'true_progressive_compatibility':'UNKNOWN','official_parser_padding_must_not_count_as_validity':True,'native_platform_equivalence':'NOT_VERIFIED','conclusion':'Keep blocked until complete-road candidate, saved-state continuation and quality benefit verified.'}
        atomic_json(run.path/'metrics/summary.json',summary);return run.finish('PARTIAL',canonical(summary),acceptance='PARTIAL')
    except BaseException:run.log('failure',traceback=traceback.format_exc());return run.finish('BLOCKED',traceback.format_exc(),['Actual WAM runtime failed; see retained exception. No simulated result.'])

UNIDRIVE_REPO=Path(os.environ.get('FRAMELEASE_UNIDRIVE_REPO',ROOT/('third_party/UniDriveVLA-linux' if sys.platform.startswith('linux') else 'third_party/UniDriveVLA')))
UNIDRIVE_ENV=Path(os.environ.get('FRAMELEASE_MODEL_ENV',ROOT/('.conda-unidrive-linux' if sys.platform.startswith('linux') else '.conda-unidrive')))
UNIDRIVE_COMMIT='a93c175af893b35dc16618e659eca4d18bb1ec86'
UNIDRIVE_CONFIG='Bench2Drive/projects/configs/unidrivevla_b2d_stage2_unified_2b.py'
UNIDRIVE_AGENT='Bench2Drive/bench2drive/leaderboard/team_code/unidrivevla_b2d_agent.py'
UNIDRIVE_HEAD='Bench2Drive/projects/mmdet3d_plugin/models/vla/qwenvl3_vla_planning_head.py'

def native_probe(run,name,argv,cwd=None,env=None,timeout=45):
    """Retain exact subprocess output, including dependency/build failures."""
    start=time.perf_counter_ns()
    try:
        p=subprocess.run([str(x) for x in argv],cwd=cwd,env=env,capture_output=True,timeout=timeout)
        result={'returncode':p.returncode,'stdout':p.stdout.decode('utf8','replace'),'stderr':p.stderr.decode('utf8','replace')}
    except subprocess.TimeoutExpired as e:
        result={'returncode':None,'error':'TIMEOUT','stdout':(e.stdout or b'').decode('utf8','replace'),'stderr':(e.stderr or b'').decode('utf8','replace')}
    except OSError as e:result={'returncode':None,'error':repr(e),'stdout':'','stderr':''}
    result.update(name=name,argv=[str(x) for x in argv],cwd=str(cwd or ROOT),wall_s=(time.perf_counter_ns()-start)/1e9)
    atomic_json(run.path/'raw'/(name+'.json'),result);run.record({'kind':'native_probe','name':name},result)
    return result

def unidrive_source_audit():
    """Static contracts from the pinned official source; never an inference result."""
    import ast
    actual=subprocess.check_output(['git','-C',str(UNIDRIVE_REPO),'rev-parse','HEAD'],text=True).strip()
    if actual!=UNIDRIVE_COMMIT:raise ValueError('UniDrive source revision changed')
    tracked_diff=subprocess.check_output(['git','-C',str(UNIDRIVE_REPO),'status','--porcelain','--untracked-files=no'],text=True).strip()
    if tracked_diff:raise ValueError('Pinned UniDrive tracked sources modified: '+tracked_diff)
    paths=[UNIDRIVE_AGENT,UNIDRIVE_CONFIG,UNIDRIVE_HEAD,'LICENSE.txt',
        'Bench2Drive/projects/mmdet3d_plugin/models/detectors/unidrivevla.py',
        'Bench2Drive/projects/mmdet3d_plugin/models/vla/unidrivevla_vlm_qwenvl3.py',
        'Bench2Drive/projects/mmdet3d_plugin/models/vla/unified_perception_decoder.py',
        'Bench2Drive/projects/mmdet3d_plugin/ops/setup.py','docs/installation.md',
        'Bench2Drive/bench2drive/leaderboard/scripts/run_evaluation.sh']
    sources={p:file_hash(UNIDRIVE_REPO/p) for p in paths if (UNIDRIVE_REPO/p).is_file()}
    agent=ast.parse((UNIDRIVE_REPO/UNIDRIVE_AGENT).read_text('utf8'))
    cls=next(n for n in agent.body if isinstance(n,ast.ClassDef) and n.name=='UniDriveVLAB2DAgent')
    sensors=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='sensors')
    sensor_list=next(n.value for n in sensors.body if isinstance(n,ast.Assign) and isinstance(n.value,ast.List))
    sensor_specs=ast.literal_eval(sensor_list)
    head=ast.parse((UNIDRIVE_REPO/UNIDRIVE_HEAD).read_text('utf8'))
    methods={n.name:{'start':n.lineno,'end':n.end_lineno} for n in ast.walk(head) if isinstance(n,ast.FunctionDef) and n.name in ('forward_test','_denoise_step','denorm_delta','embed_prefix','embed_perception')}
    import runpy
    previous_project_dir=os.environ.get('PROJECT_DIR')
    try:
        os.environ['PROJECT_DIR']=str((UNIDRIVE_REPO/'Bench2Drive').resolve())
        cfg=runpy.run_path(str(UNIDRIVE_REPO/UNIDRIVE_CONFIG))
    finally:
        if previous_project_dir is None:os.environ.pop('PROJECT_DIR',None)
        else:os.environ['PROJECT_DIR']=previous_project_dir
    anchors=sorted(set([*cfg['anchor_paths'].values(),cfg['spat_path_6x8_2m'],cfg['spat_path_6x8_5m']]))
    def strings(value):
        if isinstance(value,str):yield value
        elif isinstance(value,dict):
            for item in value.values():yield from strings(item)
        elif isinstance(value,(list,tuple)):
            for item in value:yield from strings(item)
    consumed=set(strings(cfg['model']))
    required_anchors=[p for p in anchors if p in consumed]
    return {'source_commit':actual,'tracked_sources_clean':True,'project_dir_resolved':cfg['project_dir'],'sources':sources,'official_agent':'UniDriveVLAB2DAgent','sensors':sensor_specs,'methods':methods,
        'input':{'camera_count':6,'camera_raw_size_wh':[1600,900],'command_classes':6,'ego_status_dimensions':6,'bev':'official tick() also consumes bev; evaluation/visualization only','navigation':'official route command, despite gt_ego_fut_cmd name; no future trajectory truth supplied'},
        'output':{'shape':[6,2],'units':'metres','frame':'official LiDAR XY; preserve native PID axes','sample_interval_s':.5,'horizon_s':3.,'timing_requires_native_validation':True},
        'anchor_paths':anchors,'anchor_presence':{p:Path(p).is_file() for p in anchors},
        'required_anchor_paths':required_anchors,'declared_but_unused_anchor_paths':[p for p in anchors if p not in consumed],
        'computation':{'shared_prefix_and_perception_kv':True,'action_update':'x_t += (-1/num_steps) * v_t','candidate_export':'denorm_delta and cumulative sum only AFTER flow loop','intermediate_executable_readout_verified':False,'cache_scope':'prefix/perception reuse within native forward; cross-observation temporal banks and RNG not validated','training_stage_is_inference_depth':False},
        'perception':{'internal_outputs':['det','map'],'detector_public_output':'final_planning only; det/map deliberately skipped','deployment_tracking_and_error_bounds_validated':False},
        'model_loaded':False,'adapter_equivalence':'NOT_RUN','quality_gain':'NOT_MEASURED','source_audit_only':True}

def run_unidrive_audit(args):
    if dry_plan(args,[{'mode':'unidrive-audit','source_commit':UNIDRIVE_COMMIT,'interpreter':str(UNIDRIVE_ENV),'operations':['source contracts','GPU availability','native imports','official CUDA extension build','native Agent import']} ]):return 0
    require_conda()
    if Path(sys.prefix).resolve()!=UNIDRIVE_ENV.resolve():raise RuntimeError('Use the separate model Conda: '+str(UNIDRIVE_ENV))
    source=unidrive_source_audit()
    run=StageRun('stage02_real_vla',args,{'mode':args.mode,'source':source,'scope':'native dependency and contract audit'},['SOURCE_AUDIT','ENVIRONMENT_PROBE'],[UNIDRIVE_REPO/p for p in source['sources']])
    try:
        import shutil
        run.record({'kind':'unidrive_source_contract'},source);atomic_json(run.path/'metrics/source_contract.json',source)
        gpu=native_probe(run,'torch_cuda',[sys.executable,'-c',"import torch,json; from torch.utils.cpp_extension import CUDA_HOME; print(json.dumps({'torch':torch.__version__,'cuda':torch.version.cuda,'available':torch.cuda.is_available(),'device':torch.cuda.get_device_name(),'CUDA_HOME':CUDA_HOME}))"])
        probes=[]
        for module in ('carla','mmcv.ops','mmdet','mmdet3d','flash_attn','transformers.models.qwen3_vl'):
            probes.append(native_probe(run,'import_'+module.replace('.','_'),[sys.executable,'-c',f'import {module}; print({module}.__file__)']))
        ops=UNIDRIVE_REPO/'Bench2Drive/projects/mmdet3d_plugin/ops'
        if sys.platform.startswith('linux'):
            import importlib.machinery
            extension=next((ops/('deformable_aggregation_ext'+suffix) for suffix in importlib.machinery.EXTENSION_SUFFIXES if (ops/('deformable_aggregation_ext'+suffix)).is_file()),ops/'extension_not_built')
            probes.append({'name':'official_cuda_build','returncode':0 if extension.is_file() else None,'stderr':'' if extension.is_file() else 'Run bash linux/build_official_ops.sh with the Linux toolchain; no matching Python ABI extension exists'})
        else:
            build_script=ROOT/'audits/route_a/build_official_ops.cmd'
            if build_script.is_file():
                shutil.copy2(build_script,run.path/'raw/build_official_ops.cmd')
                probes.append(native_probe(run,'official_cuda_build',['cmd.exe','/d','/c',build_script],timeout=240))
            else:probes.append({'name':'official_cuda_build','returncode':None,'stderr':'Reproducible build helper missing'})
            extension=ops/'deformable_aggregation_ext.cp310-win_amd64.pyd'
        if extension.is_file():
            # Keep the child ledger shallow: nested 64-character cache keys plus
            # atomic temporary names exceed Win32 MAX_PATH in a nested run tree.
            operator_root=ROOT/'outputs'/('unidrive_ops_'+run.path.name[-8:])
            r=native_probe(run,'official_cuda_operator',[sys.executable,'stage02_real_vla.py','--mode','unidrive-operator','--output-dir',operator_root],timeout=120)
            if r['returncode']==0:
                operator_manifest=verified_manifest(operator_root/'manifest.json')
                atomic_json(run.path/'raw/operator_evidence.json',{'manifest':str(Path(operator_manifest['run_dir'])/'manifest.json'),'sha256':file_hash(Path(operator_manifest['run_dir'])/'manifest.json'),'status':operator_manifest['status'],'scope':'OPERATOR_ONLY'})
            probes.append({**r,'name':'official_cuda_operator'})
        b2d=UNIDRIVE_REPO/'Bench2Drive';env=os.environ.copy()
        env['PYTHONPATH']=os.pathsep.join(str(p) for p in (b2d,b2d/'bench2drive',b2d/'bench2drive/leaderboard',b2d/'bench2drive/scenario_runner',Path(os.environ.get('CARLA_ROOT',str(Path.home()/'opt/CARLA_0.9.15')))/'PythonAPI/carla'))+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
        env.update(IS_BENCH2DRIVE='1',PLANNER_TYPE='traj',IS_VISUALIZE='0')
        probes.append(native_probe(run,'official_agent_import',[sys.executable,'-c','from team_code.unidrivevla_b2d_agent import UniDriveVLAB2DAgent; print(UniDriveVLAB2DAgent)'],cwd=b2d,env=env))
        probe_tools={'commands':{n:shutil.which(n) for n in ('nvcc','gcc','g++','cmake','ninja','nvidia-smi','bash')},'CUDA_HOME':os.environ.get('CUDA_HOME'),'model_env':str(UNIDRIVE_ENV),'source_root':str(UNIDRIVE_REPO)}
        atomic_json(run.path/'raw/compiler_paths.json',probe_tools)
        blockers=[p['name']+': '+(p['stderr'].strip().splitlines()[-1] if p['stderr'].strip() else p.get('error','nonzero exit')) for p in probes if p['returncode']!=0]
        if gpu['returncode']!=0:blockers.append('CUDA GPU unavailable: '+(gpu['stderr'].strip().splitlines()[-1] if gpu['stderr'].strip() else gpu.get('error','probe failed')))
        missing=[p for p in source['required_anchor_paths'] if not source['anchor_presence'][p]]
        if missing:blockers.append('Missing official anchors: '+', '.join(missing))
        result={'source_commit':UNIDRIVE_COMMIT,'model_loaded':False,'native_imports_passed':not any(p['returncode']!=0 for p in probes if p['name'].startswith('import_')),'official_cuda_extension_build_passed':next((p['returncode']==0 for p in probes if p['name']=='official_cuda_build'),False),'official_cuda_operator_passed':next((p['returncode']==0 for p in probes if p['name']=='official_cuda_operator'),False),'gpu_probe_success':gpu['returncode']==0,'blockers':blockers,'official_sample_executed':False,'progressive_status':'PROGRESSIVE_VLA_BLOCKED','critical_environment_blocker':any(p['name'].startswith('import_') and p['returncode']!=0 for p in probes),'native_platform_equivalence':'NOT_VERIFIED','python_compatibility':'Python3.10 with official cp310 CARLA0.9.15 and torch2.5.1; recipe Python3.8 conflict documented; full equivalence NOT_VERIFIED'}
        run.record({'kind':'unidrive_backend_readiness'},result);atomic_json(run.path/'metrics/backend_readiness.json',result)
        return run.finish('BLOCKED' if blockers else 'PARTIAL',canonical(result),blockers,acceptance='BLOCKED')
    except BaseException:run.log('failure',traceback=traceback.format_exc());return run.finish('FAILED',traceback.format_exc())

def checkpoint_tensor_inventory(checkpoint):
    """Honor the official DeepSpeed container; an empty inventory is an audit error."""
    import torch
    if not isinstance(checkpoint,dict):raise ValueError('Checkpoint must be a mapping')
    state=checkpoint.get('module',checkpoint.get('state_dict',checkpoint))
    if not isinstance(state,dict):raise ValueError('Checkpoint tensor container must be a mapping')
    rows=[{'name':k,'shape':list(v.shape),'dtype':str(v.dtype),'numel':v.numel()} for k,v in state.items() if isinstance(v,torch.Tensor)]
    if not rows:raise ValueError('Checkpoint inventory has zero tensors; unknown container, not a successful parameter audit')
    return rows

def run_unidrive_resources(args):
    """Pinned public resources, bounded acquisition, safe CPU checkpoint inventory."""
    meta=read_json(ROOT/'audits/route_a/unidrive_weights.json');f=next(x for x in meta['files'] if x['name'].endswith('.pt'))
    target=ROOT/'checkpoints/UniDriveVLA'/meta['revision']/f['name']
    if dry_plan(args,[{'target':str(target),'bytes':f['size'],'revision':meta['revision'],'sha256':f['lfs']['sha256'],'max_60s_download_attempts':args.download_attempts}]):return 0
    require_conda()
    if Path(sys.prefix).resolve()!=UNIDRIVE_ENV.resolve():raise RuntimeError('Use .conda-unidrive for new model resources')
    run=StageRun('stage02_real_vla',args,{'mode':args.mode,'resource':meta,'target':str(target),'bounded_attempts':args.download_attempts},['OFFICIAL_RESOURCE_AUDIT'],[ROOT/'stage00_environment.py',ROOT/'audits/route_a/unidrive_weights.json'])
    try:
        from stage00_environment import download_file
        with writer_lock(target.parent):
            r=download_file('https://huggingface.co/owl10/UniDriveVLA_B2D_Base_Stage3/resolve/'+meta['revision']+'/'+f['name'],target,f['size'],f['lfs']['sha256'],retries=args.download_attempts)
        run.record({'kind':'official_checkpoint_download'},r)
        if r['status']!='COMPLETED':return run.finish('BLOCKED',canonical(r),['Checkpoint download incomplete; partial retained'])
        import torch
        # Static pickle GLOBAL inventory is retained; only the builtin set container
        # is missing from torch2.5's weights-only allowlist. Never enable arbitrary pickle.
        import zipfile,pickletools
        with zipfile.ZipFile(target) as z:
            pickle_name=next(n for n in z.namelist() if n.endswith('data.pkl'))
            globals_used=sorted({arg for op,arg,pos in pickletools.genops(z.read(pickle_name)) if op.name=='GLOBAL'})
        atomic_json(run.path/'raw/checkpoint_pickle_globals.json',globals_used)
        with torch.serialization.safe_globals([set]):
            checkpoint=torch.load(target,map_location='cpu',weights_only=True,mmap=True)
        rows=checkpoint_tensor_inventory(checkpoint)
        if isinstance(checkpoint.get('config'),str):(run.path/'raw/checkpoint_training_config.txt').write_text(checkpoint['config'],encoding='utf8')
        atomic_json(run.path/'raw/checkpoint_metadata.json',{k:checkpoint.get(k) for k in ('shared_params','buffer_names','epoch','iter','seed','ds_version','mmdet_version','exp_name')})
        write_csv(run.path/'metrics/checkpoint_tensors.csv',rows)
        result={'path':str(target),'sha256':r['sha256'],'tensor_count':len(rows),'stored_tensor_elements':sum(x['numel'] for x in rows),'model_instantiated':False,'strict_loading_coverage':'NOT_VERIFIED_REQUIRES_INSTANTIATED_NATIVE_MODEL','top_level_keys':list(checkpoint)[:20],'planning_key_count':sum('planning_head' in x['name'] for x in rows),'action_expert_key_count':sum('action_expert' in x['name'] for x in rows),'perception_expert_key_count':sum('perception_expert' in x['name'] for x in rows),'license':'Official code LICENSE.txt Apache-2.0; checkpoint HF card has no separate license metadata; do not assume redistribution/training terms'}
        run.record({'kind':'official_checkpoint_inventory'},result);atomic_json(run.path/'metrics/checkpoint_inventory.json',result)
        return run.finish('PARTIAL',canonical(result),['Resource inspection is not full model loading or inference'],acceptance='PARTIAL')
    except BaseException:run.log('failure',traceback=traceback.format_exc());return run.finish('FAILED',traceback.format_exc())

def run_unidrive_base_resources(args):
    meta=read_json(ROOT/'audits/route_a/qwen.json');raw=read_json(ROOT/'audits/route_a/qwen.raw')
    if raw['sha']!=meta['revision']:raise ValueError('Qwen resource metadata revision mismatch')
    needed=('config.json','model.safetensors','preprocessor_config.json','video_preprocessor_config.json','generation_config.json','tokenizer.json','tokenizer_config.json','chat_template.json','merges.txt','vocab.json')
    files=[{'name':row['rfilename'],'size':row['size'],'lfs':row.get('lfs'),'git_blob_sha1':row['blobId']} for name in needed for row in raw['siblings'] if row['rfilename']==name]
    if len(files)!=len(needed):raise ValueError('Incomplete pinned resource metadata')
    target=ROOT/'checkpoints/Qwen3-VL-2B-Instruct'/meta['revision']
    if dry_plan(args,[{'target':str(target/f['name']),'bytes':f['size'],'revision':meta['revision'],'sha256':(f.get('lfs') or {}).get('sha256')} for f in files]):return 0
    if Path(sys.prefix).resolve()!=UNIDRIVE_ENV.resolve():raise RuntimeError('Use .conda-unidrive for new model resources')
    run=StageRun('stage02_real_vla',args,{'mode':args.mode,'repo':'Qwen/Qwen3-VL-2B-Instruct','revision':meta['revision'],'files':files,'attempts':args.download_attempts},['OFFICIAL_RESOURCE_AUDIT'],[ROOT/'stage00_environment.py',ROOT/'audits/route_a/qwen.json',ROOT/'audits/route_a/qwen.raw'])
    try:
        from stage00_environment import download_file
        results=[]
        with writer_lock(target):
            for f in files:
                path=target/f['name'];result=download_file('https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/resolve/'+meta['revision']+'/'+f['name'],path,f['size'],(f.get('lfs') or {}).get('sha256'),retries=args.download_attempts)
                result.update(name=f['name'],bytes=path.stat().st_size if path.exists() else None,sha256=file_hash(path) if path.exists() else None,expected_sha256=(f.get('lfs') or {}).get('sha256'))
                if result['status']=='COMPLETED' and not f.get('lfs'):
                    import hashlib
                    content=path.read_bytes();actual=hashlib.sha1(('blob '+str(len(content))+'\0').encode()+content).hexdigest()
                    result.update(git_blob_sha1=actual,expected_git_blob_sha1=f['git_blob_sha1'])
                    if actual!=f['git_blob_sha1']:raise ValueError('Pinned Git blob checksum mismatch: '+f['name'])
                results.append(result)
                run.record({'kind':'qwen_base_resource','name':f['name']},result,'COMPLETED' if result['status']=='COMPLETED' else 'BLOCKED',None if result['status']=='COMPLETED' else 'bounded public download incomplete; partial retained')
                if result['status']!='COMPLETED':break
        complete=len(results)==len(files) and all(r['status']=='COMPLETED' for r in results)
        atomic_json(run.path/'metrics/qwen_resources.json',{'repo':'Qwen/Qwen3-VL-2B-Instruct','revision':meta['revision'],'license':'Apache-2.0','resources':results,'all_verified':complete,'aggregate_bytes':sum(r['bytes'] or 0 for r in results)})
        return run.finish('PARTIAL' if complete else 'BLOCKED',canonical({'resources':results,'all_verified':complete}),[] if complete else ['At least one pinned Qwen base resource is incomplete'])
    except BaseException:run.log('failure',traceback=traceback.format_exc());return run.finish('FAILED',traceback.format_exc())

def run_unidrive_data_audit(args):
    """Verify official annotations and recover exact checkpoint anchor values only.

    This does not train, construct a sample, or install recovered anchors into
    the official source. Missing images/splits cannot be replaced by JSONL text.
    """
    meta=read_json(ROOT/'audits/route_a/unidrive_data.json')
    f=next(x for x in meta['files'] if x['name']=='b2d_traj_train.jsonl')
    target=ROOT/'datasets/UniDriveVLA'/meta['revision']/f['name']
    if dry_plan(args,[{'annotation':str(target),'revision':meta['revision'],'scope':'resource and schema audit only; no training'}]):return 0
    if Path(sys.prefix).resolve()!=UNIDRIVE_ENV.resolve():raise RuntimeError('Use .conda-unidrive')
    source=unidrive_source_audit();wm=verified_manifest(ROOT/'outputs/stage02_unidrive_resources/manifest.json')
    inventory=read_json(Path(wm['run_dir'])/'metrics/checkpoint_inventory.json')
    run=StageRun('stage02_real_vla',args,{'mode':args.mode,'backend':'UniDriveVLA','annotation':meta,'source':source,'checkpoint':inventory},['OFFICIAL_RESOURCE_AUDIT'],[ROOT/'stage00_environment.py',ROOT/'audits/route_a/unidrive_data.json'])
    try:
        from stage00_environment import download_file
        with writer_lock(target.parent):
            download=download_file('https://huggingface.co/datasets/owl10/UniDriveVLA_Data/resolve/'+meta['revision']+'/'+f['name'],target,f['size'],f['lfs']['sha256'],retries=args.download_attempts)
        run.record({'kind':'official_annotation_download'},download)
        if download['status']!='COMPLETED':return run.finish('BLOCKED',canonical(download),['Official annotations incomplete; partial retained'])
        from collections import Counter
        routes=Counter();camera_counts=Counter();count=0;duplicates=0;seen=set();missing=0;refs=0;prompt_4s=0
        data_root=UNIDRIVE_REPO/'Bench2Drive';image_root_exists=(data_root/'data/bench2drive').is_dir()
        with target.open(encoding='utf8') as handle:
            for line in handle:
                row=json.loads(line);images=row.get('image',[])
                if not isinstance(images,list) or not all(isinstance(p,str) for p in images):raise ValueError('Invalid annotation image references')
                count+=1;camera_counts[len(images)]+=1;refs+=len(images)
                key=digest(images);duplicates+=int(key in seen);seen.add(key)
                for p in images:
                    if Path(p).is_absolute() or '..' in Path(p).parts:raise ValueError('Unsafe image reference')
                    missing+=int(not image_root_exists or not (data_root/p).is_file())
                if images:
                    parts=Path(images[0]).parts
                    routes[parts[3] if len(parts)>3 else 'UNKNOWN']+=1
                prompt_4s+=int(any('4-second' in x.get('value','') for x in row.get('conversations',[]) if x.get('from')=='system'))
        write_csv(run.path/'metrics/annotation_routes.csv',[{'route':route,'records':n} for route,n in sorted(routes.items())])
        import torch,numpy as np
        checkpoint_path=Path(inventory['path'])
        if file_hash(checkpoint_path)!=inventory['sha256']:raise ValueError('Checkpoint content changed')
        with torch.serialization.safe_globals([set]):checkpoint=torch.load(checkpoint_path,map_location='cpu',weights_only=True,mmap=True)
        state=checkpoint['module'];anchors=[]
        for filename,key in [('b2d_det_900.npy','planning_head.unified_decoder.det_instance_bank.anchor'),('b2d_map_100.npy','planning_head.unified_decoder.map_instance_bank.anchor'),('b2d_motion_6.npy','planning_head.unified_decoder.motion_anchor')]:
            value=state[key].detach().float().cpu().numpy()
            path=run.path/'raw'/filename;np.save(path,value,allow_pickle=False)
            if not np.array_equal(np.load(path,allow_pickle=False),value) or not np.isfinite(value).all():raise ValueError('Recovered anchor verification failed')
            anchors.append({'filename':filename,'key':key,'shape':list(value.shape),'stored_dtype':str(state[key].dtype),'export_dtype':str(value.dtype),'sha256':file_hash(path),'installed_in_official_source':False,'original_kmeans_file_equivalence':'NOT_VERIFIED; exact checkpoint values only'})
        result={'annotation_revision':meta['revision'],'annotation_path':str(target),'annotation_sha256':download['sha256'],'complete_annotation_verified':True,'records':count,'unique_image_sets':len(seen),'duplicate_image_sets':duplicates,'camera_count_histogram':dict(camera_counts),'referenced_image_entries':refs,'missing_image_entries_at_official_local_root':missing,'image_root':str(data_root/'data/bench2drive'),'unique_route_directories':len(routes),'system_prompt_4_second_count':prompt_4s,'timing_conflict':'JSONL system prompt says 4-second; human asks six points. Do not override native head/PID contract; physical time validation pending','hf_annotation_license':meta.get('card',{}).get('license'),'raw_bench2drive_images_license':'separate upstream resource; not conveyed by annotation card','released_annotation_files':[x['name'] for x in meta['files']],'b2d_validation_test_splits':'NOT_PROVIDED in this annotation repository; nuScenes val is not B2D val','train_validation_test_disjointness':'NOT_VERIFIED','native_sample_ready':False,'training_authorized_by_evidence':False,'recovered_anchors':anchors,'declared_unused_spatial_anchors':source['declared_but_unused_anchor_paths'],'full_model_loaded':False}
        atomic_json(run.path/'metrics/data_readiness.json',result);run.record({'kind':'official_data_readiness'},result)
        return run.finish('PARTIAL',canonical(result),['Real six-camera images/calibration and independent B2D train/validation/test not verified; native Gate1 still blocked'],acceptance='RESOURCE_AUDIT_ONLY')
    except BaseException:run.log('failure',traceback=traceback.format_exc());return run.finish('FAILED',traceback.format_exc())

def run_unidrive_operator(args):
    """Real compiled official operator, constant numerical fixture; not model inference."""
    ops=UNIDRIVE_REPO/'Bench2Drive/projects/mmdet3d_plugin/ops'
    if dry_plan(args,[{'operation':'official deformable CUDA forward/backward','scope':'OPERATOR_DIAGNOSTIC_ONLY'}]):return 0
    source=unidrive_source_audit()
    run=StageRun('stage02_real_vla',args,{'mode':args.mode,'backend':'UniDriveVLA','source':source['source_commit'],'scope':'CUDA_OPERATOR_ONLY'},['REAL_GPU_OPERATOR_DIAGNOSTIC'],[ops/'src/deformable_aggregation.cpp',ops/'src/deformable_aggregation_cuda.cu'])
    try:
        import torch
        if not torch.cuda.is_available():
            return run.finish('BLOCKED','CUDA device/driver unavailable; compiled operator was not executed.', ['CUDA device/driver unavailable'],acceptance='BLOCKED')
        sys.path.insert(0,str(ops));import deformable_aggregation_ext as extension
        with writer_lock(ROOT/'results/shared_gpu_resource'):
            feat=torch.ones((1,24,4),device='cuda');shape=torch.tensor([[[2,2]]]*6,device='cuda',dtype=torch.int32)
            starts=torch.tensor([[i*4] for i in range(6)],device='cuda',dtype=torch.int32)
            loc=torch.full((1,1,1,6,2),.5,device='cuda');weights=torch.ones((1,1,1,6,1,1),device='cuda')
            a,b=torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True)
            a.record();out=extension.deformable_aggregation_forward(feat,shape,starts,loc,weights);b.record();b.synchronize()
            grads=[torch.zeros_like(x) for x in (feat,loc,weights)]
            extension.deformable_aggregation_backward(feat,shape,starts,loc,weights,torch.ones_like(out),*grads);torch.cuda.synchronize()
            result={'device':torch.cuda.get_device_name(),'torch':torch.__version__,'extension':extension.__file__,'binary_sha256':file_hash(extension.__file__),'output':out.cpu().tolist(),'expected':[[[6.,6.,6.,6.]]],'forward_max_error':float((out-6).abs().max()),'backward_finite':all(bool(torch.isfinite(g).all()) for g in grads),'feature_grad_sum':float(grads[0].sum()),'weight_grad':grads[2].cpu().tolist(),'cuda_forward_ms':a.elapsed_time(b),'timing_scope':'single cold CUDA operator call; not VLA latency','model_loaded':False,'model_output_used':False,'scope':'constant tensor numerical unit fixture only; no driving/anytime claim'}
        atomic_json(run.path/'metrics/operator.json',result);run.record({'kind':'native_cuda_operator'},result)
        if result['forward_max_error']>1e-6 or not result['backward_finite'] or abs(result['feature_grad_sum']-24)>1e-6:raise AssertionError('Official operator numerical check failed')
        return run.finish('COMPLETED',canonical(result),acceptance='OPERATOR_ONLY')
    except BaseException:run.log('failure',traceback=traceback.format_exc());return run.finish('FAILED',traceback.format_exc())

def b2d_future_targets(infos,capture,steps=6,interval_s=.5):
    """Offline GT supervision only. Explicit time and both-endpoint masks."""
    import numpy as np
    if steps!=6 or interval_s!=.5:raise ValueError('Frozen six-point/3s contract required')
    folder=capture['folder'];frame=int(capture['frame_idx']);index={}
    for r in infos:
        key=(r['folder'],int(r['frame_idx']))
        if key in index:raise ValueError('Duplicate annotation frame')
        index[key]=r
    ids=np.asarray(capture['gt_ids']);transform=np.asarray(capture['sensors']['LIDAR_TOP']['world2lidar'])
    if transform.shape!=(4,4) or not np.isfinite(transform).all():raise ValueError('Invalid capture transform')
    n=len(ids);origins=np.zeros((n,steps+1,2));centers=np.zeros_like(origins);present=np.zeros((n,steps+1),dtype=bool);reasons=[];times=[]
    for j in range(steps+1):
        target=frame+int(round(j*interval_s*10));r=index.get((folder,target));times.append(j*interval_s)
        if r is None:reasons.append('MISSING_FRAME');continue
        rids=np.asarray(r['gt_ids'])
        if len(set(rids.tolist()))!=len(rids):raise ValueError('Duplicate actor id')
        world_from_lidar=np.linalg.inv(np.asarray(r['sensors']['LIDAR_TOP']['world2lidar']))
        if not np.isfinite(world_from_lidar).all():raise ValueError('Invalid future transform')
        reasons.append('PRESENT')
        for i,actor in enumerate(ids):
            found=np.where(rids==actor)[0]
            if not len(found):continue
            k=int(found[0]);origin=transform@np.asarray(r['npc2world'][k]);center=transform@world_from_lidar@np.r_[np.asarray(r['gt_boxes'][k])[:3],1.]
            if not np.isfinite(origin).all() or not np.isfinite(center).all():raise ValueError('Nonfinite supervised geometry')
            origins[i,j]=origin[:2,3];centers[i,j]=center[:2];present[i,j]=True
    mask=present[:,1:]&present[:,:-1];delta=np.diff(origins,axis=1);delta[~mask]=0
    velocity=delta/interval_s;acc_mask=mask[:,1:]&mask[:,:-1];acceleration=np.diff(velocity,axis=1)/interval_s;acceleration[~acc_mask]=0
    return {'actor_ids':ids.tolist(),'future_seconds':times[1:],'origin_delta_xy':delta.tolist(),'box_center_absolute_xy':centers[:,1:].tolist(),'absolute_position_mask':present[:,1:].tolist(),'delta_mask':mask.tolist(),'velocity_xy_mps':velocity.tolist(),'acceleration_xy_mps2':acceleration.tolist(),'acceleration_mask':acc_mask.tolist(),'future_frame_reasons':reasons[1:],'scope':'OFFLINE_GT_SUPERVISION_ONLY_NOT_ONLINE_INPUT','origin_reference':'actor_transform_origin; box_center separately retained','safety_certified':False}

def b2d_dynamic_box_targets(capture,raw_annotations):
    """Recorded future cuboids in capture LiDAR frame; OFFLINE GT only."""
    import numpy as np
    from shapely.geometry import MultiPoint
    transform=np.asarray(capture['sensors']['LIDAR_TOP']['world2lidar'],dtype=float)
    if transform.shape!=(4,4) or not np.isfinite(transform).all():raise ValueError('Invalid capture transform')
    frame=int(capture['frame_idx']);now_ann=raw_annotations[frame]
    def corners(box):
        xyz=np.asarray(box.get('world_cord'),dtype=float)
        if xyz.shape!=(8,3) or not np.isfinite(xyz).all():return None
        xyz=xyz*np.array([1.,-1.,1.]);return (transform@np.c_[xyz,np.ones(8)].T).T[:,:3]
    def polygon(xyz):return MultiPoint(xyz[:,:2]).convex_hull
    actors={int(o['id']):o for o in now_ann['bounding_boxes'] if o['class'] in ('vehicle','walker')};rows=[];future=[]
    if len(actors)!=sum(o['class'] in ('vehicle','walker') for o in now_ann['bounding_boxes']):raise ValueError('Duplicate capture actor')
    visible={int(x) for x in capture['gt_ids']}
    for j in range(1,7):
        target_frame=frame+5*j;ann=raw_annotations.get(target_frame)
        hero=next((o for o in ann['bounding_boxes'] if o['class']=='ego_vehicle'),None) if ann else None;ego=corners(hero) if hero else None
        objects={int(o['id']):o for o in ann['bounding_boxes'] if o['class'] in ('vehicle','walker')} if ann else {}
        body={'delay_s':.5*j,'frame_idx':target_frame,'future_frame_present':ann is not None,'ego_world_corners_in_capture_lidar':ego.tolist() if ego is not None else None,'ego_body_center_xy':ego.mean(0)[:2].tolist() if ego is not None else None,'actors':[]}
        for actor,captured in actors.items():
            present=objects.get(actor);static=corners(captured);dynamic=corners(present) if present else None
            valid=ego is not None and static is not None and dynamic is not None
            row={'capture_frame':frame,'actor_id':actor,'actor_class':captured['class'],'delay_s':.5*j,'capture_visible_converter_subset':actor in visible,'future_frame_present':ann is not None,'future_actor_present':present is not None,'valid_cuboids':valid,'recorded_static_overlap':None,'recorded_dynamic_overlap':None,'target_displacement_m':None}
            if valid:
                row.update(recorded_static_overlap=polygon(ego).intersects(polygon(static)),recorded_dynamic_overlap=polygon(ego).intersects(polygon(dynamic)),target_displacement_m=float(np.linalg.norm(dynamic.mean(0)[:2]-static.mean(0)[:2])))
            body['actors'].append({'id':actor,'class':captured['class'],'capture_visible_converter_subset':actor in visible,'future_corners':dynamic.tolist() if dynamic is not None else None,'future_mask':dynamic is not None})
            rows.append(row)
        future.append(body)
    return {'capture_frame':frame,'coordinate_frame':'CAPTURE_LIDAR_RIGHT_HANDED','scope':'OFFLINE_GT_SUPERVISION_ONLY_NOT_ONLINE_INPUT','future':future},rows

B2D_CAMERAS=('CAM_FRONT','CAM_FRONT_LEFT','CAM_FRONT_RIGHT','CAM_BACK','CAM_BACK_LEFT','CAM_BACK_RIGHT')
B2D_MODEL_KEYS=frozenset(('img','img_metas','projection_mat','ego_status','gt_ego_fut_cmd','image_wh','timestamp','rescale','return_loss'))

def b2d_ego_targets(infos,capture):
    """Future recorded LiDAR origins; missing endpoints never become zero truth."""
    import numpy as np
    index={}
    for r in infos:
        key=(r['folder'],int(r['frame_idx']))
        if key in index:raise ValueError('Duplicate annotation frame')
        index[key]=r
    transform=np.asarray(capture['sensors']['LIDAR_TOP']['world2lidar'],dtype=float)
    if transform.shape!=(4,4) or not np.isfinite(transform).all():raise ValueError('Invalid capture transform')
    positions=np.zeros((7,2));valid=np.zeros(7,dtype=bool);reasons=[]
    for j in range(7):
        record=index.get((capture['folder'],int(capture['frame_idx'])+5*j))
        if record is None:reasons.append('MISSING_FRAME');continue
        future=np.asarray(record['sensors']['LIDAR_TOP']['world2lidar'],dtype=float)
        if future.shape!=(4,4) or not np.isfinite(future).all():raise ValueError('Invalid future transform')
        positions[j]=(transform@np.linalg.inv(future))[:2,3];valid[j]=True;reasons.append('PRESENT')
    mask=valid[:-1]&valid[1:];delta=np.diff(positions,axis=0);delta[~mask]=0
    return {'absolute_xy':positions[1:].tolist(),'absolute_mask':valid[1:].tolist(),'delta_xy':delta.tolist(),'delta_mask':mask.tolist(),'contiguous_prefix_mask':np.logical_and.accumulate(valid)[1:].tolist(),'future_frame_indices':[int(capture['frame_idx'])+5*j for j in range(1,7)],'future_seconds':[.5*j for j in range(1,7)],'reasons':reasons[1:],'reference':'RECORDED_LIDAR_ORIGIN_IN_CAPTURE_LIDAR','scope':'OFFLINE_EXPERT_TARGET_ONLY'}

def b2d_current_input_spec(capture,data_root):
    """Explicit current-only whitelist. Recorded pose is offline teacher forcing."""
    import numpy as np
    frame=int(capture['frame_idx']);folder=capture['folder'];paths=[];projections=[];cam_transforms=[]
    root=Path(data_root).resolve();lidar=capture['sensors']['LIDAR_TOP'];l2e=np.asarray(lidar['lidar2ego'],dtype=float);w2l=np.asarray(lidar['world2lidar'],dtype=float)
    for t in (l2e,w2l):
        if t.shape!=(4,4) or not np.isfinite(t).all():raise ValueError('Invalid current transform')
    for camera in B2D_CAMERAS:
        sensor=capture['sensors'][camera];relative=Path(sensor['data_path'])
        if relative.is_absolute() or '..' in relative.parts or relative.stem!=f'{frame:05d}' or str(relative.parent.parent.parent)!=folder:raise ValueError('Image does not belong to current clip/frame')
        path=root/relative
        if not path.is_file():raise DependencyBlocked('Current camera missing: '+str(path))
        c2e=np.asarray(sensor['cam2ego'],dtype=float);intrinsic=np.asarray(sensor['intrinsic'],dtype=float)
        if c2e.shape!=(4,4) or intrinsic.shape!=(3,3) or not np.isfinite(c2e).all() or not np.isfinite(intrinsic).all():raise ValueError('Invalid camera calibration')
        cam=np.linalg.inv(c2e)@l2e;K=np.eye(4);K[:3,:3]=intrinsic;projections.append((K@cam).tolist());cam_transforms.append(cam.T.tolist());paths.append(str(path))
    command=int(capture['command_near'])
    if command<0:command=4
    if command not in range(1,7):raise ValueError('Invalid navigation command')
    onehot=np.eye(6,dtype=np.float32)[command-1]
    status=np.r_[capture['ego_vel'][0],np.asarray(capture['ego_accel'])[:2],np.asarray(capture['ego_rotation_rate'])[:2],capture['steer']]
    if status.shape!=(6,) or not np.isfinite(status).all():raise ValueError('Invalid current ego status')
    return {'sample_id':f'{folder}/{frame:05d}','folder':folder,'scene_token':folder,'frame_idx':frame,'timestamp':frame/10.,'camera_order':list(B2D_CAMERAS),'image_paths':paths,'image_sha256':[file_hash(p) for p in paths],'lidar2img':projections,'lidar2cam':cam_transforms,'lidar2global':np.linalg.inv(w2l).tolist(),'ego_status':status.tolist(),'gt_ego_fut_cmd':onehot.tolist(),'input_scope':'OFFLINE_DATASET_CURRENT_OBSERVATION_WITH_RECORDED_POSE_AND_PREVIOUS_EXPERT_CONTROL','future_truth_in_model_input':False}

def b2d_contract_source():
    """Resolve immutable, verified source run; do not silently use unrelated clips."""
    import pickle,gzip
    path=ROOT/'outputs/linux_b2d_supervision_audit_20261106/manifest.json';manifest=verified_manifest(path);base=Path(manifest['run_dir']);infos_path=base/'raw/infos/contract_development/b2d_infos_train_0.pkl'
    infos=pickle.loads(infos_path.read_bytes());clip=manifest['identity']['config']['clip'];data_root=base/'raw/official_data';clip_root=data_root/'v1'/clip
    hashes=read_json(base/'raw/input_hashes.json')
    for p,h in hashes.items():
        if file_hash(p)!=h:raise ValueError('Original clip input changed: '+p)
    annotations={int(p.name.split('.')[0]):json.load(gzip.open(p,'rt')) for p in (clip_root/'anno').glob('*.json.gz')}
    return path,base,infos_path,infos,data_root,annotations

def run_b2d_map_audit(args):
    if dry_plan(args,[{'operation':'official map resource limit and separately labeled local OpenDRIVE audit','download':False}]):return 0
    import numpy as np,collections,xml.etree.ElementTree as ET
    audit=ROOT/'audits/dac2027_map_alignment_20261106';metadata=audit/'discovery/map_mirror.raw';meta=read_json(metadata);resource=next(r for r in meta['siblings'] if r['rfilename']=='Town11_HD_map.npz')
    xodr=Path(os.environ['CARLA_ROOT'])/'CarlaUE4/Content/Carla/Maps/Town11/OpenDrive/Town11.xodr'
    path,base,infos_path,infos,data_root,annotations=b2d_contract_source()
    config={'mode':args.mode,'official_map_revision':meta['sha'],'official_file':resource,'download_budget_bytes':1024**3,'official_map_download_status':'BLOCKED_BUDGET' if resource['size']>1024**3 else 'NOT_DOWNLOADED','local_xodr':str(xodr),'local_xodr_sha256':file_hash(xodr),'source_manifest':str(base/'manifest.json'),'source_manifest_sha256':file_hash(base/'manifest.json'),'scope':'OFFLINE_LOCAL_CARLA_OPENDRIVE_ALIGNMENT_NOT_OFFICIAL_HD_MAP_EQUIVALENCE','gate_promoted':False}
    run=StageRun('stage02_real_vla',args,config,['OFFICIAL_METADATA_AUDIT','LOCAL_OPENDRIVE_GEOMETRY_DIAGNOSTIC'],[metadata,audit/'PROTOCOL.md',audit/'INPUT_CONTRACT.md',Path(os.environ['FRAMELEASE_BENCHMARK_ROOT'])/'docs/anno.md']);run.path=run.path.resolve()
    try:
        import carla
        model=carla.Map('Town11',xodr.read_text());xml=ET.parse(xodr);road_lengths={int(r.attrib['id']):float(r.attrib['length']) for r in xml.findall('road')};types_count=collections.Counter(l.attrib['type'] for l in xml.findall('.//lane'));width_records=len(xml.findall('.//lane/width'))
        rows=[];ribbons={}
        for frame,ann in sorted(annotations.items()):
            ego=next(o for o in ann['bounding_boxes'] if o['class']=='ego_vehicle');location=carla.Location(*ego['location']);wp=model.get_waypoint(location,True,carla.LaneType.Driving)
            row={'frame_idx':frame,'recorded_road_id':ego['road_id'],'recorded_lane_id':ego['lane_id'],'recorded_section_id':ego['section_id'],'local_map_found':wp is not None}
            if wp is not None:
                loc=wp.transform.location;right=wp.transform.get_right_vector();delta=np.array([location.x-loc.x,location.y-loc.y]);lateral=float(delta@np.array([right.x,right.y]));member=model.get_waypoint(location,False,carla.LaneType.Driving)
                corner_valid=[];corner_z=[]
                for xyz in ego['world_cord']:
                    w=model.get_waypoint(carla.Location(*xyz),False,carla.LaneType.Driving);corner_valid.append(w is not None);corner_z.append(abs(xyz[2]-w.transform.location.z) if w is not None else None)
                row.update(map_road_id=wp.road_id,map_lane_id=wp.lane_id,map_section_id=wp.section_id,ids_match=(wp.road_id==ego['road_id'] and wp.lane_id==ego['lane_id'] and wp.section_id==ego['section_id']),signed_lateral_m=lateral,lane_width_m=wp.lane_width,reference_height_error_m=abs(location.z-loc.z),is_junction=wp.is_junction,origin_in_driving_lane=member is not None,body_vertices_in_driving_lane=sum(corner_valid),body_vertex_max_height_above_road_m=max((z for z in corner_z if z is not None),default=None))
                # Offline sampled lane edges only. Do not join separate lanes or
                # junctions into an asserted physical free-space boundary.
                for s in np.arange(max(0.,math.floor(wp.s)-35),min(road_lengths[wp.road_id],math.floor(wp.s)+35),.5):
                    key=(wp.road_id,wp.lane_id,float(s))
                    if key in ribbons:continue
                    w=model.get_waypoint_xodr(*key)
                    if w is None or w.lane_type!=carla.LaneType.Driving:continue
                    center=w.transform.location;normal=w.transform.get_right_vector();c=np.array([center.x,center.y,center.z]);n=np.array([normal.x,normal.y,normal.z]);half=w.lane_width/2
                    ribbons[key]={'road_id':w.road_id,'lane_id':w.lane_id,'section_id':w.section_id,'s':w.s,'width_m':w.lane_width,'is_junction':w.is_junction,'center_carla_lh':c.tolist(),'left_edge_carla_lh':(c-half*n).tolist(),'right_edge_carla_lh':(c+half*n).tolist(),'left_marking':str(w.left_lane_marking.type),'right_marking':str(w.right_lane_marking.type)}
            rows.append(row)
        write_csv(run.path/'metrics/recorded_ego_vs_opendrive.csv',rows)
        with (run.path/'raw/local_lane_samples.jsonl').open('w') as f:
            for r in ribbons.values():f.write(canonical(r)+'\n')
        atomic_json(run.path/'raw/annotation_hashes.json',{str(data_root/'v1'/infos[0]['folder'].split('/')[-1]/'anno'/f'{f:05d}.json.gz'):file_hash(data_root/'v1'/infos[0]['folder'].split('/')[-1]/'anno'/f'{f:05d}.json.gz') for f in annotations})
        result={'official_map_download_status':config['official_map_download_status'],'official_map_bytes':resource['size'],'official_map_sha256':resource['lfs']['sha256'],'local_xodr_bytes':xodr.stat().st_size,'carla_python_version':getattr(carla,'__version__','0.9.15 installed egg; see environment evidence'),'xml_lane_types':dict(types_count),'xml_lane_width_records':width_records,'raw_frames':len(rows),'local_map_found':sum(r['local_map_found'] for r in rows),'road_lane_section_matches':sum(r.get('ids_match',False) for r in rows),'height_error_p95_m':quantile([r['reference_height_error_m'] for r in rows if r['local_map_found']],.95),'abs_lateral_p95_m':quantile([abs(r['signed_lateral_m']) for r in rows if r['local_map_found']],.95),'ego_origins_in_driving_lanes':sum(r.get('origin_in_driving_lane',False) for r in rows),'all_eight_body_vertices_in_driving_lanes':sum(r.get('body_vertices_in_driving_lane',0)==8 for r in rows),'lane_edge_samples':len(ribbons),'road_boundary_loss_enabled':False,'model_input_changed':False,'gate_promoted':False,'limits':['Local installed CARLA OpenDRIVE is separately identified; official NPZ equivalence not established','Point membership and sampled lane width edges are not continuous vehicle-footprint or swept safety','No polygon union, vertical surface intersection, shoulder/junction semantics or static-obstacle free space certified','Map geometry is offline supervision diagnostic only; no online GT input']}
        atomic_json(run.path/'metrics/map_audit.json',result);run.record({'kind':'town11_local_map_semantics'},result);return run.finish('PARTIAL',canonical(result),['Official Town11 NPZ exceeds frozen budget; local OpenDRIVE not certified drivable-area supervision'],acceptance='BLOCKED')
    except BaseException:
        error=traceback.format_exc();run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')

def run_b2d_alignment_audit(args):
    if dry_plan(args,[{'operation':'current observation / expert target alignment for original real clip','model_forward':False}]):return 0
    import numpy as np,ast,copy,types
    path,base,infos_path,infos,data_root,annotations=b2d_contract_source();audit=ROOT/'audits/dac2027_map_alignment_20261106';dataset=UNIDRIVE_REPO/'Bench2Drive/projects/mmdet3d_plugin/datasets/bench2drive_dataset.py'
    config={'mode':args.mode,'source_manifest':str(base/'manifest.json'),'source_manifest_sha256':file_hash(base/'manifest.json'),'infos_sha256':file_hash(infos_path),'scope':'SINGLE_KNOWN_TRAINING_CLIP_CURRENT_INPUT_EXPERT_TARGET_ALIGNMENT','feature_frames':[0,50,100,150,200,250],'gate_promoted':False}
    run=StageRun('stage02_real_vla',args,config,['OFFICIAL_REAL_DATA_ALIGNMENT'],[dataset,audit/'PROTOCOL.md',audit/'INPUT_CONTRACT.md']);run.path=run.path.resolve()
    try:
        from PIL import Image
        cls=next(n for n in ast.parse(dataset.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Bench2DriveDataset');methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
        module=ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(methods[n]) for n in ('_split_data_infos','get_ego_temporal_trajs')],type_ignores=[]));ns={'np':np};exec(compile(module,str(dataset),'exec'),ns)
        official=types.SimpleNamespace(data_infos=infos.copy(),split_group=5)
        for name in ('_split_data_infos','get_ego_temporal_trajs'):setattr(official,name,types.MethodType(ns[name],official))
        official._split_data_infos();indices={(r['folder'],r['frame_idx']):i for i,r in enumerate(official.data_infos)}
        rows=[];hashes={};observations=[];targets=[];dynamic_hash=file_hash(base/'raw/dynamic_box_targets.jsonl')
        for capture in sorted(infos,key=lambda r:r['frame_idx']):
            current=b2d_current_input_spec(capture,data_root);target=b2d_ego_targets(infos,capture);frame=capture['frame_idx'];expert=data_root/capture['folder']/'expert_assessment'/f'{frame-1:05d}.npz';hashes[str(expert)]=file_hash(expert)
            for image,h in zip(current['image_paths'],current['image_sha256']):
                hashes[image]=h
                with Image.open(image) as im:
                    if im.size!=(1600,900):raise ValueError('Unexpected original image dimensions')
            old_delta,old_mask=official.get_ego_temporal_trajs(indices[(capture['folder'],frame)],6,5);mask=np.asarray(target['delta_mask']);old_mask=old_mask.astype(bool);common=mask&old_mask
            valid=np.asarray(target['contiguous_prefix_mask']);truth=np.asarray(target['absolute_xy']);reconstructed=np.cumsum(np.asarray(target['delta_xy']),axis=0)
            row={'frame_idx':frame,'six_images_present':True,'valid_future_points':int(sum(target['absolute_mask'])),'complete_three_second_target':bool(valid.all()),'official_valid_points':int(old_mask.sum()),'official_invalid_accepted':int((old_mask&~mask).sum()),'official_available_rejected':int((mask&~old_mask).sum()),'official_common_delta_max_error_m':float(np.max(np.abs(old_delta[common]-np.asarray(target['delta_xy'])[common]))) if common.any() else None,'delta_absolute_roundtrip_max_error_m':float(np.max(np.abs(reconstructed[valid]-truth[valid]))) if valid.any() else None,'previous_control_frame':frame-1}
            rows.append(row);observations.append(current);targets.append({'sample_id':current['sample_id'],'frame_idx':frame,'ego':target,'dynamic_boxes_source':{'path':str(base/'raw/dynamic_box_targets.jsonl'),'sha256':dynamic_hash,'record_key':frame}})
        for name,records in (('current_observations.jsonl',observations),('expert_targets.jsonl',targets)):
            with (run.path/'raw'/name).open('w') as f:
                for record in records:f.write(canonical(record)+'\n')
        atomic_json(run.path/'raw/input_hashes.json',hashes);write_csv(run.path/'metrics/alignment.csv',rows)
        result={'frames':len(rows),'image_references':len(rows)*6,'unique_images':len({p for r in observations for p in r['image_paths']}),'complete_three_second_targets':sum(r['complete_three_second_target'] for r in rows),'future_point_denominator':len(rows)*6,'valid_future_points':sum(r['valid_future_points'] for r in rows),'official_invalid_accepted_points':sum(r['official_invalid_accepted'] for r in rows),'official_available_rejected_points':sum(r['official_available_rejected'] for r in rows),'official_common_delta_max_error_m':max(r['official_common_delta_max_error_m'] or 0 for r in rows),'delta_absolute_roundtrip_max_error_m':max(r['delta_absolute_roundtrip_max_error_m'] or 0 for r in rows),'feature_frames':config['feature_frames'],'model_forwards':0,'training_steps':0,'gate_promoted':False,'input_contract':'Current recorded sensor state, calibration, pose and previous expert control; no future GT. Offline teacher-forced input, not deployment perception validation','limits':['Same training clip, no independent generalization','Recorded expert plans are not automatically safe','Missing tails masked, not used as zero labels','Features not yet extracted by this mode; separate bounded probe required']}
        atomic_json(run.path/'metrics/alignment.json',result);run.record({'kind':'real_current_future_alignment'},result);return run.finish('PARTIAL',canonical(result),['Cross-scene training/calibration and valid road geometry remain incomplete'],acceptance='BLOCKED')
    except BaseException:
        error=traceback.format_exc();run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')

def b2d_validate_model_inputs(inputs):
    if set(inputs)!=B2D_MODEL_KEYS:raise ValueError('Model input whitelist mismatch; future labels/unknown fields prohibited')
    if inputs['return_loss'] is not False:raise ValueError('This probe must not train')
    for meta in inputs['img_metas']:
        if set(meta)-{'T_global','T_global_inv','timestamp','scene_token'}:raise ValueError('Unexpected model metadata')

def run_b2d_feature_probe(args):
    if dry_plan(args,[{'operation':'six fixed real clip current-frame model forwards plus feature capture','training':False}]):return 0
    if Path(sys.prefix).resolve()!=UNIDRIVE_ENV.resolve():raise RuntimeError('Use isolated UniDrive Linux Conda')
    import shutil
    audit=ROOT/'audits/dac2027_map_alignment_20261106';mp=ROOT/'outputs/linux_b2d_alignment_audit_20261106/manifest.json';manifest=verified_manifest(mp);base=Path(manifest['run_dir']);checkpoint=Path(os.environ['CHECKPOINT'])
    config={'mode':args.mode,'source_manifest':str(base/'manifest.json'),'source_manifest_sha256':file_hash(base/'manifest.json'),'checkpoint_sha256':file_hash(checkpoint),'source':unidrive_source_audit(),'frames':[0,50,100,150,200,250],'precision':'EXPLICIT_BF16_AUTOCAST_COMPATIBILITY','command_prompt':'official_unmodified','temporal':'independent observation reset before each forward','max_wall_s':900,'max_gpu_allocated_bytes':22*1024**3,'max_feature_bytes':2*1024**3,'disk_reserve_bytes':20*1024**3,'scope':'OFFLINE_KNOWN_TRAINING_CLIP_CURRENT_FEATURE_EXPERT_ALIGNMENT_NOT_DEPLOYMENT','gate_promoted':False}
    run=StageRun('stage02_real_vla',args,config,['REAL_VLA','REAL_GPU','OFFLINE_FEATURE_ALIGNMENT'],[audit/'PROTOCOL.md',audit/'INPUT_CONTRACT.md',UNIDRIVE_REPO/UNIDRIVE_AGENT,UNIDRIVE_REPO/UNIDRIVE_HEAD,UNIDRIVE_REPO/UNIDRIVE_CONFIG,UNIDRIVE_REPO/'Bench2Drive/projects/mmdet3d_plugin/datasets/pipelines/transform.py']);run.path=run.path.resolve();oldcwd=Path.cwd();old_save=os.environ.get('SAVE_PATH');rows=[];saved_bytes=0;started=time.monotonic()
    try:
        import torch,numpy as np,random,cv2
        from mmcv.parallel import DataContainer
        from mmcv.parallel import collate
        observations={r['frame_idx']:r for r in map(json.loads,(base/'raw/current_observations.jsonl').read_text().splitlines())};targets={r['frame_idx']:r for r in map(json.loads,(base/'raw/expert_targets.jsonl').read_text().splitlines())}
        if shutil.disk_usage(ROOT).free-config['max_feature_bytes']<config['disk_reserve_bytes']:raise DependencyBlocked('Feature disk budget unavailable')
        random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed);os.environ['SAVE_PATH']=str(run.path/'raw');os.chdir(UNIDRIVE_REPO/'Bench2Drive')
        from team_code.unidrivevla_b2d_agent import UniDriveVLAB2DAgent
        with writer_lock(ROOT/'results/shared_gpu_resource'),torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
            agent=UniDriveVLAB2DAgent.__new__(UniDriveVLAB2DAgent);agent.setup(str(UNIDRIVE_REPO/UNIDRIVE_CONFIG)+'+'+str(checkpoint));agent.model.requires_grad_(False);head=agent.model.planning_head;decoder=head.unified_decoder;original=decoder.forward_stage2;captured={}
            def capture(*a,**kw):
                out=original(*a,**kw)
                for name in ('det_instance_feature','map_instance_feature','ego_instance_feature','det_anchor','map_anchor'):
                    if isinstance(out.get(name),torch.Tensor):captured[name]=out[name].detach()
                return out
            decoder.forward_stage2=capture
            try:
                for frame in config['frames']:
                    if time.monotonic()-started>config['max_wall_s']:raise DependencyBlocked('Feature wall budget exhausted')
                    spec=observations[frame];target=targets[frame]
                    if not all(target['ego']['contiguous_prefix_mask']):raise ValueError('Frozen probe has incomplete expert target')
                    for p,h in zip(spec['image_paths'],spec['image_sha256']):
                        if file_hash(p)!=h:raise ValueError('Image hash changed')
                    inp={k:spec[k] for k in ('folder','scene_token','frame_idx','timestamp')};inp.update(img=[cv2.imread(p).astype(np.float32) for p in spec['image_paths']],lidar2img=np.array(spec['lidar2img']),lidar2cam=np.array(spec['lidar2cam']),lidar2global=np.array(spec['lidar2global']),ego_status=np.array(spec['ego_status'],np.float32),gt_ego_fut_cmd=np.array(spec['gt_ego_fut_cmd'],np.float32),aug_config=agent.get_augmentation())
                    processed=collate([agent.inference_only_pipeline(inp)],samples_per_gpu=1)
                    for k,value in processed.items():
                        if isinstance(value,DataContainer):value=value.data[0]
                        elif isinstance(value[0],DataContainer):value=value[0].data
                        processed[k]=value.cuda() if isinstance(value,torch.Tensor) else value
                    inputs={k:processed[k] for k in ('img','img_metas','projection_mat','ego_status','gt_ego_fut_cmd','image_wh','timestamp')};inputs.update(rescale=True,return_loss=False);b2d_validate_model_inputs(inputs)
                    restore_unidrive_temporal(head,None,None);captured.clear();torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();a=torch.cuda.Event(enable_timing=True);b=torch.cuda.Event(enable_timing=True);t=time.perf_counter_ns();a.record();output=agent.model(**inputs);b.record();torch.cuda.synchronize();wall=(time.perf_counter_ns()-t)/1e6
                    trajectory=output[0]['img_bbox']['final_planning'].detach().float().cpu();peak=torch.cuda.max_memory_allocated()
                    if peak>config['max_gpu_allocated_bytes']:raise DependencyBlocked('GPU allocation exceeds frozen budget')
                    if trajectory.shape!=(6,2) or not torch.isfinite(trajectory).all() or not captured:raise ValueError('Invalid actual trajectory/features')
                    features={k:v.cpu() for k,v in captured.items()}
                    if any(not torch.isfinite(v).all() for v in features.values()):raise ValueError('Nonfinite actual feature')
                    payload={'sample_id':spec['sample_id'],'features':features,'original_trajectory':trajectory,'feature_source':'original unified_decoder.forward_stage2 actual output','checkpoint_sha256':config['checkpoint_sha256'],'observation_sha256':digest(spec),'future_targets_in_features':False};file=run.path/'raw'/f'features_{frame:05d}.pt';torch.save(payload,file);saved_bytes+=file.stat().st_size
                    if saved_bytes>config['max_feature_bytes']:raise DependencyBlocked('Feature artifact budget exceeded')
                    truth=np.asarray(target['ego']['absolute_xy']);errors=np.linalg.norm(trajectory.numpy()-truth,axis=1)
                    row={'frame_idx':frame,'sample_id':spec['sample_id'],'forward_wall_ms':wall,'forward_cuda_elapsed_ms':a.elapsed_time(b),'cuda_peak_allocated_bytes':peak,'trajectory_xy':trajectory.tolist(),'expert_absolute_xy':truth.tolist(),'expert_L2_by_horizon_m':errors.tolist(),'ADE_m':float(errors.mean()),'FDE_m':float(errors[-1]),'feature_path':str(file),'feature_sha256':file_hash(file),'feature_shapes':{k:list(v.shape) for k,v in features.items()},'feature_bytes':file.stat().st_size,'input_keys':sorted(inputs),'observation_sha256':digest(spec),'expert_target_sha256':digest(target),'temporal_reset':True}
                    rows.append(row);atomic_json(run.path/'raw'/f'forward_{frame:05d}.json',row);run.log('actual_forward_completed',frame_idx=frame,wall_ms=wall,ADE_m=row['ADE_m'])
                    del output,inputs,processed,features,payload;captured.clear()
            finally:decoder.forward_stage2=original
        os.chdir(oldcwd);result={'model_forwards':len(rows),'training_steps':0,'closed_loop_episodes':0,'independent_source_clips':1,'feature_bytes':saved_bytes,'frames':rows,'mean_ADE_m':sum(r['ADE_m'] for r in rows)/len(rows),'forward_wall_p50_ms':quantile([r['forward_wall_ms'] for r in rows],.5),'peak_allocated_bytes':max(r['cuda_peak_allocated_bytes'] for r in rows),'gate_promoted':False,'limits':['Six predetermined frames of one known training clip, not independent test quality','Recorded current pose and previous expert control are teacher-forced offline inputs','Native offline JPEG loading uses official inference pipeline; no extra live sensor JPEG roundtrip','Timing includes feature-reference hook and original output CPU transfer, excludes preprocessing/setup/artifact serialization','No adapter trained; original trajectories not approved as legal Fast or safe plans']}
        atomic_json(run.path/'metrics/feature_probe.json',result);run.record({'kind':'real_b2d_current_feature_probe'},result);return run.finish('PARTIAL',canonical(result),['Safe baseline, useful refinement and independent calibration remain unestablished'],acceptance='BLOCKED')
    except BaseException:
        os.chdir(oldcwd);error=traceback.format_exc();atomic_json(run.path/'metrics/feature_probe_failure.json',{'completed_forwards':len(rows),'rows':rows,'error':error});run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')
    finally:
        os.chdir(oldcwd)
        if old_save is None:os.environ.pop('SAVE_PATH',None)
        else:os.environ['SAVE_PATH']=old_save

def b2d_extract_verified_archive(archive_path,destination,max_bytes,expected_root):
    """Bounded local research extraction; verify all bytes when reusing."""
    import tarfile,shutil,hashlib
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);root=destination.resolve();rows=[];seen=set();total=0
    with tarfile.open(archive_path,'r:gz') as archive:
        members=archive.getmembers()
        for member in members:
            p=Path(member.name)
            if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!=expected_root or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):raise ValueError('Unsafe archive member')
            if member.name in seen:raise ValueError('Duplicate archive member')
            seen.add(member.name);total+=member.size
            if total>max_bytes:raise DependencyBlocked('Frozen aggregate extraction budget exceeded')
            if not (destination/p).resolve().is_relative_to(root):raise ValueError('Existing path escapes extraction root')
        for member in members:
            out=destination/member.name
            if member.isdir():out.mkdir(parents=True,exist_ok=True);continue
            out.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256()
            with archive.extractfile(member) as src:
                if out.exists():
                    for block in iter(lambda:src.read(1024*1024),b''):h.update(block)
                    if out.stat().st_size!=member.size or file_hash(out)!=h.hexdigest():raise ValueError('Existing extracted data mismatch')
                else:
                    with out.open('xb') as dst:
                        for block in iter(lambda:src.read(1024*1024),b''):h.update(block);dst.write(block)
            rows.append({'path':str(out),'bytes':member.size,'sha256':h.hexdigest()})
    return rows,total

def run_b2d_multiscene_resources(args):
    validation_mode=args.mode=='b2d-validation-resources'
    if dry_plan(args,[{'operation':'frozen official validation clips' if validation_mode else 'four frozen official training clips','training':False}]):return 0
    import shutil,gzip,pickle,collections
    from stage00_environment import download_file
    audit=ROOT/('audits/dac2027_adapter_pilot_20261106' if validation_mode else 'audits/dac2027_map_alignment_20261106');selection=audit/('VALIDATION_SELECTION.json' if validation_mode else 'MULTISCENE_SELECTION.json');config=read_json(selection);config.update(mode=args.mode,gate_promoted=False)
    converter=UNIDRIVE_REPO/'Bench2Drive/tools/data_converter/bench2drive_converter.py';benchmark=Path(os.environ['FRAMELEASE_BENCHMARK_ROOT']);catalog=benchmark/'docs/bench2drive_base_1000.json'
    if file_hash(catalog)!=config['catalog_sha256']:raise ValueError('Frozen catalog changed')
    if not config['dataset_revision']:raise DependencyBlocked('Remote dataset revision not pinned')
    if sum(r['size'] for r in config['clips'])>config['max_aggregate_archive_bytes']:raise DependencyBlocked('Frozen archive budget exceeded')
    if validation_mode:
        split=ROOT/'audits/dac2027_data_semantics_20261106/discovery/bench2drive_base_train_val_split.json'
        if file_hash(split)!=config['official_split_sha256']:raise ValueError('Frozen official validation split changed')
        val={Path(p).name for p in read_json(split)['val']};excluded={tuple(k) for k in config['training_route_keys']+config['reserved_route_keys']}
        for chosen in config['clips']:
            parsed=parse_unidrive_route_directory(chosen['name'].removesuffix('.tar.gz'))
            if chosen['name'].removesuffix('.tar.gz') not in val or (parsed['town'],parsed['route_id']) in excluded:raise ValueError('Validation route overlaps excluded source')
    run=StageRun('stage02_real_vla',args,config,['OFFICIAL_REAL_DATA_ACQUISITION','OFFLINE_CROSS_SCENE_COVERAGE_AUDIT'],[selection,audit/('CORPUS_PROTOCOL.md' if validation_mode else 'MULTISCENE_PROTOCOL.md'),ROOT/'audits/dac2027_map_alignment_20261106/discovery/dataset.raw',converter,catalog,benchmark/'LICENSE']);run.path=run.path.resolve();rows=[];total_extract=0
    try:
        if shutil.disk_usage(ROOT).free-config['actual_total_archive_bytes']-config['max_aggregate_extraction_bytes']<config['disk_reserve_bytes']:raise DependencyBlocked('Insufficient reserve for frozen acquisition')
        for chosen in config['clips']:
            clip=chosen['name'].removesuffix('.tar.gz');target=ROOT/'datasets/Bench2Drive'/('adapter_validation' if validation_mode else 'training_prerequisites')/chosen['sha256']/chosen['name'];record={**chosen,'archive':str(target),'status':'NOT_STARTED'}
            try:
                with writer_lock(target.parent):
                    url=f"https://hf-mirror.com/datasets/rethinklab/Bench2Drive/resolve/{config['dataset_revision']}/{chosen['name']}";download=download_file(url,target,chosen['size'],chosen['sha256'],timeout=8,retries=config['download_attempts_per_file']);record.update(url=url,download=download,status=download['status']);atomic_json(run.path/'raw'/(clip+'_download.json'),record)
                    if download['status']!='COMPLETED':rows.append(record);continue
                    files,extracted_bytes=b2d_extract_verified_archive(target,target.parent/'extracted',config['max_aggregate_extraction_bytes']-total_extract,clip);total_extract+=extracted_bytes
                clip_root=target.parent/'extracted'/clip;record.update(extracted=str(clip_root),extracted_bytes=extracted_bytes,files=len(files));atomic_json(run.path/'raw'/(clip+'_input_hashes.json'),files)
                annotations={int(p.name.split('.')[0]):json.load(gzip.open(p,'rt')) for p in (clip_root/'anno').glob('*.json.gz')};counts=collections.Counter(o['class'] for ann in annotations.values() for o in ann['bounding_boxes']);raw_frames=sorted(annotations)
                root=run.path/'raw/official_data';(root/'v1').mkdir(parents=True,exist_ok=True);(root/'v1'/clip).symlink_to(clip_root,target_is_directory=True)
                helper=run.path/'raw/convert_official_multiscene.py'
                if not helper.exists():helper.write_text("import importlib.util,sys\nfrom pathlib import Path\nsource,root,out,clip=sys.argv[1:]\nspec=importlib.util.spec_from_file_location('official_b2d_converter',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\nm.DATAROOT=root;m.OUT_DIR=out\nPath(out).mkdir(parents=True,exist_ok=True)\nm.preprocess(['v1/'+clip],0,'contract_development','train')\n")
                probe=native_probe(run,'convert_'+clip,[sys.executable,helper,converter,root,run.path/'raw/infos'/clip,clip],ROOT,timeout=300)
                if probe['returncode']!=0:record.update(status='CONVERSION_FAILED',raw_annotation_frames=len(annotations),raw_class_actor_frames=dict(counts));rows.append(record);continue
                info_path=run.path/'raw/infos'/clip/'contract_development/b2d_infos_train_0.pkl';infos=pickle.loads(info_path.read_bytes());converted_frames={r['frame_idx'] for r in infos};walker_rows=[];complete=0;observations=[];targets=[]
                for capture in infos:
                    current=b2d_current_input_spec(capture,root);future=b2d_ego_targets(infos,capture);complete+=all(future['contiguous_prefix_mask']);observations.append(current);targets.append({'sample_id':current['sample_id'],'ego':future,'actors':b2d_future_targets(infos,capture)})
                    objects={int(o['id']):o for o in annotations[capture['frame_idx']]['bounding_boxes']};walker_rows.append({'frame_idx':capture['frame_idx'],'raw_walker_count':sum(o['class']=='walker' for o in objects.values()),'converter_visible_walker_count':sum(objects[int(identity)]['class']=='walker' for identity in capture['gt_ids'])})
                for suffix,records in (('current_observations',observations),('expert_targets',targets)):
                    with (run.path/'raw'/(clip+'_'+suffix+'.jsonl')).open('w') as f:
                        for r in records:f.write(canonical(r)+'\n')
                write_csv(run.path/'metrics'/(clip+'_walker_visibility.csv'),walker_rows)
                accelerations=[(annotations[b]['speed']-annotations[a]['speed'])/((b-a)/10.) for a,b in zip(raw_frames,raw_frames[1:]) if b==a+1]
                record.update(status='COMPLETED',raw_annotation_frames=len(annotations),converted_frames=len(infos),omitted_raw_frame_indices=sorted(set(raw_frames)-converted_frames),raw_class_actor_frames=dict(counts),raw_frames_with_walkers=sum(any(o['class']=='walker' for o in ann['bounding_boxes']) for ann in annotations.values()),converted_visible_walker_actor_frames=sum(r['converter_visible_walker_count'] for r in walker_rows),converted_raw_walker_actor_frames=sum(r['raw_walker_count'] for r in walker_rows),complete_three_second_ego_targets=complete,six_camera_references=len(infos)*6,min_adjacent_recorded_speed_accel_mps2=min(accelerations,default=None),infos_path=str(info_path),infos_sha256=file_hash(info_path),mechanism_validation='NOT_ESTABLISHED_BY_SCENARIO_NAME_OR_CLASS_COUNTS',training_steps=0)
            except Exception:record.update(status='FAILED',error=traceback.format_exc());run.log('clip_failed',clip=clip,error=record['error'])
            rows.append(record);atomic_json(run.path/'metrics/multiscene_progress.json',rows);run.log('clip_completed',clip=clip,status=record['status'])
        result={'clips':rows,'requested_clips':len(config['clips']),'completed_clips':sum(r['status']=='COMPLETED' for r in rows),'archive_bytes_verified':sum(r['size'] for r in rows if r.get('download',{}).get('status')=='COMPLETED'),'extracted_bytes':total_extract,'raw_annotation_frames':sum(r.get('raw_annotation_frames',0) for r in rows),'converted_frames':sum(r.get('converted_frames',0) for r in rows),'complete_three_second_ego_targets':sum(r.get('complete_three_second_ego_targets',0) for r in rows),'model_forwards':0,'training_steps':0,'validation_or_test_data_used':False,'gate_promoted':False,'disk_free_after_bytes':shutil.disk_usage(ROOT).free,'limits':['Training-side resources only; no independent calibration or test evidence','Actor counts and scenario names do not establish crossing, cut-in, braking or occlusion events','Official converter may omit frames/actors; omitted denominators preserved','Supervision alone does not establish safe plans or trained refinement']}
        if validation_mode:
            result.pop('validation_or_test_data_used',None)
            result.update(validation_resources_acquired=True,validation_data_read_for_conversion=True,final_test_data_used=False,adapter_split='VALIDATION_ONLY_NOT_OPTIMIZER_INPUT')
            result['limits'][0]='Adapter validation source clips acquired; complete foundation pretraining independence unknown; not final test'
        atomic_json(run.path/'metrics/multiscene_resources.json',result);run.record({'kind':'adapter_validation_source_prerequisites' if validation_mode else 'four_scene_training_prerequisites'},result);return run.finish('PARTIAL',canonical(result),['Independent calibration, valid geometry, actual adapter training and quality evaluation outstanding'],acceptance='BLOCKED')
    except BaseException:
        error=traceback.format_exc();run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')

def b2d_select_corpus_samples(observations,targets,cap=80):
    """Frozen time-based sampling, with no dependence on labels or model errors."""
    import numpy as np
    obs={r['sample_id']:r for r in observations};truth={r['sample_id']:r for r in targets}
    if len(obs)!=len(observations) or len(truth)!=len(targets) or set(obs)!=set(truth):raise ValueError('Duplicate or unmatched observation/target identity')
    eligible=sorted((key for key,r in obs.items() if r['frame_idx']%5==0 and all(truth[key]['ego']['contiguous_prefix_mask'])),key=lambda k:obs[k]['frame_idx'])
    indices=np.linspace(0,len(eligible)-1,min(cap,len(eligible)),dtype=int).tolist() if eligible else []
    return [eligible[i] for i in indices],{'all_observations':len(obs),'eligible_complete_2hz':len(eligible),'selected':len(indices),'cap':cap}

def b2d_assert_partition_separation(samples):
    groups={k:set() for k in ('train','validation')};identities=set()
    for r in samples:
        if r['split'] not in groups:raise ValueError('Only frozen train/adapter-validation partitions permitted')
        parsed=parse_unidrive_route_directory(r['clip'])
        if parsed is None:raise ValueError('Unrecognized dataset route identity')
        groups[r['split']].add((parsed['town'],parsed['route_id']))
        if r['sample_id'] in identities:raise ValueError('Duplicate corpus sample')
        identities.add(r['sample_id'])
    if groups['train']&groups['validation']:raise ValueError('Train and validation route keys overlap')
    if not all(groups.values()):raise ValueError('Both train and adapter-validation sources required')
    return {key:sorted(value) for key,value in groups.items()}

def run_b2d_corpus_manifest(args):
    if dry_plan(args,[{'operation':'freeze all training/validation feature sample IDs before model extraction'}]):return 0
    audit=ROOT/'audits/dac2027_adapter_pilot_20261106';sources=[];entries=[]
    original=verified_manifest(ROOT/'outputs/linux_b2d_alignment_audit_20261106/manifest.json');base=Path(original['run_dir']);sources.append(base/'manifest.json');entries.append({'clip':'ControlLoss_Town11_Route401_Weather11','split':'train','observations':str(base/'raw/current_observations.jsonl'),'targets':str(base/'raw/expert_targets.jsonl')})
    for split,folder in (('train','multiscene_resources'),('validation','validation_resources')):
        manifest=verified_manifest(ROOT/f'outputs/linux_b2d_{folder}_20261106/manifest.json');base=Path(manifest['run_dir']);sources.append(base/'manifest.json');data=read_json(base/'metrics/multiscene_resources.json')
        if data['completed_clips']!=data['requested_clips']:raise DependencyBlocked('Frozen source corpus incomplete; no silent clip substitution')
        for r in data['clips']:
            clip=r['name'].removesuffix('.tar.gz');entries.append({'clip':clip,'split':split,'observations':str(base/'raw'/(clip+'_current_observations.jsonl')),'targets':str(base/'raw'/(clip+'_expert_targets.jsonl'))})
    config={'mode':args.mode,'source_manifests':{str(p):file_hash(p) for p in sources},'scope':'FROZEN_ADAPTER_TRAIN_VALIDATION_CORPUS_NOT_FINAL_TEST','cap_per_clip':80,'frame_modulo':5,'max_samples':800,'gate_promoted':False}
    run=StageRun('stage02_real_vla',args,config,['FROZEN_REAL_CORPUS_IDENTITY'],[audit/'CORPUS_PROTOCOL.md',audit/'VALIDATION_SELECTION.json',audit/'TRAINING_PROTOCOL.json']);run.path=run.path.resolve()
    try:
        samples=[];counts=[]
        for entry in entries:
            observations=[json.loads(s) for s in Path(entry['observations']).read_text().splitlines()];targets=[json.loads(s) for s in Path(entry['targets']).read_text().splitlines()];chosen,count=b2d_select_corpus_samples(observations,targets,config['cap_per_clip']);obs={r['sample_id']:r for r in observations};truth={r['sample_id']:r for r in targets};counts.append({**entry,**count})
            for key in chosen:
                samples.append({'sample_id':key,'clip':entry['clip'],'split':entry['split'],'frame_idx':obs[key]['frame_idx'],'observation':obs[key],'expert_target':truth[key]['ego'],'observation_sha256':digest(obs[key]),'expert_target_sha256':digest(truth[key]['ego']),'source_observations':entry['observations'],'source_observations_sha256':file_hash(entry['observations']),'source_targets':entry['targets'],'source_targets_sha256':file_hash(entry['targets'])})
        partitions=b2d_assert_partition_separation(samples)
        if len(samples)>config['max_samples']:raise DependencyBlocked('Frozen corpus exceeds extraction budget')
        atomic_json(run.path/'raw/samples.json',samples);atomic_json(run.path/'metrics/corpus.json',{'samples':len(samples),'per_clip':counts,'route_keys':partitions,'training_samples':sum(r['split']=='train' for r in samples),'validation_samples':sum(r['split']=='validation' for r in samples),'sample_identity_sha256':digest([r['sample_id'] for r in samples]),'checkpoint_full_training_exposure':'UNKNOWN','gate_promoted':False})
        result=read_json(run.path/'metrics/corpus.json');run.record({'kind':'frozen_adapter_corpus'},result);return run.finish('PARTIAL',canonical(result),['Corpus frozen only; no model quality or deployment gate established'],acceptance='BLOCKED')
    except BaseException:
        error=traceback.format_exc();run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')

def b2d_prepare_pipeline_input(agent,spec,reference_pipeline=None):
    """Actual official preprocessing, current-only; return CPU tensors for hashing."""
    import numpy as np,cv2,torch
    from mmcv.parallel import DataContainer,collate
    for p,h in zip(spec['image_paths'],spec['image_sha256']):
        if file_hash(p)!=h:raise ValueError('Frozen camera bytes changed')
    inp={k:spec[k] for k in ('folder','scene_token','frame_idx','timestamp')}
    inp.update(lidar2img=np.array(spec['lidar2img']),lidar2cam=np.array(spec['lidar2cam']),lidar2global=np.array(spec['lidar2global']),ego_status=np.array(spec['ego_status'],np.float32),gt_ego_fut_cmd=np.array(spec['gt_ego_fut_cmd'],np.float32),aug_config=agent.get_augmentation())
    if reference_pipeline is None:
        inp['img']=[cv2.imread(p).astype(np.float32) for p in spec['image_paths']];pipeline=agent.inference_only_pipeline
    else:inp['img_filename']=spec['image_paths'];pipeline=reference_pipeline
    processed=collate([pipeline(inp)],samples_per_gpu=1)
    for k,value in processed.items():
        if isinstance(value,DataContainer):value=value.data[0]
        elif isinstance(value[0],DataContainer):value=value[0].data
        processed[k]=value
    result={k:processed[k] for k in ('img','img_metas','projection_mat','ego_status','gt_ego_fut_cmd','image_wh','timestamp')};result.update(rescale=True,return_loss=False);b2d_validate_model_inputs(result);return result

def b2d_tensor_identity(value):
    import torch,hashlib
    if not isinstance(value,torch.Tensor):raise TypeError('Actual tensor required')
    data=value.detach().cpu().contiguous()
    return {'shape':list(data.shape),'dtype':str(data.dtype),'sha256':hashlib.sha256(data.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest(),'finite':bool(torch.isfinite(data).all())}

def run_b2d_corpus_features(args):
    if dry_plan(args,[{'operation':'actual multi-clip GPU features for frozen sample IDs','training':False}]):return 0
    if Path(sys.prefix).resolve()!=UNIDRIVE_ENV.resolve():raise RuntimeError('Use isolated UniDrive Conda')
    import shutil
    audit=ROOT/'audits/dac2027_adapter_pilot_20261106';manifest=verified_manifest(ROOT/'outputs/linux_b2d_corpus_manifest_20261106/manifest.json');base=Path(manifest['run_dir']);samples=read_json(base/'raw/samples.json');partitions=b2d_assert_partition_separation(samples);checkpoint=Path(os.environ['CHECKPOINT'])
    prior=verified_manifest(ROOT/'outputs/linux_b2d_feature_probe_20261106/manifest.json');prior_base=Path(prior['run_dir']);prior_data=read_json(prior_base/'metrics/feature_probe.json');reusable={r['sample_id']:r for r in prior_data['frames']}
    config={'mode':args.mode,'corpus_manifest':str(base/'manifest.json'),'corpus_manifest_sha256':file_hash(base/'manifest.json'),'samples_sha256':file_hash(base/'raw/samples.json'),'prior_feature_manifest':str(prior_base/'manifest.json'),'prior_feature_manifest_sha256':file_hash(prior_base/'manifest.json'),'checkpoint_sha256':file_hash(checkpoint),'source':unidrive_source_audit(),'precision':'bf16-autocast','prompt':'official','max_wall_s':1200,'max_feature_bytes':1024**3,'max_gpu_allocated_bytes':22*1024**3,'disk_reserve_bytes':20*1024**3,'scope':'FROZEN_OFFLINE_ADAPTER_CORPUS_NOT_DEPLOYMENT','gate_promoted':False}
    if prior['identity']['config']['checkpoint_sha256']!=config['checkpoint_sha256'] or prior['identity']['seed']!=args.seed:raise ValueError('Previous features incompatible with current checkpoint/seed')
    run=StageRun('stage02_real_vla',args,config,['REAL_VLA','REAL_GPU','FROZEN_REAL_FEATURE_CORPUS'],[audit/'CORPUS_PROTOCOL.md',audit/'TRAINING_PROTOCOL.json',UNIDRIVE_REPO/UNIDRIVE_AGENT,UNIDRIVE_REPO/UNIDRIVE_CONFIG,UNIDRIVE_REPO/UNIDRIVE_HEAD,UNIDRIVE_REPO/'Bench2Drive/projects/mmdet3d_plugin/datasets/pipelines/transform.py']);run.path=run.path.resolve();oldcwd=Path.cwd();old_save=os.environ.get('SAVE_PATH');rows=[];events=[];new_count=0;saved_bytes=0;started=time.monotonic()
    try:
        import numpy as np,torch,random
        if shutil.disk_usage(ROOT).free-config['max_feature_bytes']<config['disk_reserve_bytes']:raise DependencyBlocked('Frozen feature reserve unavailable')
        random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed);os.environ['SAVE_PATH']=str(run.path/'raw');os.chdir(UNIDRIVE_REPO/'Bench2Drive')
        from team_code import unidrivevla_b2d_agent as official
        with writer_lock(ROOT/'results/shared_gpu_resource'),torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
            agent=official.UniDriveVLAB2DAgent.__new__(official.UniDriveVLAB2DAgent);agent.setup(str(UNIDRIVE_REPO/UNIDRIVE_CONFIG)+'+'+str(checkpoint));agent.model.requires_grad_(False);head=agent.model.planning_head;decoder=head.unified_decoder;capture={};original=decoder.forward_stage2;checked_clips=set()
            cfg=official.Config.fromfile(str(UNIDRIVE_REPO/UNIDRIVE_CONFIG));reference_pipeline=official.Compose(cfg.inference_only_pipeline)
            def capture_output(*a,**kw):
                out=original(*a,**kw)
                for name in ('det_instance_feature','map_instance_feature','ego_instance_feature','det_anchor','map_anchor'):
                    if isinstance(out.get(name),torch.Tensor):capture[name]=out[name].detach()
                return out
            decoder.forward_stage2=capture_output
            try:
                for sample in samples:
                    if time.monotonic()-started>config['max_wall_s']:raise DependencyBlocked('Corpus feature wall budget exhausted')
                    spec=sample['observation'];identity=digest(sample['sample_id']);input_cpu=b2d_prepare_pipeline_input(agent,spec);hashes={k:b2d_tensor_identity(v) for k,v in input_cpu.items() if isinstance(v,torch.Tensor)}
                    if not all(r['finite'] for r in hashes.values()):raise ValueError('Nonfinite input tensor')
                    if sample['clip'] not in checked_clips:
                        reference=b2d_prepare_pipeline_input(agent,spec,reference_pipeline);comparisons={k:float((input_cpu[k]-reference[k]).abs().max()) for k in hashes}
                        if any(error!=0 for error in comparisons.values()):raise ValueError('Manual current-image loading differs from official LoadMultiViewImageFromFiles pipeline')
                        events.append({'clip':sample['clip'],'preprocessing_comparison_max_abs':comparisons,'sample_id':sample['sample_id']});checked_clips.add(sample['clip']);del reference
                    input_record={'sample_id':sample['sample_id'],'observation_sha256':sample['observation_sha256'],'model_input_keys':sorted(input_cpu),'tensors':hashes,'meta_keys':[sorted(m) for m in input_cpu['img_metas']],'future_truth_provided':False,'method':'Hashes before unchanged dtype/device copy to GPU'};atomic_json(run.path/'raw'/('input_'+identity+'.json'),input_record)
                    existing=reusable.get(sample['sample_id']);old=None
                    if existing:
                        if existing['observation_sha256']!=sample['observation_sha256'] or file_hash(existing['feature_path'])!=existing['feature_sha256']:raise ValueError('Previous feature provenance mismatch')
                        old=torch.load(existing['feature_path'],map_location='cpu',weights_only=True)
                    if old is not None:
                        file=Path(existing['feature_path']);trajectory=old['original_trajectory'];shapes={k:list(v.shape) for k,v in old['features'].items()};wall=None;elapsed=None;peak=None;reused=True
                    else:
                        inputs={k:v.cuda() if isinstance(v,torch.Tensor) else v for k,v in input_cpu.items()};restore_unidrive_temporal(head,None,None);capture.clear();torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();a=torch.cuda.Event(enable_timing=True);b=torch.cuda.Event(enable_timing=True);t=time.perf_counter_ns();a.record();out=agent.model(**inputs);b.record();torch.cuda.synchronize();wall=(time.perf_counter_ns()-t)/1e6;elapsed=a.elapsed_time(b);new_count+=1;peak=torch.cuda.max_memory_allocated()
                        if peak>config['max_gpu_allocated_bytes']:raise DependencyBlocked('Corpus feature GPU allocation exceeds budget')
                        trajectory=out[0]['img_bbox']['final_planning'].detach().float().cpu();features={k:v.cpu() for k,v in capture.items()}
                        if trajectory.shape!=(6,2) or not torch.isfinite(trajectory).all() or len(features)!=5 or any(not torch.isfinite(v).all() for v in features.values()):raise ValueError('Actual model output/features invalid')
                        file=run.path/'raw'/('feature_'+identity+'.pt');torch.save({'sample_id':sample['sample_id'],'features':features,'original_trajectory':trajectory,'checkpoint_sha256':config['checkpoint_sha256'],'observation_sha256':sample['observation_sha256'],'future_targets_in_features':False},file);saved_bytes+=file.stat().st_size;shapes={k:list(v.shape) for k,v in features.items()};reused=False;del features,out,inputs;capture.clear()
                    if saved_bytes>config['max_feature_bytes']:raise DependencyBlocked('Corpus feature disk budget exceeded')
                    row={k:sample[k] for k in ('sample_id','clip','split','frame_idx','observation_sha256','expert_target_sha256')};row.update(feature_path=str(file),feature_sha256=file_hash(file),feature_shapes=shapes,input_record=str(run.path/'raw'/('input_'+identity+'.json')),input_record_sha256=file_hash(run.path/'raw'/('input_'+identity+'.json')),reused_previous_feature=reused,forward_wall_ms=wall,forward_cuda_elapsed_ms=elapsed,cuda_peak_allocated_bytes=peak);rows.append(row)
                    with (run.path/'raw/completed_samples.jsonl').open('a') as log:log.write(canonical(row)+'\n')
                    if len(rows)%20==0:run.log('corpus_progress',completed=len(rows),requested=len(samples),new_forwards=new_count);atomic_json(run.path/'metrics/progress.json',{'completed':len(rows),'requested':len(samples),'new_forwards':new_count,'elapsed_s':time.monotonic()-started})
                    del input_cpu,old
            finally:decoder.forward_stage2=original
        os.chdir(oldcwd);atomic_json(run.path/'raw/feature_index.json',rows);atomic_json(run.path/'metrics/preprocessing_equivalence.json',events)
        result={'samples':len(rows),'new_model_forwards':new_count,'reused_features':sum(r['reused_previous_feature'] for r in rows),'feature_bytes_written':saved_bytes,'wall_s':time.monotonic()-started,'forward_wall_p50_ms':quantile([r['forward_wall_ms'] for r in rows if r['forward_wall_ms'] is not None],.5),'peak_gpu_allocated_bytes':max((r['cuda_peak_allocated_bytes'] for r in rows if r['cuda_peak_allocated_bytes'] is not None),default=0),'per_split':{s:sum(r['split']==s for r in rows) for s in ('train','validation')},'route_keys':partitions,'official_preprocessing_equivalence_clips':len(events),'training_steps':0,'gate_promoted':False,'limits':['Actual frozen VLA features; current pose and previous expert control are teacher forced offline','Validation source separation does not prove all foundation pretraining unseen','Old six features reused explicitly, not additional model forwards','Independent frames reset temporal state; no closed-loop execution']}
        atomic_json(run.path/'metrics/corpus_features.json',result);run.record({'kind':'real_frozen_multiscene_features'},result);return run.finish('PARTIAL',canonical(result),['No trained adapter or safety/refinement gate established by feature extraction'],acceptance='BLOCKED')
    except BaseException:
        os.chdir(oldcwd);error=traceback.format_exc();atomic_json(run.path/'metrics/feature_failure.json',{'completed':len(rows),'new_model_forwards':new_count,'error':error});run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')
    finally:
        os.chdir(oldcwd)
        if old_save is None:os.environ.pop('SAVE_PATH',None)
        else:os.environ['SAVE_PATH']=old_save

def build_b2d_refinement_adapter(hidden_dim=128,max_delta_m=2.,quanta=3):
    """New explicitly trained module; never represented as a pretrained backend."""
    import torch
    from torch import nn
    class RecurrentFeatureRefiner(nn.Module):
        def __init__(self):
            super().__init__();self.hidden_dim=hidden_dim;self.max_delta_m=max_delta_m;self.quanta=quanta
            self.project=nn.Sequential(nn.LayerNorm(256),nn.Linear(256,hidden_dim),nn.SiLU());self.geometry=nn.Linear(2,hidden_dim);self.token_type=nn.Embedding(3,hidden_dim)
            self.key=nn.Linear(hidden_dim,hidden_dim);self.value=nn.Linear(hidden_dim,hidden_dim);self.query=nn.Linear(hidden_dim,hidden_dim);self.trajectory=nn.Linear(3,hidden_dim)
            self.cell=nn.GRUCell(hidden_dim*2,hidden_dim);self.readout=nn.Linear(hidden_dim,2);nn.init.zeros_(self.readout.weight);nn.init.zeros_(self.readout.bias)
        def prepare(self,features,original_trajectory):
            required={'det_instance_feature','map_instance_feature','ego_instance_feature','det_anchor','map_anchor'}
            if set(features)!=required:raise ValueError('Refinement input must be frozen current features only')
            if original_trajectory.ndim!=3 or original_trajectory.shape[1:]!=(6,2):raise ValueError('Complete six-point original candidate required')
            if not torch.isfinite(original_trajectory).all() or any(not torch.isfinite(v).all() for v in features.values()):raise ValueError('Nonfinite refinement input')
            det=features['det_instance_feature'].float();maps=features['map_instance_feature'].float();ego=features['ego_instance_feature'].float();bs=det.shape[0]
            centers=torch.cat([features['det_anchor'][...,:2].float(),features['map_anchor'].float().reshape(bs,-1,20,2).mean(2),det.new_zeros(bs,1,2)],dim=1)
            tokens=self.project(torch.cat([det,maps,ego],dim=1));types=torch.cat([torch.zeros(det.shape[1],device=det.device,dtype=torch.long),torch.ones(maps.shape[1],device=det.device,dtype=torch.long),torch.full((1,),2,device=det.device,dtype=torch.long)])
            tokens=tokens+self.geometry(centers/50.)+self.token_type(types)[None];keys=self.key(tokens);values=self.value(tokens);hidden=self.project(ego).expand(-1,6,-1).contiguous()
            return {'keys':keys,'values':values,'centers':centers,'hidden':hidden,'trajectory':original_trajectory,'quantum':0}
        def advance(self,state):
            if state['quantum']>=self.quanta:raise ValueError('Frozen refinement quantum budget exceeded')
            traj=state['trajectory'];bs=traj.shape[0];horizons=torch.arange(1,7,device=traj.device,dtype=traj.dtype).view(1,6,1).expand(bs,-1,-1)/6
            encoded=self.trajectory(torch.cat([traj/50.,horizons],dim=-1));query=self.query(state['hidden']+encoded)
            logits=torch.bmm(query,state['keys'].transpose(1,2))/math.sqrt(self.hidden_dim)
            distance=(traj[:,:,None,:]-state['centers'][:,None,:,:]).square().sum(-1);attention=(logits-distance/(2*20.**2)).softmax(-1);context=torch.bmm(attention,state['values'])
            hidden=self.cell(torch.cat([context,encoded],dim=-1).reshape(bs*6,-1),state['hidden'].reshape(bs*6,-1)).reshape(bs,6,-1);updated=traj+self.max_delta_m*torch.tanh(self.readout(hidden))
            return {**state,'hidden':hidden,'trajectory':updated,'quantum':state['quantum']+1}
        def forward(self,features,original_trajectory):
            state=self.prepare(features,original_trajectory);candidates=[]
            for _ in range(self.quanta):state=self.advance(state);candidates.append(state['trajectory'])
            return candidates
    return RecurrentFeatureRefiner()

def run_b2d_adapter_pilot(args):
    if dry_plan(args,[{'operation':'one frozen lightweight adapter training and validation pilot','formal_gates':'BLOCKED'}]):return 0
    if Path(sys.prefix).resolve()!=UNIDRIVE_ENV.resolve():raise RuntimeError('Use isolated UniDrive Conda')
    audit=ROOT/'audits/dac2027_adapter_pilot_20261106';protocol=read_json(audit/'TRAINING_PROTOCOL.json');feature_m=verified_manifest(ROOT/'outputs/linux_b2d_corpus_features_20261106/manifest.json');feature_base=Path(feature_m['run_dir']);corpus_m=verified_manifest(feature_m['identity']['config']['corpus_manifest']);corpus_base=Path(corpus_m['run_dir']);samples=read_json(corpus_base/'raw/samples.json');partitions=b2d_assert_partition_separation(samples);index=read_json(feature_base/'raw/feature_index.json')
    config={'mode':args.mode,'protocol':protocol,'feature_manifest':str(feature_base/'manifest.json'),'feature_manifest_sha256':file_hash(feature_base/'manifest.json'),'corpus_manifest':str(corpus_base/'manifest.json'),'corpus_manifest_sha256':file_hash(corpus_base/'manifest.json'),'scope':'FROZEN_ONE_RUN_IMITATION_ADAPTER_PILOT_NOT_SAFE_PLANNING_OR_FORMAL_TEST','gate_promoted':False}
    run=StageRun('stage02_real_vla',args,config,['REAL_GPU','TRAINED_ADAPTER_PILOT','OFFLINE_ADAPTER_VALIDATION'],[audit/'TRAINING_PROTOCOL.json',audit/'CORPUS_PROTOCOL.md',audit/'VALIDATION_SELECTION.json']);run.path=run.path.resolve();completed=0;events=[];history=[]
    try:
        os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
        import torch,random,numpy as np
        torch.set_num_threads(4);torch.manual_seed(protocol['seed']);np.random.seed(protocol['seed']);random.seed(protocol['seed']);torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        by_id={r['sample_id']:r for r in samples};records={r['sample_id']:r for r in index}
        if set(by_id)!=set(records) or len(index)!=len(records):raise ValueError('Feature corpus incomplete or duplicated')
        cache={}
        for identity,row in records.items():
            if file_hash(row['feature_path'])!=row['feature_sha256']:raise ValueError('Actual feature bytes changed')
            saved=torch.load(row['feature_path'],map_location='cpu',weights_only=True);sample=by_id[identity]
            if saved['sample_id']!=identity or saved['observation_sha256']!=sample['observation_sha256'] or saved['future_targets_in_features'] is not False:raise ValueError('Feature/input provenance mismatch')
            if not all(sample['expert_target']['contiguous_prefix_mask']):raise ValueError('Training pilot requires frozen complete supervision')
            cache[identity]={'features':{k:v.float() for k,v in saved['features'].items()},'original':saved['original_trajectory'].float().unsqueeze(0),'target':torch.tensor(sample['expert_target']['absolute_xy'],dtype=torch.float32).unsqueeze(0)}
        groups={}
        for row in samples:
            if row['split']=='train':groups.setdefault(row['clip'],[]).append(row['sample_id'])
        clips=sorted(groups);validation=[r['sample_id'] for r in samples if r['split']=='validation'];train_ids=[r['sample_id'] for r in samples if r['split']=='train'];rng=random.Random(protocol['seed'])
        def batch(identities):
            features={k:torch.cat([cache[x]['features'][k] for x in identities],dim=0).cuda() for k in cache[identities[0]]['features']};original=torch.cat([cache[x]['original'] for x in identities],dim=0).cuda();target=torch.cat([cache[x]['target'] for x in identities],dim=0).cuda();return features,original,target
        def measured(label,fn,**metadata):
            torch.cuda.synchronize();a=torch.cuda.Event(enable_timing=True);b=torch.cuda.Event(enable_timing=True);t=time.perf_counter_ns();a.record();value=fn();b.record();torch.cuda.synchronize();events.append({'event':label,'cuda_elapsed_ms':a.elapsed_time(b),'wall_ms':(time.perf_counter_ns()-t)/1e6,**metadata});return value
        def screen(traj):
            values=np.asarray(traj);velocity=np.diff(np.vstack([np.zeros((1,2)),values]),axis=0)/.5;speed=np.linalg.norm(velocity,axis=1);acc=np.linalg.norm(np.diff(velocity,axis=0)/.5,axis=1)
            return {'finite':bool(np.isfinite(values).all()),'max_speed_mps':float(speed.max()),'max_vector_acceleration_mps2':float(acc.max()),'kinematic_screen_pass':bool(speed.max()<=protocol['kinematic_screen']['max_segment_speed_mps'] and acc.max()<=protocol['kinematic_screen']['max_vector_acceleration_mps2'])}
        with writer_lock(ROOT/'results/shared_gpu_resource'):
            model=build_b2d_refinement_adapter(protocol['hidden_dim'],protocol['max_delta_per_axis_per_quantum_m'],protocol['quanta']).cuda();parameters=sum(p.numel() for p in model.parameters())
            if parameters>protocol['max_parameters']:raise DependencyBlocked('Frozen adapter parameter budget exceeded')
            optimizer=torch.optim.AdamW(model.parameters(),lr=protocol['learning_rate'],weight_decay=protocol['weight_decay']);start=time.monotonic();torch.cuda.reset_peak_memory_stats();model.train()
            with (run.path/'raw/training_batches.jsonl').open('w') as batch_log:
                for step in range(protocol['train_steps']):
                    if time.monotonic()-start>protocol['max_training_wall_s']:raise DependencyBlocked('Frozen training wall budget exhausted')
                    chosen=[rng.choice(groups[rng.choice(clips)]) for _ in range(protocol['batch_size'])]
                    if any(by_id[x]['split']!='train' for x in chosen):raise ValueError('Validation leak into optimizer batch')
                    features,base,target=batch(chosen);optimizer.zero_grad(set_to_none=True);candidates=model(features,base);loss=sum(w*torch.nn.functional.smooth_l1_loss(pred,target,beta=1.) for w,pred in zip(protocol['loss_quanta_weights'],candidates))
                    if not torch.isfinite(loss):raise ValueError('Nonfinite real training loss')
                    loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),protocol['gradient_clip_norm'])
                    if not torch.isfinite(norm):raise ValueError('Nonfinite gradient')
                    optimizer.step();completed+=1;row={'step':completed,'loss':float(loss.detach()),'gradient_norm_before_clip':float(norm),'samples_sha256':digest(chosen)};history.append(row);batch_log.write(canonical({'step':completed,'sample_ids':chosen})+'\n')
                    if completed%25==0:batch_log.flush();atomic_json(run.path/'metrics/training_progress.json',{'steps':completed,'loss':row['loss'],'elapsed_s':time.monotonic()-start});run.log('training_progress',**row)
                    if torch.cuda.max_memory_allocated()>protocol['max_training_gpu_allocated_bytes']:raise DependencyBlocked('Training GPU budget exceeded')
            torch.cuda.synchronize();training_wall=time.monotonic()-start;training_peak=torch.cuda.max_memory_allocated();write_csv(run.path/'metrics/training_curve.csv',history)
            checkpoint=run.path/'raw/adapter_final.pt';torch.save({'state_dict':model.state_dict(),'optimizer':optimizer.state_dict(),'training_steps':completed,'protocol':protocol,'feature_manifest_sha256':config['feature_manifest_sha256'],'initialization':'New adapter trained in this run; not original pretrained checkpoint'},checkpoint);checkpoint_hash=file_hash(checkpoint);model.eval()
            # Actual-input gradient positive control after fitting; never optimizer data from validation.
            f,base,target=batch([train_ids[0]]);probe={k:v.detach().requires_grad_(True) for k,v in f.items()};pred=model(probe,base)[-1];gradients=torch.autograd.grad(pred.sum(),tuple(probe.values()),allow_unused=True);gradient_result={k:float(g.norm()) if g is not None else 0. for k,g in zip(probe,gradients)}
            atomic_json(run.path/'metrics/feature_gradient_control.json',{'real_training_sample':train_ids[0],'gradient_norms':gradient_result,'checkpoint_sha256':checkpoint_hash,'optimizer_steps_added':0});del f,base,target,probe,pred,gradients
            evaluations=[]
            with torch.no_grad():
                # Preserve all per-quantum candidates. These validation outputs
                # never select a checkpoint, optimizer step, or hyperparameter.
                for split,identities in (('train',train_ids),('validation',validation)):
                    for position,identity in enumerate(identities):
                        features,base,target=batch([identity]);truth=target[0].cpu().numpy();original=base[0].cpu().numpy();record={'sample_id':identity,'clip':by_id[identity]['clip'],'split':split,'expert_xy':truth.tolist(),'candidates':{}}
                        def append(label,value):
                            xy=value[0].detach().cpu().numpy();error=np.linalg.norm(xy-truth,axis=-1);record['candidates'][label]={'trajectory_xy':xy.tolist(),'ADE_m':float(error.mean()),'FDE_m':float(error[-1]),'L2_by_horizon_m':error.tolist(),**screen(xy)}
                        append('original',base)
                        state=measured('adapter_prepare',lambda:model.prepare(features,base),sample_id=identity,split=split);key_ptr=state['keys'].data_ptr();value_ptr=state['values'].data_ptr()
                        for quantum in range(protocol['quanta']):
                            state=measured('refine_quantum',lambda:model.advance(state),sample_id=identity,split=split,quantum=quantum+1)
                            if state['keys'].data_ptr()!=key_ptr or state['values'].data_ptr()!=value_ptr:raise ValueError('Refinement unexpectedly recomputed encoded features')
                            append('refine_'+str(quantum+1),state['trajectory'])
                        if split=='validation':
                            zero={k:torch.zeros_like(v) for k,v in features.items()};other_identity=identities[(position+1)%len(identities)];other,_,_=batch([other_identity])
                            for label,control in (('zero_features',zero),('cyclic_other_features',other)):
                                outputs=model(control,base)
                                for quantum,value in enumerate(outputs,1):append(label+'_'+str(quantum),value)
                            record['cyclic_control_source']=other_identity
                        evaluations.append(record)
                        with (run.path/'raw/predictions.jsonl').open('a') as handle:handle.write(canonical(record)+'\n')
                # A -> distinct B -> A resume on real GPU with actual source features.
                a_id=groups[clips[0]][0];b_id=groups[clips[1]][0];fa,ba,_=batch([a_id]);fb,bb,_=batch([b_id]);a=model.prepare(fa,ba);uninterrupted=[]
                for _ in range(protocol['quanta']):a=model.advance(a);uninterrupted.append(a['trajectory'].clone())
                a=model.advance(model.prepare(fa,ba));saved=measured('pause_state_gpu_clone',lambda:{k:v.clone() if isinstance(v,torch.Tensor) else v for k,v in a.items()});state_bytes=sum(v.numel()*v.element_size() for v in saved.values() if isinstance(v,torch.Tensor));measured('interleaved_B_all_quanta',lambda:model(fb,bb));restored=measured('resume_state_gpu_clone',lambda:{k:v.clone() if isinstance(v,torch.Tensor) else v for k,v in saved.items()});differences=[]
                for q in range(1,protocol['quanta']):restored=model.advance(restored);differences.append(float((restored['trajectory']-uninterrupted[q]).abs().max()))
                reuse={'a_sample':a_id,'b_sample':b_id,'saved_after_quantum':1,'candidate_max_abs_errors_m':differences,'tolerance_m':protocol['numeric_equivalence_tolerance_m'],'equivalent':max(differences)<=protocol['numeric_equivalence_tolerance_m'],'state_bytes':state_bytes,'feature_encoder_reexecuted_on_resume':False,'scope':'Real GPU adapter state diagnostic, not integrated preemptible runtime'};atomic_json(run.path/'metrics/adapter_state_reuse.json',reuse)
            if file_hash(checkpoint)!=checkpoint_hash:raise ValueError('Final checkpoint mutated during validation')
        write_csv(run.path/'metrics/gpu_events.csv',events);summaries=[]
        for split in ('train','validation'):
            subset=[r for r in evaluations if r['split']==split];labels=list(subset[0]['candidates'])
            for label in labels:
                per_clip=[]
                for clip in sorted({r['clip'] for r in subset}):
                    rows=[r for r in subset if r['clip']==clip];per_clip.append({'clip':clip,'samples':len(rows),'ADE_m':sum(r['candidates'][label]['ADE_m'] for r in rows)/len(rows),'FDE_m':sum(r['candidates'][label]['FDE_m'] for r in rows)/len(rows),'improvement_over_original_ADE_m':sum(r['candidates']['original']['ADE_m']-r['candidates'][label]['ADE_m'] for r in rows)/len(rows),'kinematic_screen_failures':sum(not r['candidates'][label]['kinematic_screen_pass'] for r in rows)})
                summaries.append({'split':split,'candidate':label,'samples':len(subset),'source_clips':len(per_clip),'sample_mean_ADE_m':sum(r['candidates'][label]['ADE_m'] for r in subset)/len(subset),'clip_mean_ADE_m':sum(r['ADE_m'] for r in per_clip)/len(per_clip),'clip_improvement_bootstrap':bootstrap_mean([r['improvement_over_original_ADE_m'] for r in per_clip],seed=protocol['seed'],n=2000),'samples_improved_over_original':sum(r['candidates'][label]['ADE_m']<r['candidates']['original']['ADE_m'] for r in subset),'kinematic_screen_failures':sum(r['kinematic_screen_failures'] for r in per_clip),'per_clip':per_clip})
        validation_rows=[r for r in evaluations if r['split']=='validation'];regressions=[{'from':'original' if q==1 else 'refine_'+str(q-1),'to':'refine_'+str(q),'worse_samples':sum(r['candidates']['refine_'+str(q)]['ADE_m']>r['candidates']['original' if q==1 else 'refine_'+str(q-1)]['ADE_m'] for r in validation_rows),'samples':len(validation_rows)} for q in range(1,4)]
        timing={kind:{'n':len(values),'wall_p50_ms':quantile(values,.5),'wall_p95_ms':quantile(values,.95)} for kind in ('adapter_prepare','refine_quantum','pause_state_gpu_clone','resume_state_gpu_clone') for values in [[r['wall_ms'] for r in events if r['event']==kind]]}
        result={'training_steps':completed,'parameter_count':parameters,'training_wall_s':training_wall,'training_peak_gpu_allocated_bytes':training_peak,'checkpoint_path':str(checkpoint),'checkpoint_sha256':checkpoint_hash,'train_samples':len(train_ids),'validation_samples':len(validation),'route_keys':partitions,'summaries':summaries,'successive_validation_regressions':regressions,'real_feature_gradient_control':gradient_result,'gpu_timing':timing,'state_reuse':reuse,'gate_promoted':False,'formal_tables':'NOT_AVAILABLE','limitations':['Imitation-only small-corpus adapter pilot; no road/dynamic safety loss or live control','Original full10-step plan is base candidate, not an accepted legal Fast','Feature preparation, original VLA prefix and all original flow steps remain charged before adapter refinement','Validation split separated by source route; complete foundation pretraining exposure unknown','Zero/shuffled features are explicit ablation controls, not replacement backends','Single seed, five validation clips; nested frames are not independent episodes','All regressions retained; useful refinement and safety gates require independent quality and closed-loop evidence']}
        atomic_json(run.path/'metrics/adapter_pilot.json',result);run.record({'kind':'real_trained_adapter_pilot'},result);return run.finish('PARTIAL',canonical(result),['No accepted safe Fast, road/dynamic validity, calibrated online AVL or integrated runtime'],acceptance='BLOCKED')
    except BaseException:
        error=traceback.format_exc();atomic_json(run.path/'metrics/training_failure.json',{'completed_training_steps':completed,'history':history,'error':error});run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')

def run_b2d_supervision_audit(args):
    if dry_plan(args,[{'operation':'official real clip conversion and temporal supervision audit','training':False}]):return 0
    import ast,types,copy,pickle,collections,gzip
    resources=verified_manifest(ROOT/'outputs/linux_b2d_resource_audit_20261106/manifest.json');data=read_json(Path(resources['run_dir'])/'metrics/data_resources.json')
    if data['clip_status']!='COMPLETED':raise DependencyBlocked('Verified actual clip required')
    converter=UNIDRIVE_REPO/'Bench2Drive/tools/data_converter/bench2drive_converter.py';dataset=UNIDRIVE_REPO/'Bench2Drive/projects/mmdet3d_plugin/datasets/bench2drive_dataset.py'
    protocol=ROOT/'audits/dac2027_data_semantics_20261106/PROTOCOL.md';clip=data['selected_clip'].removesuffix('.tar.gz');clip_root=Path(data['extracted'])/clip
    config={'mode':args.mode,'resource_manifest_sha256':file_hash(ROOT/'outputs/linux_b2d_resource_audit_20261106/manifest.json'),'archive_sha256':file_hash(data['archive']),'clip':clip,'scope':'REAL_OFFICIAL_TRAINING_CLIP_CONTRACT_DEVELOPMENT_NOT_HELDOUT','online_truth_allowed':False,'training_steps':0,'gate_promoted':False}
    run=StageRun('stage02_real_vla',args,config,['OFFICIAL_REAL_DATA_CONVERSION','OFFLINE_SUPERVISION_AUDIT'],[converter,dataset,protocol,ROOT/'audits/dac2027_data_semantics_20261106/DYNAMIC_SUPERVISION_PROTOCOL.md'])
    try:
        raw=run.path.resolve()/'raw';root=raw/'official_data';(root/'v1').mkdir(parents=True);(root/'v1'/clip).symlink_to(clip_root,target_is_directory=True)
        helper=raw/'convert_official.py';helper.write_text('''import importlib.util,sys,json\nfrom pathlib import Path\nsource,root,out,clip=sys.argv[1:]\nspec=importlib.util.spec_from_file_location('official_b2d_converter',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\nm.DATAROOT=root;m.OUT_DIR=out\nPath(out).mkdir(parents=True,exist_ok=True)\nm.preprocess(['v1/'+clip],0,'contract_development','train')\nprint(json.dumps({'conversion_completed':True,'source_modified':False,'visibility_filter_unchanged':m.FILTER_INVISINLE}))\n''')
        probe=native_probe(run,'official_clip_conversion',[sys.executable,helper,converter,root,raw/'infos',clip],ROOT,timeout=300)
        if probe['returncode']!=0:return run.finish('BLOCKED',canonical(probe),['Actual official converter failed; raw diagnostics retained'],acceptance='BLOCKED')
        infos_path=raw/'infos/contract_development/b2d_infos_train_0.pkl'
        # This pickle was produced by our pinned converter subprocess, not downloaded.
        infos=pickle.loads(infos_path.read_bytes());import numpy as np
        raw_ann=sorted((clip_root/'anno').glob('*.json.gz'));info_frames={r['frame_idx'] for r in infos};raw_frames={int(f.name.split('.')[0]) for f in raw_ann}
        annotations={int(f.name.split('.')[0]):json.load(gzip.open(f,'rt')) for f in raw_ann}
        source=dataset.read_text();tree=ast.parse(source);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Bench2DriveDataset');methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
        selected=[copy.deepcopy(methods[n]) for n in ('_split_data_infos','get_agent_trajs','get_ego_temporal_trajs')];module=ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[]));(raw/'extracted_official_temporal.py.txt').write_text(ast.unparse(module));ns={'np':np};exec(compile(module,str(dataset),'exec'),ns)
        official=types.SimpleNamespace(data_infos=infos,split_group=5)
        for name in ('_split_data_infos','get_agent_trajs','get_ego_temporal_trajs'):setattr(official,name,types.MethodType(ns[name],official))
        official._split_data_infos();records=[];rows=[];ego_rows=[];time_rows=[]
        for i,r in enumerate(official.data_infos):
            prior_delta,prior_mask=official.get_agent_trajs(i,6,1);corrected=b2d_future_targets(infos,r);correct_mask=np.asarray(corrected['delta_mask'],dtype=bool);correct_delta=np.asarray(corrected['origin_delta_xy']);velocity=np.asarray(corrected['velocity_xy_mps']);accel=np.asarray(corrected['acceleration_xy_mps2']);acc_mask=np.asarray(corrected['acceleration_mask'],dtype=bool)
            records.append({'frame_idx':int(r['frame_idx']),'corrected':corrected,'official_delta_xy':prior_delta.tolist(),'official_mask':prior_mask.tolist()})
            for actor_idx,actor in enumerate(r['gt_ids']):
                for step in range(6):
                    good=bool(correct_mask[actor_idx,step]);old=bool(prior_mask[actor_idx,step]);rows.append({'frame_idx':int(r['frame_idx']),'actor_id':int(actor),'delay_s':.5*(step+1),'official_valid':old,'timestamp_endpoint_valid':good,'official_accepted_without_two_endpoints':old and not good,'official_rejected_available_pair':good and not old,'same_pair_delta_error_m':float(np.linalg.norm(prior_delta[actor_idx,step]-correct_delta[actor_idx,step])) if good and old else None,'actual_pair_speed_mps':float(np.linalg.norm(velocity[actor_idx,step])) if good else None,'source_formula_speed_mps':float(np.linalg.norm(correct_delta[actor_idx,step]/(10/5))) if good else None})
            for j in range(1,7):
                if i+j<len(official.data_infos) and official.data_infos[i+j]['folder']==r['folder']:
                    actual=(official.data_infos[i+j]['frame_idx']-r['frame_idx'])/10;time_rows.append({'capture_frame':int(r['frame_idx']),'horizon_index':j,'expected_s':j*.5,'official_index_dt_s':actual,'time_matches':abs(actual-j*.5)<1e-8})
            ego_delta,ego_mask=official.get_ego_temporal_trajs(i,6,5)
            ego_rows.append({'frame_idx':int(r['frame_idx']),'valid_waypoints':int(ego_mask.sum()),'delta_xy':ego_delta.tolist(),'mask':ego_mask.tolist()})
        with (raw/'future_targets.jsonl').open('w') as f:
            for r in records:f.write(canonical(r)+'\n')
        dynamic_rows=[]
        with (raw/'dynamic_box_targets.jsonl').open('w') as f:
            for capture in infos:
                target,comparison=b2d_dynamic_box_targets(capture,annotations);f.write(canonical(target)+'\n');dynamic_rows.extend(comparison)
        write_csv(run.path/'metrics/static_vs_future_cuboids.csv',dynamic_rows)
        write_csv(run.path/'metrics/actor_target_comparison.csv',rows);write_csv(run.path/'metrics/official_index_times.csv',time_rows);atomic_json(raw/'ego_targets.json',ego_rows)
        input_hashes={str(f):file_hash(f) for f in clip_root.rglob('*') if f.is_file()};atomic_json(raw/'input_hashes.json',input_hashes)
        image_paths=[root/s['data_path'] for r in infos for key,s in r['sensors'].items() if key!='LIDAR_TOP'];geometry=[]
        for frame in sorted(info_frames):
            ann=json.load(gzip.open(clip_root/'anno'/f'{frame:05d}.json.gz','rt'));r=next(x for x in infos if x['frame_idx']==frame)
            for box,actor in zip(r['gt_boxes'],r['gt_ids']):
                npc=next(n for n in ann['bounding_boxes'] if int(n['id'])==actor);expected=np.asarray(npc['extent'])[[1,0,2]]*2;geometry.append(float(np.max(np.abs(box[3:6]-expected))))
        result={'raw_annotation_frames':len(raw_ann),'converted_frames':len(infos),'omitted_raw_frame_indices':sorted(raw_frames-info_frames),'six_camera_references':len(image_paths),'missing_images':sum(not p.is_file() for p in image_paths),'bbox_size_roundtrip_max_abs_m':max(geometry,default=None),'actor_horizon_targets':len(rows),'official_valid':sum(r['official_valid'] for r in rows),'endpoint_timestamp_valid':sum(r['timestamp_endpoint_valid'] for r in rows),'official_accepted_without_two_endpoints':sum(r['official_accepted_without_two_endpoints'] for r in rows),'official_rejected_available_pair':sum(r['official_rejected_available_pair'] for r in rows),'paired_delta_max_error_m':max((r['same_pair_delta_error_m'] for r in rows if r['same_pair_delta_error_m'] is not None),default=None),'source_index_timestamp_mismatches':sum(not r['time_matches'] for r in time_rows),'source_speed_formula':'offset/(10/split_group) divides by2 at split_group5; verified timestamps require dt0.5 => speed is quarter of dt-based value','source_acceleration_formula':'abs(v_next - v_prev/(10/split_group)); missing parentheses and reciprocal-time mismatch, not (v_next-v_prev)/dt','map_contract':'Broken/Solid/SolidSolid are marking types, Center lane centerline; none alone certifies drivable outer boundary','labels_do_not_imply_safe_plan':True,'data_split':'KNOWN_QA_TRAINING_CLIP_USED_FOR_CONTRACT_DEVELOPMENT','training_infos_scope':'ONE_OFFICIAL_CLIP_ONLY_NOT_COMPLETE_CHECKPOINT_TRAINING_INFOS','input_files_hashed':len(input_hashes),'training_steps':0,'model_forwards':0,'gate_promoted':False,'limits':['Corrected function is offline supervision only and does not feed online AVL','Official converter visibility subset may omit valid actors; missing pairs remain invalid','No full future oriented-box or static-road free-space supervision implemented','One source clip cannot establish model quality or independent generalization','Current source audit does not reconstruct historical checkpoint training']}
        result['limits'][2]='Future annotated cuboids implemented offline at six sampled times; continuous swept volume, height overlap and static-road free space not verified'
        valid_dynamic=[r for r in dynamic_rows if r['valid_cuboids']]
        result['dynamic_cuboid_supervision']={'actor_time_denominator':len(dynamic_rows),'valid':len(valid_dynamic),'missing_future_frame':sum(not r['future_frame_present'] for r in dynamic_rows),'missing_future_actor_in_present_frame':sum(r['future_frame_present'] and not r['future_actor_present'] for r in dynamic_rows),'class_coverage':dict(collections.Counter(r['actor_class'] for r in dynamic_rows)),'static_overlap_samples':sum(r['recorded_static_overlap'] for r in valid_dynamic),'dynamic_overlap_samples':sum(r['recorded_dynamic_overlap'] for r in valid_dynamic),'static_dynamic_disagreements':sum(r['recorded_static_overlap']!=r['recorded_dynamic_overlap'] for r in valid_dynamic),'target_displacement_max_m':max((r['target_displacement_m'] for r in valid_dynamic),default=None),'scope':'Recorded expert ego body vs recorded actor bodies; offline sampled planar overlap, NOT official collision/continuous safety'}
        atomic_json(run.path/'metrics/supervision_audit.json',result);run.record({'kind':'real_clip_supervision_contract'},result)
        return run.finish('PARTIAL',canonical(result),['Full independent supervised dataset/maps and safeFast/refinement training not established'],acceptance='BLOCKED')
    except BaseException:
        error=traceback.format_exc();run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')

def run_b2d_resource_audit(args):
    """Recover official split and attempt only one pinned, bounded data clip."""
    if dry_plan(args,[{'operation':'official split/resource audit plus one bounded clip','max_archive_bytes':1024**3,'training':False}]):return 0
    import shutil,tarfile,collections
    from stage00_environment import download_file
    audit=ROOT/'audits/dac2027_data_semantics_20261106';discovery=audit/'discovery'
    benchmark=Path(os.environ['FRAMELEASE_BENCHMARK_ROOT']);mini=read_json(benchmark/'docs/bench2drive_mini_10.json');base=read_json(benchmark/'docs/bench2drive_base_1000.json')
    split_file=discovery/'bench2drive_base_train_val_split.json';split=read_json(split_file)
    if file_hash(split_file)!='a2b1cbfe87b6a707fdd46ee47da4e07ef5338d96a8231860b44fb722c24e365e':raise ValueError('Official split hash mismatch')
    candidates=read_json(ROOT/'outputs/linux_split_audit_20261106/manifest.json');reserved=read_json(Path(candidates['run_dir'])/'metrics/split_audit.json')['candidates'];reserved_keys={(r['town'],r['route_id']) for r in reserved if 'route_id' in r}
    eligible=[]
    for name,info in mini.items():
        parsed=parse_unidrive_route_directory(name.removesuffix('.tar.gz'))
        if 'v1/'+name.removesuffix('.tar.gz') in split['val'] or (parsed['town'],parsed['route_id']) in reserved_keys:continue
        if info['size']<=1024**3:eligible.append((info['size'],name,info))
    size,name,expected=min(eligible);free=shutil.disk_usage(ROOT).free
    if free-size-2*1024**3<20*1024**3:raise DependencyBlocked('Bounded archive+extraction would violate disk reserve')
    config={'mode':args.mode,'split_sha256':file_hash(split_file),'source_revision':read_json(discovery/'zoo_commit.raw')['sha'],'selected_clip':name,'expected_bytes':size,'expected_sha256':expected['sha256'],'selection':'Smallest official Mini clip outside official validation and reserved candidate route keys; contract-development only','max_extraction_bytes':2*1024**3,'training':False,'gate_promoted':False}
    dependencies=[split_file,discovery/'DATA_PREP.md',discovery/'github_blob_records.json',benchmark/'docs/bench2drive_mini_10.json',benchmark/'docs/bench2drive_base_1000.json',benchmark/'docs/anno.md',benchmark/'LICENSE',audit/'PROTOCOL.md']
    run=StageRun('stage02_real_vla',args,config,['OFFICIAL_METADATA_AUDIT','BOUNDED_DATA_ACQUISITION'],dependencies)
    try:
        destination=ROOT/'datasets/Bench2Drive/official_splits'/config['source_revision']/split_file.name;destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists() and file_hash(destination)!=file_hash(split_file):raise ValueError('Existing split differs')
        if not destination.exists():shutil.copyfile(split_file,destination)
        val_dirs={Path(v).name for v in split['val']};base_dirs={n.removesuffix('.tar.gz') for n in base};annot=read_json(ROOT/'outputs/linux_split_audit_20261106/manifest.json');import csv
        with (Path(annot['run_dir'])/'metrics/training_directories.csv').open() as f:annotation_dirs={r['directory'] for r in csv.DictReader(f)}
        target=ROOT/'datasets/Bench2Drive/contract_development'/expected['sha256']/name;attempts=[]
        for host in ('huggingface.co','hf-mirror.com'):
            url=f'https://{host}/datasets/rethinklab/Bench2Drive/resolve/main/{name}'
            result=download_file(url,target,size,expected['sha256'],timeout=10,retries=1);attempts.append({'host':host,'url':url,'result':result})
            atomic_json(run.path/'raw/acquisition_attempts.json',attempts)
            if result['status']=='COMPLETED':break
        inventory=[];extracted=None
        if result['status']=='COMPLETED':
            with tarfile.open(target,'r:gz') as archive:
                members=archive.getmembers();total=0;names=set()
                for m in members:
                    path=Path(m.name)
                    if path.is_absolute() or '..' in path.parts or m.issym() or m.islnk() or not (m.isfile() or m.isdir()):raise ValueError('Unsafe tar entry')
                    if m.name in names:raise ValueError('Duplicate tar member')
                    names.add(m.name);total+=m.size
                    if total>config['max_extraction_bytes']:raise DependencyBlocked('Clip exceeds frozen extraction budget; archive retained')
                    inventory.append({'name':m.name,'bytes':m.size,'is_file':m.isfile()})
                extracted=target.parent/'extracted';extracted.mkdir(exist_ok=True)
                for m in members:
                    out=extracted/m.name
                    if m.isdir():out.mkdir(parents=True,exist_ok=True);continue
                    out.parent.mkdir(parents=True,exist_ok=True)
                    if out.exists():
                        import hashlib
                        h=hashlib.sha256()
                        with archive.extractfile(m) as src:
                            for block in iter(lambda:src.read(1024*1024),b''):h.update(block)
                        if out.stat().st_size!=m.size or file_hash(out)!=h.hexdigest():raise ValueError('Existing extracted member differs from verified archive')
                    else:
                        with archive.extractfile(m) as src,out.open('xb') as dst:shutil.copyfileobj(src,dst)
            write_csv(run.path/'metrics/archive_inventory.csv',inventory)
        result={'official_base_clip_count':len(base_dirs),'official_val_clip_count':len(val_dirs),'val_not_in_base':sorted(val_dirs-base_dirs),'known_QA_clip_count':len(annotation_dirs),'known_QA_intersection_official_val':sorted(annotation_dirs&val_dirs),'base_minus_official_val_equals_known_QA':base_dirs-val_dirs==annotation_dirs,'base_training_names_missing_from_QA':sorted(base_dirs-val_dirs-annotation_dirs),'QA_names_missing_from_base_training':sorted(annotation_dirs-(base_dirs-val_dirs)),'split_installed':str(destination),'split_sha256':file_hash(destination),'selected_clip':config['selected_clip'],'selected_in_QA_training':name.removesuffix('.tar.gz') in annotation_dirs,'clip_status':result['status'],'archive':str(target),'extracted':str(extracted) if extracted else None,'uncompressed_bytes':sum(r['bytes'] for r in inventory),'attempts':attempts,'disk_free_before_bytes':free,'disk_free_after_bytes':shutil.disk_usage(ROOT).free,'checkpoint_training_exposure':'Still unknown: current upstream split and matching QA directories do not prove checkpoint full training lineage','usage':'Public research contract-development audit only; CC-BY-NC-ND source retained locally, no redistribution','training_executed':False,'gate_promoted':False}
        atomic_json(run.path/'metrics/data_resources.json',result);run.record({'kind':'official_split_and_bounded_data_resources'},result)
        blockers=['Full infos/maps and independent training lineage not established; no adapter training']
        if result['clip_status']!='COMPLETED':blockers.append('Pinned minimum real clip download blocked; raw errors retained')
        return run.finish('PARTIAL',canonical(result),blockers,acceptance='BLOCKED')
    except BaseException:
        error=traceback.format_exc();run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')

def run_minddrive_linux_audit(args):
    if dry_plan(args,[{'operation':'MindDrive3B Linux feasibility; no weight download/model switch'}]):return 0
    import ast,shutil,importlib.metadata
    repo=ROOT/'third_party/MindDrive';revision='1a4085dab1c20895a0c8d2b67b4f8e65712fa8de';accept=read_json(ROOT/'audits/route_a/acceptance.json')
    if accept['compatibility_episode_completed_count']<4 or accept['gates']['4']['status']!='BLOCKED':raise ValueError('Expected evidenced native/quality blocker before fallback audit')
    if subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()!=revision:raise ValueError('MindDrive revision mismatch')
    paths=['README.md','LICENSE','requirements.txt','adzoo/minddrive/configs/minddrive_qwen25_3B_infer.py','team_code/minddrive_b2d_agent.py','mmcv/models/detectors/minddrive.py','rl_projects/leaderboard/leaderboard_evaluator.py']
    config={'mode':args.mode,'backend':'MindDrive3B','source_commit':revision,'trigger_acceptance_sha256':file_hash(ROOT/'audits/route_a/acceptance.json'),'trigger':'Four completed UniDrive development episodes collided; useful refinement unproven','scope':'Native Linux source/resource/current-environment import audit, no model load','gate_promoted':False}
    run=StageRun('stage02_real_vla',args,config,['SOURCE_AUDIT','ENVIRONMENT_PROBE'],[*(repo/p for p in paths),ROOT/'audits/route_a/minddrive_hf.json',ROOT/'audits/dac2027_data_semantics_20261106/PROTOCOL.md'])
    try:
        env=os.environ.copy();env['PYTHONPATH']=os.pathsep.join([str(repo),str(repo/'rl_projects'),os.environ.get('PYTHONPATH','')])
        probe=native_probe(run,'minddrive_linux_agent_available_environment',[sys.executable,'-c','from team_code.minddrive_b2d_agent import MinddriveAgent; print(MinddriveAgent)'],repo,env)
        alias=run.path.resolve()/'raw/python_alias';alias.mkdir();(alias/'Bench2DriveZoo').symlink_to(repo,target_is_directory=True)
        alias_env=env.copy();alias_env['PYTHONPATH']=str(alias)+os.pathsep+env['PYTHONPATH']
        alias_probe=native_probe(run,'minddrive_linux_agent_expected_package_layout',[sys.executable,'-c','from team_code.minddrive_b2d_agent import MinddriveAgent; print(MinddriveAgent)'],repo,alias_env)
        apis=[{'api':name,'available':hasattr(os,name)} for name in ('setsid','killpg')]
        requirements=[]
        from packaging.requirements import Requirement
        for line in (repo/'requirements.txt').read_text().splitlines():
            line=line.split('#',1)[0].strip()
            if not line:continue
            try:
                req=Requirement(line)
                if req.marker is not None and not req.marker.evaluate():continue
                try:installed=importlib.metadata.version(req.name)
                except importlib.metadata.PackageNotFoundError:installed=None
                requirements.append({'requirement':line,'installed':installed,'compatible':installed is not None and (not req.specifier or installed in req.specifier)})
            except Exception as e:requirements.append({'requirement':line,'parse_error':str(e)})
        meta=read_json(ROOT/'audits/route_a/minddrive_hf.json');selected=[f for f in meta['files'] if f['rfilename']=='minddrive_3b_rltrain.pth' or f['rfilename'].startswith('llava-qwen2.5-3b/') and any(f['rfilename'].endswith(suffix) for suffix in ('.safetensors','config.json','index.json','tokenizer.json','tokens.json','merges.txt','vocab.json','tokens_map.json'))]
        # Separate the projector: it may be present in the final checkpoint, but
        # historical metadata alone cannot prove this without actual loading.
        projector=next(f for f in meta['files'] if f['rfilename']=='llava-qwen2.5-3b-eva02_petr_proj.pth');download=sum(f['size'] for f in selected);free=shutil.disk_usage(ROOT).free
        detector=repo/'mmcv/models/detectors/minddrive.py';tree=ast.parse(detector.read_text());symbols=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.FunctionDef) and n.name in ('simple_test','simple_test_pts','future_states_predict'):
                symbols.append({'symbol':n.name,'first_line':n.lineno,'last_line':n.end_lineno});(run.path/'raw'/(n.name+'.py.txt')).write_text(ast.get_source_segment(detector.read_text(),n))
        result={'platform':sys.platform,'process_apis':apis,'carla_binary_present':(Path(os.environ['CARLA_ROOT'])/'CarlaUE4.sh').is_file(),'old_platform_blocker_resolved':all(r['available'] for r in apis),'documented_environment':'Python3.8 torch2.4.1+cu118; official custom mmcv package; CARLA0.9.15','probe_environment':environment(),'import_probe':probe,'requirements_in_current_unidrive_environment':requirements,'same_environment_is_not_official_minddrive_validation':True,'checkpoint_metadata_revision':meta['revision'],'checkpoint_metadata_live_refresh':'Failed direct HF request retained in discovery; using previously pinned metadata, not a new verification','required_download_files':selected,'download_bytes_lower_bound':download,'projector_additional_if_needed':projector,'free_disk_bytes':free,'remaining_after_lower_bound_bytes':free-download,'reserve_20GiB_and_new_environment_budget_passed':free-download>20*1024**3,'fp32_infer':True,'inference_peak_vram':'NOT_MEASURED; archive bytes cannot establish VRAM','source_symbols':symbols,'anytime_interface':'future_states_predict computes six horizon states, point decoders stack a complete trajectory after the loop; no complete-trajectory iterative quality refinement interface established','selection':'NOT_SELECTED; no new safe baseline or anytime quality evidence; downloading3B would consume most reserve before isolated environment','model_loaded':False,'native_episode_executed':False,'training_executed':False,'gate_promoted':False}
        result['package_layout_probe']=alias_probe
        result['package_layout_repair']='Invocation-local Bench2DriveZoo symlink matches official absolute package imports; no source/environment mutation'
        atomic_json(run.path/'metrics/minddrive_linux_feasibility.json',result);run.record({'kind':'minddrive_linux_feasibility'},result)
        return run.finish('PARTIAL',canonical(result),['Official isolated environment and 3B loading unexecuted; disk budget and inference peak unresolved','Inspected path does not establish complete-plan refinement; no safety/refinement evidence'],acceptance='BLOCKED')
    except BaseException:
        error=traceback.format_exc();run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')

def run_minddrive_audit(args):
    repo=ROOT/'third_party/MindDrive';revision='1a4085dab1c20895a0c8d2b67b4f8e65712fa8de'
    if dry_plan(args,[{'mode':'minddrive-audit','conditional_on':'actual native UniDrive platform blocker','source':revision}]):return 0
    prior=read_json(ROOT/'audits/route_a/native_evaluator_platform.json')
    if prior.get('native_launch_possible') is not False:raise RuntimeError('Conditional fallback audit lacks a demonstrated UniDrive blocker')
    actual=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    if actual!=revision:raise ValueError('MindDrive source mismatch')
    sources=['README.md','LICENSE','requirements.txt','adzoo/minddrive/configs/minddrive_qwen25_3B_infer.py','team_code/minddrive_b2d_agent.py','mmcv/models/detectors/minddrive.py','rl_projects/leaderboard/leaderboard_evaluator.py']
    run=StageRun('stage02_real_vla',args,{'mode':args.mode,'backend':'MindDrive3B','source_commit':actual,'trigger':prior,'sources':{p:file_hash(repo/p) for p in sources}},['SOURCE_AUDIT','ENVIRONMENT_PROBE'],[repo/p for p in sources])
    try:
        meta=read_json(ROOT/'audits/route_a/minddrive_hf.json');file=next(f for f in meta['files'] if f['rfilename']=='minddrive_3b_rltrain.pth')
        # This is an explicitly labelled import probe in the available new environment,
        # not a test of the documented Python3.8/torch2.4.1 environment.
        env=os.environ.copy();env['PYTHONPATH']=os.pathsep.join([str(repo),str(repo/'rl_projects')])
        p=native_probe(run,'minddrive_agent_available_environment',[sys.executable,'-c','from team_code.minddrive_b2d_agent import MinddriveAgent; print(MinddriveAgent)'],repo,env)
        import ast
        evaluator=repo/sources[-1];tree=ast.parse(evaluator.read_text('utf8'));calls=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id=='os' and n.attr in ('setsid','killpg'):
                calls.append({'line':n.lineno,'api':ast.unparse(n),'available':hasattr(os,n.attr)})
        result={'source_commit':actual,'checkpoint_revision':meta['revision'],'checkpoint':file,'model_loaded':False,'official_score_is_local_measurement':False,'native_process_api':calls,'same_native_windows_blocker':any(not r['available'] for r in calls),'documented_environment':'Python3.8 torch2.4.1+cu118 Linux CARLA0.9.15','probe_environment':environment(),'probe_returncode':p['returncode'],'planning':'decision_expert LoRA action distribution -> action_expert features -> future_states_predict -> six temporal waypoints; horizon point loop is not quality-refinement depth','anytime_state_reuse':'NOT_VERIFIED; no complete-trajectory refinement API exposed by inspected inference path','memory':'checkpoint file size is not inference VRAM; fp32_infer=True in official3B config, actual GPU memory unavailable','data_license':'README identifies external Bench2Drive as CC BY-NC-ND4.0; code Apache2.0. Training data/split rights require dataset-specific audit','selection':'NOT_SELECTED; does not resolve evidenced native evaluator platform blocker'}
        run.record({'kind':'minddrive_feasibility'},result);atomic_json(run.path/'metrics/minddrive_feasibility.json',result)
        return run.finish('BLOCKED',canonical(result),['Native Linux evaluator unavailable on current host; candidate not substituted'],acceptance='BLOCKED')
    except BaseException:run.log('failure',traceback=traceback.format_exc());return run.finish('FAILED',traceback.format_exc())

def run_unidrive_model_load(args):
    """Execute original Agent.setup and verify all loaded state, without fake sensors."""
    if dry_plan(args,[{'operation':'official Agent.setup with checkpoint coverage','inference':False}]):return 0
    if Path(sys.prefix).resolve()!=UNIDRIVE_ENV.resolve():raise RuntimeError('Use isolated UniDrive Linux Conda')
    source=unidrive_source_audit();checkpoint=Path(os.environ['CHECKPOINT'])
    config={'mode':args.mode,'source':source,'checkpoint':str(checkpoint),'checkpoint_sha256':file_hash(checkpoint),'scope':'OFFICIAL_SETUP_ONLY_NO_FORWARD'}
    run=StageRun('stage02_real_vla',args,config,['MODEL_LOAD_AUDIT'],[UNIDRIVE_REPO/UNIDRIVE_AGENT,UNIDRIVE_REPO/UNIDRIVE_CONFIG])
    result={'model_loaded':False,'forward_executed':False,'closed_loop_executed':False};oldcwd=Path.cwd();old_save=os.environ.get('SAVE_PATH');original_loader=None;agent_module=None
    evidence_path=(run.path/'metrics/checkpoint_coverage.json').resolve()
    try:
        import collections,re,torch
        os.environ['SAVE_PATH']=str((run.path/'raw').resolve())
        os.chdir(UNIDRIVE_REPO/'Bench2Drive')
        from team_code import unidrivevla_b2d_agent as agent_module
        original_loader=agent_module.load_checkpoint
        def audited_load(model,filename,*a,**kw):
            ckpt=original_loader(model,filename,*a,**kw)
            state=ckpt.get('module',ckpt.get('state_dict',ckpt));state={re.sub(r'^module\.', '',k):v for k,v in state.items()}
            actual=model.state_dict();missing=sorted(set(actual)-set(state));unexpected=sorted(set(state)-set(actual));mismatch=[]
            for key in actual.keys() & state.keys():
                value=actual[key];saved=state[key]
                if value.shape!=saved.shape or not torch.equal(value.detach().cpu(),saved.to(dtype=value.dtype,device='cpu')):mismatch.append(key)
            coverage={'checkpoint_tensors':len(state),'model_state_tensors':len(actual),'missing':missing,'unexpected':unexpected,'mismatched_after_dtype_conversion':mismatch,'matched':len(actual)-len(missing)-len(mismatch),'comparison':'Exact equality after official model dtype conversion'}
            atomic_json(evidence_path,coverage);result['checkpoint_coverage']=coverage
            if missing or unexpected or mismatch:raise RuntimeError('Incomplete checkpoint loading; see checkpoint_coverage.json')
            return ckpt
        agent_module.load_checkpoint=audited_load
        # Constructor needs a real hero actor. Setup is independently callable; no
        # observation, sensor interface, trajectory or driving result is invented.
        agent=agent_module.UniDriveVLAB2DAgent.__new__(agent_module.UniDriveVLAB2DAgent)
        started=time.perf_counter()
        with writer_lock(ROOT/'results/shared_gpu_resource'):
            torch.cuda.reset_peak_memory_stats()
            agent.setup(str(UNIDRIVE_REPO/UNIDRIVE_CONFIG)+'+'+str(checkpoint))
            torch.cuda.synchronize()
        dtypes=collections.Counter()
        for parameter in agent.model.parameters():dtypes[str(parameter.dtype)]+=parameter.numel()
        result.update(model_loaded=True,setup_wall_s=time.perf_counter()-started,parameter_count=sum(p.numel() for p in agent.model.parameters()),parameter_dtypes=dict(dtypes),cuda_allocated_bytes=torch.cuda.memory_allocated(),cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved(),sensors=agent.sensors(),official_setup=True,full_constructor=False)
        # The run directory may be relative, so restore cwd before ledger writes.
        os.chdir(oldcwd);atomic_json(run.path/'metrics/model_load.json',result);run.record({'kind':'official_agent_setup_checkpoint_coverage'},result)
        return run.finish('PARTIAL',canonical(result),acceptance='BLOCKED')
    except BaseException:
        os.chdir(oldcwd);result['error']=traceback.format_exc();atomic_json(run.path/'metrics/model_load.json',result);run.log('failure',traceback=result['error'])
        run.record({'kind':'official_agent_setup_checkpoint_coverage'},result,'FAILED',result['error'])
        return run.finish('FAILED',canonical(result),[result['error']],acceptance='BLOCKED')
    finally:
        os.chdir(oldcwd)
        if original_loader is not None:agent_module.load_checkpoint=original_loader
        if old_save is None:os.environ.pop('SAVE_PATH',None)
        else:os.environ['SAVE_PATH']=old_save

def run_unidrive_replay(args):
    """Replay a saved real first-frame model call; no generated observation data."""
    if args.unidrive_input is None:raise ValueError('--unidrive-input is required')
    if dry_plan(args,[{'operation':'real recorded first observation replay','input':str(args.unidrive_input)}]):return 0
    if Path(sys.prefix).resolve()!=UNIDRIVE_ENV.resolve():raise RuntimeError('Use isolated UniDrive Conda')
    path=args.unidrive_input.resolve();reference=path.with_name('first_model_output.pt');checkpoint=Path(os.environ['CHECKPOINT'])
    config={'mode':args.mode,'backend':'UniDriveVLA','input':str(path),'input_sha256':file_hash(path),'reference_sha256':file_hash(reference) if reference.is_file() else None,'checkpoint_sha256':file_hash(checkpoint),'source':unidrive_source_audit(),'scope':'RECORDED_REAL_FIRST_FRAME_REPLAY','max_abs_tolerance':1e-5}
    run=StageRun('stage02_real_vla',args,config,['RECORDED_INPUT_REPLAY'],[UNIDRIVE_REPO/UNIDRIVE_AGENT,UNIDRIVE_REPO/UNIDRIVE_CONFIG,*sorted((ROOT/'linux/patches').glob('*.patch'))]);oldcwd=Path.cwd();old_save=os.environ.get('SAVE_PATH');result={'forward_executed':False,'closed_loop_executed':False}
    try:
        import torch,contextlib,numpy as np,random
        # Match the evaluator's construction seed as well as the captured forward
        # RNG. A checkpoint need not contain every nonpersistent runtime tensor.
        random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed)
        record=torch.load(path,map_location='cpu',weights_only=False);precision=record['precision']
        if precision not in ('official','bf16-autocast'):raise ValueError('Unknown recorded precision')
        os.environ['SAVE_PATH']=str((run.path/'raw').resolve());os.chdir(UNIDRIVE_REPO/'Bench2Drive')
        from team_code.unidrivevla_b2d_agent import UniDriveVLAB2DAgent
        def gpu(value):
            if isinstance(value,torch.Tensor):return value.cuda()
            if isinstance(value,dict):return {k:gpu(v) for k,v in value.items()}
            if isinstance(value,list):return [gpu(v) for v in value]
            if isinstance(value,tuple):return tuple(gpu(v) for v in value)
            return value
        with writer_lock(ROOT/'results/shared_gpu_resource'):
            agent=UniDriveVLAB2DAgent.__new__(UniDriveVLAB2DAgent);agent.setup(str(UNIDRIVE_REPO/UNIDRIVE_CONFIG)+'+'+str(checkpoint))
            inputs=gpu(record['args']);kwargs=gpu(record['kwargs']);torch.set_rng_state(record['torch_rng_state']);torch.cuda.set_rng_state_all(record['cuda_rng_state'])
            torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();begin=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
            started=time.perf_counter_ns();begin.record()
            context=torch.autocast('cuda',dtype=torch.bfloat16) if precision=='bf16-autocast' else contextlib.nullcontext()
            with torch.no_grad(),context:outputs=agent.model(*inputs,**kwargs)
            end.record();torch.cuda.synchronize();wall=(time.perf_counter_ns()-started)/1e6
            trajectory=outputs[0]['img_bbox']['final_planning'].detach().cpu();result.update(forward_executed=True,precision=precision,trajectory=trajectory.tolist(),shape=list(trajectory.shape),finite=bool(torch.isfinite(trajectory).all()),wall_ms=wall,cuda_event_ms=begin.elapsed_time(end),cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated())
            if reference.exists():
                expected=torch.load(reference,map_location='cpu',weights_only=False)[0]['img_bbox']['final_planning']
                result['reference_max_abs_error']=float((trajectory-expected).abs().max()) if trajectory.shape==expected.shape else None
                result['reference_equivalent']=trajectory.shape==expected.shape and result['reference_max_abs_error']<=config['max_abs_tolerance']
            else:result['reference_equivalent']=None
        os.chdir(oldcwd);atomic_json(run.path/'metrics/replay.json',result);run.record({'kind':'unidrive_recorded_real_frame_replay'},result)
        run.state['evidence_type']+=['REAL_VLA','REAL_GPU']
        blockers=[]
        if not result['finite']:blockers.append('Recorded-input replay produced a nonfinite trajectory')
        if result['reference_equivalent'] is False:blockers.append('Strict recorded-input replay equivalence failed at the frozen tolerance')
        if result['reference_equivalent'] is None:blockers.append('No recorded reference output; replay equivalence unverified')
        return run.finish('PARTIAL',canonical(result),blockers,acceptance='BLOCKED')
    except BaseException:
        os.chdir(oldcwd);result['error']=traceback.format_exc();atomic_json(run.path/'metrics/replay.json',result);run.log('failure',traceback=result['error']);run.record({'kind':'unidrive_recorded_real_frame_replay'},result,'FAILED',result['error'])
        return run.finish('FAILED',canonical(result),[result['error']],acceptance='BLOCKED')
    finally:
        os.chdir(oldcwd)
        if old_save is None:os.environ.pop('SAVE_PATH',None)
        else:os.environ['SAVE_PATH']=old_save

def capture_unidrive_temporal(head,cpu_copy):
    """Only active temporal bank runtime fields; parameters remain in checkpoint."""
    decoder=head.unified_decoder
    result={'run_step':decoder.run_step,'initialized':decoder.is_init_bank_list,'banks':{}}
    if decoder.is_init_bank_list:
        result['bank_length']=decoder.bank_length;index=decoder.run_step%decoder.bank_length
        for name in ('det_instance_bank_list','map_instance_bank_list','ego_instance_bank_list'):
            if hasattr(decoder,name):
                bank=getattr(decoder,name)[index]
                result['banks'][name]={'index':index,'attributes':{k:cpu_copy(v) for k,v in vars(bank).items() if not k.startswith('_')}}
    return result

def install_unidrive_command_prompt(head,mode):
    """Explicit prompt-only compatibility ablation; suffix command stays one-hot."""
    if mode=='official':return None
    if mode!='onehot-argmax':raise ValueError('Unknown navigation prompt mode')
    import ast,inspect,textwrap
    method=type(head)._build_driving_batch;source=textwrap.dedent(inspect.getsource(method))
    replacement=ast.parse("""if command.ndim != 2 or command.shape != (b, 6):
    raise ValueError('Prompt compatibility requires batch x 6 one-hot command')
if not torch.all((command == 0) | (command == 1)) or not torch.all(command.sum(-1) == 1):
    raise ValueError('Navigation command must be one-hot')
cmd_idx = command.argmax(dim=-1).view(-1).long()
""").body
    class Replace(ast.NodeTransformer):
        count=0
        def visit_Assign(self,node):
            if ast.unparse(node)=='cmd_idx = command.view(-1).long()':
                self.count+=1;return replacement
            return self.generic_visit(node)
    transform=Replace();tree=transform.visit(ast.parse(source));ast.fix_missing_locations(tree)
    if transform.count!=1:raise ValueError('Pinned official command decoding changed')
    transformed=ast.unparse(tree);namespace=dict(method.__globals__);namespace.setdefault('torch',__import__('torch'))
    exec(compile(tree,'<framelease_explicit_prompt_argmax>','exec'),namespace)
    head._build_driving_batch=types.MethodType(namespace['_build_driving_batch'],head)
    return transformed

def restore_unidrive_temporal(head,snapshot,move):
    decoder=head.unified_decoder;decoder.is_init_bank_list=False;decoder.run_step=0;decoder._stage1_cache={}
    if snapshot and snapshot['initialized']:
        decoder.init_instance_bank_list()
        if decoder.bank_length!=snapshot['bank_length']:raise ValueError('Temporal bank count mismatch')
        for name,item in snapshot['banks'].items():
            bank=getattr(decoder,name)[item['index']]
            for k,v in item['attributes'].items():setattr(bank,k,move(v,'cuda'))
        decoder.run_step=snapshot['run_step']

def build_unidrive_flow_prepare(head):
    """Extract the pinned official prefix verbatim; stop before its Euler loop."""
    import ast,inspect,textwrap
    method=inspect.unwrap(type(head).forward_test);source=textwrap.dedent(inspect.getsource(method));tree=ast.parse(source)
    fn=tree.body[0];loops=[i for i,n in enumerate(fn.body) if isinstance(n,ast.While)]
    if len(loops)!=1:raise ValueError('Expected one official flow loop')
    index=loops[0]
    if ast.unparse(fn.body[index].test)!='time_tensor >= -dt_val / 2':raise ValueError('Official flow stopping rule changed')
    fn.name='prepare_flow_state';fn.decorator_list=[]
    state="""return dict(schema=1, batch=batch, cached_pad_masks=cached_pad_masks,
        past_key_values=past_key_values, x_t=x_t, time_tensor=time_tensor,
        dt_val=dt_val, dtype=dtype, max_perception_pos=max_perception_pos,
        ego_status_pred=ego_status_pred, det=det_result, map=map_result,
        completed_steps=0, num_steps=num_steps, prefix_len=prefix_len,
        perception_len=perception_len, perception_lengths=perception_lengths)"""
    fn.body=fn.body[:index]+ast.parse(state).body;ast.fix_missing_locations(tree)
    namespace=dict(method.__globals__);exec(compile(tree,'<framelease_pinned_unidrive_flow_prefix>','exec'),namespace)
    return types.MethodType(namespace['prepare_flow_state'],head),source,ast.unparse(tree)

def unidrive_flow_advance(head,state):
    """One original Euler quantum and its TRAINING-form clean trajectory estimate.

    The estimate is a complete trajectory prediction, not the noisy flow latent.
    Its road/control validity remains a separate empirical requirement.
    """
    import torch
    if state.get('schema')!=1:raise ValueError('Unknown flow state schema')
    if state['completed_steps']>=state['num_steps']:raise ValueError('Flow schedule already complete; cannot extend past t=0')
    x=state['x_t'];t=state['time_tensor'];batch=x.shape[0]
    v=head._denoise_step(state['batch'],state['cached_pad_masks'],state['past_key_values'],x.to(state['dtype']),t.expand(batch).to(state['dtype']),state['max_perception_pos'],ego_status_pred=state['ego_status_pred'])
    clean=x-t*v
    candidate=torch.cumsum(head.denorm_delta(clean),dim=1)
    state['x_t']=x+state['dt_val']*v;state['time_tensor']=t+state['dt_val'];state['completed_steps']+=1
    return candidate

def build_unidrive_flow_reference(head):
    """Use the original loop/decoder verbatim with an identical prepared state."""
    import ast,inspect,textwrap
    method=inspect.unwrap(type(head).forward_test);tree=ast.parse(textwrap.dedent(inspect.getsource(method)))
    original=tree.body[0];loops=[i for i,n in enumerate(original.body) if isinstance(n,ast.While)]
    if len(loops)!=1 or ast.unparse(original.body[loops[0]].test)!='time_tensor >= -dt_val / 2':
        raise ValueError('Pinned official flow loop changed')
    fn=ast.parse('def reference_flow_tail(self, state):\n    pass').body[0]
    names=('batch','cached_pad_masks','past_key_values','x_t','time_tensor','dt_val','dtype','max_perception_pos','ego_status_pred')
    prefix='\n'.join(f'{name} = state[{name!r}]' for name in names)
    prefix+="\nbsz = x_t.shape[0]\ndevice = x_t.device\ndet_result = state['det']\nmap_result = state['map']"
    fn.body=ast.parse(prefix).body+original.body[loops[0]:]
    tree.body=[fn];ast.fix_missing_locations(tree)
    namespace=dict(method.__globals__);exec(compile(tree,'<framelease_official_tail_reference>','exec'),namespace)
    return types.MethodType(namespace['reference_flow_tail'],head),ast.unparse(tree)

def tensor_tree_differences(a,b,path='root'):
    """Compare observed tensor boundaries without conflating shapes or dtypes."""
    import torch
    if isinstance(a,torch.Tensor) and isinstance(b,torch.Tensor):
        row={'path':path,'shape_a':list(a.shape),'shape_b':list(b.shape),'dtype_a':str(a.dtype),'dtype_b':str(b.dtype)}
        if a.shape!=b.shape:row.update(equal=False,max_abs_error=None)
        else:row.update(equal=bool(torch.equal(a,b)),max_abs_error=float((a.double()-b.double()).abs().max()) if a.numel() else 0.)
        return [row]
    if isinstance(a,dict) and isinstance(b,dict):
        rows=[]
        for key in sorted(set(a)|set(b)):
            if key not in a or key not in b:rows.append({'path':path+'.'+str(key),'equal':False,'reason':'missing key'})
            else:rows.extend(tensor_tree_differences(a[key],b[key],path+'.'+str(key)))
        return rows
    if isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
        if len(a)!=len(b):return [{'path':path,'equal':False,'reason':'length mismatch'}]
        return [r for i,(x,y) in enumerate(zip(a,b)) for r in tensor_tree_differences(x,y,path+f'[{i}]')]
    return []

def run_unidrive_flow_probe(args):
    """Actual recorded-input capability diagnostic, never a closed-loop gate."""
    if args.unidrive_input is None:raise ValueError('--unidrive-input required')
    if dry_plan(args,[{'operation':'original flow prefix + trained clean readout + pause/resume','input':str(args.unidrive_input),'closed_loop':False}]):return 0
    if Path(sys.prefix).resolve()!=UNIDRIVE_ENV.resolve():raise RuntimeError('Use isolated UniDrive Conda')
    path=args.unidrive_input.resolve();checkpoint=Path(os.environ['CHECKPOINT']);oldcwd=Path.cwd();old_save=os.environ.get('SAVE_PATH')
    interleave_path=args.unidrive_interleave_input.resolve() if args.unidrive_interleave_input else path
    config={'mode':args.mode,'backend':'UniDriveVLA','source':unidrive_source_audit(),'input':str(path),'input_sha256':file_hash(path),'checkpoint_sha256':file_hash(checkpoint),'scope':'ONE_REAL_OBSERVATION_FLOW_CAPABILITY_NOT_DRIVING_QUALITY','seed':args.seed,'grid_steps':10,'strict_tolerance_m':1e-5,'clean_readout':'cumsum(denorm_delta(x_t - t * v_t)); same form as training loss','interruption':'saved state, separate full compute on same recorded observation, restore; not a distinct fresh observation','precision':'recorded explicit bf16-autocast only'}
    config.update(interleave_input=str(interleave_path),interleave_input_sha256=file_hash(interleave_path),prompt_command_mode=args.unidrive_prompt_command,timing_scope='Synchronized CUDA event elapsed intervals and host wall time; intervals may include host stalls/transfers and are not summed GPU kernel busy time',equivalence_controls='independent official repeat plus original verbatim tail on the identical prepared state')
    config.update(numerical_boundaries=args.unidrive_numerical_audit,gpu_resident_switch=args.unidrive_resident_switch)
    if interleave_path!=path:config['interruption']='saved old state, full compute on a separately captured real observation with its temporal context, restore old state'
    run=StageRun('stage02_real_vla',args,config,['RECORDED_INPUT_REPLAY'],[UNIDRIVE_REPO/UNIDRIVE_HEAD,UNIDRIVE_REPO/UNIDRIVE_AGENT,UNIDRIVE_REPO/UNIDRIVE_CONFIG]);run.path=run.path.resolve();result={'gate_promoted':False};events=[]
    try:
        import torch,numpy as np,random,copy,inspect
        random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed)
        record=torch.load(path,map_location='cpu',weights_only=False)
        if record['precision']!='bf16-autocast':raise ValueError('This diagnostic requires the declared BF16 recording')
        def move(value,device):
            if isinstance(value,torch.Tensor):return value.detach().to(device).clone()
            if dataclasses.is_dataclass(value):return dataclasses.replace(value,**{f.name:move(getattr(value,f.name),device) for f in dataclasses.fields(value)})
            if isinstance(value,dict):return {k:move(v,device) for k,v in value.items()}
            if isinstance(value,list):return [move(v,device) for v in value]
            if isinstance(value,tuple):return tuple(move(v,device) for v in value)
            if type(value).__module__.startswith('transformers.cache_utils'):
                moved=copy.copy(value)
                for k,v in vars(value).items():setattr(moved,k,move(v,device))
                return moved
            return copy.deepcopy(value)
        def measured(label,fn):
            torch.cuda.synchronize();a=torch.cuda.Event(enable_timing=True);b=torch.cuda.Event(enable_timing=True);start=time.perf_counter_ns();a.record();out=fn();b.record();torch.cuda.synchronize()
            scope='HOST_IO_OR_TRANSFER_INTERVAL' if any(key in label for key in ('disk_','_to_cpu','_to_gpu')) else 'GPU_FORWARD_ELAPSED_INTERVAL'
            row={'event':label,'cuda_ms':a.elapsed_time(b),'wall_ms':(time.perf_counter_ns()-start)/1e6,'allocated_bytes':torch.cuda.memory_allocated(),'timing_scope':scope,'gpu_busy_time_measured':False};events.append(row);run.log('measurement',measurement=row);return out
        os.environ['SAVE_PATH']=str((run.path/'raw').resolve());os.chdir(UNIDRIVE_REPO/'Bench2Drive')
        from team_code.unidrivevla_b2d_agent import UniDriveVLAB2DAgent
        with writer_lock(ROOT/'results/shared_gpu_resource'),torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
            agent=UniDriveVLAB2DAgent.__new__(UniDriveVLAB2DAgent);agent.setup(str(UNIDRIVE_REPO/UNIDRIVE_CONFIG)+'+'+str(checkpoint));head=agent.model.planning_head
            prompt_source=install_unidrive_command_prompt(head,args.unidrive_prompt_command)
            if prompt_source:(run.path/'raw/prompt_command_compatibility.py.txt').write_text(prompt_source)
            if head.num_sample_steps!=10:raise ValueError('Pinned 10-step protocol/model mismatch')
            prepare,official_source,extracted_source=build_unidrive_flow_prepare(head)
            reference_tail,reference_tail_source=build_unidrive_flow_reference(head)
            # Resolve paths before restoring the source's native working directory.
            base=Path(run.path) if Path(run.path).is_absolute() else oldcwd/run.path
            (base/'raw/official_forward_test.py.txt').write_text(official_source);(base/'raw/extracted_prefix.py.txt').write_text(extracted_source)
            (base/'raw/official_reference_tail.py.txt').write_text(reference_tail_source)
            inputs=move(record['args'],'cuda');kwargs=move(record['kwargs'],'cuda')
            def reset():
                restore_unidrive_temporal(head,record.get('temporal_context'),move)
                torch.set_rng_state(record['torch_rng_state']);torch.cuda.set_rng_state_all(record['cuda_rng_state'])
            boundary_calls=[];boundary_current={};boundary_originals={}
            if args.unidrive_numerical_audit:
                decoder=head.unified_decoder
                import importlib
                native_blocks=importlib.import_module('projects.mmdet3d_plugin.models.blocks')
                native_daf=native_blocks.DAF;daf_record={}
                def record_daf(*a,**kw):
                    if not daf_record:daf_record['args']=move(a,'cpu')
                    return native_daf(*a,**kw)
                native_blocks.DAF=record_daf
                for name in ('forward_stage1','forward_stage2'):
                    native=getattr(decoder,name);boundary_originals[name]=native
                    def capture(*a,_name=name,_native=native,**kw):
                        # Record only numerical feature inputs, not evaluator GT.
                        boundary_current[_name+'_feature_input']=move(a[0],'cpu')
                        out=_native(*a,**kw);boundary_current[_name+'_output']=move(out,'cpu');return out
                    setattr(decoder,name,capture)
            reset();official=measured('official_full_forward',lambda:agent.model(*inputs,**kwargs))[0]['img_bbox']['final_planning'].cpu()
            if args.unidrive_numerical_audit:boundary_calls.append(boundary_current);boundary_current={}
            reset();official_repeat=measured('official_full_forward_repeat',lambda:agent.model(*inputs,**kwargs))[0]['img_bbox']['final_planning'].cpu()
            if args.unidrive_numerical_audit:
                boundary_calls.append(boundary_current)
                native_blocks.DAF=native_daf
                for name,native in boundary_originals.items():setattr(decoder,name,native)
                differences=tensor_tree_differences(*boundary_calls)
                torch.save(boundary_calls,base/'raw/independent_boundary_outputs.pt')
                atomic_json(base/'metrics/independent_boundary_differences.json',differences)
                result['numerical_boundary_summary']={name:{'tensor_count':len(selected:=[r for r in differences if r['path'].startswith('root.'+name)]),'different_tensors':sum(not r['equal'] for r in selected),'max_abs_error':max((r.get('max_abs_error') or 0. for r in selected),default=None)} for name in boundary_calls[0]}
                if daf_record:
                    daf_gpu=move(daf_record['args'],'cuda')
                    daf_outputs=[measured('isolated_real_input_DAF_repeat_'+str(i),lambda:native_daf(*daf_gpu)).cpu() for i in range(10)]
                    daf_errors=[float((x-daf_outputs[0]).abs().max()) for x in daf_outputs[1:]]
                    torch.save({'args':daf_record['args'],'outputs':daf_outputs},base/'raw/real_input_operator_repeat.pt')
                    result['isolated_real_input_operator']={'repeats':10,'max_abs_error_vs_first':daf_errors,'any_nonidentical':any(e>0 for e in daf_errors),'scope':'Original DAF on identical actual recorded numerical inputs; does not quantify contribution to driving failure'}
                    del daf_gpu,daf_outputs,daf_record
                del boundary_calls,boundary_current
            # Capture detector-to-head arguments while retaining native dispatch.
            original=head.forward_test;captured={}
            class PrefixCaptured(Exception):pass
            def only_prepare(*a,**kw):
                state=prepare(*a,**kw);captured['state']=state
                raise PrefixCaptured()
            def native_prepare():
                try:agent.model(*inputs,**kwargs)
                except PrefixCaptured:return captured['state']
                raise RuntimeError('Native detector did not invoke the captured head')
            reset();head.forward_test=only_prepare
            try:measured('official_prefix_and_perception',native_prepare)
            finally:head.forward_test=original
            state=captured['state'];initial=measured('prefix_state_gpu_to_cpu',lambda:move(state,'cpu'));torch.save(initial,base/'raw/initial_flow_state.pt')
            torch.save(move({'det':state['det'],'map':state['map']},'cpu'),base/'raw/perception_outputs.pt')
            continuous=[]
            for i in range(10):continuous.append(measured('continuous_quantum_'+str(i+1),lambda:unidrive_flow_advance(head,state)).float().cpu())
            continuous_final=torch.cumsum(head.denorm_delta(state['x_t']),dim=1).float().cpu()
            reference_state=move(initial,'cuda')
            reference_final=measured('official_tail_same_prepared_state',lambda:reference_tail(reference_state))['traj'].float().cpu()
            del reference_state
            # Reuse the identical prepared prefix/noise, rather than comparing
            # nondeterministic fresh perception reductions to a resumed state.
            state=measured('prefix_state_cpu_to_gpu',lambda:move(initial,'cuda'));resumed=[]
            for i in range(3):resumed.append(measured('before_pause_quantum_'+str(i+1),lambda:unidrive_flow_advance(head,state)).float().cpu())
            snapshot={'state':measured('pause_state_gpu_to_cpu',lambda:move(state,'cpu')),'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all(),'input_sha256':config['input_sha256']}
            measured('pause_state_disk_write',lambda:torch.save(snapshot,base/'raw/paused_after_3.pt'));del state
            other=torch.load(interleave_path,map_location='cpu',weights_only=False)
            if other['precision']!=record['precision']:raise ValueError('Interleaved recording precision differs')
            restore_unidrive_temporal(head,other.get('temporal_context'),move);torch.set_rng_state(other['torch_rng_state']);torch.cuda.set_rng_state_all(other['cuda_rng_state'])
            other_args=move(other['args'],'cuda');other_kwargs=move(other['kwargs'],'cuda')
            measured('interleaved_distinct_input_full_forward' if interleave_path!=path else 'interleaved_same_input_full_forward',lambda:agent.model(*other_args,**other_kwargs))
            saved=measured('pause_state_disk_read',lambda:torch.load(base/'raw/paused_after_3.pt',map_location='cpu',weights_only=False));state=measured('resume_state_cpu_to_gpu',lambda:move(saved['state'],'cuda'));torch.set_rng_state(saved['torch_rng']);torch.cuda.set_rng_state_all(saved['cuda_rng'])
            for i in range(3,10):resumed.append(measured('resumed_quantum_'+str(i+1),lambda:unidrive_flow_advance(head,state)).float().cpu())
            resumed_final=torch.cumsum(head.denorm_delta(state['x_t']),dim=1).float().cpu()
            if args.unidrive_resident_switch:
                if config['input_sha256']==config['interleave_input_sha256']:raise ValueError('Resident switch requires distinct recorded observations')
                resident_a=measured('resident_A_initial_state_cpu_to_gpu',lambda:move(initial,'cuda'))
                torch.cuda.reset_peak_memory_stats();resident_candidates=[]
                for i in range(3):resident_candidates.append(measured('resident_A_quantum_'+str(i+1),lambda:unidrive_flow_advance(head,resident_a)))
                a_rng=(torch.get_rng_state(),torch.cuda.get_rng_state_all())
                def activate_b():
                    restore_unidrive_temporal(head,other.get('temporal_context'),move)
                    torch.set_rng_state(other['torch_rng_state']);torch.cuda.set_rng_state_all(other['cuda_rng_state'])
                measured('resident_B_temporal_context_cpu_to_gpu',activate_b)
                def other_prepare():
                    try:agent.model(*other_args,**other_kwargs)
                    except PrefixCaptured:return captured['state']
                    raise RuntimeError('Other real observation did not invoke head')
                head.forward_test=only_prepare
                try:resident_b=measured('resident_B_real_prefix',other_prepare)
                finally:head.forward_test=original
                both_resident_bytes=torch.cuda.memory_allocated()
                for i in range(10):measured('resident_B_quantum_'+str(i+1),lambda:unidrive_flow_advance(head,resident_b))
                def activate_a():
                    torch.set_rng_state(a_rng[0]);torch.cuda.set_rng_state_all(a_rng[1])
                    return resident_a
                measured('resident_A_reselect_and_rng',activate_a)
                for i in range(3,10):resident_candidates.append(measured('resident_A_resumed_quantum_'+str(i+1),lambda:unidrive_flow_advance(head,resident_a)))
                resident_final=torch.cumsum(head.denorm_delta(resident_a['x_t']),dim=1).float().cpu()
                resident_candidates=[x.float().cpu() for x in resident_candidates]
                result['resident_switch']={'distinct_observations':True,'all_candidates_max_abs_error_m':max(float((a-b).abs().max()) for a,b in zip(continuous,resident_candidates)),'final_max_abs_error_m':float((continuous_final-resident_final).abs().max()),'both_contexts_allocated_bytes':both_resident_bytes,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'old_flow_state_cpu_or_disk_roundtrip_during_interruption':False,'new_observation_temporal_context':'replayed CPU recording moved to GPU; measured separately','scope':'two recorded observations on one model; no live tick owner, leases or scheduler'}
                torch.save({'candidates':resident_candidates,'final':resident_final},base/'raw/resident_switch_outputs.pt')
            candidates=[]
            for i,(a,b) in enumerate(zip(continuous,resumed)):
                traj=a[0];deltas=torch.diff(torch.cat([torch.zeros(1,2),traj]),dim=0)
                candidates.append({'depth':i+1,'trajectory':traj.tolist(),'finite':bool(torch.isfinite(traj).all()),'resume_max_abs_error_m':float((a-b).abs().max()),'distance_to_full_max_abs_m':float((a-continuous_final).abs().max()),'segment_speeds_mps':(torch.linalg.vector_norm(deltas,dim=-1)/.5).tolist(),'validity':'UNVALIDATED_ROAD_AND_CONTROL','readout':'TRAINING_CLEAN_ESTIMATE_NOT_NOISY_LATENT'})
            torch.save({'official':official,'official_repeat':official_repeat,'official_tail_same_state':reference_final,'continuous_final':continuous_final,'resumed_final':resumed_final,'continuous_candidates':continuous,'resumed_candidates':resumed},base/'raw/flow_outputs.pt')
            def describe(v):
                if isinstance(v,torch.Tensor):return {'type':'tensor','shape':list(v.shape),'dtype':str(v.dtype),'finite':bool(torch.isfinite(v).all()) if v.is_floating_point() else True}
                if isinstance(v,dict):return {k:describe(x) for k,x in v.items()}
                if isinstance(v,(list,tuple)):return [describe(x) for x in v]
                return {'type':type(v).__name__}
            result.update(forward_executed=True,official_vs_extracted_full_max_abs_m=float((official-continuous_final[0]).abs().max()),same_prefix_resume_max_abs_m=float((resumed_final-continuous_final).abs().max()),max_candidate_resume_error_m=max(x['resume_max_abs_error_m'] for x in candidates),candidates=candidates,perception_schema=describe({'det':initial['det'],'map':initial['map']}),peak_allocated_bytes=torch.cuda.max_memory_allocated(),state_snapshot_bytes=(base/'raw/paused_after_3.pt').stat().st_size,events=events,source_form_matches_training_loss=True,road_validity='UNVALIDATED',refinement_quality_benefit='UNTESTED',distinct_observation_interleaving=config['input_sha256']!=config['interleave_input_sha256'])
            result['strict_same_prefix_resume_passed']=result['same_prefix_resume_max_abs_m']<=1e-5 and result['max_candidate_resume_error_m']<=1e-5
            result['strict_official_equivalence_passed']=result['official_vs_extracted_full_max_abs_m']<=1e-5
            result.update(official_independent_repeat_max_abs_m=float((official-official_repeat).abs().max()),same_state_official_tail_max_abs_m=float((reference_final-continuous_final).abs().max()),timing_scope=config['timing_scope'])
            result['strict_same_state_official_tail_passed']=result['same_state_official_tail_max_abs_m']<=1e-5
        os.chdir(oldcwd);atomic_json(run.path/'metrics/flow_probe.json',result);write_csv(run.path/'metrics/quantum_times.csv',events);run.record({'kind':'actual_flow_clean_readout_and_resume_diagnostic'},result);run.state['evidence_type']+=['REAL_VLA','REAL_GPU']
        blockers=['Recorded development observations only; road/control validity and quality benefit unvalidated']
        if not result['distinct_observation_interleaving']:blockers.append('Distinct-observation interleaving not yet executed')
        if not result['strict_same_prefix_resume_passed']:blockers.append('Same-prefix resume numerical check failed')
        if not result['strict_official_equivalence_passed']:blockers.append('Independent official/extracted full comparison fails frozen tolerance')
        if not result['strict_same_state_official_tail_passed']:blockers.append('Original tail vs quantum implementation on identical state fails frozen tolerance')
        if args.unidrive_resident_switch and max(result['resident_switch']['final_max_abs_error_m'],result['resident_switch']['all_candidates_max_abs_error_m'])>1e-5:blockers.append('GPU resident continuation differs at frozen tolerance')
        return run.finish('PARTIAL',canonical(result),blockers,acceptance='BLOCKED')
    except BaseException:
        os.chdir(oldcwd);result['error']=traceback.format_exc();atomic_json(run.path/'metrics/flow_probe.json',result);run.record({'kind':'actual_flow_clean_readout_and_resume_diagnostic'},result,'FAILED',result['error']);return run.finish('FAILED',result['error'],[result['error']],acceptance='BLOCKED')
    finally:
        os.chdir(oldcwd)
        if old_save is None:os.environ.pop('SAVE_PATH',None)
        else:os.environ['SAVE_PATH']=old_save

def unidrive_condition_state(initial,condition):
    """Only change explicit suffix conditions; preserve cached positions and noise."""
    import torch
    allowed=('baseline','baseline_repeat','mask_perception_cache','zero_ego_status','mask_and_zero')
    if condition not in allowed:raise ValueError('Unknown condition intervention')
    state=dict(initial)
    for key in ('x_t','time_tensor','cached_pad_masks','ego_status_pred'):
        state[key]=initial[key].clone()
    n,p=state['prefix_len'],state['perception_len']
    if n<=0 or p<=0 or state['cached_pad_masks'].shape[1]!=n+p:
        raise ValueError('Invalid recorded prefix/perception boundary')
    if state['cached_pad_masks'].dtype!=torch.bool:raise ValueError('Expected native boolean attention mask')
    if condition in ('mask_perception_cache','mask_and_zero'):state['cached_pad_masks'][:,n:]=False
    if condition in ('zero_ego_status','mask_and_zero'):state['ego_status_pred'].zero_()
    return state

def run_unidrive_condition_probe(args):
    """Fixed-state OOD condition intervention; no GT, learning, or safety claim."""
    paths=[p.resolve() for p in (args.unidrive_probe_inputs or [])]
    if not paths or len(set(paths))!=len(paths):raise ValueError('Require distinct --unidrive-probe-inputs')
    if dry_plan(args,[{'operation':'same-state condition intervention','inputs':list(map(str,paths))}]):return 0
    if Path(sys.prefix).resolve()!=UNIDRIVE_ENV.resolve():raise RuntimeError('Use isolated UniDrive Conda')
    manifests={p.parents[2]/'manifest.json' for p in paths}
    for m in manifests:verified_manifest(m)
    # Native setup changes cwd. Every ledger/cache destination must be fixed
    # before then, including per-condition records written during inference.
    args.output_dir=args.output_dir.resolve()
    checkpoint=Path(os.environ['CHECKPOINT']);oldcwd=Path.cwd();old_save=os.environ.get('SAVE_PATH')
    conditions=['baseline','baseline_repeat','mask_perception_cache','zero_ego_status','mask_and_zero']
    config={'mode':args.mode,'backend':'UniDriveVLA','source':unidrive_source_audit(),'inputs':{str(p):file_hash(p) for p in paths},'source_manifests':{str(p):file_hash(p) for p in manifests},'checkpoint_sha256':file_hash(checkpoint),'conditions':conditions,'same_state_tolerance_m':1e-5,'num_steps':10,'precision':'bf16-autocast','scope':'DEVELOPMENT_OOD_CONDITION_INTERVENTION_NOT_DRIVING_FIX','gt_used':False,'timing':'CUDA event elapsed, synchronized wall; not kernel busy time or live latency'}
    resolved_agent=Path(__import__('importlib.util',fromlist=['find_spec']).find_spec('team_code.unidrivevla_b2d_agent').origin)
    dependencies=[UNIDRIVE_REPO/p for p in config['source']['sources']]+[ROOT/'linux/env.sh',resolved_agent,resolved_agent.with_name('pid_controller.py')]
    run=StageRun('stage02_real_vla',args,config,['REAL_MODEL','REAL_GPU','RECORDED_INPUT_REPLAY'],dependencies);run.path=run.path.resolve();rows=[];events=[]
    try:
        import torch,numpy as np,random,copy,inspect
        random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed)
        def move(value,device):
            if isinstance(value,torch.Tensor):return value.detach().to(device).clone()
            if dataclasses.is_dataclass(value):return dataclasses.replace(value,**{f.name:move(getattr(value,f.name),device) for f in dataclasses.fields(value)})
            if isinstance(value,dict):return {k:move(v,device) for k,v in value.items()}
            if isinstance(value,list):return [move(v,device) for v in value]
            if isinstance(value,tuple):return tuple(move(v,device) for v in value)
            if type(value).__module__.startswith('transformers.cache_utils'):
                out=copy.copy(value)
                for k,v in vars(value).items():setattr(out,k,move(v,device))
                return out
            return copy.deepcopy(value)
        def measured(label,fn):
            torch.cuda.synchronize();a=torch.cuda.Event(enable_timing=True);b=torch.cuda.Event(enable_timing=True);start=time.perf_counter_ns();a.record();out=fn();b.record();torch.cuda.synchronize()
            event={'event':label,'cuda_elapsed_ms':a.elapsed_time(b),'wall_ms':(time.perf_counter_ns()-start)/1e6,'allocated_bytes':torch.cuda.memory_allocated()};events.append(event);run.log('measurement',measurement=event);return out
        os.environ['SAVE_PATH']=str(run.path/'raw');os.chdir(UNIDRIVE_REPO/'Bench2Drive')
        from team_code.unidrivevla_b2d_agent import UniDriveVLAB2DAgent
        with writer_lock(ROOT/'results/shared_gpu_resource'),torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
            agent=UniDriveVLAB2DAgent.__new__(UniDriveVLAB2DAgent);agent.setup(str(UNIDRIVE_REPO/UNIDRIVE_CONFIG)+'+'+str(checkpoint));head=agent.model.planning_head
            if head.num_sample_steps!=10:raise ValueError('Official schedule mismatch')
            prepare,official_source,extracted=build_unidrive_flow_prepare(head);tail,tail_source=build_unidrive_flow_reference(head)
            for name,value in [('official_forward',official_source),('extracted_prefix',extracted),('original_tail',tail_source),('denoise',inspect.getsource(type(head)._denoise_step))]:
                (run.path/'raw'/(name+'.py.txt')).write_text(value)
            checkpoint_record=torch.load(checkpoint,map_location='cpu',weights_only=False,mmap=True)
            meta=checkpoint_record.get('meta') if isinstance(checkpoint_record,dict) else None
            atomic_json(run.path/'raw/checkpoint_metadata.json',{'top_level_keys':list(checkpoint_record) if isinstance(checkpoint_record,dict) else None,'meta_repr':repr(meta),'scope':'Checkpoint metadata only; does not independently prove training protocol'})
            training_config=checkpoint_record.get('config')
            (run.path/'raw/checkpoint_training_config.txt').write_text(training_config if isinstance(training_config,str) else repr(training_config))
            atomic_json(run.path/'raw/checkpoint_training_metadata.json',{k:checkpoint_record.get(k) for k in ('seed','exp_name','epoch','iter','global_steps','global_samples','ds_version','mmdet_version')})
            del checkpoint_record
            atomic_json(run.path/'metrics/loaded_head_objectives.json',{k:getattr(head,k,None) for k in ('collision_loss_weight','map_bound_loss_weight','map_dir_loss_weight','feature_source','num_sample_steps')})
            for path in paths:
                record=torch.load(path,map_location='cpu',weights_only=False);step=record['native_step']
                if record['precision']!='bf16-autocast':raise ValueError('Input precision mismatch')
                inputs=move(record['args'],'cuda');kwargs=move(record['kwargs'],'cuda')
                restore_unidrive_temporal(head,record.get('temporal_context'),move);torch.set_rng_state(record['torch_rng_state']);torch.cuda.set_rng_state_all(record['cuda_rng_state'])
                captured={};original=head.forward_test
                class Captured(Exception):pass
                def only_prepare(*a,**kw):captured['state']=prepare(*a,**kw);raise Captured()
                def native_prepare():
                    try:agent.model(*inputs,**kwargs)
                    except Captured:return captured['state']
                    raise RuntimeError('Native detector did not invoke head')
                head.forward_test=only_prepare
                try:initial=measured(f'step{step}_prefix',native_prepare)
                finally:head.forward_test=original
                torch.save(move(initial,'cpu'),run.path/'raw'/f'initial_state_{step:04d}.pt')
                rng_cpu=torch.get_rng_state();rng_gpu=torch.cuda.get_rng_state_all();outputs={};baseline=None
                for condition in conditions:
                    torch.set_rng_state(rng_cpu);torch.cuda.set_rng_state_all(rng_gpu)
                    state=unidrive_condition_state(initial,condition)
                    original_out=measured(f'step{step}_{condition}_official_tail',lambda:tail(state))['traj'].float().cpu()
                    torch.set_rng_state(rng_cpu);torch.cuda.set_rng_state_all(rng_gpu)
                    state=unidrive_condition_state(initial,condition);candidates=[]
                    for depth in range(10):candidates.append(measured(f'step{step}_{condition}_quantum{depth+1}',lambda:unidrive_flow_advance(head,state)).float().cpu())
                    final=torch.cumsum(head.denorm_delta(state['x_t']),dim=1).float().cpu()
                    if baseline is None:baseline=original_out
                    row={'step':step,'condition':condition,'prefix_tokens':initial['prefix_len'],'perception_tokens':initial['perception_len'],'perception_lengths':initial['perception_lengths'],'original_allowed_cache_tokens':int(initial['cached_pad_masks'].sum()),'condition_allowed_cache_tokens':int(state['cached_pad_masks'].sum()),'ego_status_l2':float(state['ego_status_pred'].float().norm()),'trajectory':original_out.tolist(),'max_abs_difference_from_baseline_m':float((original_out-baseline).abs().max()),'mean_waypoint_distance_from_baseline_m':float((original_out-baseline).norm(dim=-1).mean()),'official_tail_vs_quantum_max_abs_m':float((original_out-final).abs().max()),'finite':bool(torch.isfinite(original_out).all()),'gt_used':False,'gate_promoted':False}
                    if not row['finite'] or row['official_tail_vs_quantum_max_abs_m']>1e-5:raise AssertionError('Invalid/mismatched same-state official tail')
                    if condition=='baseline_repeat' and row['max_abs_difference_from_baseline_m']>1e-5:raise AssertionError('Uncontrolled same-state repeat difference')
                    outputs[condition]={'original_final':original_out,'candidates':candidates,'quantum_final':final};rows.append(row);run.record({'kind':'condition_intervention','step':step,'condition':condition},row)
                torch.save(outputs,run.path/'raw'/f'condition_outputs_{step:04d}.pt')
                del record,inputs,kwargs,initial,state,captured,outputs;torch.cuda.empty_cache()
        os.chdir(oldcwd);write_csv(run.path/'metrics/timings.csv',events);atomic_json(run.path/'metrics/condition_probe.json',{'rows':rows,'independent_episodes':1,'observations':len(paths),'scope':config['scope'],'not_a_safety_improvement':True,'gate_promoted':False})
        return run.finish('PARTIAL','Actual fixed-state condition interventions executed. '+canonical(rows),['OOD sensitivity is not safe planning, refinement benefit or independent calibration'],acceptance='BLOCKED')
    except BaseException:
        error=traceback.format_exc();atomic_json(run.path/'metrics/partial.json',{'rows':rows,'events':events,'error':error});run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')
    finally:
        os.chdir(oldcwd)
        if old_save is None:os.environ.pop('SAVE_PATH',None)
        else:os.environ['SAVE_PATH']=old_save

def run_unidrive_gradient_audit(args):
    """Official loss autograd audit on CUDA; no model training or forward claim."""
    if dry_plan(args,[{'operation':'official geometric-loss gradient audit','training':False,'model_forward':False}]):return 0
    import ast,copy,importlib.util,types,shutil
    package=UNIDRIVE_REPO/'Bench2Drive/projects/mmdet3d_plugin'
    head_path=package/'models/vla/qwenvl3_vla_planning_head.py'
    loss_paths=[package/'losses'/name for name in ('collision_loss.py','plan_map_loss.py','flow_planning_loss.py')]
    protocol=ROOT/'audits/dac2027_state_estimation_20261106/N3_GRADIENT_PROTOCOL.md'
    source=ROOT/'outputs/linux_condition_probe_20261106/runs/20261106T030843_35a260a0'
    converter=UNIDRIVE_REPO/'Bench2Drive/tools/data_converter/bench2drive_converter.py'
    training_config=ROOT/'audits/dac2027_planning_tracking_20261106/checkpoint_training_config.txt'
    verified_manifest(source/'manifest.json')
    inputs=[source/'raw'/f'condition_outputs_{step:04d}.pt' for step in (180,200,210)]
    config={'mode':args.mode,'source_manifest_sha256':file_hash(source/'manifest.json'),'trajectory_inputs':{str(p):file_hash(p) for p in inputs},'protocol_sha256':file_hash(protocol),'device':'cuda','fixture_scope':'Real saved trajectory values with explicitly constructed geometric fixtures; gradient engineering only, not actual GT or model inference','gate_promoted':False}
    run=StageRun('stage02_real_vla',args,config,['OFFICIAL_SOURCE_AUDIT','CUDA_AUTOGRAD_ENGINEERING_DIAGNOSTIC'],[head_path,*loss_paths,converter,training_config,protocol])
    try:
        import torch
        if not torch.cuda.is_available():raise DependencyBlocked('Real CUDA required; no CPU or simulated replacement')
        modules=[]
        for path in loss_paths:
            spec=importlib.util.spec_from_file_location('_framelease_gradient_'+path.stem,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);modules.append(module)
        tree=ast.parse(head_path.read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and any(isinstance(f,ast.FunctionDef) and f.name=='norm_delta' for f in n.body))
        methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)};forward=methods['forward_train'];begin=next(i for i,n in enumerate(forward.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_pred_abs' for t in n.targets))
        branch=copy.deepcopy(forward.body[begin:begin+5])
        if len(branch)!=5 or not all(isinstance(n,ast.If) for n in branch[1:]):raise ValueError('Official geometry branch structure changed')
        wrapper=ast.parse('def geometry(self,pred_x_gt,gt_bboxes_3d,gt_map_pts,gt_map_labels,gt_ego_fut_masks):\n stats={}\n return stats, _pred_abs\n').body[0]
        wrapper.body=wrapper.body[:1]+branch+wrapper.body[-1:]
        functions=[copy.deepcopy(methods[name]) for name in ('norm_delta','denorm_delta')]+[wrapper]
        module=ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[]));extracted=ast.unparse(module);(run.path/'raw/extracted_official_geometry.py.txt').write_text(extracted)
        ns={'torch':torch};exec(compile(module,str(head_path),'exec'),ns)
        head=types.SimpleNamespace(collision_loss_fn=modules[0].CollisionLoss().cuda(),map_bound_loss_fn=modules[1].GTMapBoundLoss().cuda(),map_dir_loss_fn=modules[1].GTMapDirectionLoss().cuda(),collision_loss_weight=1.,map_bound_loss_weight=1.,map_dir_loss_weight=1.)
        for name in ('norm_delta','denorm_delta'):setattr(head,name,types.MethodType(ns[name],head))
        flow=modules[2].FlowPlanningLoss(hybrid_loss_weight=.5,detach_window_size=10).cuda();results=[]
        with writer_lock(ROOT/'results/shared_gpu_resource'):
            for path in inputs:
                traj=torch.load(path,map_location='cpu',weights_only=False)['baseline']['original_final'].float().cuda()
                delta=torch.diff(torch.cat([torch.zeros_like(traj[:,:1]),traj],dim=1),dim=1);leaf=head.norm_delta(delta).detach().requires_grad_(True)
                first=traj[0,0].detach();u=torch.linspace(-.3,.3,20,device='cuda')
                boundary=torch.stack([first[0]+.25+u*0,first[1]+u],dim=-1)
                divider=torch.stack([first[0]+u,first[1]+.1+u*.2],dim=-1)
                maps=[torch.stack([boundary,divider])[:,None]];labels=[torch.tensor([2,1],device='cuda')]
                box=torch.tensor([[0.,0.,0.,4.,4.,1.5,0.,0.,0.]],device='cuda');box[0,:2]=first+.25;boxes=[box];mask=torch.ones((1,6),device='cuda')
                original,pred_abs=ns['geometry'](head,leaf,boxes,maps,labels,mask)
                connected_abs=torch.cumsum(head.denorm_delta(leaf),dim=1)
                connected={'loss_collision':head.collision_loss_fn(connected_abs,boxes,mask),'loss_map_bound':head.map_bound_loss_fn(connected_abs,maps,labels,mask),'loss_map_dir':head.map_dir_loss_fn(connected_abs,maps,labels,mask)}
                reference=leaf.detach()+.1;flow_loss=flow(leaf,reference,torch.tensor([.5],device='cuda'),gt_ego_fut_masks=mask,pred_x0=leaf,gt_x0=reference)
                flow_grad=torch.autograd.grad(flow_loss.sum(),leaf,retain_graph=True)[0]
                combined_grad=torch.autograd.grad((flow_loss+sum(original.values())).sum(),leaf,retain_graph=True)[0]
                details={}
                for name in original:
                    g=torch.autograd.grad(connected[name].sum(),leaf,retain_graph=True,allow_unused=True)[0] if connected[name].requires_grad else None
                    details[name]={'official_value':float(original[name].detach()),'official_requires_grad':original[name].requires_grad,'connected_value':float(connected[name].detach()),'connected_gradient_norm':float(g.norm()) if g is not None else None,'connected_gradient':g.detach().cpu().tolist() if g is not None else None}
                    if original[name].requires_grad or not torch.equal(original[name],connected[name]):raise AssertionError('Unexpected official detached geometry behavior')
                torch.cuda.synchronize()
                row={'input':str(path),'input_sha256':file_hash(path),'official_pred_abs_requires_grad':pred_abs.requires_grad,'denormalization_roundtrip_max_abs_m':float((connected_abs.detach()-traj).abs().max()),'flow_gradient_norm':float(flow_grad.norm()),'combined_minus_flow_gradient_max_abs':float((combined_grad-flow_grad).abs().max()),'losses':details,'fixture_not_actual_gt':True,'training_steps':0,'model_forwards':0}
                if row['combined_minus_flow_gradient_max_abs']!=0 or row['flow_gradient_norm']<=0:raise AssertionError('Gradient positive/negative control failed')
                results.append(row)
                torch.save({'saved_real_trajectory':traj.cpu(),'normalized_leaf':leaf.detach().cpu(),'fixture_boxes':box.cpu(),'fixture_maps':maps[0].cpu(),'fixture_labels':labels[0].cpu(),'flow_gradient':flow_grad.cpu(),'combined_gradient':combined_grad.cpu()},run.path/'raw'/(path.stem+'_gradient.pt'))
        for name in ('loss_collision','loss_map_bound','loss_map_dir'):
            if not any((r['losses'][name]['connected_gradient_norm'] or 0)>0 for r in results):raise AssertionError('No active connected positive control: '+name)
        cfg_ast=ast.parse(training_config.read_text());map_classes=next(ast.literal_eval(n.value) for n in cfg_ast.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='map_class_names' for t in n.targets))
        main_block=next(n for n in ast.parse(converter.read_text()).body if isinstance(n,ast.If) and '__name__' in ast.unparse(n.test))
        called=[n.func.id for n in ast.walk(main_block) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        data_root=UNIDRIVE_REPO/'Bench2Drive/data';required=['infos/b2d_infos_train.pkl','infos/b2d_infos_val.pkl','infos/b2d_map_anno.pkl','infos/b2d_map_infos.pkl','splits/bench2drive_base_train_val_split.json','bench2drive/v1','bench2drive/maps']
        result={'cuda_device':torch.cuda.get_device_name(),'rows':results,'source_geometry_range':[branch[0].lineno,branch[-1].end_lineno],'loaded_checkpoint_geometry_weights':read_json(ROOT/'audits/dac2027_planning_tracking_20261106/planning_information_audit.json')['loaded_head_geometry_weights'],'map_label_audit':{'checkpoint_classes':map_classes,'default_boundary_index':head.map_bound_loss_fn.boundary_cls_idx,'actual_class_at_boundary_index':map_classes[head.map_bound_loss_fn.boundary_cls_idx],'default_divider_index':head.map_dir_loss_fn.divider_cls_idx,'actual_class_at_divider_index':map_classes[head.map_dir_loss_fn.divider_cls_idx],'interpretation':'NuScenes defaults do not establish B2D road boundary/centerline semantics; require explicit audited mapping'},'collision_loss_scope':'Static GT box centers and sizes repeated at every future step; yaw and velocity unused; not dynamic swept-body collision','converter_main_calls':called,'converter_generates_training_infos': 'generate_infos' in called,'required_data':[{'path':str(data_root/p),'exists':(data_root/p).exists()} for p in required],'disk_free_bytes':shutil.disk_usage(ROOT).free,'training_steps':0,'full_model_forwards':0,'gate_promoted':False,'limits':['Real CUDA loss graph only; artificial geometry fixtures are not driving/safety evidence','Current source does not prove exact historical checkpoint training implementation','Removing detach alone does not repair geometry semantics or provide refinement training/quality','No independent real feature-label training data; no trained adapter']}
        atomic_json(run.path/'metrics/gradient_audit.json',result);run.record({'kind':'official_loss_gradient_audit'},result)
        return run.finish('PARTIAL',canonical(result),['Current optional geometry path has no trajectory gradient','B2D geometry semantics, expert supervision and independent data incomplete; adapter training blocked'],acceptance='BLOCKED')
    except BaseException:
        error=traceback.format_exc();run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')

def parse_unidrive_route_directory(folder):
    import re
    match=re.fullmatch(r'(.+)_(Town\d+(?:HD)?)_Route(\d+)_Weather(.+)',folder)
    if match is None:return None
    scenario,town,route,weather=match.groups()
    return {'scenario':scenario,'town':town,'route_id':int(route),'weather':weather}

UNIDRIVE_SPLIT_SCENARIOS={
    'cut_in':('StaticCutIn','cut_in_with_static_vehicle.py','Parked vehicle cuts in; actual trigger and motion require recording'),
    'braking':('HardBreakRoute','hard_break.py','StopFrontVehicles then Idle(10) then StartFrontVehicles; requires background front vehicles'),
    'crossing_candidate_requires_actor_audit':('PedestrianCrossing','pedestrian_crossing.py','Three spawned pedestrians cross; actual exposure requires actor/sensor audit'),
    'occlusion_candidate_requires_visibility_audit':('ParkingCrossingPedestrian','object_crash_vehicle.py','Vehicle blocker plus crossing walker; source intent does not prove measured occlusion'),
}

def select_unidrive_split_candidates(routes):
    """Same scenario mechanism per pair, deterministic and independent of outcomes."""
    candidates=[];used_geometry={r['geometry_sha256'] for r in routes if r['development_used']};used_keys={(r['town'],r['route_id']) for r in routes if r['development_used']}
    for family,(scenario,_,_) in UNIDRIVE_SPLIT_SCENARIOS.items():
        pool=sorted([r for r in routes if r['scenario']==scenario and not r['development_used']],key=lambda r:(r['known_annotation_overlap'],digest([r['town'],r['route_id'],r['scenario']])))
        selected=[];local_geometry=set(used_geometry);local_keys=set(used_keys)
        for r in pool:
            key=(r['town'],r['route_id'])
            if r['geometry_sha256'] in local_geometry or key in local_keys:continue
            selected.append(r);local_geometry.add(r['geometry_sha256']);local_keys.add(key)
            if len(selected)==2:break
        for i,split in enumerate(('calibration_candidate','test_candidate')):
            if len(selected)<2:
                candidates.append({'family':family,'scenario':scenario,'split':split,'status':'BLOCKED_NO_UNIQUE_SAME_SCENARIO_PAIR'});continue
            candidates.append(dict(selected[i],family=family,split=split,status='PROVISIONAL_NOT_COLLECTED_NOT_VERIFIED_HELDOUT',seed=101 if i==0 else 1001))
        if len(selected)==2:used_geometry=local_geometry;used_keys=local_keys
    return candidates

def run_unidrive_split_audit(args):
    """Audit available official training metadata; never invent a held-out split."""
    if dry_plan(args,[{'operation':'local training annotation/route overlap audit','downloads':False,'training':False}]):return 0
    import re,xml.etree.ElementTree as ET,collections
    metadata=read_json(ROOT/'audits/route_a/unidrive_data.json');entry=next(f for f in metadata['files'] if f['name']=='b2d_traj_train.jsonl')
    annotation=ROOT/'datasets/UniDriveVLA'/metadata['revision']/entry['name'];annotation_hash=file_hash(annotation)
    if annotation_hash!=entry['lfs']['sha256']:raise ValueError('Training annotation hash mismatch')
    data_root=UNIDRIVE_REPO/'Bench2Drive';xml_path=data_root/'bench2drive/leaderboard/data/bench2drive220.xml'
    training_config=ROOT/'audits/dac2027_planning_tracking_20261106/checkpoint_training_config.txt'
    benchmark=Path(os.environ['FRAMELEASE_BENCHMARK_ROOT']);license_path=benchmark/'LICENSE'
    protocol=ROOT/'audits/dac2027_state_estimation_20261106/N2_SPLIT_PROTOCOL.md'
    source_files=[benchmark/'scenario_runner/srunner/scenarios'/v[1] for v in UNIDRIVE_SPLIT_SCENARIOS.values()]
    source_files.extend([benchmark/'scenario_runner/srunner/scenarios/background_activity.py',benchmark/'scenario_runner/srunner/tools/background_manager.py'])
    config={'mode':args.mode,'source_commit':UNIDRIVE_COMMIT,'annotation':str(annotation),'annotation_sha256':annotation_hash,'routes_xml':str(xml_path),'routes_sha256':file_hash(xml_path),'checkpoint_config_sha256':file_hash(training_config),'protocol_sha256':file_hash(protocol),'scope':'KNOWN_ANNOTATION_OVERLAP_AND_PROVISIONAL_COLLECTION_SPLITS_NOT_VERIFIED_HELDOUT','development_route':['Town12',2086],'selection':'v3: same exact scenario per pair; known-unseen route keys first; SHA256 of town/id/scenario; unique keys and waypoint geometry; seeds101/1001','gate_promoted':False}
    run=StageRun('stage02_real_vla',args,config,['OFFICIAL_METADATA_AUDIT'],[xml_path,training_config,ROOT/'audits/route_a/unidrive_data.json',license_path,protocol,*source_files])
    try:
        directories=collections.Counter();route_keys=collections.Counter();seen=set();duplicate_frames=unknown=records=0;scenarios=collections.Counter()
        with annotation.open() as f:
            for line in f:
                row=json.loads(line);images=row['image'];records+=1
                key=tuple(images);duplicate_frames+=key in seen;seen.add(key)
                parents={str(Path(p).parents[2]) for p in images}
                if len(parents)!=1:raise ValueError('Camera images disagree on route folder')
                folder=Path(images[0]).parts[3];directories[folder]+=1
                parsed=parse_unidrive_route_directory(folder)
                if parsed:
                    route_keys[(parsed['town'],parsed['route_id'])]+=1;scenarios[parsed['scenario']]+=1
                else:unknown+=1
        write_csv(run.path/'metrics/training_directories.csv',[{'directory':d,'records':n,'parsed':parse_unidrive_route_directory(d) is not None,**(parse_unidrive_route_directory(d) or {})} for d,n in sorted(directories.items())])
        train_text=training_config.read_text();info_refs=sorted(set(re.findall(r"['\"]([^'\"]*b2d_infos_[^'\"]*\.pkl)['\"]",train_text)))
        infos=[{'config_reference':s,'expected_path':str(data_root/s),'exists':(data_root/s).is_file(),'sha256':file_hash(data_root/s) if (data_root/s).is_file() else None} for s in info_refs]
        routes=[];elements={}
        for route in ET.parse(xml_path).getroot().findall('route'):
            town=route.get('town');identity=int(route.get('id'));names=[s.get('type') for s in route.findall('./scenarios/scenario')]
            if not names:names=[s.get('name','UNKNOWN') for s in route.findall('./scenarios/scenario')]
            waypoints=[{k:float(v) for k,v in p.attrib.items()} for p in route.findall('./waypoints/position')]
            geometry=digest({'town':town,'waypoints':waypoints});scenario=';'.join(names)
            families=[family for family,(target,_,_) in UNIDRIVE_SPLIT_SCENARIOS.items() if scenario==target]
            key=(town,identity);item={'town':town,'route_id':identity,'scenario':scenario,'known_annotation_records':route_keys[key],'known_annotation_overlap':key in route_keys,'development_used':key==('Town12',2086),'geometry_sha256':geometry,'xml_route_sha256':digest(ET.tostring(route,encoding='unicode')),'families':families,'pretrained_training_independence':'UNKNOWN_MISSING_FULL_TRAINING_INFOS'}
            if key in elements:raise ValueError('Duplicate benchmark route identity')
            elements[key]=route;routes.append(item)
        write_csv(run.path/'metrics/benchmark_route_overlap.csv',routes)
        candidates=select_unidrive_split_candidates(routes)
        for selected in candidates:
            if 'route_id' not in selected:continue
            destination=run.path/'raw'/f"{selected['family']}_{selected['split']}_route{selected['route_id']}.xml";tree=ET.Element('routes');tree.append(elements[(selected['town'],selected['route_id'])]);ET.ElementTree(tree).write(destination,encoding='utf-8',xml_declaration=True);selected['derived_route_xml']=str(destination);selected['derived_route_sha256']=file_hash(destination)
        source_evidence=[]
        for family,(scenario,filename,mechanism) in UNIDRIVE_SPLIT_SCENARIOS.items():
            active=benchmark/'scenario_runner/srunner/scenarios'/filename;vendored=data_root/'bench2drive/scenario_runner/srunner/scenarios'/filename
            source_evidence.append({'family':family,'scenario':scenario,'mechanism':mechanism,'active_path':str(active),'active_sha256':file_hash(active),'model_vendored_path':str(vendored),'model_vendored_sha256':file_hash(vendored),'same_bytes':file_hash(active)==file_hash(vendored),'observed_exposure':False})
        atomic_json(run.path/'metrics/scenario_source_audit.json',{'sources':source_evidence,'runtime_xml_sha256':file_hash(benchmark/'leaderboard/data/bench2drive220.xml'),'model_xml_sha256':file_hash(xml_path),'geometry_uniqueness_scope':'Exact town/waypoint sequence only, not disjoint roads or pretraining independence'})
        result={'annotation_records':records,'route_directories':len(directories),'unique_town_route_keys':len(route_keys),'duplicate_image_sets':duplicate_frames,'unparsed_annotation_records':unknown,'training_infos':infos,'benchmark_routes':len(routes),'benchmark_routes_overlapping_known_annotation':sum(r['known_annotation_overlap'] for r in routes),'development_route_known_annotation_records':route_keys[('Town12',2086)],'scenario_types_in_known_annotation':dict(scenarios),'candidates':candidates,'license_evidence':{'annotation_hf_card':metadata.get('card'),'benchmark_license_file':str(license_path),'benchmark_license_sha256':file_hash(license_path),'benchmark_readme':'All assets and code CC-BY-NC-ND unless specified otherwise; annotation card does not relicense source images','redistribution_performed':False},'independent_calibration_test_established':False,'blockers':['Checkpoint full train/val infos and referenced camera images unavailable; JSONL is not proof of all pretraining exposure','Source scenario names do not establish visibility/actor coverage; provisional routes need source and actual sensor audit','No candidate recordings, calibration or held-out evaluation executed'],'gate_promoted':False}
        result['scenario_source_evidence']=source_evidence
        if unknown:result['blockers'].append(f'{unknown} annotation records have unparsed route identity; overlap coverage is incomplete')
        atomic_json(run.path/'metrics/split_audit.json',result);run.record({'kind':'training_route_overlap_and_provisional_split'},result)
        return run.finish('PARTIAL',canonical(result),result['blockers'],acceptance='BLOCKED')
    except BaseException:
        error=traceback.format_exc();run.log('failure',traceback=error);return run.finish('FAILED',error,[error])

def main(argv=None):
    p=parser('stage02_real_vla',('smoke','profile','refinement','full','plan-audit','legal-pair','closed-loop-audit','contract-audit','anytime-audit','wam-audit','unidrive-audit','unidrive-resources','minddrive-audit','unidrive-operator','unidrive-base-resources','unidrive-data-audit','unidrive-model-load','unidrive-replay','unidrive-flow-probe','unidrive-condition-probe','unidrive-split-audit','unidrive-gradient-audit','b2d-resource-audit','minddrive-linux-audit','b2d-supervision-audit','b2d-map-audit','b2d-alignment-audit','b2d-feature-probe','b2d-multiscene-resources','b2d-validation-resources','b2d-corpus-manifest','b2d-corpus-features','b2d-adapter-pilot'));p.add_argument('--unidrive-probe-inputs',nargs='+',type=Path);p.add_argument('--unidrive-numerical-audit',action='store_true');p.add_argument('--unidrive-resident-switch',action='store_true');p.add_argument('--unidrive-input',type=Path);p.add_argument('--unidrive-prompt-command',choices=('official','onehot-argmax'),default='official');p.add_argument('--unidrive-interleave-input',type=Path); p.add_argument('--input-manifest',type=Path,default=ROOT/'datasets/recogdrive/input_manifest.json');p.add_argument('--backbone-only',action='store_true',help='Explicit actual pretrained VLM diagnostic; never full driving VLA evidence');p.add_argument('--backend',choices=('official','windows-eager'),default='official');p.add_argument('--profile-sweep',action='store_true',help='Actual 3 tiling budgets x 3 DDIM depths; no ground-truth quality claim');p.add_argument('--saved-manifest',type=Path,default=ROOT/'outputs/stage02/runs/20261102T074818_6ca58097/manifest.json');p.add_argument('--closed-loop-episode',type=Path);p.add_argument('--route-geometry',type=Path);p.add_argument('--download-attempts',type=int,default=3);args=p.parse_args(argv)
    if args.download_attempts<1 or args.download_attempts>30:p.error('download-attempts must be 1..30')
    if args.mode=='b2d-corpus-manifest':return run_b2d_corpus_manifest(args)
    if args.mode=='b2d-corpus-features':return run_b2d_corpus_features(args)
    if args.mode=='b2d-adapter-pilot':return run_b2d_adapter_pilot(args)
    if args.mode in ('b2d-multiscene-resources','b2d-validation-resources'):return run_b2d_multiscene_resources(args)
    if args.mode=='b2d-map-audit':return run_b2d_map_audit(args)
    if args.mode=='b2d-alignment-audit':return run_b2d_alignment_audit(args)
    if args.mode=='b2d-feature-probe':return run_b2d_feature_probe(args)
    if args.mode=='b2d-supervision-audit':return run_b2d_supervision_audit(args)
    if args.mode=='b2d-resource-audit':return run_b2d_resource_audit(args)
    if args.mode=='minddrive-linux-audit':return run_minddrive_linux_audit(args)
    if args.mode=='unidrive-gradient-audit':return run_unidrive_gradient_audit(args)
    if args.mode=='unidrive-split-audit':return run_unidrive_split_audit(args)
    if args.mode=='unidrive-condition-probe':return run_unidrive_condition_probe(args)
    if args.mode=='unidrive-flow-probe':return run_unidrive_flow_probe(args)
    if args.mode=='unidrive-replay':return run_unidrive_replay(args)
    if args.mode=='unidrive-model-load':return run_unidrive_model_load(args)
    if args.mode=='unidrive-base-resources':return run_unidrive_base_resources(args)
    if args.mode=='unidrive-data-audit':return run_unidrive_data_audit(args)
    if args.mode=='unidrive-operator':return run_unidrive_operator(args)
    if args.mode=='minddrive-audit':return run_minddrive_audit(args)
    if args.mode=='unidrive-audit':return run_unidrive_audit(args)
    if args.mode=='unidrive-resources':return run_unidrive_resources(args)
    if args.profile_sweep and (args.backend!='windows-eager' or args.backbone_only):p.error('Profile sweep requires explicit windows-eager full network backend')
    if args.config:
        config=read_json(args.config)
        if set(config)-{'input_manifest'}:p.error('Supported Stage02 config keys: input_manifest')
        if 'input_manifest' in config:args.input_manifest=Path(config['input_manifest'])
    return run_experiment(args)
if __name__=='__main__':raise SystemExit(main())

