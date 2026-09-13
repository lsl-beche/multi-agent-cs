# 金丝雀灰度与回滚（ArgoCD + image 权重）

## 灰度流程

1. 构建新镜像并推送（CI 完成）：`csagent:${GITHUB_SHA::8}`
2. 更新镜像（ArgoCD 自动同步或手动）：
   `kubectl set image deployment/csagent csagent=registry/csagent:${SHA} -n csagent`
3. 观察 5% 流量？ArgoCD 金丝雀：用 AnalysisTemplate + 权重路由；
   简化方案：先升 `replicas=1` 新版本 Pod，灰度指标满足后全量。
4. 灰度期指标：错误率 <1%、P99 <3s、转人工无激增（Grafana 看板）。

## 回滚

```bash
kubectl rollout undo deployment/csagent -n csagent
# 或恢复到上一镜像 tag
kubectl set image deployment/csagent csagent=registry/csagent:previous-tag -n csagent
```

回滚后跑 `python scripts/eval_dialogue.py --threshold 0.95` 验证 AI 未回退。

## 大促预扩容

```bash
kubectl scale deployment/csagent --replicas=20 -n csagent
kubectl scale deployment/csagent-vllm --replicas=8 -n csagent
```
