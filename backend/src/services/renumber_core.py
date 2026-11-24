"""换号单的纯逻辑校验：同一批曲谱互换或循环换号，撞号或重号则整单退回。"""

MAX_NUMBER = 999_999_999


def _number(value, label):
    if type(value) is not int or not 1 <= value <= MAX_NUMBER:
        raise ValueError(f'{label}必须为 1 至 {MAX_NUMBER} 之间的整数')
    return value


def plan_renumber(catalog, items):
    """Validate one renumber sheet against the current catalog.

    catalog: iterable of (score_id, number, title) tuples, the current directory.
    items: list of {'number': old, 'new_number': new} dicts.
    Returns the moves to apply, each carrying score_id and title. Raises
    ValueError with the rejection reason; a rejected sheet changes nothing.
    """
    if not isinstance(items, list) or not 1 <= len(items) <= 5000:
        raise ValueError('换号明细须为 1 至 5000 条的数组')
    moves = []
    old_seen = {}
    new_seen = {}
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError(f'第 {index} 项换号明细须为对象')
        old = _number(item.get('number'), f'第 {index} 项的旧编号')
        new = _number(item.get('new_number'), f'第 {index} 项的新编号')
        if old == new:
            raise ValueError(f'第 {index} 项的新编号与旧编号 {old} 相同')
        if old in old_seen:
            raise ValueError(f'旧编号 {old} 在第 {old_seen[old]} 项与第 {index} 项重复出现')
        if new in new_seen:
            raise ValueError(f'新编号 {new} 同时分给第 {new_seen[new]} 项与第 {index} 项，'
                             '同一个新号不能分给多首曲谱')
        old_seen[old] = index
        new_seen[new] = index
        moves.append({'old_number': old, 'new_number': new})

    holders = {}
    for score_id, number, title in catalog:
        holders[number] = (score_id, title)
    missing = [move['old_number'] for move in moves if move['old_number'] not in holders]
    if missing:
        raise ValueError(f'换号单包含目录中不存在的编号：{"、".join(map(str, missing))}')
    for move in moves:
        move['score_id'], move['title'] = holders[move['old_number']]
    participating = {move['score_id'] for move in moves}
    for move in moves:
        holder = holders.get(move['new_number'])
        if holder is not None and holder[0] not in participating:
            raise ValueError(f'新编号 {move["new_number"]} 撞上未参与换号的曲谱'
                             f'《{holder[1]}》（现编号 {move["new_number"]}），整张换号单退回')
    return moves
