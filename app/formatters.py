import re
import unicodedata
import urllib
from datetime import datetime, timedelta, timezone
from functools import partial
from math import floor, log10
from numbers import Number

import ago
import dateutil
import humanize
from flask import Markup, url_for
from flask_babel import _
from notifications_utils.field import Field
from notifications_utils.formatters import make_quotes_smart
from notifications_utils.formatters import nl2br as utils_nl2br
from notifications_utils.recipients import InvalidPhoneError, validate_phone_number
from notifications_utils.take import Take
from notifications_utils.timezones import utc_string_to_aware_gmt_datetime


def convert_to_boolean(value):
    if isinstance(value, str):
        if value.lower() in ["t", "true", "on", "yes", "1"]:
            return True
        elif value.lower() in ["f", "false", "off", "no", "0"]:
            return False

    return value


def format_datetime(date):
    return "{} at {}".format(format_date(date), format_time(date))


def format_datetime_24h(date):
    return "{} at {}".format(
        format_date(date),
        format_time_24h(date),
    )


def format_datetime_normal(date):
    return "{} at {}".format(format_date_normal(date), format_time(date))


def format_datetime_short(date):
    return "{} at {}".format(format_date_short(date), format_time(date))


def format_datetime_relative(date):
    return "{} at {}".format(get_human_day(date), format_time(date))


def format_datetime_numeric(date):
    return "{} {}".format(
        format_date_numeric(date),
        format_time_24h(date),
    )


def format_date_numeric(date):
    return utc_string_to_aware_gmt_datetime(date).strftime("%Y-%m-%d")


def format_time_24h(date):
    return utc_string_to_aware_gmt_datetime(date).strftime("%H:%M")


def get_human_day(time, date_prefix=""):

    #  Add 1 minute to transform 00:00 into ‘midnight today’ instead of ‘midnight tomorrow’
    date = (utc_string_to_aware_gmt_datetime(time) - timedelta(minutes=1)).date()
    now = datetime.utcnow()

    if date == (now + timedelta(days=1)).date():
        return _("tomorrow")
    if date == now.date():
        return _("today")
    if date == (now - timedelta(days=1)).date():
        return _("yesterday")
    if date.strftime("%Y") != now.strftime("%Y"):
        return "{} {} {}".format(
            date_prefix,
            _format_datetime_short(date),
            date.strftime("%Y"),
        ).strip()
    return "{} {}".format(
        date_prefix,
        _format_datetime_short(date),
    ).strip()


def format_time(date):
    return (
        {"12:00AM": _("Midnight"), "12:00PM": _("Midday")}
        .get(
            utc_string_to_aware_gmt_datetime(date).strftime("%-I:%M%p"),
            utc_string_to_aware_gmt_datetime(date).strftime("%-I:%M%p"),
        )
        .lower()
    )


def format_date(date):
    return utc_string_to_aware_gmt_datetime(date).strftime("%A %d %B %Y")


def format_date_normal(date):
    return utc_string_to_aware_gmt_datetime(date).strftime("%d %B %Y").lstrip("0")


def format_date_short(date):
    return _format_datetime_short(utc_string_to_aware_gmt_datetime(date))


def format_date_human(date):
    return get_human_day(date)


def format_datetime_human(date, date_prefix=""):
    return "{} at {}".format(
        get_human_day(date, date_prefix="on"),
        format_time(date),
    )


def format_day_of_week(date):
    return utc_string_to_aware_gmt_datetime(date).strftime("%A")


def _format_datetime_short(datetime):
    return datetime.strftime("%d %B").lstrip("0")


def naturaltime_without_indefinite_article(date):
    _base = {
        "minute": _("minute"),
        "minutes": _("minutes"),
        "hour": _("hour"),
        "hours": _("hours"),
        "day": _("day"),
        "days": _("days"),
        "month": _("month"),
        "months": _("months"),
        "year": _("year"),
        "years": _("years"),
    }
    return re.sub(
        "an? (.*) ago",
        lambda match: _("1 {} ago").format(_base.get(match.group(1), match.group(1))),
        humanize.naturaltime(date),
    )


def format_delta(date):
    delta = (datetime.now(timezone.utc)) - (utc_string_to_aware_gmt_datetime(date))
    if delta < timedelta(seconds=30):
        return _("just now")
    if delta < timedelta(seconds=60):
        return _("in the last minute")
    return naturaltime_without_indefinite_article(delta)


