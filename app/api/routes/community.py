# SPDX-License-Identifier: Apache-2.0
"""Membership-based local community groups."""

from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import Caller, caller, can_manage, require_manager
from app.repositories.community import community_db
from app.schemas.community import GroupInput, PostInput


router = APIRouter(prefix="/community/groups")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def group_for(connection, tenant: str, group_id: str):
    row = connection.execute("SELECT * FROM community_groups WHERE id = ? AND tenant = ?",
                             (group_id, tenant)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return row


def joined(connection, group_id: str, identity: Caller) -> bool:
    return connection.execute(
        "SELECT 1 FROM community_members WHERE group_id = ? AND tenant = ? AND user_id = ?",
        (group_id, identity.tenant, identity.user)).fetchone() is not None


def view(connection, row, identity: Caller) -> dict:
    count = connection.execute("SELECT COUNT(*) FROM community_members WHERE group_id = ? AND tenant = ?",
                               (row["id"], identity.tenant)).fetchone()[0]
    return {**dict(row), "member_count": count, "joined": joined(connection, row["id"], identity)}


@router.get("")
def list_groups(identity: Caller = Depends(caller)) -> list[dict]:
    with closing(community_db()) as connection:
        rows = connection.execute("SELECT * FROM community_groups WHERE tenant = ? "
                                  "ORDER BY created_at DESC, rowid DESC LIMIT 100",
                                  (identity.tenant,)).fetchall()
        return [view(connection, row, identity) for row in rows]


@router.post("", status_code=201)
def create_group(body: GroupInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "community_groups")
    title, description = body.title.strip(), body.description.strip()
    if len(title) < 5 or len(description) < 20:
        raise HTTPException(status_code=422, detail="Group text is too short")
    group_id = str(uuid4())
    with closing(community_db()) as connection:
        with connection:
            connection.execute("INSERT INTO community_groups VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (group_id, identity.tenant, title, description,
                                body.area.strip() or None if body.area else None, identity.user, now()))
            connection.execute("INSERT INTO community_members VALUES (?, ?, ?, ?)",
                               (group_id, identity.tenant, identity.user, now()))
        return view(connection, group_for(connection, identity.tenant, group_id), identity)


@router.post("/{group_id}/join")
def join_group(group_id: str, identity: Caller = Depends(caller)) -> dict:
    with closing(community_db()) as connection:
        with connection:
            row = group_for(connection, identity.tenant, group_id)
            connection.execute("INSERT OR IGNORE INTO community_members VALUES (?, ?, ?, ?)",
                               (group_id, identity.tenant, identity.user, now()))
        return view(connection, row, identity)


@router.delete("/{group_id}/join")
def leave_group(group_id: str, identity: Caller = Depends(caller)) -> dict:
    with closing(community_db()) as connection:
        with connection:
            row = group_for(connection, identity.tenant, group_id)
            connection.execute("DELETE FROM community_members WHERE group_id = ? AND tenant = ? AND user_id = ?",
                               (group_id, identity.tenant, identity.user))
        return view(connection, row, identity)


@router.get("/{group_id}/posts")
def list_posts(group_id: str, identity: Caller = Depends(caller)) -> list[dict]:
    with closing(community_db()) as connection:
        group_for(connection, identity.tenant, group_id)
        if not joined(connection, group_id, identity) and not can_manage(identity, "community_groups"):
            raise HTTPException(status_code=403, detail="Join the group to view posts")
        rows = connection.execute("SELECT id, group_id, user_id, body, created_at FROM community_posts "
                                  "WHERE tenant = ? AND group_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 100",
                                  (identity.tenant, group_id)).fetchall()
        return [dict(row) for row in rows]


@router.post("/{group_id}/posts", status_code=201)
def create_post(group_id: str, body: PostInput, identity: Caller = Depends(caller)) -> dict:
    content = body.body.strip()
    if len(content) < 3:
        raise HTTPException(status_code=422, detail="Post text is too short")
    with closing(community_db()) as connection:
        with connection:
            group_for(connection, identity.tenant, group_id)
            if not joined(connection, group_id, identity):
                raise HTTPException(status_code=403, detail="Join the group to post")
            values = (str(uuid4()), group_id, identity.tenant, identity.user, content, now())
            connection.execute("INSERT INTO community_posts VALUES (?, ?, ?, ?, ?, ?)", values)
        row = connection.execute("SELECT id, group_id, user_id, body, created_at "
                                 "FROM community_posts WHERE id = ?", (values[0],)).fetchone()
        return dict(row)
