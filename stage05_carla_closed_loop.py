"""Actual VLA/CARLA loop. Independent wall-paced tick owner; real model in Conda worker.
No synthetic policy fallback. Ego localization is an explicitly required official model signal.
Deployment obstacle perception/calibration and benchmark evaluator remain separate prerequisites.
"""
from __future__ import annotations
import collections, dataclasses, math, multiprocessing as mp, os, queue, socket, subprocess, sys, threading, time, traceback
from pathlib import Path
from framelease_common import *
SCENARIOS=('straight','following','sudden_braking','cut_in','intersection','pedestrian','occlusion','dense_traffic')

def wrap_angle(x):return (x+math.pi)%(2*math.pi)-math.pi

def trajectory_reference(trajectory,origin,elapsed):
    """Fixed observation origin; point zero is t=.5, not t=0. No future nearest-point jump."""
    if len(trajectory)!=8 or not 0<=elapsed<=4:raise ValueError('Reference outside decoded four-second trajectory')
    points=[[0.,0.,0.]]+trajectory;i=min(7,int(elapsed/.5));u=(elapsed-i*.5)/.5
    a,b=points[i],points[i+1];x=a[0]+u*(b[0]-a[0]);y=a[1]+u*(b[1]-a[1]);heading=a[2]+u*wrap_angle(b[2]-a[2])
    c,s=math.cos(origin[2]),math.sin(origin[2]);v=math.hypot(b[0]-a[0],b[1]-a[1])/.5
    prev=math.hypot(a[0]-points[max(0,i-1)][0],a[1]-points[max(0,i-1)][1])/.5 if i else v
    return {'pose':[origin[0]+c*x-s*y,origin[1]+s*x+c*y,wrap_angle(origin[2]+heading)],'speed_mps':v,'acceleration_mps2':(v-prev)/.5,'segment':i}

def diagnostic_evidence_type(oracle_route=False,sensor_only=False):
    return 'CARLA_SENSOR_DIAGNOSTIC' if sensor_only else 'CARLA_ORACLE_DIAGNOSTIC' if oracle_route else 'CARLA_CLOSED_LOOP'

class TrajectoryTracker:
    def __init__(self,wheelbase=2.875,max_speed=60.,max_steer_angle=.7):
        self.wheelbase=wheelbase;self.max_speed=max_speed;self.max_steer_angle=max_steer_angle
    def control(self,trajectory,origin,pose,speed,elapsed,acceleration=0.):
        ref=trajectory_reference(trajectory,origin,elapsed)
        target=trajectory_reference(trajectory,origin,min(4.,elapsed+.7))['pose']
        dx,dy=target[0]-pose[0],target[1]-pose[1]
        local_x=math.cos(pose[2])*dx+math.sin(pose[2])*dy;local_y=-math.sin(pose[2])*dx+math.cos(pose[2])*dy
        raw=math.atan2(2*self.wheelbase*local_y,max(1.,dx*dx+dy*dy))/self.max_steer_angle
        steer=max(-1.,min(1.,raw));desired=min(self.max_speed,ref['speed_mps']);error=desired-speed
        # A target behind ego is not a forward pure-pursuit command. Keep the cause visible.
        behind=local_x<-.25;throttle=0. if behind or error<=0 else min(.6,.12+.22*error)
        brake=1. if behind else min(1.,max(0.,-.3*error))
        rx,ry=pose[0]-ref['pose'][0],pose[1]-ref['pose'][1];rh=ref['pose'][2]
        return {'throttle':throttle,'brake':brake,'steer':steer,'target_speed_mps':desired,
                'reference_pose':ref['pose'],'reference_speed_mps':ref['speed_mps'],'reference_segment':ref['segment'],
                'cross_track_error_m':-math.sin(rh)*rx+math.cos(rh)*ry,'along_track_error_m':math.cos(rh)*rx+math.sin(rh)*ry,
                'heading_error_rad':wrap_angle(pose[2]-rh),'speed_error_mps':speed-desired,
                'acceleration_error_mps2':acceleration-ref['acceleration_mps2'],
                'command_saturation':abs(raw)>1 or throttle>=.6 or brake>=1,'target_behind_ego':behind,
                'speed_cap_active':ref['speed_mps']>self.max_speed}

def merge_collision_callbacks(callbacks,dt=.05,gap_s=.5):
    groups=[];last={}
    for c in sorted(callbacks,key=lambda x:x['frame']):
        actor=c['other_actor'];stamp=c.get('sim_s',c['frame']*dt);g=last.get(actor)
        if g is None or stamp-g['end_s']>gap_s+1e-6:
            g={'event_id':len(groups)+1,'other_actor':actor,'start_s':stamp,'end_s':stamp,'first_frame':c['frame'],'last_frame':c['frame'],'callback_count':0,'impulse_peak_Ns':None};groups.append(g);last[actor]=g
        g['end_s']=stamp;g['last_frame']=c['frame'];g['callback_count']+=1
        if c.get('impulse_Ns') is not None:g['impulse_peak_Ns']=max(g['impulse_peak_Ns'] or 0.,c['impulse_Ns'])
    return groups

