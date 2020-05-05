from bitcoin_cli import blockchain_height, get_block_time
from datatypes import BlockHeight, Timestamp


def get_first_block_after_time_t(t: Timestamp) -> BlockHeight:
    """
    return the height of the first block with timestamp greater or equal to
    the given timestamp
    """
    low: int = 0
    high = blockchain_height()
    
    # simple binary search
    while low < high:
        m = (low + high) // 2
        m_time = get_block_time(m)
        if m_time < t:
            low = m + 1
        else:
            high = m
    
    return low
