# Carried patches

Patches in this directory are applied to the upstream kolla-ansible source while the
image is built. They are grouped per OpenStack release, and the build clones the matching
upstream branch before applying them (see `Containerfile`):

```sh
for patchfile in $(find /patches/$OPENSTACK_VERSION -name "*.patch" | LC_ALL=C sort); do
  ( cd /repository && patch --forward --batch -p1 --dry-run ) < $patchfile || exit 1
  ( cd /repository && patch --forward --batch -p1 ) < $patchfile
done
```

Three things follow from that loop:

- Only files ending in `.patch` are applied. A patch parked as `*.patch.disabled` stays in
  the tree but is not used.
- Patches are applied in `LC_ALL=C` filename order, so renaming a file can change the
  order in which patches apply.
- `patch --forward` treats an already-applied patch as a failure, so a patch that has
  landed upstream in the branch we build from **breaks the build** rather than being
  skipped. Retiring such a patch promptly is not cosmetic.

## Upstream status

Every patch must record what upstream knows about it. Carrying a patch and upstreaming it
are separate pieces of work, and without a written status the second one silently never
happens: a 2026-09 audit found that of 42 carried patches, 23 had never been proposed
upstream at all and one had been copied from a review its author had marked *Do Not
Merge*.

The header goes **above the diff** — `patch` ignores everything before the first
`diff`/`---` line, so for a plain diff it is simply a block at the top of the file, and
for `git format-patch` output it belongs in the commit message next to `Change-Id`.

```
Upstream-Status: Backport [<review url> merged YYYY-MM-DD]
Upstream-Status: Submitted [<review url>]
Upstream-Status: Pending
Upstream-Status: Pending [<reason>]
Upstream-Status: Inappropriate [<reason>]
Upstream-Status: Denied [<reason>]
Bug: <url>
Related: <url> (<short note>)
```

### Values

| Value | Use it when |
|---|---|
| `Backport` | The change is merged upstream on `master`, and we carry it only because the stable branch we build from does not have it yet. The bracket gives the review URL and the date it merged. |
| `Submitted` | Proposed upstream and awaiting review. The bracket gives the review URL. |
| `Pending` | Not submitted upstream. This is the value that represents debt — see below. |
| `Inappropriate` | Will never be upstreamable as written, because it encodes something specific to OSISM: the `/share` layout, our inventory groups, our own playbook handling. The bracket must say which. |
| `Denied` | Proposed and rejected upstream. The bracket gives the reason. |

`Backport` and `Submitted` both mean upstream has the change and the patch retires itself
once the branch catches up. `Pending` and `Inappropriate` are the two that persist, and
they are not interchangeable: `Inappropriate` stops counting as debt, so moving a patch
there is a decision, not a shrug. If the honest answer is "we have not got round to it",
the value is `Pending`.

### `Pending` reasons

The bracket is free text, with one rule. When the reason is that we have not tested the
change enough to defend it upstream, write it as:

```
Upstream-Status: Pending [untested since YYYY-MM-DD: <condition>]
```

The date and the condition are both required, and the condition must be something a
reader can check has happened — "one deployment cycle on a production cloud", not "more
testing". An undated "needs more testing" cannot be wrong, so it never expires; that is
how a temporary carry becomes a permanent one. `check_patch_headers.py --report` lists
these by age.

### `Bug:` and `Related:`

Both optional, both repeatable.

`Bug:` is the upstream bug this patch addresses. It is worth recording separately from
the review because it outlives any individual change — LP#2068002 has spanned two reviews
so far — and because upstream reviewers ask for one.

`Related:` is anything else another maintainer would want to know: a companion change in
another repo (several patches here depend on merged changes in `openstack/kolla`), a fix
in the service's own project rather than in kolla-ansible, or **an open upstream change
that touches the same code**. That last case is the one worth being diligent about. A
competing upstream change will not show up in any search for our own authorship, and when
it merges our patch does not merely become redundant — it conflicts, or it keeps
configuring something that no longer exists.

## Retiring a patch

When the upstream change reaches the branch we build from, delete the patch file. Leaving
it in place breaks the build the next time the branch is refreshed, because
`patch --forward` refuses an already-applied patch.

## Checking

```sh
python3 scripts/check_patch_headers.py            # validate; non-zero on any violation
python3 scripts/check_patch_headers.py --report   # summary by status, and stale entries
python3 scripts/check_patch_headers.py --verify   # check the claims against Gerrit
```

The first two read files only. That is why the validation runs in `check` on every
change: it cannot fail because of anything outside this repository.

`--verify` is different. It reads every review URL and every `Change-Id` out of the
headers and asks Gerrit whether the claim still holds — that a `Backport` really did
merge on the date given, that a `Submitted` change is still open, that a patch recorded
as never pushed really has no change. It needs the network, and it can start failing
because upstream moved rather than because anything here changed, so it runs in
`periodic-daily` and never in `check`. Putting it in the gate would fail unrelated pull
requests on the day an upstream change merges.

For a `Backport` it also asks the question the original review cannot answer: **has the
change reached the branch this release is built from?** That happens as a *separate*
Gerrit change on that branch, sharing the `Change-Id`; the original stays `MERGED` on
master throughout and tells you nothing. So `--verify` looks for a merged sibling on
`stable/<release>` or `unmaintained/<release>`.

Those are Gerrit branch *names*, not the ref the `Containerfile` clones, and the
difference matters. An end-of-life series is built from a tag — 2024.2 from
`2024.2-eol` — but a change never carries a tag in its `branch` field; it keeps the name
of the branch it merged to, and that record outlives the branch. `openstack/kolla-ansible`
has no `stable/2024.2` branch today, while its merged changes still say `stable/2024.2`.
Matching on the tag name would find nothing and silently clear every 2024.2 backport.
`unmaintained/<release>` covers series that were renamed rather than tagged, such as
2024.1.

That is the detector for the case the image build misses, and `backport-953750.patch` is
why it is worth having. A carried patch does not necessarily stop applying when upstream
lands the same fix, so nothing fails: that patch kept applying cleanly for six months
after `stable/2025.1` already had the change, because upstream had fixed it at a
different point in the same file. Comparing patch *content* would not have caught it
either — the carried file turned out to be patch set 1 of the review, which upstream
reworked into something quite different before merging. Only the `Change-Id` links the
two.