def audit_episode(path,output):
    """Read immutable raw evidence. Missing historical fields stay unavailable."""
    data=read_json(path/'final_events.json');ticks=data['ticks'];by_frame={t['frame']:t for t in ticks}
    dt=statistics.median(b['sim_s']-a['sim_s'] for a,b in zip(ticks,ticks[1:]));commits=[e for e in data['events'] if e['kind']=='commit']
    candidates={};rows=[];callbacks=[];errors=[];discontinuities=[];previous_candidate=None
    for t in ticks:
        eligible=[e for e in commits if e['application_sim_s']<=t['sim_s']+1e-7];active=eligible[-1] if eligible else None
        ref=None;candidate=None
        if active:
            f=path/('candidate_'+str(active['frame'])+'.json')
            if f.is_file():
                if active['frame'] not in candidates:candidates[active['frame']]=read_json(f)
                candidate=candidates[active['frame']];age=t['sim_s']-candidate['record']['capture_s']
                if 0<=age<=4:ref=trajectory_reference(candidate['result']['trajectory'],candidate['record']['origin'],age)
                if previous_candidate is not None and previous_candidate['record']['frame']!=active['frame']:
                    oldage=t['sim_s']-previous_candidate['record']['capture_s']
                    if ref and 0<=oldage<=4:
                        old=trajectory_reference(previous_candidate['result']['trajectory'],previous_candidate['record']['origin'],oldage)
                        discontinuities.append({'frame':t['frame'],'old_observation':previous_candidate['record']['frame'],'new_observation':active['frame'],'position_jump_m':math.dist(old['pose'][:2],ref['pose'][:2]),'heading_jump_rad':wrap_angle(ref['pose'][2]-old['pose'][2]),'reference_speed_jump_mps':ref['speed_mps']-old['speed_mps']})
                previous_candidate=candidate
        if ref:
            state=t.get('model_reference_state',t.get('pre_state',t));dx,dy=state['x_m']-ref['pose'][0],-state['y_m']-ref['pose'][1]
            errors.append({'frame':t['frame'],'observation_id':active['frame'],'time_alignment':'exact_pre_state' if 'pre_state' in t else 'legacy_position_post_tick_vs_reference_pre_tick_50ms_bias','cross_track_error_m':-math.sin(ref['pose'][2])*dx+math.cos(ref['pose'][2])*dy,'position_error_m':math.hypot(dx,dy),'speed_error_mps':state['speed_mps']-ref['speed_mps'],'fallback':t['fallback']})
    for index,c in enumerate(data['collisions']):
        t=by_frame.get(c['frame']);active=None;candidate=None
        if t:
            active=next((e for e in reversed(commits) if e['application_sim_s']<=t['sim_s']+1e-7),None)
            if active:candidate=candidates.get(active['frame'])
        collision={**c,'sim_s':c.get('sim_s',t.get('post_sim_s',t['sim_s']+dt) if t else c['frame']*dt)};callbacks.append(collision)
        prev=by_frame.get(c['frame']-1)
        rows.append({'callback_index':index,'frame':c['frame'],'other_actor':c['other_actor'],'collision_sim_s':collision['sim_s'],
            'sim_time_source':'sensor' if 'sim_s' in c else 'reconstructed_post_tick','callback_wall_ns':c.get('wall_ns'),
            'tick_wall_ns':t.get('wall_ns') if t else None,'ego_x_m':t.get('x_m') if t else None,'ego_y_m':t.get('y_m') if t else None,
            'speed_mps':t.get('speed_mps') if t else None,'acceleration_mps2':t.get('acceleration_mps2') if t else None,
            'ego_yaw_rad':t.get('post_state',{}).get('yaw_rad') if t else None,'fallback':t.get('fallback') if t else None,
            'control':{k:t.get(k) for k in ('throttle','brake','steer')} if t else None,'previous_control':{k:prev.get(k) for k in ('throttle','brake','steer')} if prev else None,
            'observation_id':active['frame'] if active else None,'active_trajectory':candidate['result']['trajectory'] if candidate else None,
            'capture_sim_s':candidate['record']['capture_s'] if candidate else None,'worker_start_ns':candidate['start_ns'] if candidate else None,'worker_end_ns':candidate['end_ns'] if candidate else None,
            'validation_ns':active.get('validation_end_ns') if active else None,'commit_ns':active.get('commit_wall_ns') if active else None,
            'apply_command_ns':t.get('command_ns') if t else None,'observation_age_s':t.get('action_age_s') if t else None,
            'nearby_objects':t.get('evaluation_context') if t else None,'impulse_Ns':c.get('impulse_Ns'),'other_actor_type':c.get('other_actor_type')})
    groups=merge_collision_callbacks(callbacks,dt);summary={'episode_source':str(path.resolve()),'source_sha256':file_hash(path/'final_events.json'),'callback_count':len(rows),'unique_collision_events':len(groups),'collision_episodes':int(bool(rows)),'episodes':1,'severity':'measured impulse' if all(c.get('impulse_Ns') is not None for c in callbacks) and callbacks else 'UNKNOWN','merge_gap_s':.5,'event_count_sensitivity':{str(g):len(merge_collision_callbacks(callbacks,dt,g)) for g in (.2,.5,1.)},'progress_m':data['progress_recomputed_m'],'fallback_fraction':statistics.mean(t['fallback'] for t in ticks),'trajectory_discontinuities':len(discontinuities),'position_jump_max_m':max([r['position_jump_m'] for r in discontinuities],default=None),'legacy_timestamp_mixing':any('post_sim_s' not in t for t in ticks),'safety_acceptance':'FAILED' if rows else 'UNVALIDATED'}
    output.mkdir(parents=True,exist_ok=True);atomic_json(output/'collision_callbacks.json',rows);write_csv(output/'collision_callbacks.csv',[{k:canonical(v) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows]);write_csv(output/'collision_events.csv',groups);write_csv(output/'tracking_errors.csv',errors);write_csv(output/'trajectory_discontinuities.csv',discontinuities);atomic_json(output/'collision_summary.json',summary)
    report='# Collision Root Cause Report\n\n'+canonical(summary)+'\n\n## Evidence\nAll raw callbacks are retained. Events merge the same actor within 0.5 simulation seconds; 0.2/1.0-second sensitivity is reported. Each row links the active observation, candidate, worker timing and controls. Historical missing impulse, actor type, yaw, road margin, exact validation/commit time and callback wall time are UNKNOWN, not inferred measurements.\n\n## Confirmed implementation defects\nThe legacy tick row mixes post-step position/frame with pre-step time/speed/acceleration. Legacy nearest-point selection can jump into a future segment; the first reference speed excludes the t=0 observation origin. No lane/dynamic validation precedes kinematic-only admission. These are source-level findings, not proof that any single defect caused the collision.\n\n## Causal limits and next checks\nRepeated contact does not identify the object class or impact severity. Camera frames can support qualitative road-departure diagnosis but cannot replace logged geometry. New runs log synchronized pre/post states, collision impulse/object identity, map-relative geometry (evaluation only), active candidate timing and reference errors. Fixed diagnostic TTL is not online AVL. Any positive progress with collisions remains failed safety acceptance.\n'
    (output/'Collision_Root_Cause_Report.md').write_text(report,encoding='utf8');return summary

def local_history(history,current):
    c,s=math.cos(current['yaw']),math.sin(current['yaw']);out=[]
    for h in history:
        dx,dy=h['x']-current['x'],h['y']-current['y'];heading=(h['yaw']-current['yaw']+math.pi)%(2*math.pi)-math.pi
        out.append({'pose':[c*dx+s*dy,-s*dx+c*dy,heading],'velocity':[c*h['vx']+s*h['vy'],-s*h['vx']+c*h['vy']],'acceleration':[c*h['ax']+s*h['ay'],-s*h['ax']+c*h['ay']],'driving_command':h['command'],'capture_s':h['capture_s']})
    return out

def reference_state(state,offset_x,omega,alpha):
    """Rigid-body point transform in CARLA world XY; angular units radians."""
    yaw=state['yaw_rad'];rx=math.cos(yaw)*offset_x;ry=math.sin(yaw)*offset_x
    return {**state,'x_m':state['x_m']+rx,'y_m':state['y_m']+ry,
            'vx_mps':state['vx_mps']-omega*ry,'vy_mps':state['vy_mps']+omega*rx,
            'ax_mps2':state['ax_mps2']-alpha*ry-omega*omega*rx,'ay_mps2':state['ay_mps2']+alpha*rx-omega*omega*ry}

def model_worker(input_queue,output_queue,stop,vlm,planner,seed,backend='official',steps=5,runtime_policy=None):
    try:
        worker_sources={name:file_hash(ROOT/name) for name in ('stage02_real_vla.py','stage03_avl_validation.py','stage04_gpu_runtime.py','stage05_carla_closed_loop.py','framelease_common.py')}
        # multiprocessing spawn transfers parent sys.path even with set_executable.
        # Restore only this child to the explicitly selected isolated model environment.
        import site
        env_root=ROOT/'.conda-model'
        if Path(sys.executable).resolve()!= (env_root/'python.exe').resolve():raise RuntimeError('Wrong model child interpreter: '+sys.executable)
        sys.path[:]=[p for p in sys.path if '.conda-carla' not in str(p).lower()]
        for p in (env_root/'Lib',env_root/'DLLs',env_root/'Lib/site-packages'):
            if str(p) not in sys.path:sys.path.insert(0,str(p))
        site.addsitedir(str(env_root/'Lib/site-packages'))
        dll_handles=[os.add_dll_directory(str(p)) for p in (env_root,env_root/'Library/bin') if p.is_dir()]
        from stage02_real_vla import ReCogAdapter,WindowsInferenceAdapter
        model=(ReCogAdapter if backend=='official' else WindowsInferenceAdapter)(vlm,planner)
        if backend=='windows-eager':model.configure_profile(12,steps)
        elif steps!=5:raise RuntimeError('Official profile override requires audited backend')
        output_queue.put({'kind':'ready','interpreter':sys.executable,'torch_module':model.torch.__file__,'provenance':model.provenance,'worker_source_hashes':worker_sources})
        if runtime_policy:
            from stage04_gpu_runtime import cooperative_model_loop
            cooperative_model_loop(model,input_queue,output_queue,stop,seed,runtime_policy);return
        while not stop.is_set():
            try:record=input_queue.get(timeout=.2)
            except queue.Empty:continue
            if record is None:break
            # Drain queued observations before admission; model kernels are not interrupted.
            while True:
                try:new=input_queue.get_nowait()
                except queue.Empty:break
                if new is None:stop.set();break
                record=new
            if stop.is_set():break
            start=time.perf_counter_ns();result,_=model.infer(record,observation_seed(seed,record))
            output_queue.put({'kind':'candidate','record':record,'result':result,'start_ns':start,'end_ns':time.perf_counter_ns()})
    except BaseException:output_queue.put({'kind':'worker_failure','traceback':traceback.format_exc()})

def prerequisites(args):
    from stage02_real_vla import resolve_resources,DependencyBlocked
    blockers=[];resources=None
    try:resources=resolve_resources()
    except (DependencyBlocked,FileNotFoundError,KeyError) as e:blockers.append(str(e))
    try:
        import carla
        client_path=carla.__file__
    except ImportError as e:client_path=None;blockers.append('CARLA client unavailable in this interpreter; use .conda-carla: '+repr(e))
    exe=args.carla_path/'CarlaUE4/Binaries/Win64/CarlaUE4-Win64-Shipping.exe'
    if not exe.is_file():blockers.append('CARLA 0.9.15 Shipping executable missing')
    if args.diagnostic_closed_loop:
        deployment={'diagnostic_only':True,'camera':{'width':640,'height':360,'fov':90,'location':{'x':1.5,'y':0,'z':2.4}},'history_interval_s':.5,'validated_max_age_s':args.diagnostic_age_cap,'age_cap_scope':'explicit experimental TTL, not validated safety lease','navigation_command':[0,1,0,0]}
        return blockers,resources,deployment,client_path
    deployment=read_json(args.deployment_config) if args.deployment_config and args.deployment_config.is_file() else None
    if deployment is None:blockers.append('Validated CARLA camera/local-history/coordinate calibration and deployment perception contract missing')
    else:
        for key in ('camera','history_interval_s','coordinate_validation_evidence','perception_evidence','lease_evidence','online_bounds'):
            if not deployment.get(key):blockers.append('Deployment configuration missing '+key)
        for key in ('coordinate_validation_evidence','perception_evidence','lease_evidence'):
            if deployment.get(key) and not Path(deployment[key]).is_file():blockers.append('Deployment evidence does not exist: '+key)
        if not args.online_avl:blockers.append('Formal admission requires --online-avl; fixed diagnostic TTL prohibited')
        if deployment.get('online_bounds',{}).get('status')!='CALIBRATED':blockers.append('Deployment bounds not calibrated and independently validated')
        blockers.append('Current forward radar adapter has unvalidated occlusion/road coverage; formal deployment remains blocked')
    return blockers,resources,deployment,client_path

def spawn_scenario(world,vehicle,scenario,owned,seed):
    """Scenario actors are simulation intervention/evaluation only, never model input."""
    import carla
    rng=random.Random(seed);lib=world.get_blueprint_library();origin=vehicle.get_transform();forward=origin.get_forward_vector();right=origin.get_right_vector();actors=[]
    def vehicle_at(distance,lateral=0):
        t=carla.Transform(origin.location+forward*distance+right*lateral,origin.rotation);t.location.z+=.3
        actor=world.try_spawn_actor(lib.find('vehicle.audi.a2'),t)
        if actor:owned.append(actor);actors.append(actor)
        return actor
    lead=vehicle_at(24) if scenario in ('following','sudden_braking') else None
    cutter=vehicle_at(18,3.5) if scenario=='cut_in' else None
    if scenario in ('pedestrian','occlusion'):
        if scenario=='occlusion':vehicle_at(20,2.5)
        t=carla.Transform(origin.location+forward*28+right*5);t.location.z+=1
        walkers=list(lib.filter('walker.pedestrian.*'));walker=world.try_spawn_actor(walkers[seed%len(walkers)],t)
        if walker:owned.append(walker);actors.append(walker)
        else:raise RuntimeError('Requested pedestrian scenario failed to spawn actor')
    else:walker=None
    if scenario=='dense_traffic':
        for d in (15,25,40,55):vehicle_at(d,3.5*(-1 if rng.random()<.5 else 1))
    if scenario=='intersection':
        wp=world.get_map().get_waypoint(origin.location)
        if not wp.is_junction:raise DependencyError('Intersection scenario requires configured junction spawn, default route is not a valid intersection benchmark')
    if scenario in ('following','sudden_braking') and lead is None:raise RuntimeError('Required lead actor spawn failed')
    if scenario=='cut_in' and cutter is None:raise RuntimeError('Required cut-in actor spawn failed')
    def update(elapsed):
        if lead:lead.apply_control(carla.VehicleControl(throttle=.35,brake=1. if scenario=='sudden_braking' and elapsed>3 else 0.))
        if cutter:cutter.apply_control(carla.VehicleControl(throttle=.3,steer=-.2 if 2<elapsed<3 else 0.))
        if walker:walker.apply_control(carla.WalkerControl(direction=carla.Vector3D(-right.x,-right.y,0),speed=1.5))
    return update,actors
class DependencyError(RuntimeError):pass

def carla_state(vehicle):
    tr=vehicle.get_transform();v=vehicle.get_velocity();a=vehicle.get_acceleration()
    return {'x_m':tr.location.x,'y_m':tr.location.y,'z_m':tr.location.z,'yaw_rad':math.radians(tr.rotation.yaw),
            'vx_mps':v.x,'vy_mps':v.y,'ax_mps2':a.x,'ay_mps2':a.y,'speed_mps':math.hypot(v.x,v.y),'acceleration_mps2':math.hypot(a.x,a.y)}

def basic_straight_spawn(carla_map):
    """Scene design uses map geometry, not online control/perception truth."""
    candidates=[]
    for index,transform in enumerate(carla_map.get_spawn_points()):
        wp=carla_map.get_waypoint(transform.location)
        if wp is None or wp.is_junction:continue
        origin_yaw=math.radians(wp.transform.rotation.yaw);points=[];valid=True;current=wp
        for _ in range(20):
            nxt=current.next(2.)
            if len(nxt)!=1:valid=False;break
            current=nxt[0]
            if current.is_junction or abs(wrap_angle(math.radians(current.transform.rotation.yaw)-origin_yaw))>math.radians(5):valid=False;break
            points.append([current.transform.location.x,current.transform.location.y])
        if valid:candidates.append({'spawn_index':index,'verified_straight_length_m':40,'road_id':wp.road_id,'lane_id':wp.lane_id,'points':points})
    if not candidates:raise DependencyError('No verified nonjunction 40m straight spawn on this map')
    return candidates[0]['spawn_index'],{'selection':'lowest spawn index satisfying frozen geometry criteria, no outcome-based selection','candidates':candidates}

def capture_route_geometry(carla_map,location):
    """Fixed connected lane, evaluator/oracle ONLY; ambiguous junctions stay unknown."""
    first=carla_map.get_waypoint(location);back=[];wp=first
    for _ in range(20):
        prev=wp.previous(.5)
        if len(prev)!=1 or prev[0].is_junction:break
        wp=prev[0];back.append(wp)
    chain=list(reversed(back))+[first];wp=first;stop='distance_limit'
    for _ in range(300):
        nxt=wp.next(.5)
        if len(nxt)!=1:stop='ambiguous_branch_or_route_end';break
        if nxt[0].is_junction:stop='junction_requires_explicit_route';break
        wp=nxt[0];chain.append(wp)
    nodes=[];distance=0.
    for w in chain:
        tr=w.transform;xy=[tr.location.x,-tr.location.y]
        if nodes:distance+=math.dist(xy,nodes[-1]['xy'])
        nodes.append({'xy':xy,'yaw':-math.radians(tr.rotation.yaw),'s':distance,'width':w.lane_width,'road_id':w.road_id,'lane_id':w.lane_id,'section_id':w.section_id,'junction':w.is_junction,'left_marking':str(w.left_lane_marking.type),'right_marking':str(w.right_lane_marking.type),'lane_change':str(w.lane_change)})
    return {'source':'CARLA_GROUND_TRUTH_EVALUATION_OR_EXPLICIT_ORACLE_ONLY','map':carla_map.name,'opendrive_sha256':hashlib.sha256(carla_map.to_opendrive().encode()).hexdigest(),'nodes':nodes,'stop_reason':stop,'allowed_lane_changes':[],'route_intent':'GO_STRAIGHT_FIXED_CONNECTED_LANE','junction_scope':'UNKNOWN beyond recorded chain; no nearest-lane reassignment'}

def route_projection(route,xy):
    best=None
    for a,b in zip(route['nodes'],route['nodes'][1:]):
        dx,dy=b['xy'][0]-a['xy'][0],b['xy'][1]-a['xy'][1];l2=dx*dx+dy*dy
        if l2<1e-12:continue
        raw=((xy[0]-a['xy'][0])*dx+(xy[1]-a['xy'][1])*dy)/l2;u=max(0.,min(1.,raw));p=[a['xy'][0]+u*dx,a['xy'][1]+u*dy];dist=math.dist(xy,p)
        if best is None or dist<best['distance_m']:
            yaw=math.atan2(dy,dx);best={'s':a['s']+u*(b['s']-a['s']),'xy':p,'yaw':yaw,'width':a['width']+u*(b['width']-a['width']),'distance_m':dist,'lateral_m':-math.sin(yaw)*(xy[0]-p[0])+math.cos(yaw)*(xy[1]-p[1]),'road_id':a['road_id'],'lane_id':a['lane_id'],'raw_segment_u':raw}
    if best is None:raise ValueError('Route has fewer than two distinct nodes')
    return best

def route_pose(route,s):
    if not route['nodes'][0]['s']<=s<=route['nodes'][-1]['s']:raise ValueError('Outside declared route geometry')
    for a,b in zip(route['nodes'],route['nodes'][1:]):
        if a['s']<=s<=b['s']:
            u=(s-a['s'])/(b['s']-a['s']);return [a['xy'][0]+u*(b['xy'][0]-a['xy'][0]),a['xy'][1]+u*(b['xy'][1]-a['xy'][1]),wrap_angle(a['yaw']+u*wrap_angle(b['yaw']-a['yaw']))]
    raise ValueError('Route interpolation failed')

def oracle_route_candidate(route,origin,speed):
    """D4 only. This function must never be called in the real-VLA path."""
    s=route_projection(route,origin[:2])['s'];out=[];c,si=math.cos(origin[2]),math.sin(origin[2])
    for i in range(1,9):
        p=route_pose(route,s+speed*.5*i);dx,dy=p[0]-origin[0],p[1]-origin[1]
        out.append([c*dx+si*dy,-si*dx+c*dy,wrap_angle(p[2]-origin[2])])
    return out

def route_polygon(route):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    sections=[]
    for a,b in zip(route['nodes'],route['nodes'][1:]):
        corners=[]
        for n,sign in ((a,1),(b,1),(b,-1),(a,-1)):
            corners.append((n['xy'][0]-sign*math.sin(n['yaw'])*n['width']/2,n['xy'][1]+sign*math.cos(n['yaw'])*n['width']/2))
        polygon=Polygon(corners)
        if not polygon.is_valid:raise ValueError('Invalid route ribbon polygon')
        sections.append(polygon)
    return unary_union(sections)

def footprint_route_check(pose,geometry,route,polygon,tolerance=.05):
    from shapely.geometry import Polygon
    c,s=math.cos(pose[2]),math.sin(pose[2]);offset=geometry.get('bounding_box_offset_model_m',[0.,0.]);angle=geometry.get('bounding_box_yaw_model_rad',0.)
    cx=pose[0]+c*offset[0]-s*offset[1];cy=pose[1]+s*offset[0]+c*offset[1];c,s=math.cos(pose[2]+angle),math.sin(pose[2]+angle)
    l,w=geometry['bounding_box_half_length_m'],geometry['bounding_box_half_width_m']
    corners=[[cx+c*x-s*y,cy+s*x+c*y] for x,y in ((l,w),(l,-w),(-l,-w),(-l,w))];footprint=Polygon(corners)
    projections=[route_projection(route,p) for p in corners];center=route_projection(route,pose[:2]);length=route['nodes'][-1]['s']
    covered=all(.001<p['s']<length-.001 for p in projections)
    outside=not polygon.buffer(tolerance).covers(footprint)
    return {'route_coverage':'KNOWN' if covered else 'UNKNOWN_ROUTE_ENDPOINT','outside':outside if covered else None,'outside_area_m2':footprint.difference(polygon).area if covered else None,'lateral_m':center['lateral_m'],'heading_error_rad':wrap_angle(pose[2]-center['yaw']),'route_s':center['s'],'road_id':center['road_id'],'lane_id':center['lane_id'],'corners':corners}

def audit_road_candidates(episode,route,geometry,output,tolerance=.05):
    """D2 all saved candidates; D3 exact-pose counterfactual, no simulated backend."""
    output.mkdir(parents=True,exist_ok=True);polygon=route_polygon(route);data=read_json(episode/'final_events.json');rows=[];raw=[];ticks=[]
    for file in sorted(episode.glob('candidate_*.json'),key=lambda p:int(p.stem.split('_')[-1])):
        msg=read_json(file);record,result=msg['record'],msg['result'];trajectory=result['trajectory'];origin=record['origin'];path=[]
        candidate_geometry=dict(geometry);offset=geometry.get('bounding_box_offset_model_m',[0.,0.]);candidate_geometry['bounding_box_offset_model_m']=[offset[0]-record.get('reference_offset_x_m',0.),offset[1]]
        for k in range(81):
            ref=trajectory_reference(trajectory,origin,k*.05);path.append({'elapsed_s':k*.05,'world_model_pose':ref['pose'],'world_carla_pose':[ref['pose'][0],-ref['pose'][1],-ref['pose'][2]],**footprint_route_check(ref['pose'],candidate_geometry,route,polygon,tolerance)})
        initial=record['ego_history'][-1];v0=math.hypot(*initial['velocity']);v1=math.hypot(*trajectory[0][:2])/.5;heading_jump=abs(wrap_angle(trajectory[0][2]))/.5
        points=[[0.,0.,0.]]+trajectory;curvatures=[];direction_errors=[]
        for a,b in zip(points,points[1:]):
            distance=math.dist(a[:2],b[:2])
            if distance>.01:
                curvatures.append(abs(wrap_angle(b[2]-a[2]))/distance);direction_errors.append(abs(wrap_angle(math.atan2(b[1]-a[1],b[0]-a[0])-a[2])))
        max_curvature=max(curvatures,default=0.);vehicle_curvature_limit=math.tan(geometry['max_steer_angle_rad'])/geometry['wheelbase_m']
        outside=sum(p['outside'] is True for p in path);unknown=sum(p['outside'] is None for p in path);end=path[-1]
        row={'observation_id':record['frame'],'source':str(file),'sha256':file_hash(file),'road_status':'FAIL' if outside else ('UNKNOWN' if unknown else 'PASS_GEOMETRY_ONLY'),'outside_samples':outside,'unknown_samples':unknown,'sample_count':81,'max_abs_route_lateral_m':max(abs(p['lateral_m']) for p in path),'endpoint_heading_error_rad':end['heading_error_rad'],'endpoint_navigation':'FAIL_STRAIGHT_HEADING' if abs(end['heading_error_rad'])>math.radians(20) else ('UNKNOWN' if unknown else 'CONSISTENT_STRAIGHT_GEOMETRY'),'first_interval_speed_mps':v1,'actual_capture_speed_mps':v0,'first_interval_required_acceleration_mps2':(v1-v0)/.5,'first_interval_heading_rate_radps':heading_jump,'control_executability':'FAIL_ENGINEERING_ACCEL_SCREEN' if abs((v1-v0)/.5)>20 else 'UNKNOWN_VEHICLE_DYNAMICS','prohibited_lane_crossing':'OUTSIDE_ASSIGNED_STRAIGHT_LANE_NO_LANE_CHANGE_REQUEST' if outside else 'NOT_OBSERVED_IN_SAMPLED_PATH','D3_exact_tracking_outside_samples':outside,'D3_scope':'zero-tracking-error replay of identical VLA path, no physics execution'}
        row.update(max_sampled_curvature_per_m=max_curvature,measured_static_steer_curvature_limit_per_m=vehicle_curvature_limit,max_segment_direction_heading_error_rad=max(direction_errors,default=0.),current_state_execution_scope='necessary acceleration/steering screens only; tire dynamics and speed-dependent steer not certified')
        if max_curvature>vehicle_curvature_limit:row['control_executability']='FAIL_STATIC_STEER_GEOMETRY'
        raw.append({'summary':row,'local_trajectory':trajectory,'origin':origin,'complete_path':path});rows.append(row)
    for t in data['ticks']:
        st=t['post_state'];ticks.append({'frame':t['frame'],'sim_s':t['post_sim_s'],'active_observation_id':t.get('active_observation_id'),**footprint_route_check([st['x_m'],-st['y_m'],-st['yaw_rad']],geometry,route,polygon,tolerance)})
    summary={'episode':str(episode),'source_sha256':file_hash(episode/'final_events.json'),'candidates':len(rows),'candidate_road_failures':sum(r['road_status']=='FAIL' for r in rows),'candidate_unknown':sum(r['road_status']=='UNKNOWN' for r in rows),'candidate_geometry_pass':sum(r['road_status']=='PASS_GEOMETRY_ONLY' for r in rows),'ticks':len(ticks),'route_outside_ticks':sum(t['outside'] is True for t in ticks),'route_unknown_ticks':sum(t['outside'] is None for t in ticks),'collision_callbacks':len(data['collisions']),'lane_invasion_callbacks':len(data.get('lane_invasions',[])),'progress_m':data['progress_recomputed_m'],'tolerance_m':tolerance,'footprint':'full planar rectangle including measured bbox offset; polygon containment','temporal_resolution_s':.05,'between_samples':'Not a continuous-time safety proof','D3':'Exact sampled pose counterfactual, no alternative controller or model'}
    protocol=read_json(ROOT/'configs/road_refinement_protocol.json');crit=protocol['criteria'];cleanup=read_json(episode/'cleanup.json')
    summary['frozen_acceptance']={'protocol_sha256':file_hash(ROOT/'configs/road_refinement_protocol.json'),'passed':bool(len(ticks)==protocol['ticks'] and summary['progress_m']>=crit['minimum_planar_progress_m'] and not summary['collision_callbacks'] and not summary['lane_invasion_callbacks'] and not summary['route_outside_ticks'] and not summary['route_unknown_ticks'] and not cleanup['errors']),'scope':'D4 only validates oracle controller capacity; D1 is still necessary','independent_episodes':1}
    atomic_json(output/'complete_candidate_geometry.json',raw);write_csv(output/'candidate_geometry.csv',rows);atomic_json(output/'executed_route_geometry.json',ticks);atomic_json(output/'summary.json',summary);return summary

def evaluation_context(world,vehicle):
    """Simulator truth for attribution ONLY. Never passed to the model/controller/lease."""
    tr=vehicle.get_transform();wp=world.get_map().get_waypoint(tr.location);near=[]
    for actor in world.get_actors():
        if actor.id==vehicle.id or not actor.type_id.startswith(('vehicle.','walker.')):continue
        p=actor.get_location();d=math.hypot(p.x-tr.location.x,p.y-tr.location.y)
        if d<50:near.append({'id':actor.id,'type':actor.type_id,'relative_world_xy_m':[p.x-tr.location.x,p.y-tr.location.y],'distance_m':d})
    if wp:
        yaw=math.radians(wp.transform.rotation.yaw);dx=tr.location.x-wp.transform.location.x;dy=tr.location.y-wp.transform.location.y
        lateral=-math.sin(yaw)*dx+math.cos(yaw)*dy
        lane={'road_id':wp.road_id,'lane_id':wp.lane_id,'is_junction':wp.is_junction,'lane_width_m':wp.lane_width,'signed_lateral_error_m':lateral,'center_to_boundary_m':wp.lane_width/2-abs(lateral),'heading_error_rad':wrap_angle(math.radians(tr.rotation.yaw)-yaw),'nearest_driving_waypoint':[wp.transform.location.x,wp.transform.location.y,yaw]}
    else:lane=None
    return {'source':'CARLA_GROUND_TRUTH_EVALUATION_ONLY','nearby_actors':near,'road':lane}

def run_episode(args,resources,deployment,scenario,seed,output):
    import carla
    dt=.05;exe=args.carla_path/'CarlaUE4/Binaries/Win64/CarlaUE4-Win64-Shipping.exe';server=None;world=None;original=None;owned=[];worker=None;camera=None;cleanup=[];events=[];ticks=[];collisions=[];lane_invasions=[];radar_packets=[];perception_records=[];perception_evaluation=[];last_radar_frame=-1;radar_adapter=None;latest_perception=None
    for port in (args.port,args.port+1,args.port+2):
        with socket.socket() as s:s.bind(('127.0.0.1',port))
    output.mkdir(parents=True,exist_ok=False);sensor_lock=threading.Lock();images={};sensor_errors=[];history=collections.deque(maxlen=80);truth_history={};start=None;stop=mp.get_context('spawn').Event();inq=mp.get_context('spawn').Queue(maxsize=2);outq=mp.get_context('spawn').Queue()
    primary=None;perception_truth=[]
    try:
        log=(output/'server.log').open('wb');startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        server=subprocess.Popen([str(exe),'CarlaUE4','/Game/Carla/Maps/'+args.carla_map,'-RenderOffScreen','-nosound','-quality-level=Low','-unattended','-NoCrashDialog','-carla-rpc-port='+str(args.port)],cwd=args.carla_path,stdout=log,stderr=log,startupinfo=startup,creationflags=subprocess.CREATE_NO_WINDOW)
        for attempt in range(20):
            if server.poll() is not None:raise RuntimeError('Owned server exited')
            time.sleep(1);client=carla.Client('127.0.0.1',args.port);client.set_timeout(3)
            try:world=client.get_world();break
            except RuntimeError:continue
        if world is None:raise RuntimeError('CARLA startup failed')
        client.set_timeout(10)
        if client.get_server_version()!='0.9.15':raise RuntimeError('CARLA server version mismatch')
        if world.get_map().name.split('/')[-1]!=args.carla_map:raise RuntimeError('Map mismatch')
        original=world.get_settings();settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=dt;settings.substepping=True;settings.max_substeps=5;settings.max_substep_delta_time=.01;world.apply_settings(settings)
        bp=world.get_blueprint_library().find('vehicle.tesla.model3');bp.set_attribute('role_name','framelease_owned_vla');spawns=world.get_map().get_spawn_points();spawn_id=args.spawn_index if args.spawn_index is not None else deployment.get('scenario_spawns',{}).get(scenario,0)
        if args.basic_straight:
            spawn_id,selection=basic_straight_spawn(world.get_map());atomic_json(output/'scene_selection.json',selection)
        vehicle=world.spawn_actor(bp,spawns[spawn_id]);owned.append(vehicle)
        vehicle.apply_control(carla.VehicleControl(brake=1.))
        for _ in range(5):world.tick()
        control_scenario,scenario_actors=spawn_scenario(world,vehicle,scenario,owned,seed)
        if args.perception_probe:
            probe_transform=vehicle.get_transform();probe_transform.location+=probe_transform.get_forward_vector()*18;probe_transform.location.z+=.3
            probe=world.spawn_actor(world.get_blueprint_library().find('vehicle.audi.a2'),probe_transform);owned.append(probe);scenario_actors.append(probe)
            if args.probe_occlusion:
                blocker_transform=vehicle.get_transform();blocker_transform.location+=blocker_transform.get_forward_vector()*9;blocker_transform.location.z+=.3
                blocker=world.spawn_actor(world.get_blueprint_library().find('vehicle.mercedes.sprinter'),blocker_transform);owned.append(blocker);blocker.apply_control(carla.VehicleControl(brake=1.))
            def control_scenario(elapsed):probe.apply_control(carla.VehicleControl(throttle=.22 if 3<elapsed<8 and not args.probe_occlusion else 0.,brake=1. if elapsed>=8 or args.probe_occlusion else 0.))
        cbp=world.get_blueprint_library().find('sensor.camera.rgb');camera_cfg=deployment['camera']
        for k,v in {'image_size_x':camera_cfg['width'],'image_size_y':camera_cfg['height'],'fov':camera_cfg['fov'],'sensor_tick':camera_cfg.get('sensor_tick_s',.2)}.items():cbp.set_attribute(k,str(v))
        camera=world.spawn_actor(cbp,carla.Transform(carla.Location(**camera_cfg['location']),carla.Rotation(**camera_cfg.get('rotation',{}))),attach_to=vehicle);owned.append(camera)
        def on_image(image):
            try:
                path=(output/('frame_'+str(image.frame)+'.png')).resolve();image.save_to_disk(str(path));record={'frame':image.frame,'capture_s':image.timestamp,'image_path':str(path),'image_sha256':file_hash(path),'receive_ns':time.perf_counter_ns()}
                with sensor_lock:images[image.frame]=record
            except Exception as e:sensor_errors.append(repr(e))
        camera.listen(on_image);collision_sensor=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=vehicle);owned.append(collision_sensor)
        def on_collision(e):
            impulse=e.normal_impulse
            collisions.append({'frame':e.frame,'sim_s':e.timestamp,'wall_ns':time.perf_counter_ns(),'other_actor':e.other_actor.id,'other_actor_type':e.other_actor.type_id,'impulse_vector_Ns':[impulse.x,impulse.y,impulse.z],'impulse_Ns':impulse.length(),'event_pose':[e.transform.location.x,e.transform.location.y,math.radians(e.transform.rotation.yaw)]})
        collision_sensor.listen(on_collision)
        lane_sensor=world.spawn_actor(world.get_blueprint_library().find('sensor.other.lane_invasion'),carla.Transform(),attach_to=vehicle);owned.append(lane_sensor)
        lane_sensor.listen(lambda e:lane_invasions.append({'frame':e.frame,'sim_s':e.timestamp,'wall_ns':time.perf_counter_ns(),'crossed_markings':[str(x.type) for x in e.crossed_lane_markings],'scope':'SIMULATOR_EVALUATION_ONLY'}))
        if args.radar_perception:
            from stage03_avl_validation import RadarPerceptionAdapter
            radar_adapter=RadarPerceptionAdapter();rbp=world.get_blueprint_library().find('sensor.other.radar')
            for k,v in {'horizontal_fov':40,'vertical_fov':12,'points_per_second':4000,'range':50,'sensor_tick':.1}.items():rbp.set_attribute(k,str(v))
            if rbp.has_attribute('noise_seed'):rbp.set_attribute('noise_seed',str(seed))
            radar=world.spawn_actor(rbp,carla.Transform(carla.Location(x=2.,z=1.)),attach_to=vehicle);owned.append(radar)
            def on_radar(measurement):
                tr=measurement.transform
                packet={'frame':measurement.frame,'capture_s':measurement.timestamp,'receive_ns':time.perf_counter_ns(),'sensor_pose':[tr.location.x,-tr.location.y,-math.radians(tr.rotation.yaw)],'detections':[{'depth_m':d.depth,'azimuth_rad':d.azimuth,'altitude_rad':d.altitude,'radial_velocity_mps':d.velocity} for d in measurement]}
                with sensor_lock:radar_packets.append(packet)
            radar.listen(on_radar)
        route=capture_route_geometry(world.get_map(),vehicle.get_location());atomic_json(output/'route_geometry.json',route)
        physics=vehicle.get_physics_control();wheels=physics.wheels
        tr=vehicle.get_transform();inverse=tr.get_inverse_matrix();wheel_local=[]
        for w in wheels:
            vector=[w.position.x/100,w.position.y/100,w.position.z/100,1.]
            wheel_local.append(carla.Location(*[sum(inverse[i][j]*vector[j] for j in range(4)) for i in range(3)]))
        axle_front=sum(w.x for w in wheel_local[:2])/2;axle_rear=sum(w.x for w in wheel_local[2:])/2
        wheelbase=abs(axle_front-axle_rear);steer_angle=math.radians(max(w.max_steer_angle for w in wheels))
        if not 1.5<wheelbase<4 or not .2<steer_angle<1.6:raise ValueError('Unsupported measured vehicle geometry')
        reference_offset=axle_rear if args.model_reference=='rear-axle' and not args.oracle_route else 0.
        if reference_offset and not -3<reference_offset<0:raise ValueError('Measured rear-axle offset inconsistent with actor origin')
        atomic_json(output/'vehicle_and_map.json',{'wheelbase_m':wheelbase,'max_steer_angle_rad':steer_angle,'bounding_box_half_width_m':vehicle.bounding_box.extent.y,'bounding_box_half_length_m':vehicle.bounding_box.extent.x,'spawn_index':spawn_id,'spawn':str(spawns[spawn_id]),'map':world.get_map().name,'initial_evaluation_context':evaluation_context(world,vehicle),'camera':camera_cfg,'coordinate_adapter':'CARLA x,y,yaw -> model x,-y,-yaw; steer sign inverted','training_reference_point_equivalence':'UNVALIDATED'})
        geom=read_json(output/'vehicle_and_map.json');geom.update(bounding_box_offset_model_m=[vehicle.bounding_box.location.x,-vehicle.bounding_box.location.y],bounding_box_yaw_model_rad=-math.radians(vehicle.bounding_box.rotation.yaw),wheel_positions_world_cm=[[w.position.x,w.position.y,w.position.z] for w in wheels],wheel_positions_local_m=[[w.x,w.y,w.z] for w in wheel_local],model_reference=args.model_reference,reference_offset_x_m=reference_offset,training_reference_point_equivalence='rear axle convention corrected; camera/domain equivalence UNKNOWN');atomic_json(output/'vehicle_and_map.json',geom)
        from stage04_gpu_runtime import OnlineActionRuntime
        action_runtime=OnlineActionRuntime(args.runtime_policy or ('Fast Only' if args.ddim_steps==3 else 'Fixed Deep'))
        if not args.oracle_route and not args.sensor_only:
            mp.set_executable(str(ROOT/'.conda-model/python.exe'));worker=mp.get_context('spawn').Process(target=model_worker,args=(inq,outq,stop,str(resources[0]),str(resources[1]),seed,args.model_backend,args.ddim_steps,args.runtime_policy));worker.start()
        tracker=TrajectoryTracker(wheelbase,args.speed_cap,steer_angle);incumbent=None;version=(-1,-1);last_frame=-1;start=time.perf_counter();sim0=world.get_snapshot().timestamp.elapsed_seconds;previous_xy=None;progress=0.;previous_accel=0.;model_ready=False;previous_command=None
        previous_omega=None
        route_length=float(deployment.get('route_length_m',100));duration=args.duration if args.diagnostic_closed_loop else (6 if args.quick or args.mode=='smoke' else args.duration)
        for tick in range(math.ceil(duration/dt)):
            target=start+tick*dt
            if time.perf_counter()<target:time.sleep(target-time.perf_counter())
            snapshot=world.get_snapshot();sim=snapshot.timestamp.elapsed_seconds;transform=vehicle.get_transform();velocity=vehicle.get_velocity();accel=vehicle.get_acceleration();pose=[transform.location.x,transform.location.y,math.radians(transform.rotation.yaw)];pre_state=carla_state(vehicle)
            if radar_adapter:
                truth_history[snapshot.frame]={a.id:carla_state(snapshot.find(a.id)) for a in scenario_actors if snapshot.find(a.id) is not None}
                perception_truth.append({'frame':snapshot.frame,'sim_s':sim,'source':'OFFLINE_GROUND_TRUTH_EVALUATION_ONLY','actors':[{'actor_id':a.id,'type':a.type_id,'state':truth_history[snapshot.frame][a.id],'half_length_m':a.bounding_box.extent.x,'half_width_m':a.bounding_box.extent.y} for a in scenario_actors if a.id in truth_history[snapshot.frame]]})
                with sensor_lock:ready_packets=[p for p in radar_packets if p['frame']>last_radar_frame and p['capture_s']<=sim]
                for packet in sorted(ready_packets,key=lambda p:p['frame']):
                    latest_perception=radar_adapter.update(packet);last_radar_frame=packet['frame'];perception_records.append(latest_perception)
                    snapshot_at_sensor=world.get_snapshot()
                    for actor in scenario_actors:
                        truth=carla_state(actor);delay=sim-packet['capture_s'];tx,ty=truth['x_m'],-truth['y_m'];tracks=latest_perception['tracked_agents']
                        plausible=[a for a in tracks if math.hypot(a['x']+a['vx']*delay-tx,a['y']+a['vy']*delay-ty)<6]
                        match=min(plausible,key=lambda a:math.hypot(a['x']-tx,a['y']-ty)) if plausible else None
                        # Ground truth read only here for error evaluation; never adapter input.
                        capture_truth=truth_history.get(packet['frame'],{}).get(actor.id);truth_capture_exact=capture_truth is not None
                        perception_evaluation.append({'seed':seed,'observation_id':packet['frame'],'actor_id':actor.id,'matched':match is not None,'association':'nearest surface cluster within 6m; no identity labels supplied to tracker','truth_time_s':sim,'capture_s':packet['capture_s'],'delay_s':delay,'truth_capture_exact':truth_capture_exact,'position_error_m':math.hypot(match['x']-capture_truth['x_m'],match['y']+capture_truth['y_m']) if match and capture_truth else None,'velocity_error_mps':math.hypot(match['vx']-capture_truth['vx_mps'],match['vy']+capture_truth['vy_mps']) if match and capture_truth and match['velocity_status']=='ESTIMATED' else None,'acceleration_error_mps2':math.hypot(match['ax']-capture_truth['ax_mps2'],match['ay']+capture_truth['ay_mps2']) if match and capture_truth and match['acceleration_status']=='ESTIMATED' else None,'delay_state_error_m':math.hypot(match['x']+match['vx']*delay-tx,match['y']+match['vy']*delay-ty) if match else None,'occluded':bool(args.probe_occlusion),'occlusion_reliability':'prescribed aligned van occluder, ray coverage not certified' if args.probe_occlusion else 'unoccluded single-actor probe','truth_source':'CARLA_GROUND_TRUTH_EVALUATION_ONLY'})
            omega=math.radians(vehicle.get_angular_velocity().z);alpha=0. if previous_omega is None else (omega-previous_omega)/dt;previous_omega=omega
            rs=reference_state(pre_state,reference_offset,omega,alpha)
            command=deployment.get('navigation_command',[0,1,0,0]);h={'capture_s':sim,'x':rs['x_m'],'y':-rs['y_m'],'yaw':-pose[2],'vx':rs['vx_mps'],'vy':-rs['vy_mps'],'ax':rs['ax_mps2'],'ay':-rs['ay_mps2'],'command':command};history.append(h)
            with sensor_lock:available=[r for r in images.values() if r['capture_s']<=sim]
            latest=max(available,key=lambda r:r['frame']) if available else None
            if not args.oracle_route and not args.sensor_only and latest and latest['frame']>last_frame and len(history)>=31:
                selected=[]
                for i in (3,2,1,0):selected.append(min(history,key=lambda r:abs(r['capture_s']-(latest['capture_s']-i*.5))))
                if max(abs(r['capture_s']-(latest['capture_s']-(3-i)*.5)) for i,r in enumerate(selected))<=dt*1.1:
                    record={**latest,'ego_history':local_history(selected,selected[-1]),'coordinate_frame':'ego_local_xy_heading_radians','origin':[selected[-1]['x'],selected[-1]['y'],selected[-1]['yaw']],'relative_capture_tick':int(round((latest['capture_s']-sim0)/dt)),'episode_seed':seed,'navigation_source':'prescribed straight scene intent, official index 1'}
                    record.update(reference_point=args.model_reference,reference_offset_x_m=reference_offset,reference_state_method='measured wheel world cm -> actor local m; rigid-body velocity and finite-difference angular acceleration')
                    aligned=[p for p in perception_records if abs(p['capture_s']-record['capture_s'])<1e-5]
                    record['perception']=dict(aligned[-1],observation_id=record['frame']) if aligned else {'observation_id':record['frame'],'capture_s':record['capture_s'],'source':'NO_ALIGNED_DEPLOYMENT_PERCEPTION','tracked_agents':[],'coverage_validated':False,'occlusion_state':'UNKNOWN'}
                    record['runtime_feedback']={k:action_runtime.incumbent[k] for k in ('version','capture','deadline')} if action_runtime.incumbent else None
                    try:inq.put_nowait(record);last_frame=latest['frame'];events.append({'kind':'observation_enqueued','frame':last_frame,'capture_sim_s':latest['capture_s'],'wall_ns':time.perf_counter_ns()})
                    except queue.Full:
                        try:
                            dropped=inq.get_nowait();inq.put_nowait(record);last_frame=latest['frame'];events.append({'kind':'superseded_queued_observation','frame':dropped['frame'],'replacement':last_frame})
                        except (queue.Empty,queue.Full):events.append({'kind':'observation_queue_race','frame':latest['frame']})
            while True:
                try:msg=outq.get_nowait()
                except queue.Empty:break
                if msg['kind']=='worker_failure':raise RuntimeError(msg['traceback'])
                if msg['kind']=='ready':model_ready=True;events.append(msg);continue
                candidate=msg['result'];record=msg['record'];candidate_version=(record['frame'],len(candidate['clean_candidates']));age=sim-record['capture_s']
                atomic_json(output/('candidate_'+str(record['frame'])+'.json'),msg)
                # Lease comes from externally validated deployment policy, never actor ground truth.
                validation_start_ns=time.perf_counter_ns();lease=float(deployment.get('validated_max_age_s',0.));accepted=candidate['validation']['valid'] and candidate_version>version and 0<=age and age+dt<lease;validation_end_ns=time.perf_counter_ns();commit_ns=time.perf_counter_ns()
                online_result=None
                if args.online_avl:
                    from stage02_real_vla import candidate_validity
                    if 'validity' not in candidate:raise RuntimeError('Online runtime requires worker-supplied complete-plan validity')
                    candidate['schedule_steps']=candidate.get('schedule_steps',len(candidate['clean_candidates']))
                    online_result=action_runtime.commit(candidate,record['perception'],record['origin'],{'pose':[pose[0],-pose[1],-pose[2]],'radius_m':math.hypot(vehicle.bounding_box.extent.x,vehicle.bounding_box.extent.y)},sim,deployment.get('online_bounds'))
                    accepted=online_result['accepted'] and candidate_version>version;lease=(online_result['lease']['expiration_s']-record['capture_s']) if online_result.get('lease') else 0.
                    events.append({'kind':'online_avl','frame':record['frame'],'time_s':sim,**online_result})
                events.append({'kind':'commit' if accepted else 'reject','frame':record['frame'],'application_sim_s':sim,'source_capture_sim_s':record['capture_s'],'model_wall_ms':candidate['wall_ms'],'worker_start_ns':msg['start_ns'],'worker_end_ns':msg['end_ns'],'validation_start_ns':validation_start_ns,'validation_end_ns':validation_end_ns,'commit_wall_ns':commit_ns,'validation':candidate['validation'],'age_s':age,'reason':'kinematic_version_experimental_ttl' if accepted and args.diagnostic_closed_loop else ('validated_version_and_age' if accepted else 'invalid_stale_or_expired')})
                if accepted:incumbent={'trajectory':candidate['trajectory'],'origin':record['origin'],'capture':record['capture_s'],'deadline':record['capture_s']+lease,'observation_id':record['frame'],'commit_ns':commit_ns,'first_apply_ns':None};version=candidate_version
            if args.oracle_route and (tick==0 or tick%4==0):
                origin=[pose[0],-pose[1],-pose[2]]
                try:trajectory=oracle_route_candidate(route,origin,args.speed_cap)
                except ValueError:
                    events.append({'kind':'oracle_route_horizon_exhausted','tick':tick,'sim_s':sim});break
                incumbent={'trajectory':trajectory,'origin':origin,'capture':sim,'deadline':sim+1.,'observation_id':snapshot.frame,'commit_ns':time.perf_counter_ns(),'first_apply_ns':None}
                events.append({'kind':'oracle_commit','source':'D4_ORACLE_ROUTE_DIAGNOSTIC','frame':snapshot.frame,'application_sim_s':sim,'trajectory':trajectory,'origin':origin})
            fallback=incumbent is None or sim+dt>=incumbent['deadline']
            model_pose=[rs['x_m'],-rs['y_m'],-pose[2]]
            c={'throttle':0.,'brake':1.,'steer':0.} if fallback or args.stationary_interface else tracker.control(incumbent['trajectory'],incumbent['origin'],model_pose,math.hypot(rs['vx_mps'],rs['vy_mps']),sim-incumbent['capture'],math.cos(pose[2])*rs['ax_mps2']+math.sin(pose[2])*rs['ay_mps2'])
            command_ns=time.perf_counter_ns();vehicle.apply_control(carla.VehicleControl(throttle=c['throttle'],brake=c['brake'],steer=-c['steer']));control_scenario(sim-sim0);frame=world.tick();actual=vehicle.get_control();location=vehicle.get_location()
            if incumbent and not fallback and incumbent['first_apply_ns'] is None:incumbent['first_apply_ns']=command_ns
            post_state=carla_state(vehicle);post_sim=world.get_snapshot().timestamp.elapsed_seconds
            current_xy=(float(location.x),float(location.y))
            if previous_xy is not None:progress+=math.hypot(current_xy[0]-previous_xy[0],current_xy[1]-previous_xy[1])
            previous_xy=current_xy
            ticks.append({'tick':tick,'frame':frame,'pre_frame':snapshot.frame,'sim_s':sim,'post_sim_s':post_sim,'wall_ns':time.perf_counter_ns(),'command_ns':command_ns,'control_verified_frame':frame,'fallback':fallback,'stationary_interface':args.stationary_interface,'active_observation_id':None if incumbent is None else incumbent['observation_id'],'action_age_s':None if fallback else sim-incumbent['capture'],'active_deadline_s':None if incumbent is None else incumbent['deadline'],'first_apply_delay_s':None if fallback else (incumbent['first_apply_ns']-incumbent['commit_ns'])/1e9,'x_m':location.x,'y_m':location.y,'speed_mps':post_state['speed_mps'],'acceleration_mps2':post_state['acceleration_mps2'],'jerk_mps3':(post_state['acceleration_mps2']-previous_accel)/dt,'throttle':actual.throttle,'brake':actual.brake,'steer':actual.steer,'previous_command':previous_command,'tracker':c,'pre_state':pre_state,'model_reference_state':rs,'post_state':post_state,'evaluation_context':evaluation_context(world,vehicle)});previous_accel=post_state['acceleration_mps2'];previous_command={'throttle':actual.throttle,'brake':actual.brake,'steer':actual.steer}
            if tick%20==0:atomic_json(output/'partial.json',{'status':'RUNNING','ticks':ticks,'events':events,'collisions':collisions,'lane_invasions':lane_invasions})
        elapsed=time.perf_counter()-start;sim_elapsed=world.get_snapshot().timestamp.elapsed_seconds-sim0
        # Stop owned callback producers before freezing the completed raw artifact.
        for sensor in (camera,collision_sensor,lane_sensor):sensor.stop()
        if radar_adapter:radar.stop()
        time.sleep(.1)
        commits=[e for e in events if e['kind']=='commit']
        recomputed_progress=sum(math.hypot(b['x_m']-a['x_m'],b['y_m']-a['y_m']) for a,b in zip(ticks,ticks[1:]))
        if abs(progress-recomputed_progress)>1e-9:raise AssertionError('Progress does not match recorded planar displacement')
        atomic_json(output/'final_events.json',{'ticks':ticks,'events':events,'collisions':collisions,'lane_invasions':lane_invasions,'real_time_factor':sim_elapsed/elapsed,'model_ready':model_ready,'commit_count':len(commits),'progress_recomputed_m':recomputed_progress})
        active=[t for t in ticks if not t['fallback']];road=[t['evaluation_context']['road'] for t in ticks if t['evaluation_context']['road']]
        footprint_margin=[r['center_to_boundary_m']-vehicle.bounding_box.extent.y*abs(math.cos(r['heading_error_rad']))-vehicle.bounding_box.extent.x*abs(math.sin(r['heading_error_rad'])) for r in road]
        control_acceptance={'scope':'diagnostic_basic_straight_only' if args.basic_straight else 'diagnostic_unqualified_scene','collision_callbacks':len(collisions),'lane_invasion_callbacks':len(lane_invasions),'footprint_lane_margin_min_m':min(footprint_margin,default=None),'footprint_outside_nearest_lane_ticks':sum(m<0 for m in footprint_margin),'moving_ticks':sum(t['speed_mps']>.1 for t in ticks),'total_ticks':len(ticks),'progress_m':progress,'cross_track_abs_p95_m':quantile([abs(t['tracker'].get('cross_track_error_m',0)) for t in active],.95),'heading_abs_p95_rad':quantile([abs(t['tracker'].get('heading_error_rad',0)) for t in active],.95),'speed_abs_error_p95_mps':quantile([abs(t['tracker'].get('speed_error_mps',0)) for t in active],.95),'command_saturation_fraction':statistics.mean(t['tracker'].get('command_saturation',False) for t in active) if active else None,'measured_first_apply_delay_p95_s':quantile([t['first_apply_delay_s'] for t in active],.95),'basic_motion_pass':bool(not args.stationary_interface and progress>5 and not collisions and not lane_invasions and footprint_margin and min(footprint_margin)>=0),'formal_safety_acceptance':False}
        atomic_json(output/'control_acceptance.json',control_acceptance)
        if radar_adapter:
            atomic_json(output/'radar_raw.json',radar_packets);atomic_json(output/'perception_tracks.json',perception_records);atomic_json(output/'perception_evaluation.json',perception_evaluation);atomic_json(output/'perception_truth.json',perception_truth)
        attribution=audit_episode(output,output/'collision_audit')
        if not model_ready and not args.oracle_route and not args.sensor_only:raise RuntimeError('Real-VLA worker never became ready')
        if not commits and not args.online_avl and not args.oracle_route and not args.sensor_only:raise RuntimeError('No actual real-VLA candidate reached applied control; closed-loop acceptance failed')
        if args.online_avl and not any(e['kind']=='online_avl' for e in events):raise RuntimeError('No actual candidate reached online lease admission')
        if sensor_errors:raise RuntimeError('Sensor errors '+repr(sensor_errors))
        return {'status':'PARTIAL','evidence':diagnostic_evidence_type(args.oracle_route,args.sensor_only),'scenario':scenario,'seed':seed,'ticks':ticks,'events':events,'collisions':collisions,'metrics':{'progress_m':progress,'route_completion':'NOT_AVAILABLE_DISTANCE_IS_NOT_ROUTE_SCORE','driving_score':'NOT_AVAILABLE_OFFICIAL_EVALUATOR_REQUIRED','collision_callback_count':len(collisions),'collision_events':attribution['unique_collision_events'],'collision_episode':bool(collisions),'fallback_rate':statistics.mean(t['fallback'] for t in ticks),'sensor_to_action_age_p95_s':quantile([t['action_age_s'] for t in ticks if t['action_age_s'] is not None],.95),'real_time_factor':sim_elapsed/elapsed,'acceleration_rms':math.sqrt(statistics.mean(t['acceleration_mps2']**2 for t in ticks))},'limitations':['Online AVL rejects unvalidated perception/road coverage; positive deployment acceptance absent' if args.online_avl else 'Fixed diagnostic age cap; not online safety AVL','Actual benchmark evaluator/route score not installed','Model distribution/calibration may differ from CARLA','Stationary interface mode is never driving acceptance' if args.stationary_interface else 'Low-speed controller cap declared in configuration']}
    except BaseException as e:primary=e;raise
    finally:
        stop.set()
        if radar_adapter and primary is not None:
            atomic_json(output/'radar_raw_partial.json',radar_packets);atomic_json(output/'perception_tracks_partial.json',perception_records);atomic_json(output/'perception_evaluation_partial.json',perception_evaluation)
        if worker:
            worker.join(timeout=3)
            if worker.is_alive():worker.terminate();worker.join(timeout=3)
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception as e:cleanup.append(repr(e))
        if world and original:
            try:world.apply_settings(original)
            except Exception as e:cleanup.append(repr(e))
        if server and server.poll() is None:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
        if 'log' in locals():log.close()
        atomic_json(output/'cleanup.json',{'errors':cleanup,'primary_error':repr(primary) if primary else None,'finished':now()})
        if cleanup and primary is None:raise RuntimeError('Cleanup failed '+repr(cleanup))


