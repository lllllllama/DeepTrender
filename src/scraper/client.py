"""
OpenReview API 客户端封装
"""

import logging
import re
import time
from typing import Any, Iterable, Optional, Iterator
import openreview
from openreview.api import OpenReviewClient as ORClient

from config import OPENREVIEW_API_URL, OPENREVIEW_USERNAME, OPENREVIEW_PASSWORD


logger = logging.getLogger(__name__)


class OpenReviewClient:
    """OpenReview API 客户端"""

    def __init__(
        self,
        baseurl: str = OPENREVIEW_API_URL,
        username: str = OPENREVIEW_USERNAME,
        password: str = OPENREVIEW_PASSWORD,
    ):
        """
        初始化客户端

        Args:
            baseurl: API 基础 URL
            username: OpenReview 用户名（可选）
            password: OpenReview 密码（可选）
        """
        self.baseurl = baseurl

        # 创建客户端（无需登录也可以访问公开数据）
        if username and password:
            self.client = ORClient(
                baseurl=baseurl,
                username=username,
                password=password,
            )
        else:
            self.client = ORClient(baseurl=baseurl)

    def get_submissions(
        self,
        venue_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
        details: str = "original",
    ) -> Iterator[openreview.api.Note]:
        """
        获取会议的所有提交论文

        Args:
            venue_id: 会议 ID，如 "ICLR.cc/2024/Conference"
            limit: 限制返回数量（None 表示全部）
            offset: 起始偏移量

        Yields:
            论文 Note 对象
        """
        # 获取接受的论文
        invitation = f"{venue_id}/-/Submission"

        try:
            # 尝试获取 Submission invitation
            notes = list(self.client.get_all_notes(
                invitation=invitation,
                details=details,
            ))

            if not notes:
                # 尝试其他常见的 invitation 格式
                alternative_invitations = [
                    f"{venue_id}/-/Blind_Submission",
                    f"{venue_id}/-/blind-submission",
                ]
                for alt_invitation in alternative_invitations:
                    try:
                        notes = list(self.client.get_all_notes(
                            invitation=alt_invitation,
                            details=details,
                        ))
                        if notes:
                            break
                    except Exception:
                        logger.debug(
                            "OpenReview invitation fetch failed: %s",
                            alt_invitation,
                            exc_info=True,
                        )
                        continue
        except Exception:
            logger.exception("Failed to fetch OpenReview submissions for %s", venue_id)
            return

        # 应用 offset 和 limit
        if offset > 0:
            notes = notes[offset:]
        if limit is not None:
            notes = notes[:limit]

        for note in notes:
            yield note

    def get_accepted_papers(
        self,
        venue_id: str,
        limit: Optional[int] = None,
    ) -> Iterator[openreview.api.Note]:
        """
        获取会议接受的论文（通过检查 decision）

        Args:
            venue_id: 会议 ID
            limit: 限制返回数量

        Yields:
            接受的论文 Note 对象
        """
        count = 0

        # Prefer explicit accepted-note invitations when a venue publishes them.
        for note in self._get_explicit_accepted_notes(venue_id):
            yield note
            count += 1
            if limit is not None and count >= limit:
                return
            time.sleep(0.01)

        if count:
            return

        for note in self.get_submissions(venue_id, limit=None, details="directReplies"):
            if not self._is_accepted_note(note, venue_id):
                continue

            yield note
            count += 1
            if limit is not None and count >= limit:
                break
            time.sleep(0.01)

    def _get_explicit_accepted_notes(self, venue_id: str) -> Iterator[openreview.api.Note]:
        """Yield notes from accepted-paper invitations if the venue exposes one."""

        accepted_invitations = [
            f"{venue_id}/-/Accepted_Submission",
            f"{venue_id}/-/Accepted_Paper",
            f"{venue_id}/-/Accepted_Papers",
        ]

        for invitation in accepted_invitations:
            try:
                notes = list(
                    self.client.get_all_notes(
                        invitation=invitation,
                        details="original",
                    )
                )
            except Exception:
                logger.debug(
                    "OpenReview accepted invitation fetch failed: %s",
                    invitation,
                    exc_info=True,
                )
                continue

            if notes:
                yield from notes
                return

    def _is_accepted_note(self, note: Any, venue_id: str) -> bool:
        """Return True only when OpenReview metadata explicitly marks acceptance."""

        decision_texts = list(self._iter_decision_texts(note))
        if not decision_texts:
            return False

        for field, text in decision_texts:
            if self._looks_rejected(text):
                return False

        for field, text in decision_texts:
            if field == "venueid" and self._accepted_venueid(text, venue_id):
                return True
            if self._looks_accepted(text):
                return True

        return False

    def _iter_decision_texts(self, note: Any) -> Iterator[tuple[str, str]]:
        """Extract decision-like text from note content and direct replies."""

        content = getattr(note, "content", {}) or {}
        for field in (
            "decision",
            "final_decision",
            "recommendation",
            "status",
            "venue",
            "venueid",
            "presentation",
            "result",
        ):
            if field in content:
                yield field, self._stringify(self._content_value(content[field]))

        details = getattr(note, "details", {}) or {}
        if not isinstance(details, dict):
            return

        for reply in details.get("directReplies", []) or []:
            reply_content = self._reply_content(reply)
            invitation_text = " ".join(self._reply_invitations(reply)).lower()
            has_decision_invitation = "decision" in invitation_text
            matched_decision_field = False

            for field in ("decision", "final_decision"):
                if field in reply_content:
                    matched_decision_field = True
                    yield field, self._stringify(self._content_value(reply_content[field]))

            if not has_decision_invitation:
                continue

            for field in ("recommendation", "status"):
                if field in reply_content:
                    matched_decision_field = True
                    yield field, self._stringify(self._content_value(reply_content[field]))

            if has_decision_invitation and reply_content and not matched_decision_field:
                yield "decision", self._stringify(reply_content)

    @staticmethod
    def _content_value(value: Any) -> Any:
        if isinstance(value, dict) and "value" in value:
            return value["value"]
        return value

    @staticmethod
    def _reply_content(reply: Any) -> dict:
        if isinstance(reply, dict):
            return reply.get("content", {}) or {}
        return getattr(reply, "content", {}) or {}

    @staticmethod
    def _reply_invitations(reply: Any) -> Iterable[str]:
        if isinstance(reply, dict):
            invitations = reply.get("invitations", []) or []
        else:
            invitations = getattr(reply, "invitations", []) or []
        if isinstance(invitations, str):
            return [invitations]
        return [str(item) for item in invitations]

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            return " ".join(str(item) for item in value)
        if isinstance(value, dict):
            return " ".join(str(item) for item in value.values())
        return str(value)

    @staticmethod
    def _looks_rejected(text: str) -> bool:
        return bool(
            re.search(
                r"\b(reject(?:ed)?|withdrawn?|declin(?:e|ed)|desk reject|not accept(?:ed)?)\b",
                text.lower(),
            )
        )

    @staticmethod
    def _looks_accepted(text: str) -> bool:
        return bool(
            re.search(
                r"\b(accept(?:ed)?|poster|spotlight|oral)\b",
                text.lower(),
            )
        )

    @staticmethod
    def _accepted_venueid(text: str, venue_id: str) -> bool:
        values = {item.strip() for item in re.split(r"[\s,;]+", text) if item.strip()}
        for value in values:
            if value == venue_id:
                return True
            if value.startswith(f"{venue_id}/") and any(
                marker in value.lower()
                for marker in ("accepted", "poster", "spotlight", "oral")
            ):
                return True
        return False


def create_client() -> OpenReviewClient:
    """创建默认客户端"""
    return OpenReviewClient()
