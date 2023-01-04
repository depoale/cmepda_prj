import unittest
import numpy as np
from matplotlib import pyplot as plt
from context import prepro_ale as ale

class PreproTests(unittest.TestCase):
    def test_sets(self):
        x_train, y_train, x_test, y_test= ale.get_data()
        if len(x_train)!= len(y_train) or len(x_test)!= len(y_test):
            raise ValueError('dimension mismatch') 
    
if __name__ == '__main__':
    unittest.main()