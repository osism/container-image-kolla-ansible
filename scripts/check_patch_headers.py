#!/usr/bin/env python3
"""Check that every carried patch records what upstream knows about it.

See patches/README.md for the convention. Run without arguments to validate;
run with --report for a summary by status and a list of stale "untested"
entries.
"""

import argparse
import datetime
import json
import pathlib
import re
import sys
import urllib.request
from collections import Counter

# Values that must carry a bracketed argument. "Pending" may stand alone; a
# bare "Pending" is the honest way to say "not submitted, no reason recorded".
VALUES = ("Pending", "Submitted", "Backport", "Inappropriate", "Denied")
NEEDS_BRACKET = ("Submitted", "Backport", "Inappropriate", "Denied")

STATUS_RE = re.compile(r"^Upstream-Status:\s*(?P<value>\S+)\s*(?P<rest>.*)$")
BRACKET_RE = re.compile(r"^\[(?P<inner>.*)\]$")
UNTESTED_RE = re.compile(
    r"^untested since (?P<date>\d{4}-\d{2}-\d{2}):\s*(?P<condition>\S.*)$"
)
URL_FIELD_RE = re.compile(r"^(?P<field>Bug|Related):\s*(?P<value>.*)$")

# The diff starts at the first "diff --git", "Index:", or file marker. A bare
# "---" is the git format-patch separator, not a file marker, so it must not
# end the header region.
DIFF_START_RE = re.compile(r"^(diff --git |Index: |--- \S|\+\+\+ \S)")

DEFAULT_STALE_DAYS = 180

GERRIT = "https://review.opendev.org"

REVIEW_URL_RE = re.compile(r"https?://\S*?/(?P<number>\d+)\b")
BACKPORT_CLAIM_RE = re.compile(
    r"https?://\S*?/(?P<number>\d+)\s+merged\s+(?P<date>\d{4}-\d{2}-\d{2})"
)
CHANGE_ID_RE = re.compile(r"^Change-Id:\s*(I[0-9a-f]{8,})\s*$", re.MULTILINE)


class Summary:
    def __init__(self):
        self.counts = Counter()
        self.per_release = {}
        self.stale = []
        self.untracked = []
        self.related = []


def header_of(text):
    """Return the lines above the diff."""
    lines = []
    for line in text.splitlines():
        if DIFF_START_RE.match(line):
            break
        lines.append(line)
    return lines


def untested_date(inner):
    """Return the date from an "untested since ..." reason.

    Returns None when the reason is not that shape, or when it is but names a
    day that does not exist. Both callers go through here so that validation
    and reporting can never disagree about whether a date is usable.
    """
    match = UNTESTED_RE.match(inner)
    if not match:
        return None
    try:
        return datetime.date.fromisoformat(match.group("date"))
    except ValueError:
        return None


def find_patches(root):
    """Yield applied patch files, in the order the build applies them.

    Mirrors the Containerfile: only *.patch is applied, so *.patch.disabled is
    deliberately skipped.
    """
    return sorted(pathlib.Path(root).rglob("*.patch"))


def parse(path):
    """Return (value, bracket, fields) for a patch, or (None, None, fields)."""
    header = header_of(path.read_text(errors="replace"))
    statuses = []
    fields = []
    for line in header:
        match = STATUS_RE.match(line)
        if match:
            statuses.append(match)
        url_match = URL_FIELD_RE.match(line)
        if url_match:
            fields.append((url_match.group("field"), url_match.group("value").strip()))
    return statuses, fields


def check_file(path):
    """Return a list of human-readable problems with one patch file."""
    errors = []
    statuses, fields = parse(path)

    if not statuses:
        errors.append("no Upstream-Status: header (see patches/README.md)")
    elif len(statuses) > 1:
        errors.append("more than one Upstream-Status: header")

    for field, value in fields:
        if not value.startswith("http://") and not value.startswith("https://"):
            errors.append("%s: must be a URL, got %r" % (field, value))

    if len(statuses) != 1:
        return errors

    value = statuses[0].group("value")
    rest = statuses[0].group("rest").strip()

    if value not in VALUES:
        errors.append(
            "unknown Upstream-Status %r, expected one of %s"
            % (value, ", ".join(VALUES))
        )
        return errors

    inner = None
    if rest:
        bracket = BRACKET_RE.match(rest)
        if not bracket:
            errors.append(
                "text after %s must be wrapped in [brackets], got %r" % (value, rest)
            )
            return errors
        inner = bracket.group("inner").strip()

    if value in NEEDS_BRACKET and not inner:
        errors.append(
            "%s requires a bracketed argument, e.g. %s [<url or reason>]"
            % (value, value)
        )

    # Backport and Submitted name a review that --verify has to look up, so
    # validation requires exactly the shape --verify parses. Accepting more
    # here than that mode can read is how a claim ends up silently unchecked.
    if value == "Submitted" and inner and not REVIEW_URL_RE.search(inner):
        errors.append("Submitted requires a review URL, got %r" % inner)
    if value == "Backport" and inner and not BACKPORT_CLAIM_RE.search(inner):
        errors.append(
            "Backport must read [<review url> merged YYYY-MM-DD], got %r" % inner
        )

    if value == "Pending" and inner and inner.split()[0] == "untested":
        match = UNTESTED_RE.match(inner)
        if not match:
            errors.append(
                'Pending [untested ...] must read "untested since YYYY-MM-DD: <condition>", '
                "where the condition is something a reader can check has happened; got %r"
                % inner
            )
        elif untested_date(inner) is None:
            errors.append(
                "Pending [untested since %s: ...] is not a real calendar date"
                % match.group("date")
            )

    return errors


