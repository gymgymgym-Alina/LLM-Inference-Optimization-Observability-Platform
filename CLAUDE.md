# 项目背景与上下文（LLM 推理服务性能优化）

> 本文件是项目的完整上下文，供 Claude Code 使用。每次开始工作前先读这份文件。

## 我是谁、目标是什么

应届生，目标岗位 MLE / AI Engineer。这个项目是简历核心项目，用来证明模型部署 + 性能工程能力。**核心资产不是代码，而是真实的实验数据**：通过「压测 → 找瓶颈 → 优化 → 再压测」循环，产出带数字的优化结论（如"dynamic batching 使吞吐量从 X 提升到 Y QPS"）。

前辈建议：不要做"FastAPI + Docker 部署"的教程型项目，要选一个点做深，用 data-driven 的指标证明系统真能扛高并发。本项目按这个思路设计。

## 项目一句话

把 Qwen2.5-1.5B-Instruct 部署成生产级 API 服务，逐轮优化延迟和吞吐量，全程用压测数据记录对比。

## 技术选型（已定，不要更换）

- 模型：Qwen2.5-1.5B-Instruct（HuggingFace transformers 起步）
- API：FastAPI；容器：Docker + docker-compose
- GPU：RunPod / Vast.ai 按小时租（RTX 3090/4090）；部署云：AWS EC2
- 压测：Locust；监控：Prometheus + Grafana
- 优化路线：手写 dynamic batching → 对比 vLLM → AWQ/GPTQ 量化

## 时间线（赶进度版，8/22 前出粗糙可用版本）

1. **7/28–8/3（阶段 1）**：Docker 速成 + baseline 服务（无任何优化的 v0，作为后续对比基准）
2. **8/4–8/9**：Locust 压测 + Prometheus/Grafana 接入，拿到 baseline 数据（P50/P99、QPS、GPU 利用率）
3. **8/10–8/16**：核心环节——用 asyncio 队列手写 dynamic batching（凑满 batch 或超时窗口触发），压测对比；再跑 vLLM 做三方对比
4. **8/17–8/22**：量化（先只测延迟/显存）+ README 技术报告 + 简历 bullet
5. **8/22 之后打磨**：量化精度评估（MMLU 子集）、CI、技术博客、数据漂移报警

## 对 Claude Code 的工作要求（重要，优先于通用代码风格偏好）

1. **每完成一个模块，解释关键设计决策**（为什么这么写、trade-off 是什么）。用户需要在面试中回答追问，不能只有能跑的代码。**每阶段结束时列出 2-3 个面试官最可能问的问题及答案要点。**
2. **实验纪律**：每轮优化只改一个变量；所有压测结果记入根目录 `experiments.md` 表格（日期、配置、并发数、P50/P99、QPS、GPU 利用率）。数据必须来自真实运行，**绝不编造**。
3. **省钱纪律**：代码开发和调试尽量在本地/CPU 上完成，只在跑实验时提醒开 GPU 机器，跑完提醒关。任何涉及云资源创建/计费的操作，先跟用户确认。
4. **简历底线**：简历 bullet 只写已真实测出的数字，不写预测值/典型值。
5. 从第一天起维护 README，最终写成技术报告（架构图、瓶颈分析、每轮优化的动机→方法→数据）。
6. 用户 Docker/云是零基础，Python 熟练。涉及 Docker/云操作时给出逐步命令，并简要解释每条命令的作用。

## 简历 bullet 模板（数字用实测替换，阶段 4 定稿）

- Built and deployed a production-style LLM inference service (Qwen2.5-1.5B, FastAPI, Docker, AWS) with Prometheus/Grafana observability covering latency, throughput, and GPU utilization
- Identified GPU serialization bottleneck via load testing (Locust); implemented asyncio-based dynamic batching, improving throughput from X to Y QPS (N×) and reducing P99 latency by Z% under 100 concurrent users
- Applied INT4 quantization (AWQ), cutting P50 latency by X% and GPU memory by Y% with <Z% accuracy degradation on MMLU subset
- Benchmarked custom batching against vLLM's continuous batching, analyzing scheduling-level differences (request-level vs token-level)

## 当前状态与下一步

当前状态：仓库刚初始化。`week1-docker-basics/` 下有一个和 LLM 无关的 hello-world FastAPI + Docker 练习（验证过 Python 逻辑，Docker 镜像未验证——本机未装 Docker），可以当作 Docker 语法参考，但不是阶段 1 的正式交付物。

**阶段 1 正在进行（验收标准）**：
- `curl` 一个 prompt 能返回模型生成的回复
- Docker 镜像能在 GPU 机器上运行（本地先用 CPU 验证正确性）
- README 有项目简介和运行说明

**阶段 1 范围**：
1. 初始化项目结构（`app/`、Dockerfile、docker-compose、README 骨架、根目录 `experiments.md` 模板）
2. baseline：加载 Qwen2.5-1.5B-Instruct，`POST /generate`（输入 prompt 返回生成文本）+ `/health`，单请求同步推理，故意不做任何优化
3. Docker 化，含 GPU 支持（nvidia-container-toolkit、`--gpus all`），并给出本地 CPU 先跑通验证的方案
4. 教怎么部署到租来的 GPU 机器上跑通一次真实推理
