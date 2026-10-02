import textwrap

import pytest

import check_patch_headers as chk

PLAIN_DIFF = textwrap.dedent("""\
    --- a/ansible/roles/horizon/defaults/main.yml
    +++ b/ansible/roles/horizon/defaults/main.yml
    @@ -1,1 +1,1 @@
    -old
    +new
    """)

FORMAT_PATCH_DIFF = textwrap.dedent("""\
    ---
     ansible/roles/octavia/templates/x.j2 | 1 +
     1 file changed, 1 insertion(+)

    diff --git a/ansible/roles/octavia/templates/x.j2 b/ansible/roles/octavia/templates/x.j2
    --- a/ansible/roles/octavia/templates/x.j2
    +++ b/ansible/roles/octavia/templates/x.j2
    @@ -1,1 +1,1 @@
    -old
    +new
    """)


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return path


def check(tmp_path, name, header, body=PLAIN_DIFF):
    return chk.check_file(write(tmp_path, name, header + body))


class TestHeaderRegion:
    def test_plain_diff_header_is_read(self, tmp_path):
        assert check(tmp_path, "a.patch", "Upstream-Status: Pending\n\n") == []

    def test_format_patch_header_is_read(self, tmp_path):
        header = textwrap.dedent("""\
            From abc Mon Sep 17 00:00:00 2001
            From: Someone <s@example.com>
            Subject: [PATCH] do a thing

            Upstream-Status: Pending
            Change-Id: I0123456789abcdef0123456789abcdef01234567
            """)
        assert check(tmp_path, "b.patch", header, FORMAT_PATCH_DIFF) == []

    def test_status_inside_the_diff_does_not_count(self, tmp_path):
        body = PLAIN_DIFF + "+Upstream-Status: Pending\n"
        errors = check(tmp_path, "c.patch", "", body)
        assert any("no Upstream-Status" in e for e in errors)


class TestValues:
    @pytest.mark.parametrize(
        "line",
        [
            "Upstream-Status: Pending",
            "Upstream-Status: Pending [nobody has got round to it]",
            "Upstream-Status: Submitted [https://review.opendev.org/c/x/+/1]",
            "Upstream-Status: Backport [https://review.opendev.org/c/x/+/1 merged 2025-01-17]",
            "Upstream-Status: Inappropriate [osism-specific: /share layout]",
            "Upstream-Status: Denied [upstream prefers the other approach]",
        ],
    )
    def test_accepted(self, tmp_path, line):
        assert check(tmp_path, "d.patch", line + "\n\n") == []

    def test_missing_is_an_error(self, tmp_path):
        errors = check(tmp_path, "e.patch", "")
        assert any("no Upstream-Status" in e for e in errors)

    def test_unknown_value_is_an_error(self, tmp_path):
        errors = check(tmp_path, "f.patch", "Upstream-Status: Maybe\n\n")
        assert any("unknown Upstream-Status" in e for e in errors)

    def test_duplicate_is_an_error(self, tmp_path):
        header = "Upstream-Status: Pending\nUpstream-Status: Denied [x]\n\n"
        errors = check(tmp_path, "g.patch", header)
        assert any("more than one" in e for e in errors)

    @pytest.mark.parametrize(
        "value", ["Submitted", "Backport", "Inappropriate", "Denied"]
    )
    def test_bracket_is_required(self, tmp_path, value):
        errors = check(tmp_path, "h.patch", "Upstream-Status: %s\n\n" % value)
        assert any("requires a bracketed" in e for e in errors)

    def test_empty_bracket_is_an_error(self, tmp_path):
        errors = check(tmp_path, "i.patch", "Upstream-Status: Denied []\n\n")
        assert any("requires a bracketed" in e for e in errors)


