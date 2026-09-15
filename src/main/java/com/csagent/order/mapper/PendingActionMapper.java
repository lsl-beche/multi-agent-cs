package com.csagent.order.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.csagent.order.entity.PendingAction;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface PendingActionMapper extends BaseMapper<PendingAction> {

    /** 原子抢占:仅 PENDING 且未过期可进入 EXECUTING。受影响行数=1 即抢到执行权。 */
    @Update("UPDATE pending_actions SET status = 'EXECUTING', confirmed_at = NOW() "
            + "WHERE id = #{id} AND status = 'PENDING' AND expires_at > NOW()")
    int claimForExecution(@Param("id") long id);

    /** 用户撤销提案:PENDING → CANCELLED(原子)。 */
    @Update("UPDATE pending_actions SET status = 'CANCELLED', finished_at = NOW() "
            + "WHERE id = #{id} AND status = 'PENDING'")
    int cancelIfPending(@Param("id") long id);

    /** 副作用执行成功:EXECUTING → DONE(仅执行权持有者可标记)。 */
    @Update("UPDATE pending_actions SET status = 'DONE', finished_at = NOW() "
            + "WHERE id = #{id} AND status = 'EXECUTING'")
    int markDoneIfExecuting(@Param("id") long id);

    /** 副作用执行失败:EXECUTING → FAILED,等待重试。 */
    @Update("UPDATE pending_actions SET status = 'FAILED', finished_at = NOW() "
            + "WHERE id = #{id} AND status = 'EXECUTING'")
    int markFailedIfExecuting(@Param("id") long id);

    /** 惰性过期:确认撞上已过期提案时顺带归档。 */
    @Update("UPDATE pending_actions SET status = 'EXPIRED', finished_at = NOW() "
            + "WHERE id = #{id} AND status = 'PENDING' AND expires_at <= NOW()")
    int expireIfDue(@Param("id") long id);

    /** 崩溃恢复:EXECUTING 超过 60 秒未完成,视为持有者已死,放回队列重抢。 */
    @Update("UPDATE pending_actions SET status = 'PENDING', confirmed_at = NULL "
            + "WHERE status = 'EXECUTING' AND confirmed_at < NOW() - INTERVAL 60 SECOND")
    int requeueStuck();

    /** 兜底扫表:批量归档过期 PENDING。 */
    @Update("UPDATE pending_actions SET status = 'EXPIRED', finished_at = NOW() "
            + "WHERE status = 'PENDING' AND expires_at <= NOW()")
    int expireDuePending();

    /** 对拍专用(复刻 Python 侧缺陷):不带状态条件的终态写入。生产代码禁止使用。 */
    @Update("UPDATE pending_actions SET status = 'DONE', finished_at = NOW() WHERE id = #{id}")
    int markDoneUnconditional(@Param("id") long id);
}
