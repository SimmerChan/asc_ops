# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
反馈接口模块

提供知识纠错反馈的收集和处理接口
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from .citation_tracker import CitationTracker, EntityType
from ..storage.redis_client import RedisClient

logger = logging.getLogger(__name__)


class CorrectionType(Enum):
    """纠错类型"""
    WRONG = "wrong"           # 知识错误
    INCOMPLETE = "incomplete"  # 知识不完整
    OUTDATED = "outdated"     # 知识过时
    MISLEADING = "misleading" # 知识误导


@dataclass
class CorrectionReport:
    """纠错报告"""
    entity_id: str
    entity_type: str
    correction_type: CorrectionType
    user_id: Optional[str]
    description: str
    suggested_fix: Optional[str]
    reported_at: datetime

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "correction_type": self.correction_type.value,
            "user_id": self.user_id,
            "description": self.description,
            "suggested_fix": self.suggested_fix,
            "reported_at": self.reported_at.isoformat(),
        }


@dataclass
class CorrectionStats:
    """纠错统计"""
    entity_id: str
    entity_type: str
    total_corrections: int
    by_type: Dict[str, int]
    last_reported_at: Optional[datetime]


class FeedbackAPI:
    """
    反馈收集接口

    收集和处理用户对知识的纠错反馈

    Redis Key Pattern (统一为 ascendc:corrections:* 前缀):
    - ascendc:corrections:detail:{entity_type}:{entity_id}:{correction_type} -> Counter
    - ascendc:corrections:reports:{entity_type}:{entity_id} -> List of reports
    - ascendc:corrections:threshold:{entity_type} -> int
    - ascendc:corrections:index -> Sorted Set (全局索引)
    """

    CORRECTION_COUNT_KEY = "ascendc:corrections:detail:{entity_type}:{entity_id}:{correction_type}"
    CORRECTION_REPORTS_KEY = "ascendc:corrections:reports:{entity_type}:{entity_id}"
    CORRECTION_THRESHOLD_KEY = "ascendc:corrections:threshold:{entity_type}"
    # 全局修正报告索引: sorted set，score=timestamp，value=json{entity_type,entity_id,correction_type,reported_at}
    CORRECTION_INDEX_KEY = "ascendc:corrections:index"

    # 默认纠错阈值 (超过此值触发告警)
    DEFAULT_CORRECTION_THRESHOLD = 5

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        citation_tracker: Optional[CitationTracker] = None
    ):
        """
        初始化反馈接口

        Args:
            redis_client: Redis 客户端
            citation_tracker: 引用追踪器 (用于同步更新准确性分数)
        """
        self.redis = redis_client or RedisClient(mock=True)
        self.citation_tracker = citation_tracker or CitationTracker(self.redis)
        self._correction_threshold = self.DEFAULT_CORRECTION_THRESHOLD
        logger.info("FeedbackAPI initialized")

    def set_correction_threshold(self, threshold: int, entity_type: Optional[str] = None) -> None:
        """
        设置纠错告警阈值

        Args:
            threshold: 纠错次数阈值
            entity_type: 实体类型 (可选，为空则设置全局阈值)
        """
        if entity_type:
            key = self.CORRECTION_THRESHOLD_KEY.format(entity_type=entity_type)
            self.redis.set(key, str(threshold))
        else:
            self._correction_threshold = threshold

    def _get_threshold(self, entity_type: str) -> int:
        """获取实体类型的纠错阈值"""
        key = self.CORRECTION_THRESHOLD_KEY.format(entity_type=entity_type)
        value = self.redis.get(key)
        if value:
            try:
                return int(value)
            except ValueError:
                pass
        return self._correction_threshold

    async def report_correction(
        self,
        entity_id: str,
        entity_type: str,
        correction_type: str,
        user_id: Optional[str] = None,
        description: Optional[str] = None,
        suggested_fix: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        上报纠错反馈

        Args:
            entity_id: 实体 ID
            entity_type: 实体类型 (bug | optimization | api)
            correction_type: 纠错类型 (wrong | incomplete | outdated | misleading)
            user_id: 用户 ID (可选)
            description: 纠错描述 (可选)
            suggested_fix: 建议修复 (可选)

        Returns:
            Dict containing:
            - success: 是否成功
            - correction_count: 当前纠错总数
            - threshold_exceeded: 是否超过阈值
            - alert_triggered: 是否触发了告警
        """
        # 规范化纠错类型
        try:
            corr_type = CorrectionType(correction_type)
        except ValueError:
            logger.warning(f"Unknown correction type: {correction_type}, using WRONG")
            corr_type = CorrectionType.WRONG

        entity_type = self._normalize_entity_type(entity_type)
        timestamp = datetime.now()

        # 1. 增加纠错计数
        count_key = self.CORRECTION_COUNT_KEY.format(
            entity_type=entity_type,
            entity_id=entity_id,
            correction_type=corr_type.value
        )
        new_count = self._incr(count_key)

        # 2. 记录纠错报告到列表
        reports_key = self.CORRECTION_REPORTS_KEY.format(
            entity_type=entity_type,
            entity_id=entity_id
        )
        report = CorrectionReport(
            entity_id=entity_id,
            entity_type=entity_type,
            correction_type=corr_type,
            user_id=user_id,
            description=description or "",
            suggested_fix=suggested_fix,
            reported_at=timestamp
        )
        report_json = self._serialize_report(report)
        self.redis.rpush(reports_key, report_json)

        # 2.5 添加到全局索引
        import json
        index_entry = json.dumps({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "correction_type": corr_type.value,
            "reported_at": timestamp.isoformat(),
        })
        # 使用时间戳作为分数，便于范围查询
        score = timestamp.timestamp()
        self.redis.zadd(self.CORRECTION_INDEX_KEY, {index_entry: score})

        # 3. 同步更新 CitationTracker
        self.citation_tracker.record_correction(entity_id, entity_type, timestamp)

        # 4. 检查是否超过阈值
        threshold = self._get_threshold(entity_type)
        total_corrections = self.get_total_corrections(entity_id, entity_type)
        threshold_exceeded = total_corrections >= threshold

        # 5. 如果超过阈值，触发告警
        alert_triggered = False
        if threshold_exceeded:
            alert_triggered = await self.alert_high_correction(entity_id, entity_type, total_corrections)

        logger.info(
            f"Correction reported: {entity_type}:{entity_id} "
            f"type={corr_type.value} count={new_count} "
            f"threshold_exceeded={threshold_exceeded}"
        )

        return {
            "success": True,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "correction_type": corr_type.value,
            "correction_count": int(new_count),
            "total_corrections": total_corrections,
            "threshold_exceeded": threshold_exceeded,
            "alert_triggered": alert_triggered,
        }

    def get_total_corrections(self, entity_id: str, entity_type: str) -> int:
        """
        获取实体的总纠错次数

        Args:
            entity_id: 实体 ID
            entity_type: 实体类型

        Returns:
            总纠错次数
        """
        entity_type = self._normalize_entity_type(entity_type)
        total = 0

        for corr_type in CorrectionType:
            count_key = self.CORRECTION_COUNT_KEY.format(
                entity_type=entity_type,
                entity_id=entity_id,
                correction_type=corr_type.value
            )
            count = self.redis.get(count_key)
            if count:
                try:
                    total += int(count)
                except ValueError:
                    pass

        return total

    def get_correction_stats(self, entity_id: str, entity_type: str) -> CorrectionStats:
        """
        获取实体的纠错统计

        Args:
            entity_id: 实体 ID
            entity_type: 实体类型

        Returns:
            CorrectionStats: 纠错统计
        """
        entity_type = self._normalize_entity_type(entity_type)
        by_type = {}
        last_reported = None

        for corr_type in CorrectionType:
            count_key = self.CORRECTION_COUNT_KEY.format(
                entity_type=entity_type,
                entity_id=entity_id,
                correction_type=corr_type.value
            )
            count = self.redis.get(count_key)
            count_int = int(count) if count else 0
            by_type[corr_type.value] = count_int

            # 获取最后报告时间
            if count_int > 0:
                reports_key = self.CORRECTION_REPORTS_KEY.format(
                    entity_type=entity_type,
                    entity_id=entity_id
                )
                reports = self.redis.lrange(reports_key, 0, -1)
                if reports:
                    last_report = self._deserialize_report(reports[-1])
                    if last_report and (
                        last_reported is None or
                        last_report.reported_at > last_reported
                    ):
                        last_reported = last_report.reported_at

        return CorrectionStats(
            entity_id=entity_id,
            entity_type=entity_type,
            total_corrections=sum(by_type.values()),
            by_type=by_type,
            last_reported_at=last_reported
        )

    def get_correction_reports(
        self,
        entity_id: str,
        entity_type: str,
        limit: int = 10
    ) -> List[CorrectionReport]:
        """
        获取实体的纠错报告列表

        Args:
            entity_id: 实体 ID
            entity_type: 实体类型
            limit: 返回数量

        Returns:
            List of CorrectionReport
        """
        entity_type = self._normalize_entity_type(entity_type)
        reports_key = self.CORRECTION_REPORTS_KEY.format(
            entity_type=entity_type,
            entity_id=entity_id
        )

        reports_json = self.redis.lrange(reports_key, -limit, -1)
        reports = []
        for json_str in reports_json:
            report = self._deserialize_report(json_str)
            if report:
                reports.append(report)

        return list(reversed(reports))

    def query_correction_reports(
        self,
        entity_type: Optional[str] = None,
        correction_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """
        分页查询全局纠错报告

        Args:
            entity_type: 实体类型过滤 (bug | optimization | api)
            correction_type: 纠错类型过滤 (wrong | incomplete | outdated | misleading)
            start_date: 开始时间 (可选)
            end_date: 结束时间 (可选)
            page: 页码 (从1开始)
            page_size: 每页数量

        Returns:
            Dict containing reports, total_count, page, page_size, total_pages
        """
        import json

        # 计算分数范围
        min_score = start_date.timestamp() if start_date else 0
        max_score = end_date.timestamp() if end_date else "+inf"

        # 获取索引范围内的所有条目
        entries = self.redis.zrangebyscore(
            self.CORRECTION_INDEX_KEY,
            min=min_score,
            max=max_score,
            withscores=True,
        )

        # 过滤并收集报告
        filtered_reports = []
        total_count = 0

        for entry_json, score in entries:
            try:
                entry = json.loads(entry_json)
                # 应用过滤器
                if entity_type and entry.get("entity_type") != self._normalize_entity_type(entity_type):
                    continue
                if correction_type:
                    try:
                        corr_type_enum = CorrectionType(correction_type)
                        if entry.get("correction_type") != corr_type_enum.value:
                            continue
                    except ValueError:
                        pass

                # 获取完整报告
                reports_key = self.CORRECTION_REPORTS_KEY.format(
                    entity_type=entry["entity_type"],
                    entity_id=entry["entity_id"],
                )
                # 查找匹配的报告
                all_reports = self.redis.lrange(reports_key, 0, -1)
                for report_json in all_reports:
                    report = self._deserialize_report(report_json)
                    if report and report.reported_at.isoformat() == entry.get("reported_at"):
                        filtered_reports.append(report)
                        total_count += 1
                        break

            except (json.JSONDecodeError, KeyError):
                continue

        # 计算分页
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        # 按时间倒序返回
        paginated_reports = sorted(
            filtered_reports,
            key=lambda r: r.reported_at,
            reverse=True
        )[start_idx:end_idx]

        return {
            "reports": paginated_reports,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def alert_high_correction(
        self,
        entity_id: str,
        entity_type: str,
        correction_count: int
    ) -> bool:
        """
        纠错过多时触发告警

        Args:
            entity_id: 实体 ID
            entity_type: 实体类型
            correction_count: 当前纠错次数

        Returns:
            是否触发了告警
        """
        logger.warning(
            f"HIGH CORRECTION ALERT: {entity_type}:{entity_id} "
            f"has {correction_count} corrections (threshold: {self._get_threshold(entity_type)})"
        )

        # TODO: 实现实际的告警机制 (如发送通知到飞书/钉钉)
        # 目前只是记录日志
        return True

    def _normalize_entity_type(self, entity_type: str) -> str:
        """规范化实体类型"""
        try:
            return EntityType(entity_type).value
        except ValueError:
            pass

        type_map = {
            "bug": EntityType.BUG.value,
            "bugs": EntityType.BUG.value,
            "bugfix": EntityType.BUG.value,
            "optimization": EntityType.OPTIMIZATION.value,
            "opt": EntityType.OPTIMIZATION.value,
            "opts": EntityType.OPTIMIZATION.value,
            "api": EntityType.API.value,
            "apis": EntityType.API.value,
        }
        return type_map.get(entity_type.lower(), entity_type)

    def _incr(self, key: str) -> int:
        """增加计数器"""
        if self.redis.is_mock:
            current = self.redis.get(key) or "0"
            try:
                new_value = int(current) + 1
            except ValueError:
                new_value = 1
            self.redis.set(key, str(new_value))
            return new_value
        else:
            return self.redis._client.incr(key)

    def _serialize_report(self, report: CorrectionReport) -> str:
        """序列化纠错报告为 JSON"""
        import json
        return json.dumps({
            "entity_id": report.entity_id,
            "entity_type": report.entity_type,
            "correction_type": report.correction_type.value,
            "user_id": report.user_id,
            "description": report.description,
            "suggested_fix": report.suggested_fix,
            "reported_at": report.reported_at.isoformat(),
        })

    def _deserialize_report(self, json_str: str) -> Optional[CorrectionReport]:
        """从 JSON 反序列化纠错报告"""
        import json
        try:
            data = json.loads(json_str)
            return CorrectionReport(
                entity_id=data["entity_id"],
                entity_type=data["entity_type"],
                correction_type=CorrectionType(data["correction_type"]),
                user_id=data.get("user_id"),
                description=data.get("description", ""),
                suggested_fix=data.get("suggested_fix"),
                reported_at=datetime.fromisoformat(data["reported_at"]),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to deserialize correction report: {e}")
            return None
