package com.csagent.order.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.LocalDateTime;
import lombok.Data;

/** 交易 Outbox 事件(本地消息表)。 */
@Data
@TableName("outbox_events")
public class OutboxEvent {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String eventType;

    private String aggregateNo;

    private String payload;

    /** PENDING / SENT / FAILED */
    private String status;

    private Integer retryCount;

    private LocalDateTime nextRetryAt;

    private LocalDateTime createdAt;

    private LocalDateTime sentAt;
}
