package com.csagent.order;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * CSagent 订单服务(Java)——交易写链路:订单查询/提案确认执行/SKU 扣减/幂等。
 * 智能层(Python CSagent)经 REST + Idempotency-Key 调用本服务。
 * MapperScan 扫根包:幂等 Mapper 独立成包,靠 @Mapper 注解识别(扫子包会漏注册)。
 */
@EnableScheduling
@SpringBootApplication
@MapperScan("com.csagent.order")
public class OrderServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(OrderServiceApplication.class, args);
    }
}
