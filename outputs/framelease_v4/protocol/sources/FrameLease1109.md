FrameLease：DAC 六页论文最终完整大纲（修订版）
论文定位： 面向资源受限自动驾驶系统的 Action-Validity-Aware Runtime Scheduling。
核心创新主线：
Validity Lease
动作还能有效多久？
Shielded Scheduling
哪些计算选择合法？
Utility Selection
哪个选择收益更大？
Runtime safeguards 为整个决策过程提供计算预算控制、执行验证与故障回退。
本文不是提出一个新的 VLA 模型，也不是提出新的 RL 算法，而是提出一种将动作有效性转化为计算调度约束，并在合法选择中优化闭环驾驶效用的系统方法。
一、最终章节与篇幅分配
|
章节
|
主要内容
|
正文篇幅
|
| --- | --- | --- |
|
I. Introduction
|
问题、洞察、贡献
|
0.70 页
|
|
II. Motivation and Problem Formulation
|
Freshness–Depth 冲突、系统模型、目标
|
0.80 页
|
|
III. FrameLease Design
|
Lease、Shielded RL、Runtime
|
2.30 页
|
|
IV. Evaluation
|
端到端性能、消融、运行时验证
|
1.70 页
|
|
V. Related Work
|
相关研究与区别
|
0.30 页
|
|
VI. Conclusion
|
总结
|
0.20 页
|
|
总计
|
正文六页
|
6.00 页
|
Section III 仍然只保留三个子节，Section IV 只保留两个子节。全文安排约 3 张图、2 张表和 1 个紧凑的算法框。
建议的论文标题：
FrameLease: Action-Validity-Aware Compute Scheduling for Real-Time Autonomous Driving
这个标题强调系统贡献，避免把 RL 或 VLA 加速误写成唯一创新。
I. INTRODUCTION
建议篇幅：0.7 页｜4 个自然段 + 3 条 Contributions
本节不设子标题。只需要清楚回答：为什么现有方案不够、核心新洞察是什么、FrameLease 解决了什么问题。
Paragraph 1 — Background and challenge
说明 VLA 驱动的自动驾驶系统面临计算时间与观测新鲜度之间的冲突。
随着推理深度增加，候选轨迹可能变得更准确，但推理延迟也会增加，导致动作所依据的环境信息逐渐过时。
需要强调：
[num 1/0] Deep inference 不一定产生更好的实际闭环控制。
[num 1/0] Fresh observation 不一定值得立即重新计算。
[num 1/0] 在有限 GPU 预算下，推理深度和刷新频率必须共同决定。
第一段引出核心问题：
When should the system spend its limited compute budget refining an existing action, and when should it refresh the observation instead?
Paragraph 2 — Limitations of existing approaches
集中指出三类现有方案的不足。
Fixed-depth or early-exit inference： 通常聚焦推理质量、退出位置或延迟，但不一定考虑候选动作在持续变化的环境下还能使用多久。
Age-based or event-triggered refresh： 通常依据观测年龄、固定时间阈值或外部事件触发刷新，缺少对具体候选轨迹有效性的分析。
Deadline-aware scheduling： 能决定哪些任务可以在期限内完成，但期限本身未必反映候选动作随时间变化的有效性。
由此引出关键缺口：
Existing scheduling policies do not explicitly couple the time-varying validity of an individual action with the utility of allocating additional computation to refinement or observation refresh.
这段应准确限定到相关工作的具体方法，避免对整个领域作过强概括。
Paragraph 3 — Core insight and FrameLease
提出核心洞察：
Action validity should be determined by the action's predicted trajectory, not observation age alone.
不同轨迹在相同观测年龄下可能具有完全不同的剩余有效时间。
FrameLease 因此引入三个紧密连接的设计：
[num 2/0] Action-Conditioned Validity Lease：由时间对齐轨迹余量与残差不确定性估计候选动作的有效截止时间。
[num 2/0] Shielded Utility-Aware Scheduling：将 lease deadline 用作调度约束，并利用轻量 RL 在合法的 REFINE 和 REFRESH 选择中优化驾驶效用。
[num 2/0] Runtime Safeguards：结合可抢占的推理边界、版本化提交和预算化策略推理，实现可部署的运行时控制。
注意：这三个机制在 Introduction 中只各用一句话，不展开公式。
Paragraph 4 — Contributions
建议最终只保留三条贡献。
C1. Action-conditioned validity abstraction.
We introduce a trajectory-suffix-based validity lease that characterizes how long a candidate driving action remains admissible under a residual uncertainty envelope.
C2. Validity-constrained utility-aware scheduling.
We design a shielded scheduler that derives feasible compute choices from action-validity deadlines and uses a lightweight learned policy to optimize driving utility within the admissible action set.
C3. Runtime integration and evaluation.
We implement a budget-aware runtime with cooperative preemption, versioned action commitment, and deterministic fallback, and evaluate its driving performance and timing behavior under constrained computing resources.
第三条的实测结论，等 Evaluation 数据确定后再补入可量化的结果，不能预先虚构提升比例。
II. MOTIVATION AND PROBLEM FORMULATION
建议篇幅：0.8 页｜无二级标题｜Fig. 1
本节承担两个任务：用实验现象建立问题必要性，再定义调度系统的输入、输出及优化目标。
Paragraph 1 — Freshness–Depth conflict
Fig. 1. The Freshness–Depth Tradeoff in VLA-Based Driving
Deep@Old
推理充分，但环境可能已变化
Fast@Fresh
观测更新快，但动作推理可能不足
以上仅为动机示意，不代表已有实测结果。正式论文应以 pilot profiling 或闭环实验数据绘制 crossover。
正文强调：
[num 3/0] 更多 refinement 可能改善候选轨迹，但消耗时间。
[num 3/0] 刷新观测能够减少信息陈旧，但会中断或重启部分推理。
[num 3/0] 两者的相对收益取决于环境、已有动作的有效性以及剩余计算资源。
Fig. 1 最好包含真实的 crossover 证据，而不只是概念示意图。
Paragraph 2 — System model
定义系统变量。
在时刻 tkt_ktk，系统获取观测 oko_kok，VLA 模型生成候选动作轨迹 ξkj\xi_k^jξkj，其中 jjj 表示 refinement 阶段或候选版本。
运行时可以选择：
A={REFINE,REFRESH}.\mathcal A= \{\mathrm{REFINE},\mathrm{REFRESH}\}.A={REFINE,REFRESH}.
REFINE 使用额外计算改善当前候选轨迹；REFRESH 获取更新的观测并启动相应推理。
系统受到 GPU 计算预算、任务运行时间和控制动作有效性的约束。
特别明确：REFINE 不改变原始观测时间戳 tkt_ktk，只有 REFRESH 获取新观测后才更新它。
Paragraph 3 — Optimization objective
以闭环驾驶表现作为唯一主效用目标：
max⁡μθEμθ $Sdrive$ \max_{\mu_\theta} \mathbb E_{\mu_\theta} \left $S_rmdriveright$ μθmaxEμθ $Sdrive​$
subject to
action validity constraints,runtime timing constraints,GPU resource budget.\begin{aligned} &\text{action validity constraints},\\ &\text{runtime timing constraints},\\ &\text{GPU resource budget}. \end{aligned}action validity constraints,runtime timing constraints,GPU resource budget.
其中 μθ\mu_\thetaμθ 为调度策略，不是底层 VLA 模型本身。
说明这些约束分别由 Lease、Shield 和 Runtime 执行机制落实。这里不提前定义复杂的 lease 公式，也不介绍 Q-Network。
本节最后一句自然衔接 Section III：
FrameLease addresses this constrained scheduling problem by translating action validity into compute deadlines and selecting useful computation only among admissible choices.
III. FRAMELEASE DESIGN
建议篇幅：2.3 页｜整篇论文的技术核心｜Fig. 2 + Algorithm 1
建议分配：
|
子节
|
篇幅
|
核心任务
|
| --- | --- | --- |
|
III-A. Action-Conditioned Validity Lease
|
0.70 页
|
从轨迹有效性得到截止时间
|
|
III-B. Shielded Utility-Aware Scheduling
|
1.05 页
|
在合法计算选择中优化驾驶效用
|
|
III-C. Runtime Implementation and Timing Safeguards
|
0.55 页
|
实现低开销调度、提交保护和回退
|
Section III 开头只用一小段总述，结合 Fig. 2 介绍系统数据流。
Fig. 2. FrameLease Runtime Architecture
建议采用以下结构：
Observation + VLA Candidate Trajectory
Timestamp · Candidate Version · Trajectory
Validity Lease Estimator
Trajectory suffix · Uncertainty bound · Deadline
Real-Time Shield
Validity · Timing · GPU Budget
CPU Q-Policy
If both feasible
Default Policy
Forced / Bypassed
GPU Dispatch
REFINE / REFRESH · Cooperative Preemption
Versioned Commit + Watchdog
Final Validity Check · Controller / Fallback
这是论文架构图的逻辑草图。正式排版建议加入 CPU/GPU 泳道，以及从 GPU 输出返回 Lease Estimator 的反馈箭头。
这张图应让读者一眼看清：Lease 不直接决定调度动作，Shield 先筛选合法选择，RL 仅负责可行集合内的效用排序，最终动作仍须接受提交检查。
A. Action-Conditioned Validity Lease
0.70 页｜建议 4 个自然段、3 组公式、1 个简短 Proposition
本节核心问题：How long can a candidate action remain valid?
Paragraph 1 — Candidate trajectory and nominal margin
在观测时间 tkt_ktk，VLA 生成第 jjj 个候选轨迹：
ξkj(τ),τ∈ $0,Tpred$ .\xi_k^j(\tau),\qquad \tau\in $0,T_rmpred$ .ξkj(τ),τ∈ $0,Tpred​$ .
其中 τ\tauτ 是相对于观测时间 tkt_ktk 的轨迹时间，TpredT_{\rm pred}Tpred 为预测覆盖时长。
定义：
[num 4/0] mkj(τ)m_k^j(\tau)mkj(τ)：候选轨迹在时间 τ\tauτ 的名义安全余量。
[num 4/0] Δ=t−tk\Delta=t-t_kΔ=t−tk：当前观测年龄。
[num 4/0] TcT_cTc：准备提交的动作需要覆盖的控制执行时长。
[num 4/0] Bkj(Δ,τ)B_k^j(\Delta,\tau)Bkj(Δ,τ)：由于观测陈旧、预测残差、动态扰动等因素引入的安全余量误差包络。
如果安全约束不止一个，可以先将各约束余量归一化，再取最小余量。
这里不展开车辆动力学或可达集算法，只引用或说明不确定性包络如何获得，并明确其适用假设。
Paragraph 2 — Residual uncertainty and suffix-aligned margin
定义在观测年龄 Δ\DeltaΔ 时，候选动作在未来控制时域内的保守余量：
Mkj(Δ)=min⁡τ∈ $Δ,Δ+Tcmkjτ-BkjΔτ$ (1)\boxed{ M_k^j(\Delta)= \min_{\tau\in $Delta,Delta+T_c$ } \left $m_kjtau-B_kjDeltatauright$  } \tag{1}Mkj(Δ)=τ∈ $Δ,Δ+Tc​$ min $mkj​τ-Bkj​Δτ$ (1)
这里必须强调 trajectory suffix alignment。
系统在 tk+Δt_k+\Deltatk+Δ 时刻执行动作，不需要重新评估已经过去的轨迹前缀，而应评估与当前时间对齐的未来轨迹后缀。
相较于直接使用整个预测区间上的 global minimum margin，suffix-aligned margin 可以避免过去某个低余量时刻永久限制后续调度。
但也要指出：这种减小保守性的收益取决于误差包络是否充分覆盖实际轨迹偏差。
Paragraph 3 — First-failure validity horizon
定义预测覆盖所允许的最大年龄：
Hˉ=max⁡(0,Tpred−Tc).\bar H=\max(0,T_{\rm pred}-T_c).Hˉ=max(0,Tpred−Tc).
若 Tpred<TcT_{\rm pred}<T_cTpred<Tc，则候选动作不具备所要求的完整预测覆盖，设其有效期为零。
其余情况下：
Hkj=inf⁡({Δ∈ $0,Hˉ$ :Mkj(Δ)≤δ}∪{Hˉ})(2)\boxed{ H_k^j= \inf\left( \left\{ \Delta\in $0,barH$ : M_k^j(\Delta)\leq\delta \right\} \cup\{\bar H\} \right) } \tag{2}Hkj=inf({Δ∈ $0,Hˉ$ :Mkj(Δ)≤δ}∪{Hˉ})(2)
其中 δ\deltaδ 为所需的安全余量阈值。
这一形式同时处理：
[num 5/0] 安全余量首次失效；
[num 5/0] 预测覆盖耗尽；
[num 5/0] 没有在预测范围内发生余量失效；
[num 5/0] 余量可能非单调变化的情况。
特别说明，即使后续 Mkj(Δ)M_k^j(\Delta)Mkj(Δ) 又恢复为正值，也不允许跳过首次失效时间继续使用原 lease。
动作有效截止时间定义为：
Dkj=tk+Hkj(3)\boxed{ D_k^j=t_k+H_k^j } \tag{3}Dkj=tk+Hkj(3)
所有截止时间比较都采用统一的单调时钟。生成新 refinement 候选不会改变其源观测时间戳。
Paragraph 4 — Validity property and assumptions
加入一个短小的命题：
Proposition 1 — Conditional Lease Validity.
假设 residual uncertainty envelope 对真实轨迹余量误差提供有效上界，即实际安全余量不小于 mkj(τ)−Bkj(Δ,τ)m_k^j(\tau)-B_k^j(\Delta,\tau)mkj(τ)−Bkj(Δ,τ)。
那么，对于任何满足 0≤Δ<Hkj0\leq\Delta<H_k^j0≤Δ<Hkj 的有效候选，在对应的  $Δ,Δ+TcDelta,Delta+T_cΔ,Δ+Tc​$ 控制时域上，其实际轨迹余量不低于 δ\deltaδ。
证明只需利用式 (1) 和首次失效的定义。
但必须区分：
[num 6/0] 确定性误差上界： 命题可以给出所定义模型约束下的条件性保证。
[num 6/0] 统计标定的误差包络： 需要报告覆盖率，不能将经验置信度表述为无条件的安全保证。
这段的价值不是增加理论篇幅，而是让 Lease 成为一个定义明确、可检验的系统抽象。
本节最后一句：
The resulting action-specific deadline provides a dynamic computational horizon for deciding whether to refine the current candidate or refresh the observation.
B. Shielded Utility-Aware Scheduling
1.05 页｜全篇最重要的系统设计小节
本节核心问题：Which feasible compute operation provides higher expected driving utility?
这里将 Real-Time Shield 和 Lightweight RL 统一为同一个调度器的两个层次，不单独设置 RL 章节。
Paragraph 1 — Scheduling actions and decision epochs
系统在 refinement quantum 完成、候选更新或其他允许的调度边界进行决策。
调度动作集合：
A={REFINE,REFRESH}.(4)\mathcal A= \{\mathrm{REFINE},\mathrm{REFRESH}\}. \tag{4}A={REFINE,REFRESH}.(4)
REFINE：继续计算当前观测对应的候选轨迹。
REFRESH：取得新观测并执行能够生成下一可用候选所需的计算。
调度时刻不一定等间隔，因为 refinement quantum、GPU 排队和刷新计算的运行时间可能不同。
因此，可以将该问题表述为有限回合的半马尔可夫决策过程，但不必专门设置 SMDP 子小节。
Paragraph 2 — Action-specific feasibility shield
这是相对原方案最重要的数学调整。
定义当前控制器所使用的已验证动作的截止时间为 D∗D^\astD∗，或在已切换到经过验证的降级控制模式时，使用该模式对应的受保护时间界。
对于每种调度动作 aaa，定义：
[num 7/0] LabndL_a^{\rm bnd}Labnd：该调度操作的时间预算，包括相关的 GPU 计算、排队或边界切换开销。
[num 7/0] LπbndL_\pi^{\rm bnd}Lπbnd：CPU 调度策略的时间预算。
[num 7/0] LcommitbndL_{\rm commit}^{\rm bnd}Lcommitbnd：结果验证与提交时间预算。
[num 7/0] RabndR_a^{\rm bnd}Rabnd：根据设计需要保留的恢复计算预算。
[num 7/0] ϵ\epsilonϵ：时序保护余量。
[num 7/0] GremG_{\rm rem}Grem：剩余 GPU 资源预算。
最终可行集合：
Afeas(st)={a∈A:  Ca(st)=1,G(a)≤Grem,t+Lπbnd+Labnd+Lcommitbnd+Rabnd+ϵ<D∗}.(5)\boxed{ \begin{aligned} \mathcal A_{\rm feas}(s_t) =\{a\in\mathcal A:\;&C_a(s_t)=1,\\ &G(a)\leq G_{\rm rem},\\ &t+L_\pi^{\rm bnd} +L_a^{\rm bnd}\\ &+L_{\rm commit}^{\rm bnd} +R_a^{\rm bnd} +\epsilon<D^\ast\}. \end{aligned} } \tag{5}Afeas(st)={a∈A:Ca(st)=1,G(a)≤Grem,t+Lπbnd+Labnd+Lcommitbnd+Rabnd+ϵ<D∗}.(5)
其中 Ca(st)C_a(s_t)Ca(st) 包括该操作的前置有效性检查，以及对应结果能否合法使用的条件。
这里需要明确两个动作的区别。
REFINE： 必须检查当前候选尚未失效、继续 refinement 所需计算预算是否充足，以及是否仍能及时完成结果验证。若系统要求保留完整的刷新恢复路径，可以设置 RREFINEbndR_{\rm REFINE}^{\rm bnd}RREFINEbnd 为对应的恢复预算。
REFRESH： 必须检查刷新操作自身的完成时间与资源需求，包括获取新观测以及产生首个可用动作所需的计算。若不需要再预留额外恢复操作，可取 RREFRESHbnd=0R_{\rm REFRESH}^{\rm bnd}=0RREFRESHbnd=0。
这避免了无条件将 refinement 与 refresh 的全部执行时间同时相加造成的过度保守。
特别注意： 如果式 (5) 中的 LbndL^{\rm bnd}Lbnd 只是由 P99 profiling 得到的经验预算，那么它只能提供相应假设下的软实时准入，而不能宣称无条件硬实时保证。
Paragraph 3 — Lightweight utility-aware RL
Shield 确定可行集合后，轻量 RL 只在其中进行效用选择：
at∗=arg⁡max⁡a∈Afeas(st)Qθ(st,a)(6)\boxed{ a_t^\ast= \arg\max_{a\in\mathcal A_{\rm feas}(s_t)} Q_\theta(s_t,a) } \tag{6}at∗=arga∈Afeas(st)maxQθ(st,a)(6)
建议将 RL 的设计压缩为一个连续段落，包含以下信息。
|
组成
|
最终设计
|
| --- | --- |
|
State
|
约 16 维标量
|
|
Key features
|
Lease slack、observation age、refinement progress、GPU budget、runtime latency
|
|
Action
|
REFINE / REFRESH
|
|
Objective
|
Maximization of closed-loop driving score
|
|
Training
|
Offline finite-horizon, undiscounted Fitted Q-Learning
|
|
Deployment
|
小型固定权重 CPU Q-Network
|
|
Decision scope
|
仅在两种动作都可行且策略预算允许时运行
|
尤其要保留 lease slack：
slease=D∗−t.s_{\rm lease}=D^\ast-t.slease=D∗−t.
这是连接 validity abstraction 和学习策略的关键状态特征。
不应只是把 observation age 与 refinement depth 输入 DQN，然后声称具备 action awareness。
Paragraph 4 — Reward and offline training
使用与论文整体目标一致的驾驶得分。
若存在一致且可加的前缀得分 SnS_nSn，则：
rn=Sn+1−Sn.(7)r_n=S_{n+1}-S_n. \tag{7}rn=Sn+1−Sn.(7)
由此可以使整个 episode 的累计奖励与最终评分变化一致。
如果驾驶评分只在完整 episode 结束时有效，则采用 terminal-only reward，中间奖励设为零。
训练采用有限回合、无折扣的 Fitted Q-Learning：
Qθ(sn,an)←rn+max⁡a′∈Afeas(sn+1)Qθˉ(sn+1,a′).Q_\theta(s_n,a_n) \leftarrow r_n+ \max_{a'\in\mathcal A_{\rm feas}(s_{n+1})} Q_{\bar\theta}(s_{n+1},a').Qθ(sn,an)←rn+a′∈Afeas(sn+1)maxQθˉ(sn+1,a′).
这是示意性的非终止转移目标；终止状态不包含 bootstrap 项。实际训练需考虑离线数据的动作覆盖和分布外动作估值问题。
本段只需解释三点：
[num 8/0] 决策间隔不等长，因此需要基于实际调度转移建模。
[num 8/0] 训练目标与完整闭环驾驶评分一致，不额外引入难以解释的多个 reward。
[num 8/0] 离线训练、不在线探索，部署时只有固定参数的轻量 CPU 推理。
不展开网络层数、优化器细节和长篇 RL 推导。
Paragraph 5 — Unified shielded decision
给出整个调度器的最终决策规则：
at={arg⁡max⁡a∈Afeas(st)Qθ(st,a),if both feasible and policy budget permits,adet(st),if a feasible choice exists otherwise,FALLBACK,if Afeas(st)=∅.(8)\boxed{ a_t= \begin{cases} \displaystyle \arg\max_{a\in\mathcal A_{\rm feas}(s_t)} Q_\theta(s_t,a), & \text{if both feasible and policy budget permits},\\ $6pt$  a_{\rm det}(s_t), & \text{if a feasible choice exists otherwise},\\ $4pt$  \mathrm{FALLBACK}, & \text{if }\mathcal A_{\rm feas}(s_t)=\varnothing . \end{cases} } \tag{8}at=⎩⎨⎧arga∈Afeas(st)maxQθ(st,a),adet(st),FALLBACK,if both feasible and policy budget permits,if a feasible choice exists otherwise,if Afeas(st)=∅.(8)
其中 adet(st)a_{\rm det}(s_t)adet(st) 必须从合法集合中选择。
FALLBACK 是独立的控制降级路径，不属于 RL 的两个调度动作。
这样也解决了原方案容易忽略的三个边界情况：
[num 9/0] 只有一个动作可行时，不调用 RL。
[num 9/0] CPU 策略计算预算不足时，直接执行确定性合法选择。
[num 9/0] 没有合法调度动作时，进入经过验证的降级控制路径，而不是强制选择 REFINE 或 REFRESH。
最后强调：无论动作来自 RL 还是确定性策略，真正提交新的控制动作前，都必须重新进行有效性验证。
这一节的核心技术主张应该是：
The validity lease dynamically shapes the feasible compute-action set, while the learned policy optimizes driving utility only within that set.
重点不是 RL 决定安全，而是 Shield 负责准入，RL 负责价值判断。
C. Runtime Implementation and Timing Safeguards
0.55 页｜运行时机制 + Algorithm 1
本节核心问题：How is the scheduling decision executed without introducing uncontrolled latency or stale-action commitment?
建议将原来的 Timing Guarantees 改成 Timing Safeguards，因为当前设计包含经验 profiling 的预算估计，而不是天然具有完整的硬实时证明。
Paragraph 1 — Cooperative preemption
VLA refinement 被组织为一系列可支持的计算 quantum。
GPU 调度只在允许的 quantum 边界进行切换，不承诺任意 kernel 级别的抢占。
需要说明：
[num 10/0] 单个不可抢占 quantum 的延迟；
[num 10/0] 在当前 GPU 执行边界切换的开销；
[num 10/0] REFRESH 对正在运行的 refinement 的处理方式；
[num 10/0] 被取消任务的计算结果如何处理。
这些开销应该进入调度的时间预算或运行时测量。
Paragraph 2 — Versioned commit
每个候选动作带有观测版本、refinement 版本、源观测时间戳和对应 lease deadline。
提交动作至少检查：
tcommit<Dkj,Mkj(tcommit−tk)>δ,candidate version is admissible,candidate is not cancelled.(9)\begin{aligned} &t_{\rm commit}<D_k^j,\\ &M_k^j(t_{\rm commit}-t_k)>\delta,\\ &\text{candidate version is admissible},\\ &\text{candidate is not cancelled}. \end{aligned} \tag{9}tcommit<Dkj,Mkj(tcommit−tk)>δ,candidate version is admissible,candidate is not cancelled.(9)
还必须满足相应的预测覆盖、轨迹验证和控制器接收条件。
版本比较要区分：
[num 11/0] 同一观测下新的 refinement 版本；
[num 11/0] 新观测产生的新候选；
[num 11/0] 较旧观测上的延迟完成结果。
一个晚完成的旧观测结果，不能覆盖控制器已经采用的更新观测版本。
这形成重要的程序级不变量：
Expired, cancelled, invalid, or regressive candidates must never be committed.
Watchdog 独立检查控制线程和有效截止时间，异常时触发已验证的 fallback。Fallback 本身的执行时间、有效性和适用范围也必须经过独立验证。
Paragraph 3 — Budgeted CPU policy execution
Q-Network 使用固定网络结构、预分配缓冲区以及有界的 CPU 推理调用。
策略运行不能阻塞控制线程。
当预算不足、超时或被强制调度条件覆盖时：
[num 12/0] 跳过 RL；
[num 12/0] 使用确定性合法策略；
[num 12/0] 依然执行最终 commit verification。
这里不需要详细展示 CPU 网络结构，只要说明运行方式和可测量开销。
Algorithm 1 — FrameLease Runtime Scheduler
建议采用一个紧凑的伪代码框：
Input: Observation, candidate, runtime state
1: Update candidate timestamp and version
2: Estimate suffix validity M and deadline D
3: At each scheduling boundary:
4:    Check active-action validity and GPU budget
5:    Build feasible set using the shield
6:    if no action is feasible:
7:        Trigger fallback and recovery
8:    else if policy budget permits and both feasible:
9:        Select action using Q-policy
10:   else:
11:       Select deterministic feasible action
12:   Dispatch at a supported GPU boundary
13:   On completion, recompute candidate validity
14:   Commit only if deadline and version checks pass
正文结束前用一句话区分两种保证：
严格的版本与提交检查可以形成程序不变量；端到端时间保证是否成立，则取决于采用的是可证明的运行时间上界，还是经验 profiling 预算。
后者必须用真实硬件延迟和 deadline miss 数据验证。
IV. EVALUATION
建议篇幅：1.7 页｜两个子节｜Fig. 3 + Table I + Table II
Evaluation 的核心目标是建立一条完整的实验证据链：
Action-conditioned lease 有效 → Shielded scheduling 改善计算分配 → RL 带来独立增益 → Runtime 开销可控。
不要将实验拆成六七个零散的小节，也不要把大量篇幅消耗在常规超参数介绍上。
A. End-to-End Performance
0.95 页｜实验设置 + 主性能表 + Pareto 图
本节核心问题：Does FrameLease improve closed-loop driving performance under the same compute budget?
Paragraph 1 — Experimental setup
开头用一个紧凑段落交代：
|
项目
|
需要报告的设置
|
| --- | --- |
|
Benchmark
|
Bench2Drive 闭环场景与测试划分
|
|
Model
|
VLA backbone、refinement 方式
|
|
Hardware
|
GPU、CPU、内存与软件运行环境
|
|
Runtime
|
控制周期、GPU 预算、quantum 配置
|
|
Evaluation
|
场景数量、随机种子、成功率与驾驶评分
|
需要说明 RL 的训练场景与测试场景是否严格分离，并尽可能避免通过测试集反复调整调度超参数。
不单独创建 Experimental Setup 子节。
Paragraph 2 — Main benchmark comparison
Table I. End-to-End Driving Performance under Matched Compute Budgets
建议比较以下七种方法：
|
Baseline
|
比较目的
|
| --- | --- |
|
Fixed Deep
|
固定深度推理
|
|
Fast Only
|
高刷新、浅推理
|
|
Age-Only
|
基于固定观测年龄阈值刷新
|
|
Event-Triggered
|
基于事件或场景变化触发刷新
|
|
Original FrameLease
|
已有或先前版本的调度方法
|
|
FrameLease + Heuristic
|
同样的 Lease 和 Shield，确定性效用选择
|
|
Full FrameLease
|
Suffix Lease + Shield + RL + Runtime
|
这里必须精确定义 Original FrameLease 与 Full FrameLease 的实现差异。不能用一个含义不明确的“原始版本”作为主要对照。
主表优先包含：
[num 13/0] Driving Score：主要指标。
[num 13/0] Success Rate：闭环任务成功率。
[num 13/0] Collision / Infraction：安全相关结果。
[num 13/0] GPU usage：计算资源使用情况。
[num 13/0] Deadline Miss Rate：时序表现。
所有主要方法应使用相同的 VLA backbone、评测场景、GPU 资源约束及控制配置。
Paragraph 3 — Freshness–quality frontier
Fig. 3. Driving Score versus Action Age under Constrained GPU Budgets
图表选项
Illustrative Freshness–Quality Frontier
Synthetic data for figure planning only, not experimental results.
仅演示预期图形形式，全部数值为示意数据。正式论文必须替换为真实实验结果，并用不同标记区分各调度方法。
这张图应展示不同调度方法的 Driving Score–Action Age 权衡关系。
但要注意一个重要问题：FrameLease 并不是以最小化 Action Age 为目标。
它有时会允许“年龄较高但仍有效”的动作继续执行，从而节省计算并提高驾驶效用。因此不能简单把越低的 age 解释为越好。
建议在图注或相邻文字中同时交代有效性违规情况以及 GPU 预算，避免 Pareto 图造成错误结论。
Paragraph 4 — Main findings
建议以三句话总结主要结果，最终填入真实数据：
[num 14/0] Full FrameLease 相比固定深度和固定刷新方法，在相同预算下改善闭环驾驶表现。
[num 14/0] Action-aware scheduling 相比 Age-Only 和 Event-Triggered 更有效地利用计算资源。
[num 14/0] RL 相比共享相同 Shield 的 heuristic 进一步改善调度效用。
第三条只有在实验结果支持时才能成立。如果收益不明显，应如实分析，而不是将不显著差异包装成核心贡献。
B. Mechanism Ablation and Runtime Overhead
0.75 页｜Table II + 简短消融分析 + Runtime 测量
本节核心问题：Why does FrameLease work, and can the runtime execute it reliably?
建议按三个层次组织实验，但不再增加三级标题。
Paragraph 1 — Validity lease ablation
对比：
[num 15/0] Age-Only Lease；
[num 15/0] Global-Margin Lease；
[num 15/0] Suffix-Aligned Lease。
优先报告以下指标：
|
指标
|
希望验证的性质
|
| --- | --- |
|
Validity violation rate
|
是否错误地允许失效动作继续使用
|
|
Lease utilization
|
是否充分利用有效时间窗口
|
|
Premature refresh rate
|
是否减少不必要的提前刷新
|
|
Driving Score
|
更有效的 lease 是否带来闭环收益
|
最关键的是：Suffix Lease 不应只是让截止时间变长，而应当在相近的有效性风险水平下，提供更大的可利用计算窗口。
如果 BkjB_k^jBkj 来源于统计标定，还应报告包络覆盖率或经验失效率。
Paragraph 2 — RL contribution ablation
建议对比：
[num 16/0] Shield + Heuristic；
[num 16/0] Shield + Contextual Bandit；
[num 16/0] Shield + Fitted Q-Learning；
[num 16/0] Full RL without Lease-Slack Features。
其中第四项非常关键，因为它能直接验证动作有效期信息对学习调度策略是否有帮助。
还应报告：
Pboth=Pr⁡(∣Afeas(st)∣=2).P_{\rm both}= \Pr\left( |\mathcal A_{\rm feas}(s_t)|=2 \right).Pboth=Pr(∣Afeas(st)∣=2).
即两种动作均可行的决策比例。
如果这个比例非常低，就意味着 RL 很少拥有真正的决策自由度，必须谨慎解释其收益。
最好同时报告 RL 相对 heuristic 的增益随不同场景类别、GPU 预算和随机种子的变化，而不仅给出单次最佳结果。
Paragraph 3 — Runtime timing and robustness
保留真实硬件开销测量，不建议删除。
至少报告：
[num 17/0] CPU Q-Network inference：P50、P99。
[num 17/0] Shield + Lease computation：P50、P99。
[num 17/0] GPU quantum blocking / switching latency。
[num 17/0] Versioned commit overhead。
[num 17/0] Deadline miss rate。
[num 17/0] Policy bypass 和 fallback 触发次数。
测试应覆盖正常运行与资源竞争、接近截止时间、任务取消等压力条件。
Table II. Mechanism Ablations and Runtime Overhead
建议将 Table II 组织为两个紧凑 panel。
|
Panel
|
内容
|
目的
|
| --- | --- | --- |
|
A. Ablations
|
Global vs Suffix；Heuristic vs Bandit vs RL；No Lease Feature
|
证明每项设计的独立贡献
|
|
B. Runtime
|
Policy P99、Shield P99、Preemption、Deadline Miss、Fallback
|
证明系统实际可运行
|
两组结果可以在同一个表编号下排成上下两个 panel，以适应六页篇幅。
V. RELATED WORK
建议篇幅：0.3 页｜3 个紧凑段落｜不设子节
Related Work 不能单纯罗列参考文献，应该围绕 FrameLease 的三项核心区别展开。
Paragraph 1 — Efficient and Asynchronous VLA Inference
讨论 VLA early exit、动态计算深度、自适应推理和异步控制。
重点定位 DeeAD、EagleVLA 等相关方向的具体机制及适用范围。
需要强调的区别是：FrameLease 关注当前候选动作在未来执行时域内是否仍然有效，并据此决定是否继续计算或更新观测。
Paragraph 2 — Freshness-Aware and Event-Triggered Scheduling
讨论 Age of Information、事件触发控制及 deadline-aware scheduling。
指出 observation age 是信息新鲜度的重要代理指标，但同一 age 下不同轨迹的剩余有效性可能不同。
FrameLease 通过 trajectory-specific margin 和 uncertainty envelope 获得 action-conditioned deadline。
Paragraph 3 — Safety-Aware Runtime and Adaptive Scheduling
讨论实时系统中的 admission control、runtime shield、计算资源调度及安全回退。
说明 FrameLease 的重点不是单独提出 RL 或 preemption，而是将 action validity、feasible compute allocation 和 utility-aware selection 整合在同一执行框架中。
避免在这一节宣称“first-ever”，除非文献对比确实支持这一判断。
VI. CONCLUSION
建议篇幅：0.2 页｜一个自然段，约 80–110 个英文单词
结论只做三件事。
首先，重申问题：有限计算预算下，VLA 推理面临 refinement depth 与 observation freshness 的动态冲突。
其次，总结方法：FrameLease 利用 action-conditioned validity lease 约束计算调度，并通过 shielded utility-aware policy 在合法选择中优化闭环驾驶效用。
最后，总结实验：使用实际得到的驾驶性能提升、时序开销和关键消融结果支持方法有效性，同时准确限定其安全和时间保证条件。
不要在 Conclusion 引入未来架构、新的算法细节或未经验证的安全宣称。
七、最终图表安排
|
编号
|
内容
|
建议位置
|
重要性
|
| --- | --- | --- | --- |
|
Fig. 1
|
Freshness–Depth crossover
|
Section II
|
高
|
|
Fig. 2
|
FrameLease runtime architecture
|
Section III 开头
|
必须
|
|
Fig. 3
|
Driving Score–Action Age frontier
|
Section IV-A
|
高
|
|
Table I
|
End-to-end benchmark comparison
|
Section IV-A
|
必须
|
|
Table II
|
Mechanism ablation + timing
|
Section IV-B
|
必须
|
|
Algorithm 1
|
FrameLease runtime scheduler
|
Section III-C
|
高
|
六页论文里，最不建议压缩的是 Table I、Table II 和关键运行时开销。如果篇幅紧张，优先缩短常规背景、公式后重复解释及网络训练细节。
Algorithm 1 可以设计成非常紧凑的单栏算法框；Fig. 2 可以合并一个很小的 CPU/GPU 时序示意，避免新增独立时间线图。
八、写作时必须保持一致的五个技术定义
这是最终大纲中最需要统一的地方。
|
对象
|
统一定义
|
| --- | --- |
|
Observation timestamp tkt_ktk
|
只有获得新观测时更新；refinement 不重置 age
|
|
Validity deadline DkjD_k^jDkj
|
来源于 candidate-specific suffix validity，不是任意固定时长
|
|
Feasible action set
|
每种操作独立进行有效性、时间预算、资源及恢复路径检查
|
|
RL policy
|
只在多个合法动作可选且 CPU 预算允许时执行
|
|
Timing guarantees
|
区分程序不变量、条件性安全性质和基于 profiling 的软时序预算
|
特别强调：候选动作的有效性证明、调度操作是否能按时完成、以及控制器最终是否允许提交，是三个不同的判断。 不要把它们合并成一个模糊的 safe deadline。
九、可以直接使用的 LaTeX 目录
LaTeX
\section{Introduction}
\section{Motivation and Problem Formulation}
\section{FrameLease Design}
\subsection{Action-Conditioned Validity Lease}
\subsection{Shielded Utility-Aware Scheduling}
\subsection{Runtime Implementation and Timing Safeguards}
\section{Evaluation}
\subsection{End-to-End Performance}
\subsection{Mechanism Ablation and Runtime Overhead}
\section{Related Work}
\section{Conclusion}
十、我对这版大纲的最终判断
这版可以作为正式写作的固定结构，不建议继续增加一级或二级章节。
它相比之前最大的改进有三个：
第一，Lease 成为了可分析的技术贡献。 它不仅是预测 deadline 的公式，而是具有首次失效语义、预测覆盖边界和条件性有效性性质的系统抽象。
第二，Shield 与 RL 形成一个统一的调度方法。 Shield 将 action validity 转化为可行计算集合，RL 在这一集合内部选择效用较高的计算动作。这样即使没有学习策略，系统仍然有完整的确定性执行路径。
第三，系统正确性与性能收益被明确区分。 Versioned Commit、Watchdog 和 Budgeted Policy Execution 负责运行时保护；闭环 Driving Score 证明调度有用；硬件延迟测量说明部署成本；它们不再互相替代。
我建议整篇论文始终围绕以下一句话展开：
FrameLease turns action-specific validity horizons into runtime compute constraints and optimizes the refinement–refresh tradeoff through shielded utility-aware scheduling.
如果最终的实验确实支持这条主张，这份大纲就能形成一条比较完整的 DAC Systems 论文论证链：
真实系统冲突 → 新的有效性抽象 → 受约束的调度方法 → 可执行的 Runtime → 可量化的闭环收益。
下一步应该直接按这个大纲写 Section III。 建议先完成 III-A 的 Lease 定义与有效性命题，再完成 III-B 的准入条件和 RL 目标，最后用 III-C 将它们落实到统一算法。这样可以先锁定论文中最核心、也最容易受到技术质疑的部分。
Illustrative Freshness–Quality Frontier
Synthetic data for figure planning only, not experimental results.

[TABLE]
| age | score |
| 85 | 53 |
| 115 | 66 |
| 145 | 62 |
| 180 | 75 |
| 205 | 72 |
| 245 | 61 |
[/TABLE]