def format_delta_days(date):
    now = datetime.now(timezone.utc)
    date = utc_string_to_aware_gmt_datetime(date)
    if date.strftime("%Y-%m-%d") == now.strftime("%Y-%m-%d"):
        return _("today")
    if date.strftime("%Y-%m-%d") == (now - timedelta(days=1)).strftime("%Y-%m-%d"):
        return _("yesterday")
    return naturaltime_without_indefinite_article(now - date)


def valid_phone_number(phone_number):
    try:
        validate_phone_number(phone_number)
        return True
    except InvalidPhoneError:
        return False


def format_notification_type(notification_type):
    return {"email": _("Email"), "sms": _("Text message"), "letter": _("Letter")}[notification_type]


def format_notification_status(status, template_type):
    return {
        "email": {
            "failed": _("Failed"),
            "technical-failure": _("Technical failure"),
            "temporary-failure": _("Inbox not accepting messages right now"),
            "permanent-failure": _("Email address does not exist"),
            "delivered": _("Delivered"),
            "sending": _("Sending"),
            "created": _("Sending"),
            "sent": _("Delivered"),
        },
        "sms": {
            "failed": _("Failed"),
            "technical-failure": _("Technical failure"),
            "temporary-failure": _("Phone not accepting messages right now"),
            "permanent-failure": _("Not delivered"),
            "delivered": _("Delivered"),
            "sending": _("Sending"),
            "created": _("Sending"),
            "pending": _("Sending"),
            "sent": _("Sent to an international number"),
        },
        "letter": {
            "failed": "",
            "technical-failure": _("Technical failure"),
            "temporary-failure": "",
            "permanent-failure": _("Permanent failure"),
            "delivered": "",
            "received": "",
            "accepted": "",
            "sending": "",
            "created": "",
            "sent": "",
            "pending-virus-check": "",
            "virus-scan-failed": _("Virus detected"),
            "returned-letter": "",
            "cancelled": "",
            "validation-failed": _("Validation failed"),
        },
    }[template_type].get(status, status)


def format_notification_status_as_time(status, created, updated):
    return dict.fromkeys({"created", "pending", "sending"}, _(" since {}").format(created)).get(status, updated)


def format_notification_status_as_field_status(status, notification_type):
    return (
        {
            "letter": {
                "failed": _("error"),
                "technical-failure": _("error"),
                "temporary-failure": _("error"),
                "permanent-failure": _("error"),
                "delivered": None,
                "sent": None,
                "sending": None,
                "created": None,
                "accepted": None,
                "pending-virus-check": None,
                "virus-scan-failed": _("error"),
                "returned-letter": None,
                "cancelled": _("error"),
            },
        }
        .get(
            notification_type,
            {
                "failed": _("error"),
                "technical-failure": _("error"),
                "temporary-failure": _("error"),
                "permanent-failure": _("error"),
                "delivered": None,
                "sent": "sent-international" if notification_type == "sms" else None,
                "sending": _("default"),
                "created": _("default"),
                "pending": _("default"),
            },
        )
        .get(status, "error")
    )


def format_notification_status_as_url(status, notification_type):
    url = partial(url_for, "main.message_status")

    if status not in {
        "technical-failure",
        "temporary-failure",
        "permanent-failure",
    }:
        return None

    return {"email": url(_anchor="email-statuses"), "sms": url(_anchor="text-message-statuses")}.get(notification_type)


def nl2br(value):
    if value:
        return Markup(
            Take(
                Field(
                    value,
                    html="escape",
                )
            ).then(utils_nl2br)
        )
    return ""


def format_number_in_pounds_as_currency(number):
    if number >= 1:
        return f"£{number:,.2f}"

    return f"{number * 100:.0f}p"


def format_list_items(items, format_string, *args, **kwargs):
    """
    Apply formatting to each item in an iterable. Returns a list.
    Each item is made available in the format_string as the 'item' keyword argument.
    example usage: ['png','svg','pdf']|format_list_items('{0}. {item}', [1,2,3]) -> ['1. png', '2. svg', '3. pdf']
    """
    return [format_string.format(*args, item=item, **kwargs) for item in items]


def linkable_name(value):
    return urllib.parse.quote_plus(value)


def format_thousands(value):
    if isinstance(value, Number):
        return "{:,.0f}".format(value)
    if value is None:
        return ""
    return value


def email_safe(string, whitespace="."):
    # strips accents, diacritics etc
    string = "".join(c for c in unicodedata.normalize("NFD", string) if unicodedata.category(c) != "Mn")
    string = "".join(
        word.lower() if word.isalnum() or word == whitespace else ""
        for word in re.sub(r"\s+", whitespace, string.strip())
    )
    string = re.sub(r"\.{2,}", ".", string)
    return string.strip(".")


