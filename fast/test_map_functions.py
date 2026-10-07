"""Independent edge cases for the mathematical catalog and key encoding."""
import unittest

from map_functions import catalog, key


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.unary = {name: table for name, _, table in catalog(4, False)}
        cls.binary = {name: table for name, _, table in catalog(4, True)}

    def test_modular_and_signed_edges(self):
        self.assertEqual(self.unary['increment'][15], 0)
        self.assertEqual(self.unary['negation'][1], 15)
        self.assertEqual(self.unary['signed_abs'][15], 1)
        self.assertEqual(self.unary['signed_abs'][8], 8)
        self.assertEqual(self.unary['square'][15], 1)
        self.assertEqual(self.binary['add'][15*16+1], 0)
        self.assertEqual(self.binary['subtract'][0*16+1], 15)
        self.assertEqual(self.binary['unsigned_divide_zero_returns_zero'][15*16], 0)

    def test_comparison_encoding_and_order(self):
        self.assertEqual(self.binary['less_than_unsigned_bool'][1*16+2], 1)
        self.assertEqual(self.binary['less_than_unsigned_mask'][1*16+2], 15)
        self.assertEqual(self.binary['less_than_signed_bool'][15*16], 1)
        self.assertEqual(self.binary['less_than_unsigned_bool'][15*16], 0)
        self.assertEqual(self.binary['identity_of_x'][3*16+7], 3)
        self.assertEqual(self.binary['identity_of_y'][3*16+7], 7)

    def test_bitwise_and_gray(self):
        self.assertEqual(self.unary['bit_reverse'][3], 12)
        self.assertEqual(self.unary['rotate_left_1'][8], 1)
        for x in range(16):
            self.assertEqual(self.unary['gray_decode'][self.unary['gray_encode'][x]], x)
        for name, code in [('and','1000'), ('or','1110'), ('xor','0110'), ('nand','0111')]:
            self.assertEqual(self.binary[name], self.binary['bitwise_boolean_'+code])

    def test_exact_packing(self):
        self.assertEqual(key(tuple(range(16)), 4), (0xfedcba9876543210, 0))


if __name__ == '__main__':
    unittest.main()
