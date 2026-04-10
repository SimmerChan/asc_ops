# 昇腾仓PR/Commit采样分析报告

**分析日期**: 2026-04-10

**采样范围**: 6个昇腾算子仓


## HierarchicalKV-ascend

| 指标 | 值 |
|------|-----|
| 总commits | 16 |
| Bugfix | 6 (37.5%) |
| Optimization | 2 (12.5%) |
| Feature | 6 (37.5%) |
| Bugfix有issue引用 | 0.0% |
| Bugfix有详细描述 | 100.0% |
| 平均消息长度 | 29.4字符 |

### Bugfix示例

- [fix]适配bisheng修改arch编译选项
- [fix]解决benchmark内存泄漏问题
- [fix]修复新版本CANN当SOC_VERSION为小写时coredump的bug

### Optimization示例

- [feat][HKV][A5]find_or_insert_ptr性能优化
- [feat]readme&&run.sh&&构建输出优化

## fbgemm-ascend

| 指标 | 值 |
|------|-----|
| 总commits | 13 |
| Bugfix | 3 (23.1%) |
| Optimization | 0 (0.0%) |
| Feature | 6 (46.2%) |
| Bugfix有issue引用 | 0.0% |
| Bugfix有详细描述 | 66.7% |
| 平均消息长度 | 30.2字符 |

### Bugfix示例

- [fix][A5][ops]同步block_bucketize_sparse_features检视意见修改 - main
- [fix][A5][ops]同步 block_bucketize_sparse_features 算子优化
- [fix]修改复制错误

## ops-nn

| 指标 | 值 |
|------|-----|
| 总commits | 100 |
| Bugfix | 27 (27.0%) |
| Optimization | 5 (5.0%) |
| Feature | 68 (68.0%) |
| Bugfix有issue引用 | 3.7% |
| Bugfix有详细描述 | 77.8% |
| 平均消息长度 | 28.8字符 |

### Bugfix示例

- repeat_interleave_grad 核数大于64精度异常修复
- 修复dynamicquantv2 warning提示
- 修复NPU_ARCH 5102平台的QuantBatchMatmulV3 tiling误拦截

### Optimization示例

- 优化TopkV2算子与aclSetAclOpExecutorRepeatable接口的兼容性
- modified md files(for readability improvement)
- conv3d_backprop_filter_v2 新增StreamK模板，确定性计算性能优化

## ops-math

| 指标 | 值 |
|------|-----|
| 总commits | 100 |
| Bugfix | 26 (26.0%) |
| Optimization | 5 (5.0%) |
| Feature | 69 (69.0%) |
| Bugfix有issue引用 | 3.8% |
| Bugfix有详细描述 | 88.5% |
| 平均消息长度 | 28.9字符 |

### Bugfix示例

- fix doc
- fix calling l0op but return nullptr without truely check under multithread situation
- fix aclnn_bernoulli prob fp64 cast to fp32

### Optimization示例

- 优化TopkV2算子与aclSetAclOpExecutorRepeatable接口的兼容性
- batch_to_space_nd性能优化
- grouped_bias_add_grad算子性能优化

## ops-transformer

| 指标 | 值 |
|------|-----|
| 总commits | 100 |
| Bugfix | 40 (40.0%) |
| Optimization | 2 (2.0%) |
| Feature | 58 (58.0%) |
| Bugfix有issue引用 | 2.5% |
| Bugfix有详细描述 | 67.5% |
| 平均消息长度 | 29.8字符 |

### Bugfix示例

- 修复qsfa和qsfap在sparse mode为3，且多batch中有actualQ>actualKv的场景时精度fail的问题
- MLA非量化lastBN判断 bugfix
- 修复tilingkey找不到问题

### Optimization示例

- QSFA&&QSFAP 优化 hifloat8 拦截
- mmRS 8p 性能优化公式化tiling

## ops-cv

| 指标 | 值 |
|------|-----|
| 总commits | 100 |
| Bugfix | 33 (33.0%) |
| Optimization | 12 (12.0%) |
| Feature | 54 (54.0%) |
| Bugfix有issue引用 | 3.0% |
| Bugfix有详细描述 | 60.6% |
| 平均消息长度 | 28.1字符 |

### Bugfix示例

- GridSample算子UT问题修改
- fix: 修复文档拼写错误及目录结构问题
- 【bugfix】整改roiAlignRotated文档

### Optimization示例

- modified md files(for readability improvement)
- 【描    述】  Optimizer Markdown Information
- modified md files(for readability improvement)