def collect_sensor_input(args,run):
    """Owned CARLA recording, no model or claimed VLA closed loop.
    Coordinate adapter: CARLA left-handed XY -> right-handed x,-y,-yaw.
    Ego truth is explicitly the localization signal required by official input; no actor truth input.
    """
    import carla
    dt=.05;root=run.path/'raw/sensor_recording';root.mkdir(parents=True)
    exe=args.carla_path/'CarlaUE4/Binaries/Win64/CarlaUE4-Win64-Shipping.exe'
    if not exe.is_file():raise DependencyError('CARLA executable missing')
    for port in (args.port,args.port+1,args.port+2):
        with socket.socket() as s:s.bind(('127.0.0.1',port))
    server=None;world=None;settings0=None;owned=[];camera=None;errors=[];samples=[];states={};guard=threading.Lock();events=[];primary=None
    try:
        logfile=(root/'server.log').open('wb');startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        command=[str(exe),'CarlaUE4','/Game/Carla/Maps/'+args.carla_map,'-RenderOffScreen','-nosound','-quality-level=Low','-unattended','-NoCrashDialog','-carla-rpc-port='+str(args.port)]
        server=subprocess.Popen(command,cwd=args.carla_path,stdout=logfile,stderr=logfile,startupinfo=startup,creationflags=subprocess.CREATE_NO_WINDOW)
        for attempt in range(20):
            if server.poll() is not None:raise RuntimeError('Owned recording server exited')
            time.sleep(1);client=carla.Client('127.0.0.1',args.port);client.set_timeout(3)
            try:world=client.get_world();break
            except RuntimeError as e:events.append({'kind':'startup_retry','attempt':attempt,'error':str(e)})
        if world is None:raise RuntimeError('CARLA recorder startup timeout')
        client.set_timeout(20)
        if client.get_server_version()!='0.9.15':raise RuntimeError('CARLA 0.9.15 required')
        settings0=world.get_settings();settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=dt;settings.substepping=True;settings.max_substeps=5;settings.max_substep_delta_time=.01;world.apply_settings(settings)
        lib=world.get_blueprint_library();bp=lib.find('vehicle.tesla.model3');bp.set_attribute('role_name','framelease_owned_input_recorder');vehicle=None
        for index,spawn in enumerate(world.get_map().get_spawn_points()[:20]):
            candidate=world.try_spawn_actor(bp,spawn)
            if candidate:vehicle=candidate;break
        if vehicle is None:raise RuntimeError('No owned recording vehicle spawn')
        owned.append(vehicle);cbp=lib.find('sensor.camera.rgb')
        camera_config={'width':640,'height':360,'fov_deg':90,'sensor_tick_s':dt,'location_m':{'x':1.5,'y':0,'z':2.4},'rotation_deg':{'pitch':0,'yaw':0,'roll':0}}
        for key,value in {'image_size_x':640,'image_size_y':360,'fov':90,'sensor_tick':dt}.items():cbp.set_attribute(key,str(value))
        camera=world.spawn_actor(cbp,carla.Transform(carla.Location(x=1.5,z=2.4)),attach_to=vehicle);owned.append(camera)
        def callback(image):
            try:
                path=root/('rgb_%06d.png'%image.frame);image.save_to_disk(str(path))
                record={'frame':image.frame,'capture_s':image.timestamp,'receive_monotonic_ns':time.perf_counter_ns(),'image_path':str(path.resolve()),'image_sha256':file_hash(path),'width':image.width,'height':image.height}
                with guard:samples.append(record)
            except BaseException as e:errors.append(repr(e))
        camera.listen(callback);start=time.perf_counter();sim0=world.get_snapshot().timestamp.elapsed_seconds;ticks=[]
        for tick in range(150):
            due=start+tick*dt
            if time.perf_counter()<due:time.sleep(due-time.perf_counter())
            # Prescribed recorder motion only, openly identified; no learned control.
            vehicle.apply_control(carla.VehicleControl(throttle=.22 if tick<100 else 0,brake=.8 if tick>=100 else 0))
            frame=world.tick();snap=world.get_snapshot();transform=vehicle.get_transform();v=vehicle.get_velocity();a=vehicle.get_acceleration()
            state={'frame':frame,'capture_s':snap.timestamp.elapsed_seconds,'x':transform.location.x,'y':-transform.location.y,'yaw':-math.radians(transform.rotation.yaw),'vx':v.x,'vy':-v.y,'ax':a.x,'ay':-a.y,'command':[0,1,0,0]}
            states[frame]=state;ticks.append({'frame':frame,'sim_s':state['capture_s'],'wall_ns':time.perf_counter_ns(),'speed_mps':v.length(),'control_source':'prescribed_input_recorder','x_m':state['x'],'y_m':state['y']})
        elapsed=time.perf_counter()-start;sim_elapsed=world.get_snapshot().timestamp.elapsed_seconds-sim0
        camera.stop();time.sleep(.2)
        if errors:raise RuntimeError('Recorder sensor errors '+repr(errors))
        records=[]
        with guard:ordered=sorted(samples,key=lambda r:r['frame'])
        for image in ordered:
            f=image['frame'];required=[f-30,f-20,f-10,f]
            if f%10 or not all(i in states for i in required):continue
            hist=[states[i] for i in required]
            if abs(hist[-1]['capture_s']-image['capture_s'])>1e-5:raise RuntimeError('Sensor/world timestamp mismatch')
            records.append({**image,'ego_history':local_history(hist,hist[-1]),'coordinate_frame':'ego_local_xy_heading_radians','ego_state_source':'CARLA localization truth explicitly required model ego input; no actor truth','navigation_command_source':'prescribed straight recorder route, not an inferred traffic signal'})
        if len(records)<5:raise RuntimeError('Insufficient complete timestamped recording samples')
        dataset={'schema':1,'fabricated':False,'source_type':'CARLA_SENSOR_RECORDING','source':{'map':world.get_map().name,'client_version':client.get_client_version(),'server_version':client.get_server_version(),'owned_server_pid':server.pid,'spawn_index':index,'camera':camera_config,'coordinate_conversion':'CARLA x,y,yaw -> x,-y,-yaw; local history around current ego','official_training_calibration_equivalent':False,'domain':'CARLA simulated sensor data, not real-road log','control':'prescribed recorder throttle/brake, no VLA'},'records':records}
        manifest=root/'input_manifest.json';atomic_json(manifest,dataset);atomic_json(root/'raw_sensor_timestamps.json',ordered);atomic_json(root/'ego_states.json',list(states.values()));write_csv(root/'ticks.csv',ticks)
        summary={'status':'COMPLETED','scope':'INPUT_INFRASTRUCTURE_ONLY','ticks':len(ticks),'rgb_frames':len(ordered),'complete_input_records':len(records),'real_time_factor':sim_elapsed/elapsed,'manifest':str(manifest.resolve()),'manifest_sha256':file_hash(manifest),'closed_loop_vla':False,'calibration_equivalence_verified':False}
        atomic_json(root/'summary.json',summary);return summary
    except BaseException as e:primary=e;raise
    finally:
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop') and actor.is_listening:actor.stop()
                actor.destroy()
            except BaseException as e:errors.append('cleanup '+repr(e))
        if world is not None and settings0 is not None:
            try:world.apply_settings(settings0)
            except BaseException as e:errors.append('restore '+repr(e))
        if server and server.poll() is None:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
        if 'logfile' in locals():logfile.close()
        atomic_json(root/'cleanup.json',{'errors':errors,'primary_error':repr(primary) if primary else None,'finished':now()})
        if errors and primary is None:raise RuntimeError('Recorder cleanup/sensor errors: '+repr(errors))

