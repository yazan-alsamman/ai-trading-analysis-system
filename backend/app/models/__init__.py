# استورد النماذج هنا حتى يراها Alembic
from app.db.base import Base
from app.models.api_key import ApiKey, Scope
from app.models.backtest import Backtest, BacktestStatus, BacktestTrade
from app.models.candle import Candle, Timeframe
from app.models.custom_strategy import CustomStrategy, CustomStrategyKind, Visibility
from app.models.instrument import Instrument, MarketType
from app.models.notification import (
    Channel,
    DeliveryStatus,
    LoginFingerprint,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationType,
    Platform,
    Severity,
    TelegramLink,
    UserDevice,
)
from app.models.refresh_token import RefreshToken
from app.models.risk import RiskProfile, SignalPlan
from app.models.strategy import Signal, SignalSide, UserStrategy
from app.models.user import User, UserRole
from app.models.workspace import Workspace

__all__ = [
    "Channel",
    "DeliveryStatus",
    "LoginFingerprint",
    "Notification",
    "NotificationDelivery",
    "NotificationPreference",
    "NotificationType",
    "Platform",
    "Severity",
    "TelegramLink",
    "UserDevice",
    "ApiKey",
    "Backtest",
    "BacktestStatus",
    "BacktestTrade",
    "Base",
    "Candle",
    "CustomStrategy",
    "CustomStrategyKind",
    "Instrument",
    "MarketType",
    "RefreshToken",
    "RiskProfile",
    "Scope",
    "Signal",
    "SignalPlan",
    "SignalSide",
    "Timeframe",
    "User",
    "UserRole",
    "UserStrategy",
    "Visibility",
    "Workspace",
]