class TestUntestedNeedsADate:
    def test_dated_untested_is_accepted(self, tmp_path):
        line = "Upstream-Status: Pending [untested since 2026-09-14: no soak on a production cloud]"
        assert check(tmp_path, "j.patch", line + "\n\n") == []

    def test_undated_untested_is_an_error(self, tmp_path):
        errors = check(tmp_path, "k.patch", "Upstream-Status: Pending [untested]\n\n")
        assert any("untested" in e and "since YYYY-MM-DD" in e for e in errors)

    def test_untested_without_a_condition_is_an_error(self, tmp_path):
        line = "Upstream-Status: Pending [untested since 2026-09-14]"
        errors = check(tmp_path, "m.patch", line + "\n\n")
        assert any("untested" in e for e in errors)

    def test_impossible_calendar_date_is_an_error(self, tmp_path):
        """The shape is right but the day does not exist.

        Worth its own case because the shape check alone passes, and the
        reporting path then parses the same string for real.
        """
        line = (
            "Upstream-Status: Pending [untested since 2026-02-30: a deployment cycle]"
        )
        errors = check(tmp_path, "r.patch", line + "\n\n")
        assert any("not a real calendar date" in e for e in errors)

    def test_impossible_month_is_an_error(self, tmp_path):
        line = (
            "Upstream-Status: Pending [untested since 2026-13-01: a deployment cycle]"
        )
        errors = check(tmp_path, "s.patch", line + "\n\n")
        assert any("not a real calendar date" in e for e in errors)

    def test_other_pending_reasons_need_no_date(self, tmp_path):
        assert check(tmp_path, "n.patch", "Upstream-Status: Pending [effort]\n\n") == []


class TestOptionalFields:
    def test_bug_and_related_are_accepted(self, tmp_path):
        header = textwrap.dedent("""\
            Upstream-Status: Pending
            Bug: https://bugs.launchpad.net/kolla-ansible/+bug/2085943
            Related: https://review.opendev.org/c/openstack/kolla-ansible/+/1000345 (competing fix)

            """)
        assert check(tmp_path, "o.patch", header) == []

    def test_repeated_fields_are_accepted(self, tmp_path):
        header = textwrap.dedent("""\
            Upstream-Status: Pending
            Bug: https://bugs.launchpad.net/kolla-ansible/+bug/1
            Bug: https://bugs.launchpad.net/glance/+bug/2

            """)
        assert check(tmp_path, "p.patch", header) == []

    def test_non_url_is_an_error(self, tmp_path):
        header = "Upstream-Status: Pending\nBug: LP#2085943\n\n"
        errors = check(tmp_path, "q.patch", header)
        assert any("must be a URL" in e for e in errors)


class TestDiscovery:
    def test_disabled_patches_are_skipped(self, tmp_path):
        (tmp_path / "2025.1").mkdir()
        (tmp_path / "2025.1" / "x.patch.disabled").write_text(PLAIN_DIFF)
        (tmp_path / "2025.1" / "y.patch").write_text(
            "Upstream-Status: Pending\n\n" + PLAIN_DIFF
        )
        assert [p.name for p in chk.find_patches(tmp_path)] == ["y.patch"]

    def test_patches_are_found_recursively(self, tmp_path):
        for release in ("2025.1", "2026.1"):
            (tmp_path / release).mkdir()
            (tmp_path / release / "z.patch").write_text(
                "Upstream-Status: Pending\n\n" + PLAIN_DIFF
            )
        assert len(list(chk.find_patches(tmp_path))) == 2