def run_experiment(args):
    if args.mode=='linux-infrastructure':return run_linux_infrastructure(args)
    if args.mode=='native-benchmark':return run_native_benchmark(args)
    if args.mode=='native-geometry':return run_native_geometry(args)
    if args.mode=='native-forensics-analysis':return run_native_forensics_analysis(args)
    if args.mode=='native-observe':return run_native_observer(args)
    if args.mode=='flow-road-analysis':return run_flow_road_analysis(args)
    if args.mode=='native-preflight':return run_native_preflight(args)
    if args.mode=='road-audit':
        if not args.audit_episode or not args.route_geometry:raise ValueError('--audit-episode and --route-geometry required')
        if dry_plan(args,[{'source':str(args.audit_episode),'route':str(args.route_geometry),'D2_D3':True}]):return 0
        route=read_json(args.route_geometry);geom=read_json(args.audit_episode/'vehicle_and_map.json')
        if args.geometry_reference:geom=read_json(args.geometry_reference)
        has_model_candidates=any(args.audit_episode.glob('candidate_*.json'));source_events=read_json(args.audit_episode/'final_events.json')['events']
        evidence=['REAL_VLA','CARLA_CLOSED_LOOP'] if has_model_candidates else ['CARLA_ORACLE_DIAGNOSTIC'] if any(e['kind']=='oracle_commit' for e in source_events) else ['CARLA_SENSOR_DIAGNOSTIC']
        run=StageRun('stage05_carla_closed_loop',args,{'mode':'road-audit','source':str(args.audit_episode),'source_sha256':file_hash(args.audit_episode/'final_events.json'),'route_sha256':file_hash(args.route_geometry),'vehicle_geometry':geom},evidence)
        result=audit_road_candidates(args.audit_episode,route,geom,run.path/'metrics');run.record({'kind':'D2_D3_route_diagnostic'},result)
        return run.finish('PARTIAL',canonical(result),acceptance='PARTIAL')
    if args.mode=='audit':
        if not args.audit_episode:raise ValueError('--audit-episode required')
        if dry_plan(args,[{'source':str(args.audit_episode),'operation':'saved_collision_attribution'}]):return 0
        run=StageRun('stage05_carla_closed_loop',args,{'mode':'audit','source':str(args.audit_episode),'source_sha256':file_hash(args.audit_episode/'final_events.json')},['CARLA_CLOSED_LOOP'])
        result=audit_episode(args.audit_episode,run.path/'metrics');run.record({'kind':'collision_attribution'},result)
        return run.finish('PARTIAL',(run.path/'metrics/Collision_Root_Cause_Report.md').read_text(encoding='utf8'),acceptance='PARTIAL')
    scenarios=['straight'] if args.mode=='smoke' else list(SCENARIOS)
    planned=[{'scope':'INPUT_INFRASTRUCTURE_ONLY','ticks':150,'dt_s':.05,'model_execution':False}] if args.collect_input else [{'scenario':s,'seed':args.seed,'backend':'real ReCogDrive + CARLA 0.9.15'} for s in scenarios]
    if dry_plan(args,planned):return 0
    run=StageRun('stage05_carla_closed_loop',args,{'mode':args.mode,'collect_input':args.collect_input,'diagnostic_closed_loop':args.diagnostic_closed_loop,'stationary_interface':args.stationary_interface,'oracle_route':args.oracle_route,'sensor_only':args.sensor_only,'model_reference':args.model_reference,'basic_straight':args.basic_straight,'radar_perception':args.radar_perception,'perception_probe':args.perception_probe,'probe_occlusion':args.probe_occlusion,'online_avl':args.online_avl,'runtime_policy':args.runtime_policy,'ddim_steps':args.ddim_steps,'speed_cap_mps':args.speed_cap,'spawn_index':args.spawn_index,'experimental_age_cap_s':args.diagnostic_age_cap,'model_backend':args.model_backend,'scenarios':scenarios,'duration_s':args.duration,'map':args.carla_map,'deployment':str(args.deployment_config),'deployment_sha256':file_hash(args.deployment_config) if args.deployment_config.is_file() else None},[],[ROOT/'stage02_real_vla.py',ROOT/'stage03_avl_validation.py',ROOT/'stage04_gpu_runtime.py'])
    try:
        if args.collect_input:
            with writer_lock(ROOT/'results/shared_gpu_resource'):summary=collect_sensor_input(args,run)
            run.record({'kind':'actual_sensor_input_recording'},summary)
            return run.finish('PARTIAL','# CARLA input infrastructure recording\n\n'+canonical(summary)+'\n\nActual camera frames and synchronized four-state ego history saved. No VLA inference, no real-road log, no closed-loop driving score. Camera/domain equivalence to official training input is unvalidated.',acceptance='PARTIAL')
        blockers,resources,deployment,client=prerequisites(args);run.record({'kind':'dependency_audit'},{'blockers':blockers,'carla_client':client})
        if blockers:return run.finish('BLOCKED','# Stage05 real VLA + CARLA\n\n'+'\n'.join('- '+b for b in blockers)+'\n\nIndependent tick owner, real Conda model worker, timestamped camera/history, tracker, commits, expiry fallback and owned cleanup implemented. Runtime path unvalidated because prerequisites are missing. Historical 140-tick infrastructure diagnostic remains separate; no driving score or closed-loop result claimed.',blockers)
        results=[]
        with writer_lock(ROOT/'results/shared_gpu_resource'):
            for scenario in scenarios:
                task={'scenario':scenario,'seed':args.seed,'diagnostic':'D4_ORACLE_ROUTE_DIAGNOSTIC' if args.oracle_route else 'D1_REAL_VLA'}
                try:
                    result=run_episode(args,resources,deployment,scenario,args.seed,run.path/'raw'/scenario);result['scope']='SENSOR_ONLY_DIAGNOSTIC' if args.sensor_only else 'D4_ORACLE_ROUTE_DIAGNOSTIC' if args.oracle_route else ('ONLINE_AVL_DEPLOYMENT_GATE_DIAGNOSTIC' if args.online_avl else ('DIAGNOSTIC_WITH_UNVALIDATED_EXPERIMENTAL_TTL' if args.diagnostic_closed_loop else 'DEPLOYMENT'));result['experimental_age_cap_s']=args.diagnostic_age_cap;run.state['evidence_type']=['CARLA_SENSOR_DIAGNOSTIC'] if args.sensor_only else ['CARLA_ORACLE_DIAGNOSTIC'] if args.oracle_route else ['CARLA_CLOSED_LOOP','REAL_VLA'];run.record(task,result);results.append(result)
                except Exception as e:run.record(task,{},'FAILED',repr(e));run.log('scenario_failure',scenario=scenario,traceback=traceback.format_exc())
        write_csv(run.path/'metrics/episodes.csv',[{'scenario':r['scenario'],**r['metrics']} for r in results])
        reasons=[t['reason'] for t in run.state['tasks'] if t['status']=='FAILED']
        return run.finish('PARTIAL' if results else 'FAILED','Actual executed closed-loop subset; official route evaluation and live action-conditioned perception/scheduler acceptance remain incomplete. Diagnostic mode uses an unvalidated experimental TTL, not calibrated AVL. Failed attempts: '+canonical(reasons),reasons,acceptance='PARTIAL' if results else 'FAILED')
    except BaseException:run.log('failure',traceback=traceback.format_exc());return run.finish('FAILED',traceback.format_exc())