def id_safe(string):
    return email_safe(string, whitespace="-")


def round_to_significant_figures(value, number_of_significant_figures):
    if value == 0:
        return value
    return int(round(value, number_of_significant_figures - int(floor(log10(abs(value)))) - 1))


def redact_mobile_number(mobile_number, spacing=""):
    indices = [-4, -5, -6, -7]
    redact_character = spacing + "•" + spacing
    mobile_number_list = list(mobile_number.replace(" ", ""))
    for i in indices:
        mobile_number_list[i] = redact_character
    return "".join(mobile_number_list)


def get_time_left(created_at, service_data_retention_days=7):
    return ago.human(
        (datetime.now(timezone.utc))
        - (
            dateutil.parser.parse(created_at).replace(hour=0, minute=0, second=0)
            + timedelta(days=service_data_retention_days + 1)
        ),
        future_tense=_("Data available for {}"),
        past_tense=_("Data no longer available"),  # No-one should ever see this
        precision=1,
    )


def starts_with_initial(name):
    return bool(re.match(r"^.\.", name))


def remove_middle_initial(name):
    return re.sub(r"\s+.\s+", " ", name)


def remove_digits(name):
    return "".join(c for c in name if not c.isdigit())


def normalize_spaces(name):
    return " ".join(name.split())


def guess_name_from_email_address(email_address):

    possible_name = re.split(r"[\@\+]", email_address)[0]

    if "." not in possible_name or starts_with_initial(possible_name):
        return ""

    return (
        Take(possible_name)
        .then(str.replace, ".", " ")
        .then(remove_digits)
        .then(remove_middle_initial)
        .then(str.title)
        .then(make_quotes_smart)
        .then(normalize_spaces)
    )


def message_count_label(count, template_type, suffix=None):
    if suffix is None:
        suffix = _("sent")

    if suffix:
        return f"{message_count_noun(count, template_type)} {suffix}"

    return message_count_noun(count, template_type)


def message_count_noun(count, template_type):
    if template_type is None:
        if count == 1:
            return _("message")
        else:
            return _("messages")

    if template_type == "sms":
        if count == 1:
            return _("text message")
        else:
            return _("text messages")

    elif template_type == "email":
        if count == 1:
            return _("email")
        else:
            return _("emails")

    elif template_type == "letter":
        if count == 1:
            return _("letter")
        else:
            return _("letters")

    elif template_type == "broadcast":
        if count == 1:
            return _("broadcast")
        else:
            return _("broadcasts")


def message_count(count, template_type):
    return f"{format_thousands(count)} " f"{message_count_noun(count, template_type)}"


def recipient_count_label(count, template_type):

    if template_type is None:
        if count == 1:
            return _("recipient")
        else:
            return _("recipients")

    if template_type == "sms":
        if count == 1:
            return _("phone number")
        else:
            return _("phone numbers")

    elif template_type == "email":
        if count == 1:
            return _("email address")
        else:
            return _("email addresses")

    elif template_type == "letter":
        if count == 1:
            return _("address")
        else:
            return _("addresses")


def recipient_count(count, template_type):
    return f"{format_thousands(count)} " f"{recipient_count_label(count, template_type)}"


def iteration_count(count):
    if count == 1:
        return _("once")
    elif count == 2:
        return _("twice")
    else:
        return _("%%s times") % count


def character_count(count):
    if count == 1:
        return _("1 character")
    return _("%%s characters") % format_thousands(count)


def format_mobile_network(network):
    if network in ("three", "vodafone", "o2"):
        return network.capitalize()
    return "EE"


def format_billions(count):
    return humanize.intword(count)


def format_yes_no(value, yes=None, no=None, none=None):
    if yes is None:
        yes = _("Yes")
    if no is None:
        no = _("No")
    if none is None:
        none = _("No")

    if value is None:
        return none
    return yes if value else no


def square_metres_to_square_miles(area):
    return area * 3.86e-7


def format_auth_type(auth_type, with_indefinite_article=False):
    indefinite_article, auth_type = {
        "email_auth": ("an", _("Email link")),
        "sms_auth": ("a", _("Text message code")),
        "webauthn_auth": ("a", _("Security key")),
    }[auth_type]

    if with_indefinite_article:
        return f"{indefinite_article} {auth_type.lower()}"

    return auth_type
