import logging

from agt.config import RedactionFilter


def test_redaction_filter_masks_sensitive_text() -> None:
    filt = RedactionFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="authorization: Bearer abc",
        args=(),
        exc_info=None,
    )
    assert filt.filter(record) is True
    assert record.msg == "[REDACTED SENSITIVE LOG MESSAGE]"
