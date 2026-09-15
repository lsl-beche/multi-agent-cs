package com.csagent.order.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.csagent.order.entity.OutboxEvent;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.List;

@Mapper
public interface OutboxEventMapper extends BaseMapper<OutboxEvent> {

    /** 到期待投递:PENDING,或 FAILED 且退避时间已到。 */
    @Select("SELECT * FROM outbox_events "
            + "WHERE status = 'PENDING' "
            + "   OR (status = 'FAILED' AND next_retry_at IS NOT NULL AND next_retry_at <= NOW()) "
            + "ORDER BY id LIMIT #{limit}")
    List<OutboxEvent> selectDue(@Param("limit") int limit);

    @Update("UPDATE outbox_events SET status = 'SENT', sent_at = NOW() WHERE id = #{id}")
    int markSent(@Param("id") long id);

    /** 指数退避:next = now + min(10 × 2^retryCount, 600) 秒。 */
    @Update("UPDATE outbox_events SET status = 'FAILED', retry_count = retry_count + 1, "
            + "next_retry_at = DATE_ADD(NOW(), INTERVAL LEAST(POW(retry_count, 2) * 10, 600) SECOND) "
            + "WHERE id = #{id}")
    int markFailedWithBackoff(@Param("id") long id);

    /** 清理已投递归档(示例保留接口)。 */
    @Delete("DELETE FROM outbox_events WHERE status = 'SENT' AND sent_at < NOW() - INTERVAL 7 DAY")
    int purgeSent();
}