def summarise(root, stale_days=DEFAULT_STALE_DAYS, today=None):
    today = today or datetime.date.today()
    summary = Summary()
    seen_related = set()
    for path in find_patches(root):
        statuses, fields = parse(path)
        if len(statuses) != 1:
            continue
        value = statuses[0].group("value")
        rest = statuses[0].group("rest").strip()
        bracket = BRACKET_RE.match(rest)
        inner = bracket.group("inner").strip() if bracket else ""

        # Counts are per release directory. The same logical patch is carried
        # in several releases under names that do not always match (2026.1
        # prefixes them with NNNN- and renames some), so there is no reliable
        # way to collapse them here -- and "how much does release X carry" is
        # the more useful question anyway.
        release = path.parent.name
        summary.counts[value] += 1
        summary.per_release.setdefault(release, Counter())[value] += 1

        # A Submitted change with no bug is the one upstream reviewers ask
        # about. Pending without a bug is expected, so it is not reported.
        if value == "Submitted" and not any(f == "Bug" for f, _ in fields):
            summary.untracked.append(str(path))

        for field, url in fields:
            if field == "Related" and url not in seen_related:
                seen_related.add(url)
                summary.related.append((path.name, url))

        since = untested_date(inner)
        if since:
            age = (today - since).days
            if age > stale_days:
                summary.stale.append((str(path), age))
    return summary


def report(root, stale_days):
    summary = summarise(root, stale_days=stale_days)
    releases = sorted(summary.per_release)
    print("%d patch files under %s\n" % (sum(summary.counts.values()), root))
    print("  %-14s %s  %s" % ("", "".join("%8s" % r for r in releases), "   all"))
    for value in VALUES:
        cells = "".join("%8d" % summary.per_release[r].get(value, 0) for r in releases)
        print("  %-14s %s  %6d" % (value, cells, summary.counts.get(value, 0)))

    if summary.stale:
        print(
            "\n%d untested entries older than %d days:"
            % (len(summary.stale), stale_days)
        )
        for path, age in sorted(summary.stale, key=lambda item: -item[1]):
            print("  %5d days  %s" % (age, path))

    if summary.related:
        print(
            "\n%d Related: links to check (an open upstream change may be about to land):"
            % len(summary.related)
        )
        for name, url in sorted(summary.related):
            print("  %-52s %s" % (name, url))

    if summary.untracked:
        print(
            "\n%d Submitted patches with no Bug: link (upstream tends to ask):"
            % len(summary.untracked)
        )
        for name in sorted(summary.untracked):
            print("  %s" % name)


def gerrit_get(path):
    """Fetch and decode one Gerrit REST response.

    Gerrit prefixes every JSON body with a )]}' guard line that has to go
    before the rest will parse.
    """
    with urllib.request.urlopen(GERRIT + path, timeout=30) as response:
        body = response.read().decode()
    return json.loads(body.split("\n", 1)[1])


