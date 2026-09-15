package com.csagent.order.service;

import com.csagent.order.entity.OutboxEvent;
import com.csagent.order.mapper.OutboxEventMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Outbox 投递器:本地消息表的最终一致性实现(Phase 1 用 HTTP webhook 代替 MQ)。
 *
 * - 业务事务内只写 outbox 行(与业务同事务,天然原子);
 * - 本任务轮询到期待投递事件,投递到 webhook(CSagent 事件入口)或日志消费者;
 * - 失败指数退避(10s×2^n,封顶 600s),投递幂等由消费方按 event id 去重;
 * - 引入 MQ 时仅需替换 deliver() 为 MQ 发送,表结构与轮询语义不变。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class OutboxDispatcher {

    private static final int BATCH = 20;

    private final OutboxEventMapper outboxEventMapper;

    @Value("${app.outbox.webhook-url:}")
    private String webhookUrl;

    @Value("${app.outbox.scheduler-enabled:true}")
    private boolean schedulerEnabled;

    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3))
            .build();

    @Scheduled(fixedDelay = 2000)
    public void scheduled() {
        if (!schedulerEnabled) {
            return;   // 测试关闭调度,用例手动 dispatchDue() 保证确定性
        }
        try {
            dispatchDue();
        } catch (Exception ex) {
            log.error("outbox 投递轮询异常", ex);
        }
    }

    /** 手动触发入口(测试/运维),返回本轮处理条数。 */
    public int dispatchDue() {
        List<OutboxEvent> due = outboxEventMapper.selectDue(BATCH);
        for (OutboxEvent event : due) {
            deliver(event);
        }
        return due.size();
    }

    private void deliver(OutboxEvent event) {
        try {
            if (webhookUrl == null || webhookUrl.isBlank()) {
                // 未配置 webhook:日志即消费者(演示/本地形态)
                log.info("[outbox] -> log-consumer: {} {} {}",
                        event.getEventType(), event.getAggregateNo(), event.getPayload());
            } else {
                HttpRequest request = HttpRequest.newBuilder(URI.create(webhookUrl))
                        .timeout(Duration.ofSeconds(5))
                        .header("Content-Type", "application/json")
                        .POST(HttpRequest.BodyPublishers.ofString(
                                event.getPayload() == null ? "{}" : event.getPayload()))
                        .build();
                HttpResponse<String> resp = http.send(request, HttpResponse.BodyHandlers.ofString());
                if (resp.statusCode() >= 300) {
                    throw new IllegalStateException("webhook 响应 " + resp.statusCode());
                }
            }
            outboxEventMapper.markSent(event.getId());
        } catch (Exception ex) {
            outboxEventMapper.markFailedWithBackoff(event.getId());
            log.warn("[outbox] 投递失败 id={}, 已安排退避重试: {}",
                    event.getId(), ex.getMessage());
        }
    }
}
