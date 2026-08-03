#!/usr/bin/env python3
"""groups.py: manage Canvas group sets (group categories) and their teams.

For any course that puts students in teams: create a group set and populate it,
either from a roster mapping you already have (a spreadsheet of who's on which
team) or by letting Canvas randomly distribute students. Delegates every Canvas
call to canvas.py.

Two subcommands:

  create  Make a group set (group category), optionally with empty named groups
          or with Canvas auto-creating and randomly filling N groups.

  assign  Ensure a group set and its named teams exist, then set memberships
          from a JSON file. Members may be Canvas user ids OR emails (resolved
          against the roster). Additive by default (adds missing members, never
          removes); pass --sync to also remove members not listed.

Both subcommands write, so both are gated: nothing reaches Canvas without
--live, and against a course folder that folder's canvas/config.json must also
say "write_mode": "live". Without --live you get the plan -- for `assign`, the
exact per-team add and remove lists. --dry-run is the same preview and wins if
both are given. --sync is the reason this matters: it is the one command here
that removes a student from a team, and a removal is not recoverable from
Canvas's UI history. Every team it touches gets an actions.log line recording
the membership as it was before the change, which is what an undo reads.

Usage:
  groups.py create --course 326 --name "Project Teams" --groups 6 --live
  groups.py create --course 326 --name "Project Teams" --auto 6 --live
  groups.py create --course 326 --name "Study Groups" --self-signup enabled --group-limit 4 --live

  groups.py assign teams.json --course 326 --live
  groups.py assign teams.json --course 326 --sync --dry-run
  groups.py assign teams.json --course-id 12345 --live          # no course folder

teams.json for `assign`:
  {
    "group_set": "Project Teams",
    "self_signup": null,            // or "enabled" / "restricted"
    "group_limit": null,
    "teams": {
      "Team Alpha": [11111, "student@example.edu"],
      "Team Beta":  [33333, 44444]
    }
  }

Output: JSON summary on stdout. Errors: JSON on stderr, nonzero exit code.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canvas_common  # noqa: E402

die = canvas_common.die


class Ctx:
    """What every Canvas call here needs beyond its own arguments.

    Which course folder supplies config and credentials, which numeric course id
    to build paths from, and whether this run has been authorized to write. It is
    threaded through the helpers rather than kept in globals so that `live` has to
    be handed to each call explicitly -- a helper that forgets it produces a dry
    run, which is the safe direction to fail in.
    """

    def __init__(self, args, course_id):
        self.course = args.course
        self.course_id = course_id
        self.override = args.override_mode
        self.live = False  # flipped on only once the gate has said yes


def cc(ctx, cli_args, what, write=False):
    """One canvas.py call, dying with Canvas's own message on failure.

    Reads never carry --live. Writes carry whatever the gate decided, and when it
    decided no they also carry --dry-run so canvas.py prints the request it would
    have sent instead of a blank stdout the caller cannot parse.
    """
    if write and not ctx.live:
        cli_args = list(cli_args) + ["--dry-run"]
    data, error = canvas_common.canvas_cli(
        cli_args, course=ctx.course,
        live=ctx.live if write else False,
        override=ctx.override if write else False)
    if error is not None:
        die(f"Failed to {what}", error)
    return data


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #

def find_category(ctx, name):
    cats = cc(ctx, ["get", f"/courses/{ctx.course_id}/group_categories", "--all"],
              "list group categories")
    return next((c for c in cats if c.get("name") == name), None)


def create_category(ctx, name, self_signup=None, group_limit=None,
                    create_group_count=None):
    # group_categories create is a FLAT payload (not nested under a key).
    payload = {"name": name}
    if self_signup:
        payload["self_signup"] = self_signup
    if group_limit is not None:
        payload["group_limit"] = group_limit
    if create_group_count is not None:
        payload["create_group_count"] = create_group_count
    return cc(ctx, ["post", f"/courses/{ctx.course_id}/group_categories",
                    "--json", json.dumps(payload)],
              "create group category", write=True)


def list_groups(ctx, category_id):
    return cc(ctx, ["get", f"/group_categories/{category_id}/groups", "--all"],
              "list groups in the category")


def create_group(ctx, category_id, name):
    return cc(ctx, ["post", f"/group_categories/{category_id}/groups",
                    "--json", json.dumps({"name": name})],
              f"create group {name!r}", write=True)


def group_member_ids(ctx, group_id):
    users = cc(ctx, ["get", f"/groups/{group_id}/users", "--all"],
               "list group members")
    return {u.get("id") for u in users if u.get("id") is not None}


def roster_email_map(ctx):
    users = cc(ctx, ["get", f"/courses/{ctx.course_id}/users", "--all",
                     "--param", "enrollment_type[]=student", "--param", "include[]=email"],
               "read the roster")
    by_email, id_set = {}, set()
    for u in users:
        uid = u.get("id")
        if uid is None:
            continue
        id_set.add(uid)
        email = (u.get("email") or "").strip().lower()
        if email:
            by_email[email] = uid
    return by_email, id_set


def resolve_member(member, by_email, id_set):
    """A member entry is a user id (int/str) or an email. Return uid or None.

    A numeric id is accepted only if it's an enrolled student (so a wrong id is
    flagged, not silently written); emails resolve through the roster map.
    """
    if isinstance(member, int) or str(member).strip().isdigit():
        uid = int(member)
        return uid if uid in id_set else None
    return by_email.get(str(member).strip().lower())


# --------------------------------------------------------------------------- #
# create
# --------------------------------------------------------------------------- #

def cmd_create(args, course_id):
    ctx = Ctx(args, course_id)
    existing = find_category(ctx, args.name)

    # The existence check reads first and gates second, so a preview of a name
    # that is already taken still shows the plan rather than the gate's note.
    ctx.live = canvas_common.should_write(args, f"group set {args.name!r}")
    if existing and ctx.live:
        die(f"A group set named {args.name!r} already exists",
            {"group_category_id": existing.get("id"),
             "hint": "use `groups.py assign` to populate it, or pick a new name"})

    if args.auto:
        cat = create_category(ctx, args.name, self_signup=args.self_signup,
                              group_limit=args.group_limit, create_group_count=args.auto)
        result = {"group_set": args.name, "mode": "auto", "requested_groups": args.auto}
        if ctx.live:
            cat_id = cat.get("id")
            # create_group_count makes empty groups; distribute students into them.
            prog = cc(ctx, ["post", f"/group_categories/{cat_id}/assign_unassigned_members",
                            "--json", json.dumps({"sync": True})],
                      "auto-assign members", write=True)
            result["group_category_id"] = cat_id
            result["assign_progress"] = {"id": prog.get("id"), "url": prog.get("url"),
                                         "note": "async; poll GET /progress/<id>"}
            # A group set that did not exist has no before-value to record. The
            # undo for this is deleting the category, and the log names it.
            canvas_common.log_action(
                args.course, "group-set-create", cat_id, before=None,
                after={"name": args.name, "mode": "auto",
                       "requested_groups": args.auto,
                       "assign_progress": prog.get("id")},
                course_id=course_id)
        else:
            result["request"] = cat
            result["dry_run"] = True
        print(json.dumps(result, indent=2))
        return

    cat = create_category(ctx, args.name, self_signup=args.self_signup,
                          group_limit=args.group_limit)
    result = {"group_set": args.name, "mode": "manual",
              "self_signup": args.self_signup, "group_limit": args.group_limit}
    if not ctx.live:
        result["dry_run"] = True
        result["request"] = cat
        result["would_create_groups"] = [f"{args.name} {i}" for i in range(1, (args.groups or 0) + 1)]
        print(json.dumps(result, indent=2))
        return

    cat_id = cat.get("id")
    result["group_category_id"] = cat_id
    created = []
    for i in range(1, (args.groups or 0) + 1):
        g = create_group(ctx, cat_id, f"{args.name} {i}")
        created.append({"id": g.get("id"), "name": g.get("name")})
    result["groups_created"] = created
    canvas_common.log_action(
        args.course, "group-set-create", cat_id, before=None,
        after={"name": args.name, "mode": "manual", "groups": created},
        course_id=course_id)
    print(json.dumps(result, indent=2))


# --------------------------------------------------------------------------- #
# assign
# --------------------------------------------------------------------------- #

def cmd_assign(args, course_id):
    spec = canvas_common.load_json_file(args.teams_file, what="Teams file")
    set_name = spec.get("group_set")
    teams = spec.get("teams")
    if not set_name or not isinstance(teams, dict) or not teams:
        die("teams file needs a 'group_set' string and a non-empty 'teams' object")

    ctx = Ctx(args, course_id)
    by_email, id_set = roster_email_map(ctx)

    # Resolve every member up front so a typo aborts before any writes.
    resolved_teams, unresolved = {}, []
    for team, members in teams.items():
        ids = []
        for m in members:
            uid = resolve_member(m, by_email, id_set)
            if uid is None:
                unresolved.append({"team": team, "member": m})
            else:
                ids.append(uid)
        resolved_teams[team] = ids
    if unresolved:
        die("Some members could not be resolved to a Canvas student",
            {"unresolved": unresolved,
             "hint": "use a Canvas user id or an email that matches the roster"})

    category = find_category(ctx, set_name)
    plan = {"group_set": set_name, "teams": {}}

    removals = 0
    ctx.live = canvas_common.should_write(
        args, f"team memberships for {set_name!r}" + (" (with removals)" if args.sync else ""))

    if not ctx.live:
        existing_groups = {g.get("name"): g for g in (list_groups(ctx, category["id"]) if category else [])}
        for team, ids in resolved_teams.items():
            g = existing_groups.get(team)
            current = group_member_ids(ctx, g["id"]) if g else set()
            to_add = [u for u in ids if u not in current]
            to_remove = [u for u in current if u not in ids] if args.sync else []
            removals += len(to_remove)
            plan["teams"][team] = {
                "group_exists": bool(g), "target_members": ids,
                "will_add": to_add, "will_remove": to_remove}
        plan["group_set_exists"] = bool(category)
        plan["dry_run"] = True
        if removals:
            plan["note"] = (f"--sync would remove {removals} student(s) from their "
                            f"current team. Removals are not visible in Canvas's own "
                            f"history; run with --live only once this list is right.")
        print(json.dumps(plan, indent=2))
        return

    if category is None:
        category = create_category(ctx, set_name,
                                   self_signup=spec.get("self_signup"),
                                   group_limit=spec.get("group_limit"))
    cat_id = category["id"]
    existing_groups = {g.get("name"): g for g in list_groups(ctx, cat_id)}

    for team, ids in resolved_teams.items():
        g = existing_groups.get(team) or create_group(ctx, cat_id, team)
        # Read the membership before touching it: this is the before-value the
        # audit log needs, and with --sync it is the only record that a removed
        # student was ever on this team.
        current = group_member_ids(ctx, g["id"])
        added, removed = [], []
        for uid in ids:
            if uid not in current:
                cc(ctx, ["post", f"/groups/{g['id']}/memberships",
                         "--json", json.dumps({"user_id": uid})],
                   f"add user {uid} to {team}", write=True)
                added.append(uid)
        if args.sync:
            for uid in current:
                if uid not in ids:
                    cc(ctx, ["delete", f"/groups/{g['id']}/users/{uid}"],
                       f"remove user {uid} from {team}", write=True)
                    removed.append(uid)
        canvas_common.log_action(
            args.course, "group-assign", f"{set_name}/{team}",
            before=sorted(current), after=sorted(ids if args.sync else set(current) | set(ids)),
            group_id=g["id"], added=added, removed=removed, sync=bool(args.sync),
            course_id=course_id)
        plan["teams"][team] = {"group_id": g["id"], "added": added, "removed": removed,
                               "final_size": len(ids)}
    plan["group_category_id"] = cat_id
    plan["dry_run"] = False
    print(json.dumps(plan, indent=2))


def main():
    common = canvas_common.global_flags()
    parser = argparse.ArgumentParser(
        description="Manage Canvas group sets and teams", parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    pc = sub.add_parser("create", parents=[common],
                        help="Create a group set (group category)")
    pc.add_argument("--name", required=True, help="Name of the group set")
    pc.add_argument("--self-signup", choices=["enabled", "restricted"], default=None,
                    help="Let students self-select (restricted = within their section)")
    pc.add_argument("--group-limit", type=int, default=None,
                    help="Max members per group (needed for self-signup)")
    grp = pc.add_mutually_exclusive_group()
    grp.add_argument("--groups", type=int, default=0,
                     help="Create this many empty named groups")
    grp.add_argument("--auto", type=int, default=0,
                     help="Create this many groups and randomly distribute all students")

    pa = sub.add_parser("assign", parents=[common],
                        help="Populate teams from a JSON mapping")
    pa.add_argument("teams_file", help="Path to a teams JSON file")
    pa.add_argument("--sync", action="store_true",
                    help="Also remove members not listed (default: only add)")

    args = canvas_common.apply_global_defaults(parser.parse_args())
    course_id = canvas_common.resolve_course_id(args.course, args.course_id)

    if args.command == "create":
        cmd_create(args, course_id)
    elif args.command == "assign":
        cmd_assign(args, course_id)


if __name__ == "__main__":
    main()
