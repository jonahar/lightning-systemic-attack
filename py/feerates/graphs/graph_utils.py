from dataclasses import dataclass
from datetime import datetime
from typing import List

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from bitcoin_cli import blockchain_height, get_block_time
from datatypes import BlockHeight, Feerate, Timestamp


@dataclass
class PlotData:
    """PlotData represents data for a single graph - feerate as a function of timestamp"""
    timestamps: List[Timestamp]
    feerates: List[Feerate]
    label: str


def plot_figure(title: str, plot_data_list: List[PlotData], **fig_kw) -> Figure:
    """
    add the given plot data to a new figure. all graphs on the same figure
    """
    fig = plt.figure(**fig_kw)
    for plot_data in plot_data_list:
        plt.plot(plot_data.timestamps, plot_data.feerates, label=plot_data.label)
    
    min_timestamp = min(min(plot_data.timestamps) for plot_data in plot_data_list)
    max_timestamp = max(max(plot_data.timestamps) for plot_data in plot_data_list)
    min_feerate = min(min(plot_data.feerates) for plot_data in plot_data_list)
    max_feerate = max(max(plot_data.feerates) for plot_data in plot_data_list)
    # graph config
    plt.legend(loc="best")
    plt.title(title)
    
    xticks = np.linspace(start=min_timestamp, stop=max_timestamp, num=5)
    yticks = np.linspace(start=min_feerate, stop=max_feerate, num=5)
    
    timestamp_to_date_str = lambda t: datetime.utcfromtimestamp(t).strftime('%Y-%m-%d')
    plt.xticks(
        ticks=xticks,
        labels=[timestamp_to_date_str(t) for t in xticks]
    )
    
    plt.yticks(ticks=yticks)
    
    return fig


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
