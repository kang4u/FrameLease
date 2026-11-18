FrameLease 的 Introduction 可以从 背景、挑战、方法、创新点 四个方面进行总结，整体围绕一条核心逻辑：如何在有限计算资源下，根据动作的实际有效性，动态决定继续推理还是刷新观测。
1. 背景（Background）
[num 1/0] VLA（Vision-Language-Action）模型通过融合视觉感知、语义推理与轨迹生成，为自动驾驶提供了更强的决策能力。
[num 1/0] 更深的推理可能提升轨迹质量，但同时带来更高的计算延迟。
[num 1/0] 在实时驾驶中，环境持续变化，推理时间越长，模型所依赖的观测信息就越陈旧。
[num 1/0] 因此，自动驾驶系统面临 推理深度（Reasoning Depth）与观测新鲜度（Observation Freshness）之间的权衡。
2. 挑战（Challenges）
挑战一：推理质量与观测新鲜度存在冲突。
继续 REFINE 可以改善候选轨迹，但也会增加观测年龄；执行 REFRESH 可以获取新信息，却可能中断尚有价值的推理。
挑战二：Observation Age 无法准确表征 Action Validity。
即使两个动作来自相同时间的观测，它们的安全余量和对环境变化的敏感程度也可能不同。因此，固定刷新周期或基于观测年龄的调度难以充分利用计算资源。
挑战三：实时约束下难以选择最有价值的计算操作。
系统不仅需要判断 REFINE 或 REFRESH 是否能够及时完成，还需要比较二者对最终闭环驾驶表现的潜在收益，同时避免执行失效动作。
3. 方法（Methodology）
提出 FrameLease，一种面向实时自动驾驶的动作有效性感知计算调度框架，包含三个相互关联的机制。
① Action-Conditioned Validity Lease
[num 2/0] 利用候选轨迹的时间对齐后缀和残差不确定性包络，估计动作剩余有效时间。
[num 2/0] 将轨迹有效性转换为候选动作专属的截止时间（Validity Deadline）。
[num 2/0] 不再单纯依赖 Observation Age 判断何时刷新。
② Shielded Utility-Aware Scheduling
[num 3/0] Shield 根据动作有效性、执行时间和 GPU 预算筛选合法的 REFINE / REFRESH 操作。
[num 3/0] 轻量 RL 在合法操作中选择预期闭环驾驶收益更高的动作。
[num 3/0] RL 不负责安全保证，且在计算预算不足时可以绕过。
③ Runtime Implementation and Timing Safeguards
[num 4/0] Cooperative Preemption：在允许的计算边界进行任务切换。
[num 4/0] Versioned Commit：防止过期、取消或版本倒退的候选动作进入控制器。
[num 4/0] Budgeted Policy Execution：限制 RL 的执行开销，并提供确定性回退机制。
4. 创新点（Contributions）

[TABLE]
| 创新点 | 核心贡献 | 相比已有方法的区别 |
| C1. Action-Conditioned Validity Lease | 根据轨迹安全余量和不确定性估计动作有效截止时间 | 从 observation-age-based 转向 action-validity-based |
| C2. Shielded Utility-Aware Scheduling | 将动作有效期转化为计算调度约束，并在合法选择中利用 RL 优化驾驶效用 | 不仅判断计算能否按时完成，还判断哪种计算更值得执行 |
| C3. Budget-Aware Runtime Integration | 结合可抢占计算、版本化提交和预算化策略执行 | 将调度决策落实为具有明确执行保护机制的运行时系统 |
[/TABLE]

其中，C1 是关键的系统抽象，C2 是核心调度创新，C3 是系统实现与部署贡献。