def run_native_preflight(args):
    """Execute the original evaluator import chain; never launch the old ReCog agent."""
    from stage02_real_vla import UNIDRIVE_REPO,UNIDRIVE_COMMIT,UNIDRIVE_AGENT,UNIDRIVE_CONFIG,native_probe,unidrive_source_audit
    if dry_plan(args,[{'backend':'UniDriveVLA','agent_kind':'OFFICIAL_NATIVE_AGENT','operation':'original evaluator CLI and platform preflight'}]):return 0
    b2d=UNIDRIVE_REPO/'Bench2Drive';evaluator=b2d/'bench2drive/leaderboard/leaderboard/leaderboard_evaluator.py'
    run=StageRun('stage05_carla_closed_loop',args,{'mode':args.mode,'backend':'UniDriveVLA','source_commit':UNIDRIVE_COMMIT,'agent_kind':'OFFICIAL_NATIVE_AGENT','evaluator_sha256':file_hash(evaluator)},['NATIVE_EVALUATOR_PROBE'],[evaluator,UNIDRIVE_REPO/UNIDRIVE_AGENT,UNIDRIVE_REPO/UNIDRIVE_CONFIG])
    try:
        import ast,xml.etree.ElementTree as ET
        contract=unidrive_source_audit();env=os.environ.copy();env['PYTHONPATH']=os.pathsep.join(str(p) for p in (b2d,b2d/'bench2drive',b2d/'bench2drive/leaderboard',b2d/'bench2drive/scenario_runner',args.carla_path/'PythonAPI/carla'))+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
        env.update(CARLA_ROOT=str(args.carla_path),IS_BENCH2DRIVE='1',PLANNER_TYPE='traj',IS_VISUALIZE='0')
        probe=native_probe(run,'official_evaluator_help',[sys.executable,evaluator,'--help'],b2d,env)
        tree=ast.parse(evaluator.read_text('utf8'));platform_calls=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id in ('os','signal') and n.attr in ('setsid','killpg','SIGKILL'):
                mod=__import__(n.value.id)
                try:getattr(mod,n.attr);error=None
                except AttributeError as e:error=repr(e)
                platform_calls.append({'line':n.lineno,'api':ast.unparse(n),'available':error is None,'error':error})
        routes=[]
        for f in sorted((b2d/'bench2drive/leaderboard/data').rglob('*.xml')):
            doc=ET.parse(f);rs=doc.getroot().findall('route')
            routes.append({'path':str(f),'sha256':file_hash(f),'route_count':len(rs),'towns':sorted(set(r.get('town','') for r in rs))})
        blockers=[]
        if probe['returncode']!=0:blockers.append('Original evaluator import/CLI failed; retained exact stderr')
        if any(not x['available'] for x in platform_calls):blockers.append('Official evaluator needs unavailable POSIX process lifecycle APIs; Windows port is not native equivalence')
        if not (args.carla_path/'CarlaUE4.sh').is_file():blockers.append('Official CarlaUE4.sh server executable absent')
        prior=ROOT/('outputs/linux_stage02_unidrive_audit/manifest.json' if sys.platform.startswith('linux') else 'outputs/stage02_unidrive_audit/manifest.json')
        if prior.exists():
            m=verified_manifest(prior);blockers+=m['blockers']
        else:blockers.append('Native model readiness audit missing')
        result={'backend':'UniDriveVLA','agent_kind':'OFFICIAL_NATIVE_AGENT','model_source_commit':UNIDRIVE_COMMIT,'platform_calls':platform_calls,'routes':routes,'input_contract':contract['input'],'sensor_specs':contract['sensors'],'official_evaluator_started':False,'official_agent_instantiated':False,'closed_loop_passed':False,'driving_score':None,'progress_m':None,'framelease_integration_executed':False,'blockers':blockers}
        atomic_json(run.path/'metrics/native_preflight.json',result);run.record({'kind':'native_closed_loop_preflight'},result)
        return run.finish('BLOCKED' if blockers else 'PARTIAL',canonical(result),blockers,acceptance='BLOCKED')
    except BaseException:run.log('failure',traceback=traceback.format_exc());return run.finish('FAILED',traceback.format_exc())

def require_free_ports(ports):
    """Refuse to connect to an existing server owned by another experiment."""
    for port in ports:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',port))

def stop_owned_group(process):
    import signal
    try:os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:pass
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    process.wait(timeout=10)

def run_linux_infrastructure(args):
    if dry_plan(args,[{'operation':'Linux offscreen camera/control probe','model_execution':False}]):return 0
    run=StageRun('stage05_carla_closed_loop',args,{'mode':args.mode,'scope':'CARLA_INFRASTRUCTURE_ONLY','map':args.carla_map,'port':args.port,'ticks':80,'dt_s':.05,'quality':'Low'},['CARLA_SENSOR_DIAGNOSTIC'])
    process=None;world=None;settings=None;actors=[];cleanup=[];error=None;result={}
    with writer_lock(ROOT/'results/shared_gpu_resource'):
        try:
            import carla,numpy as np
            if not sys.platform.startswith('linux'):raise RuntimeError('Linux mode requires native Linux')
            require_free_ports([args.port,args.port+1,args.port+2])
            cmd=[str(args.carla_path/'CarlaUE4.sh'),'-RenderOffScreen','-nosound','-quality-level=Low','-stdout','-FullStdOutLogOutput',f'-carla-rpc-port={args.port}']
            with (run.path/'logs/carla.log').open('w') as log:
                process=subprocess.Popen(cmd,cwd=args.carla_path,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            run.log('server_started',pid=process.pid,command=cmd)
            client=carla.Client('127.0.0.1',args.port);client.set_timeout(2)
            deadline=time.monotonic()+120
            while True:
                if process.poll() is not None:raise RuntimeError('CARLA server exited: '+str(process.returncode))
                try:
                    # An RPC client created before the server listens can retain a
                    # failed connection. Reconnect on every bounded startup retry.
                    client=carla.Client('127.0.0.1',args.port);client.set_timeout(2)
                    world=client.get_world();run.log('rpc_ready',map=world.get_map().name);break
                except RuntimeError:
                    if time.monotonic()>deadline:raise
                    time.sleep(1)
            client.set_timeout(60);world=client.load_world(args.carla_map);run.log('map_loaded',map=world.get_map().name)
            settings=world.get_settings();sync=world.get_settings();sync.synchronous_mode=True;sync.fixed_delta_seconds=.05;world.apply_settings(sync)
            bp=world.get_blueprint_library();vehicle_bp=bp.find('vehicle.lincoln.mkz_2020');vehicle_bp.set_attribute('role_name','framelease_infrastructure')
            vehicle=world.spawn_actor(vehicle_bp,world.get_map().get_spawn_points()[0]);actors.append(vehicle)
            cam_bp=bp.find('sensor.camera.rgb');cam_bp.set_attribute('image_size_x','800');cam_bp.set_attribute('image_size_y','450');cam_bp.set_attribute('fov','70');cam_bp.set_attribute('sensor_tick','.05')
            camera=world.spawn_actor(cam_bp,carla.Transform(carla.Location(x=.8,z=1.6)),attach_to=vehicle);actors.append(camera)
            frames=queue.Queue();camera.listen(frames.put);rows=[];images=[]
            # Settle before measuring planar displacement, excluding spawn physics.
            for _ in range(20):world.tick()
            previous=vehicle.get_location();start=[previous.x,previous.y];distance=0.
            for i in range(80):
                control=carla.VehicleControl(throttle=.35 if i<50 else 0.,brake=0. if i<50 else 1.)
                applied=time.perf_counter_ns();vehicle.apply_control(control);frame=world.tick();snapshot=world.get_snapshot()
                image_deadline=time.monotonic()+15
                while True:
                    image=frames.get(timeout=max(.001,image_deadline-time.monotonic()))
                    if image.frame>=frame:break
                if image.frame!=frame:raise RuntimeError('Camera/world timestamp mismatch')
                loc=vehicle.get_location();vel=vehicle.get_velocity();distance+=math.hypot(loc.x-previous.x,loc.y-previous.y);previous=loc
                row={'frame':frame,'sim_s':snapshot.timestamp.elapsed_seconds,'image_sim_s':image.timestamp,'apply_wall_ns':applied,'receive_wall_ns':time.perf_counter_ns(),'x':loc.x,'y':loc.y,'speed_mps':math.sqrt(vel.x**2+vel.y**2+vel.z**2),'throttle':control.throttle,'brake':control.brake};rows.append(row)
                if i in (0,40,79):
                    dest=run.path/'raw'/f'camera_{frame}.png';image.save_to_disk(str(dest));images.append({'file':str(dest),'sha256':file_hash(dest),'pixel_std':float(np.frombuffer(image.raw_data,dtype=np.uint8).reshape(image.height,image.width,4)[:,:,:3].std())})
            write_csv(run.path/'raw/control_trace.csv',rows)
            result={'scope':'CARLA_INFRASTRUCTURE_ONLY','model_executed':False,'server_version':client.get_server_version(),'client_version':client.get_client_version(),'map':world.get_map().name,'available_maps':client.get_available_maps(),'ticks':len(rows),'camera_frames_matched':len(rows),'images':images,'distance_xy_m':distance,'net_displacement_m':math.hypot(previous.x-start[0],previous.y-start[1]),'peak_speed_mps':max(r['speed_mps'] for r in rows),'final_speed_mps':rows[-1]['speed_mps'],'official_driving_score':None}
            if result['server_version']!='0.9.15' or result['client_version']!='0.9.15':raise RuntimeError('CARLA version mismatch')
            if distance<1 or result['final_speed_mps']>.2 or any(x['pixel_std']<1 for x in images):raise RuntimeError('Infrastructure movement/brake/image check failed')
        except BaseException:error=traceback.format_exc();run.log('failure',traceback=error)
        finally:
            for actor in reversed(actors):
                try:
                    if hasattr(actor,'stop'):actor.stop()
                    if not actor.destroy():cleanup.append('Actor destroy returned false: '+str(actor.id))
                except Exception as e:cleanup.append(repr(e))
            if world is not None and settings is not None:
                try:world.apply_settings(settings)
                except Exception as e:cleanup.append(repr(e))
            if process is not None:
                try:stop_owned_group(process)
                except Exception as e:cleanup.append(repr(e))
            result['cleanup_errors']=cleanup;result['error']=error
            atomic_json(run.path/'metrics/infrastructure.json',result)
    ok=error is None and not cleanup
    run.record({'kind':'actual_linux_carla_infrastructure'},result,'COMPLETED' if ok else 'FAILED',error or str(cleanup))
    return run.finish('PARTIAL' if ok else 'FAILED',canonical(result),[] if ok else [error or str(cleanup)],acceptance='PARTIAL' if ok else 'FAILED')

def native_evaluator_owned_cleanup(source):
    """Only narrow the upstream crash cleanup; preserve evaluator/scoring behavior."""
    old='''            cmd2 = "ps -ef | grep '-graphicsadapter="+ str(args.gpu_rank) + "' | grep -v grep | awk '{print $2}' | xargs -r kill -9"
            server = subprocess.Popen(cmd2, shell=True, preexec_fn=os.setsid)
            atexit.register(os.killpg, server.pid, signal.SIGKILL)'''
    if source.count(old)!=1:raise ValueError('Official evaluator cleanup source changed')
    return source.replace(old,'''            try:
                os.killpg(self.server.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass''')

def run_native_geometry(args):
    """Evaluate immutable recorded poses against CARLA map geometry, never drive."""
    if args.native_source is None:raise ValueError('--native-source is required')
    source=args.native_source.resolve();manifest=verified_manifest(source/'manifest.json')
    if manifest['identity']['config'].get('backend')!='UniDriveVLA':raise ValueError('Require recorded UniDrive source')
    if dry_plan(args,[{'operation':'recorded pose/map geometry diagnosis','source':str(source),'online_gt':False}]):return 0
    agent=source/'raw/agent';poses=read_json(agent/'metric_info.json')
    controls=[json.loads(x) for x in (agent/'control_trace.jsonl').read_text().splitlines()]
    if len(poses)!=len(controls):raise ValueError('Pose/control coverage mismatch')
    config={'mode':args.mode,'scope':'OFFLINE_MAP_GEOMETRY_ONLY_NOT_COLLISION_CAUSAL_PROOF','source_manifest':str(source/'manifest.json'),'source_sha256':file_hash(source/'manifest.json'),'map':args.carla_map,'lane_sampling_m':1.,'height_band_m':3.,'roi_padding_m':35.,'vehicle':'vehicle.lincoln.mkz_2020','pose_source':'saved native metric_info; no resimulated motion','model_executed':False}
    run=StageRun('stage05_carla_closed_loop',args,config,['CARLA_MAP_GEOMETRY_DIAGNOSTIC'],[agent/'metric_info.json',agent/'control_trace.jsonl'])
    process=None;vehicle=None;error=None;cleanup=[];result={}
    with writer_lock(ROOT/'results/shared_gpu_resource'):
        try:
            import carla,numpy as np
            from shapely.geometry import Polygon,Point,MultiPoint,mapping
            from shapely.ops import unary_union
            require_free_ports([args.port,args.port+1,args.port+2])
            cmd=[str(args.carla_path/'CarlaUE4.sh'),'-RenderOffScreen','-nosound','-quality-level=Low',f'-carla-rpc-port={args.port}']
            with (run.path/'logs/carla.log').open('w') as log:process=subprocess.Popen(cmd,cwd=args.carla_path,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            end=time.monotonic()+120
            while True:
                if process.poll() is not None:raise RuntimeError('Owned CARLA exited')
                try:
                    client=carla.Client('127.0.0.1',args.port);client.set_timeout(2);client.get_world();break
                except RuntimeError:
                    if time.monotonic()>end:raise
                    time.sleep(1)
            client.set_timeout(90);world=client.load_world(args.carla_map);road=world.get_map()
            first=poses[str(controls[0]['step'])];loc=first['location']
            vehicle=world.spawn_actor(world.get_blueprint_library().find(config['vehicle']),carla.Transform(carla.Location(x=loc[0],y=loc[1],z=loc[2]+4)))
            vehicle.set_simulate_physics(False);bbox=vehicle.bounding_box
            xyz=np.asarray([poses[str(c['step'])]['location'] for c in controls]);lo=xyz.min(0)-config['roi_padding_m'];hi=xyz.max(0)+config['roi_padding_m']
            polygons=[];segments=[]
            def edge(w):
                t=w.transform;r=t.get_right_vector();p=t.location;h=w.lane_width/2
                return [[p.x-r.x*h,p.y-r.y*h],[p.x+r.x*h,p.y+r.y*h]]
            for wp in road.generate_waypoints(1.):
                p=wp.transform.location
                if not (lo[0]<p.x<hi[0] and lo[1]<p.y<hi[1] and xyz[:,2].min()-3<p.z<xyz[:,2].max()+3):continue
                if wp.lane_type!=carla.LaneType.Driving:continue
                for other in wp.next(1.):
                    a,b=edge(wp),edge(other);poly=Polygon([a[0],a[1],b[1],b[0]])
                    if not poly.is_valid:poly=poly.buffer(0)
                    if not poly.is_empty:polygons.append(poly);segments.append({'road':wp.road_id,'lane':wp.lane_id,'junction':wp.is_junction,'polygon':mapping(poly)})
            if not polygons:raise ValueError('No map surface in recorded route ROI')
            sampling_domain={'xy_min':lo[:2].tolist(),'xy_max':hi[:2].tolist(),'z_min':float(xyz[:,2].min()-3),'z_max':float(xyz[:,2].max()+3),'interior_margin_m':2.,'outside_domain':'UNKNOWN_MAP_COVERAGE; never an off-road finding'}
            surface=unary_union(polygons);atomic_json(run.path/'raw/map_geometry.json',{'map':road.name,'opendrive_sha256':hashlib.sha256(road.to_opendrive().encode()).hexdigest(),'sampling_domain':sampling_domain,'surface':mapping(surface),'segments':segments,'bbox':{'location':[bbox.location.x,bbox.location.y,bbox.location.z],'extent':[bbox.extent.x,bbox.extent.y,bbox.extent.z]},'label':'approximate Driving lane union; junction/connectivity and 3D topology limits apply'})
            rows=[];footprints=[];previous=None
            for c in controls:
                p=poses[str(c['step'])];x,y,z=p['location'];roll,pitch,yaw=p['rotation']
                transform=carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(roll=roll,pitch=pitch,yaw=yaw))
                poly=MultiPoint([(v.x,v.y) for v in bbox.get_world_vertices(transform)]).convex_hull
                f=transform.get_forward_vector();r=transform.get_right_vector()
                # The two frames are labelled separately: official PID uses body
                # origin; LIDAR2EGO locates the learned frame 0.39m behind it.
                paths={}
                for name,offset in [('body_origin',0.),('lidar_origin',-.39)]:
                    paths[name]=[[x+f.x*(v+offset)+r.x*u,y+f.y*(v+offset)+r.y*u] for u,v in c['trajectory']]
                near=road.get_waypoint(transform.location,project_to_road=False,lane_type=carla.LaneType.Driving)
                dt=c['simulation_timestamp']-previous['simulation_timestamp'] if previous else None
                speed=math.dist([x,y],previous['xy'])/dt if previous and dt>0 else None
                rows.append({'step':c['step'],'sim_s':c['simulation_timestamp'],'x':x,'y':y,'yaw_deg':yaw,'speed_from_saved_pose_mps':speed,'throttle':c['throttle'],'brake':c['brake'],'steer':c['steer'],'command':c['command'],'body_area_m2':poly.area,'outside_approx_driving_area_m2':poly.difference(surface).area,'center_driving_point_query':near is not None,'first_body_candidate_outside_point':next((i for i,pt in enumerate(paths['body_origin']) if not surface.covers(Point(pt))),None),'first_lidar_candidate_outside_point':next((i for i,pt in enumerate(paths['lidar_origin']) if not surface.covers(Point(pt))),None)})
                footprints.append({'step':c['step'],'polygon':mapping(poly),'candidate_paths':paths});previous={'xy':[x,y],'simulation_timestamp':c['simulation_timestamp']}
            write_csv(run.path/'metrics/recorded_geometry.csv',rows);atomic_json(run.path/'raw/footprints.json',footprints)
            import matplotlib;matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            fig,axes=plt.subplots(1,2,figsize=(12,5))
            for ax in axes:
                for p in polygons:xs,ys=p.exterior.xy;ax.fill(xs,ys,color='#dddddd',linewidth=0)
                ax.plot(xyz[:,0],xyz[:,1],color='#075a9c',lw=1,label='Recorded ego origin')
                ax.set_aspect('equal');ax.set(xlabel='CARLA world X [m]',ylabel='CARLA world Y [m]')
            for index in range(0,len(rows),40):
                from shapely.geometry import shape
                poly=shape(footprints[index]['polygon']);xs,ys=poly.exterior.xy
                axes[0].plot(xs,ys,color='#b7352e' if rows[index]['outside_approx_driving_area_m2']>.1 else '#328753',lw=.6)
            pick=next((i for i,r in enumerate(rows) if r['sim_s']>=29.35),len(rows)-1);row=rows[pick]
            poly=shape(footprints[pick]['polygon']);xs,ys=poly.exterior.xy;axes[1].plot(xs,ys,color='#b7352e',lw=1.5,label='Recorded vehicle footprint')
            path=np.asarray(footprints[pick]['candidate_paths']['lidar_origin']);axes[1].plot(path[:,0],path[:,1],'o-',color='#b96a0b',ms=3,label='Predicted trajectory (lidar origin)')
            axes[0].set_xlim(xyz[:,0].min()-8,xyz[:,0].max()+8);axes[0].set_ylim(xyz[:,1].min()-8,xyz[:,1].max()+8)
            axes[1].set_xlim(row['x']-12,row['x']+12);axes[1].set_ylim(row['y']-12,row['y']+12);axes[1].legend(fontsize=7)
            axes[0].set_title('Saved native run / approximate road geometry');axes[1].set_title(f"Saved pose at {row['sim_s']:.2f}s; evaluation only")
            figure_save(fig,run.path/'figures/recorded_road_geometry');plt.close(fig)
            result={'scope':config['scope'],'recorded_pose_count':len(rows),'map_segments':len(segments),'max_outside_approx_area_m2':max(r['outside_approx_driving_area_m2'] for r in rows),'first_outside_gt_0p1m2':next((r for r in rows if r['outside_approx_driving_area_m2']>.1),None),'selected_stall_row':row,'last_row':rows[-1],'threshold_note':'0.1m2 descriptive event marker, not a safety acceptance threshold','collision_cause':'UNRESOLVED; map footprint overlap alone cannot identify contact object/physics','gate_promoted':False}
        except BaseException:error=traceback.format_exc();run.log('failure',traceback=error)
        finally:
            if vehicle is not None:
                try:vehicle.destroy()
                except Exception as e:cleanup.append(repr(e))
            if process is not None:
                try:stop_owned_group(process)
                except Exception as e:cleanup.append(repr(e))
    result.update(error=error,cleanup_errors=cleanup);atomic_json(run.path/'metrics/geometry_summary.json',result)
    run.record({'kind':'recorded_native_map_geometry'},result,'FAILED' if error or cleanup else 'COMPLETED',error)
    return run.finish('FAILED' if error or cleanup else 'PARTIAL',canonical(result),[error] if error else [],acceptance='BLOCKED')

def run_native_observer(args):
    """Read-only evaluation client: never tick, spawn, control or stop the server."""
    if args.native_source is None:raise ValueError('--native-source required for owned experiment identity')
    source=args.native_source.resolve();m=read_json(source/'manifest.json')
    if m['status']!='RUNNING' or m['identity']['config']['port']!=args.port:raise ValueError('Observer must match an active declared native run/port')
    if dry_plan(args,[{'operation':'read-only CARLA actor evaluation','source':str(source),'model_input':False}]):return 0
    run=StageRun('stage05_carla_closed_loop',args,{'mode':args.mode,'scope':'EVALUATION_GT_ONLY_NO_ONLINE_FEEDBACK','source_run':str(source),'source_identity':m['identity_sha256'],'port':args.port,'duration_s':args.duration,'actor_radius_m':60,'mutating_rpc_calls':False},['CARLA_EVALUATION_GROUND_TRUTH'])
    import carla
    client=carla.Client('127.0.0.1',args.port);client.set_timeout(3);rows=0;discarded=0;last=None;errors=[];start=time.monotonic()
    try:
        world=client.get_world()
        with (run.path/'raw/actor_frames.jsonl').open('w') as f:
            while time.monotonic()-start<args.duration:
                if read_json(source/'manifest.json')['status']!='RUNNING':break
                before=world.get_snapshot()
                if before.frame==last:time.sleep(.2);continue
                actors=world.get_actors();hero=next((a for a in actors if a.attributes.get('role_name')=='hero'),None)
                if hero is None:time.sleep(.2);continue
                h=hero.get_transform();location=h.location;objects=[]
                for a in actors:
                    if not (a.type_id.startswith('vehicle.') or a.type_id.startswith('walker.') or a.type_id.startswith('traffic.')):continue
                    tr=a.get_transform()
                    if tr.location.distance(location)>60:continue
                    vel=a.get_velocity();box=a.bounding_box
                    objects.append({'id':a.id,'type':a.type_id,'is_hero':a.id==hero.id,'location':[tr.location.x,tr.location.y,tr.location.z],'rotation':[tr.rotation.roll,tr.rotation.pitch,tr.rotation.yaw],'velocity':[vel.x,vel.y,vel.z],'bbox_local_center':[box.location.x,box.location.y,box.location.z],'bbox_extent':[box.extent.x,box.extent.y,box.extent.z],'world_vertices':[[v.x,v.y,v.z] for v in box.get_world_vertices(tr)]})
                after=world.get_snapshot()
                if before.frame!=after.frame:discarded+=1;continue
                row={'scope':'GROUND_TRUTH_EVALUATION_ONLY','frame':before.frame,'world_elapsed_s':before.timestamp.elapsed_seconds,'hero_id':hero.id,'objects':objects}
                f.write(canonical(row)+'\n');f.flush();rows+=1;last=before.frame
                time.sleep(.2)
    except BaseException:errors.append(traceback.format_exc())
    result={'source_run':str(source),'frames_recorded':rows,'inconsistent_frame_reads_discarded':discarded,'errors':errors,'mutated_world':False,'fed_policy':False,'wall_s':time.monotonic()-start,'scope':'Evaluation actor ground truth; availability does not establish perception recall/coverage'}
    run.record({'kind':'read_only_actor_observer'},result,'FAILED' if errors else 'COMPLETED',str(errors) if errors else None)
    return run.finish('FAILED' if errors else 'PARTIAL',canonical(result),errors,acceptance='BLOCKED')

def classify_map_point(surface,domain,point):
    """A clipped map cannot establish that an unobserved location is off-road."""
    from shapely.geometry import Point
    margin=domain['interior_margin_m']
    if any(not domain['xy_min'][i]+margin<=point[i]<=domain['xy_max'][i]-margin for i in (0,1)):
        return 'UNKNOWN_MAP_COVERAGE'
    return 'INSIDE_APPROX_SURFACE' if surface.covers(Point(point)) else 'OUTSIDE_APPROX_SURFACE'

def run_flow_road_analysis(args):
    """Saved real clean candidates -> descriptive map diagnostics; no new inference."""
    if not args.flow_manifest or not args.geometry_manifest or not args.native_source:raise ValueError('Require flow/geometry manifests and native source')
    flow=verified_manifest(args.flow_manifest);geometry=verified_manifest(args.geometry_manifest);native=verified_manifest(args.native_source/'manifest.json')
    if dry_plan(args,[{'operation':'saved clean-candidate geometric analysis','online_gt':False}]):return 0
    fp=artifact_path(flow['run_dir']);gp=artifact_path(geometry['run_dir']);np=artifact_path(native['run_dir'])
    map_data=read_json(gp/'raw/map_geometry.json')
    if 'sampling_domain' not in map_data:raise ValueError('Map sampling coverage not recorded; regenerate native-geometry before candidate evaluation')
    result=read_json(fp/'metrics/flow_probe.json');input_path=Path(flow['identity']['config']['input'])
    if input_path.parent.resolve()!=(np/'raw/agent').resolve():raise ValueError('Native source/input provenance mismatch')
    step=int(input_path.stem.rsplit('_',1)[1]);pose=read_json(np/'raw/agent/metric_info.json')[str(step)]
    run=StageRun('stage05_carla_closed_loop',args,{'mode':args.mode,'scope':'RECORDED_CLEAN_CANDIDATE_MAP_DIAGNOSTIC_NOT_DRIVING_QUALITY','source_manifests':{str(p):file_hash(p) for p in (args.flow_manifest,args.geometry_manifest,args.native_source/'manifest.json')},'native_step':step,'map_limits':'approximate road union; point tests do not establish swept-body/dynamic/route validity','coordinate_contract':'native lidar x=right,y=forward; lidar origin 0.39m behind body; z ignored for 2D map'},['REAL_VLA_RECORDED_OUTPUT_ANALYSIS'],[fp/'metrics/flow_probe.json',gp/'raw/map_geometry.json'])
    import numpy as numpy
    from shapely.geometry import shape,Point
    surface=shape(map_data['surface']);forward=numpy.array(pose['forward_vector'][:2]);right=numpy.array(pose['right_vector'][:2]);origin=numpy.array(pose['location'][:2])-.39*forward
    rows=[];paths=[]
    for item in result['candidates']:
        traj=numpy.array(item['trajectory']);path=origin+traj[:,1,None]*forward+traj[:,0,None]*right;paths.append(path)
        # Sample connected point path, separately from vehicle footprint validity.
        chain=numpy.vstack([origin,path]);samples=[]
        for a,b in zip(chain,chain[1:]):samples.extend(a+(b-a)*u for u in numpy.linspace(0,1,max(2,int(numpy.linalg.norm(b-a)/.1)+1)))
        labels=[classify_map_point(surface,map_data['sampling_domain'],p) for p in samples]
        known=[p for p,label in zip(samples,labels) if label!='UNKNOWN_MAP_COVERAGE'];outside=labels.count('OUTSIDE_APPROX_SURFACE');unknown=labels.count('UNKNOWN_MAP_COVERAGE')
        rows.append({'depth':item['depth'],'finite':item['finite'],'point_path_samples':len(samples),'point_path_unknown_count':unknown,'point_path_outside_count':outside,'point_path_outside_fraction':outside/len(known) if known else None,'outside_fraction_denominator':'only sampled ROI known points','max_point_distance_to_driving_surface_m':max((surface.distance(Point(p)) for p in known),default=None),'map_coverage':'COMPLETE_XY_ROI' if not unknown else 'PARTIAL_UNKNOWN','max_segment_speed_mps':max(item['segment_speeds_mps']),'distance_to_full_max_abs_m':item['distance_to_full_max_abs_m'],'safe_candidate':'UNVALIDATED','quality_gain':'NOT_ESTABLISHED'})
    write_csv(run.path/'metrics/clean_candidates_geometry.csv',rows)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,6))
    for part in getattr(surface,'geoms',[surface]):
        if hasattr(part,'exterior'):xs,ys=part.exterior.xy;ax.fill(xs,ys,color='#dddddd',linewidth=0)
    for depth in (1,3,5,10):p=paths[depth-1];ax.plot(p[:,0],p[:,1],'o-',ms=3,label=f'Clean estimate after {depth} quantum(s)')
    ax.scatter(*origin,color='black',s=20);all_points=numpy.vstack(paths+[origin[None]]);lo=all_points.min(0)-4;hi=all_points.max(0)+4
    ax.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),xlabel='CARLA world X [m]',ylabel='CARLA world Y [m]',title=f'Recorded observation step {step}: clean estimates, not safety validation');ax.set_aspect('equal');ax.legend(fontsize=7);figure_save(fig,run.path/'figures/clean_candidate_map');plt.close(fig)
    data={'native_step':step,'rows':rows,'model_inference_executed':False,'source':str(fp),'gate_promoted':False,'limits':run.identity['config']['map_limits']};run.record({'kind':'clean_candidate_map_diagnostic'},data)
    return run.finish('PARTIAL',canonical(data),['Map point path only; full road/control/dynamic validity and refinement quality remain unvalidated'],acceptance='BLOCKED')

