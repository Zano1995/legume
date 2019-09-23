import numpy as np

import legume.backend as bd
from .backend import backend as bd


class Lattice(object):
	'''
	Class for constructing a Bravais lattice
	'''

	def __init__(self, *args):
		'''
		Initialize a Bravais lattice.
		If a single argument is passed, then
			- 'square': initializes a square lattice
			- 'hexagonal': initializes a hexagonal lattice
			(lattice constant 1 in both cases)
		If two arguments are passed, they should each be 2-element arrays
		defining the elementary vectors of the lattice
		'''

		(a1, a2) = self._parse_input(*args)
		self.a1 = a1[0:2]
		self.a2 = a2[0:2]

		ec_area = bd.norm(bd.cross(a1, a2))
		a3 = bd.array([0, 0, 1])

		b1 = 2 * np.pi * bd.cross(a2, a3) / bd.dot(a1, bd.cross(a2, a3))
		b2 = 2 * np.pi * bd.cross(a3, a1) / bd.dot(a2, bd.cross(a3, a1))

		bz_area = bd.norm(bd.cross(b1, b2))

		# Reciprocal lattice vectors
		self.b1 = b1[0:2]
		self.b2 = b2[0:2]

		self.ec_area = ec_area  # Elementary cell area
		self.bz_area = bz_area  # Brillouin zone area

	def __repr__(self):
		return "Lattice(a1 = [%.4f, %.4f], a2 = [%.4f, %.4f])" % \
			   (self.a1[0], self.a1[1], self.a2[0], self.a2[1])

	def _parse_input(self, *args):
		if len(args) == 1:
			if args[0] == 'square':
				self.type = 'square'
				a1 = bd.array([1, 0, 0])
				a2 = bd.array([0, 1, 0])
			elif args[0] == 'hexagonal':
				self.type = 'hexagonal'
				a1 = bd.array([0.5, bd.sqrt(3) / 2, 0])
				a2 = bd.array([0.5, -bd.sqrt(3) / 2, 0])
			else:
				raise ValueError("Lattice can be 'square' or 'hexagonal," \
								 "or defined through two primitive vectors.")

		elif len(args) == 2:
			self.type = 'custom'
			a1 = bd.hstack((bd.array(args[0]), 0))
			a2 = bd.hstack((bd.array(args[1]), 0))

		return (a1, a2)

	def xy_grid(self, Nx=100, Ny=100):
		'''
		Define an xy-grid for visualization purposes based on the lattice
		vectors of the PhC (not sure if it works for very weird lattices)
		'''
		ymax = np.abs(max([self.a1[1], self.a2[1]]))
		ymin = -ymax

		xmax = np.abs(max([self.a1[0], self.a2[0]]))
		xmin = -xmax

		return (np.linspace(xmin, xmax, Nx), np.linspace(ymin, ymax, Ny))

	def bz_path(self, pts, ns):
		'''
		Make a path in the Brillouin zone
			- pts is a list of points
			- ns is a list of length either 1 or len(pts) - 1, specifying
				how many points are to be added between each two pts
		'''

		npts = len(pts)
		if npts < 2:
			raise ValueError("At least two points must be given")

		if len(ns) == 1:
			ns = ns[0] * np.ones(npts - 1, dtype=np.int_)
		elif len(ns) == npts - 1:
			ns = np.array(ns)
		else:
			raise ValueError("Length of ns must be either 1 or len(pts) - 1")

		kpoints = np.zeros((2, np.sum(ns) + 1))
		inds = [0]
		count = 0

		for ip in range(npts - 1):
			p1 = self._parse_point(pts[ip])
			p2 = self._parse_point(pts[ip + 1])
			kpoints[:, count:count + ns[ip]] = p1[:, np.newaxis] + np.outer( \
				(p2 - p1), np.linspace(0, 1, ns[ip], endpoint=False))
			count = count + ns[ip]
			inds.append(count)
		kpoints[:, -1] = p2

		path = type('', (), {})()  # Create an "empty" object
		path.kpoints = kpoints
		path.pt_labels = [str(pt) for pt in pts]
		path.pt_inds = inds

		return path

	def _parse_point(self, pt):
		'''
		Returns a numpy array corresponding to a BZ point pt
		'''
		if type(pt) == np.ndarray:
			return pt
		elif type(pt) == str:
			if pt.lower() == 'g' or pt.lower() == 'gamma':
				return np.array([0, 0])

			if pt.lower() == 'x':
				if self.type == 'square':
					return np.array([np.pi, 0])
				else:
					raise ValueError("'X'-point is only defined for lattice" \
									 "initialized as 'square'.")

			if pt.lower() == 'm':
				if self.type == 'square':
					return np.array([np.pi, np.pi])
				elif self.type == 'hexagonal':
					return np.array([np.pi, np.pi / np.sqrt(3)])
				else:
					raise ValueError("'М'-point is only defined for lattice" \
									 "initialized as 'square' or 'hexagonal'.")

			if pt.lower() == 'k':
				if self.type == 'hexagonal':
					return np.array([4 / 3 * np.pi, 0])
				else:
					raise ValueError("'K'-point is only defined for lattice" \
									 "initialized as 'hexagonal'.")

		raise ValueError("Something was wrong with BZ point definition")