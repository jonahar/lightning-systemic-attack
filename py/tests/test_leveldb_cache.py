import os
import shutil
import unittest

from utils import get_leveldb_cache_fullpath, leveldb_cache


class MyTestCase(unittest.TestCase):
    
    @staticmethod
    def __init_cached_function(key_to_str=None):
        db_path = get_leveldb_cache_fullpath("test_method_for_leveldb_cache_test")
        if os.path.exists(db_path):
            shutil.rmtree(db_path)
        
        @leveldb_cache(value_to_str=str, str_to_value=float, key_to_str=key_to_str)
        def test_method_for_leveldb_cache_test(x, y, z) -> float:
            test_method_for_leveldb_cache_test.calls_counter += 1
            return (x + y) * z
        
        test_method_for_leveldb_cache_test.calls_counter = 0
        return test_method_for_leveldb_cache_test
    
    def test_not_entering_original_funcion_twice(self):
        cached_function = self.__init_cached_function()
        
        args_kwargs_pairs = [
            ((1, 2, 3), {}),
            ((1, 2), {"z": 3}),
            ((1,), {"y": 2, "z": 3}),
            ((), {"x": 1, "y": 2, "z": 3}),
        ]
        for args, kwargs in args_kwargs_pairs:
            self.assertEqual(cached_function(*args, **kwargs), cached_function(*args, **kwargs))
        
        self.assertEqual(cached_function.calls_counter, len(args_kwargs_pairs))
    
    def test_correct_result_with_custom_key_to_str(self):
        def custom_key_to_str(*args, **kwargs):
            return "CONSTANT KEY"

        cached_function = self.__init_cached_function(key_to_str=custom_key_to_str)
        self.assertEqual(cached_function.calls_counter, 0)

        # different calls, but the key_to_str function is constant, so they should
        # be treated as the same call
        cached_function(1, 1, 1)
        cached_function(2, 2, 2)
        cached_function(3, 3, 3)

        self.assertEqual(cached_function.calls_counter, 1)


if __name__ == '__main__':
    unittest.main()
