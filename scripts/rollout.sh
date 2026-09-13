#!/usr/bin/env bash
# 灰度发布辅助：参数 = 镜像 tag
set -euo pipefail
TAG="${1:?用法: ./rollout.sh <image-tag>}"
NAMESPACE="${NAMESPACE:-csagent}"

echo "== 滚动更新 deployment/csagent -> ${TAG} =="
kubectl set image deployment/csagent csagent="registry/csagent:${TAG}" -n "$NAMESPACE"
kubectl rollout status deployment/csagent -n "$NAMESPACE" --timeout=300s
echo "== 发布完成；建议观察 10 分钟错误率/P99（Grafana）=="
