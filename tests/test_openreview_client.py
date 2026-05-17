"""OpenReview accepted-paper filtering tests."""

from types import SimpleNamespace

from scraper.client import OpenReviewClient


class FakeOpenReviewApi:
    def __init__(self, submission_notes=None, accepted_notes=None):
        self.submission_notes = submission_notes or []
        self.accepted_notes = accepted_notes or []
        self.calls = []

    def get_all_notes(self, invitation, details=None):
        self.calls.append((invitation, details))
        if invitation.endswith("/-/Accepted_Submission"):
            return self.accepted_notes
        if invitation.endswith("/-/Submission"):
            return self.submission_notes
        return []


def make_note(note_id, content=None, direct_replies=None):
    return SimpleNamespace(
        id=note_id,
        content=content or {},
        details={"directReplies": direct_replies or []},
    )


def make_client(api):
    client = object.__new__(OpenReviewClient)
    client.baseurl = "https://api2.openreview.net"
    client.client = api
    return client


class TestOpenReviewAcceptedPapers:
    def test_filters_submissions_by_direct_reply_decision(self):
        venue_id = "ICLR.cc/2024/Conference"
        notes = [
            make_note(
                "accepted",
                direct_replies=[
                    {
                        "invitations": [f"{venue_id}/Paper1/-/Decision"],
                        "content": {"decision": {"value": "Accept (poster)"}},
                    }
                ],
            ),
            make_note(
                "rejected",
                direct_replies=[
                    {
                        "invitations": [f"{venue_id}/Paper2/-/Decision"],
                        "content": {"decision": {"value": "Reject"}},
                    }
                ],
            ),
            make_note(
                "unlabeled",
                content={"venue": {"value": "Submitted to ICLR 2024"}},
            ),
        ]

        client = make_client(FakeOpenReviewApi(submission_notes=notes))

        accepted = list(client.get_accepted_papers(venue_id))

        assert [note.id for note in accepted] == ["accepted"]

    def test_ignores_non_decision_reviewer_recommendations(self):
        venue_id = "ICLR.cc/2024/Conference"
        notes = [
            make_note(
                "accepted_with_reviewer_reject",
                direct_replies=[
                    {
                        "invitations": [f"{venue_id}/Paper1/-/Official_Review"],
                        "content": {"recommendation": {"value": "Reject"}},
                    },
                    {
                        "invitations": [f"{venue_id}/Paper1/-/Decision"],
                        "content": {"decision": {"value": "Accept (poster)"}},
                    },
                ],
            ),
        ]

        client = make_client(FakeOpenReviewApi(submission_notes=notes))

        accepted = list(client.get_accepted_papers(venue_id))

        assert [note.id for note in accepted] == ["accepted_with_reviewer_reject"]

    def test_accepts_final_venueid_and_rejects_reject_venueid(self):
        venue_id = "ICLR.cc/2024/Conference"
        notes = [
            make_note("accepted", content={"venueid": {"value": venue_id}}),
            make_note("rejected", content={"venueid": {"value": f"{venue_id}/Reject"}}),
        ]

        client = make_client(FakeOpenReviewApi(submission_notes=notes))

        accepted = list(client.get_accepted_papers(venue_id))

        assert [note.id for note in accepted] == ["accepted"]

    def test_prefers_explicit_accepted_invitation_when_available(self):
        venue_id = "ICLR.cc/2024/Conference"
        accepted_note = make_note("accepted_invitation")
        rejected_submission = make_note(
            "rejected_submission",
            direct_replies=[
                {
                    "invitations": [f"{venue_id}/Paper2/-/Decision"],
                    "content": {"decision": {"value": "Reject"}},
                }
            ],
        )
        api = FakeOpenReviewApi(
            submission_notes=[rejected_submission],
            accepted_notes=[accepted_note],
        )
        client = make_client(api)

        accepted = list(client.get_accepted_papers(venue_id))

        assert [note.id for note in accepted] == ["accepted_invitation"]
        assert (f"{venue_id}/-/Submission", "directReplies") not in api.calls