def evaluation_actor_snapshot(world,hero,sensor_frame,radius=60.):
    """Read-only GT for offline diagnosis, never passed to the driving policy."""
    before=world.get_snapshot();location=hero.get_location();objects=[]
    for actor in world.get_actors():
        if not actor.type_id.startswith(('vehicle.','walker.','traffic.')):continue
        transform=actor.get_transform()
        if transform.location.distance(location)>radius:continue
        velocity=actor.get_velocity();bbox=actor.bounding_box
        row={'id':actor.id,'type':actor.type_id,'is_hero':actor.id==hero.id,
             'location':[transform.location.x,transform.location.y,transform.location.z],
             'rotation':[transform.rotation.roll,transform.rotation.pitch,transform.rotation.yaw],
             'velocity':[velocity.x,velocity.y,velocity.z],
             'bbox_local_center':[bbox.location.x,bbox.location.y,bbox.location.z],
             'bbox_extent':[bbox.extent.x,bbox.extent.y,bbox.extent.z],
             'world_vertices':[[v.x,v.y,v.z] for v in bbox.get_world_vertices(transform)]}
        if hasattr(actor,'trigger_volume'):
            trigger=actor.trigger_volume
            row['trigger_world_vertices']=[[v.x,v.y,v.z] for v in trigger.get_world_vertices(transform)]
        objects.append(row)
    after=world.get_snapshot()
    if before.frame!=after.frame or before.frame!=sensor_frame:
        return {'scope':'EVALUATION_ONLY_NEVER_AGENT_INPUT','valid':False,'frame':before.frame,'after_frame':after.frame,'sensor_frame':sensor_frame,'objects':[],'reason':'Snapshot/sensor frame mismatch; no mixed-time GT used'}
    return {'scope':'EVALUATION_ONLY_NEVER_AGENT_INPUT','valid':True,'frame':before.frame,'sensor_frame':sensor_frame,'world_elapsed_s':before.timestamp.elapsed_seconds,'hero_id':hero.id,'objects':objects}

def native_candidate_body_samples(trajectory,pose,hero,reference='lidar',dt=.05):
    """Descriptive planar footprint samples; no vehicle dynamics certification."""
    import numpy as np
    from shapely.geometry import Polygon
    trajectory=np.asarray(trajectory,dtype=float)
    if trajectory.shape!=(6,2) or not np.isfinite(trajectory).all():raise ValueError('Expected finite native six x two trajectory')
    if reference not in ('lidar','body'):raise ValueError('Unknown native reference')
    forward=np.asarray(pose['forward_vector'][:2]);forward/=np.linalg.norm(forward)
    right=np.array([-forward[1],forward[0]]);origin=np.asarray(pose['location'][:2])
    if reference=='lidar':origin=origin-.39*forward
    path=np.vstack([origin,origin+trajectory[:,1,None]*forward+trajectory[:,0,None]*right])
    ex,ey=hero['bbox_extent'][:2];cx,cy=hero['bbox_local_center'][:2];samples=[];direction=forward
    for k in range(round(3/dt)+1):
        elapsed=k*dt;segment=min(5,int(elapsed/.5));u=(elapsed-segment*.5)/.5
        delta=path[segment+1]-path[segment]
        if k and np.linalg.norm(delta)>1e-6:direction=delta/np.linalg.norm(delta)
        lateral=np.array([-direction[1],direction[0]]);anchor=path[segment]+u*delta
        body=anchor+(.39*direction if reference=='lidar' else 0.)
        center=body+cx*direction+cy*lateral
        poly=Polygon([center+sx*ex*direction+sy*ey*lateral for sx,sy in ((-1,-1),(-1,1),(1,1),(1,-1))])
        samples.append({'elapsed_s':elapsed,'frame_offset':k,'body_xy':body,'polygon':poly})
    return samples

