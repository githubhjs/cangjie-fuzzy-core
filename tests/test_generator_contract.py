"""Independent bounded oracle for generated rule sets; complements real-engine probes.

This models fuzz and xlit for the default one-stage generator, not all Rime algebra.
"""
import random
import re
import unittest
import gen_fuzzy as generator


def compile_rules(profile):
    result = []
    for rule in generator.rules(generator.layout_neighbors(profile), 1, 2, 5, 1, False):
        if rule.startswith('fuzz/'):
            _, pattern, replacement, _ = rule.split('/')
            replacement = re.sub(r'\$\{(\d+)\}', r'\\g<\1>', replacement)
            result.append((re.compile(pattern), replacement))
        else:
            assert rule == 'xlit|ABCDEFGHIJKLMNOPQRSTUVWXYZ|abcdefghijklmnopqrstuvwxyz|'
    return result


def project(code, compiled):
    variants = {code}
    for pattern, replacement in compiled:
        variants |= {pattern.sub(replacement, v) for v in variants if pattern.search(v)}
    return {v.lower() for v in variants}


def oracle(code, neighbors):
    expected = {code}
    if len(code) >= 2:
        for i, key in enumerate(code):
            for neighbor in neighbors[key]:
                expected.add(code[:i] + neighbor + code[i + 1:])
    return expected


class GeneratorContract(unittest.TestCase):
    def test_complete_variant_sets_against_independent_oracle(self):
        rng = random.Random(225)
        for profile in ('pc', 'phone'):
            neighbors = generator.layout_neighbors(profile)
            compiled = compile_rules(profile)
            samples = {'yhmbc', 'aaaaa', 'mmmmm', 'zzzzz', 'qwert', 'ppppp'}
            samples |= {key * size for key in neighbors for size in range(1, 6)}
            samples |= {''.join(rng.choice(tuple(neighbors)) for _ in range(size))
                        for size in range(1, 6) for _ in range(80)}
            for code in sorted(samples):
                with self.subTest(profile=profile, code=code):
                    self.assertEqual(project(code, compiled), oracle(code, neighbors))
            print(f'{profile}: {len(samples)} complete variant sets checked')

    def test_tolerance_zero_has_no_rules(self):
        for profile in ('pc', 'phone'):
            self.assertEqual(generator.rules(generator.layout_neighbors(profile), 0, 2, 5, 1, False), [])

    def test_maps_are_symmetric_and_have_no_self_edges(self):
        for profile in ('pc', 'phone'):
            neighbors = generator.layout_neighbors(profile)
            self.assertEqual(set(neighbors), set('abcdefghijklmnopqrstuvwxyz'))
            for key, adjacent in neighbors.items():
                self.assertNotIn(key, adjacent)
                self.assertEqual(len(adjacent), len(set(adjacent)))
                for other in adjacent:
                    self.assertIn(key, neighbors[other])

    def test_reference_error_budget(self):
        for profile in ('pc', 'phone'):
            outputs = project('yhmbc', compile_rules(profile))
            self.assertIn('yhmbv', outputs)
            self.assertIn('yhnbc', outputs)
            self.assertNotIn('yhnbv', outputs)
            self.assertNotIn('yhmbp', outputs)


if __name__ == '__main__':
    unittest.main()
