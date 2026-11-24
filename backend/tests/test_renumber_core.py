"""换号单校验与号码沿革口径的单元测试（仅依赖标准库）。

运行：python3 -I -m unittest discover -s backend/tests -t backend -v
"""

import unittest

from src.services.renumber_core import plan_renumber

CATALOG = [
    (1, 1201, '纸鸢圆舞曲'),
    (2, 1205, '松影三重奏'),
    (3, 1207, '溪畔变奏曲'),
    (4, 1209, '江湾晨曲'),
    (5, 1210, '竹桥间奏'),
]


class PlanRenumberTest(unittest.TestCase):
    def test_swap_two_scores(self):
        moves = plan_renumber(CATALOG, [
            {'number': 1205, 'new_number': 1207},
            {'number': 1207, 'new_number': 1205},
        ])
        self.assertEqual([(m['score_id'], m['new_number']) for m in moves], [(2, 1207), (3, 1205)])
        self.assertEqual([m['title'] for m in moves], ['松影三重奏', '溪畔变奏曲'])

    def test_rotation_cycle(self):
        moves = plan_renumber(CATALOG, [
            {'number': 1205, 'new_number': 1207},
            {'number': 1207, 'new_number': 1209},
            {'number': 1209, 'new_number': 1205},
        ])
        self.assertEqual([m['new_number'] for m in moves], [1207, 1209, 1205])

    def test_move_into_vacant_number(self):
        moves = plan_renumber(CATALOG, [{'number': 1205, 'new_number': 1305}])
        self.assertEqual(moves[0]['score_id'], 2)

    def test_new_number_hits_non_participating_score(self):
        with self.assertRaisesRegex(ValueError, '撞上未参与换号的曲谱《纸鸢圆舞曲》'):
            plan_renumber(CATALOG, [
                {'number': 1205, 'new_number': 1305},
                {'number': 1207, 'new_number': 1201},
            ])

    def test_same_new_number_for_two_scores(self):
        with self.assertRaisesRegex(ValueError, '同一个新号不能分给多首曲谱'):
            plan_renumber(CATALOG, [
                {'number': 1205, 'new_number': 1305},
                {'number': 1207, 'new_number': 1305},
            ])

    def test_unknown_old_number(self):
        with self.assertRaisesRegex(ValueError, '目录中不存在的编号：1401'):
            plan_renumber(CATALOG, [{'number': 1401, 'new_number': 1402}])

    def test_duplicate_old_number(self):
        with self.assertRaisesRegex(ValueError, '重复出现'):
            plan_renumber(CATALOG, [
                {'number': 1205, 'new_number': 1305},
                {'number': 1205, 'new_number': 1306},
            ])

    def test_same_old_and_new_number(self):
        with self.assertRaisesRegex(ValueError, '相同'):
            plan_renumber(CATALOG, [{'number': 1205, 'new_number': 1205}])

    def test_rejects_malformed_items(self):
        for bad in (None, {}, [], [{'number': 1205}], [{'number': True, 'new_number': 2}],
                    [{'number': 1205.5, 'new_number': 1305}], [{'number': '1205', 'new_number': 1305}],
                    [{'number': 0, 'new_number': 1305}], [{'number': 1205, 'new_number': 10**10}],
                    ['1205→1305'], [{}] * 5001):
            with self.assertRaises(ValueError, msg=repr(bad)):
                plan_renumber(CATALOG, bad)

    def test_input_items_are_not_mutated(self):
        items = [{'number': 1205, 'new_number': 1305}]
        plan_renumber(CATALOG, items)
        self.assertEqual(items, [{'number': 1205, 'new_number': 1305}])