def run_native_forensics_analysis(args):
    """Evaluate saved model/control/actor evidence, with explicit missing coverage."""
    if args.native_source is None:raise ValueError('--native-source required')
    native=verified_manifest(args.native_source/'manifest.json');source=artifact_path(native['run_dir']);agent=source/'raw/agent'
    if not native['identity']['config'].get('evaluation_forensics'):raise ValueError('Require complete native forensics recording')
    flow=verified_manifest(args.flow_manifest) if args.flow_manifest else None
    geometry=verified_manifest(args.geometry_manifest) if args.geometry_manifest else None
    if dry_plan(args,[{'operation':'saved dynamic footprint and perception diagnosis','online_gt':False}]):return 0
    config={'mode':args.mode,'backend':'UniDriveVLA','scope':'OFFLINE_DEVELOPMENT_DIAGNOSIS_NOT_DEPLOYMENT_CALIBRATION','native_manifest':str(args.native_source/'manifest.json'),'native_sha256':file_hash(args.native_source/'manifest.json'),'flow_manifest_sha256':file_hash(args.flow_manifest) if flow else None,'perception_radius_m':40.,'max_height_difference_m':3.,'matching_distance_m':2.,'score_thresholds':[.1,.3,.5],'coarse_classes':'vehicle incl bicycle vs pedestrian; not official 9-class AP','denominator':'all nearby recorded actors incl occluded/invisible; not visibility-conditioned recall','trajectory_dt_s':.5,'evaluation_dt_s':.05,'references':['body','lidar'],'selected_steps':[180,200,210,220,230,240,250,260,280,300],'counterfactual_limit':'Future other actors follow the actually recorded replanning episode, not responses to the held candidate; overlaps are diagnostics, not causal collision predictions','body_limit':'Planar tangent orientation, piecewise linear path and rigid box; ignores tire dynamics/3D grade','gate_promoted':False}
    config['geometry_manifest_sha256']=file_hash(args.geometry_manifest) if geometry else None
    run=StageRun('stage05_carla_closed_loop',args,config,['REAL_VLA_RECORDED_OUTPUT_ANALYSIS','CARLA_EVALUATION_GROUND_TRUTH'])
    try:
        import torch,numpy as np
        from scipy.optimize import linear_sum_assignment
        from shapely.geometry import MultiPoint,Point,shape,box
        surface=domain=None
        if geometry:
            map_data=read_json(artifact_path(geometry['run_dir'])/'raw/map_geometry.json');coverage=map_data['sampling_domain'];margin=coverage['interior_margin_m']
            surface=shape(map_data['surface']);domain=box(coverage['xy_min'][0]+margin,coverage['xy_min'][1]+margin,coverage['xy_max'][0]-margin,coverage['xy_max'][1]-margin)
            native_town=read_json(source/'raw/official_results.json')['_checkpoint']['records'][0]['town_name']
            if not map_data['map'].endswith(native_town):raise ValueError('Map/native town mismatch')
        controls={r['step']:r for r in map(json.loads,(agent/'control_trace.jsonl').read_text().splitlines())}
        poses=read_json(agent/'metric_info.json')
        all_actors=list(map(json.loads,(agent/'actor_evaluation.jsonl').read_text().splitlines()))
        actors={r['step']:r for r in all_actors if r['valid']};by_frame={r['frame']:r for r in actors.values()}
        collisions=list(map(json.loads,(agent/'collision_evaluation.jsonl').read_text().splitlines())) if (agent/'collision_evaluation.jsonl').exists() else []
        collision_ids=set(r['other_actor_id'] for r in collisions)
        summaries=[];matches=[];target_rows=[];stop_rows=[];polygons={}
        def hull(obj):return MultiPoint(np.asarray(obj['world_vertices'])[:,:2]).convex_hull
        for step,record in actors.items():
            if record['frame']!=controls[step]['sensor_frames']['CAM_FRONT']:raise ValueError('Actor/control frame mismatch')
            hero=next(x for x in record['objects'] if x['is_hero']);location=np.asarray(hero['location']);pose=poses[str(step)]
            f=np.asarray(pose['forward_vector'][:2]);f/=np.linalg.norm(f);right=np.array([-f[1],f[0]]);origin=location[:2]-.39*f
            objects=[o for o in record['objects'] if not o['is_hero'] and o['type'].startswith(('vehicle.','walker.')) and np.linalg.norm(np.asarray(o['location'][:2])-location[:2])<=config['perception_radius_m'] and abs(o['location'][2]-location[2])<=config['max_height_difference_m']]
            polygons[record['frame']]={o['id']:hull(o) for o in record['objects'] if not o['is_hero'] and o['type'].startswith(('vehicle.','walker.')) and abs(o['location'][2]-location[2])<=config['max_height_difference_m']}
            for stop in record['objects']:
                if stop['type'].startswith('traffic.stop') and stop.get('trigger_world_vertices'):
                    center=np.asarray(stop['trigger_world_vertices']).mean(0);distance=float(np.linalg.norm(center[:2]-location[:2]))
                    stop_rows.append({'step':step,'sim_s':record['sim_s'],'stop_id':stop['id'],'trigger_center_distance_m':distance,'within_4m_center':distance<4.,'sensor_speed_mps':controls[step]['sensor_speed_mps'],'brake':controls[step]['brake'],'note':'proximity only; official criterion also uses map waypoints and stateful scan'})
            pp=agent/f'perception_{step:04d}.pt'
            if not pp.exists():raise ValueError('Missing recorded perception '+str(pp))
            perception=torch.load(pp,map_location='cpu',weights_only=False);det=perception['det'][0]
            boxes=det['boxes_3d'].float().numpy();scores=det['scores_3d'].float().numpy();labels=det['labels_3d'].numpy()
            centers=origin+boxes[:,1,None]*f+boxes[:,0,None]*right
            velocities=boxes[:,8,None]*f+boxes[:,7,None]*right
            for threshold in config['score_thresholds']:
                chosen=np.where((scores>=threshold)&np.isin(labels,[0,1,2,3,7])&(np.linalg.norm(boxes[:,:2],axis=1)<=config['perception_radius_m']))[0]
                gt=np.array([np.asarray(o['world_vertices']).mean(0)[:2] for o in objects]).reshape(-1,2)
                distance=np.linalg.norm(gt[:,None,:]-centers[chosen][None,:,:],axis=-1)
                compatible=np.array([[int(labels[j])==7 if o['type'].startswith('walker.') else int(labels[j])!=7 for j in chosen] for o in objects],dtype=bool).reshape(len(objects),len(chosen))
                allowed=(distance<=config['matching_distance_m'])&compatible
                pairs=[]
                if len(objects) and len(chosen):
                    ii,jj=linear_sum_assignment(np.where(allowed,distance,1e6+distance))
                    pairs=[(int(i),int(j)) for i,j in zip(ii,jj) if allowed[i,j]]
                matched={i:j for i,j in pairs}
                summaries.append({'step':step,'frame':record['frame'],'threshold':threshold,'all_gt_count':len(objects),'predicted_count':len(chosen),'matched_count':len(pairs),'unmatched_gt':len(objects)-len(pairs),'unmatched_predictions':len(chosen)-len(pairs)})
                for i,o in enumerate(objects):
                    j=chosen[matched[i]] if i in matched else None
                    row={'step':step,'frame':record['frame'],'sim_s':record['sim_s'],'threshold':threshold,'actor_id':o['id'],'actor_type':o['type'],'matched':j is not None,'center_error_m':float(np.linalg.norm(gt[i]-centers[j])) if j is not None else None,'velocity_error_mps':float(np.linalg.norm(np.asarray(o['velocity'][:2])-velocities[j])) if j is not None else None,'score':float(scores[j]) if j is not None else None,'prediction_label':int(labels[j]) if j is not None else None,'instance_id':int(det['instance_ids'][j]) if j is not None else None}
                    matches.append(row)
                    if o['id'] in collision_ids:
                        row=dict(row,actual_bbox_separation_m=hull(hero).distance(hull(o)),sensor_speed_mps=controls[step]['sensor_speed_mps'],desired_speed_mps=controls[step]['pid_metadata']['desired_speed'],brake=controls[step]['brake']);target_rows.append(row)
        trajectory_rows=[];sample_rows=[];plans=[]
        for step in config['selected_steps']:
            if step in actors:plans.append((step,'native_full',controls[step]['trajectory']))
        if flow:
            fconfig=flow['identity']['config'];input_path=Path(fconfig['input'])
            if input_path.parent.resolve()!=agent.resolve():raise ValueError('Flow input belongs to a different native run')
            step=int(input_path.stem.rsplit('_',1)[1]);data=read_json(artifact_path(flow['run_dir'])/'metrics/flow_probe.json')
            plans.extend((step,'clean_depth_'+str(c['depth']),c['trajectory']) for c in data['candidates'])
        for step,label,trajectory in plans:
            rec=actors[step];hero=next(o for o in rec['objects'] if o['is_hero']);pose=poses[str(step)]
            deltas=np.diff(np.vstack([[0.,0.],trajectory]),axis=0);speeds=np.linalg.norm(deltas,axis=1)/.5
            for reference in config['references']:
                overlaps=[];unknown=[];distances=[];divergence=[];road_areas=[];road_unknown=0
                for sample in native_candidate_body_samples(trajectory,pose,hero,reference):
                    road_missing=surface is None or not domain.covers(sample['polygon']) or not coverage['z_min']<=pose['location'][2]<=coverage['z_max']
                    if road_missing:road_unknown+=1
                    else:road_areas.append(sample['polygon'].difference(surface).area)
                    frame=rec['frame']+sample['frame_offset'];future=by_frame.get(frame);pairs=[]
                    coverage_unknown=future is None
                    if future is not None:
                        actual=next(o for o in future['objects'] if o['is_hero'])
                        # The actor recorder has a bounded 60m query domain.
                        coverage_unknown=float(np.linalg.norm(sample['body_xy']-np.asarray(actual['location'][:2])))+math.hypot(*hero['bbox_extent'][:2])>55.
                    if coverage_unknown:unknown.append(sample['elapsed_s'])
                    else:
                        pairs=[(oid,sample['polygon'].distance(poly),sample['polygon'].intersection(poly).area) for oid,poly in polygons[frame].items()]
                        for oid,distance,area in pairs:
                            if area>0:overlaps.append({'elapsed_s':sample['elapsed_s'],'actor_id':oid,'overlap_m2':area})
                        actual=next(o for o in future['objects'] if o['is_hero'])
                        divergence.append(float(np.linalg.norm(np.asarray(actual['location'][:2])-sample['body_xy'])))
                    min_distance=min((p[1] for p in pairs),default=None)
                    if min_distance is not None:distances.append(min_distance)
                    sample_rows.append({'step':step,'candidate':label,'reference':reference,'elapsed_s':sample['elapsed_s'],'world_x':float(sample['body_xy'][0]),'world_y':float(sample['body_xy'][1]),'future_record_available':future is not None,'actor_coverage_unknown':coverage_unknown,'min_recorded_actor_separation_m':min_distance,'overlap_actor_ids':';'.join(str(p[0]) for p in pairs if p[2]>0)})
                trajectory_rows.append({'step':step,'candidate':label,'reference':reference,'unknown_future_samples':len(unknown),'unknown_road_samples':road_unknown,'max_body_area_outside_approx_surface_m2':max(road_areas,default=None),'sampled_overlap_count':len(overlaps),'first_overlap_s':overlaps[0]['elapsed_s'] if overlaps else None,'overlap_actor_ids':sorted(set(o['actor_id'] for o in overlaps)),'min_separation_m':min(distances,default=None),'max_speed_mps':float(speeds.max()),'max_discrete_acceleration_mps2':float(np.max(np.abs(np.diff(np.r_[controls[step]['sensor_speed_mps'],speeds])/.5))),'actual_replanned_path_divergence_max_m':max(divergence,default=None),'validity':'UNVALIDATED; recorded-world counterfactual only'})
        write_csv(run.path/'metrics/perception_frames.csv',summaries);write_csv(run.path/'metrics/perception_matches.csv',matches);write_csv(run.path/'metrics/collision_actor.csv',target_rows);write_csv(run.path/'metrics/stop_proximity.csv',stop_rows)
        write_csv(run.path/'metrics/candidate_dynamic.csv',trajectory_rows);write_csv(run.path/'metrics/candidate_dynamic_samples.csv',sample_rows)
        atomic_json(run.path/'raw/collision_callbacks.json',collisions)
        perception_summary=[]
        for threshold in config['score_thresholds']:
            rows=[r for r in summaries if r['threshold']==threshold];matched=[r for r in matches if r['threshold']==threshold and r['matched']];denominator=sum(r['all_gt_count'] for r in rows)
            perception_summary.append({'threshold':threshold,'gt_actor_frame_count':denominator,'matched_actor_frame_count':len(matched),'all_actor_matching_fraction':len(matched)/denominator if denominator else None,'conditional_center_error_p95_m':quantile([r['center_error_m'] for r in matched],.95),'conditional_velocity_error_p95_mps':quantile([r['velocity_error_mps'] for r in matched],.95),'not_independent_samples':True,'not_calibrated_bounds':True})
        result={'gate_promoted':False,'native_run':str(source),'recorded_frames':len(all_actors),'valid_actor_frames':len(actors),'invalid_actor_frames':len(all_actors)-len(actors),'collision_callbacks':len(collisions),'collision_actor_ids':sorted(collision_ids),'perception':perception_summary,'candidate_diagnostics':trajectory_rows,'limits':config}
        atomic_json(run.path/'metrics/forensics_summary.json',result)
        import matplotlib;matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(3,1,figsize=(10,8),sharex=True)
        steps=sorted(controls);t=[controls[s]['simulation_timestamp'] for s in steps]
        axes[0].plot(t,[controls[s]['sensor_speed_mps'] for s in steps],label='Actual speed');axes[0].plot(t,[controls[s]['pid_metadata']['desired_speed'] for s in steps],label='PID desired speed');axes[0].set_ylabel('Speed [m/s]')
        axes[1].plot(t,[controls[s]['throttle'] for s in steps],label='Throttle');axes[1].plot(t,[controls[s]['brake'] for s in steps],label='Brake');axes[1].set_ylabel('Control [0..1]')
        for oid in sorted(collision_ids):
            rr=[r for r in target_rows if r['threshold']==.3 and r['actor_id']==oid]
            axes[2].plot([r['sim_s'] for r in rr],[r['actual_bbox_separation_m'] for r in rr],label=f'Actual separation actor {oid}')
            bad=[r for r in rr if not r['matched']];axes[2].scatter([r['sim_s'] for r in bad],[r['actual_bbox_separation_m'] for r in bad],marker='x',s=15,label='Unmatched at score >= 0.3')
        for ax in axes:
            ax.grid(alpha=.2);ax.legend(fontsize=8)
            for collision in collisions:
                collision_step=next((s for s in steps if controls[s]['sensor_frames']['CAM_FRONT']>=collision['frame']),None)
                if collision_step is not None:ax.axvline(controls[collision_step]['simulation_timestamp'],color='red',alpha=.3)
        axes[2].set(xlabel='Episode simulation time [s]',ylabel='Separation [m]');fig.suptitle('Native development episode: perception / planning / control diagnosis');figure_save(fig,run.path/'figures/forensics_timeline');plt.close(fig)
        if flow:
            fig,axes=plt.subplots(1,2,figsize=(12,6));step=int(Path(flow['identity']['config']['input']).stem.rsplit('_',1)[1]);rec=actors[step];hero=next(o for o in rec['objects'] if o['is_hero'])
            for ax,depth in zip(axes,(1,10)):
                if surface is not None:
                    for part in getattr(surface,'geoms',[surface]):
                        if hasattr(part,'exterior'):x,y=part.exterior.xy;ax.fill(x,y,color='#dedede',linewidth=0)
                traj=next(t for s,label,t in plans if label=='clean_depth_'+str(depth));samples=native_candidate_body_samples(traj,poses[str(step)],hero,'lidar')
                xy=np.array([s['body_xy'] for s in samples]);ax.plot(xy[:,0],xy[:,1],color='#1466a0',label='Clean candidate body origin')
                sample=samples[14];x,y=sample['polygon'].exterior.xy;ax.plot(x,y,color='#1466a0',label='Candidate box at +0.70 s')
                future=by_frame.get(rec['frame']+14)
                if future:
                    for obj in future['objects']:
                        if obj['id'] in collision_ids:
                            poly=hull(obj);x,y=poly.exterior.xy;ax.fill(x,y,alpha=.3,color='#c13c3c',label='Recorded target box at +0.70 s')
                current=hull(hero);x,y=current.exterior.xy;ax.plot(x,y,color='black',label='Observed ego box')
                ax.set(xlim=(xy[:,0].min()-5,xy[:,0].max()+5),ylim=(xy[:,1].min()-5,xy[:,1].max()+5),xlabel='CARLA world X [m]',ylabel='CARLA world Y [m]',title=f'Observation {step}, clean depth {depth}')
                ax.set_aspect('equal');ax.legend(fontsize=7)
            fig.suptitle('Sampled boxes against recorded traffic; diagnostic counterfactual, not safety proof');figure_save(fig,run.path/'figures/clean_candidate_conflict');plt.close(fig)
        run.record({'kind':'saved_native_forensics_analysis'},result)
        return run.finish('PARTIAL',canonical(result),['Development actor matching is not independent perception calibration; sampled recorded-world overlaps are not a safety or causal proof'],acceptance='BLOCKED')
    except BaseException:
        error=traceback.format_exc();run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')

def native_sensor_telemetry(input_data,episode_s):
    """Retain unavailable raw sensor values explicitly without changing policy."""
    import numpy as np
    unavailable=[]
    def clean(value,path):
        if isinstance(value,np.ndarray):return clean(value.tolist(),path)
        if isinstance(value,np.generic):return clean(value.item(),path)
        if isinstance(value,dict):return {str(k):clean(v,path+'.'+str(k)) for k,v in value.items()}
        if isinstance(value,(tuple,list)):return [clean(v,path+f'[{i}]') for i,v in enumerate(value)]
        if isinstance(value,float) and not math.isfinite(value):unavailable.append(path);return None
        return value
    sensors={name:{'frame':int(input_data[name][0]),'values':clean(input_data[name][1],name)} for name in ('GPS','IMU','SPEED')}
    return {'frame':int(input_data['CAM_FRONT'][0]),'episode_capture_s':float(episode_s),'source':'RAW_AGENT_SENSOR_INPUT','uses_actor_truth':False,'sensors':sensors,'nonfinite_value_paths':unavailable}

def native_sensor_localization_record(step,frame,episode_s,model_kwargs):
    """Extract ONLY the Agent's GPS/IMU-derived model input, never actor pose."""
    import numpy as np
    metas=model_kwargs['img_metas']
    if not isinstance(metas,list) or len(metas)!=1:raise ValueError('Require batch-one native metadata')
    meta=metas[0];transform=np.asarray(meta['T_global'],dtype=float);inverse=np.asarray(meta['T_global_inv'],dtype=float)
    if transform.shape!=(4,4) or inverse.shape!=(4,4) or not np.isfinite(transform).all() or not np.isfinite(inverse).all():raise ValueError('Invalid native sensor localization')
    if not np.allclose(transform@inverse,np.eye(4),atol=1e-5,rtol=0) or not np.allclose(transform[3],[0,0,0,1],atol=1e-6,rtol=0):raise ValueError('Inconsistent native localization inverse')
    status=model_kwargs['ego_status'].detach().float().cpu().numpy()
    if status.shape!=(1,6) or not np.isfinite(status).all():raise ValueError('Invalid sensor ego status')
    if not all(math.isfinite(float(x)) for x in (episode_s,meta['timestamp'])):raise ValueError('Invalid localization timestamp')
    return {'schema':1,'step':int(step),'sensor_frame':int(frame),'episode_capture_s':float(episode_s),'model_timestamp_s':float(meta['timestamp']),'clock_note':'episode timestamp and step/frame_rate model timestamp are different origins','T_global':transform.tolist(),'T_global_inv':inverse.tolist(),'ego_status':status[0].tolist(),'source':'OFFICIAL_AGENT_GNSS_IMU_SPEED_INPUT','coordinate_contract':'native model lidar-to-global matrix, right-handed model world; do not mix with CARLA world Y without transform','uses_actor_truth':False,'localization_error_bounds':'UNCALIBRATED'}

