"""
This file defines the classes used to represent a 'coordinate', which includes
axes, ticks, tick labels, and grid lines.
"""

import numpy as np
from astropy import units as u

from matplotlib.ticker import Formatter
from matplotlib.transforms import Affine2D, ScaledTranslation
from matplotlib.patches import PathPatch
from matplotlib import rcParams

from .formatter_locator import AngleFormatterLocator, ScalarFormatterLocator
from .ticks import Ticks
from .ticklabels import TickLabels
from .axislabels import AxisLabels
from .grid_paths import get_lon_lat_path, get_gridline_path
from . import settings

from . import six

__all__ = ['CoordinateHelper']


def wrap_angle_at(values, coord_wrap):
    return np.mod(values - coord_wrap, 360.) - (360. - coord_wrap)


class CoordinateHelper(object):

    def __init__(self, parent_axes=None, parent_map=None, transform=None, coord_index=None,
                 coord_type='scalar',coord_unit=None, coord_wrap=None, frame=None):

        # Keep a reference to the parent axes and the transform
        self.parent_axes = parent_axes
        self.parent_map = parent_map
        self.transform = transform
        self.coord_index = coord_index
        self.coord_unit = coord_unit
        self.frame = frame

        self.set_coord_type(coord_type, coord_wrap)

        # Initialize ticks
        self.dpi_transform = Affine2D()
        self.offset_transform = ScaledTranslation(0, 0, self.dpi_transform)
        self.ticks = Ticks(transform=parent_axes.transData + self.offset_transform)

        # Initialize tick labels
        self.ticklabels = TickLabels(self.frame,
                                     transform=None,  # display coordinates
                                     figure=parent_axes.get_figure())
        self.ticks.display_minor_ticks(False)
        self.minor_frequency = 5

        # Initialize axis labels
        self.axislabels = AxisLabels(self.frame,
                                     transform=None,  # display coordinates
                                     figure=parent_axes.get_figure())

        # Initialize container for the grid lines
        self.grid_lines = []

        # Initialize grid style. Take defaults from matplotlib.rcParams.
        # Based on matplotlib.axis.YTick._get_gridline.
        #
        # Matplotlib's gridlines use Line2D, but ours use PathPatch.
        # Patches take a slightly different format of linestyle argument.
        lines_to_patches_linestyle = {
            '-': 'solid',
            '--': 'dashed',
            '-.': 'dashdot',
            ':': 'dotted',
            'none': 'none',
            'None': 'none',
            ' ': 'none',
            '': 'none'
        }
        self.grid_lines_kwargs = {'visible':False,
                                  'facecolor':'none',
                                  'edgecolor': rcParams['grid.color'],
                                  'linestyle': lines_to_patches_linestyle[rcParams['grid.linestyle']],
                                  'linewidth': rcParams['grid.linewidth'],
                                  'alpha': rcParams['grid.alpha'],
                                  'transform':self.parent_axes.transData}

    def grid(self, draw_grid=True, grid_type='lines', **kwargs):
        """
        Plot grid lines for this coordinate.

        Standard matplotlib appearance options (color, alpha, etc.) can be
        passed as keyword arguments.

        Parameters
        ----------
        draw_grid : bool
            Whether to show the gridlines
        grid_type : { 'lines' | 'contours' }
            Whether to plot the contours by determining the grid lines in
            world coordinates and then plotting them in world coordinates
            (``'lines'``) or by determining the world coordinates at many
            positions in the image and then drawing contours
            (``'contours'``). The first is recommended for 2-d images, while
            for 3-d (or higher dimensional) cubes, the ``'contours'`` option
            is recommended.
        """

        if grid_type in ('lines', 'contours'):
            self._grid_type = grid_type
        else:
            raise ValueError("grid_type should be 'lines' or 'contours'")

        if 'color' in kwargs:
            kwargs['edgecolor'] = kwargs.pop('color')

        self.grid_lines_kwargs.update(kwargs)

        if self.grid_lines_kwargs['visible']:
            if not draw_grid:
                self.grid_lines_kwargs['visible'] = False
        else:
            self.grid_lines_kwargs['visible'] = True

    def set_coord_type(self, coord_type, coord_wrap=None):
        """
        Set the coordinate type for the axis.

        Parameters
        ----------
        coord_type : str
            One of 'longitude', 'latitude' or 'scalar'
        coord_wrap : float, optional
            The value to wrap at for angular coordinates
        """

        self.coord_type = coord_type

        if coord_type == 'longitude' and coord_wrap is None:
            self.coord_wrap = 360
        elif coord_type != 'longitude' and coord_wrap is not None:
            raise NotImplementedError('coord_wrap is not yet supported for non-longitude coordinates')
        else:
            self.coord_wrap = coord_wrap

        # Initialize tick formatter/locator
        if coord_type == 'scalar':
            self._formatter_locator = ScalarFormatterLocator(unit=self.coord_unit)
        elif coord_type in ['longitude', 'latitude']:
            self._formatter_locator = AngleFormatterLocator()
        else:
            raise ValueError("coord_type should be one of 'scalar', 'longitude', or 'latitude'")

    def set_major_formatter(self, formatter):
        """
        Set the formatter to use for the major tick labels.

        Parameters
        ----------
        formatter : str or Formatter
            The format or formatter to use.
        """
        if isinstance(formatter, Formatter):
            raise NotImplementedError()  # figure out how to swap out formatter
        elif isinstance(formatter, six.string_types):
            self._formatter_locator.format = formatter
        else:
            raise TypeError("formatter should be a string or a Formatter "
                            "instance")

    def set_format_unit(self, unit):
        """
        Set the unit for the major tick labels.

        Parameters
        ----------
        unit : class:`~astropy.units.Unit`
            The unit to which the tick labels should be converted to.
        """
        if (not issubclass(unit.__class__, u.UnitBase)):
            raise TypeError("unit should be an astropy UnitBase subclass")
        self._formatter_locator.format_unit = unit

    def set_ticks(self, values=None, spacing=None, number=None, size=None,
                  width=None, color=None, alpha=None):
        """
        Set the location and properties of the ticks.

        At most one of the options from ``values``, ``spacing``, or
        ``number`` can be specified.

        Parameters
        ----------
        values : iterable, optional
            The coordinate values at which to show the ticks.
        spacing : float, optional
            The spacing between ticks.
        number : float, optional
            The approximate number of ticks shown.
        size : float, optional
            The length of the ticks in points
        color : str or tuple
            A valid Matplotlib color for the ticks
        """

        if sum([values is None, spacing is None, number is None]) < 2:
            raise ValueError("At most one of values, spacing, or number should "
                             "be specified")

        if values is not None:
            self._formatter_locator.values = values
        elif spacing is not None:
            self._formatter_locator.spacing = spacing
        elif number is not None:
            self._formatter_locator.number = number

        if size is not None:
            self.ticks.set_ticksize(size)

        if width is not None:
            self.ticks.set_linewidth(width)

        if color is not None:
            self.ticks.set_color(color)

        if alpha is not None:
            self.ticks.set_alpha(alpha)

    def set_ticks_position(self, position):
        """
        Set where ticks should appear

        Parameters
        ----------
        position : str
            The axes on which the ticks for this coordinate should appear.
            Should be a string containing zero or more of ``'b'``, ``'t'``,
            ``'l'``, ``'r'``. For example, ``'lb'`` will lead the ticks to be
            shown on the left and bottom axis.
        """
        self.ticks.set_visible_axes(position)

    def set_ticklabel(self, **kwargs):
        """
        Set the visual properties for the tick labels.

        Parameters
        ----------
        kwargs
            Keyword arguments are passed to :class:`matplotlib.text.Text`. These
            can include keywords to set the ``color``, ``size``, ``weight``, and
            other text properties.
        """
        self.ticklabels.set(**kwargs)

    def set_ticklabel_position(self, position):
        """
        Set where tick labels should appear

        Parameters
        ----------
        position : str
            The axes on which the tick labels for this coordinate should
            appear. Should be a string containing zero or more of ``'b'``,
            ``'t'``, ``'l'``, ``'r'``. For example, ``'lb'`` will lead the
            tick labels to be shown on the left and bottom axis.
        """
        self.ticklabels.set_visible_axes(position)

    def set_axislabel(self, text, minpad=1, **kwargs):
        """
        Set the text and optionally visual properties for the axis label.

        Parameters
        ----------
        text : str
            The axis label text.
        minpad : float, optional
            The padding for the label in terms of axis label font size.
        kwargs
            Keywords are passed to :class:`matplotlib.text.Text`. These
            can include keywords to set the ``color``, ``size``, ``weight``, and
            other text properties.
        """
        self.axislabels.set_text(text)
        self.axislabels.set_minpad(minpad)
        self.axislabels.set(**kwargs)

    def set_axislabel_position(self, position):
        """
        Set where axis labels should appear

        Parameters
        ----------
        position : str
            The axes on which the axis label for this coordinate should
            appear. Should be a string containing zero or more of ``'b'``,
            ``'t'``, ``'l'``, ``'r'``. For example, ``'lb'`` will lead the
            axis label to be shown on the left and bottom axis.
        """
        self.axislabels.set_visible_axes(position)

    @property
    def locator(self):
        return self._formatter_locator.locator

    @property
    def formatter(self):
        return self._formatter_locator.formatter

    def _draw(self, renderer, bboxes):

        renderer.open_group('coordinate_axis')

        self._update_ticks(renderer)

        self.ticks.draw(renderer)
        self.ticklabels.draw(renderer, bboxes=bboxes)

        if self.grid_lines_kwargs['visible']:

            if self._grid_type == 'lines':
                self._update_grid_lines()
            else:
                self._update_grid_contour()

            if self._grid_type == 'lines':

                for path in self.grid_lines:
                    p = PathPatch(path, **self.grid_lines_kwargs)
                    p.set_clip_path(self.frame.patch)
                    p.draw(renderer)

            else:

                for line in self.grid.collections:
                    line.set(**self.grid_lines_kwargs)
                    line.draw(renderer)

        renderer.close_group('coordinate_axis')

    def _draw_axislabels(self, renderer, bboxes):

        renderer.open_group('axis labels')

        visible_ticks = self.ticklabels.get_visible_axes()

        ticklabels_bbox_list = self.ticklabels.get_ticklabels_bbox_list()

        self.axislabels.draw(renderer, bboxes=bboxes,
            ticklabels_bbox_list=ticklabels_bbox_list, visible_ticks=visible_ticks)

        renderer.close_group('axis labels')

    def _update_ticks(self, renderer):

        # TODO: this method should be optimized for speed

        # Here we determine the location and rotation of all the ticks. For
        # each axis, we can check the intersections for the specific
        # coordinate and once we have the tick positions, we can use the WCS
        # to determine the rotations.

        # Find the range of coordinates in all directions
        coord_range = self.parent_map.get_coord_range()

        # First find the ticks we want to show
        tick_world_coordinates, spacing = self._formatter_locator.locator(*coord_range[self.coord_index])
        if self.ticks.get_display_minor_ticks():
            minor_ticks_w_coordinates = self._formatter_locator.minor_locator(spacing, self.get_minor_frequency(), *coord_range[self.coord_index])

        # We want to allow non-standard rectangular frames, so we just rely on
        # the parent axes to tell us what the bounding frame is.
        frame = self.frame.sample(settings.FRAME_BOUNDARY_SAMPLES)

        self.ticks.clear()
        self.ticklabels.clear()
        lblinfo = []
        lbl_world = []
        lbl_minor_world = []
        # Look up parent axes' transform from data to figure coordinates.
        #
        # See:
        # http://matplotlib.org/users/transforms_tutorial.html#the-transformation-pipeline
        transData = self.parent_axes.transData
        invertedTransLimits = transData.inverted()

        for axis, spine in six.iteritems(frame):

            # Determine tick rotation in display coordinates and compare to
            # the normal angle in display coordinates.

            pixel0 = spine.data
            world0 = spine.world[:,self.coord_index]
            world0 = self.transform.transform(pixel0)[:,self.coord_index]
            axes0 = transData.transform(pixel0)

            # Advance 2 pixels in figure coordinates
            pixel1 = axes0.copy()
            pixel1[:,0] += 2.0
            pixel1 = invertedTransLimits.transform(pixel1)
            world1 = self.transform.transform(pixel1)[:,self.coord_index]

            # Advance 2 pixels in figure coordinates
            pixel2 = axes0.copy()
            pixel2[:,1] += 2.0 if self.frame.origin == 'lower' else -2.0
            pixel2 = invertedTransLimits.transform(pixel2)
            world2 = self.transform.transform(pixel2)[:,self.coord_index]

            dx = (world1 - world0)
            dy = (world2 - world0)

            # Rotate by 90 degrees
            dx, dy = -dy, dx

            if self.coord_type == 'longitude':
                # Here we wrap at 180 not self.coord_wrap since we want to
                # always ensure abs(dx) < 180 and abs(dy) < 180
                dx = wrap_angle_at(dx, 180.)
                dy = wrap_angle_at(dy, 180.)

            tick_angle = np.degrees(np.arctan2(dy, dx))

            normal_angle_full = np.hstack([spine.normal_angle, spine.normal_angle[-1]])
            reset = (((normal_angle_full - tick_angle) % 360 > 90.) &
                    ((tick_angle - normal_angle_full) % 360 > 90.))
            tick_angle[reset] -= 180.

            # We find for each interval the starting and ending coordinate,
            # ensuring that we take wrapping into account correctly for
            # longitudes.
            w1 = spine.world[:-1, self.coord_index]
            w2 = spine.world[1:, self.coord_index]
            if self.coord_type == 'longitude':
                w1 = wrap_angle_at(w1, self.coord_wrap)
                w2 = wrap_angle_at(w2, self.coord_wrap)
                w1[w2 - w1 > 180.] += 360
                w2[w1 - w2 > 180.] += 360

            # For longitudes, we need to check ticks as well as ticks + 360,
            # since the above can produce pairs such as 359 to 361 or 0.5 to
            # 1.5, both of which would match a tick at 0.75. Otherwise we just
            # check the ticks determined above.
            tick_world_coordinates_unit = tick_world_coordinates.unit
            tick_world_coordinates_values = tick_world_coordinates.value
            if self.coord_type == 'longitude':
                tick_world_coordinates_values = np.hstack([tick_world_coordinates_values,
                                                    tick_world_coordinates_values + 360])

            for t in tick_world_coordinates_values:

                # Find steps where a tick is present
                intersections = np.nonzero(((t - w1) * (t - w2)) < 0)[0]

                # Loop over ticks, and find exact pixel coordinates by linear
                # interpolation
                for imin in intersections:

                    imax = imin + 1

                    frac = (t - w1[imin]) / (w2[imin] - w1[imin])
                    x_data_i = spine.data[imin, 0] + frac * (spine.data[imax, 0] - spine.data[imin, 0])
                    y_data_i = spine.data[imin, 1] + frac * (spine.data[imax, 1] - spine.data[imin, 1])
                    x_pix_i = spine.pixel[imin, 0] + frac * (spine.pixel[imax, 0] - spine.pixel[imin, 0])
                    y_pix_i = spine.pixel[imin, 1] + frac * (spine.pixel[imax, 1] - spine.pixel[imin, 1])
                    delta_angle = tick_angle[imax] - tick_angle[imin]
                    if delta_angle > 180.:
                        delta_angle -= 360.
                    elif delta_angle < -180.:
                        delta_angle += 360.
                    angle_i = tick_angle[imin] + frac * delta_angle

                    if self.coord_type == 'longitude':
                        world = wrap_angle_at(t, self.coord_wrap)
                    else:
                        world = t

                    self.ticks.add(axis=axis,
                                   pixel=(x_data_i, y_data_i),
                                   world=world,
                                   angle=angle_i,
                                   axis_displacement=imin + frac)

                    # store information to pass to ticklabels.add
                    # it's faster to format many ticklabels at once outside
                    # of the loop
                    lblinfo.append(dict(axis=axis,
                                   pixel=(x_pix_i, y_pix_i),
                                   world=world,
                                   angle=spine.normal_angle[imin],
                                   axis_displacement=imin + frac))
                    lbl_world.append(world)

            if self.ticks.get_display_minor_ticks():

                minor_ticks_w_coordinates_values = minor_ticks_w_coordinates.value
                if self.coord_type == 'longitude':
                    minor_ticks_w_coordinates_values = np.hstack([minor_ticks_w_coordinates_values,
                                                              minor_ticks_w_coordinates_values + 360])

                for t in minor_ticks_w_coordinates_values:

                    # Find steps where a tick is present
                    intersections = np.nonzero(((t - w1) * (t - w2)) < 0)[0]

                    # Loop over ticks, and find exact pixel coordinates by linear
                    # interpolation
                    for imin in intersections:

                        imax = imin + 1

                        frac = (t - w1[imin]) / (w2[imin] - w1[imin])
                        x_data_i = spine.data[imin, 0] + frac * (spine.data[imax, 0] - spine.data[imin, 0])
                        y_data_i = spine.data[imin, 1] + frac * (spine.data[imax, 1] - spine.data[imin, 1])
                        x_pix_i = spine.pixel[imin, 0] + frac * (spine.pixel[imax, 0] - spine.pixel[imin, 0])
                        y_pix_i = spine.pixel[imin, 1] + frac * (spine.pixel[imax, 1] - spine.pixel[imin, 1])
                        delta_angle = tick_angle[imax] - tick_angle[imin]
                        if delta_angle > 180.:
                            delta_angle -= 360.
                        elif delta_angle < -180.:
                            delta_angle += 360.
                        angle_i = tick_angle[imin] + frac * delta_angle

                        if self.coord_type == 'longitude':
                            world = wrap_angle_at(t, self.coord_wrap)
                        else:
                            world = t

                        self.ticks.add_minor(minor_axis=axis,
                                             minor_pixel=(x_data_i, y_data_i),
                                             minor_world=world,
                                             minor_angle=angle_i,
                                             minor_axis_displacement=imin + frac)
                        lbl_minor_world.append(world)


        # format tick labels, add to scene
        text = self._formatter_locator.formatter(lbl_world * tick_world_coordinates_unit, spacing=spacing)
        for kwargs, txt in zip(lblinfo, text):
            self.ticklabels.add(text=txt, **kwargs)

    def display_minor_ticks(self, display_minor_ticks):
        """
        Display minor ticks for this coordinate.

        Parameters
        ----------
        display_minor_ticks : bool
            Whether or not to display minor ticks.
        """
        self.ticks.display_minor_ticks(display_minor_ticks)

    def get_minor_frequency(self):
        return self.minor_frequency

    def set_minor_frequency(self, frequency):
        """
        Set the frequency of minor ticks per major ticks.

        Parameters
        ----------
        frequency : int
            The number of minor ticks per major ticks.
        """
        self.minor_frequency = frequency

    def _update_grid_lines(self):

        # For 3-d WCS with a correlated third axis, the *proper* way of
        # drawing a grid should be to find the world coordinates of all pixels
        # and drawing contours. What we are doing here assumes that we can
        # define the grid lines with just two of the coordinates (and
        # therefore assumes that the other coordinates are fixed and set to
        # the value in the slice). Here we basically assume that if the WCS
        # had a third axis, it has been abstracted away in the transformation.

        coord_range = self.parent_map.get_coord_range()

        tick_world_coordinates, spacing = self._formatter_locator.locator(*coord_range[self.coord_index])
        tick_world_coordinates_values = tick_world_coordinates.value

        self.grid_lines = []
        for w in tick_world_coordinates_values:
            if self.coord_index == 0:
                x_world = np.repeat(w, 1000)
                y_world = np.linspace(coord_range[1][0], coord_range[1][1], 1000)
            else:
                x_world = np.linspace(coord_range[0][0], coord_range[0][1], 1000)
                y_world = np.repeat(w, 1000)
            xy_world = np.vstack([x_world, y_world]).transpose()
            self.grid_lines.append(self._get_gridline(xy_world))

    def _get_gridline(self, xy_world):
        if self.coord_type == 'scalar':
            return get_gridline_path(self.parent_axes, self.transform, xy_world)
        else:
            return get_lon_lat_path(self.parent_axes, self.transform, xy_world)

    def _update_grid_contour(self):

        xmin, xmax = self.parent_axes.get_xlim()
        ymin, ymax = self.parent_axes.get_ylim()

        X, Y, field = self.transform.get_coord_slices(xmin, xmax, ymin, ymax, 200, 200)

        coord_range = self.parent_map.get_coord_range()

        tick_world_coordinates, spacing = self._formatter_locator.locator(*coord_range[self.coord_index])

        field = field[self.coord_index]

        # tick_world_coordinates is a Quantities array and we only needs its values
        tick_world_coordinates_values = tick_world_coordinates.value

        if self.coord_type == 'longitude':
            # Find biggest gap in tick_world_coordinates and wrap in  middle
            # For now just assume spacing is equal, so any mid-point will do
            mid = 0.5 * (tick_world_coordinates_values[0] + tick_world_coordinates_values[1])
            field = wrap_angle_at(field, mid)
            tick_world_coordinates_values = wrap_angle_at(tick_world_coordinates_values, mid)

            # Replace wraps by NaN
            reset = (np.abs(np.diff(field[:,:-1], axis=0)) > 180) | (np.abs(np.diff(field[:-1,:], axis=1)) > 180)
            field[:-1,:-1][reset] = np.nan
            field[1:,:-1][reset] = np.nan
            field[:-1,1:][reset] = np.nan
            field[1:,1:][reset] = np.nan

        self.grid = self.parent_axes.contour(X, Y, field.transpose(), levels=tick_world_coordinates_values)
