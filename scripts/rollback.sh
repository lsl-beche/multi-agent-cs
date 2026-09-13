#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-csagent}"
kubectl rollout undo deployment/csagent -n "$NAMESPACE"
kubectl rollout status deployment/csagent -n "$NAMESPACE" --timeout=300s
echo "== 已回滚到上一版本 =="