def claims(root):
    """Collect the header claims that name something outside this repository.

    Returns three dicts keyed by what has to be asked of Gerrit, each mapping
    to the patch files making that claim. Keying this way means a change
    carried in six releases is queried once, not six times.
    """
    backport, submitted, unpushed, malformed = {}, {}, {}, []
    for path in find_patches(root):
        statuses, _ = parse(path)
        if len(statuses) != 1:
            continue
        value = statuses[0].group("value")
        bracket = BRACKET_RE.match(statuses[0].group("rest").strip())
        inner = bracket.group("inner").strip() if bracket else ""

        if value == "Backport":
            match = BACKPORT_CLAIM_RE.search(inner)
            if match:
                key = (match.group("number"), match.group("date"))
                backport.setdefault(key, []).append(path)
            else:
                malformed.append((path, "Backport claim %r is unreadable" % inner))
        elif value == "Submitted":
            match = REVIEW_URL_RE.search(inner)
            if match:
                submitted.setdefault(match.group("number"), []).append(path)
            else:
                malformed.append((path, "Submitted claim %r is unreadable" % inner))
        elif value == "Pending" and "never pushed" in inner:
            match = CHANGE_ID_RE.search(path.read_text(errors="replace"))
            if match:
                unpushed.setdefault(match.group(1), []).append(path)
            else:
                malformed.append(
                    (path, "claims it was never pushed, but has no Change-Id")
                )
    return backport, submitted, unpushed, malformed


def candidate_branches(release):
    """The Gerrit branch names a change on this release's line can carry.

    Deliberately not "the ref the Containerfile clones". An end-of-life series
    is built from a tag -- 2024.2 from 2024.2-eol -- but a Gerrit change never
    carries a tag here: it keeps the name of the branch it merged to, and that
    record outlives the branch itself. openstack/kolla-ansible today has no
    stable/2024.2 branch at all, while its merged changes still say
    stable/2024.2. A series that has moved to unmaintained/ carries both names
    over its lifetime, so both are accepted.
    """
    return {"stable/%s" % release, "unmaintained/%s" % release}


def verify(root, get=gerrit_get):
    """Check every header claim that names an external artifact, against Gerrit.

    This needs the network, which is why it is not part of the default
    validation: that one reads files only, so it is safe to gate merges on.
    Upstream state moves on upstream's schedule, so this belongs on a timer.
    """
    problems = []
    backport, submitted, unpushed, malformed = claims(root)
    problems.extend("%s: %s" % (path, reason) for path, reason in malformed)

    for (number, date), paths in sorted(backport.items()):
        change = get("/changes/%s" % number)
        if change["status"] != "MERGED":
            problems.append(
                "%s: Backport %s is %s upstream, not MERGED"
                % (paths[0], number, change["status"])
            )
            continue
        if (change.get("submitted") or "")[:10] != date:
            problems.append(
                "%s: Backport %s merged %s, header says %s"
                % (paths[0], number, (change.get("submitted") or "?")[:10], date)
            )

        # The reason this mode exists. A backport stops being needed when the
        # change reaches the branch we build from, which happens as a separate
        # Gerrit change on that branch -- the original stays MERGED on master
        # and tells us nothing. A carried patch does not necessarily stop
        # applying at that point, so nothing else notices.
        siblings = get("/changes/?q=change:%s" % change["change_id"])
        for path in paths:
            want = candidate_branches(path.parent.name)
            landed = [
                c for c in siblings if c["branch"] in want and c["status"] == "MERGED"
            ]
            if landed:
                problems.append(
                    "%s: redundant -- %s is already on %s as change %s; delete the patch"
                    % (path, number, landed[0]["branch"], landed[0]["_number"])
                )

    for number, paths in sorted(submitted.items()):
        change = get("/changes/%s" % number)
        if change["status"] != "NEW":
            problems.append(
                "%s: Submitted %s is %s upstream; the patch may be retirable"
                % (paths[0], number, change["status"])
            )

    for change_id, paths in sorted(unpushed.items()):
        found = get("/changes/?q=change:%s" % change_id)
        if found:
            problems.append(
                "%s: %s was pushed after all, as %s"
                % (paths[0], change_id, ", ".join(str(c["_number"]) for c in found))
            )

    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=pathlib.Path(__file__).resolve().parent.parent / "patches",
        type=pathlib.Path,
        help="directory holding the per-release patch directories",
    )
    parser.add_argument(
        "--report", action="store_true", help="print a summary instead of validating"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="check header claims against Gerrit (needs network)",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help="age at which an untested entry is reported (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        print("%s is not a directory" % args.root, file=sys.stderr)
        return 2

    if args.report:
        report(args.root, args.stale_days)
        return 0

    if args.verify:
        problems = verify(args.root)
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            print(
                "\n%d header claim(s) no longer match Gerrit" % len(problems),
                file=sys.stderr,
            )
            return 1
        print("all header claims match Gerrit")
        return 0

    failed = 0
    for path in find_patches(args.root):
        errors = check_file(path)
        if errors:
            failed += 1
            for error in errors:
                print("%s: %s" % (path, error), file=sys.stderr)

    if failed:
        print(
            "\n%d patch file(s) with problems; see patches/README.md" % failed,
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
