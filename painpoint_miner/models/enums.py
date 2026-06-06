"""PainPoint Miner - 枚举类型定义。"""

from enum import Enum


class Platform(str, Enum):
    """支持的社交平台。"""

    TWITTER = "twitter"
    XIAOHONGSHU = "xiaohongshu"
    WEIBO = "weibo"
    DOUYIN = "douyin"
    ZHIHU = "zhihu"


class PainType(str, Enum):
    """痛点类型。"""

    UX_PROBLEM = "ux_problem"
    PERFORMANCE = "performance"
    MISSING_FEATURE = "missing_feature"
    PRICING = "pricing"
    CUSTOMER_SERVICE = "customer_service"
    BUG = "bug"
    ONBOARDING = "onboarding"
    OTHER = "other"


class Sentiment(str, Enum):
    """情感极性。"""

    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


class Severity(int, Enum):
    """严重度等级 1-5。"""

    TRIVIAL = 1
    MINOR = 2
    MODERATE = 3
    MAJOR = 4
    CRITICAL = 5


class AnalysisMode(str, Enum):
    """分析模式。"""

    MERGED = "merged"
    SPLIT = "split"
