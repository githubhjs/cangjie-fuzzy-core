import itertools
import unittest
from matcher import Matcher


def geometry():
    result = {key: [] for key in 'abcdefghijklmnopqrstuvwxyz'}
    for a, b in [('a', 'b'), ('b', 'c'), ('c', 'd')]:
        result[a].append(b)
        result[b].append(a)
    return result


class MatcherTests(unittest.TestCase):
    def test_exact_order_and_dedup_take_precedence(self):
        matcher = Matcher({'ab': ['first', 'shared', 'last'], 'ac': ['fuzzy', 'shared']}, geometry())
        result = matcher.lookup('ab', 1)
        self.assertEqual([r.text for r in result], ['first', 'shared', 'last', 'fuzzy'])
        self.assertEqual([r.exact for r in result], [True, True, True, False])
        self.assertEqual(result[-1].code, 'ac')

    def test_complete_toy_dictionary_against_hamming_oracle(self):
        neighbors = geometry()
        codes = [''.join(chars) for chars in itertools.product('abcd', repeat=3)]
        matcher = Matcher({code: [code] for code in codes}, neighbors)
        for typed in codes:
            wanted = set()
            for code in codes:
                differences = [i for i in range(3) if typed[i] != code[i]]
                if not differences or (len(differences) == 1 and code[differences[0]] in neighbors[typed[differences[0]]]):
                    wanted.add(code)
            self.assertEqual({r.text for r in matcher.lookup(typed, 1)}, wanted)
            self.assertEqual([r.text for r in matcher.lookup(typed, 0)], [typed])

    def test_input_and_configuration_boundaries(self):
        matcher = Matcher({'a': ['single'], 'b': ['neighbor']}, geometry())
        self.assertEqual([r.text for r in matcher.lookup('a', 1)], ['single'])
        for typed in ['', 'A', 'a b', 'abcdef', 'é']:
            self.assertEqual(matcher.lookup(typed, 1), [])
        for tolerance in [-1, 2, True, 1.0]:
            with self.assertRaises(ValueError): matcher.lookup('a', tolerance)
        bad = geometry(); bad['a'] = []
        with self.assertRaises(ValueError): Matcher({}, bad)


if __name__ == '__main__':
    unittest.main()
