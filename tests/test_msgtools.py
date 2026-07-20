import unittest

from util.msgtools import parse_float, parse_int, parse_string


class MessageToolsTests(unittest.TestCase):
    def test_values_can_be_parsed_one_after_another(self) -> None:
        text = '42  3.14 hello'

        integer, index = parse_int(text)
        self.assertEqual(index, 2)

        number, index = parse_float(text, index)
        self.assertEqual(index, 8)

        string, index = parse_string(text, index)

        self.assertEqual(integer, 42)
        self.assertEqual(number, 3.14)
        self.assertEqual(string, 'hello')
        self.assertEqual(index, len(text))

    def test_custom_separator_is_supported(self) -> None:
        text = '10,20.5,value'

        integer, index = parse_int(text, separator=',')
        number, index = parse_float(text, index, separator=',')
        string, index = parse_string(text, index, separator=',')

        self.assertEqual((integer, number, string), (10, 20.5, 'value'))
        self.assertEqual(index, len(text))

    def test_invalid_number_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            parse_int('not-a-number')

    def test_empty_separator_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_string('value', separator='')


if __name__ == '__main__':
    unittest.main()
