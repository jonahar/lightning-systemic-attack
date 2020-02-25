import os
import unittest

from utils import get_sqlite_cache_fullpath, sqlite_cache


class MyTestCase(unittest.TestCase):
    
    def __init_cached_function(self, key_to_str=None):
        db_path = get_sqlite_cache_fullpath("foo")
        if os.path.isfile(db_path):
            os.remove(db_path)
        
        @sqlite_cache(value_to_str=str, str_to_value=float, key_to_str=key_to_str)
        def foo(x, y, z) -> float:
            foo.calls_counter += 1
            return (x + y) * z
        
        foo.calls_counter = 0
        return foo
    
    def test_not_entering_original_funcion_twice(self):
        foo = self.__init_cached_function()
        
        args_kwargs_pairs = [
            ((1, 2, 3), {}),
            ((1, 2), {"z": 3}),
            ((1,), {"y": 2, "z": 3}),
            ((), {"x": 1, "y": 2, "z": 3}),
        ]
        for args, kwargs in args_kwargs_pairs:
            self.assertEqual(foo(*args, **kwargs), foo(*args, **kwargs))
        
        self.assertEqual(foo.calls_counter, len(args_kwargs_pairs))
    
    def test_correct_result_with_custom_key_to_str(self):
        def custom_key_to_str(*args, **kwargs):
            return "CONSTANT KEY"
        
        foo = self.__init_cached_function(key_to_str=custom_key_to_str)
        self.assertEqual(foo.calls_counter, 0)
        
        # different calls, but the key_to_str function is constant, so they should
        # be treated as the same call
        foo(1, 1, 1)
        foo(2, 2, 2)
        foo(3, 3, 3)
        
        self.assertEqual(foo.calls_counter, 1)


if __name__ == '__main__':
    unittest.main()
