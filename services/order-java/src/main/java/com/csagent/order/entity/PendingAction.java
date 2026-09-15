package com.csagent.order.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.LocalDateTime;
import lombok.Data;

/**
 * 待确认提案状态机:
 *   PENDING -(用户确认,原子抢占)- EXECUTING -(副作用完成)- DONE
 *   PENDING -(用户取消/过期)---- CANCELLED / EXPIRED
 *   EXECUTING -(副作用失败)----- FAILED(可重试)
 *   EXECUTING -(持有者崩溃,超时回收)- PENDING
 * 抢占/终态迁移全部走条件 UPDATE(受影响行数即结果),不复刻 Python 侧
 * "读→判→写"的 check-then-act 缺陷(对拍见 /api/debug/* 与 scripts/)。
 */
@Data
@TableName("pending_actions")
public class PendingAction {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String sessionId;

    private Long userId;

    /** CANCEL_ORDER / CONFIRM_RECEIPT / UPDATE_ADDRESS */
    private String actionType;

    private Long orderId;

    private String payload;

    private String status;

    private LocalDateTime expiresAt;

    private LocalDateTime createdAt;

    private LocalDateTime confirmedAt;

    private LocalDateTime finishedAt;
}
