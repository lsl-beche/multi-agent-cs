package com.csagent.order.controller;

import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 健康检查。路径与 CSagent 对齐(/api/health),
 * 便于后续 Locust 压测脚本把两个服务纳入同一基线。
 */
@RestController
public class HealthController {

    @GetMapping("/api/health")
    public Map<String, Object> health() {
        return Map.of(
                "status", "ok",
                "service", "order-service",
                "ts", System.currentTimeMillis());
    }
}