class DirectoryModel:
    """In-memory mirror of the SQL semantics in renumber._apply / resolve_range."""

    def __init__(self, catalog):
        self.version = 1
        self.current = {score_id: [number, title] for score_id, number, title in catalog}
        self.aliases = [
            {'score_id': score_id, 'number': number, 'from_version': 1, 'to_version': None}
            for score_id, number, _ in catalog
        ]

    def apply(self, moves):
        self.version += 1
        for move in moves:
            score_id = move['score_id']
            for alias in self.aliases:
                if alias['score_id'] == score_id and alias['to_version'] is None:
                    alias['to_version'] = self.version
            self.aliases.append({'score_id': score_id, 'number': move['new_number'],
                                 'from_version': self.version, 'to_version': None})
            self.current[score_id][0] = move['new_number']

    def resolve(self, start, end, version):
        rows = []
        for alias in self.aliases:
            open_at_version = alias['to_version'] is None or alias['to_version'] > version
            if start <= alias['number'] <= end and alias['from_version'] <= version and open_at_version:
                number, title = self.current[alias['score_id']]
                rows.append({'old_number': alias['number'], 'current_number': number, 'title': title})
        return sorted(rows, key=lambda row: row['old_number'])


class NumberHistoryTest(unittest.TestCase):
    def test_old_slip_recognizes_scores_after_several_renumberings(self):
        directory = DirectoryModel(CATALOG)
        slip_version = directory.version  # 借阅单按第 1 版目录开出，号段 1204 至 1212
        directory.apply(plan_renumber(CATALOG, [
            {'number': 1205, 'new_number': 1207},
            {'number': 1207, 'new_number': 1209},
            {'number': 1209, 'new_number': 1205},
        ]))
        catalog_v2 = [(sid, number, title) for sid, (number, title) in directory.current.items()]
        directory.apply(plan_renumber(catalog_v2, [
            {'number': 1207, 'new_number': 1307},
            {'number': 1205, 'new_number': 1305},
        ]))
        rows = directory.resolve(1204, 1212, slip_version)
        by_old = {row['old_number']: row for row in rows}
        self.assertEqual(set(by_old), {1205, 1207, 1209, 1210})
        # 1205 的曲谱经两次换号：1205 → 1207 → 1307
        self.assertEqual(by_old[1205]['current_number'], 1307)
        self.assertEqual(by_old[1205]['title'], '松影三重奏')
        # 1209 的曲谱换过一次：1209 → 1205 → 1305
        self.assertEqual(by_old[1209]['current_number'], 1305)
        # 1207 的曲谱经循环换号到 1209，未参与第二单
        self.assertEqual(by_old[1207]['current_number'], 1209)
        # 未换号的曲谱保持原号
        self.assertEqual(by_old[1210]['current_number'], 1210)

    def test_number_reuse_resolves_to_the_score_holding_it_at_slip_time(self):
        directory = DirectoryModel(CATALOG)
        slip_version = directory.version
        catalog_v1 = [(sid, number, title) for sid, (number, title) in directory.current.items()]
        # 第一单：1205 的曲谱让出编号，迁往 1305
        directory.apply(plan_renumber(catalog_v1, [{'number': 1205, 'new_number': 1305}]))
        catalog_v2 = [(sid, number, title) for sid, (number, title) in directory.current.items()]
        # 第二单：另一首曲谱改占用空出的 1205
        directory.apply(plan_renumber(catalog_v2, [{'number': 1210, 'new_number': 1205}]))
        rows = directory.resolve(1205, 1205, slip_version)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['title'], '松影三重奏')
        self.assertEqual(rows[0]['current_number'], 1305)

    def test_current_version_resolution_matches_current_directory(self):
        directory = DirectoryModel(CATALOG)
        catalog_v1 = [(sid, number, title) for sid, (number, title) in directory.current.items()]
        directory.apply(plan_renumber(catalog_v1, [
            {'number': 1205, 'new_number': 1207},
            {'number': 1207, 'new_number': 1205},
        ]))
        rows = directory.resolve(1, 999_999_999, directory.version)
        self.assertEqual([(r['old_number'], r['title']) for r in rows],
                         [(1201, '纸鸢圆舞曲'), (1205, '溪畔变奏曲'), (1207, '松影三重奏'),
                          (1209, '江湾晨曲'), (1210, '竹桥间奏')])


if __name__ == '__main__':
    unittest.main()