class TestReport:
    def test_counts_by_status(self, tmp_path):
        (tmp_path / "2025.1").mkdir()
        (tmp_path / "2025.1" / "a.patch").write_text(
            "Upstream-Status: Pending\n\n" + PLAIN_DIFF
        )
        (tmp_path / "2025.1" / "b.patch").write_text(
            "Upstream-Status: Submitted [https://review.opendev.org/c/x/+/1]\n\n"
            + PLAIN_DIFF
        )
        summary = chk.summarise(tmp_path)
        assert summary.counts["Pending"] == 1
        assert summary.counts["Submitted"] == 1

    def test_the_same_patch_in_two_releases_counts_twice(self, tmp_path):
        """2026.1 renames patches, so cross-release dedup is not reliable.

        Counting per release is honest; pretending to count logical patches
        would silently undercount whatever 2026.1 renamed.
        """
        for release, name in (("2025.2", "x.patch"), ("2026.1", "0007-x.patch")):
            (tmp_path / release).mkdir()
            (tmp_path / release / name).write_text(
                "Upstream-Status: Pending\n\n" + PLAIN_DIFF
            )
        summary = chk.summarise(tmp_path)
        assert summary.counts["Pending"] == 2
        assert summary.per_release["2025.2"]["Pending"] == 1
        assert summary.per_release["2026.1"]["Pending"] == 1

    def test_submitted_without_a_bug_is_flagged(self, tmp_path):
        (tmp_path / "2025.1").mkdir()
        (tmp_path / "2025.1" / "a.patch").write_text(
            "Upstream-Status: Submitted [https://review.opendev.org/c/x/+/1]\n\n"
            + PLAIN_DIFF
        )
        (tmp_path / "2025.1" / "b.patch").write_text(
            "Upstream-Status: Submitted [https://review.opendev.org/c/x/+/2]\n"
            "Bug: https://bugs.launchpad.net/kolla-ansible/+bug/1\n\n" + PLAIN_DIFF
        )
        # Pending without a bug is normal and must not be reported.
        (tmp_path / "2025.1" / "c.patch").write_text(
            "Upstream-Status: Pending\n\n" + PLAIN_DIFF
        )
        summary = chk.summarise(tmp_path)
        assert [p.split("/")[-1] for p in summary.untracked] == ["a.patch"]

    def test_report_does_not_crash_on_an_impossible_date(self, tmp_path):
        """--report is runnable on a tree that has not been validated.

        check_file rejects such a date, so CI never reaches this, but the
        report must not traceback when run by hand on a dirty tree.
        """
        (tmp_path / "2025.1").mkdir()
        (tmp_path / "2025.1" / "a.patch").write_text(
            "Upstream-Status: Pending [untested since 2026-02-30: a soak]\n\n"
            + PLAIN_DIFF
        )
        summary = chk.summarise(tmp_path)
        assert summary.counts["Pending"] == 1
        assert summary.stale == []

    def test_stale_untested_entries_are_listed(self, tmp_path):
        (tmp_path / "2025.1").mkdir()
        old = "Upstream-Status: Pending [untested since 2020-01-01: a soak]\n\n"
        (tmp_path / "2025.1" / "a.patch").write_text(old + PLAIN_DIFF)
        summary = chk.summarise(tmp_path, stale_days=180)
        assert len(summary.stale) == 1
        assert summary.stale[0][1] > 180


