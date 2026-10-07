"""Test code to translate into Universe-1 programs. Every function is ordinary Python over W-bit
unsigned ints (W = 4 by default). Unary functions take x; binary take (x, y). Sources:
Dimension42 explorer/ai/pbe.py TESTS (scaled from 8 to W bits) and classic bit-trick kernels."""
W = 4
M = (1 << W) - 1

UNARY = {
    # Dimension42 TESTS, unary members (b -> x)
    "a_plus_5":      lambda x: (x + 5) & M,
    "not_b":         lambda x: M - x,
    "a_minus_1":     lambda x: (x - 1) & M,
    "rotl3":         lambda x: ((x << 3) | (x >> (W - 3))) & M,
    "times3":        lambda x: (3 * x) & M,
    # classic kernels
    "gray":          lambda x: x ^ (x >> 1),
    "ungray":        lambda x: (lambda g: g ^ (g >> 1) ^ (g >> 2) ^ (g >> 3))(x) & M,
    "popcount":      lambda x: bin(x).count("1"),
    "parity":        lambda x: bin(x).count("1") & 1,
    "abs_signed":    lambda x: (x if x < (1 << (W - 1)) else (-x) & M),
    "sign_bit":      lambda x: x >> (W - 1),
    "nibble_swap":   lambda x: ((x << (W // 2)) | (x >> (W - W // 2))) & M,
    "sat_inc":       lambda x: min(x + 1, M),
    "sat_dec":       lambda x: max(x - 1, 0),
    "is_pow2":       lambda x: int(x != 0 and (x & (x - 1)) == 0),
    "mod3":          lambda x: x % 3,
    "div3":          lambda x: x // 3,
    "square":        lambda x: (x * x) & M,
    "cube":          lambda x: (x * x * x) & M,
    "bitrev":        lambda x: int(f"{x:0{W}b}"[::-1], 2),
    "clz":           lambda x: W - x.bit_length(),
    "ctz":           lambda x: (x & -x).bit_length() - 1 if x else W,
    "lowbit":        lambda x: x & -x & M,
    "clear_lowbit":  lambda x: x & (x - 1) & M,
    "fill_right":    lambda x: (x | (x >> 1) | (x >> 2) | (x >> 3)) & M,
    "bcd_inc":       lambda x: (x + 1) % 10 if x < 10 else x,
    "sign_extend2":  lambda x: ((x & 3) | (M & ~3 if x & 2 else 0)) & M,
    "lerp_half":     lambda x: (x + M) >> 1,
    "triangular":    lambda x: (x * (x + 1) // 2) & M,
    "collatz_step":  lambda x: (x // 2 if x % 2 == 0 else (3 * x + 1) & M),
}

BINARY = {
    # Dimension42 TESTS, binary members (a -> x, b -> y)
    "a_plus_b":      lambda x, y: (x + y) & M,
    "a_xor_b":       lambda x, y: x ^ y,
    "2a_plus_b":     lambda x, y: (2 * x + y) & M,
    "a_plus_b_plus1":lambda x, y: (x + y + 1) & M,
    "a_xor_b_xor7":  lambda x, y: x ^ y ^ 7,
    # classic kernels
    "a_minus_b":     lambda x, y: (x - y) & M,
    "sat_add":       lambda x, y: min(x + y, M),
    "sat_sub":       lambda x, y: max(x - y, 0),
    "carry_out":     lambda x, y: int(x + y > M),
    "half_adder_sum":lambda x, y: (x ^ y) & 1,
    "mul":           lambda x, y: (x * y) & M,
    "mul_hi":        lambda x, y: (x * y) >> W,
    "min":           lambda x, y: min(x, y),
    "max":           lambda x, y: max(x, y),
    "abs_diff":      lambda x, y: abs(x - y),
    "avg_floor":     lambda x, y: (x + y) >> 1,
    "eq":            lambda x, y: int(x == y),
    "lt":            lambda x, y: int(x < y),
    "and_not":       lambda x, y: x & ~y & M,
    "mux_lsb":       lambda x, y: x if y & 1 else y,
    "shl_var":       lambda x, y: (x << y) & M if y < W else 0,
    "shr_var":       lambda x, y: x >> y if y < W else 0,
    "hamming":       lambda x, y: bin(x ^ y).count("1"),
    "gcd":           lambda x, y: __import__("math").gcd(x, y),
    "mod":           lambda x, y: x % y if y else x,
}

def tables(w=W):
    n = 1 << w
    un = {k: [f(x) & ((1 << w) - 1) for x in range(n)] for k, f in UNARY.items()}
    bi = {k: [f(x, y) & ((1 << w) - 1) for x in range(n) for y in range(n)] for k, f in BINARY.items()}
    return un, bi
