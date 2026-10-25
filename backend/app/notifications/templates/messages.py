"""Every user-facing notification text, in Arabic and English. Wording changes go here only.

Placeholders are ``str.format`` fields; numbers arrive already formatted.
"""

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        # signals
        "side.buy": "BUY",
        "side.sell": "SELL",
        "signal.title": "{side} signal: {symbol} {timeframe}",
        "signal.strategy": "Strategy: {strategy} · strength {strength}",
        "signal.price": "Price: {price}",
        "plan.header": "Trade plan ({account} {currency} account):",
        "plan.entry": "Entry ≈ {entry}",
        "plan.stop": "Stop: {stop}",
        "plan.target": "Target {n}: {price} ({r}R, close {pct}%)",
        "plan.size": "Size: {qty} ({notional} {currency})",
        "plan.risk": "Risk: {risk} {currency} ({risk_pct}%) · R:R {rr}",
        "plan.invalid": "No valid trade plan: {reason}",
        "plan.none": "No trade plan was computed.",
        "reason.stop_unavailable": "the stop cannot be computed yet (not enough history)",
        "reason.stop_wrong_side": "the stop is on the wrong side of the entry",
        "reason.atr_unavailable": "the ATR is not available yet",
        "reason.no_equity": "the account size is zero",
        "reason.size_below_min": "the position is below the minimum size",
        # backtests
        "backtest_completed.title": "Backtest finished: {strategy} on {symbol} {timeframe}",
        "backtest_completed.body": (
            "Return {ret}% · Max drawdown {dd}% · Sharpe {sharpe} · Trades {trades} · "
            "Win rate {win}%"
        ),
        "backtest_failed.title": "Backtest failed: {strategy} on {symbol} {timeframe}",
        "backtest_failed.body": "Error: {error}",
        # security
        "security.new_login.title": "New sign-in to your account",
        "security.new_login.body": (
            "Signed in from a new device or network (IP {ip}, {agent}). "
            "If this was not you, change your password now."
        ),
        "security.password_changed.title": "Your password was changed",
        "security.password_changed.body": (
            "Your password was changed and all other sessions were signed out. "
            "If this was not you, contact support."
        ),
        "security.api_key_created.title": "API key created",
        "security.api_key_created.body": 'The API key "{name}" ({prefix}…) was created.',
        "security.api_key_revoked.title": "API key revoked",
        "security.api_key_revoked.body": 'The API key "{name}" ({prefix}…) was revoked.',
        "security.account_locked.title": "Your account is temporarily locked",
        "security.account_locked.body": (
            "Too many failed sign-in attempts. Sign-in is blocked for {minutes} minutes. "
            "If this was not you, change your password afterwards."
        ),
        # other
        "test.title": "Test notification",
        "test.body": "Notifications through {channel} work.",
        "digest.title": "{count} notifications",
        "digest.intro": "While notifications were paused or capped:",
        "digest.more": "…and {count} more",
        "email.footer": "You receive this because of your notification settings.",
        # posts and comments (Y18)
        "new_post.title": "{author} posted: {title}",
        "new_post.instrument": "{symbol} · {direction}",
        "direction.bullish": "bullish",
        "direction.bearish": "bearish",
        "direction.neutral": "neutral",
        "comment_reply.post.title": "{author} commented on your post",
        "comment_reply.comment.title": "{author} replied to your comment",
        "comment_reply.body": 'On "{post}": {excerpt}',
        "post_liked.title.one": "1 person liked your post",
        "post_liked.title.many": "{count} people liked your post",
        "post_liked.body": '"{post}"',
        "content_hidden.post.title": "Your post was hidden by moderation",
        "content_hidden.comment.title": "Your comment was hidden by moderation",
        "content_hidden.body": '"{excerpt}" is no longer visible to others.',
        "content_hidden.reason": "Reason: {reason}",
        # price alerts (Y18)
        "price_alert.title": "Price alert: {symbol} {condition}",
        "cond.above": "at or above {value}",
        "cond.below": "at or below {value}",
        "cond.crosses_above": "crossed above {value}",
        "cond.crosses_below": "crossed below {value}",
        "cond.change_pct": "moved {change}% in {window} min",
        "price_alert.price": "Price: {price} (1m bar {bar} UTC)",
        "rule.above": "Rule: high ≥ {value}",
        "rule.below": "Rule: low ≤ {value}",
        "rule.crosses_above": "Rule: close crossed above {value} (previous close {previous})",
        "rule.crosses_below": "Rule: close crossed below {value} (previous close {previous})",
        "rule.change_pct": "Rule: move ≥ {value}% in {window} min (from {reference})",
        "price_alert.note": "Note: {note}",
        "price_alert.once": "This alert is now off (it fires once).",
        # AI setups (B11)
        "ai_setup.ARMED.title": "{side} setup {symbol}: entry {entry}",
        "ai_setup.ACTIVE.title": "Setup active: {side} {symbol}",
        "ai_setup.CLOSED.title": "Setup closed: {side} {symbol} {r}R",
        "ai_setup.EXPIRED.title": "Setup expired: {side} {symbol}",
        "ai_setup.INVALIDATED.title": "Setup invalidated: {side} {symbol}",
        "ai_setup.prices": "Entry {entry} · Stop {sl} · Target {tp}",
        "ai_setup.scores": "Grade {grade} · Probability {probability}% · {r_multiple}R",
        "ai_setup.scores_no_grade": "Probability {probability}% · {r_multiple}R",
        "ai_setup.scores_no_model": "Probability n/a · {r_multiple}R",
        "ai_setup.explanation_unavailable": "Explanation unavailable",
        "ai_setup.valid_until": "Valid until {time} UTC",
        "ai_setup.size": "Your size: {lots} lots, risking {risk} {currency}",
        "ai_setup.size_infeasible": "No position for your account",
        "ai_setup.size_error": "Your size could not be computed",
        "ai_setup.warning": "Note: {warning}",
        "ai_setup.reason": "Reason: {reason}",
        "ai_setup.pnl": "Your result: {pnl} ({r}R)",
        "ai_setup.late": "(late notice)",
        # experts, subscriptions, chat (Y19)
        "content_hidden.message.title": "Your chat message was hidden by moderation",
        "interval.month": "month",
        "interval.year": "year",
        "chat_message.title.one": "New message from {sender}",
        "chat_message.title.many": "{count} new messages from {sender}",
        "subscription_started.title": "Subscription started: {expert}",
        "subscription_started.trial": (
            "{plan}: free trial until {date}, then {price} {currency} / {interval}."
        ),
        "subscription_started.paid": (
            "{plan}: {price} {currency} / {interval}. Next renewal on {date}."
        ),
        "subscription_renewed.title": "Subscription renewed: {expert}",
        "subscription_renewed.body": (
            "Paid {amount} {currency} (invoice {invoice}). Next renewal on {date}."
        ),
        "subscription_payment_failed.title": "Payment failed: {expert}",
        "subscription_payment_failed.body": (
            "Invoice {invoice} ({amount} {currency}) could not be charged: {reason}. "
            "Your access continues until {grace}, then the subscription ends."
        ),
        "subscription_canceled.title": "Subscription ended: {expert}",
        "subscription_canceled.period_end": "You canceled the subscription; it ended on {date}.",
        "subscription_canceled.payment_failed": (
            "The renewal payment failed and the grace period is over."
        ),
        "subscription_canceled.refund": (
            "Invoice {invoice} was refunded and the subscription ended."
        ),
        "new_subscriber.title": "New subscriber: {subscriber}",
        "new_subscriber.paid": "{plan}: {price} {currency} / {interval}.",
        "new_subscriber.trial": (
            "{plan}: {days}-day free trial, then {price} {currency} / {interval}."
        ),
        # Telegram bot replies
        "bot.linked": "✅ Linked. You will receive your notifications here.",
        "bot.bad_code": "This link code is invalid or expired. Create a new one in the app.",
        "bot.help": (
            "Open the app, go to notification settings and tap 'Link Telegram'. "
            "Commands: /status, /stop"
        ),
        "bot.unlinked": "Unlinked. You will not receive notifications here any more.",
        "bot.not_linked": "This chat is not linked to an account.",
        "bot.status": "Linked to {email}.",
    },
    "ar": {
        "side.buy": "شراء",
        "side.sell": "بيع",
        "signal.title": "إشارة {side}: {symbol} {timeframe}",
        "signal.strategy": "الاستراتيجية: {strategy} · القوة {strength}",
        "signal.price": "السعر: {price}",
        "plan.header": "خطة الصفقة (حساب {account} {currency}):",
        "plan.entry": "الدخول ≈ {entry}",
        "plan.stop": "وقف الخسارة: {stop}",
        "plan.target": "الهدف {n}: {price} ({r}R، إغلاق {pct}%)",
        "plan.size": "الكمية: {qty} ({notional} {currency})",
        "plan.risk": "المخاطرة: {risk} {currency} ({risk_pct}%) · العائد/المخاطرة {rr}",
        "plan.invalid": "لا توجد خطة صالحة: {reason}",
        "plan.none": "لم تُحسب خطة صفقة.",
        "reason.stop_unavailable": "لا يمكن حساب الوقف بعد (البيانات غير كافية)",
        "reason.stop_wrong_side": "الوقف في الجهة الخاطئة من سعر الدخول",
        "reason.atr_unavailable": "مؤشر ATR غير متاح بعد",
        "reason.no_equity": "حجم الحساب صفر",
        "reason.size_below_min": "حجم الصفقة أقل من الحد الأدنى",
        "backtest_completed.title": "انتهى الاختبار التاريخي: {strategy} على {symbol} {timeframe}",
        "backtest_completed.body": (
            "العائد {ret}% · أقصى تراجع {dd}% · شارب {sharpe} · الصفقات {trades} · "
            "نسبة الربح {win}%"
        ),
        "backtest_failed.title": "فشل الاختبار التاريخي: {strategy} على {symbol} {timeframe}",
        "backtest_failed.body": "الخطأ: {error}",
        "security.new_login.title": "تسجيل دخول جديد إلى حسابك",
        "security.new_login.body": (
            "تم تسجيل الدخول من جهاز أو شبكة جديدة (IP {ip}، {agent}). "
            "إن لم تكن أنت، غيّر كلمة المرور فوراً."
        ),
        "security.password_changed.title": "تم تغيير كلمة المرور",
        "security.password_changed.body": (
            "تم تغيير كلمة المرور وتسجيل الخروج من بقية الجلسات. إن لم تكن أنت، تواصل مع الدعم."
        ),
        "security.api_key_created.title": "تم إنشاء مفتاح API",
        "security.api_key_created.body": 'تم إنشاء مفتاح API باسم "{name}" ({prefix}…).',
        "security.api_key_revoked.title": "تم إلغاء مفتاح API",
        "security.api_key_revoked.body": 'تم إلغاء مفتاح API باسم "{name}" ({prefix}…).',
        "security.account_locked.title": "حسابك مقفل مؤقتاً",
        "security.account_locked.body": (
            "محاولات دخول فاشلة كثيرة. تسجيل الدخول متوقف لمدة {minutes} دقيقة. "
            "إن لم تكن أنت، غيّر كلمة المرور بعدها."
        ),
        "test.title": "إشعار تجريبي",
        "test.body": "الإشعارات عبر {channel} تعمل.",
        "digest.title": "{count} إشعارات",
        "digest.intro": "أثناء إيقاف الإشعارات أو تجاوز الحد:",
        "digest.more": "…و{count} أخرى",
        "email.footer": "تصلك هذه الرسالة بحسب إعدادات الإشعارات في حسابك.",
        "new_post.title": "{author} نشر تحليلاً: {title}",
        "new_post.instrument": "{symbol} · {direction}",
        "direction.bullish": "صاعد",
        "direction.bearish": "هابط",
        "direction.neutral": "محايد",
        "comment_reply.post.title": "{author} علّق على منشورك",
        "comment_reply.comment.title": "{author} ردّ على تعليقك",
        "comment_reply.body": "على «{post}»: {excerpt}",
        "post_liked.title.one": "أعجب مستخدم واحد بمنشورك",
        "post_liked.title.many": "أعجب {count} من المستخدمين بمنشورك",
        "post_liked.body": "«{post}»",
        "content_hidden.post.title": "تم إخفاء منشورك من قبل الإشراف",
        "content_hidden.comment.title": "تم إخفاء تعليقك من قبل الإشراف",
        "content_hidden.body": "«{excerpt}» لم يعد ظاهراً للآخرين.",
        "content_hidden.reason": "السبب: {reason}",
        "price_alert.title": "تنبيه سعر: {symbol} {condition}",
        "cond.above": "عند أو فوق {value}",
        "cond.below": "عند أو تحت {value}",
        "cond.crosses_above": "اخترق صعوداً {value}",
        "cond.crosses_below": "اخترق هبوطاً {value}",
        "cond.change_pct": "تحرّك {change}% خلال {window} دقيقة",
        "price_alert.price": "السعر: {price} (شمعة الدقيقة {bar} UTC)",
        "rule.above": "الشرط: أعلى سعر ≥ {value}",
        "rule.below": "الشرط: أدنى سعر ≤ {value}",
        "rule.crosses_above": "الشرط: الإغلاق اخترق صعوداً {value} (الإغلاق السابق {previous})",
        "rule.crosses_below": "الشرط: الإغلاق اخترق هبوطاً {value} (الإغلاق السابق {previous})",
        "rule.change_pct": "الشرط: حركة ≥ {value}% خلال {window} دقيقة (من {reference})",
        "price_alert.note": "ملاحظة: {note}",
        "price_alert.once": "تم إيقاف هذا التنبيه (يعمل مرة واحدة).",
        # إعدادات AI (B11)
        "ai_setup.ARMED.title": "إعداد {side} على {symbol}: الدخول {entry}",
        "ai_setup.ACTIVE.title": "الإعداد مفعّل: {side} {symbol}",
        "ai_setup.CLOSED.title": "أُغلق الإعداد: {side} {symbol} {r}R",
        "ai_setup.EXPIRED.title": "انتهت صلاحية الإعداد: {side} {symbol}",
        "ai_setup.INVALIDATED.title": "أُلغي الإعداد: {side} {symbol}",
        "ai_setup.prices": "الدخول {entry} · الوقف {sl} · الهدف {tp}",
        "ai_setup.scores": "التقييم {grade} · الاحتمال {probability}% · {r_multiple}R",
        "ai_setup.scores_no_grade": "الاحتمال {probability}% · {r_multiple}R",
        "ai_setup.scores_no_model": "الاحتمال غير متاح · {r_multiple}R",
        "ai_setup.explanation_unavailable": "الشرح غير متاح",
        "ai_setup.valid_until": "صالح حتى {time} بتوقيت UTC",
        "ai_setup.size": "حجمك: {lots} لوت، بمخاطرة {risk} {currency}",
        "ai_setup.size_infeasible": "لا يوجد حجم مناسب لحسابك",
        "ai_setup.size_error": "تعذّر حساب حجمك",
        "ai_setup.warning": "ملاحظة: {warning}",
        "ai_setup.reason": "السبب: {reason}",
        "ai_setup.pnl": "نتيجتك: {pnl} ({r}R)",
        "ai_setup.late": "(إشعار متأخر)",
        "content_hidden.message.title": "تم إخفاء رسالتك في المحادثة من قبل الإشراف",
        "interval.month": "شهر",
        "interval.year": "سنة",
        "chat_message.title.one": "رسالة جديدة من {sender}",
        "chat_message.title.many": "رسائل جديدة من {sender}: {count}",
        "subscription_started.title": "بدأ اشتراكك: {expert}",
        "subscription_started.trial": (
            "{plan}: تجربة مجانية حتى {date}، ثم {price} {currency} / {interval}."
        ),
        "subscription_started.paid": (
            "{plan}: {price} {currency} / {interval}. التجديد القادم في {date}."
        ),
        "subscription_renewed.title": "تم تجديد اشتراكك: {expert}",
        "subscription_renewed.body": (
            "تم دفع {amount} {currency} (الفاتورة {invoice}). التجديد القادم في {date}."
        ),
        "subscription_payment_failed.title": "فشل الدفع: {expert}",
        "subscription_payment_failed.body": (
            "تعذّر تحصيل الفاتورة {invoice} ({amount} {currency}): {reason}. "
            "يبقى وصولك حتى {grace}، ثم ينتهي الاشتراك."
        ),
        "subscription_canceled.title": "انتهى اشتراكك: {expert}",
        "subscription_canceled.period_end": "ألغيت الاشتراك، وانتهى في {date}.",
        "subscription_canceled.payment_failed": "فشل دفع التجديد وانتهت مهلة السماح.",
        "subscription_canceled.refund": "تم استرداد الفاتورة {invoice} وانتهى الاشتراك.",
        "new_subscriber.title": "مشترك جديد: {subscriber}",
        "new_subscriber.paid": "{plan}: {price} {currency} / {interval}.",
        "new_subscriber.trial": (
            "{plan}: تجربة مجانية {days} يوماً، ثم {price} {currency} / {interval}."
        ),
        "bot.linked": "✅ تم الربط. ستصلك إشعاراتك هنا.",
        "bot.bad_code": "رمز الربط غير صالح أو منتهي. أنشئ رمزاً جديداً من التطبيق.",
        "bot.help": (
            "افتح التطبيق، ثم إعدادات الإشعارات واضغط «ربط تيليغرام». الأوامر: /status و /stop"
        ),
        "bot.unlinked": "تم إلغاء الربط. لن تصلك الإشعارات هنا بعد الآن.",
        "bot.not_linked": "هذه المحادثة غير مرتبطة بأي حساب.",
        "bot.status": "مرتبط بالحساب {email}.",
    },
}

CHANNEL_NAMES = {
    "en": {"in_app": "the app", "telegram": "Telegram", "email": "email", "push": "push"},
    "ar": {
        "in_app": "التطبيق",
        "telegram": "تيليغرام",
        "email": "البريد",
        "push": "إشعارات الجوال",
    },
}
