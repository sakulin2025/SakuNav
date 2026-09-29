"""分类与链接的数据访问函数（业务仓储层）。

所有函数接收 Database 实例，每次调用独立开连接提交，
避免线程间共享连接带来的并发问题。
"""

from typing import Any, Optional

from sakunav.db import Database


def _next_sort(conn, table: str, where: str = "", params: tuple = ()) -> int:
    row = conn.execute(
        f"SELECT COALESCE(MAX(sort_order), -1) AS m FROM {table} {where}", params
    ).fetchone()
    return int(row["m"]) + 1


# ---------------- 分类 ----------------

def list_categories(db: Database, with_counts: bool = False) -> list[dict]:
    with db.session() as conn:
        if with_counts:
            rows = conn.execute(
                "SELECT c.*, (SELECT COUNT(*) FROM links l WHERE l.category_id = c.id) AS link_count "
                "FROM categories c ORDER BY c.sort_order, c.id"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM categories ORDER BY sort_order, id"
            ).fetchall()
    return [dict(r) for r in rows]


def get_category(db: Database, cid: int) -> Optional[dict]:
    with db.session() as conn:
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (cid,)).fetchone()
    return dict(row) if row else None


def create_category(db: Database, name: str, icon: str = "") -> int:
    with db.session() as conn:
        cur = conn.execute(
            "INSERT INTO categories(name, icon, sort_order) VALUES(?, ?, ?)",
            (name, icon, _next_sort(conn, "categories")),
        )
        return int(cur.lastrowid)


def update_category(db: Database, cid: int, name: Optional[str] = None, icon: Optional[str] = None) -> bool:
    sets, params = [], []
    if name is not None:
        sets.append("name = ?")
        params.append(name)
    if icon is not None:
        sets.append("icon = ?")
        params.append(icon)
    if not sets:
        return False
    sets.append("updated_at = datetime('now')")
    params.append(cid)
    with db.session() as conn:
        cur = conn.execute(f"UPDATE categories SET {', '.join(sets)} WHERE id = ?", params)
        return cur.rowcount > 0


def delete_category(db: Database, cid: int) -> bool:
    with db.session() as conn:
        cur = conn.execute("DELETE FROM categories WHERE id = ?", (cid,))
        return cur.rowcount > 0


def move_category(db: Database, cid: int, direction: str) -> bool:
    """在全局排序中上移/下移一个分类（交换相邻 sort_order）。"""
    with db.session() as conn:
        rows = conn.execute(
            "SELECT id, sort_order FROM categories ORDER BY sort_order, id"
        ).fetchall()
    return _swap_sort(db, rows, cid, direction, "categories")


def _swap_sort(db: Database, rows, target_id: int, direction: str, table: str) -> bool:
    idx = next((i for i, r in enumerate(rows) if r["id"] == target_id), None)
    if idx is None:
        return False
    j = idx - 1 if direction == "up" else idx + 1
    if j < 0 or j >= len(rows):
        return False
    a, b = rows[idx], rows[j]
    with db.session() as conn:
        conn.execute(f"UPDATE {table} SET sort_order = ? WHERE id = ?", (b["sort_order"], a["id"]))
        conn.execute(f"UPDATE {table} SET sort_order = ? WHERE id = ?", (a["sort_order"], b["id"]))
    return True


# ---------------- 链接 ----------------

def list_links(db: Database, category_id: Optional[int] = None, search: Optional[str] = None) -> list[dict]:
    sql = "SELECT * FROM links"
    where, params = [], []
    if category_id is not None:
        where.append("category_id = ?")
        params.append(category_id)
    if search:
        where.append("(title LIKE ? OR url LIKE ? OR description LIKE ?)")
        kw = f"%{search}%"
        params.extend([kw, kw, kw])
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY category_id, sort_order, id"
    with db.session() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_link(db: Database, lid: int) -> Optional[dict]:
    with db.session() as conn:
        row = conn.execute("SELECT * FROM links WHERE id = ?", (lid,)).fetchone()
    return dict(row) if row else None


_LINK_FIELDS = ("category_id", "title", "url", "description", "icon", "color", "sort_order", "target")


def create_link(db: Database, **fields: Any) -> int:
    category_id = int(fields.get("category_id", 0))
    with db.session() as conn:
        cur = conn.execute(
            "INSERT INTO links(category_id, title, url, description, icon, color, sort_order, target) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (
                category_id,
                fields["title"].strip(),
                fields["url"].strip(),
                fields.get("description", "").strip(),
                fields.get("icon", "").strip(),
                fields.get("color", "").strip(),
                fields.get("sort_order", _next_sort(conn, "links", "WHERE category_id = ?", (category_id,))),
                fields.get("target", "_blank"),
            ),
        )
        return int(cur.lastrowid)


def update_link(db: Database, lid: int, **fields: Any) -> bool:
    sets, params = [], []
    for key in _LINK_FIELDS:
        if key in fields:
            sets.append(f"{key} = ?")
            params.append(fields[key])
    if not sets:
        return False
    sets.append("updated_at = datetime('now')")
    params.append(lid)
    with db.session() as conn:
        cur = conn.execute(f"UPDATE links SET {', '.join(sets)} WHERE id = ?", params)
        return cur.rowcount > 0


def delete_link(db: Database, lid: int) -> bool:
    with db.session() as conn:
        cur = conn.execute("DELETE FROM links WHERE id = ?", (lid,))
        return cur.rowcount > 0


def move_link(db: Database, lid: int, direction: str) -> bool:
    """在所属分类内上移/下移一个链接。"""
    link = get_link(db, lid)
    if link is None:
        return False
    with db.session() as conn:
        rows = conn.execute(
            "SELECT id, sort_order FROM links WHERE category_id = ? ORDER BY sort_order, id",
            (link["category_id"],),
        ).fetchall()
    return _swap_sort(db, rows, lid, direction, "links")


# ---------------- 统计 ----------------

def count_links(db: Database) -> int:
    with db.session() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM links").fetchone()
    return int(row["c"])


def count_categories(db: Database) -> int:
    with db.session() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()
    return int(row["c"])


def recent_links(db: Database, limit: int = 8) -> list[dict]:
    with db.session() as conn:
        rows = conn.execute(
            "SELECT l.*, c.name AS category_name FROM links l "
            "LEFT JOIN categories c ON c.id = l.category_id "
            "ORDER BY l.created_at DESC, l.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
