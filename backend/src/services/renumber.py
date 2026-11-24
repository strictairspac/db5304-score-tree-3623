"""谱夹换号与借阅开单：整单校验、目录版本乐观锁、一次性切换、旧号认回。"""

from fastapi import HTTPException
from sqlalchemy import or_, select

from src.config.settings import engine
from src.models.tables import (borrow_slips, catalog_scores, catalog_state,
                               number_aliases, renumber_orders)
from src.services.renumber_core import MAX_NUMBER, plan_renumber
from src.services.workflow import found, log, recent
from src.utils.time import utc_time

STATE_ID = 1
APPLIED = 'applied'
REJECTED = 'rejected'


def ensure_catalog():
    """Keep the singleton catalog version row, even when demo seeding is off."""
    with engine.begin() as conn:
        exists = conn.execute(select(catalog_state.c.id).where(catalog_state.c.id == STATE_ID)).first()
        if not exists:
            conn.execute(catalog_state.insert().values(id=STATE_ID, version=1))


def _version(conn):
    return conn.execute(select(catalog_state.c.version)
                        .where(catalog_state.c.id == STATE_ID)).scalar_one()


def catalog():
    with engine.connect() as conn:
        rows = conn.execute(select(catalog_scores).order_by(catalog_scores.c.number)).mappings()
        return {'version': _version(conn), 'scores': [dict(row) for row in rows]}


def orders():
    return recent(renumber_orders)


def slips():
    return recent(borrow_slips)


def _record(conn, base_version, items, status, actor, reason=None, result_version=None):
    order_id = conn.execute(renumber_orders.insert().values(
        base_version=base_version, result_version=result_version, status=status, reason=reason,
        items=items, actor=actor, created_at=utc_time())).inserted_primary_key[0]
    log(conn, actor, f'renumber_{status}', order_id)
    return order_id


def _apply(conn, moves, new_version):
    """Switch the whole sheet at once; titles and copies stay with their scores."""
    ids = [move['score_id'] for move in moves]
    # 先把参与曲谱停到负数临时号，再统一落到新号，互换编号时不会触发唯一键冲突。
    conn.execute(catalog_scores.update().where(catalog_scores.c.id.in_(ids))
                 .values(number=-catalog_scores.c.id))
    for move in moves:
        conn.execute(catalog_scores.update().where(catalog_scores.c.id == move['score_id'])
                     .values(number=move['new_number']))
    conn.execute(number_aliases.update()
                 .where(number_aliases.c.score_id.in_(ids), number_aliases.c.to_version.is_(None))
                 .values(to_version=new_version))
    conn.execute(number_aliases.insert(), [
        {'score_id': move['score_id'], 'number': move['new_number'],
         'from_version': new_version, 'to_version': None} for move in moves])


def submit(base_version, items, actor):
    """Apply one renumber sheet, or record it as rejected and send it back whole."""
    if type(base_version) is not int or base_version < 1:
        raise HTTPException(422, '目录版本必须为不小于 1 的整数')
    rejection = None
    with engine.begin() as conn:
        current = _version(conn)
        if current != base_version:
            reason = f'目录已切换到第 {current} 版，基于第 {base_version} 版的换号单整张退回'
            order_id = _record(conn, base_version, items, REJECTED, actor, reason)
            rejection = (409, reason)
        else:
            rows = conn.execute(select(catalog_scores.c.id, catalog_scores.c.number,
                                       catalog_scores.c.title)).all()
            try:
                moves = plan_renumber([(row.id, row.number, row.title) for row in rows], items)
            except ValueError as exc:
                order_id = _record(conn, base_version, items, REJECTED, actor, str(exc))
                rejection = (422, str(exc))
            else:
                bumped = conn.execute(catalog_state.update().where(
                    catalog_state.c.id == STATE_ID,
                    catalog_state.c.version == base_version)
                    .values(version=base_version + 1)).rowcount
                if bumped != 1:
                    # 并发的另一张同版换号单先一步提交，本张退回。
                    reason = '目录版本在提交期间被另一张换号单更新，本张换号单整张退回'
                    order_id = _record(conn, base_version, items, REJECTED, actor, reason)
                    rejection = (409, reason)
                else:
                    _apply(conn, moves, base_version + 1)
                    order_id = _record(conn, base_version, moves, APPLIED, actor,
                                       result_version=base_version + 1)
    if rejection:
        raise HTTPException(rejection[0], rejection[1])
    with engine.connect() as conn:
        return found(conn, renumber_orders, order_id)


def make_slip(range_start, range_end, actor):
    for value, label in ((range_start, '起始曲谱编号'), (range_end, '结束曲谱编号')):
        if type(value) is not int or not 1 <= value <= MAX_NUMBER:
            raise HTTPException(422, f'{label}必须为 1 至 {MAX_NUMBER} 之间的整数')
    if range_start > range_end:
        raise HTTPException(422, '起始曲谱编号须小于或等于结束曲谱编号')
    with engine.begin() as conn:
        slip_id = conn.execute(borrow_slips.insert().values(
            range_start=range_start, range_end=range_end, catalog_version=_version(conn),
            actor=actor, created_at=utc_time())).inserted_primary_key[0]
        log(conn, actor, 'borrow_slip', slip_id)
        return found(conn, borrow_slips, slip_id)


def resolve_range(conn, start, end, version):
    """Map the numbers a slip recorded back then to the scores' current numbers."""
    still_open = or_(number_aliases.c.to_version.is_(None),
                     number_aliases.c.to_version > version)
    rows = conn.execute(
        select(number_aliases.c.number.label('old_number'),
               catalog_scores.c.number.label('current_number'),
               catalog_scores.c.title, catalog_scores.c.available_copies)
        .select_from(number_aliases.join(catalog_scores,
                                         catalog_scores.c.id == number_aliases.c.score_id))
        .where(number_aliases.c.number.between(start, end),
               number_aliases.c.from_version <= version, still_open)
        .order_by(number_aliases.c.number)).mappings()
    return [dict(row) for row in rows]


def slip_detail(identity):
    with engine.connect() as conn:
        slip = found(conn, borrow_slips, identity)
        rows = resolve_range(conn, slip['range_start'], slip['range_end'], slip['catalog_version'])
        return {**slip, 'current_version': _version(conn), 'rows': rows}