def get_entry_point():
    """Explicit measured compatibility Agent; retains official sensors/PID/planner."""
    import torch
    from team_code.unidrivevla_b2d_agent import UniDriveVLAB2DAgent
    def cpu_copy(value):
        if isinstance(value,torch.Tensor):return value.detach().cpu().clone()
        if isinstance(value,dict):return {k:cpu_copy(v) for k,v in value.items()}
        if isinstance(value,list):return [cpu_copy(v) for v in value]
        if isinstance(value,tuple):return tuple(cpu_copy(v) for v in value)
        return value
    class MeasuredUniDriveAgent(UniDriveVLAB2DAgent):
        def setup(self,path):
            super().setup(path)
            self._measurement_dir=Path(os.environ['SAVE_PATH']);self._measurement_calls=0
            self._precision_mode=os.environ.get('FRAMELEASE_NATIVE_PRECISION','official')
            self._prompt_command=os.environ.get('FRAMELEASE_NATIVE_PROMPT_COMMAND','official')
            from stage02_real_vla import install_unidrive_command_prompt
            prompt_source=install_unidrive_command_prompt(self.model.planning_head,self._prompt_command)
            if prompt_source:(self._measurement_dir/'prompt_command_compatibility.py.txt').write_text(prompt_source)
            self._diagnostics=os.environ.get('FRAMELEASE_NATIVE_DIAGNOSTICS','0')=='1'
            self._forensics=os.environ.get('FRAMELEASE_NATIVE_FORENSICS','0')=='1'
            self._capture_steps={0,100,200,300,350,380,400,420,440,500,580}
            if self._forensics:self._capture_steps.update((180,210,220,230,240,250,260,280))
            self._eval_collision=None
            if self._diagnostics:
                import carla
                self._eval_map=self.hero_actor.get_world().get_map()
                self._eval_collision=self.hero_actor.get_world().spawn_actor(self.hero_actor.get_world().get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=self.hero_actor)
                def collision(event):
                    impulse=event.normal_impulse
                    row={'scope':'EVALUATION_ONLY_NEVER_AGENT_INPUT','frame':event.frame,'sim_timestamp':event.timestamp,'other_actor_id':event.other_actor.id,'other_actor_type':event.other_actor.type_id,'impulse_xyz':[impulse.x,impulse.y,impulse.z]}
                    with (self._measurement_dir/'collision_evaluation.jsonl').open('a') as f:f.write(canonical(row)+'\n')
                self._eval_collision.listen(collision)
            self._model_start=torch.cuda.Event(enable_timing=True);self._model_end=torch.cuda.Event(enable_timing=True)
            def before(module,inputs,kwargs):
                if self._forensics:
                    localization=native_sensor_localization_record(self.step,self._sensor_frame,self._episode_capture_s,kwargs)
                    with (self._measurement_dir/'localization_trace.jsonl').open('a') as f:f.write(canonical(localization)+'\n')
                if self._measurement_calls==0:
                    torch.save({'args':cpu_copy(inputs),'kwargs':cpu_copy(kwargs),'torch_rng_state':torch.get_rng_state(),'cuda_rng_state':torch.cuda.get_rng_state_all(),'precision':self._precision_mode},self._measurement_dir/'first_model_input.pt')
                if self._diagnostics and self._measurement_calls in self._capture_steps:
                    from stage02_real_vla import capture_unidrive_temporal
                    torch.save({'args':cpu_copy(inputs),'kwargs':cpu_copy(kwargs),'torch_rng_state':torch.get_rng_state(),'cuda_rng_state':torch.cuda.get_rng_state_all(),'precision':self._precision_mode,'temporal_context':capture_unidrive_temporal(self.model.planning_head,cpu_copy),'native_step':self.step},self._measurement_dir/f'model_input_{self.step:04d}.pt')
                torch.cuda.synchronize();self._model_wall_start=time.perf_counter_ns();self._model_start.record()
            def after(module,inputs,kwargs,output):
                self._model_end.record();torch.cuda.synchronize()
                row={'call':self._measurement_calls,'model_wall_ms':(time.perf_counter_ns()-self._model_wall_start)/1e6,'cuda_event_ms':self._model_start.elapsed_time(self._model_end),'allocated_bytes':torch.cuda.memory_allocated(),'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'precision':self._precision_mode}
                row['trajectory']=cpu_copy(output[0]['img_bbox']['final_planning']).tolist()
                with (self._measurement_dir/'model_trace.jsonl').open('a') as f:f.write(canonical(row)+'\n')
                if self._measurement_calls==0:torch.save(cpu_copy(output),self._measurement_dir/'first_model_output.pt')
                self._measurement_calls+=1
            self.model.register_forward_pre_hook(before,with_kwargs=True)
            self.model.register_forward_hook(after,with_kwargs=True)
            if self._forensics:
                # The detector discards det/map; save the native head return
                # separately, without changing its values or the model input.
                native_head=self.model.planning_head.forward_test
                def record_head(*a,**kw):
                    output=native_head(*a,**kw)
                    torch.save({'step':self.step,'det':cpu_copy(output['det']),'map':cpu_copy(output['map'])},self._measurement_dir/f'perception_{self.step:04d}.pt')
                    return output
                self.model.planning_head.forward_test=record_head
        def run_step(self,input_data,timestamp):
            started=time.perf_counter_ns()
            if self._forensics:
                self._sensor_frame=input_data['CAM_FRONT'][0];self._episode_capture_s=timestamp
                telemetry=native_sensor_telemetry(input_data,timestamp)
                with (self._measurement_dir/'sensor_telemetry.jsonl').open('a') as f:f.write(canonical(telemetry)+'\n')
            if self._precision_mode=='bf16-autocast':
                with torch.autocast(device_type='cuda',dtype=torch.bfloat16):control=super().run_step(input_data,timestamp)
            elif self._precision_mode=='official':control=super().run_step(input_data,timestamp)
            else:raise ValueError('Undeclared precision mode')
            row={'step':self.step,'simulation_timestamp':timestamp,'sensor_frames':{k:v[0] for k,v in input_data.items()},'wall_ms_including_measurement':(time.perf_counter_ns()-started)/1e6,'throttle':float(control.throttle),'brake':float(control.brake),'steer':float(control.steer),'trajectory':self.pid_metadata['plan_temp'],'command':self.pid_metadata['command']}
            if self._diagnostics:
                import carla,cv2
                row['sensor_speed_mps']=float(input_data['SPEED'][1]['speed']);row['pid_metadata']=self.pid_metadata
                transform=self.hero_actor.get_transform();box=self.hero_actor.bounding_box
                vertices=box.get_world_vertices(transform)
                evaluation={'scope':'EVALUATION_ONLY_NEVER_AGENT_INPUT','step':self.step,'sensor_frame':input_data['CAM_FRONT'][0],'sim_s':timestamp,'pose':self.metric_info[self.step],'footprint_vertices':[[v.x,v.y,v.z] for v in vertices],'vertex_driving_queries':[self._eval_map.get_waypoint(v,project_to_road=False,lane_type=carla.LaneType.Driving) is not None for v in vertices]}
                with (self._measurement_dir/'geometry_evaluation.jsonl').open('a') as f:f.write(canonical(evaluation)+'\n')
                if self._forensics:
                    actors=evaluation_actor_snapshot(self.hero_actor.get_world(),self.hero_actor,input_data['CAM_FRONT'][0])
                    actors.update(step=self.step,sim_s=timestamp)
                    with (self._measurement_dir/'actor_evaluation.jsonl').open('a') as f:f.write(canonical(actors)+'\n')
                if self.step in self._capture_steps:
                    for name in ('CAM_FRONT','bev'):cv2.imwrite(str(self._measurement_dir/f'{name}_{self.step:04d}.png'),input_data[name][1][:,:,:3])
            with (self._measurement_dir/'control_trace.jsonl').open('a') as f:f.write(canonical(row)+'\n')
            return control
        def destroy(self):
            if getattr(self,'_eval_collision',None) is not None:
                self._eval_collision.stop();self._eval_collision.destroy();self._eval_collision=None
            if hasattr(self,'model'):super().destroy()
    globals()['MeasuredUniDriveAgent']=MeasuredUniDriveAgent
    return 'MeasuredUniDriveAgent'

def run_native_benchmark(args):
    from stage02_real_vla import UNIDRIVE_REPO,UNIDRIVE_AGENT,UNIDRIVE_CONFIG,UNIDRIVE_COMMIT
    b2d=UNIDRIVE_REPO/'Bench2Drive';evaluator=b2d/'bench2drive/leaderboard/leaderboard/leaderboard_evaluator.py';routes=b2d/'bench2drive/leaderboard/data/routes_debug.xml'
    if dry_plan(args,[{'backend':'UniDriveVLA','agent_kind':'MEASURED_OFFICIAL_METHODS_COMPATIBILITY' if args.native_measure else 'OFFICIAL_NATIVE_AGENT','precision_mode':args.native_precision,'routes':str(routes),'wall_timeout_s':args.native_timeout}]):return 0
    checkpoint=Path(os.environ['CHECKPOINT']);config={'mode':args.mode,'backend':'UniDriveVLA','source_commit':UNIDRIVE_COMMIT,'checkpoint':str(checkpoint),'checkpoint_sha256':file_hash(checkpoint),'routes_sha256':file_hash(routes),'seed':args.seed,'port':args.port,'tm_port':args.port+6000,'wall_timeout_s':args.native_timeout,'clock':'OFFICIAL_SYNCHRONOUS_20HZ_NOT_LIVE_FRAMELEASE','gate_promoted':False,'precision_mode':args.native_precision,'measured_agent':args.native_measure,'agent_kind':'MEASURED_OFFICIAL_METHODS_COMPATIBILITY' if args.native_measure else 'OFFICIAL_NATIVE_AGENT'}
    compat=Path(os.environ.get('FRAMELEASE_BENCHMARK_ROOT',b2d/'bench2drive'))
    dependencies=[evaluator,UNIDRIVE_REPO/UNIDRIVE_AGENT,UNIDRIVE_REPO/UNIDRIVE_CONFIG,ROOT/'stage02_real_vla.py',routes,ROOT/'linux/env.sh',*sorted((ROOT/'linux/patches').glob('*.patch'))]
    config['dependency_patches']={str(p):file_hash(p) for p in dependencies if p.suffix=='.patch'}
    config['evaluation_diagnostics']=args.native_diagnostics
    config['evaluation_forensics']=args.native_forensics
    config['forensics_contract']='all native det/map; continuous raw GPS/IMU/SPEED and model localization in separate sensor-only records; every-tick read-only actor/stop-trigger GT; fixed extra input capture steps180,210,220,230,240,250,260,280; no policy feedback'
    config['prompt_command_mode']=args.native_prompt_command
    config['diagnostic_scope']='additional evaluation-only collision/geometry and saved real inputs; no policy/controller modification'
    config['benchmark_source_files']={str(p.relative_to(compat)):file_hash(p) for p in compat.rglob('*.py')}
    run=StageRun('stage05_carla_closed_loop',args,config,['NATIVE_EVALUATOR_EXECUTION'],dependencies)
    import difflib,psutil
    original=evaluator.read_text();patched=native_evaluator_owned_cleanup(original);entry=run.path.resolve()/'raw/leaderboard_evaluator_owned.py';entry.write_text(patched)
    (run.path/'raw/evaluator_cleanup.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),patched.splitlines(True),fromfile=str(evaluator),tofile=str(entry))))
    save=run.path.resolve()/'raw/agent';save.mkdir();score=run.path.resolve()/'raw/official_results.json'
    env=os.environ.copy();env.update(SAVE_PATH=str(save),CARLA_ROOT=str(args.carla_path),IS_BENCH2DRIVE='1',IS_VISUALIZE='0',PLANNER_TYPE='traj',ROUTES=str(routes),PYTHONUNBUFFERED='1')
    env['PYTHONPATH']=str(ROOT)+os.pathsep+env.get('PYTHONPATH','');env['FRAMELEASE_NATIVE_PRECISION']=args.native_precision
    env['FRAMELEASE_NATIVE_DIAGNOSTICS']='1' if args.native_diagnostics else '0'
    env['FRAMELEASE_NATIVE_FORENSICS']='1' if args.native_forensics else '0'
    env['FRAMELEASE_NATIVE_PROMPT_COMMAND']=args.native_prompt_command
    # Official evaluator explicitly seeds Traffic Manager; seed other libraries too.
    bootstrap='import random,numpy as np,torch,runpy,sys; s=int(sys.argv.pop(1)); random.seed(s); np.random.seed(s); torch.manual_seed(s); p=sys.argv.pop(1); sys.argv[0]=p; runpy.run_path(p,run_name="__main__")'
    cmd=[sys.executable,'-u','-c',bootstrap,str(args.seed),str(entry),'--routes',str(routes),'--repetitions','1','--track','SENSORS','--checkpoint',str(score),'--debug-checkpoint',str(run.path.resolve()/'raw/live_results.txt'),'--agent',str(UNIDRIVE_REPO/UNIDRIVE_AGENT),'--agent-config',str(UNIDRIVE_REPO/UNIDRIVE_CONFIG)+'+'+str(checkpoint),'--debug','0','--port',str(args.port),'--traffic-manager-port',str(args.port+6000),'--traffic-manager-seed',str(args.seed),'--gpu-rank','0','--timeout','180']
    if args.native_measure:cmd[cmd.index('--agent')+1]=str(ROOT/'stage05_carla_closed_loop.py')
    atomic_json(run.path/'raw/command.json',{'argv':cmd,'cwd':str(b2d),'environment_overrides':{k:env[k] for k in ('SAVE_PATH','CARLA_ROOT','IS_BENCH2DRIVE','IS_VISUALIZE','PLANNER_TYPE','ROUTES','FRAMELEASE_NATIVE_PRECISION','PYTHONPATH')},'patched_evaluator_sha256':file_hash(entry)})
    process=None;owned={};error=None;timed_out=False;cleanup=[];started=time.monotonic()
    with writer_lock(ROOT/'results/shared_gpu_resource'):
        try:
            require_free_ports([args.port,args.port+1,args.port+2,args.port+6000])
            with (run.path/'logs/evaluator.log').open('w') as log:
                process=subprocess.Popen(cmd,cwd=b2d,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            run.log('evaluator_started',pid=process.pid)
            while process.poll() is None:
                try:
                    for child in psutil.Process(process.pid).children(recursive=True):owned[child.pid]=child.create_time()
                except psutil.NoSuchProcess:pass
                if time.monotonic()-started>args.native_timeout:timed_out=True;break
                time.sleep(2)
        except BaseException:error=traceback.format_exc();run.log('failure',traceback=error)
        finally:
            if process is not None:
                try:stop_owned_group(process)
                except Exception as e:cleanup.append(repr(e))
            for pid,created in owned.items():
                try:
                    child=psutil.Process(pid)
                    if child.create_time()==created and child.status()!=psutil.STATUS_ZOMBIE:
                        child.kill();child.wait(timeout=10)
                except psutil.NoSuchProcess:pass
                except Exception as e:cleanup.append(repr(e))
    scores=read_json(score) if score.exists() else None
    records=(scores or {}).get('_checkpoint',{}).get('records',[])
    result={'returncode':process.returncode if process else None,'timed_out':timed_out,'wall_s':time.monotonic()-started,'error':error,'cleanup_errors':cleanup,'official_results':scores,'route_records':len(records),'gate_promoted':False,'framelease_runtime_executed':False,'clock':config['clock'],'ownership':owned}
    atomic_json(run.path/'metrics/native_result.json',result)
    failures=[]
    if error:failures.append(error)
    if timed_out:failures.append('Bounded official evaluation wall timeout')
    if cleanup:failures.append('Owned process cleanup errors: '+str(cleanup))
    if not records:failures.append('No official route result produced')
    for record in records:
        if record.get('status')!='Completed':failures.append('Official route status: '+str(record.get('status')))
    if process and process.returncode!=0:failures.append('Evaluator exit: '+str(process.returncode))
    run.record({'kind':'official_native_debug_route'},result,'FAILED' if failures else 'COMPLETED','; '.join(failures) or None)
    return run.finish('FAILED' if failures else 'PARTIAL',canonical(result),failures,acceptance='BLOCKED')

def run_native_pid_replay(args):
    """Replay the stateful official controller on recorded sensor/model outputs."""
    if args.native_source is None:raise ValueError('--native-source required')
    if dry_plan(args,[{'operation':'official PID sequence replay, no CARLA server or VLA forward'}]):return 0
    import ast,importlib.util,importlib,numpy as np,carla
    from stage02_real_vla import UNIDRIVE_REPO,UNIDRIVE_AGENT
    source=args.native_source.resolve();native=verified_manifest(source/'manifest.json')
    agent_path=Path(importlib.util.find_spec('team_code.unidrivevla_b2d_agent').origin)
    pid_path=Path(importlib.util.find_spec('team_code.pid_controller').origin)
    official_agent=UNIDRIVE_REPO/UNIDRIVE_AGENT
    official_pid=official_agent.with_name('pid_controller.py')
    # Prove that runtime shadow paths contain the exact official bytes.
    if file_hash(agent_path)!=file_hash(official_agent) or file_hash(pid_path)!=file_hash(official_pid):
        raise ValueError('Resolved Agent/PID differs from pinned official source')
    for p in (agent_path,pid_path):
        relative=str(p.relative_to(Path(os.environ['FRAMELEASE_BENCHMARK_ROOT'])))
        if native['identity']['config']['benchmark_source_files'][relative]!=file_hash(p):
            raise ValueError('PID/Agent source differs from recorded episode')
    tree=ast.parse(agent_path.read_text());calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='PIDControllerVAD']
    if len(calls)!=1 or calls[0].args:raise ValueError('Official PID construction changed')
    parameters={k.arg:ast.literal_eval(k.value) for k in calls[0].keywords}
    controls=source/'raw/agent/control_trace.jsonl'
    config={'mode':args.mode,'scope':'RECORDED_OUTPUT_STATEFUL_PID_REPLAY','native_manifest_sha256':file_hash(source/'manifest.json'),'native_source':str(source),'resolved_agent':str(agent_path),'resolved_pid':str(pid_path),'parameters':parameters,'trajectory_dtype':'float32','speed_dtype':'float64 NumPy scalar preserving speedometer JSON value','control_tolerance':1e-7,'desired_speed_tolerance_mps':1e-7,'gt_used':False,'model_executed':False}
    run=StageRun('stage05_carla_closed_loop',args,config,['OFFICIAL_CONTROLLER_REPLAY'],[controls,agent_path,pid_path,ROOT/'stage02_real_vla.py'])
    try:
        controller=importlib.import_module('team_code.pid_controller').PIDController(**parameters)
        rows=[];records=[json.loads(line) for line in controls.read_text().splitlines()]
        for index,record in enumerate(records):
            if record['step']!=index:raise ValueError('PID replay requires full sequence from step zero')
            trajectory=np.asarray(record['trajectory'],dtype=np.float32);speed=np.float64(record['sensor_speed_mps'])
            steer,throttle,brake,meta=controller.control_pid(trajectory,speed,trajectory[-1])
            if brake<.05:brake=0.
            if throttle>brake:brake=0.
            control=carla.VehicleControl(steer=float(np.clip(steer,-1,1)),throttle=float(np.clip(throttle,0,.75)),brake=float(np.clip(brake,0,1)))
            row={'step':index,'frame':record['sensor_frames']['CAM_FRONT'],'episode_s':record['simulation_timestamp'],'speed_mps':float(speed),'desired_speed_mps':meta['desired_speed'],'speed_ratio':float(speed)/max(meta['desired_speed'],.001),'low_target_brake':meta['desired_speed']<controller.brake_speed,'overspeed_brake':float(speed)/max(meta['desired_speed'],.001)>controller.brake_ratio/max(controller.brake_kp_ratio,.001),'delta':meta['delta'],'desired_speed_error_mps':abs(meta['desired_speed']-record['pid_metadata']['desired_speed'])}
            for key in ('steer','throttle','brake'):
                value=float(getattr(control,key));row[key]=value;row[key+'_error']=abs(value-record[key])
            rows.append(row)
        write_csv(run.path/'metrics/pid_replay.csv',rows)
        errors={key:max(r[key] for r in rows) for key in ('steer_error','throttle_error','brake_error','desired_speed_error_mps')}
        result={'frames':len(rows),'max_errors':errors,'all_within_frozen_tolerance':max(errors.values())<=1e-7,'selected_rows':[r for r in rows if r['step'] in (180,200,210,215,220)],'resolved_sources':{str(p):file_hash(p) for p in (agent_path,pid_path)},'control_inputs':['six decoded trajectory points','speedometer speed','trajectory endpoint dummy target'],'explicit_obstacle_check_in_pid':False,'gate_promoted':False,'limits':'Reproducing control does not establish safety or rule out planning/control design limitations.'}
        atomic_json(run.path/'metrics/pid_replay.json',result);run.record({'kind':'official_stateful_pid_replay'},result)
        return run.finish('COMPLETED' if result['all_within_frozen_tolerance'] else 'FAILED',canonical(result),[] if result['all_within_frozen_tolerance'] else ['PID replay mismatch'],acceptance='PARTIAL')
    except BaseException:
        error=traceback.format_exc();run.log('failure',traceback=error);return run.finish('FAILED',error,[error],acceptance='BLOCKED')

def main(argv=None):
    p=parser('stage05_carla_closed_loop',('smoke','benchmark','stress','full','audit','road-audit','native-preflight','linux-infrastructure','native-benchmark','native-geometry','native-observe','flow-road-analysis','native-forensics-analysis','native-pid-replay'));p.add_argument('--flow-manifest',type=Path);p.add_argument('--geometry-manifest',type=Path);p.add_argument('--native-source',type=Path);p.add_argument('--native-prompt-command',choices=('official','onehot-argmax'),default='official');p.add_argument('--native-timeout',type=float,default=1200);p.add_argument('--native-precision',choices=('official','bf16-autocast'),default='official');p.add_argument('--native-measure',action='store_true');p.add_argument('--native-diagnostics',action='store_true');p.add_argument('--native-forensics',action='store_true');p.add_argument('--carla-path',type=Path,default=Path(os.environ.get('CARLA_ROOT','/home/kang/opt/CARLA_0.9.15' if sys.platform.startswith('linux') else 'D:/CARLA_0.9.15/WindowsNoEditor')));p.add_argument('--carla-map',default='Town10HD_Opt');p.add_argument('--port',type=int,default=2199);p.add_argument('--duration',type=float,default=30);p.add_argument('--deployment-config',type=Path,default=ROOT/'configs/carla_deployment.json');p.add_argument('--collect-input',action='store_true',help='Actual sensor recording only, never VLA closed-loop evidence');p.add_argument('--model-backend',choices=('official','windows-eager'),default='official');p.add_argument('--diagnostic-closed-loop',action='store_true',help='Explicit simulator integration experiment; no validated safety lease or official score');p.add_argument('--diagnostic-age-cap',type=float,default=1.0,help='Experimental TTL seconds; not a calibrated safety lease');p.add_argument('--audit-episode',type=Path);p.add_argument('--stationary-interface',action='store_true');p.add_argument('--ddim-steps',type=int,choices=(3,5),default=5);p.add_argument('--speed-cap',type=float,default=2.5);p.add_argument('--spawn-index',type=int);p.add_argument('--basic-straight',action='store_true');p.add_argument('--radar-perception',action='store_true');p.add_argument('--perception-probe',action='store_true');p.add_argument('--probe-occlusion',action='store_true');p.add_argument('--online-avl',action='store_true');p.add_argument('--runtime-policy',choices=('Fast Only','Fixed Deep','FrameLease'));p.add_argument('--sensor-only',action='store_true');p.add_argument('--model-reference',choices=('body-origin','rear-axle'),default='rear-axle');p.add_argument('--oracle-route',action='store_true');p.add_argument('--route-geometry',type=Path);p.add_argument('--geometry-reference',type=Path);args=p.parse_args(argv)
    if args.mode=='native-pid-replay':return run_native_pid_replay(args)
    if args.native_forensics and not (args.native_diagnostics and args.native_measure):p.error('Native forensics requires --native-diagnostics --native-measure')
    if args.native_prompt_command!='official' and not args.native_measure:p.error('Prompt compatibility requires --native-measure')
    if args.native_diagnostics and not args.native_measure:p.error('Native diagnostics require --native-measure')
    if args.native_precision!='official' and not args.native_measure:p.error('Explicit precision compatibility requires --native-measure')
    if args.sensor_only and not (args.perception_probe and args.stationary_interface and args.diagnostic_closed_loop):p.error('Sensor-only requires explicit stationary perception diagnostic')
    if args.oracle_route and not (args.diagnostic_closed_loop and args.basic_straight):p.error('Oracle is restricted to explicitly diagnostic basic straight')
    if args.online_avl and not (args.radar_perception and args.runtime_policy):p.error('Online AVL diagnostic requires radar and explicit shared runtime policy')
    if args.perception_probe and not (args.radar_perception and args.stationary_interface):p.error('Perception calibration probe requires radar and stationary ego; not driving evidence')
    if args.diagnostic_closed_loop and args.collect_input:p.error('Choose sensor collection or actual model diagnostic')
    if args.diagnostic_closed_loop and args.mode!='smoke':p.error('Unvalidated diagnostic is restricted to straight-road smoke')
    if args.diagnostic_closed_loop and not (0<args.diagnostic_age_cap<=4):p.error('Diagnostic TTL must lie within trajectory horizon')
    if args.config:
        config=read_json(args.config)
        allowed={'carla_path','carla_map','port','duration','deployment_config'}
        if set(config)-allowed:p.error('Unknown Stage05 config keys')
        for key,value in config.items():setattr(args,key,Path(value) if key in ('carla_path','deployment_config') else value)
    return run_experiment(args)
if __name__=='__main__':raise SystemExit(main())

