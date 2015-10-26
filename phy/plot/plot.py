# -*- coding: utf-8 -*-

"""Plotting interface."""


#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

from itertools import groupby
from collections import defaultdict

import numpy as np

from .base import BaseCanvas
from .interact import Grid, Boxed, Stacked
from .panzoom import PanZoom
from .transform import NDC
from .visuals import _get_array, ScatterVisual, PlotVisual, HistogramVisual


#------------------------------------------------------------------------------
# Utils
#------------------------------------------------------------------------------

class Accumulator(object):
    """Accumulate arrays for concatenation."""
    def __init__(self):
        self._data = defaultdict(list)

    def __setitem__(self, name, val):
        self._data[name].append(val)

    def __getitem__(self, name):
        return np.vstack(self._data[name]).astype(np.float32)


#------------------------------------------------------------------------------
# Base plotting interface
#------------------------------------------------------------------------------

class SubView(object):
    def __init__(self, idx):
        self.spec = {'idx': idx}

    @property
    def visual_class(self):
        return self.spec.get('visual_class', None)

    def _set(self, visual_class, spec):
        self.spec['visual_class'] = visual_class
        self.spec.update(spec)

    def __getattr__(self, name):
        return self.spec[name]

    def scatter(self, x, y, color=None, size=None, marker=None):
        # Validate x and y.
        assert x.ndim == y.ndim == 1
        assert x.shape == y.shape
        n = x.shape[0]
        # Set the color and size.
        color = _get_array(color, (n, 4), ScatterVisual._default_color)
        size = _get_array(size, (n, 1), ScatterVisual._default_marker_size)
        # Default marker.
        marker = marker or ScatterVisual._default_marker
        # Set the spec.
        spec = dict(x=x, y=y, color=color, size=size, marker=marker)
        return self._set(ScatterVisual, spec)

    def plot(self, x, y, color=None):
        x = np.atleast_2d(x)
        y = np.atleast_2d(y)
        # Validate x and y.
        assert x.ndim == y.ndim == 2
        assert x.shape == y.shape
        n_plots, n_samples = x.shape
        # Get the colors.
        color = _get_array(color, (n_plots, 4), PlotVisual._default_color)
        # Set the spec.
        spec = dict(x=x, y=y, color=color)
        return self._set(PlotVisual, spec)

    def hist(self, data, color=None):
        # Validate data.
        if data.ndim == 1:
            data = data[np.newaxis, :]
        assert data.ndim == 2
        n_hists, n_samples = data.shape
        # Get the colors.
        color = _get_array(color, (n_hists, 4), HistogramVisual._default_color)
        spec = dict(data=data, color=color)
        return self._set(HistogramVisual, spec)

    def __repr__(self):
        return str(self.spec)  # pragma: no cover


class BaseView(BaseCanvas):
    def __init__(self, interacts):
        super(BaseView, self).__init__()
        # Attach the passed interacts to the current canvas.
        for interact in interacts:
            interact.attach(self)
        self.subviews = {}

    # To override
    # -------------------------------------------------------------------------

    def iter_index(self):
        raise NotImplementedError()

    # Internal methods
    # -------------------------------------------------------------------------

    def iter_subviews(self):
        for idx in self.iter_index():
            sv = self.subviews.get(idx, None)
            if sv:
                yield sv

    def __getitem__(self, idx):
        sv = SubView(idx)
        self.subviews[idx] = sv
        return sv

    def _build_scatter(self, subviews, marker):
        """Build all scatter subviews with the same marker type."""

        ac = Accumulator()
        for sv in subviews:
            assert sv.marker == marker
            n = len(sv.x)
            ac['pos'] = np.c_[sv.x, sv.y]
            ac['color'] = sv.color
            ac['size'] = sv.size
            ac['box_index'] = np.tile(sv.idx, (n, 1))

        v = ScatterVisual(marker=marker)
        v.attach(self)
        v.set_data(pos=ac['pos'], color=ac['color'], size=ac['size'])
        v.program['a_box_index'] = ac['box_index']

    def _build_plot(self, subviews):
        """Build all plot subviews."""

        ac = Accumulator()
        for sv in subviews:
            n = sv.x.size
            ac['x'] = sv.x
            ac['y'] = sv.y
            ac['plot_colors'] = sv.color
            ac['box_index'] = np.tile(sv.idx, (n, 1))

        v = PlotVisual()
        v.attach(self)
        v.set_data(x=ac['x'], y=ac['y'], plot_colors=ac['plot_colors'])
        v.program['a_box_index'] = ac['box_index']

    def _build_histogram(self, subviews):
        """Build all histogram subviews."""

        ac = Accumulator()
        for sv in subviews:
            n = sv.data.size
            ac['data'] = sv.data
            ac['hist_colors'] = sv.color
            # NOTE: the `6 * ` comes from the histogram tesselation.
            ac['box_index'] = np.tile(sv.idx, (6 * n, 1))

        v = HistogramVisual()
        v.attach(self)
        v.set_data(hist=ac['data'], hist_colors=ac['hist_colors'])
        v.program['a_box_index'] = ac['box_index']

    def build(self):
        """Build all visuals."""
        for visual_class, subviews in groupby(self.iter_subviews(),
                                              lambda sv: sv.visual_class):
            if visual_class == ScatterVisual:
                for marker, subviews_scatter in groupby(subviews,
                                                        lambda sv: sv.marker):
                    self._build_scatter(subviews_scatter, marker)
            elif visual_class == PlotVisual:
                self._build_plot(subviews)
            elif visual_class == HistogramVisual:
                self._build_histogram(subviews)


#------------------------------------------------------------------------------
# Plotting interface
#------------------------------------------------------------------------------

class GridView(BaseView):
    def __init__(self, n_rows, n_cols):
        self.n_rows, self.n_cols = n_rows, n_cols
        pz = PanZoom(aspect=None, constrain_bounds=NDC)
        interacts = [Grid(n_rows, n_cols), pz]
        super(GridView, self).__init__(interacts)

    def iter_index(self):
        for i in range(self.n_rows):
            for j in range(self.n_cols):
                yield (i, j)


class BoxedView(BaseView):
    def __init__(self, box_bounds):
        self.n_plots = len(box_bounds)
        self._boxed = Boxed(box_bounds)
        self._pz = PanZoom(aspect=None, constrain_bounds=NDC)
        interacts = [self._boxed, self._pz]
        super(BoxedView, self).__init__(interacts)

    def iter_index(self):
        for i in range(self.n_plots):
            yield i


class StackedView(BaseView):
    def __init__(self, n_plots):
        self.n_plots = n_plots
        pz = PanZoom(aspect=None, constrain_bounds=NDC)
        interacts = [Stacked(n_plots, margin=.1), pz]
        super(StackedView, self).__init__(interacts)

    def iter_index(self):
        for i in range(self.n_plots):
            yield i
