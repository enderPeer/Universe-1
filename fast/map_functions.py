"""Recognize named finite-word functions and verify every match by execution.

Run from any directory: python fast/map_functions.py [--only RUN]
Reads only completed exp03 results and their original, extracted binary shards.
"""
import argparse
import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path

from crosscheck import key
from merge import PNAME
from sim.machine import Config, Machine, USES_OPERAND

ROOT = Path(__file__).resolve().parents[1]


def catalog(width, binary):
    n, mask = 1 << width, (1 << width) - 1
    unary = []

    def add(name, expression, fn):
        unary.append((name, expression, tuple(fn(x) & mask for x in range(n))))

    def signed(x):
        return x if x < n // 2 else x - n

    def rol(x, k):
        k %= width
        return ((x << k) | (x >> ((width - k) % width))) & mask

    def gray_decode(x):
        value = 0
        while x:
            value ^= x
            x >>= 1
        return value

    add('identity', 'x', lambda x: x)
    add('negation', '-x mod N', lambda x: -x)
    add('bitwise_not', '~x masked to W bits', lambda x: ~x)
    add('increment', '(x + 1) mod N', lambda x: x + 1)
    add('decrement', '(x - 1) mod N', lambda x: x - 1)
    add('square', 'x^2 mod N', lambda x: x*x)
    add('cube', 'x^3 mod N', lambda x: x*x*x)
    add('integer_sqrt', 'floor(sqrt(x))', math.isqrt)
    add('popcount', 'number of set bits in x, reduced mod N', int.bit_count)
    add('parity', 'popcount(x) mod 2', lambda x: x.bit_count() & 1)
    add('bit_reverse', 'reverse the W bits of x', lambda x: int(f'{x:0{width}b}'[::-1], 2))
    add('gray_encode', 'x XOR (x >> 1)', lambda x: x ^ (x >> 1))
    add('gray_decode', 'inverse reflected Gray-code transform', gray_decode)
    add('signed_abs', 'abs(signed_W(x)) mod N', lambda x: abs(signed(x)))
    add('signed_signum', 'sign(signed_W(x)) encoded mod N', lambda x: (signed(x) > 0) - (signed(x) < 0))
    add('is_zero', '1 if x = 0 else 0', lambda x: int(x == 0))
    add('is_nonzero', '1 if x != 0 else 0', lambda x: int(x != 0))
    add('is_power_of_two', '1 if x is a positive power of two else 0', lambda x: int(x != 0 and x & (x-1) == 0))
    add('lowest_set_bit', 'x AND (-x), masked to W bits', lambda x: x & -x)
    add('clear_lowest_set_bit', 'x AND (x-1)', lambda x: x & (x-1))
    add('floor_log2_zero_is_zero', 'floor(log2(x)); define output 0 at x=0', lambda x: max(0, x.bit_length()-1))
    add('leading_zeros_mod_N', 'W - bit_length(x), reduced mod N', lambda x: width-x.bit_length())
    add('trailing_zeros_mod_N', 'trailing-zero count; x=0 maps to W mod N', lambda x: width if x == 0 else (x & -x).bit_length()-1)
    for c in range(n):
        add(f'constant_{c}', str(c), lambda x, c=c: c)
        add(f'add_{c}', f'(x + {c}) mod N', lambda x, c=c: x+c)
        add(f'multiply_{c}', f'{c}*x mod N', lambda x, c=c: c*x)
        add(f'xor_{c}', f'x XOR {c}', lambda x, c=c: x^c)
        add(f'and_{c}', f'x AND {c}', lambda x, c=c: x&c)
        add(f'or_{c}', f'x OR {c}', lambda x, c=c: x|c)
        if width <= 4:
            add(f'equal_{c}', f'1 if x={c} else 0', lambda x, c=c: int(x == c))
            add(f'less_than_{c}', f'1 if x<{c} else 0 (unsigned)', lambda x, c=c: int(x < c))
    # Exhaust all affine maps for small widths; explicitly bounded catalog at W=8.
    constants = range(n) if width <= 4 else (0, 1, 2, 3, 4, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 254, 255)
    for a in constants:
        for b in constants:
            add(f'affine_{a}_{b}', f'({a}*x + {b}) mod N', lambda x, a=a, b=b: a*x+b)
    for k in range(1, width+1):
        add(f'shift_left_{k}', f'(x << {k}) mod N', lambda x, k=k: x << k)
        add(f'shift_right_{k}', f'x >> {k} (unsigned)', lambda x, k=k: x >> k)
        add(f'signed_shift_right_{k}', f'signed_W(x) >> {k}, encoded mod N', lambda x, k=k: signed(x) >> k)
        add(f'rotate_left_{k}', f'rotate W-bit x left by {k}', lambda x, k=k: rol(x, k))
        add(f'rotate_right_{k}', f'rotate W-bit x right by {k}', lambda x, k=k: rol(x, -k))
    if not binary:
        return unary

    result = []
    def binary_add(name, expression, fn):
        result.append((name, expression, tuple(fn(x, y) & mask for x in range(n) for y in range(n))))

    # Include functions that depend on just one of the two inputs.
    for name, expression, table in unary:
        result.append((name + '_of_x', expression + ' (ignore y)', tuple(table[x] for x in range(n) for y in range(n))))
        result.append((name + '_of_y', expression.replace('x', 'y') + ' (ignore x)', tuple(table[y] for x in range(n) for y in range(n))))
    specifications = [
        ('add', '(x+y) mod N', lambda x,y: x+y),
        ('subtract', '(x-y) mod N', lambda x,y: x-y),
        ('reverse_subtract', '(y-x) mod N', lambda x,y: y-x),
        ('multiply', 'x*y mod N', lambda x,y: x*y),
        ('power', 'x^y mod N; 0^0=1', lambda x,y: pow(x,y,n)),
        ('unsigned_divide_zero_returns_zero', 'floor(x/y); output 0 if y=0', lambda x,y: x//y if y else 0),
        ('unsigned_remainder_zero_returns_zero', 'x mod y; output 0 if y=0', lambda x,y: x%y if y else 0),
        ('gcd', 'gcd(x,y); gcd(0,0)=0', math.gcd),
        ('lcm_mod_N', 'lcm(x,y) mod N', math.lcm),
        ('unsigned_min', 'min(x,y)', min), ('unsigned_max', 'max(x,y)', max),
        ('signed_min', 'min(signed_W(x),signed_W(y)) encoded mod N', lambda x,y: min(signed(x),signed(y))),
        ('signed_max', 'max(signed_W(x),signed_W(y)) encoded mod N', lambda x,y: max(signed(x),signed(y))),
        ('absolute_difference', '|x-y| (unsigned inputs)', lambda x,y: abs(x-y)),
        ('saturating_add', 'min(x+y,N-1)', lambda x,y: min(x+y,mask)),
        ('saturating_subtract', 'max(x-y,0)', lambda x,y: max(x-y,0)),
        ('and', 'x AND y', lambda x,y: x&y), ('or', 'x OR y', lambda x,y: x|y),
        ('xor', 'x XOR y', lambda x,y: x^y), ('nand', 'NOT(x AND y)', lambda x,y: ~(x&y)),
        ('nor', 'NOT(x OR y)', lambda x,y: ~(x|y)), ('xnor', 'NOT(x XOR y)', lambda x,y: ~(x^y)),
        ('and_not', 'x AND NOT y', lambda x,y: x & ~y),
        ('bitwise_implication', '(NOT x) OR y', lambda x,y: ~x|y),
        ('hamming_distance', 'popcount(x XOR y), reduced mod N', lambda x,y: (x^y).bit_count()),
        ('shift_left_by_y', '(x << y) mod N; y>=W gives 0', lambda x,y: x << y),
        ('shift_right_by_y', 'x >> y (unsigned); y>=W gives 0', lambda x,y: x >> y),
        ('rotate_left_by_y', 'rotate W-bit x left by y mod W', lambda x,y: rol(x,y)),
        ('rotate_right_by_y', 'rotate W-bit x right by y mod W', lambda x,y: rol(x,-y)),
        ('carry', '1 if x+y>=N else 0', lambda x,y: int(x+y>=n)),
        ('borrow', '1 if x<y else 0 (unsigned)', lambda x,y: int(x<y)),
    ]
    for item in specifications:
        binary_add(*item)
    for name, predicate in [('equal', lambda x,y: x == y), ('not_equal', lambda x,y: x != y),
                            ('less_than', lambda x,y: x < y), ('less_equal', lambda x,y: x <= y),
                            ('greater_than', lambda x,y: x > y), ('greater_equal', lambda x,y: x >= y)]:
        for sign in (False, True):
            for full_mask in (False, True):
                suffix = ('_signed' if sign else '_unsigned') + ('_mask' if full_mask else '_bool')
                binary_add(name+suffix, f'{name}: {"signed" if sign else "unsigned"} inputs, true={mask if full_mask else 1}, false=0',
                           lambda x,y,f=predicate,s=sign,m=full_mask: (mask if m else 1)*int(f(signed(x),signed(y)) if s else f(x,y)))
    # All 16 bitwise Boolean functions, including aliases of the named operations.
    for truth in range(16):
        binary_add(f'bitwise_boolean_{truth:04b}', f'per-bit Boolean table 0b{truth:04b}, bit index=2*x_bit+y_bit',
                   lambda x,y,t=truth: sum(((t >> (2*((x>>k)&1)+((y>>k)&1))) & 1) << k for k in range(width)))
    return result


def recognize(path, candidates):
    data = json.loads(path.read_text())
    tag = path.stem.removeprefix('exp03_')
    grouped = {}
    for name, expression, table in candidates:
        table_key = key(table, data['W'])
        group = grouped.setdefault(table_key, {'table': table, 'names': []})
        if group['table'] != table:
            raise ValueError('Catalog hash collision')
        group['names'].append({'name': name, 'expression': expression})
    best, ranges = {}, []
    files = sorted((ROOT / 'results/shards').glob(f'{tag}_[0-9][0-9][0-9][0-9].bin'))
    for shard in files:
        blob = shard.read_bytes()
        header = struct.unpack_from('<8I3Q', blob)
        magic,w,a,p,i,o,binary,nisa,lo,hi,count = header
        if magic != 0x55314231 or (w,a,p,i,o,bool(binary)) != (data['W'],data['a'],data['p'],data['I'],data['opcode_bits'],data['binary']):
            raise ValueError(f'Incorrect header: {shard}')
        offset = 56+nisa
        if list(blob[56:offset]) != [PNAME.index(name) for name in data['isa']]:
            raise ValueError(f'Incorrect ISA IDs: {shard}')
        if len(blob) != offset+count*20:
            raise ValueError(f'Truncated shard: {shard}')
        ranges.append([lo,hi])
        for low, high, program in struct.iter_unpack('<QQI', memoryview(blob)[offset:]):
            k = low, high
            if k in grouped and (k not in best or program < best[k][0]):
                if not lo <= program < hi:
                    raise ValueError(f'Witness outside shard range: {shard}')
                best[k] = program, shard.name
    cursor = 0
    for lo, hi in sorted(ranges):
        if lo != cursor or hi <= lo:
            raise ValueError(f'Invalid coverage: {tag}')
        cursor = hi
    if cursor != 1 << 32 or sorted(ranges) != sorted(data['programs_covered']):
        raise ValueError(f'Incomplete source shards: {tag}')
    cfg = Config(W=data['W'], a=data['a'], p=data['p'], I=data['I'])
    machine = Machine(cfg, tuple(data['isa']))
    matches = []
    for k, (program, shard) in sorted(best.items(), key=lambda item: item[1][0]):
        words = [(program >> (j*cfg.I)) & ((1 << cfg.I)-1) for j in range(1 << cfg.p)]
        observed, reasons, steps = [], Counter(), []
        for x in range(1 << cfg.W):
            for y in range(1 << cfg.W) if data['binary'] else (0,):
                memory = [0] * (1 << cfg.a)
                if data['binary']: memory[1] = y
                state, used, reason = machine.run(words, init_A=x, init_M=memory)
                observed.append(state.A); reasons[reason] += 1; steps.append(used)
        if tuple(observed) != grouped[k]['table']:
            raise ValueError(f'False fingerprint match or invalid witness: {tag}, {program}')
        disassembly = []
        for word in words:
            opcode = data['isa'][word >> (cfg.I-machine.o)]
            disassembly.append(opcode + (f' {word & machine.opmask}' if opcode in USES_OPERAND else ''))
        matches.append({'aliases': grouped[k]['names'], 'truth_table': observed,
                        'key_low': k[0], 'key_high': k[1], 'program_id': program,
                        'program_hex': f'0x{program:08x}', 'instruction_words': words,
                        'disassembly': disassembly, 'source_shard': shard,
                        'reference_verified_inputs': len(observed), 'termination_counts': dict(reasons),
                        'mean_budget_or_halt_steps': sum(steps)/len(steps), 'max_budget_or_halt_steps': max(steps)})
    names_found = {alias['name'] for match in matches for alias in match['aliases']}
    return {'run': tag, 'W': data['W'], 'binary': data['binary'], 'isa': data['isa'],
            'geometry': {k:data[k] for k in ('a','p','I','opcode_bits')},
            'source_result_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'source_distinct_operators': data['distinct_operators'], 'source_shards': len(files),
            'catalog_labels': len(candidates), 'catalog_distinct_tables': len(grouped),
            'matched_distinct_tables': len(matches), 'matched_labels': len(names_found),
            'matches': matches,
            'not_found_in_this_run': [{'name':name,'expression':expr} for name,expr,_ in candidates if name not in names_found]}


def write_summary(out):
    reports = [json.loads(p.read_text()) for p in sorted(out.glob('*.json'))]
    lines = ['# Named mathematical functions found in Universe-1', '',
             'Exact finite-domain recognition against a bounded, explicit catalog. All matched witnesses were replayed on every input using the Python reference simulator.', '',
             'For a broader vocabulary including composed expressions, see the [Rust mapper usability matrix](../maps/usability.md) and [mapper documentation](../../docs/03_function_map.md). The catalogs differ, so their named-function counts are not directly comparable. This report retains every matching alias and explicitly states signedness, modular arithmetic, and zero-divisor conventions.', '',
             'Arithmetic wraps modulo N=2^W unless the formula says otherwise. Signed values use two\'s complement. Comparisons explicitly distinguish 0/1 from 0/all-ones outputs.', '',
             'A match describes the accumulator at HALT or step 256; it does not imply termination. Witness IDs are minimum numeric IDs across the source shards, not shortest or fastest programs.', '',
             'Unmatched functions are unclassified by this catalog, not established as novel. A missing label means it was not found in that completed run, not that it is impossible with a different ISA, geometry, or budget.', '',
             '| Run | Mode | Discovered functions | Catalog tables | Matched tables | Matched names (aliases included) |',
             '|---|---|---:|---:|---:|---:|']
    for r in reports:
        lines.append(f"| [{r['run']}]({r['run']}.json) | W={r['W']} {'binary' if r['binary'] else 'unary'} | {r['source_distinct_operators']:,} | {r['catalog_distinct_tables']} | {r['matched_distinct_tables']} | {r['matched_labels']} |")
    lines += ['', '## Distinct recognized functions across ISAs', '',
              'These counts deduplicate identical truth tables within each width and arity; aliases and repeats across ISAs count once.', '',
              '| Width | Mode | Distinct recognized functions |', '|---|---|---:|']
    for width, binary in sorted({(r['W'], r['binary']) for r in reports}):
        tables = {tuple(m['truth_table']) for r in reports if (r['W'],r['binary']) == (width,binary) for m in r['matches']}
        lines.append(f"| {width} | {'binary' if binary else 'unary'} | {len(tables)} |")
    lines += ['', '## Affine arithmetic at W=4', '',
              'There are 256 distinct functions `(a*x+b) mod 16` for a,b in 0..15.', '',
              '| Unary run | Affine functions found / 256 |', '|---|---:|']
    for r in reports:
        if r['W'] == 4 and not r['binary']:
            count = sum(a['name'].startswith('affine_') for m in r['matches'] for a in m['aliases'])
            lines.append(f"| {r['run']} | {count} |")
    highlights = {False: ['identity','negation','bitwise_not','increment','decrement','square','cube','integer_sqrt','popcount','parity','bit_reverse','gray_encode','signed_abs','is_zero','shift_left_1','shift_right_1','rotate_left_1'],
                  True: ['add','subtract','multiply','unsigned_divide_zero_returns_zero','unsigned_remainder_zero_returns_zero','unsigned_min','unsigned_max','gcd','lcm_mod_N','and','or','xor','nand','xnor','equal_unsigned_bool','less_than_unsigned_bool','less_than_unsigned_mask','carry','saturating_add','absolute_difference']}
    for binary in (False, True):
        lines += ['', f"## W=4 {'binary' if binary else 'unary'} highlights", '', '| Function | Matching completed runs and verified witness IDs |', '|---|---|']
        for name in highlights[binary]:
            hits = []
            for r in reports:
                if r['W'] != 4 or r['binary'] != binary: continue
                for match in r['matches']:
                    if name in {a['name'] for a in match['aliases']}:
                        hits.append(f"{r['run']} `{match['program_hex']}`")
            lines.append(f"| {name} | {'; '.join(hits) if hits else 'Not found in the mapped completed runs'} |")
    lines += ['', '## Reproduce / extend', '',
              'Run `python fast/map_functions.py` after extracting witness archives into `results/shards/`. `--only RUN` maps one completed sweep. The script snapshots completed result files at startup; rerun as new sweeps finish.', '',
              'The catalog includes constants, affine arithmetic, bit masks, shifts, rotations, Gray transforms, population counts, comparisons, modular arithmetic, selected number-theoretic functions, and all 16 bitwise Boolean functions. Affine coefficients are exhaustive at W<=4 and explicitly sampled at W=8.', '',
              'Per-run JSON includes formulas, aliases, full truth tables, decoded instructions, witness IDs, source shards, and termination statistics. All input values are enumerated in increasing order; binary tables use x outer / y inner. Hash matches are independently verified by complete execution.', '']
    (out/'README.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only')
    args = parser.parse_args()
    out = ROOT/'results/function-map'
    out.mkdir(exist_ok=True)
    cache = {}
    sources = sorted((ROOT/'results').glob('exp03_*.json'))
    for path in sources:
        if args.only and path.stem != 'exp03_'+args.only: continue
        data = json.loads(path.read_text())
        if 'distinct_operators' not in data: continue
        mode = data['W'], data['binary']
        if mode not in cache: cache[mode] = catalog(*mode)
        report = recognize(path, cache[mode])
        target = out/(report['run']+'.json')
        target.write_text(json.dumps(report, indent=1)+'\n', encoding='utf-8')
        print(f"{report['run']}: {report['matched_distinct_tables']} recognized tables / {report['matched_labels']} names; all witnesses fully verified", flush=True)
    write_summary(out)


if __name__ == '__main__':
    main()
