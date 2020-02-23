from dataclasses import dataclass
from datetime import datetime
from typing import List

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from datatypes import FEERATE, TIMESTAMP


@dataclass
class PlotData:
    """PlotData represents data for a single graph - feerate as a function of timestamp"""
    timestamps: List[TIMESTAMP]
    feerates: List[FEERATE]
    label: str


def plot_figure(title: str, plot_data_list: List[PlotData]) -> Figure:
    """
    add the given plot data to a new figure. all graphs on the same figure
    """
    fig = plt.figure()
    for plot_data in plot_data_list:
        plt.plot(plot_data.timestamps, plot_data.feerates, label=plot_data.label)
    
    min_timestamp = min(min(plot_data.timestamps) for plot_data in plot_data_list)
    max_timestamp = max(max(plot_data.timestamps) for plot_data in plot_data_list)
    min_feerate = min(min(plot_data.feerates) for plot_data in plot_data_list)
    max_feerate = max(max(plot_data.feerates) for plot_data in plot_data_list)
    # graph config
    plt.legend(loc="best")
    plt.title(title)
    
    xticks = np.linspace(start=min_timestamp, stop=max_timestamp, num=10)
    yticks = np.linspace(start=min_feerate, stop=max_feerate, num=10)
    
    timestamp_to_date_str = lambda t: datetime.utcfromtimestamp(t).strftime('%Y-%m-%d %H:%M')
    plt.xticks(
        ticks=xticks,
        labels=[timestamp_to_date_str(t) for t in xticks]
    )
    plt.xlabel("timestamp")
    
    plt.yticks(ticks=yticks)
    plt.ylabel("feerate")
    
    return fig
