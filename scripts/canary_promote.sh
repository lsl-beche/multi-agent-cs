#!/usr/bin/env bash
set -euo pipefail

TAG="${1:?用法: ./canary_promote.sh <image-tag>}"
NAMESPACE="${NAMESPACE:-csagent}"

kubectl set image deployment/csagent csagent="registry/csagent:${TAG}" -n "$NAMESPACE"
kubectl rollout status deployment/csagent -n "$NAMESPACE" --timeout=300s
kubectl scale deployment/csagent --replicas=6 -n "$NAMESPACE"
echo "== 金丝雀已提升；观察 10 分钟错误率/P99 =="