class TestVerify:
    """--verify checks the headers against Gerrit.

    Every test here injects a fake fetcher: the unit suite must not need the
    network, and the point of the mode is what it does with the answers.
    """

    BACKPORT = (
        "Upstream-Status: Backport "
        "[https://review.opendev.org/c/openstack/kolla-ansible/+/953750 merged 2026-03-16]"
    )
    SUBMITTED = (
        "Upstream-Status: Submitted "
        "[https://review.opendev.org/c/openstack/kolla-ansible/+/963262]"
    )
    UNPUSHED = "Upstream-Status: Pending [commit prepared but never pushed to Gerrit]"

    @staticmethod
    def fake(change, siblings=()):
        """A Gerrit stand-in: one change by number, a sibling list by query."""

        def get(path):
            if path.startswith("/changes/?q="):
                return list(siblings)
            return change

        return get

    MERGED = {
        "status": "MERGED",
        "submitted": "2026-03-16 10:00:00.000000000",
        "change_id": "I597c8f1f",
    }

    def tree(self, tmp_path, header, body=PLAIN_DIFF, name="a.patch"):
        (tmp_path / "2025.1").mkdir(exist_ok=True)
        (tmp_path / "2025.1" / name).write_text(header + "\n\n" + body)
        return tmp_path

    def test_backport_that_matches_is_silent(self, tmp_path):
        root = self.tree(tmp_path, self.BACKPORT)

        assert chk.verify(root, get=self.fake(self.MERGED)) == []

    def test_backport_not_merged_is_reported(self, tmp_path):
        root = self.tree(tmp_path, self.BACKPORT)

        get = self.fake({"status": "NEW"})
        assert any("not MERGED" in x for x in chk.verify(root, get=get))

    def test_backport_with_the_wrong_date_is_reported(self, tmp_path):
        root = self.tree(tmp_path, self.BACKPORT)

        get = self.fake(dict(self.MERGED, submitted="2026-03-20 10:00:00.000000000"))
        assert any("header says 2026-03-16" in x for x in chk.verify(root, get=get))

    def test_submitted_still_open_is_silent(self, tmp_path):
        root = self.tree(tmp_path, self.SUBMITTED)
        assert chk.verify(root, get=lambda path: {"status": "NEW"}) == []

    def test_submitted_that_merged_is_reported(self, tmp_path):
        """The signal that a carried patch has become retirable."""
        root = self.tree(tmp_path, self.SUBMITTED)
        problems = chk.verify(root, get=lambda path: {"status": "MERGED"})
        assert any("may be retirable" in x for x in problems)

    def test_unpushed_with_no_gerrit_change_is_silent(self, tmp_path):
        body = "Change-Id: I496316eecb12486ac8f83da72201be80098f4920\n" + PLAIN_DIFF
        root = self.tree(tmp_path, self.UNPUSHED, body=body)
        assert chk.verify(root, get=lambda path: []) == []

    def test_unpushed_that_was_pushed_is_reported(self, tmp_path):
        body = "Change-Id: I496316eecb12486ac8f83da72201be80098f4920\n" + PLAIN_DIFF
        root = self.tree(tmp_path, self.UNPUSHED, body=body)
        problems = chk.verify(root, get=lambda path: [{"_number": 12345}])
        assert any("pushed after all, as 12345" in x for x in problems)

    def test_a_change_carried_in_several_releases_is_queried_once(self, tmp_path):
        """Keyed by change, not by file, so six release copies are one query."""
        for release in ("2023.2", "2024.1", "2025.1"):
            (tmp_path / release).mkdir(exist_ok=True)
            (tmp_path / release / "a.patch").write_text(
                self.BACKPORT + "\n\n" + PLAIN_DIFF
            )
        calls = []
        inner = self.fake(self.MERGED)

        def get(path):
            calls.append(path)
            return inner(path)

        assert chk.verify(tmp_path, get=get) == []
        # one lookup by number, one for the sibling branches -- not six of each
        assert len(calls) == 2


class TestClaimsMustBeReadable:
    """A claim --verify cannot parse must not pass validation.

    Accepting more at validation than the verifier can read is how a header
    ends up checked by neither, while --verify still reports success.
    """

    def test_submitted_without_a_url_is_an_error(self, tmp_path):
        errors = check(
            tmp_path, "a.patch", "Upstream-Status: Submitted [not a URL]\n\n"
        )
        assert any("requires a review URL" in e for e in errors)

    def test_backport_without_a_merge_date_is_an_error(self, tmp_path):
        line = "Upstream-Status: Backport [https://review.opendev.org/c/x/+/953750]"
        errors = check(tmp_path, "b.patch", line + "\n\n")
        assert any("merged YYYY-MM-DD" in e for e in errors)

    def test_backport_without_a_url_is_an_error(self, tmp_path):
        errors = check(
            tmp_path, "c.patch", "Upstream-Status: Backport [merged 2026-03-16]\n\n"
        )
        assert any("merged YYYY-MM-DD" in e for e in errors)

    def test_verify_reports_what_it_cannot_parse(self, tmp_path):
        """--verify runs on trees that were never validated."""
        (tmp_path / "2025.1").mkdir()
        (tmp_path / "2025.1" / "a.patch").write_text(
            "Upstream-Status: Submitted [not a URL]\n\n" + PLAIN_DIFF
        )
        problems = chk.verify(tmp_path, get=lambda path: {})
        assert any("unreadable" in x for x in problems)


