#!/usr/bin/env python
"""This library is free software; you can redistribute it and/or
modify it under the terms of the IBM Common Public License as
published by the IBM Corporation; either version 1.0 of the
License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
IBM Common Public License for more details.

You should have received a copy of the IBM Common Public
License along with this library
"""
from bisect import bisect_left
from inspect import ismethod


def merge_inherited_docstrings(cls):
    for member, name in [(cls.__dict__[name], name) for name in list(cls.__dict__) if cls.__dict__[name]]:
        docstrings = []
        for base in [base for base in cls.__bases__ if base]:
            if base == object:
                break
            if hasattr(base, name) and (callable(member) or ismethod(member)):
                docstrings.append(getattr(base, name, '').__doc__)
        try:
            docstrings.append(getattr(member, '__doc__') or '')
            member.__doc__ = '\n'.join([s for s in docstrings if s])
        except AttributeError:
            pass
    return cls


class OutOfSpaceError(Exception):
    pass


class Point(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __cmp__(self, other):
        """Compares the starting position of height slices"""
        return self.x - other.x


class RectanglePacker(object):
    """Base class for rectangle packing algorithms

    By uniting all rectangle packers under this common base class, you can
    easily switch between different algorithms to find the most efficient or
    performant one for a given job.

    An almost exhaustive list of packing algorithms can be found here:
    http://www.csc.liv.ac.uk/~epa/surveyhtml.html"""

    def __init__(self, width, height):
        """Initializes a new rectangle packer

        width: Maximum width of the packing area
        height: Maximum height of the packing area"""
        self.packing_area_width = width
        self.packing_area_height = height

    def pack(self, rect_width, rect_height):
        """Allocates space for a rectangle in the packing area

        rect_width: Width of the rectangle to allocate
        rect_height: Height of the rectangle to allocate

        Returns the location at which the rectangle has been placed"""
        point = self.try_pack(rect_width, rect_height)

        if not point:
            raise OutOfSpaceError("Rectangle does not fit in packing area")

        return point

    def try_pack(self, rect_width, rect_height):
        """Tries to allocate space for a rectangle in the packing area

        rect_width: Width of the rectangle to allocate
        rect_height: Height of the rectangle to allocate

        Returns a Point instance if space for the rectangle could be allocated
        be found, otherwise returns None"""
        raise NotImplementedError


@merge_inherited_docstrings
class CygonRectanglePacker(RectanglePacker):
    """
    Packer using a custom algorithm by Markus 'Cygon' Ewald

    Algorithm conceived by Markus Ewald (cygon at nuclex dot org), though
    I'm quite sure I'm not the first one to come up with it :)

    The algorithm always places rectangles as low as possible in the packing
    area. So, for any new rectangle that is to be added, the packer has to
    determine the X coordinate at which the rectangle can have the lowest
    overall height without intersecting any other rectangles.

    To quickly discover these locations, the packer uses a sophisticated
    data structure that stores the upper silhouette of the packing area. When
    a new rectangle needs to be added, only the silouette edges need to be
    analyzed to find the position where the rectangle would achieve the lowest"""

    def __init__(self, width, height):
        super(CygonRectanglePacker, self).__init__(width, height)

        # Stores the height silhouette of the rectangles
        self.height_slices = []

        # At the beginning, the packing area is a single slice of height 0
        self.height_slices.append(Point(0, 0))

    def try_pack(self, rect_width, rect_height):
        placement = None

        # If the rectangle is larger than the packing area in any dimension,
        # it will never fit!
        if rect_width > self.packing_area_width or rect_height > \
                self.packing_area_height:
            return None

        # Determine the placement for the new rectangle
        placement = self.try_find_best_placement(rect_width, rect_height)

        # If a place for the rectangle could be found, update the height slice
        # table to mark the region of the rectangle as being taken.
        if placement:
            self.integrate_rectangle(placement.x, rect_width, placement.y
                                     + rect_height)

        return placement

    def try_find_best_placement(self, rectangle_width, rectangle_height):
        """Finds the best position for a rectangle of the given dimensions

        rectangle_width: Width of the rectangle to find a position for
        rectangle_height: Height of the rectangle to find a position for

        Returns a Point instance if a valid placement for the rectangle could
        be found, otherwise returns None"""
        # Slice index, vertical position and score of the best placement we
        # could find
        best_slice_index = -1  # Slice index where the best placement was found
        best_slice_y = 0  # Y position of the best placement found
        # lower == better!
        best_score = self.packing_area_width * self.packing_area_height

        # This is the counter for the currently checked position. The search
        # works by skipping from slice to slice, determining the suitability
        # of the location for the placement of the rectangle.
        left_slice_index = 0

        # Determine the slice in which the right end of the rectangle is located
        right_slice_index = bisect_left(self.height_slices,
                                        Point(rectangle_width, 0))
        if right_slice_index < 0:
            right_slice_index = ~right_slice_index

        while right_slice_index <= len(self.height_slices):
            # Determine the highest slice within the slices covered by the
            # rectangle at its current placement. We cannot put the rectangle
            # any lower than this without overlapping the other rectangles.
            highest = self.height_slices[left_slice_index].y
            for index in range(left_slice_index + 1, right_slice_index):
                if self.height_slices[index].y > highest:
                    highest = self.height_slices[index].y

            # Only process this position if it doesn't leave the packing area
            if highest + rectangle_height < self.packing_area_height:
                score = highest

                if score < best_score:
                    best_slice_index = left_slice_index
                    best_slice_y = highest
                    best_score = score

            # Advance the starting slice to the next slice start
            left_slice_index += 1
            if left_slice_index >= len(self.height_slices):
                break

            # Advance the ending slice until we're on the proper slice again,
            # given the new starting position of the rectangle.
            right_rectangle_end = self.height_slices[left_slice_index].x + \
                rectangle_width
            while right_slice_index <= len(self.height_slices):
                if right_slice_index == len(self.height_slices):
                    right_slice_start = self.packing_area_width
                else:
                    right_slice_start = self.height_slices[right_slice_index].x

                # Is this the slice we're looking for?
                if right_slice_start > right_rectangle_end:
                    break

                right_slice_index += 1

            # If we crossed the end of the slice array, the rectangle's right
            # end has left the packing area, and thus, our search ends.
            if right_slice_index > len(self.height_slices):
                break

        # Return the best placement we found for this rectangle. If the
        # rectangle didn't fit anywhere, the slice index will still have its
        # initialization value of -1 and we can report that no placement
        # could be found.
        if best_slice_index == -1:
            return None
        else:
            return Point(self.height_slices[best_slice_index].x, best_slice_y)

    def integrate_rectangle(self, left, width, bottom):
        """Integrates a new rectangle into the height slice table

        left: Position of the rectangle's left side
        width: Width of the rectangle
        bottom: Position of the rectangle's lower side"""
        # Find the first slice that is touched by the rectangle
        start_slice = bisect_left(self.height_slices, Point(left, 0))

        # Did we score a direct hit on an existing slice start?
        if start_slice >= 0:
            # We scored a direct hit, so we can replace the slice we have hit
            first_slice_original_height = self.height_slices[start_slice].y
            self.height_slices[start_slice] = Point(left, bottom)
        else:  # No direct hit, slice starts inside another slice
            # Add a new slice after the slice in which we start
            start_slice = ~start_slice
            first_slice_original_height = self.height_slices[start_slice - 1].y
            self.height_slices.insert(start_slice, Point(left, bottom))

        right = left + width
        start_slice += 1

        # Special case, the rectangle started on the last slice, so we cannot
        # use the start slice + 1 for the binary search and the possibly
        # already modified start slice height now only remains in our temporary
        # firstSliceOriginalHeight variable
        if start_slice >= len(self.height_slices):
            # If the slice ends within the last slice (usual case, unless it
            # has the exact same width the packing area has), add another slice
            # to return to the original height at the end of the rectangle.
            if right < self.packing_area_width:
                self.height_slices.append(
                    Point(right, first_slice_original_height))
        else:  # The rectangle doesn't start on the last slice
            end_slice = bisect_left(self.height_slices, Point(right, 0),
                                    start_slice, len(self.height_slices))

            # Another direct hit on the final slice's end?
            if end_slice > 0:
                del self.height_slices[start_slice:end_slice]
            else:  # No direct hit, rectangle ends inside another slice
                # Make index from negative bisect_left() result
                end_slice = ~end_slice

                # Find out to which height we need to return at the right end of
                # the rectangle
                if end_slice == start_slice:
                    return_height = first_slice_original_height
                else:
                    return_height = self.height_slices[end_slice - 1].y

                # Remove all slices covered by the rectangle and begin a new
                # slice at its end to return back to the height of the slice on
                # which the rectangle ends.
                del self.height_slices[start_slice:end_slice]
                if right < self.packing_area_width:
                    self.height_slices.insert(
                        start_slice, Point(right, return_height))