class TestBackportRedundancy:
    """The case the job exists for: upstream landed it on our branch.

    The original review stays MERGED on master and says nothing about this;
    the signal is a sibling change sharing the Change-Id on the branch the
    image is built from.
    """

    BACKPORT = (
        "Upstream-Status: Backport "
        "[https://review.opendev.org/c/openstack/kolla-ansible/+/953750 merged 2026-03-16]"
    )
    MERGED = {
        "status": "MERGED",
        "submitted": "2026-03-16 10:00:00.000000000",
        "change_id": "I597c8f1f",
    }

    def tree(self, tmp_path, release):
        (tmp_path / release).mkdir()
        (tmp_path / release / "backport-953750.patch").write_text(
            self.BACKPORT + "\n\n" + PLAIN_DIFF
        )
        return tmp_path

    def get(self, siblings):
        def _get(path):
            return list(siblings) if path.startswith("/changes/?q=") else self.MERGED

        return _get

    def test_landed_on_our_branch_is_reported(self, tmp_path):
        root = self.tree(tmp_path, "2025.1")
        siblings = [{"_number": 980968, "branch": "stable/2025.1", "status": "MERGED"}]
        problems = chk.verify(root, get=self.get(siblings))
        assert any("redundant" in x and "980968" in x for x in problems)

    def test_landed_on_another_branch_is_not_reported(self, tmp_path):
        root = self.tree(tmp_path, "2025.1")
        siblings = [{"_number": 980681, "branch": "stable/2025.2", "status": "MERGED"}]
        assert chk.verify(root, get=self.get(siblings)) == []

    def test_open_on_our_branch_is_not_reported(self, tmp_path):
        root = self.tree(tmp_path, "2025.1")
        siblings = [{"_number": 999999, "branch": "stable/2025.1", "status": "NEW"}]
        assert chk.verify(root, get=self.get(siblings)) == []

    def test_an_eol_series_is_matched_by_its_old_branch_name(self, tmp_path):
        """2024.2 is built from the 2024.2-eol tag, but Gerrit never says that.

        The branch was deleted at end of life; its merged changes still carry
        branch "stable/2024.2". Matching on the tag name finds nothing and
        silently clears every 2024.2 backport.
        """
        root = self.tree(tmp_path, "2024.2")
        siblings = [{"_number": 111, "branch": "stable/2024.2", "status": "MERGED"}]
        assert any("redundant" in x for x in chk.verify(root, get=self.get(siblings)))

    def test_a_tag_name_is_never_treated_as_a_branch(self, tmp_path):
        root = self.tree(tmp_path, "2024.2")
        siblings = [{"_number": 111, "branch": "2024.2-eol", "status": "MERGED"}]
        assert chk.verify(root, get=self.get(siblings)) == []

    def test_a_series_moved_to_unmaintained_is_matched(self, tmp_path):
        """2024.1 lives at unmaintained/2024.1; stable/2024.1 is gone."""
        root = self.tree(tmp_path, "2024.1")
        siblings = [
            {"_number": 222, "branch": "unmaintained/2024.1", "status": "MERGED"}
        ]
        assert any("redundant" in x for x in chk.verify(root, get=self.get(siblings)))

    def test_the_reported_branch_is_the_one_actually_found(self, tmp_path):
        root = self.tree(tmp_path, "2024.1")
        siblings = [
            {"_number": 222, "branch": "unmaintained/2024.1", "status": "MERGED"}
        ]
        problems = chk.verify(root, get=self.get(siblings))
        assert any("unmaintained/2024.1" in x for x in problems)

    def test_candidate_branches(self):
        assert chk.candidate_branches("2024.2") == {
            "stable/2024.2",
            "unmaintained/2024.2",
        }
